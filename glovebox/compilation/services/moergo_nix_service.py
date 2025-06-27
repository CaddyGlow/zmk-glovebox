"""Compilation service for the glove80 using docker image form Moergo
with the nix toolchain
"""

import logging
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from glovebox.adapters.docker_adapter import LoggerOutputMiddleware
from glovebox.compilation.models import (
    CompilationConfigUnion,
    MoergoCompilationConfig,
)
from glovebox.compilation.protocols.compilation_protocols import (
    CompilationServiceProtocol,
)
from glovebox.core.file_operations import CompilationProgressCallback
from glovebox.firmware.models import (
    BuildResult,
    FirmwareOutputFiles,
    create_build_info_file,
)
from glovebox.models.docker import DockerUserContext
from glovebox.models.docker_path import DockerPath
from glovebox.protocols import DockerAdapterProtocol, FileAdapterProtocol, MetricsProtocol
from glovebox.utils.build_log_middleware import create_build_log_middleware
from glovebox.utils.stream_process import (
    DefaultOutputMiddleware,
    OutputMiddleware,
    create_chained_middleware,
)


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile


class MoergoNixService(CompilationServiceProtocol):
    """Ultra-simplified Moergo compilation service (<200 lines)."""

    def __init__(
        self,
        docker_adapter: DockerAdapterProtocol,
        file_adapter: FileAdapterProtocol,
        session_metrics: MetricsProtocol,
    ) -> None:
        """Initialize with Docker adapter, file adapter, and session metrics."""
        self.docker_adapter = docker_adapter
        self.file_adapter = file_adapter
        self.session_metrics = session_metrics
        self.logger = logging.getLogger(__name__)

    def compile(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: CompilationConfigUnion,
        keyboard_profile: "KeyboardProfile",
        progress_callback: "CompilationProgressCallback | None" = None,
        json_file: Path | None = None,
    ) -> BuildResult:
        """Execute Moergo compilation."""
        import time

        compilation_start_time = time.time()

        self.logger.info("Starting Moergo compilation")

        # Initialize compilation metrics
        if self.session_metrics:
            compilation_operations = self.session_metrics.Counter(
                "compilation_operations_total",
                "Total compilation operations",
                ["keyboard_name", "firmware_version", "strategy"],
            )
            compilation_duration = self.session_metrics.Histogram(
                "compilation_duration_seconds", "Compilation operation duration"
            )

            compilation_operations.labels(
                keyboard_profile.keyboard_name,
                keyboard_profile.firmware_version or "unknown",
                "moergo",
            ).inc()

            with compilation_duration.time():
                return self._compile_internal(
                    keymap_file,
                    config_file,
                    output_dir,
                    config,
                    keyboard_profile,
                    progress_callback,
                    json_file,
                    compilation_start_time,
                )
        else:
            return self._compile_internal(
                keymap_file,
                config_file,
                output_dir,
                config,
                keyboard_profile,
                progress_callback,
                json_file,
                compilation_start_time,
            )

    def _compile_internal(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: MoergoCompilationConfig,
        keyboard_profile: "KeyboardProfile",
        progress_callback: CompilationProgressCallback | None = None,
        json_file: Path | None = None,
        compilation_start_time: float = 0.0,
    ) -> BuildResult:
        """Internal compilation method with progress tracking."""
        try:
            if not isinstance(config, MoergoCompilationConfig):
                return BuildResult(
                    success=False, errors=["Invalid config type for Moergo compilation"]
                )

            # Create progress coordinator for MoErgo compilation
            progress_coordinator = None
            if progress_callback:
                from glovebox.cli.components.unified_progress_coordinator import (
                    create_unified_progress_coordinator,
                )

                progress_coordinator = create_unified_progress_coordinator(
                    tui_callback=progress_callback,
                    total_boards=2,  # MoErgo typically has left and right halves
                    board_names=["glove80_lh", "glove80_rh"],
                    total_repositories=1,  # MoErgo doesn't use west update
                )

                # Start with building phase since MoErgo doesn't do workspace setup like ZMK
                progress_coordinator.transition_to_phase("building", "Starting MoErgo compilation")

            workspace_path = self._setup_workspace(
                keymap_file, config_file, keyboard_profile
            )
            if not workspace_path or not workspace_path.host_path:
                return BuildResult(success=False, errors=["Workspace setup failed"])

            compilation_success = self._run_compilation(
                workspace_path, config, output_dir, progress_coordinator
            )

            # Always try to collect artifacts, even on build failure (for debugging)
            output_files = self._collect_files(workspace_path.host_path, output_dir)

            if not compilation_success:
                return BuildResult(
                    success=False,
                    errors=["Compilation failed"],
                    output_files=output_files,  # Include partial artifacts for debugging
                )
            # Create build-info.json in artifacts directory
            if output_files.artifacts_dir:
                try:
                    # Calculate compilation duration
                    compilation_duration = time.time() - compilation_start_time

                    create_build_info_file(
                        artifacts_dir=output_files.artifacts_dir,
                        keymap_file=keymap_file,
                        config_file=config_file,
                        json_file=json_file,
                        repository=config.repository,
                        branch=config.branch,
                        head_hash=None,  # MoErgo doesn't use git workspace like ZMK
                        build_mode="moergo",
                        uf2_files=output_files.uf2_files,
                        compilation_duration=compilation_duration,
                    )
                except Exception as e:
                    self.logger.warning("Failed to create build-info.json: %s", e)

            return BuildResult(
                success=True,
                output_files=output_files,
                messages=[f"Generated {len(output_files.uf2_files)} firmware files"],
            )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Compilation failed: %s", e, exc_info=exc_info)
            return BuildResult(success=False, errors=[str(e)])

    def compile_from_json(
        self,
        json_file: Path,
        output_dir: Path,
        config: CompilationConfigUnion,
        keyboard_profile: "KeyboardProfile",
        progress_callback: CompilationProgressCallback | None = None,
    ) -> BuildResult:
        """Execute compilation from JSON layout file."""
        self.logger.info("Starting JSON to firmware compilation")

        try:
            # Convert JSON to keymap/config files first
            from glovebox.adapters import create_file_adapter, create_template_adapter
            from glovebox.layout import (
                create_behavior_registry,
                create_grid_layout_formatter,
                create_layout_component_service,
                create_layout_display_service,
                create_layout_service,
            )
            from glovebox.layout.behavior.formatter import BehaviorFormatterImpl
            from glovebox.layout.zmk_generator import ZmkFileContentGenerator

            # Create all dependencies for layout service
            file_adapter = create_file_adapter()
            template_adapter = create_template_adapter()
            behavior_registry = create_behavior_registry()
            behavior_formatter = BehaviorFormatterImpl(behavior_registry)
            dtsi_generator = ZmkFileContentGenerator(behavior_formatter)
            layout_generator = create_grid_layout_formatter()
            component_service = create_layout_component_service(file_adapter)
            layout_display_service = create_layout_display_service(layout_generator)

            layout_service = create_layout_service(
                file_adapter=file_adapter,
                template_adapter=template_adapter,
                behavior_registry=behavior_registry,
                component_service=component_service,
                layout_service=layout_display_service,
                behavior_formatter=behavior_formatter,
                dtsi_generator=dtsi_generator,
            )

            # Create temporary directory for intermediate files
            with tempfile.TemporaryDirectory(prefix="json_to_keymap_") as temp_dir:
                temp_path = Path(temp_dir)
                output_prefix = temp_path / "layout"

                # Generate keymap and config files from JSON
                # Use session_metrics which is always available
                layout_session_metrics = self.session_metrics

                layout_result = layout_service.generate_from_file(
                    profile=keyboard_profile,
                    json_file_path=json_file,
                    output_file_prefix=str(output_prefix),
                    session_metrics=layout_session_metrics,
                    force=True,
                )

                if not layout_result.success:
                    return BuildResult(
                        success=False,
                        errors=[
                            f"JSON to keymap conversion failed: {', '.join(layout_result.errors)}"
                        ],
                    )

                # Get the generated files
                output_files = layout_result.get_output_files()
                keymap_file = output_files.get("keymap")
                config_file = output_files.get("conf")

                if not keymap_file or not config_file:
                    return BuildResult(
                        success=False,
                        errors=["Failed to generate keymap or config files from JSON"],
                    )

                # Now compile using the generated files
                return self.compile(
                    keymap_file=Path(keymap_file),
                    config_file=Path(config_file),
                    output_dir=output_dir,
                    config=config,
                    keyboard_profile=keyboard_profile,
                    json_file=json_file,
                )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("JSON compilation failed: %s", e, exc_info=exc_info)
            return BuildResult(success=False, errors=[str(e)])

    def validate_config(self, config: CompilationConfigUnion) -> bool:
        """Validate configuration."""
        return isinstance(config, MoergoCompilationConfig) and bool(config.image)

    def check_available(self) -> bool:
        """Check availability."""
        return self.docker_adapter is not None

    def _setup_workspace(
        self, keymap_file: Path, config_file: Path, keyboard_profile: "KeyboardProfile"
    ) -> DockerPath | None:
        """Setup temporary workspace."""
        try:
            workspace_path = DockerPath(
                host_path=Path(tempfile.mkdtemp(prefix="moergo_")),
                container_path="/workspace",
            )
            assert workspace_path.host_path is not None

            config_dir = workspace_path.host_path / "config"
            config_dir.mkdir(parents=True)

            # Copy files with Moergo expected names
            shutil.copy2(keymap_file, config_dir / "glove80.keymap")
            shutil.copy2(config_file, config_dir / "glove80.conf")

            # Load default.nix from keyboard's toolchain directory
            default_nix_content = keyboard_profile.load_toolchain_file("default.nix")
            if not default_nix_content:
                self.logger.error("Could not load default.nix from keyboard toolchain")
                return None

            self.file_adapter.write_text(
                config_dir / "default.nix", default_nix_content
            )
            return workspace_path
        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Workspace setup failed: %s", e, exc_info=exc_info)
            return None

    def _run_compilation(
        self,
        workspace_path: DockerPath,
        config: MoergoCompilationConfig,
        output_dir: Path,
        progress_coordinator: Any = None,
    ) -> bool:
        """Run Docker compilation."""
        try:
            # Check if Docker image exists, build if not
            if not self._ensure_docker_image(config):
                self.logger.error("Failed to ensure Docker image is available")
                return False

            middlewares: list[OutputMiddleware[Any]] = []

            # Create build log middleware
            build_log_middleware = create_build_log_middleware(output_dir)
            middlewares.append(build_log_middleware)

            # Add progress middleware if coordinator is available
            if progress_coordinator:
                from glovebox.adapters import create_compilation_progress_middleware

                # Create middleware that delegates to existing coordinator
                # MoErgo skips west update, so start directly with building
                middleware = create_compilation_progress_middleware(
                    progress_coordinator=progress_coordinator,
                    skip_west_update=True,  # MoErgo doesn't use west update
                )
                middlewares.append(middleware)

            middlewares.append(LoggerOutputMiddleware(self.logger))

            # For Moergo, disable user mapping and pass user info via environment
            user_context = DockerUserContext.detect_current_user()
            user_context.enable_user_mapping = False

            # Build environment with user information and ZMK repository config
            environment = {
                "PUID": str(user_context.uid),
                "PGID": str(user_context.gid),
                "REPO": config.repository,
                "BRANCH": config.branch,
            }

            try:
                return_code, _, stderr = self.docker_adapter.run_container(
                    image=config.image,
                    command=["build.sh"],  # Use the build script, not direct nix-build
                    volumes=[workspace_path.vol()],
                    environment=environment,
                    user_context=user_context,
                    middleware=create_chained_middleware(middlewares),
                )
            finally:
                # Always close the build log middleware
                build_log_middleware.close()

            if return_code != 0:
                self.logger.error("Build failed with exit code %d", return_code)
                return False

            return True
        except Exception as e:
            self.logger.error("Docker execution failed: %s", e)
            return False

    def _collect_files(
        self, workspace_path: Path, output_dir: Path
    ) -> FirmwareOutputFiles:
        """Collect firmware files from artifacts directory, including partial artifacts for debugging."""
        output_dir.mkdir(parents=True, exist_ok=True)
        uf2_files: list[Path] = []
        artifacts_dir = None
        collected_items = []

        # Look for artifacts directory created by build.sh
        build_artifacts_dir = workspace_path / "artifacts"
        if build_artifacts_dir.exists():
            try:
                # Copy all contents of artifacts directory directly to output directory
                for item in build_artifacts_dir.iterdir():
                    try:
                        dest_path = output_dir / item.name
                        if item.is_file():
                            # Handle existing files by removing them first
                            if dest_path.exists():
                                dest_path.unlink()
                            shutil.copy2(item, dest_path)
                            collected_items.append(f"file: {item.name}")
                        elif item.is_dir():
                            # Handle existing directories by removing them first
                            if dest_path.exists():
                                shutil.rmtree(dest_path)
                            shutil.copytree(item, dest_path)
                            collected_items.append(f"directory: {item.name}")
                    except Exception as e:
                        self.logger.warning("Failed to copy artifact %s: %s", item, e)

                artifacts_dir = output_dir

                # Find all UF2 firmware files
                for uf2_file in output_dir.glob("*.uf2"):
                    uf2_files.append(uf2_file)
                    filename_lower = uf2_file.name.lower()
                    if "lh" in filename_lower or "lf" in filename_lower:
                        self.logger.debug("Found left hand UF2: %s", uf2_file)
                    elif "rh" in filename_lower:
                        self.logger.debug("Found right hand UF2: %s", uf2_file)
                    else:
                        self.logger.debug("Found UF2 file: %s", uf2_file)

                self.logger.info(
                    "Collected %d Moergo artifacts: %s",
                    len(collected_items),
                    ", ".join(collected_items),
                )
            except Exception as e:
                self.logger.error(
                    "Error collecting artifacts from %s: %s", build_artifacts_dir, e
                )
        else:
            self.logger.warning(
                "No artifacts directory found at %s - checking for partial files",
                build_artifacts_dir,
            )

            # Even without artifacts directory, check for any generated files in workspace
            partial_files: list[Path] = []
            for pattern in ["*.uf2", "*.log", "*.json", "*.dts", "*.h"]:
                partial_files.extend(workspace_path.glob(f"**/{pattern}"))

            if partial_files:
                self.logger.info(
                    "Found %d partial files for debugging: %s",
                    len(partial_files),
                    [f.name for f in partial_files],
                )
                for partial_file in partial_files:
                    try:
                        shutil.copy2(partial_file, output_dir / partial_file.name)
                        collected_items.append(f"partial: {partial_file.name}")
                        # Add UF2 files to the list
                        if partial_file.suffix.lower() == ".uf2":
                            uf2_files.append(output_dir / partial_file.name)
                    except Exception as e:
                        self.logger.warning(
                            "Failed to copy partial file %s: %s", partial_file, e
                        )

        return FirmwareOutputFiles(
            output_dir=output_dir,
            uf2_files=uf2_files,
            artifacts_dir=artifacts_dir,
        )

    def _ensure_docker_image(self, config: MoergoCompilationConfig) -> bool:
        """Ensure Docker image exists, build if not found."""
        try:
            # Generate version-based image tag using glovebox version
            versioned_image_name, versioned_tag = self._get_versioned_image_name(config)

            # Check if versioned image exists
            if self.docker_adapter.image_exists(versioned_image_name, versioned_tag):
                self.logger.debug(
                    "Versioned Docker image already exists: %s:%s",
                    versioned_image_name,
                    versioned_tag,
                )
                # Update config to use the versioned image
                config.image = f"{versioned_image_name}:{versioned_tag}"
                return True

            self.logger.info(
                "Docker image not found, building versioned image: %s:%s",
                versioned_image_name,
                versioned_tag,
            )

            # Get Dockerfile directory from keyboard profile
            keyboard_profile = self._get_keyboard_profile_for_dockerfile()
            if not keyboard_profile:
                self.logger.error(
                    "Cannot determine keyboard profile for Dockerfile location"
                )
                return False

            dockerfile_dir = keyboard_profile.get_keyboard_directory()
            if not dockerfile_dir:
                self.logger.error("Cannot find keyboard directory for Dockerfile")
                return False

            dockerfile_dir = dockerfile_dir / "toolchain"
            if not dockerfile_dir.exists():
                self.logger.error("Toolchain directory not found: %s", dockerfile_dir)
                return False

            # Build the image with versioned tag using middleware to show progress
            middleware = DefaultOutputMiddleware()
            result: tuple[int, list[str], list[str]] = self.docker_adapter.build_image(
                dockerfile_dir=dockerfile_dir,
                image_name=versioned_image_name,
                image_tag=versioned_tag,
                middleware=middleware,
            )

            if result[0] == 0:
                self.logger.info(
                    "Successfully built versioned Docker image: %s:%s",
                    versioned_image_name,
                    versioned_tag,
                )
                # Update config to use the versioned image
                config.image = f"{versioned_image_name}:{versioned_tag}"
                return True
            else:
                self.logger.error(
                    "Failed to build Docker image: %s:%s",
                    versioned_image_name,
                    versioned_tag,
                )
                return False

        except Exception as e:
            self.logger.error("Error ensuring Docker image: %s", e)
            return False

    def _get_versioned_image_name(
        self, config: MoergoCompilationConfig
    ) -> tuple[str, str]:
        """Generate versioned image name and tag based on glovebox version."""
        # Get base image name (remove any existing tag)
        base_image_name = config.image.split(":")[0]

        # Get glovebox version for tagging
        try:
            from glovebox._version import __version__

            # Convert version to valid Docker tag (replace + with -, remove invalid chars)
            docker_tag = __version__.replace("+", "-").replace("/", "-")
            return base_image_name, docker_tag
        except ImportError:
            # Fallback if version module not available
            self.logger.warning("Could not import glovebox version, using 'latest' tag")
            return base_image_name, "latest"

    def _get_keyboard_profile_for_dockerfile(self) -> "KeyboardProfile | None":
        """Get keyboard profile for accessing Dockerfile location."""
        try:
            # For Moergo compilation, we know it's typically glove80
            from glovebox.config.keyboard_profile import create_keyboard_profile

            # Create a keyboard-only profile (no firmware needed for Dockerfile access)
            # Uses unified function that always includes include-aware loading
            return create_keyboard_profile("glove80")
        except Exception as e:
            self.logger.error("Failed to create keyboard profile: %s", e)
            return None


def create_moergo_nix_service(
    docker_adapter: DockerAdapterProtocol,
    file_adapter: FileAdapterProtocol,
    session_metrics: MetricsProtocol,
) -> MoergoNixService:
    """Create Moergo nix service with session metrics for progress tracking.

    Args:
        docker_adapter: Docker adapter for container operations
        file_adapter: File adapter for file operations
        session_metrics: Session metrics for tracking operations

    Returns:
        Configured MoergoNixService instance
    """
    return MoergoNixService(docker_adapter, file_adapter, session_metrics)
