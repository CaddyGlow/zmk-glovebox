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
    from glovebox.protocols.progress_context_protocol import ProgressContextProtocol


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
        # Initialize display variables for cleanup
        progress_manager = None
        progress_context = None

        try:
            if not isinstance(config, MoergoCompilationConfig):
                return BuildResult(
                    success=False, errors=["Invalid config type for Moergo compilation"]
                )

            # Extract board information dynamically
            board_info = self._extract_board_info_from_config(config)

            # Setup progress display using the new progress manager
            from glovebox.cli.components import create_progress_manager
            from glovebox.cli.components.noop_progress_context import (
                get_noop_progress_context,
            )
            from glovebox.cli.helpers.theme import (
                get_icon_mode_from_config,
                get_themed_console,
            )
            from glovebox.config import create_user_config

            # Get user config for icon mode
            user_config = create_user_config()
            icon_mode = get_icon_mode_from_config(user_config)

            # Create progress manager with MoErgo-specific checkpoints or use noop context
            if progress_callback is not None:
                # Create dynamic checkpoints based on board count
                checkpoints = [
                    "Docker Verification",
                    "Workspace Setup",
                    "Nix Environment",
                ]

                # Add individual board build checkpoints (MoErgo typically builds left and right)
                if board_info.get("board_names"):
                    for board_name in board_info["board_names"]:
                        checkpoints.append(f"Building {board_name}")
                else:
                    # Fallback for unknown boards
                    for i in range(board_info.get("total_boards", 2)):
                        if i == 0:
                            checkpoints.append("Building Left Hand")
                        elif i == 1:
                            checkpoints.append("Building Right Hand")
                        else:
                            checkpoints.append(f"Building Board {i + 1}")

                checkpoints.append("Collecting Artifacts")

                progress_manager = create_progress_manager(
                    operation_name="MoErgo Compilation",
                    checkpoints=checkpoints,
                    icon_mode=icon_mode,
                )

                with progress_manager as progress_context:
                    return self._execute_compilation_with_progress(
                        progress_context,
                        board_info,
                        config,
                        keyboard_profile,
                        keymap_file,
                        config_file,
                        keymap_content,
                        config_content,
                        output_dir,
                        compilation_start_time,
                    )
            else:
                # Use noop progress context when no progress callback
                progress_context = get_noop_progress_context()
                return self._execute_compilation_with_progress(
                    progress_context,
                    board_info,
                    config,
                    keyboard_profile,
                    keymap_file,
                    config_file,
                    keymap_content,
                    config_content,
                    output_dir,
                    compilation_start_time,
                )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Compilation failed: %s", e, exc_info=exc_info)
            return BuildResult(success=False, errors=[str(e)])

    def _execute_compilation_with_progress(
        self,
        progress_context: "ProgressContextProtocol",
        board_info: dict,
        config: MoergoCompilationConfig,
        keyboard_profile: "KeyboardProfile",
        keymap_file: Path | None,
        config_file: Path | None,
        keymap_content: str | None,
        config_content: str | None,
        output_dir: Path,
        compilation_start_time: float,
    ) -> BuildResult:
        """Execute compilation with progress tracking."""
        try:
            progress_context.log(
                f"Starting MoErgo compilation for {board_info['total_boards']} boards",
                "info",
            )

            # Check/build Docker image with progress
            progress_context.start_checkpoint("Docker Verification")
            progress_context.log(f"Verifying Docker image: {config.image}", "info")

            if not self._ensure_docker_image(config, progress_context):
                return BuildResult(success=False, errors=["Docker image setup failed"])

            progress_context.complete_checkpoint("Docker Verification")

            # Setup workspace with progress
            progress_context.start_checkpoint("Workspace Setup")
            progress_context.log("Setting up workspace directories and files", "info")

            workspace_path = self._setup_workspace(
                keyboard_profile=keyboard_profile,
                progress_context=progress_context,
                keymap_file=keymap_file,
                config_file=config_file,
                keymap_content=keymap_content,
                config_content=config_content,
            )
            if not workspace_path or not workspace_path.host_path:
                return BuildResult(success=False, errors=["Workspace setup failed"])

            progress_context.complete_checkpoint("Workspace Setup")

            # Run compilation with board-specific progress tracking
            progress_context.log("Starting MoErgo Nix compilation", "info")

            compilation_success = self._run_compilation(
                workspace_path, config, output_dir, progress_context, board_info
            )

            # Individual board checkpoints are completed within _run_compilation

            # Collect artifacts with progress
            progress_context.start_checkpoint("Collecting Artifacts")
            progress_context.log("Collecting .uf2 files and artifacts", "info")

            output_files = self._collect_files(
                workspace_path.host_path, output_dir, progress_context
            )

            progress_context.complete_checkpoint("Collecting Artifacts")

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
        """Execute compilation from JSON layout file.

        This method reads the JSON file and delegates to compile_from_data
        following the unified input/output patterns.
        """
        self.logger.info("Starting JSON to firmware compilation")

        try:
            # Read and parse JSON file to get layout data
            from glovebox.adapters import create_file_adapter
            from glovebox.layout.utils import process_json_file

            file_adapter = create_file_adapter()

            def extract_layout_data(layout_data: Any) -> dict[str, Any]:
                """Extract layout data for delegation to compile_from_data."""
                return layout_data

            layout_data = process_json_file(
                json_file,
                "JSON parsing for compilation",
                extract_layout_data,
                file_adapter,
            )

            # Delegate to memory-first method
            return self.compile_from_data(
                layout_data=layout_data,
                output_dir=output_dir,
                config=config,
                keyboard_profile=keyboard_profile,
                progress_callback=progress_callback,
            )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("JSON compilation failed: %s", e, exc_info=exc_info)
            return BuildResult(success=False, errors=[str(e)])

    def compile_from_data(
        self,
        layout_data: dict[str, Any],
        output_dir: Path,
        config: CompilationConfigUnion,
        keyboard_profile: "KeyboardProfile",
        progress_callback: CompilationProgressCallback | None = None,
    ) -> BuildResult:
        """Execute compilation from layout data dictionary (memory-first pattern).

        This is the memory-first method that takes layout data as input
        and returns content in the result object, following the unified
        input/output patterns established in Phase 1/2 refactoring.

        Args:
            layout_data: Layout data dictionary (validated as LayoutData)
            output_dir: Output directory for build artifacts
            config: Compilation configuration
            keyboard_profile: Keyboard profile for dynamic generation
            progress_callback: Optional callback for compilation progress updates

        Returns:
            BuildResult: Results of compilation with generated content
        """
        self.logger.info("Starting compilation from layout data")

        try:
            # Convert layout data to keymap and config content
            from glovebox.compilation.helpers import (
                convert_layout_data_to_keymap_content,
            )

            keymap_content, config_content, conversion_result = (
                convert_layout_data_to_keymap_content(
                    layout_data=layout_data,
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

            # Compile directly from content (no temp files needed for MoErgo)
            return self.compile_from_content(
                keymap_content=keymap_content,
                config_content=config_content,
                output_dir=output_dir,
                config=config,
                keyboard_profile=keyboard_profile,
                progress_callback=progress_callback,
                json_file=None,  # No original JSON file since we have data directly
            )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Compilation from data failed: %s", e, exc_info=exc_info)
            return BuildResult(success=False, errors=[str(e)])

    def validate_config(self, config: CompilationConfigUnion) -> bool:
        """Validate configuration."""
        return isinstance(config, MoergoCompilationConfig) and bool(config.image)

    def check_available(self) -> bool:
        """Check availability."""
        return self.docker_adapter is not None

    def _setup_workspace(
        self,
        keyboard_profile: "KeyboardProfile",
        progress_context: "ProgressContextProtocol",
        keymap_file: Path | None = None,
        config_file: Path | None = None,
        keymap_content: str | None = None,
        config_content: str | None = None,
    ) -> DockerPath | None:
        """Setup temporary workspace from files or content."""
        try:
            progress_context.log("Creating workspace directory", "info")

            workspace_path = DockerPath(
                host_path=Path(tempfile.mkdtemp(prefix="moergo_")),
                container_path="/workspace",
            )
            assert workspace_path.host_path is not None

            config_dir = workspace_path.host_path / "config"
            config_dir.mkdir(parents=True)

            progress_context.log("Copying keymap file", "info")

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

            progress_context.log("Copying config file", "info")

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

            progress_context.log("Loading Nix toolchain", "info")

            # Load default.nix from keyboard's toolchain directory
            default_nix_content = keyboard_profile.load_toolchain_file("default.nix")
            if not default_nix_content:
                self.logger.error("Could not load default.nix from keyboard toolchain")
                return None

            self.file_adapter.write_text(
                config_dir / "default.nix", default_nix_content
            )

            progress_context.log("Workspace setup completed", "info")

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
        progress_context: "ProgressContextProtocol",
        board_info: dict[str, Any] | None = None,
    ) -> bool:
        """Run Docker compilation."""
        try:
            from glovebox.adapters.docker_adapter import LoggerOutputMiddleware
            from glovebox.models.docker import DockerUserContext
            from glovebox.utils.build_log_middleware import create_build_log_middleware
            from glovebox.utils.stream_process import (
                DefaultOutputMiddleware,
                create_chained_middleware,
            )

            # Extract board information for progress tracking
            if board_info is None:
                board_info = self._extract_board_info_from_config(config)

            board_names = board_info.get("board_names", [])
            total_boards = board_info.get("total_boards", 2)

            # Default to left/right hand for MoErgo if no specific names
            if not board_names:
                if total_boards >= 2:
                    board_names = ["Left Hand", "Right Hand"]
                else:
                    board_names = ["Firmware"]

            middlewares: list[Any] = []

            # Create build log middleware
            build_log_middleware = create_build_log_middleware(output_dir)
            middlewares.append(build_log_middleware)

            # Add board-specific progress tracking middleware
            class MoErgoBoardProgressMiddleware(DefaultOutputMiddleware):
                """Middleware to track individual board build progress for MoErgo."""

                def __init__(self):
                    super().__init__()
                    self.current_board_index = 0
                    self.boards_completed = 0
                    self.in_build_phase = False
                    self.started_nix_env = False

                def process_line(self, line: str, is_stderr: bool) -> None:
                    """Process Docker output line to track board progress."""
                    line_lower = line.lower()

                    # Detect Nix environment setup start
                    if not self.started_nix_env and (
                        "nix-shell" in line_lower or "entering nix" in line_lower
                    ):
                        progress_context.start_checkpoint("Nix Environment")
                        progress_context.log("Setting up Nix environment", "info")
                        self.started_nix_env = True

                    # Detect when Nix environment is ready and building starts
                    if (
                        self.started_nix_env
                        and ("building" in line_lower or "compiling" in line_lower)
                        and not self.in_build_phase
                    ):
                        progress_context.complete_checkpoint("Nix Environment")
                        # Start first board build
                        if self.current_board_index < len(board_names):
                            board_name = board_names[self.current_board_index]
                            checkpoint_name = f"Building {board_name}"
                            progress_context.start_checkpoint(checkpoint_name)
                            progress_context.log(
                                f"Starting build for {board_name}", "info"
                            )
                            self.in_build_phase = True

                    # Detect when a .uf2 file is created (indicates board completion)
                    if (
                        self.in_build_phase
                        and ".uf2" in line_lower
                        and ("created" in line_lower or "generated" in line_lower)
                        and self.current_board_index < len(board_names)
                    ):
                        board_name = board_names[self.current_board_index]
                        checkpoint_name = f"Building {board_name}"
                        progress_context.complete_checkpoint(checkpoint_name)
                        progress_context.log(
                            f"Completed build for {board_name}", "info"
                        )
                        self.boards_completed += 1
                        self.current_board_index += 1

                        # Update overall progress
                        progress_context.update_progress(
                            current=self.boards_completed,
                            total=total_boards,
                            status=f"Built {self.boards_completed}/{total_boards} boards",
                        )

                        # Start next board if available
                        if self.current_board_index < len(board_names):
                            board_name = board_names[self.current_board_index]
                            checkpoint_name = f"Building {board_name}"
                            progress_context.start_checkpoint(checkpoint_name)
                            progress_context.log(
                                f"Starting build for {board_name}", "info"
                            )
                        else:
                            self.in_build_phase = False

                    # Detect build failures
                    if (
                        self.in_build_phase
                        and (
                            "error:" in line_lower
                            or "failed" in line_lower
                            or "make: *** [" in line_lower
                        )
                        and self.current_board_index < len(board_names)
                    ):
                        board_name = board_names[self.current_board_index]
                        checkpoint_name = f"Building {board_name}"
                        progress_context.fail_checkpoint(checkpoint_name)
                        progress_context.log(f"Build failed for {board_name}", "error")

            middlewares.append(MoErgoBoardProgressMiddleware())

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
        self,
        workspace_path: Path,
        output_dir: Path,
        progress_context: "ProgressContextProtocol",
    ) -> FirmwareOutputFiles:
        """Collect firmware files from artifacts directory, including partial artifacts for debugging."""
        output_dir.mkdir(parents=True, exist_ok=True)
        uf2_files: list[Path] = []
        artifacts_dir = None
        collected_items = []

        progress_context.log("Scanning for build artifacts", "info")

        # Look for artifacts directory created by build.sh
        build_artifacts_dir = workspace_path / "artifacts"
        if build_artifacts_dir.exists():
            try:
                # Count items for progress tracking
                items_to_copy = list(build_artifacts_dir.iterdir())
                total_items = len(items_to_copy)

                progress_context.log(
                    f"Copying {total_items} artifacts to output directory", "info"
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
                            # TODO: Enable after refactoring
                            # progress_coordinator.update_cache_progress(
                            #     "copying",
                            #     current_progress,
                            #     100,
                            #     f"Copied {i + 1}/{total_items} artifacts",
                            # )

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

            # TODO: Enable after refactoring
            # progress_coordinator.update_cache_progress(
            #     "scanning", 75, 100, "Searching for partial build files"
            # )

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

        # TODO: Enable after refactoring
        # progress_coordinator.update_cache_progress(
        #     "completed", 100, 100, f"Collected {len(uf2_files)} firmware files"
        # )

        return FirmwareOutputFiles(
            output_dir=output_dir,
            uf2_files=uf2_files,
            artifacts_dir=artifacts_dir,
        )

    def _ensure_docker_image(
        self,
        config: MoergoCompilationConfig,
        progress_context: "ProgressContextProtocol",
    ) -> bool:
        """Ensure Docker image exists, build if not found."""
        try:
            progress_context.log("Checking Docker image availability", "info")

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

                progress_context.log("Docker image ready", "info")
                return True

            progress_context.log(
                f"Building Docker image: {versioned_image_name}", "info"
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

            progress_context.log(f"Building image from {dockerfile_dir}", "info")

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

                progress_context.log("Docker image built successfully", "info")
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
