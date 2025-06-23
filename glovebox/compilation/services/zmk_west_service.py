"""ZMK config with west compilation service."""

import logging
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

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
from glovebox.compilation.models.west_config import (
    WestManifest,
    WestManifestConfig,
)
from glovebox.compilation.protocols.compilation_protocols import (
    CompilationServiceProtocol,
)
from glovebox.config.user_config import UserConfig
from glovebox.core.cache_v2.cache_manager import CacheManager
from glovebox.core.cache_v2.models import CacheKey
from glovebox.core.errors import CompilationError
from glovebox.firmware.models import BuildResult, FirmwareOutputFiles
from glovebox.models.docker import DockerUserContext
from glovebox.protocols import DockerAdapterProtocol
from glovebox.utils.stream_process import DefaultOutputMiddleware


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile


class ZmkWestService(CompilationServiceProtocol):
    """Ultra-simplified ZMK config compilation service with intelligent caching."""

    def __init__(
        self,
        docker_adapter: DockerAdapterProtocol,
        user_config: UserConfig,
        cache_manager: CacheManager | None = None,
        workspace_cache_service: ZmkWorkspaceCacheService | None = None,
        build_cache_service: CompilationBuildCacheService | None = None,
    ) -> None:
        """Initialize with Docker adapter, user config, and both cache services."""
        self.docker_adapter = docker_adapter
        self.user_config = user_config
        self.cache_manager = cache_manager
        self.logger = logging.getLogger(__name__)

        # Create cache services if not provided
        if cache_manager is not None:
            if workspace_cache_service is None:
                self.workspace_cache_service: ZmkWorkspaceCacheService | None = (
                    ZmkWorkspaceCacheService(user_config, cache_manager)
                )
            else:
                self.workspace_cache_service = workspace_cache_service

            if build_cache_service is None:
                self.build_cache_service: CompilationBuildCacheService | None = (
                    CompilationBuildCacheService(user_config, cache_manager)
                )
            else:
                self.build_cache_service = build_cache_service
        else:
            self.workspace_cache_service = workspace_cache_service
            self.build_cache_service = build_cache_service

    def compile(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: CompilationConfigUnion,
        keyboard_profile: "KeyboardProfile",
    ) -> BuildResult:
        """Execute ZMK compilation."""
        self.logger.info("Starting ZMK config compilation")

        # Import metrics here to avoid circular dependencies
        try:
            from glovebox.metrics.collector import firmware_metrics

            metrics_enabled = True
        except ImportError:
            metrics_enabled = False

        if metrics_enabled:
            with firmware_metrics() as metrics:
                metrics.set_context(
                    profile_name=f"{keyboard_profile.keyboard_name}/{keyboard_profile.firmware_version}"
                    if keyboard_profile.firmware_version
                    else keyboard_profile.keyboard_name,
                    keyboard_name=keyboard_profile.keyboard_name,
                    firmware_version=keyboard_profile.firmware_version,
                    compilation_strategy="zmk_config",
                    board_targets=config.build_matrix.board
                    if isinstance(config, ZmkCompilationConfig)
                    else None,
                )
                return self._compile_with_metrics(
                    keymap_file,
                    config_file,
                    output_dir,
                    config,
                    keyboard_profile,
                    metrics,
                )
        else:
            return self._compile_core(
                keymap_file, config_file, output_dir, config, keyboard_profile
            )

    def _compile_with_metrics(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: CompilationConfigUnion,
        keyboard_profile: "KeyboardProfile",
        metrics: Any,
    ) -> BuildResult:
        """Execute ZMK compilation with metrics collection."""
        if not isinstance(config, ZmkCompilationConfig):
            return BuildResult(
                success=False, errors=["Invalid config type for ZMK compilation"]
            )

        # Try to use cached build result first (most specific cache)
        with metrics.time_operation("cache_check"):
            cached_build_path = self._get_cached_build_result(
                keymap_file, config_file, config
            )
            if cached_build_path:
                metrics.record_cache_event(
                    "build_result", cache_hit=True, cache_key="build_result"
                )
                self.logger.info(
                    "Found cached build - copying artifacts and skipping compilation"
                )
                output_files = self._collect_files(cached_build_path, output_dir)
                return BuildResult(
                    success=True,
                    output_files=output_files,
                    messages=["Used cached build result"],
                )

            metrics.record_cache_event("build_result", cache_hit=False)

        # Try to use cached workspace
        with metrics.time_operation("workspace_setup"):
            workspace_path, cache_used, cache_type = self._get_or_create_workspace(
                keymap_file, config_file, config
            )
            if not workspace_path:
                self.logger.error("Workspace setup failed")
                return BuildResult(success=False, errors=["Workspace setup failed"])

            # Record workspace cache event
            metrics.record_cache_event("workspace", cache_hit=cache_used)

            metrics.set_context(workspace_path=workspace_path)

        with metrics.time_operation("compilation"):
            compilation_success = self._run_compilation(
                workspace_path, config, cache_used, cache_type
            )

        # Cache workspace dependencies if it was created fresh (not from cache)
        # As per user request: "we never update the two cache once they are created"
        if not cache_used:
            with metrics.time_operation("workspace_caching"):
                self._cache_workspace(workspace_path, config)
        elif cache_type == "repo_only" and self.workspace_cache_service:
            with metrics.time_operation("workspace_caching"):
                # self._cache_workspace(workspace_path, config)
                #
                cache_result = self.workspace_cache_service.cache_workspace_repo_branch(
                    workspace_path, config.repository, config.branch
                )

                if cache_result.success:
                    self.logger.info(
                        "Cached workspace (repo+branch) for %s@%s: %s",
                        config.repository,
                        config.branch,
                        cache_result.workspace_path,
                    )
                else:
                    self.logger.warning(
                        "Failed to cache workspace (repo+branch): %s",
                        cache_result.error_message,
                    )

        # Always try to collect artifacts, even on build failure (for debugging)
        with metrics.time_operation("artifact_collection"):
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

        build_result = BuildResult(
            success=True,
            output_files=output_files,
            messages=[
                f"Generated {'1' if output_files.main_uf2 else '0'} firmware files"
            ],
        )

        # Cache the successful build result
        with metrics.time_operation("result_caching"):
            self._cache_build_result(keymap_file, config_file, config, workspace_path)

        # Set final metrics context
        metrics.set_context(
            artifacts_generated=1 if output_files.main_uf2 else 0,
            firmware_size_bytes=output_files.main_uf2.stat().st_size
            if output_files.main_uf2 and output_files.main_uf2.exists()
            else None,
        )

        self.logger.info("ZMK compilation completed successfully")
        return build_result

    def _compile_core(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: CompilationConfigUnion,
        keyboard_profile: "KeyboardProfile",
    ) -> BuildResult:
        """Execute ZMK compilation (core implementation without metrics)."""
        try:
            if not isinstance(config, ZmkCompilationConfig):
                return BuildResult(
                    success=False, errors=["Invalid config type for ZMK compilation"]
                )

            # Try to use cached build result first (most specific cache)
            cached_build_path = self._get_cached_build_result(
                keymap_file, config_file, config
            )
            if cached_build_path:
                self.logger.info(
                    "Found cached build - copying artifacts and skipping compilation"
                )
                output_files = self._collect_files(cached_build_path, output_dir)
                return BuildResult(
                    success=True,
                    output_files=output_files,
                    messages=["Used cached build result"],
                )

            # Try to use cached workspace
            workspace_path, cache_used, cache_type = self._get_or_create_workspace(
                keymap_file, config_file, config
            )
            if not workspace_path:
                self.logger.error("Workspace setup failed")
                return BuildResult(success=False, errors=["Workspace setup failed"])

            compilation_success = self._run_compilation(
                workspace_path, config, cache_used, cache_type
            )

            # Cache workspace dependencies if it was created fresh (not from cache)
            # As per user request: "we never update the two cache once they are created"
            if not cache_used:
                self._cache_workspace(workspace_path, config)

            # Always try to collect artifacts, even on build failure (for debugging)
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

            build_result = BuildResult(
                success=True,
                output_files=output_files,
                messages=[
                    f"Generated {'1' if output_files.main_uf2 else '0'} firmware files"
                ],
            )

            # Cache the successful build result
            self._cache_build_result(keymap_file, config_file, config, workspace_path)

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
    ) -> BuildResult:
        """Execute compilation from JSON layout file."""
        self.logger.info("Starting JSON to firmware compilation")

        try:
            # Convert JSON to keymap/config files first
            from glovebox.layout import create_layout_service

            layout_service = create_layout_service()

            # Create temporary directory for intermediate files
            with tempfile.TemporaryDirectory(prefix="json_to_keymap_") as temp_dir:
                temp_path = Path(temp_dir)
                output_prefix = temp_path / "layout"

                # Generate keymap and config files from JSON
                layout_result = layout_service.generate_from_file(
                    profile=keyboard_profile,
                    json_file_path=json_file,
                    output_file_prefix=str(output_prefix),
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

    def _get_cached_workspace(
        self, config: ZmkCompilationConfig
    ) -> tuple[Path | None, bool, str | None]:
        """Get cached workspace if available using new simplified cache.

        Returns:
            Tuple of (workspace_path, cache_was_used, cache_type) or (None, False, None) if no cache found
            cache_type: 'repo_branch' or 'repo_only' to distinguish cache types
        """
        if not config.use_cache or not self.workspace_cache_service:
            return None, False, None

        # Try repo+branch lookup first (more specific) - check if it has complete dependencies
        cache_result = self.workspace_cache_service.get_cached_workspace(
            config.repository, config.branch
        )

        if (
            cache_result.success
            and cache_result.workspace_path
            and (cache_result.workspace_path / "zmk").exists()
        ):
            return cache_result.workspace_path, True, "repo_branch"
            # # Check if repo+branch cache has complete dependencies (west update marker)
            # west_marker = cache_result.workspace_path / ".west_last_update"
            # if west_marker.exists():
            #     self.logger.info(
            #         "Using cached workspace (repo+branch) with complete dependencies: %s",
            #         cache_result.workspace_path,
            #     )
            #     return cache_result.workspace_path, True, "repo_branch"
            # else:
            #     self.logger.info(
            #         "Repo+branch cache found but incomplete (no west marker), checking repo-only cache"
            #     )

        # Try repo-only lookup (includes .git for west operations)
        cache_result = self.workspace_cache_service.get_cached_workspace(
            config.repository, None
        )

        if (
            cache_result.success
            and cache_result.workspace_path
            and (cache_result.workspace_path / "zmk").exists()
        ):
            self.logger.info(
                "Using cached workspace (repo-only): %s",
                cache_result.workspace_path,
            )
            return cache_result.workspace_path, True, "repo_only"

        return None, False, None

    def _cache_workspace(
        self,
        workspace_path: Path,
        config: ZmkCompilationConfig,
    ) -> None:
        """Cache workspace for future use with new dual-level strategy."""
        if not config.use_cache or not self.workspace_cache_service:
            return

        try:
            # Cache at both levels: repo+branch (more specific, excludes .git)
            # and repo-only (less specific, includes .git for branch fetching)

            # Cache repo+branch level first (most commonly used)
            cache_result = self.workspace_cache_service.cache_workspace_repo_branch(
                workspace_path, config.repository, config.branch
            )

            if cache_result.success:
                self.logger.info(
                    "Cached workspace (repo+branch) for %s@%s: %s",
                    config.repository,
                    config.branch,
                    cache_result.workspace_path,
                )
            else:
                self.logger.warning(
                    "Failed to cache workspace (repo+branch): %s",
                    cache_result.error_message,
                )

            # Cache repo-only level (for branch fetching scenarios)
            cache_result = self.workspace_cache_service.cache_workspace_repo_only(
                workspace_path, config.repository
            )

            if cache_result.success:
                self.logger.info(
                    "Cached workspace (repo-only) for %s: %s",
                    config.repository,
                    cache_result.workspace_path,
                )
            else:
                self.logger.warning(
                    "Failed to cache workspace (repo-only): %s",
                    cache_result.error_message,
                )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.warning("Failed to cache workspace: %s", e, exc_info=exc_info)

    def _get_cached_build_result(
        self, keymap_file: Path, config_file: Path, config: ZmkCompilationConfig
    ) -> Path | None:
        """Get cached build directory if available."""
        if not config.use_cache or not self.build_cache_service:
            return None

        # Generate cache key using the build cache service
        cache_key = self.build_cache_service.generate_cache_key_from_files(
            repository=config.repository,
            branch=config.branch,
            config_file=config_file,
            keymap_file=keymap_file,
        )

        # Get cached build directory
        cached_build_path = self.build_cache_service.get_cached_build(cache_key)

        if cached_build_path:
            self.logger.info(
                "Found cached build for %s: %s", keymap_file.name, cached_build_path
            )

        return cached_build_path

    def _cache_build_result(
        self,
        keymap_file: Path,
        config_file: Path,
        config: ZmkCompilationConfig,
        workspace_path: Path,
    ) -> None:
        """Cache successful build directory for future use."""
        if not config.use_cache or not self.build_cache_service:
            return

        try:
            # Generate cache key using the build cache service
            cache_key = self.build_cache_service.generate_cache_key_from_files(
                repository=config.repository,
                branch=config.branch,
                config_file=config_file,
                keymap_file=keymap_file,
            )

            # Cache the workspace build directory (contains all build artifacts)
            success = self.build_cache_service.cache_build_result(
                workspace_path, cache_key
            )

            if success:
                self.logger.info("Cached build result for %s", keymap_file.name)
            else:
                self.logger.warning(
                    "Failed to cache build result for %s", keymap_file.name
                )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.warning(
                "Failed to cache build result: %s", e, exc_info=exc_info
            )

    def _get_or_create_workspace(
        self, keymap_file: Path, config_file: Path, config: ZmkCompilationConfig
    ) -> tuple[Path | None, bool, str | None]:
        """Get cached workspace or create new one.

        Returns:
            Tuple of (workspace_path, cache_was_used, cache_type) or (None, False, None) if failed
        """
        # Try to use cached workspace
        cached_workspace, cache_used, cache_type = self._get_cached_workspace(config)
        workspace_path = Path(tempfile.mkdtemp(prefix="zmk_"))

        if cached_workspace:
            # Create temporary workspace and copy from cache
            try:
                # Copy cached workspace
                for subdir in ["modules", "zephyr", "zmk", ".west"]:
                    if (cached_workspace / subdir).exists():
                        shutil.copytree(
                            cached_workspace / subdir, workspace_path / subdir
                        )

                # Copy west update marker if it exists
                west_marker = cached_workspace / ".west_last_update"
                if west_marker.exists():
                    shutil.copy2(west_marker, workspace_path / ".west_last_update")

                # Set up config directory with fresh files
                self._setup_workspace(keymap_file, config_file, config, workspace_path)
                self.logger.info("Using cached workspace")
                return workspace_path, True, cache_type
            except Exception as e:
                exc_info = self.logger.isEnabledFor(logging.DEBUG)
                self.logger.warning(
                    "Failed to use cached workspace: %s", e, exc_info=exc_info
                )
                shutil.rmtree(workspace_path, ignore_errors=True)

        # Create fresh workspace
        self._setup_workspace(keymap_file, config_file, config, workspace_path)
        return workspace_path, False, None

    def _setup_workspace(
        self,
        keymap_file: Path,
        config_file: Path,
        config: ZmkCompilationConfig,
        workspace_path: Path,
    ) -> None:
        """Setup temporary workspace."""
        try:
            config_dir = workspace_path / "config"
            self._setup_config_dir(config_dir, keymap_file, config_file, config)

            config.build_matrix.to_yaml(workspace_path / "build.yaml")

        except Exception as e:
            raise CompilationError(f"Workspace setup failed: {e}") from e

    def _setup_config_dir(
        self,
        config_dir: Path,
        keymap_file: Path,
        config_file: Path,
        config: ZmkCompilationConfig,
    ) -> None:
        """Setup config directory with files."""
        config_dir.mkdir(exist_ok=True)

        # Copy files
        shutil.copy2(keymap_file, config_dir / keymap_file.name)
        shutil.copy2(config_file, config_dir / config_file.name)

        # Create west.yml using proper west config models
        manifest = WestManifestConfig(
            manifest=WestManifest.from_repository_config(
                repository=config.repository,
                branch=config.branch,
                config_path="config",
                import_file="app/west.yml",
            )
        )
        with (config_dir / "west.yml").open("w") as f:
            f.write(manifest.to_yaml())

    def _should_run_west_update(
        self,
        workspace_path: Path,
        cache_was_used: bool = False,
        cache_type: str | None = None,
    ) -> bool:
        """Determine if west update should be run based on cache usage and cache type.

        Args:
            workspace_path: Path to the workspace
            cache_was_used: Whether workspace was loaded from cache
            cache_type: Type of cache used ('repo_branch' or 'repo_only')

        Returns:
            True if west update should be run
        """
        # Always update for fresh workspaces (cache not used)
        if not cache_was_used:
            self.logger.info("Running west update for fresh workspace")
            return True

        # # Check if workspace has an update marker - if not, always run update regardless of cache type
        # west_marker = workspace_path / ".west_last_update"
        # if not west_marker.exists():
        #     self.logger.info("No west update marker found, running west update")
        #     return True

        # For repo+branch cache with marker, skip update (static snapshot, dependencies complete)
        if cache_type == "repo_branch":
            self.logger.info(
                "Skipping west update for repo+branch cache (static snapshot with complete dependencies)"
            )
            return False

        # For repo-only cache with marker, still skip update (already updated in this session)
        if cache_type == "repo_only":
            self.logger.info(
                "Skipping west update for repo-only cache (already updated)"
            )
            return False

        # Fallback - workspace has marker, skip update
        self.logger.info(
            "Skipping west update for cached workspace (dependencies should be complete)"
        )
        return False

    def _run_compilation(
        self,
        workspace_path: Path,
        config: ZmkCompilationConfig,
        cache_was_used: bool = False,
        cache_type: str | None = None,
    ) -> bool:
        """Run Docker compilation with intelligent west update logic.

        Args:
            workspace_path: Path to the workspace
            config: ZMK compilation configuration
            cache_was_used: Whether workspace was loaded from cache
            cache_type: Type of cache used ('repo_branch' or 'repo_only')
        """
        try:
            # Check if Docker image exists, build if not
            if not self._ensure_docker_image(config):
                self.logger.error("Failed to ensure Docker image is available")
                return False

            # Generate proper build commands using build matrix
            build_commands = self._generate_build_commands(workspace_path, config)
            if not build_commands:
                return False

            # Build base commands with conditional west update
            base_commands = ["cd /workspace"]

            # Only run west update if needed based on cache usage and type
            if cache_type == "repo_only":
                base_commands.append("west init -l config")

            if not cache_was_used:
                base_commands.append("west update")

            base_commands.append("west zephyr-export")

            # Always run west zephyr-export to set up Zephyr environment variables

            all_commands = base_commands + build_commands

            # Use current user context to avoid permission issues
            user_context = DockerUserContext.detect_current_user()

            self.logger.info("Running Docker compilation")

            result: tuple[int, list[str], list[str]] = (
                self.docker_adapter.run_container(
                    image=config.image,
                    command=["sh", "-c", " && ".join(all_commands)],
                    volumes=[(str(workspace_path), "/workspace")],
                    environment={},  # {"JOBS": "4"},
                    user_context=user_context,
                )
            )
            return_code, stdout, stderr = result

            if return_code != 0:
                self.logger.error("Build failed with exit code %d", return_code)
                return False

            self.logger.info("Build completed successfully")
            return True
        except Exception as e:
            self.logger.error("Docker execution failed: %s", e)
            return False

    def _generate_build_commands(
        self, workspace_path: Path, config: ZmkCompilationConfig
    ) -> list[str]:
        """Generate west build commands from build matrix."""
        try:
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
                    "-s zmk/app",
                    f"-b {target.board}",
                    f"-d {build_dir}",
                    "--",
                ]

                # Add CMake arguments
                cmake_args = ["-DZMK_CONFIG=/workspace/config"]
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

    def _collect_files(
        self, workspace_path: Path, output_dir: Path
    ) -> FirmwareOutputFiles:
        """Collect firmware files from build directories determined by build matrix."""
        output_dir.mkdir(parents=True, exist_ok=True)
        main_uf2 = None
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
                    output_dir=output_dir, main_uf2=None, artifacts_dir=None
                )

            build_matrix = BuildMatrix.from_yaml(build_yaml)

            # Look for build directories based on build matrix targets
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

                    # Set main_uf2 to the first .uf2 file found
                    uf2_file = cur_build_out / "zmk.uf2"
                    if uf2_file.exists() and main_uf2 is None:
                        main_uf2 = uf2_file

                except Exception as e:
                    self.logger.warning(
                        "Failed to copy build directory %s: %s", build_path, e
                    )

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
            main_uf2=main_uf2,
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
    cache_manager: CacheManager | None = None,
    workspace_cache_service: ZmkWorkspaceCacheService | None = None,
    build_cache_service: CompilationBuildCacheService | None = None,
) -> ZmkWestService:
    """Create ZMK West service with dual cache management.

    Args:
        docker_adapter: Docker adapter for container operations
        user_config: User configuration with cache settings
        cache_manager: Optional cache manager instance for both cache services
        workspace_cache_service: Optional workspace cache service
        build_cache_service: Optional build cache service

    Returns:
        Configured ZmkWestService instance
    """
    return ZmkWestService(
        docker_adapter=docker_adapter,
        user_config=user_config,
        cache_manager=cache_manager,
        workspace_cache_service=workspace_cache_service,
        build_cache_service=build_cache_service,
    )
