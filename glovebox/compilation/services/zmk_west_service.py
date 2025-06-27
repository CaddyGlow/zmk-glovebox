"""ZMK config with west compilation service."""

import logging
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from glovebox.adapters.docker_adapter import LoggerOutputMiddleware
from glovebox.cli.components.unified_progress_coordinator import (
    UnifiedCompilationProgressCoordinator,
)
from glovebox.compilation.cache.compilation_build_cache_service import (
    CompilationBuildCacheService,
)
from glovebox.compilation.cache.workspace_cache_service import (
    ZmkWorkspaceCacheService,
)
from glovebox.compilation.models import (
    CompilationConfigUnion,
    ZmkCompilationConfig,
)
from glovebox.compilation.models.build_matrix import BuildMatrix
from glovebox.compilation.protocols.compilation_protocols import (
    CompilationServiceProtocol,
)
from glovebox.compilation.services.workspace_setup_service import (
    WorkspaceSetupService,
    create_workspace_setup_service,
)
from glovebox.compilation.services.zmk_cache_service import (
    ZmkCacheService,
    create_zmk_cache_service,
)
from glovebox.config.user_config import UserConfig
from glovebox.core.cache.cache_manager import CacheManager
from glovebox.core.cache.models import CacheKey
from glovebox.core.file_operations import (
    CompilationProgress,
    CompilationProgressCallback,
    FileCopyService,
    create_copy_service,
)
from glovebox.firmware.models import (
    BuildResult,
    FirmwareOutputFiles,
    create_build_info_file,
)
from glovebox.models.docker import DockerUserContext
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


