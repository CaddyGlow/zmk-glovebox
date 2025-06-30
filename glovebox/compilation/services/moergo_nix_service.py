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
from glovebox.protocols import (
    DockerAdapterProtocol,
    FileAdapterProtocol,
    MetricsProtocol,
)
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
        """Execute Moergo compilation from files."""
        return self._compile_internal(
            keymap_file=keymap_file,
            config_file=config_file,
            keymap_content=None,
            config_content=None,
            output_dir=output_dir,
            config=config,
            keyboard_profile=keyboard_profile,
            progress_callback=progress_callback,
            json_file=json_file,
        )

    def compile_from_content(
        self,
        keymap_content: str,
        config_content: str,
        output_dir: Path,
        config: CompilationConfigUnion,
        keyboard_profile: "KeyboardProfile",
        progress_callback: "CompilationProgressCallback | None" = None,
        json_file: Path | None = None,
    ) -> BuildResult:
        """Execute Moergo compilation from content strings (eliminates temp files)."""
        return self._compile_internal(
            keymap_file=None,
            config_file=None,
            keymap_content=keymap_content,
            config_content=config_content,
            output_dir=output_dir,
            config=config,
            keyboard_profile=keyboard_profile,
            progress_callback=progress_callback,
            json_file=json_file,
        )

    def _compile_internal(
        self,
        output_dir: Path,
        config: CompilationConfigUnion,
        keyboard_profile: "KeyboardProfile",
        keymap_file: Path | None = None,
        config_file: Path | None = None,
        keymap_content: str | None = None,
        config_content: str | None = None,
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
                return self._compile_actual(
                    keymap_file=keymap_file,
                    config_file=config_file,
                    keymap_content=keymap_content,
                    config_content=config_content,
                    output_dir=output_dir,
                    config=config,
                    keyboard_profile=keyboard_profile,
                    progress_callback=progress_callback,
                    json_file=json_file,
                    compilation_start_time=compilation_start_time,
                )
        else:
            return self._compile_actual(
                keymap_file=keymap_file,
                config_file=config_file,
                keymap_content=keymap_content,
                config_content=config_content,
                output_dir=output_dir,
                config=config,
                keyboard_profile=keyboard_profile,
                progress_callback=progress_callback,
                json_file=json_file,
                compilation_start_time=compilation_start_time,
            )

    def _compile_actual(
        self,
        output_dir: Path,
        config: CompilationConfigUnion,
        keyboard_profile: "KeyboardProfile",
        keymap_file: Path | None = None,
        config_file: Path | None = None,
        keymap_content: str | None = None,
        config_content: str | None = None,
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

            # Extract board information dynamically
            board_info = self._extract_board_info_from_config(config)

            # Always create progress coordinator (no conditional checks)
            # TODO: Integrate with simple progress system
            progress_coordinator = None
            # progress_coordinator = create_simple_progress_coordinator(display)

            # Start with initialization phase
            if progress_coordinator:
                if progress_coordinator:
            progress_coordinator.transition_to_phase(
                "initialization", "Setting up build environment"
            )

            # Check/build Docker image with progress
            if progress_coordinator:
                if progress_coordinator:
            progress_coordinator.transition_to_phase(
                "docker_verification", "Verifying Docker image"
            )
            # Set the docker image name for display
            if progress_coordinator:
                if progress_coordinator:
            progress_coordinator.docker_image_name = config.image

            if not self._ensure_docker_image(config, progress_coordinator):
                return BuildResult(success=False, errors=["Docker image setup failed"])

            # Setup workspace with progress
            if progress_coordinator:
                if progress_coordinator:
            progress_coordinator.transition_to_phase(
                "nix_build", "Building Nix environment"
            )
            workspace_path = self._setup_workspace(
                keyboard_profile=keyboard_profile,
                progress_coordinator=progress_coordinator,
                keymap_file=keymap_file,
                config_file=config_file,
                keymap_content=keymap_content,
                config_content=config_content,
            )
            if not workspace_path or not workspace_path.host_path:
                return BuildResult(success=False, errors=["Workspace setup failed"])

            # Run compilation with progress (existing integration)
            if progress_coordinator:
                if progress_coordinator:
            progress_coordinator.transition_to_phase(
                "building", "Starting MoErgo Nix compilation"
            )
            compilation_success = self._run_compilation(
                workspace_path, config, output_dir, progress_coordinator
            )

            # Collect artifacts with progress
            if progress_coordinator:
                if progress_coordinator:
            progress_coordinator.transition_to_phase(
                "cache_saving", "Generating .uf2 files"
            )
            output_files = self._collect_files(
                workspace_path.host_path, output_dir, progress_coordinator
            )

            if not compilation_success:
                return BuildResult(
                    success=False,
                    errors=["Compilation failed"],
                    output_files=output_files,  # Include partial artifacts for debugging
                )

            # Create build-info.json in artifacts directory
            if output_files.artifacts_dir:
                try:
                    import time

                    # Calculate compilation duration
                    compilation_duration = time.time() - compilation_start_time

                    # For content-based compilation, we need the actual content
                    actual_keymap_content = keymap_content
                    actual_config_content = config_content

                    # If we used files instead of content, read them
                    if actual_keymap_content is None and keymap_file is not None:
                        actual_keymap_content = keymap_file.read_text()
                    if actual_config_content is None and config_file is not None:
                        actual_config_content = config_file.read_text()

                    # Only create build info if we have content
                    if (
                        actual_keymap_content is not None
                        and actual_config_content is not None
                    ):
                        create_build_info_file(
                            artifacts_dir=output_files.artifacts_dir,
                            keymap_content=actual_keymap_content,
                            config_content=actual_config_content,
                            repository=config.repository,
                            branch=config.branch,
                            head_hash=None,  # MoErgo doesn't use git workspace like ZMK
                            build_mode="moergo",
                            uf2_files=output_files.uf2_files,
                            compilation_duration=compilation_duration,
                        )
                    else:
                        self.logger.warning(
                            "Cannot create build-info.json: missing content"
                        )
                except Exception as e:
                    self.logger.warning("Failed to create build-info.json: %s", e)

            # Mark compilation as fully complete
            # Signal completion to progress coordinator for 100% display
            if progress_coordinator:
                if progress_coordinator:
            progress_coordinator.complete_all_builds()

            result = BuildResult(
                success=True,
                output_files=output_files,
            )
            # Set unified success messages for MoErgo builds
            result.set_success_messages("moergo_nix", was_cached=False)
            return result

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
        """Execute compilation from JSON layout file (optimized - no temp files)."""
        self.logger.info("Starting JSON to firmware compilation")

        # Use optimized helper to convert JSON to content (eliminates temp files)
        from glovebox.compilation.helpers import convert_json_to_keymap_content

        keymap_content, config_content, conversion_result = (
            convert_json_to_keymap_content(
                json_file=json_file,
                keyboard_profile=keyboard_profile,
                session_metrics=self.session_metrics,
            )
        )

        if not conversion_result.success:
            return conversion_result

        # Ensure content was generated successfully (type safety)
        assert keymap_content is not None, (
            "Keymap content should be generated on success"
        )
        assert config_content is not None, (
            "Config content should be generated on success"
        )

        # Compile directly from content (no temp files needed)
        return self.compile_from_content(
            keymap_content=keymap_content,
            config_content=config_content,
            output_dir=output_dir,
            config=config,
            keyboard_profile=keyboard_profile,
            progress_callback=progress_callback,
            json_file=json_file,
        )

    def validate_config(self, config: CompilationConfigUnion) -> bool:
        """Validate configuration."""
        return isinstance(config, MoergoCompilationConfig) and bool(config.image)

    def check_available(self) -> bool:
        """Check availability."""
        return self.docker_adapter is not None

    def _setup_workspace(
        self,
        keyboard_profile: "KeyboardProfile",
        progress_coordinator: Any,
        keymap_file: Path | None = None,
        config_file: Path | None = None,
        keymap_content: str | None = None,
        config_content: str | None = None,
    ) -> DockerPath | None:
        """Setup temporary workspace from files or content."""
        try:
            if progress_coordinator:
                if progress_coordinator:
            progress_coordinator.update_workspace_progress(
                0, 4, 0, 0, "", "Creating workspace directory"
            )

            workspace_path = DockerPath(
                host_path=Path(tempfile.mkdtemp(prefix="moergo_")),
                container_path="/workspace",
            )
            assert workspace_path.host_path is not None

            config_dir = workspace_path.host_path / "config"
            config_dir.mkdir(parents=True)

            if progress_coordinator:
                if progress_coordinator:
            progress_coordinator.update_workspace_progress(
                1, 4, 0, 0, "glove80.keymap", "Copying keymap file"
            )

            # Handle keymap: either copy from file or write content directly
            if keymap_content is not None:
                # Write content directly (eliminates temp file)
                self.file_adapter.write_text(
                    config_dir / "glove80.keymap", keymap_content
                )
            elif keymap_file is not None:
                # Copy file (backward compatibility)
                import shutil

                shutil.copy2(keymap_file, config_dir / "glove80.keymap")
            else:
                raise ValueError(
                    "Either keymap_file or keymap_content must be provided"
                )

            if progress_coordinator:
                if progress_coordinator:
            progress_coordinator.update_workspace_progress(
                2, 4, 0, 0, "glove80.conf", "Copying config file"
            )

            # Handle config: either copy from file or write content directly
            if config_content is not None:
                # Write content directly (eliminates temp file)
                self.file_adapter.write_text(
                    config_dir / "glove80.conf", config_content
                )
            elif config_file is not None:
                # Copy file (backward compatibility)
                import shutil

                shutil.copy2(config_file, config_dir / "glove80.conf")
            else:
                raise ValueError(
                    "Either config_file or config_content must be provided"
                )

            if progress_coordinator:
                if progress_coordinator:
            progress_coordinator.update_workspace_progress(
                3, 4, 0, 0, "default.nix", "Loading Nix toolchain"
            )

            # Load default.nix from keyboard's toolchain directory
            default_nix_content = keyboard_profile.load_toolchain_file("default.nix")
            if not default_nix_content:
                self.logger.error("Could not load default.nix from keyboard toolchain")
                return None

            self.file_adapter.write_text(
                config_dir / "default.nix", default_nix_content
            )

            if progress_coordinator:
                if progress_coordinator:
            progress_coordinator.update_workspace_progress(
                4, 4, 0, 0, "", "Workspace setup completed"
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
        progress_coordinator: Any,
    ) -> bool:
        """Run Docker compilation."""
        try:
            from glovebox.adapters.docker_adapter import LoggerOutputMiddleware
            from glovebox.models.docker import DockerUserContext
            from glovebox.utils.build_log_middleware import create_build_log_middleware
            from glovebox.utils.stream_process import create_chained_middleware

            middlewares: list[Any] = []

            # Create build log middleware
            build_log_middleware = create_build_log_middleware(output_dir)
            middlewares.append(build_log_middleware)

            # Always add progress middleware (no conditional checks)
            from glovebox.adapters import create_compilation_progress_middleware

            # Create middleware that delegates to existing coordinator with MoErgo-specific patterns
            # MoErgo skips west update, so start directly with building
            middleware = create_compilation_progress_middleware(
                progress_coordinator=progress_coordinator,
                progress_patterns=config.progress_patterns,  # Use MoErgo-specific patterns
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
        self, workspace_path: Path, output_dir: Path, progress_coordinator: Any
    ) -> FirmwareOutputFiles:
        """Collect firmware files from artifacts directory, including partial artifacts for debugging."""
        output_dir.mkdir(parents=True, exist_ok=True)
        uf2_files: list[Path] = []
        artifacts_dir = None
        collected_items = []

        if progress_coordinator:
            progress_coordinator.update_cache_progress(
            "scanning", 25, 100, "Scanning for build artifacts"
        )

        # Look for artifacts directory created by build.sh
        build_artifacts_dir = workspace_path / "artifacts"
        if build_artifacts_dir.exists():
            try:
                # Count items for progress tracking
                items_to_copy = list(build_artifacts_dir.iterdir())
                total_items = len(items_to_copy)

                if progress_coordinator:
                if progress_coordinator:
            progress_coordinator.update_cache_progress(
                    "copying",
                    50,
                    100,
                    f"Copying {total_items} artifacts to output directory",
                )

                # Copy all contents of artifacts directory directly to output directory
                for i, item in enumerate(items_to_copy):
                    try:
                        dest_path = output_dir / item.name
                        if item.is_file():
                            # Handle existing files by removing them first
                            if dest_path.exists():
                                dest_path.unlink()
                            import shutil

                            shutil.copy2(item, dest_path)
                            collected_items.append(f"file: {item.name}")
                        elif item.is_dir():
                            # Handle existing directories by removing them first
                            if dest_path.exists():
                                import shutil

                                shutil.rmtree(dest_path)
                            import shutil

                            shutil.copytree(item, dest_path)
                            collected_items.append(f"directory: {item.name}")

                        # Update progress during copying
                        if i % 5 == 0 or i == total_items - 1:  # Update every 5 items
                            current_progress = 50 + (25 * i // total_items)
                            if progress_coordinator:
                if progress_coordinator:
            progress_coordinator.update_cache_progress(
                                "copying",
                                current_progress,
                                100,
                                f"Copied {i + 1}/{total_items} artifacts",
                            )

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

            if progress_coordinator:
                if progress_coordinator:
            progress_coordinator.update_cache_progress(
                "scanning", 75, 100, "Searching for partial build files"
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
                        import shutil

                        shutil.copy2(partial_file, output_dir / partial_file.name)
                        collected_items.append(f"partial: {partial_file.name}")
                        # Add UF2 files to the list
                        if partial_file.suffix.lower() == ".uf2":
                            uf2_files.append(output_dir / partial_file.name)
                    except Exception as e:
                        self.logger.warning(
                            "Failed to copy partial file %s: %s", partial_file, e
                        )

        if progress_coordinator:
            progress_coordinator.update_cache_progress(
            "completed", 100, 100, f"Collected {len(uf2_files)} firmware files"
        )

        return FirmwareOutputFiles(
            output_dir=output_dir,
            uf2_files=uf2_files,
            artifacts_dir=artifacts_dir,
        )

    def _ensure_docker_image(
        self, config: MoergoCompilationConfig, progress_coordinator: Any
    ) -> bool:
        """Ensure Docker image exists, build if not found."""
        try:
            # Check image existence
            if progress_coordinator:
                if progress_coordinator:
            progress_coordinator.update_cache_progress(
                "checking", 25, 100, "Checking Docker image availability"
            )

            # Generate version-based image tag using glovebox version
            base_image_name = config.image.split(":")[0]
            versioned_tag = config.get_versioned_docker_tag()
            versioned_image_name = base_image_name

            # Check if versioned image exists
            if self.docker_adapter.image_exists(versioned_image_name, versioned_tag):
                self.logger.debug(
                    "Versioned Docker image already exists: %s:%s",
                    versioned_image_name,
                    versioned_tag,
                )
                # Update config to use the versioned image
                config.image = f"{versioned_image_name}:{versioned_tag}"

                if progress_coordinator:
                if progress_coordinator:
            progress_coordinator.update_cache_progress(
                    "completed", 100, 100, "Docker image ready"
                )
                return True

            if progress_coordinator:
                if progress_coordinator:
            progress_coordinator.update_cache_progress(
                "building", 50, 100, f"Building Docker image: {versioned_image_name}"
            )

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

            if progress_coordinator:
                if progress_coordinator:
            progress_coordinator.update_cache_progress(
                "building", 75, 100, f"Building image from {dockerfile_dir}"
            )

            # Build the image with versioned tag using middleware to show progress
            from glovebox.utils.stream_process import DefaultOutputMiddleware

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

                if progress_coordinator:
                if progress_coordinator:
            progress_coordinator.update_cache_progress(
                    "completed", 100, 100, "Docker image built successfully"
                )
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

    def _extract_board_info_from_config(
        self, config: MoergoCompilationConfig
    ) -> dict[str, Any]:
        """Extract board information from MoergoCompilationConfig for progress tracking.

        Args:
            config: MoErgo compilation configuration

        Returns:
            Dictionary with total_boards and board_names keys
        """
        try:
            if config.build_matrix and config.build_matrix.targets:
                board_names = [target.board for target in config.build_matrix.targets]
                total_boards = len(board_names)

                self.logger.info(
                    "Detected %d boards from config: %s (MoErgo builds %d artifacts)",
                    len(config.build_matrix.targets),
                    ", ".join(target.board for target in config.build_matrix.targets),
                    total_boards,
                )

                return {
                    "total_boards": total_boards,
                    "board_names": board_names,
                }
            else:
                # Fallback to default MoErgo boards: left and right only
                self.logger.info(
                    "No build matrix in config, using default MoErgo boards (left + right = 2 artifacts)"
                )
                return {
                    "total_boards": 2,
                    "board_names": ["glove80_lh", "glove80_rh"],
                }

        except Exception as e:
            self.logger.error("Error extracting board info from config: %s", e)
            return {
                "total_boards": 2,
                "board_names": ["glove80_lh", "glove80_rh"],
            }


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
