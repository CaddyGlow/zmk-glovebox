"""ZMK config with west compilation service."""

import json
import logging
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from glovebox.compilation.cache.workspace_cache_service import (
    ZmkWorkspaceCacheService,
    create_zmk_workspace_cache_service,
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
from glovebox.core.workspace_cache_utils import generate_workspace_cache_key
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
        cache: CacheManager | None = None,
        workspace_cache_service: ZmkWorkspaceCacheService | None = None,
    ) -> None:
        """Initialize with Docker adapter, user config, and cache manager."""
        self.docker_adapter = docker_adapter
        self.user_config = user_config
        self.cache = cache
        self.logger = logging.getLogger(__name__)

        # Create workspace cache service if not provided
        if workspace_cache_service is None and cache is not None:
            self.workspace_cache_service: ZmkWorkspaceCacheService | None = (
                create_zmk_workspace_cache_service(user_config, cache)
            )
        else:
            self.workspace_cache_service = workspace_cache_service

        # Get TTL values from user config for backward compatibility
        if self.user_config:
            cache_ttls = self.user_config._config.cache_ttls.get_workspace_ttls()
            self.CACHE_TTL_BASE = cache_ttls["base"]
            self.CACHE_TTL_BRANCH = cache_ttls["branch"]
            self.CACHE_TTL_FULL = cache_ttls["full"]
            self.CACHE_TTL_BUILD = cache_ttls["build"]
        else:
            # Fallback to default values
            self.CACHE_TTL_BASE = 30 * 24 * 3600  # 30 days
            self.CACHE_TTL_BRANCH = 24 * 3600  # 1 day
            self.CACHE_TTL_FULL = 12 * 3600  # 12 hours
            self.CACHE_TTL_BUILD = 3600  # 1 hour

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
            cached_result = self._get_cached_build_result(
                keymap_file, config_file, config
            )
            if cached_result:
                metrics.set_cache_info(cache_hit=True, cache_key="build_result")
                self.logger.info(
                    "Returning cached build result - compilation skipped entirely"
                )
                return cached_result

            metrics.set_cache_info(cache_hit=False)

        # Try to use cached workspace
        with metrics.time_operation("workspace_setup"):
            workspace_path, cache_level = self._get_or_create_workspace(
                keymap_file, config_file, config
            )
            if not workspace_path:
                self.logger.error("Workspace setup failed")
                return BuildResult(success=False, errors=["Workspace setup failed"])

            metrics.set_context(workspace_path=workspace_path)

        with metrics.time_operation("compilation"):
            compilation_success = self._run_compilation(
                workspace_path, config, cache_level
            )

        # Cache workspace dependencies even if compilation fails
        with metrics.time_operation("workspace_caching"):
            self._cache_workspace(workspace_path, config)

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
            self._cache_build_result(keymap_file, config_file, config, build_result)

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
            cached_result = self._get_cached_build_result(
                keymap_file, config_file, config
            )
            if cached_result:
                self.logger.info(
                    "Returning cached build result - compilation skipped entirely"
                )
                return cached_result

            # Try to use cached workspace
            workspace_path, cache_level = self._get_or_create_workspace(
                keymap_file, config_file, config
            )
            if not workspace_path:
                self.logger.error("Workspace setup failed")
                return BuildResult(success=False, errors=["Workspace setup failed"])

            compilation_success = self._run_compilation(
                workspace_path, config, cache_level
            )

            # Cache workspace dependencies even if compilation fails
            # This allows reuse of successfully downloaded/built dependencies
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
            self._cache_build_result(keymap_file, config_file, config, build_result)

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
    ) -> tuple[Path | None, str | None]:
        """Get cached workspace if available using tiered cache lookup.

        Returns:
            Tuple of (workspace_path, cache_level) or (None, None) if no cache found
        """
        if not config.use_cache or not self.workspace_cache_service:
            return None, None

        # Try cache lookup in order of specificity: full -> branch -> base
        cache_levels = ["full", "branch", "base"]

        for level in cache_levels:
            cache_result = self.workspace_cache_service.get_cached_workspace(
                config.repository, config.branch, level
            )

            if (
                cache_result.success
                and cache_result.workspace_path
                and (cache_result.workspace_path / "zmk").exists()
            ):
                self.logger.info(
                    "Using cached workspace (%s level): %s",
                    level,
                    cache_result.workspace_path,
                )

                # Promote cache to more specific levels if needed
                self._promote_cache_entry(
                    config, level, str(cache_result.workspace_path)
                )

                return cache_result.workspace_path, level

        return None, None

    def _cache_workspace(
        self, workspace_path: Path, config: ZmkCompilationConfig
    ) -> None:
        """Cache workspace for future use with tiered caching strategy."""
        if not config.use_cache or not self.workspace_cache_service:
            return

        try:
            # Determine appropriate cache levels based on workspace completeness
            # For a workspace that has been through compilation, it should be "full"
            # since it contains all dependencies and has been built
            cache_levels = ["full", "branch", "base"]  # Store as full level primarily

            # Use the new workspace cache service to handle caching
            cache_result = self.workspace_cache_service.cache_workspace(
                workspace_path=workspace_path,
                repository=config.repository,
                branch=config.branch,
                cache_levels=cache_levels,
                build_profile=f"{config.repository}@{config.branch}",
            )

            if cache_result.success:
                self.logger.info(
                    "Cached workspace for %s@%s: %s",
                    config.repository,
                    config.branch,
                    cache_result.workspace_path,
                )
            else:
                self.logger.warning(
                    "Failed to cache workspace: %s", cache_result.error_message
                )
        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.warning("Failed to cache workspace: %s", e, exc_info=exc_info)

    def _promote_cache_entry(
        self, config: ZmkCompilationConfig, level: str, cached_path: str
    ) -> None:
        """Promote cache entry to more specific levels to avoid repeated lookups."""
        if level == "full" or not self.cache:
            return  # Already most specific or no cache

        if level == "base":
            # Update both branch and full cache
            branch_key = self._generate_workspace_cache_key(config, "branch")
            full_key = self._generate_workspace_cache_key(config, "full")
            self.cache.set(branch_key, cached_path, ttl=self.CACHE_TTL_BRANCH)
            self.cache.set(full_key, cached_path, ttl=self.CACHE_TTL_FULL)
        elif level == "branch":
            # Update full cache only
            full_key = self._generate_workspace_cache_key(config, "full")
            self.cache.set(full_key, cached_path, ttl=self.CACHE_TTL_FULL)

    def _get_cached_build_result(
        self, keymap_file: Path, config_file: Path, config: ZmkCompilationConfig
    ) -> BuildResult | None:
        """Get cached build result if available."""
        if not config.use_cache or not self.cache:
            return None

        build_cache_key = self._generate_workspace_cache_key(
            config, "build", keymap_file, config_file
        )

        cached_result = self.cache.get(build_cache_key)

        if cached_result:
            try:
                # Deserialize cached build result
                result_data = (
                    cached_result
                    if isinstance(cached_result, dict)
                    else json.loads(cached_result)
                )
                build_result = BuildResult(**result_data)

                # Verify cached output files still exist
                if build_result.output_files and build_result.output_files.main_uf2:
                    if build_result.output_files.main_uf2.exists():
                        self.logger.info(
                            "Using cached build result for %s", keymap_file.name
                        )
                        return build_result
                    else:
                        # Clean up stale cache entry
                        self.cache.delete(build_cache_key)
                else:
                    self.cache.delete(build_cache_key)

            except Exception as e:
                self.logger.warning("Failed to deserialize cached build result: %s", e)
                self.cache.delete(build_cache_key)

        return None

    def _cache_build_result(
        self,
        keymap_file: Path,
        config_file: Path,
        config: ZmkCompilationConfig,
        build_result: BuildResult,
    ) -> None:
        """Cache build result for future use."""
        if not config.use_cache or not self.cache or not build_result.success:
            return

        try:
            build_cache_key = self._generate_workspace_cache_key(
                config, "build", keymap_file, config_file
            )

            # Serialize build result for caching
            result_data = build_result.model_dump(mode="json")

            # Cache for 1 hour since build results are very specific
            self.cache.set(build_cache_key, result_data, ttl=self.CACHE_TTL_BUILD)
            self.logger.info("Cached build result for %s", keymap_file.name)

        except Exception as e:
            self.logger.warning("Failed to cache build result: %s", e)

    def _generate_workspace_cache_key(
        self,
        config: ZmkCompilationConfig,
        level: str = "full",
        keymap_file: Path | None = None,
        config_file: Path | None = None,
    ) -> str:
        """Generate cache key for workspace based on configuration and cache level."""

        # Prepare build matrix data for shared function
        build_matrix_data = None
        if level in ["full", "build"]:
            build_matrix_data = config.build_matrix.model_dump(mode="json")

        # Prepare additional parts for build level
        additional_parts = []
        if level == "build":
            if keymap_file and keymap_file.exists():
                keymap_hash = CacheKey.from_path(keymap_file)
                additional_parts.append(keymap_hash)

            if config_file and config_file.exists():
                config_hash = CacheKey.from_path(config_file)
                additional_parts.append(config_hash)

        # Use shared utility with appropriate parameters
        return generate_workspace_cache_key(
            repository=config.repository,
            branch=config.branch,
            level=level,
            image=config.image,
            build_matrix_data=build_matrix_data,
            additional_parts=additional_parts if additional_parts else None,
        )

    def _get_or_create_workspace(
        self, keymap_file: Path, config_file: Path, config: ZmkCompilationConfig
    ) -> tuple[Path | None, str | None]:
        """Get cached workspace or create new one.

        Returns:
            Tuple of (workspace_path, cache_level) or (None, None) if failed
        """
        # Try to use cached workspace
        cached_workspace, cache_level = self._get_cached_workspace(config)
        workspace_path = Path(tempfile.mkdtemp(prefix="zmk_"))

        if cached_workspace:
            # Create temporary workspace and copy from cache
            try:
                # Copy cached workspace
                for subdir in ["modules", "zephyr", "zmk"]:
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
                self.logger.info("Using cached workspace (%s level)", cache_level)
                return workspace_path, cache_level
            except Exception as e:
                exc_info = self.logger.isEnabledFor(logging.DEBUG)
                self.logger.warning(
                    "Failed to use cached workspace: %s", e, exc_info=exc_info
                )
                shutil.rmtree(workspace_path, ignore_errors=True)

        # Create fresh workspace (no cache level)
        self._setup_workspace(keymap_file, config_file, config, workspace_path)
        return workspace_path, None

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
        self, workspace_path: Path, cache_level: str | None = None
    ) -> bool:
        """Determine if west update should be run based on cache level.

        Args:
            workspace_path: Path to the workspace
            cache_level: Cache level used ('base', 'branch', 'full', 'build')

        Returns:
            True if west update should be run
        """
        # Always update for fresh workspaces (no cache level)
        if not cache_level:
            self.logger.info("Running west update for fresh workspace")
            return True

        # Update policy based on cache level completeness:
        # - base: Always update (least complete, dependencies may be missing)
        # - branch: Never update (branch-specific dependencies should be stable)
        # - full: Never update (most complete, all dependencies present)
        # - build: Always update (build-specific, needs latest for accuracy)

        if cache_level == "base":
            self.logger.info(
                "Running west update for base cache level (dependencies may be incomplete)"
            )
            return True
        elif cache_level in ["branch", "full"]:
            self.logger.info(
                "Skipping west update for %s cache level (dependencies should be complete)",
                cache_level,
            )
            return False
        elif cache_level == "build":
            self.logger.info(
                "Running west update for build cache level (ensuring latest dependencies)"
            )
            return True
        else:
            # Unknown cache level, err on the side of updating
            self.logger.warning(
                "Unknown cache level '%s', defaulting to west update", cache_level
            )
            return True

    def _run_compilation(
        self,
        workspace_path: Path,
        config: ZmkCompilationConfig,
        cache_level: str | None = None,
    ) -> bool:
        """Run Docker compilation with intelligent west update logic.

        Args:
            workspace_path: Path to the workspace
            config: ZMK compilation configuration
            cache_level: Cache level used for this workspace
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
            base_commands = ["cd /workspace", "west init -l config"]

            # Only run west update if needed based on cache level
            if self._should_run_west_update(workspace_path, cache_level):
                base_commands.append("west update")
                # Create update marker after successful update
                base_commands.append("touch /workspace/.west_last_update")

            # Always run west zephyr-export to set up Zephyr environment variables
            base_commands.append("west zephyr-export")

            all_commands = base_commands + build_commands

            # Use current user context to avoid permission issues
            user_context = DockerUserContext.detect_current_user()

            self.logger.info("Running Docker compilation")

            result: tuple[int, list[str], list[str]] = (
                self.docker_adapter.run_container(
                    image=config.image,
                    command=["sh", "-c", " && ".join(all_commands)],
                    volumes=[(str(workspace_path), "/workspace")],
                    environment={"JOBS": "4"},
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
            if self.cache:
                cached_verification = self.cache.get(image_cache_key)

                if cached_verification:
                    return True

            # Check if image exists
            if self.docker_adapter.image_exists(image_name, image_tag):
                # Cache verification for 1 hour to avoid repeated checks
                if self.cache:
                    self.cache.set(image_cache_key, True, ttl=self.CACHE_TTL_BUILD)
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
                if self.cache:
                    self.cache.set(image_cache_key, True, ttl=self.CACHE_TTL_BUILD)
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
    cache: CacheManager | None = None,
    workspace_cache_service: ZmkWorkspaceCacheService | None = None,
) -> ZmkWestService:
    """Create ZMK West service with comprehensive cache management.

    Args:
        docker_adapter: Docker adapter for container operations
        user_config: User configuration with cache settings
        cache: Optional cache manager instance
        workspace_cache_service: Optional workspace cache service

    Returns:
        Configured ZmkWestService instance
    """
    return ZmkWestService(
        docker_adapter=docker_adapter,
        user_config=user_config,
        cache=cache,
        workspace_cache_service=workspace_cache_service,
    )