class ZmkWestService(CompilationServiceProtocol):
    """Ultra-simplified ZMK config compilation service with intelligent caching."""

    def __init__(
        self,
        docker_adapter: DockerAdapterProtocol,
        user_config: UserConfig,
        file_adapter: FileAdapterProtocol,
        cache_manager: CacheManager,
        session_metrics: MetricsProtocol,
        workspace_setup_service: WorkspaceSetupService | None = None,
        cache_service: ZmkCacheService | None = None,
        copy_service: FileCopyService | None = None,
    ) -> None:
        """Initialize with Docker adapter, user config, file adapter, cache services, and metrics."""
        self.docker_adapter = docker_adapter
        self.user_config = user_config
        self.file_adapter = file_adapter
        self.cache_manager = cache_manager
        self.session_metrics = session_metrics
        self.logger = logging.getLogger(__name__)
        self.copy_service = copy_service or create_copy_service(
            use_pipeline=True, max_workers=3
        )

        # Initialize services
        self.workspace_setup_service = (
            workspace_setup_service
            or create_workspace_setup_service(
                file_adapter=file_adapter,
                session_metrics=session_metrics,
                copy_service=self.copy_service,
            )
        )

        self.cache_service = cache_service or create_zmk_cache_service(
            user_config=user_config,
            cache_manager=cache_manager,
            session_metrics=session_metrics,
        )

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
        """Execute ZMK compilation."""
        self.logger.info("Starting ZMK config compilation")

        # Initialize compilation metrics if SessionMetrics available
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
                "zmk_config",
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
            )

    def _compile_internal(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: CompilationConfigUnion,
        keyboard_profile: "KeyboardProfile",
        progress_callback: CompilationProgressCallback | None = None,
        json_file: Path | None = None,
    ) -> BuildResult:
        """Execute ZMK compilation."""
        import time

        compilation_start_time = time.time()

        try:
            if not isinstance(config, ZmkCompilationConfig):
                return BuildResult(
                    success=False, errors=["Invalid config type for ZMK compilation"]
                )

            self.logger.info("%s@%s", config.repository, config.branch)
            # Initialize cache metrics
            cache_operations = None
            cache_duration = None
            if self.session_metrics:
                cache_operations = self.session_metrics.Counter(
                    "build_cache_operations_total",
                    "Total build cache operations",
                    ["operation", "result"],
                )
                cache_duration = self.session_metrics.Histogram(
                    "build_cache_operation_duration_seconds",
                    "Build cache operation duration",
                )

            # Try to use cached build result first (most specific cache)
            if cache_duration:
                with cache_duration.time():
                    cached_build_path = self.cache_service.get_cached_build_result(
                        keymap_file, config_file, config
                    )
            else:
                cached_build_path = self.cache_service.get_cached_build_result(
                    keymap_file, config_file, config
                )

            if cached_build_path:
                if cache_operations:
                    cache_operations.labels("lookup", "hit").inc()

                # Create progress coordinator for cache restoration display
                progress_coordinator = None
                if progress_callback:
                    from glovebox.cli.components.unified_progress_coordinator import (
                        create_unified_progress_coordinator,
                    )

                    progress_coordinator = create_unified_progress_coordinator(
                        tui_callback=progress_callback,
                        total_boards=1,  # Not relevant for cache restoration
                        board_names=[],
                        total_repositories=1,  # Single cache operation
                    )

                    # Show cache restoration progress
                    progress_coordinator.transition_to_phase(
                        "cache_restoration", "Restoring cached build"
                    )
                    progress_coordinator.update_cache_progress(
                        "restoring", 50, 100, "Loading cached build artifacts"
                    )

                self.logger.info(
                    "Found cached build - copying artifacts and skipping compilation"
                )

                if progress_coordinator:
                    progress_coordinator.update_cache_progress(
                        "copying", 75, 100, "Copying cached artifacts"
                    )

                output_files = self._collect_files(cached_build_path, output_dir)

                if progress_coordinator:
                    progress_coordinator.update_cache_progress(
                        "completed", 100, 100, "Cache restoration completed"
                    )

                return BuildResult(
                    success=True,
                    output_files=output_files,
                    messages=["Used cached build result"],
                )

            if cache_operations:
                cache_operations.labels("lookup", "miss").inc()

            # Create unified progress coordinator early for workspace setup
            progress_coordinator = None
            if progress_callback:
                from glovebox.cli.components.unified_progress_coordinator import (
                    create_unified_progress_coordinator,
                )

                # Extract board information for progress tracking
                board_info = self._extract_board_info_from_config(config)

                progress_coordinator = create_unified_progress_coordinator(
                    tui_callback=progress_callback,
                    total_boards=board_info["total_boards"],
                    board_names=board_info["board_names"],
                    total_repositories=39,  # Default repository count
                )

            # Try to use cached workspace
            workspace_path, cache_used, cache_type = (
                self.workspace_setup_service.get_or_create_workspace(
                    keymap_file,
                    config_file,
                    config,
                    self.cache_service.get_cached_workspace,
                    progress_callback,
                    progress_coordinator,
                )
            )
            if not workspace_path:
                self.logger.error("Workspace setup failed")
                return BuildResult(success=False, errors=["Workspace setup failed"])

            # Run compilation
            if self.session_metrics:
                docker_operations = self.session_metrics.Counter(
                    "docker_operations_total",
                    "Total Docker operations",
                    ["operation", "result"],
                )
                docker_duration = self.session_metrics.Histogram(
                    "docker_operation_duration_seconds", "Docker operation duration"
                )
                with docker_duration.time():
                    compilation_success = self._run_compilation(
                        workspace_path,
                        config,
                        output_dir,
                        cache_used,
                        cache_type,
                        progress_callback,
                        progress_coordinator,
                    )
                if compilation_success:
                    docker_operations.labels("compilation", "success").inc()
                else:
                    docker_operations.labels("compilation", "failed").inc()
            else:
                compilation_success = self._run_compilation(
                    workspace_path,
                    config,
                    output_dir,
                    cache_used,
                    cache_type,
                    progress_callback,
                    progress_coordinator,
                )

            # Cache workspace dependencies if it was created fresh (not from cache)
            # As per user request: "we never update the two cache once they are created"
            if not cache_used:
                self.cache_service.cache_workspace(
                    workspace_path, config, progress_coordinator
                )
            elif (
                cache_type == "repo_only" and self.cache_service.workspace_cache_service
            ):
                # Update progress coordinator for workspace cache saving
                self.cache_service.cache_workspace_repo_branch_only(
                    workspace_path, config, progress_coordinator
                )

            # Always try to collect artifacts, even on build failure (for debugging)
            if self.session_metrics:
                artifact_duration = self.session_metrics.Histogram(
                    "artifact_collection_duration_seconds",
                    "Artifact collection duration",
                )
                with artifact_duration.time():
                    output_files = self._collect_files(workspace_path, output_dir)
            else:
                output_files = self._collect_files(workspace_path, output_dir)

            if not compilation_success:
                self.logger.error(
                    "Compilation failed, returning partial results for debugging"
                )
                return BuildResult(
                    success=False,
                    errors=["Compilation failed"],
                    output_files=output_files,  # Include partial artifacts for debugging
                )

            # Create build-info.json in artifacts directory
            if output_files.artifacts_dir:
                try:
                    # Get git head hash from the workspace if available
                    head_hash = None
                    git_dir = workspace_path / "zmk" / ".git"
                    if git_dir.exists():
                        try:
                            head_file = git_dir / "HEAD"
                            if head_file.exists():
                                head_ref = head_file.read_text().strip()
                                if head_ref.startswith("ref: "):
                                    # It's a reference, resolve it
                                    ref_path = git_dir / head_ref[5:]
                                    if ref_path.exists():
                                        head_hash = ref_path.read_text().strip()
                                else:
                                    # It's a direct hash
                                    head_hash = head_ref
                        except Exception as e:
                            self.logger.debug("Failed to get git head hash: %s", e)

                    # Calculate compilation duration
                    compilation_duration = time.time() - compilation_start_time

                    create_build_info_file(
                        artifacts_dir=output_files.artifacts_dir,
                        keymap_file=keymap_file,
                        config_file=config_file,
                        json_file=json_file,
                        repository=config.repository,
                        branch=config.branch,
                        head_hash=head_hash,
                        build_mode="zmk_config",
                        uf2_files=output_files.uf2_files,
                        compilation_duration=compilation_duration,
                    )
                except Exception as e:
                    self.logger.warning("Failed to create build-info.json: %s", e)

            build_result = BuildResult(
                success=True,
                output_files=output_files,
                messages=[f"Generated {len(output_files.uf2_files)} firmware files"],
            )

            # Cache the successful build result
            self.cache_service.cache_build_result(
                keymap_file, config_file, config, workspace_path, progress_coordinator
            )

            # Record final compilation metrics
            if self.session_metrics:
                artifacts_generated = self.session_metrics.Gauge(
                    "artifacts_generated", "Number of artifacts generated"
                )
                firmware_size = self.session_metrics.Gauge(
                    "firmware_size_bytes", "Firmware file size in bytes"
                )

                artifacts_generated.set(len(output_files.uf2_files))
                # Calculate total firmware size from all UF2 files
                total_firmware_size = sum(
                    uf2_file.stat().st_size
                    for uf2_file in output_files.uf2_files
                    if uf2_file.exists()
                )
                firmware_size.set(total_firmware_size)

            self.logger.info("ZMK compilation completed successfully")
            return build_result

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
                    progress_callback=progress_callback,
                    json_file=json_file,
                )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("JSON compilation failed: %s", e, exc_info=exc_info)
            return BuildResult(success=False, errors=[str(e)])

    def validate_config(self, config: CompilationConfigUnion) -> bool:
        """Validate configuration."""
        return isinstance(config, ZmkCompilationConfig) and bool(config.image)

    def check_available(self) -> bool:
        """Check availability."""
        return self.docker_adapter is not None

    def _run_compilation(
        self,
        workspace_path: Path,
        config: ZmkCompilationConfig,
        output_dir: Path,
        cache_was_used: bool = False,
        cache_type: str | None = None,
        progress_callback: CompilationProgressCallback | None = None,
        progress_coordinator: Any = None,
    ) -> bool:
        """Run Docker compilation with intelligent west update logic."""
        try:
            # Check if Docker image exists, build if not
            if not self._ensure_docker_image(config):
                self.logger.error("Failed to ensure Docker image is available")
                return False

            # Generate proper build commands using build matrix
            build_commands = self._generate_build_commands(workspace_path, config)
            if not build_commands:
                return False

            # Build base commands with conditional west initialization and update
            base_commands = ["cd /workspace"]

            # Check if workspace is already initialized (has .west/config)
            west_config_file = workspace_path / ".west" / "config"
            workspace_initialized = west_config_file.exists()

            if workspace_initialized:
                self.logger.info(
                    "Workspace already initialized (found .west/config), skipping west init"
                )
            else:
                self.logger.info("Initializing workspace with west init")
                base_commands.append("west init -l config")

            # Only run west update if needed based on cache usage and type
            if not cache_was_used:
                base_commands.append("west update")
            else:
                self.logger.info("Skipping west update for cached workspace")

            # Always run west zephyr-export to set up Zephyr environment variables
            base_commands.append("west zephyr-export")

            base_commands.append("west status")
            base_commands.append("(cd modules/zmk && git rev-parse HEAD)")

            all_commands = base_commands + build_commands

            # Use current user context to avoid permission issues
            user_context = DockerUserContext.detect_current_user()

            self.logger.info("Running Docker compilation")

            # Create progress middleware if progress coordinator is provided
            middlewares: list[OutputMiddleware[Any]] = []

            # Create build log middleware
            build_log_middleware = create_build_log_middleware(output_dir)

            # Add build log middleware first to capture all output
            middlewares.append(build_log_middleware)

            if progress_coordinator:
                from glovebox.adapters import create_compilation_progress_middleware

                # Create middleware that delegates to existing coordinator
                middleware = create_compilation_progress_middleware(
                    progress_coordinator=progress_coordinator,
                    skip_west_update=cache_was_used,  # Skip west update if cache was used
                )

                middlewares.append(middleware)

            middlewares.append(LoggerOutputMiddleware(self.logger))

            chained = create_chained_middleware(middlewares)
            try:
                result: tuple[int, list[str], list[str]] = (
                    self.docker_adapter.run_container(
                        image=config.image,
                        command=["sh", "-c", "set -xeu; " + " && ".join(all_commands)],
                        volumes=[(str(workspace_path), "/workspace")],
                        environment={},  # {"JOBS": "4"},
                        user_context=user_context,
                        middleware=chained,
                    )
                )
                return_code, stdout, stderr = result

                if return_code != 0:
                    self.logger.error("Build failed with exit code %d", return_code)
                    return False

                self.logger.info("Build completed successfully")
                return True
            finally:
                # Always close the build log middleware
                build_log_middleware.close()
        except Exception as e:
            self.logger.error("Docker execution failed: %s", e)
            return False

    def _generate_build_commands(
        self, workspace_path: Path, config: ZmkCompilationConfig
    ) -> list[str]:
        """Generate west build commands from build matrix."""
        try:
            config_path = workspace_path / "config"
            app_relative_path = Path("zmk/app")

            build_yaml = workspace_path / "build.yaml"
            if not build_yaml.exists():
                self.logger.error("build.yaml not found")
                return []

            # Load and parse build matrix
            build_matrix = BuildMatrix.from_yaml(build_yaml)

            build_commands: list[str] = []

            for target in build_matrix.targets:
                build_dir = f"{target.artifact_name}"

                # Build west command
                cmd_parts = [
                    "west build",
                    f"-s {app_relative_path}",
                    f"-b {target.board}",
                    f"-d {build_dir}",
                    "--",
                ]

                # Add CMake arguments
                cmake_args = [f"-DZMK_CONFIG={config_path}"]
                if target.shield:
                    cmake_args.append(f"-DSHIELD={target.shield}")
                if target.cmake_args:
                    cmake_args.extend(target.cmake_args)
                if target.snippet:
                    cmake_args.append(f"-DZMK_EXTRA_MODULES={target.snippet}")

                cmd_parts.extend(cmake_args)
                build_commands.append(" ".join(cmd_parts))

            self.logger.info("Generated %d build commands", len(build_commands))
            return build_commands

        except Exception as e:
            self.logger.error("Failed to generate build commands: %s", e)
            return []

    def _extract_board_info_from_config(
        self, config: ZmkCompilationConfig
    ) -> dict[str, Any]:
        """Extract board information from ZmkCompilationConfig for early progress tracking."""
        try:
            # Extract board names from build matrix in config
            if config.build_matrix and config.build_matrix.targets:
                board_names = [target.board for target in config.build_matrix.targets]
                total_boards = len(board_names)

                self.logger.info(
                    "Detected %d boards from config: %s",
                    total_boards,
                    ", ".join(board_names),
                )

                return {
                    "total_boards": total_boards,
                    "board_names": board_names,
                }
            else:
                # Fallback to default single board
                self.logger.info(
                    "No build matrix in config, using default single board"
                )
                return {"total_boards": 1, "board_names": []}

        except Exception as e:
            self.logger.error("Error extracting board info from config: %s", e)
            return {"total_boards": 1, "board_names": []}

    def _collect_files(
        self, workspace_path: Path, output_dir: Path
    ) -> FirmwareOutputFiles:
        """Collect firmware files from build directories determined by build matrix."""
        output_dir.mkdir(parents=True, exist_ok=True)
        uf2_files: list[Path] = []
        artifacts_dir = None
        collected_items = []

        try:
            # Use build matrix resolver to determine expected build directories
            build_yaml = workspace_path / "build.yaml"
            if not build_yaml.exists():
                self.logger.error(
                    "build.yaml not found, cannot determine build directories"
                )
                return FirmwareOutputFiles(
                    output_dir=output_dir, uf2_files=[], artifacts_dir=None
                )

            build_matrix = BuildMatrix.from_yaml(build_yaml)

            # Look for build directories based on build matrix targets and copy artifacts
            for target in build_matrix.targets:
                build_dir_name = target.artifact_name
                build_path = workspace_path / build_dir_name
                if not build_path.is_dir():
                    self.logger.warning(
                        "Expected build directory not found: %s", build_path
                    )
                    continue

                try:
                    cur_build_out = output_dir / build_dir_name
                    cur_build_out.mkdir(parents=True, exist_ok=True)

                    if artifacts_dir is None:
                        artifacts_dir = output_dir

                    # Copy firmware files and other artifacts
                    build_collected = self._copy_build_artifacts(
                        build_path, cur_build_out, build_dir_name
                    )
                    collected_items.extend(build_collected)

                except Exception as e:
                    self.logger.warning(
                        "Failed to copy build directory %s: %s", build_path, e
                    )

            # After copying all artifacts, find UF2 files at the base of output directory
            for uf2_file in output_dir.glob("*.uf2"):
                uf2_files.append(uf2_file)
                filename_lower = uf2_file.name.lower()
                if "lh" in filename_lower or "lf" in filename_lower:
                    self.logger.debug("Found left hand UF2: %s", uf2_file)
                elif "rh" in filename_lower:
                    self.logger.debug("Found right hand UF2: %s", uf2_file)
                else:
                    self.logger.debug("Found UF2 file: %s", uf2_file)

        except Exception as e:
            self.logger.error(
                "Failed to resolve build matrix for artifact collection: %s", e
            )

        if collected_items:
            self.logger.info("Collected %d ZMK artifacts", len(collected_items))
        else:
            self.logger.warning("No build artifacts found in workspace")

        return FirmwareOutputFiles(
            output_dir=output_dir,
            uf2_files=uf2_files,
            artifacts_dir=artifacts_dir,
        )

    def _copy_build_artifacts(
        self, build_path: Path, cur_build_out: Path, build_dir_name: str
    ) -> list[str]:
        """Copy artifacts from a single build directory."""
        collected_items = []

        # Define file mappings: [source_path_from_zephyr, destination_filename]
        file_mappings = [
            # Firmware files
            ["zmk.uf2", "zmk.uf2"],
            ["zmk.hex", "zmk.hex"],
            ["zmk.bin", "zmk.bin"],
            ["zmk.elf", "zmk.elf"],
            # Configuration and debug files
            [".config", "zmk.kconfig"],
            ["zephyr.dts", "zmk.dts"],
            ["zephyr.dts.pre", "zmk.dts.pre"],
            ["include/generated/devicetree_generated.h", "devicetree_generated.h"],
        ]

        for src_path, dst_filename in file_mappings:
            src_file = build_path / "zephyr" / src_path
            dst_file = cur_build_out / dst_filename

            if src_file.exists():
                try:
                    shutil.copy2(src_file, dst_file)
                    collected_items.append(f"{build_dir_name}/{dst_filename}")
                except Exception as e:
                    self.logger.warning(
                        "Failed to copy %s to %s: %s", src_file, dst_file, e
                    )

        # Copy UF2 to base output directory with build directory name
        uf2_source = build_path / "zephyr" / "zmk.uf2"
        if uf2_source.exists():
            base_uf2 = cur_build_out.parent / f"{build_dir_name}.uf2"
            try:
                shutil.copy2(uf2_source, base_uf2)
                collected_items.append(f"{build_dir_name}.uf2")
            except Exception as e:
                self.logger.warning("Failed to copy UF2 to base: %s", e)

        return collected_items

    def _ensure_docker_image(self, config: ZmkCompilationConfig) -> bool:
        """Ensure Docker image exists, pull if not found."""
        try:
            # Parse image name and tag
            image_parts = config.image.split(":")
            image_name = image_parts[0]
            image_tag = image_parts[1] if len(image_parts) > 1 else "latest"

            # Check cache for recent image verification
            image_cache_key = CacheKey.from_parts("docker_image", image_name, image_tag)
            if self.cache_manager:
                cached_verification = self.cache_manager.get(image_cache_key)

                if cached_verification:
                    return True

            # Check if image exists
            if self.docker_adapter.image_exists(image_name, image_tag):
                # Cache verification for 1 hour to avoid repeated checks
                if self.cache_manager:
                    self.cache_manager.set(image_cache_key, True, ttl=3600)  # 1 hour
                return True

            self.logger.info("Docker image not found, pulling: %s", config.image)

            # Pull the image using the new pull_image method with middleware to show progress
            middleware = DefaultOutputMiddleware()
            result: tuple[int, list[str], list[str]] = self.docker_adapter.pull_image(
                image_name=image_name,
                image_tag=image_tag,
                middleware=middleware,
            )

            if result[0] == 0:
                self.logger.info("Successfully pulled Docker image: %s", config.image)
                # Cache successful pull for 1 hour
                if self.cache_manager:
                    self.cache_manager.set(image_cache_key, True, ttl=3600)  # 1 hour
                return True
            else:
                self.logger.error(
                    "Failed to pull Docker image: %s (exit code: %d)",
                    config.image,
                    result[0],
                )
                return False

        except Exception as e:
            self.logger.error("Error ensuring Docker image: %s", e)
            return False


def create_zmk_west_service(
    docker_adapter: DockerAdapterProtocol,
    user_config: UserConfig,
    file_adapter: FileAdapterProtocol,
    cache_manager: CacheManager,
    session_metrics: MetricsProtocol,
    workspace_cache_service: ZmkWorkspaceCacheService | None = None,
    build_cache_service: CompilationBuildCacheService | None = None,
) -> ZmkWestService:
    """Create ZMK West service with dual cache management and metrics.

    Args:
        docker_adapter: Docker adapter for container operations
        user_config: User configuration with cache settings
        file_adapter: File adapter for file operations
        cache_manager: Optional cache manager instance for both cache services
        workspace_cache_service: Optional workspace cache service
        build_cache_service: Optional build cache service
        session_metrics: Optional session metrics for tracking operations

    Returns:
        Configured ZmkWestService instance
    """
    return ZmkWestService(
        docker_adapter=docker_adapter,
        user_config=user_config,
        file_adapter=file_adapter,
        cache_manager=cache_manager,
        session_metrics=session_metrics,
    )
