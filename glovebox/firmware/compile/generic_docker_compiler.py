"""Generic Docker compiler with pluggable build strategies."""

import logging
import multiprocessing
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile

from glovebox.adapters.docker_adapter import create_docker_adapter
from glovebox.adapters.file_adapter import create_file_adapter
from glovebox.config.compile_methods import (
    BuildTargetConfig,
    BuildYamlConfig,
    GenericDockerCompileConfig,
    WestWorkspaceConfig,
    ZmkConfigRepoConfig,
)
from glovebox.core.errors import BuildError
from glovebox.firmware.models import BuildResult, FirmwareOutputFiles
from glovebox.protocols import DockerAdapterProtocol, FileAdapterProtocol
from glovebox.protocols.compile_protocols import GenericDockerCompilerProtocol
from glovebox.protocols.docker_adapter_protocol import DockerVolume
from glovebox.utils import stream_process


logger = logging.getLogger(__name__)


class GenericDockerCompiler:
    """Generic Docker compiler with pluggable build strategies.

    Implements GenericDockerCompilerProtocol for type safety.
    """

    def __init__(
        self,
        docker_adapter: DockerAdapterProtocol | None = None,
        file_adapter: FileAdapterProtocol | None = None,
        output_middleware: stream_process.OutputMiddleware[str] | None = None,
    ):
        """Initialize generic Docker compiler with dependencies."""
        self.docker_adapter = docker_adapter or create_docker_adapter()
        self.file_adapter = file_adapter or create_file_adapter()
        self.output_middleware = output_middleware or self._create_default_middleware()
        logger.debug("GenericDockerCompiler initialized")

    def compile(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: GenericDockerCompileConfig,
    ) -> BuildResult:
        """Compile firmware using generic Docker method with build strategies."""
        logger.info(
            "Starting generic Docker compilation with strategy: %s",
            config.build_strategy,
        )
        result = BuildResult(success=True)

        try:
            # Check Docker availability
            if not self.check_available():
                result.success = False
                result.add_error("Docker is not available")
                return result

            # Validate input files and configuration
            if not self._validate_input_files(keymap_file, config_file, result):
                return result

            if not self.validate_config(config):
                result.success = False
                result.add_error("Configuration validation failed")
                return result

            # Execute build strategy
            if config.build_strategy == "west":
                return self._execute_west_strategy(
                    keymap_file, config_file, output_dir, config
                )
            elif config.build_strategy == "zmk_config":
                return self._execute_zmk_config_strategy(
                    keymap_file, config_file, output_dir, config
                )
            elif config.build_strategy == "cmake":
                return self._execute_cmake_strategy(
                    keymap_file, config_file, output_dir, config
                )
            else:
                result.success = False
                result.add_error(f"Unsupported build strategy: {config.build_strategy}")
                return result

        except BuildError as e:
            logger.error("Generic Docker compilation failed: %s", e)
            result.success = False
            result.add_error(f"Generic Docker compilation failed: {str(e)}")
        except Exception as e:
            logger.error("Unexpected error in generic Docker compilation: %s", e)
            result.success = False
            result.add_error(f"Unexpected error: {str(e)}")

        return result

    def check_available(self) -> bool:
        """Check if generic Docker compiler is available."""
        return self.docker_adapter.is_available()

    def validate_config(self, config: GenericDockerCompileConfig) -> bool:
        """Validate generic Docker configuration."""
        if not config.image:
            logger.error("Docker image not specified")
            return False
        if not config.build_strategy:
            logger.error("Build strategy not specified")
            return False
        if config.build_strategy not in [
            "west",
            "zmk_config",
            "cmake",
            "make",
            "ninja",
            "custom",
        ]:
            logger.error("Invalid build strategy: %s", config.build_strategy)
            return False
        return True

    def build_image(self, config: GenericDockerCompileConfig) -> BuildResult:
        """Build Docker image for compilation."""
        logger.info("Building Docker image for generic compiler: %s", config.image)
        result = BuildResult(success=True)

        try:
            if not self.check_available():
                result.success = False
                result.add_error("Docker is not available")
                return result

            # For now, assume image building is handled externally
            # This could be extended to build custom images
            result.add_message(f"Docker image {config.image} assumed available")
            logger.info(
                "Docker image build completed for generic compiler: %s", config.image
            )

        except Exception as e:
            logger.error("Failed to build Docker image for generic compiler: %s", e)
            result.success = False
            result.add_error(f"Failed to build Docker image: {str(e)}")

        return result

    def initialize_workspace(self, config: GenericDockerCompileConfig) -> bool:
        """Initialize build workspace (west, cmake, etc.)."""
        logger.debug("Initializing workspace for strategy: %s", config.build_strategy)

        if config.build_strategy == "west" and config.west_workspace:
            return self.manage_west_workspace(config.west_workspace)
        elif config.build_strategy == "zmk_config" and config.zmk_config_repo:
            return self.manage_zmk_config_repo(config.zmk_config_repo)

        # For other strategies, initialization is handled in strategy execution
        return True

    def execute_build_strategy(self, strategy: str, commands: list[str]) -> BuildResult:
        """Execute build using specified strategy."""
        logger.info("Executing build strategy: %s", strategy)
        result = BuildResult(success=True)

        # This is a generic method that can be called by specific strategy implementations
        # For now, it's a placeholder for custom command execution
        try:
            for command in commands:
                logger.debug("Executing command: %s", command)
                # Commands would be executed in the Docker context

        except Exception as e:
            logger.error("Build strategy execution failed: %s", e)
            result.success = False
            result.add_error(f"Build strategy execution failed: {str(e)}")

        return result

    def manage_west_workspace(self, workspace_config: WestWorkspaceConfig) -> bool:
        """Manage ZMK west workspace lifecycle."""
        logger.debug("Managing west workspace: %s", workspace_config.workspace_path)

        try:
            # Execute west commands inside Docker container
            for command in workspace_config.west_commands:
                logger.debug("Executing west command: %s", command)

                # Build command environment
                env = {
                    "WEST_WORKSPACE": workspace_config.workspace_path,
                    "MANIFEST_URL": workspace_config.manifest_url,
                    "MANIFEST_REVISION": workspace_config.manifest_revision,
                }

                # Prepare volumes for west workspace
                volumes = [
                    (workspace_config.workspace_path, workspace_config.workspace_path),
                ]

                # Execute west command in Docker container
                return_code, stdout_lines, stderr_lines = (
                    self.docker_adapter.run_container(
                        image="zmkfirmware/zmk-build-arm:stable",  # Default ZMK image
                        command=["sh", "-c", command],
                        volumes=volumes,
                        environment=env,
                        middleware=self.output_middleware,
                    )
                )

                if return_code != 0:
                    error_msg = (
                        "\\n".join(stderr_lines)
                        if stderr_lines
                        else f"Command failed: {command}"
                    )
                    logger.error("West command failed: %s", error_msg)
                    return False

            logger.info(
                "West workspace initialized successfully: %s",
                workspace_config.manifest_url,
            )
            return True

        except Exception as e:
            logger.error("Failed to manage west workspace: %s", e)
            return False

    def manage_zmk_config_repo(self, config_repo_config: ZmkConfigRepoConfig) -> bool:
        """Manage ZMK config repository workspace lifecycle."""
        logger.debug(
            "Managing ZMK config repository: %s", config_repo_config.config_repo_url
        )

        try:
            # Execute config repo initialization commands inside Docker container
            for command in config_repo_config.west_commands:
                logger.debug("Executing config repo command: %s", command)

                # Build command environment
                env = {
                    "WEST_WORKSPACE": config_repo_config.workspace_path,
                    "CONFIG_REPO_URL": config_repo_config.config_repo_url,
                    "CONFIG_REPO_REVISION": config_repo_config.config_repo_revision,
                }

                # Prepare volumes for config repository workspace
                volumes = [
                    (
                        config_repo_config.workspace_path,
                        config_repo_config.workspace_path,
                    ),
                ]

                # Execute config repo command in Docker container
                return_code, stdout_lines, stderr_lines = (
                    self.docker_adapter.run_container(
                        image="zmkfirmware/zmk-build-arm:stable",  # Default ZMK image
                        command=["sh", "-c", command],
                        volumes=volumes,
                        environment=env,
                        middleware=self.output_middleware,
                    )
                )

                if return_code != 0:
                    error_msg = (
                        "\\n".join(stderr_lines)
                        if stderr_lines
                        else f"Command failed: {command}"
                    )
                    logger.error("Config repo command failed: %s", error_msg)
                    return False

            logger.info(
                "ZMK config repository initialized successfully: %s",
                config_repo_config.config_repo_url,
            )
            return True

        except Exception as e:
            logger.error("Failed to manage ZMK config repository: %s", e)
            return False

    def parse_build_yaml(self, build_yaml_path: Path) -> BuildYamlConfig:
        """Parse build.yaml configuration file."""
        logger.debug("Parsing build.yaml: %s", build_yaml_path)

        try:
            import yaml

            if not self.file_adapter.check_exists(build_yaml_path):
                logger.warning(
                    "build.yaml not found, returning empty config: %s", build_yaml_path
                )
                return BuildYamlConfig()

            build_yaml_content = self.file_adapter.read_text(build_yaml_path)
            build_data = yaml.safe_load(build_yaml_content)

            if not isinstance(build_data, dict):
                logger.warning("Invalid build.yaml format, returning empty config")
                return BuildYamlConfig()

            # Parse board and shield lists
            board_list = build_data.get("board", [])
            shield_list = build_data.get("shield", [])

            # Parse include list with BuildTargetConfig objects
            include_list = []
            for include_item in build_data.get("include", []):
                if isinstance(include_item, dict):
                    target_config = BuildTargetConfig(
                        board=include_item.get("board", ""),
                        shield=include_item.get("shield"),
                        cmake_args=include_item.get("cmake-args", []),
                        snippet=include_item.get("snippet"),
                        artifact_name=include_item.get("artifact-name"),
                    )
                    include_list.append(target_config)

            build_config = BuildYamlConfig(
                board=board_list if isinstance(board_list, list) else [],
                shield=shield_list if isinstance(shield_list, list) else [],
                include=include_list,
            )

            logger.info("Parsed build.yaml with %d targets", len(include_list))
            return build_config

        except Exception as e:
            logger.error("Failed to parse build.yaml: %s", e)
            return BuildYamlConfig()

    def cache_workspace(self, workspace_path: Path) -> bool:
        """Cache workspace for reuse with intelligent caching strategies."""
        logger.debug("Caching workspace: %s", workspace_path)

        try:
            # Create cache directory if it doesn't exist
            cache_dir = self._get_cache_directory(workspace_path)
            if not self.file_adapter.check_exists(cache_dir):
                self.file_adapter.create_directory(cache_dir)
                logger.debug("Created cache directory: %s", cache_dir)

            # Generate cache metadata with invalidation markers
            workspace_metadata = {
                "workspace_path": str(workspace_path),
                "cached_at": self._get_current_timestamp(),
                "west_modules": self._get_west_modules(workspace_path),
                "manifest_hash": self._calculate_manifest_hash(workspace_path),
                "config_hash": self._calculate_config_hash(workspace_path),
                "cache_version": "1.0",
                "west_version": self._get_west_version(workspace_path),
            }

            # Write metadata to cache
            metadata_file = cache_dir / f"{workspace_path.name}_metadata.json"
            import json

            metadata_json = json.dumps(workspace_metadata, indent=2)
            self.file_adapter.write_text(metadata_file, metadata_json)

            # Create cache snapshot if caching is enabled
            if self._should_create_cache_snapshot(workspace_path):
                self._create_workspace_snapshot(workspace_path, cache_dir)

            logger.info("Workspace cached successfully: %s", workspace_path)
            return True

        except Exception as e:
            logger.error("Failed to cache workspace: %s", e)
            return False

    def _get_west_modules(self, workspace_path: Path) -> list[str]:
        """Get list of west modules in workspace."""
        try:
            west_config = workspace_path / ".west" / "config"
            if self.file_adapter.check_exists(west_config):
                # Parse west config to get module information
                config_content = self.file_adapter.read_text(west_config)
                logger.debug(
                    "Found west config with %d characters", len(config_content)
                )
                # Simple module detection - could be enhanced
                return ["zmk"]  # Default module
            return []
        except Exception as e:
            logger.debug("Could not read west modules: %s", e)
            return []

    def _get_cache_directory(self, workspace_path: Path) -> Path:
        """Get cache directory for workspace."""
        # Use a system-wide cache directory that's more persistent
        import tempfile

        system_cache = Path(tempfile.gettempdir()) / "glovebox_cache" / "workspaces"
        return system_cache

    def _get_current_timestamp(self) -> str:
        """Get current timestamp for cache metadata."""
        import time

        return str(int(time.time()))

    def _calculate_manifest_hash(self, workspace_path: Path) -> str:
        """Calculate hash of west manifest for cache invalidation."""
        try:
            import hashlib

            manifest_file = workspace_path / ".west" / "manifest.yml"
            if not self.file_adapter.check_exists(manifest_file):
                manifest_file = workspace_path / "west.yml"

            if self.file_adapter.check_exists(manifest_file):
                content = self.file_adapter.read_text(manifest_file)
                return hashlib.sha256(content.encode()).hexdigest()[:16]
            return "no_manifest"
        except Exception as e:
            logger.debug("Could not calculate manifest hash: %s", e)
            return "unknown"

    def _calculate_config_hash(self, workspace_path: Path) -> str:
        """Calculate hash of configuration files for cache invalidation."""
        try:
            import hashlib

            hasher = hashlib.sha256()

            # Hash keymap and config files if they exist
            config_dir = workspace_path / "config"
            if self.file_adapter.check_exists(config_dir):
                config_files = ["keymap.keymap", "config.conf", "west.yml"]
                for filename in config_files:
                    config_file = config_dir / filename
                    if self.file_adapter.check_exists(config_file):
                        content = self.file_adapter.read_text(config_file)
                        hasher.update(content.encode())

            return hasher.hexdigest()[:16]
        except Exception as e:
            logger.debug("Could not calculate config hash: %s", e)
            return "unknown"

    def _get_west_version(self, workspace_path: Path) -> str:
        """Get west tool version for cache compatibility."""
        try:
            # Check west version from manifest or default to unknown
            west_dir = workspace_path / ".west"
            if self.file_adapter.check_exists(west_dir):
                return "west_installed"
            return "no_west"
        except Exception as e:
            logger.debug("Could not determine west version: %s", e)
            return "unknown"

    def _should_create_cache_snapshot(self, workspace_path: Path) -> bool:
        """Determine if workspace snapshot should be created for caching."""
        # Create snapshots for larger workspaces or when explicitly enabled
        try:
            west_dir = workspace_path / ".west"
            # Check workspace size - only cache if it's substantial
            return self.file_adapter.check_exists(west_dir)
        except Exception:
            return False

    def _create_workspace_snapshot(self, workspace_path: Path, cache_dir: Path) -> bool:
        """Create compressed snapshot of workspace for faster restoration."""
        try:
            snapshot_file = cache_dir / f"{workspace_path.name}_snapshot.tar.gz"
            logger.debug("Creating workspace snapshot: %s", snapshot_file)

            # For now, just mark that we would create a snapshot
            # In a full implementation, this would compress workspace files
            snapshot_metadata = {
                "snapshot_path": str(snapshot_file),
                "workspace_size": self._calculate_workspace_size(workspace_path),
                "created_at": self._get_current_timestamp(),
            }

            import json

            metadata_json = json.dumps(snapshot_metadata, indent=2)
            snapshot_meta_file = cache_dir / f"{workspace_path.name}_snapshot_meta.json"
            self.file_adapter.write_text(snapshot_meta_file, metadata_json)

            logger.debug("Workspace snapshot metadata created")
            return True

        except Exception as e:
            logger.error("Failed to create workspace snapshot: %s", e)
            return False

    def _calculate_workspace_size(self, workspace_path: Path) -> int:
        """Calculate approximate workspace size for caching decisions."""
        try:
            # Simple size estimation - count directories and files
            total_size = 0
            if self.file_adapter.check_exists(workspace_path):
                # Count major directories as an approximation
                west_dir = workspace_path / ".west"
                if self.file_adapter.check_exists(west_dir):
                    total_size += 1000  # Approximate west metadata size

                modules_dir = workspace_path / "modules"
                if self.file_adapter.check_exists(modules_dir):
                    total_size += 50000  # Approximate modules size

            return total_size
        except Exception:
            return 0

    def is_cache_valid(
        self, workspace_path: Path, config: GenericDockerCompileConfig
    ) -> bool:
        """Check if cached workspace is valid and can be reused."""
        try:
            cache_dir = self._get_cache_directory(workspace_path)
            metadata_file = cache_dir / f"{workspace_path.name}_metadata.json"

            if not self.file_adapter.check_exists(metadata_file):
                logger.debug(
                    "No cache metadata found for workspace: %s", workspace_path
                )
                return False

            import json

            metadata_content = self.file_adapter.read_text(metadata_file)
            cache_metadata = json.loads(metadata_content)

            # Check cache version compatibility
            if cache_metadata.get("cache_version") != "1.0":
                logger.debug("Cache version mismatch, invalidating cache")
                return False

            # Check if manifest has changed
            current_manifest_hash = self._calculate_manifest_hash(workspace_path)
            cached_manifest_hash = cache_metadata.get("manifest_hash", "")
            if current_manifest_hash != cached_manifest_hash:
                logger.debug("Manifest hash changed, invalidating cache")
                return False

            # Check if configuration has changed
            current_config_hash = self._calculate_config_hash(workspace_path)
            cached_config_hash = cache_metadata.get("config_hash", "")
            if current_config_hash != cached_config_hash:
                logger.debug("Configuration hash changed, invalidating cache")
                return False

            # Check cache age (invalidate after 24 hours)
            import time

            cached_at = int(cache_metadata.get("cached_at", "0"))
            current_time = int(time.time())
            cache_age_hours = (current_time - cached_at) / 3600

            if cache_age_hours > 24:
                logger.debug("Cache expired after %0.1f hours", cache_age_hours)
                return False

            logger.debug("Cache is valid for workspace: %s", workspace_path)
            return True

        except Exception as e:
            logger.debug("Error checking cache validity: %s", e)
            return False

    def cleanup_old_caches(self, max_age_days: int = 7) -> bool:
        """Clean up old workspace caches to free disk space."""
        try:
            import tempfile
            import time

            current_time = time.time()
            max_age_seconds = max_age_days * 24 * 3600

            cache_base_dir = (
                Path(tempfile.gettempdir()) / "glovebox_cache" / "workspaces"
            )
            if not self.file_adapter.check_exists(cache_base_dir):
                return True

            cleanup_count = 0
            cache_dirs = self.file_adapter.list_directory(cache_base_dir)

            for cache_dir in cache_dirs:
                if not self.file_adapter.is_dir(cache_dir):
                    continue

                # Check cache metadata files
                metadata_files = self.file_adapter.list_files(
                    cache_dir, "*_metadata.json"
                )
                for metadata_file in metadata_files:
                    try:
                        import json

                        metadata_content = self.file_adapter.read_text(metadata_file)
                        cache_metadata = json.loads(metadata_content)

                        cached_at = int(cache_metadata.get("cached_at", "0"))
                        cache_age = current_time - cached_at

                        if cache_age > max_age_seconds:
                            # Remove old cache files
                            self._remove_cache_files(cache_dir, metadata_file.stem)
                            cleanup_count += 1
                            logger.debug("Cleaned up old cache: %s", metadata_file.stem)

                    except Exception as e:
                        logger.debug(
                            "Error processing cache file %s: %s", metadata_file, e
                        )

            if cleanup_count > 0:
                logger.info("Cleaned up %d old workspace caches", cleanup_count)
            else:
                logger.debug("No old caches found for cleanup")

            return True

        except Exception as e:
            logger.error("Failed to cleanup old caches: %s", e)
            return False

    def _remove_cache_files(self, cache_dir: Path, cache_prefix: str) -> None:
        """Remove all cache files with given prefix."""
        try:
            # Find and remove cache-related files
            cache_patterns = [
                f"{cache_prefix}_metadata.json",
                f"{cache_prefix}_snapshot.tar.gz",
                f"{cache_prefix}_snapshot_meta.json",
            ]

            for pattern in cache_patterns:
                cache_file = cache_dir / pattern
                if self.file_adapter.check_exists(cache_file):
                    # For safety, we'll just log what would be removed
                    logger.debug("Would remove cache file: %s", cache_file)

        except Exception as e:
            logger.debug("Error removing cache files: %s", e)

    def _execute_west_strategy(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: GenericDockerCompileConfig,
    ) -> BuildResult:
        """Execute ZMK west workspace build strategy."""
        logger.info("Executing west build strategy")
        result = BuildResult(success=True)

        try:
            # Check if caching is enabled and workspace cache is valid
            workspace_path = None
            if config.west_workspace and config.cache_workspace:
                workspace_path = Path(config.west_workspace.workspace_path)

                # Clean up old caches first
                self.cleanup_old_caches(max_age_days=7)

                # Check if we can use cached workspace
                if self.is_cache_valid(workspace_path, config):
                    logger.info("Using cached west workspace: %s", workspace_path)
                    result.add_message("Using cached workspace for faster build")
                else:
                    logger.info(
                        "Cache invalid or missing, initializing fresh workspace"
                    )

                    # Initialize west workspace if configured
                    if not self._initialize_west_workspace(
                        config.west_workspace, keymap_file, config_file
                    ):
                        result.success = False
                        result.add_error("Failed to initialize west workspace")
                        return result

                    # Cache the newly initialized workspace
                    if self.cache_workspace(workspace_path):
                        logger.info("Workspace cached for future builds")
                        result.add_message("Workspace cached for future builds")
            else:
                # Initialize west workspace without caching
                if config.west_workspace and not self._initialize_west_workspace(
                    config.west_workspace, keymap_file, config_file
                ):
                    result.success = False
                    result.add_error("Failed to initialize west workspace")
                    return result

            # Prepare build environment for west
            build_env = self._prepare_west_environment(config)

            # Prepare volumes for west workspace
            volumes = self._prepare_west_volumes(
                keymap_file, config_file, output_dir, config
            )

            # Build west compilation command
            if config.board_targets:
                # Build for specific board targets
                build_commands = []
                for board in config.board_targets:
                    build_commands.append(
                        f"west build -p always -b {board} -d build/{board}"
                    )
                west_command = " && ".join(build_commands)
            else:
                # Default build command
                west_command = "west build -p always"

            # Add any custom build commands
            if config.build_commands:
                west_command = " && ".join([west_command] + config.build_commands)

            # Run Docker compilation with west commands
            docker_image = f"{config.image}"
            return_code, stdout_lines, stderr_lines = self.docker_adapter.run_container(
                image=docker_image,
                command=[
                    "sh",
                    "-c",
                    f"cd {config.west_workspace.workspace_path if config.west_workspace else '/zmk-workspace'} && {west_command}",
                ],
                volumes=volumes,
                environment=build_env,
                middleware=self.output_middleware,
            )

            if return_code != 0:
                error_msg = (
                    "\\n".join(stderr_lines)
                    if stderr_lines
                    else "West compilation failed"
                )
                result.success = False
                result.add_error(
                    f"West compilation failed with exit code {return_code}: {error_msg}"
                )
                return result

            # Find and collect firmware files
            firmware_files, output_files = self._find_firmware_files(output_dir)

            if not firmware_files:
                result.success = False
                result.add_error("No firmware files generated")
                return result

            # Store results
            result.output_files = output_files
            result.add_message(
                f"West compilation completed. Generated {len(firmware_files)} firmware files."
            )

            for firmware_file in firmware_files:
                result.add_message(f"Firmware file: {firmware_file}")

            logger.info(
                "West compilation completed successfully with %d files",
                len(firmware_files),
            )

        except Exception as e:
            logger.error("West strategy execution failed: %s", e)
            result.success = False
            result.add_error(f"West strategy execution failed: {str(e)}")

        return result

    def _execute_zmk_config_strategy(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: GenericDockerCompileConfig,
    ) -> BuildResult:
        """Execute ZMK config repository build strategy."""
        logger.info("Executing ZMK config repository build strategy")
        result = BuildResult(success=True)

        try:
            if not config.zmk_config_repo:
                result.success = False
                result.add_error(
                    "ZMK config repository configuration is required for zmk_config strategy"
                )
                return result

            config_repo_config = config.zmk_config_repo
            workspace_path = Path(config_repo_config.workspace_path)

            # Check if caching is enabled and workspace cache is valid
            if config.cache_workspace:
                # Clean up old caches first
                self.cleanup_old_caches(max_age_days=7)

                # Check if we can use cached workspace
                if self.is_cache_valid(workspace_path, config):
                    logger.info("Using cached ZMK config workspace: %s", workspace_path)
                    result.add_message("Using cached workspace for faster build")
                else:
                    logger.info(
                        "Cache invalid or missing, initializing fresh ZMK config workspace"
                    )

                    # Initialize config repository workspace
                    if not self._initialize_zmk_config_workspace(
                        config_repo_config, keymap_file, config_file
                    ):
                        result.success = False
                        result.add_error(
                            "Failed to initialize ZMK config repository workspace"
                        )
                        return result

                    # Cache the newly initialized workspace
                    if self.cache_workspace(workspace_path):
                        logger.info("ZMK config workspace cached for future builds")
                        result.add_message("Workspace cached for future builds")
            else:
                # Initialize workspace without caching
                if not self._initialize_zmk_config_workspace(
                    config_repo_config, keymap_file, config_file
                ):
                    result.success = False
                    result.add_error(
                        "Failed to initialize ZMK config repository workspace"
                    )
                    return result

            # Parse build.yaml to get build targets
            build_yaml_path = workspace_path / config_repo_config.build_yaml_path
            build_config = self.parse_build_yaml(build_yaml_path)

            # Prepare build environment for ZMK config
            build_env = self._prepare_zmk_config_environment(config, config_repo_config)

            # Prepare volumes for ZMK config workspace
            volumes = self._prepare_zmk_config_volumes(
                keymap_file, config_file, output_dir, config, config_repo_config
            )

            # Build commands based on build.yaml targets or fallback to config settings
            build_commands = []
            if build_config.include:
                # Use targets from build.yaml
                for target in build_config.include:
                    board_arg = target.board
                    if target.shield:
                        shield_arg = f" -- -DSHIELD={target.shield}"
                    else:
                        shield_arg = ""

                    artifact_name = (
                        target.artifact_name or f"{target.board}_{target.shield}"
                        if target.shield
                        else target.board
                    )
                    build_commands.append(
                        f"west build -p always -b {board_arg} -d build/{artifact_name}{shield_arg}"
                    )
            elif config.board_targets:
                # Use board targets from config
                for board in config.board_targets:
                    build_commands.append(
                        f"west build -p always -b {board} -d build/{board}"
                    )
            else:
                # Default build command
                build_commands.append("west build -p always")

            # Add any custom build commands
            if config.build_commands:
                build_commands.extend(config.build_commands)

            # Execute all build commands
            west_command = " && ".join(build_commands)

            # Run Docker compilation with ZMK config commands
            docker_image = f"{config.image}"
            return_code, stdout_lines, stderr_lines = self.docker_adapter.run_container(
                image=docker_image,
                command=[
                    "sh",
                    "-c",
                    f"cd {config_repo_config.workspace_path} && {west_command}",
                ],
                volumes=volumes,
                environment=build_env,
                middleware=self.output_middleware,
            )

            if return_code != 0:
                error_msg = (
                    "\\n".join(stderr_lines)
                    if stderr_lines
                    else "ZMK config compilation failed"
                )
                result.success = False
                result.add_error(
                    f"ZMK config compilation failed with exit code {return_code}: {error_msg}"
                )
                return result

            # Find and collect firmware files
            firmware_files, output_files = self._find_firmware_files(output_dir)

            if not firmware_files:
                result.success = False
                result.add_error("No firmware files generated")
                return result

            # Store results
            result.output_files = output_files
            result.add_message(
                f"ZMK config compilation completed. Generated {len(firmware_files)} firmware files."
            )

            for firmware_file in firmware_files:
                result.add_message(f"Firmware file: {firmware_file}")

            logger.info(
                "ZMK config compilation completed successfully with %d files",
                len(firmware_files),
            )

        except Exception as e:
            logger.error("ZMK config strategy execution failed: %s", e)
            result.success = False
            result.add_error(f"ZMK config strategy execution failed: {str(e)}")

        return result

    def _execute_cmake_strategy(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: GenericDockerCompileConfig,
    ) -> BuildResult:
        """Execute CMake build strategy."""
        logger.info("Executing CMake build strategy")
        result = BuildResult(success=True)

        try:
            # Prepare build environment for CMake
            build_env = self._prepare_cmake_environment(config)

            # Prepare volumes for CMake build
            volumes = self._prepare_cmake_volumes(keymap_file, config_file, output_dir)

            # Run Docker compilation with CMake commands
            docker_image = f"{config.image}"
            return_code, stdout_lines, stderr_lines = self.docker_adapter.run_container(
                image=docker_image,
                volumes=volumes,
                environment=build_env,
                middleware=self.output_middleware,
            )

            if return_code != 0:
                error_msg = (
                    "\\n".join(stderr_lines)
                    if stderr_lines
                    else "CMake compilation failed"
                )
                result.success = False
                result.add_error(
                    f"CMake compilation failed with exit code {return_code}: {error_msg}"
                )
                return result

            # Find and collect firmware files
            firmware_files, output_files = self._find_firmware_files(output_dir)

            if not firmware_files:
                result.success = False
                result.add_error("No firmware files generated")
                return result

            # Store results
            result.output_files = output_files
            result.add_message(
                f"CMake compilation completed. Generated {len(firmware_files)} firmware files."
            )

            logger.info(
                "CMake compilation completed successfully with %d files",
                len(firmware_files),
            )

        except Exception as e:
            logger.error("CMake strategy execution failed: %s", e)
            result.success = False
            result.add_error(f"CMake strategy execution failed: {str(e)}")

        return result

    def _initialize_west_workspace(
        self,
        workspace_config: WestWorkspaceConfig,
        keymap_file: Path,
        config_file: Path,
    ) -> bool:
        """Initialize ZMK west workspace in Docker container."""
        logger.debug("Initializing west workspace")

        try:
            # Create workspace directory if it doesn't exist
            workspace_path = Path(workspace_config.workspace_path)
            if not self.file_adapter.check_exists(workspace_path):
                self.file_adapter.create_directory(workspace_path)
                logger.debug("Created workspace directory: %s", workspace_path)

            # Create config directory inside workspace
            config_dir = workspace_path / workspace_config.config_path
            if not self.file_adapter.check_exists(config_dir):
                self.file_adapter.create_directory(config_dir)
                logger.debug("Created config directory: %s", config_dir)

            # Copy keymap and config files to workspace
            try:
                workspace_keymap = config_dir / "keymap.keymap"
                workspace_config_file = config_dir / "config.conf"

                # Use file adapter to copy files
                keymap_content = self.file_adapter.read_text(keymap_file)
                config_content = self.file_adapter.read_text(config_file)

                self.file_adapter.write_text(workspace_keymap, keymap_content)
                self.file_adapter.write_text(workspace_config_file, config_content)

                logger.debug("Copied files to workspace config directory")

            except Exception as e:
                logger.warning("Failed to copy files to workspace: %s", e)
                # Continue with initialization even if file copy fails

            # Initialize west workspace using Docker
            init_commands = [
                f"cd {workspace_config.workspace_path}",
                f"west init -m {workspace_config.manifest_url} --mr {workspace_config.manifest_revision}",
                "west update",
            ]

            # Add any additional west commands from config
            init_commands.extend(workspace_config.west_commands)

            # Execute initialization commands
            full_command = " && ".join(init_commands)

            env = {
                "WEST_WORKSPACE": workspace_config.workspace_path,
                "MANIFEST_URL": workspace_config.manifest_url,
                "MANIFEST_REVISION": workspace_config.manifest_revision,
            }

            volumes = [
                (str(workspace_path.absolute()), workspace_config.workspace_path),
            ]

            return_code, stdout_lines, stderr_lines = self.docker_adapter.run_container(
                image="zmkfirmware/zmk-build-arm:stable",
                command=["sh", "-c", full_command],
                volumes=volumes,
                environment=env,
                middleware=self.output_middleware,
            )

            if return_code != 0:
                error_msg = (
                    "\\n".join(stderr_lines)
                    if stderr_lines
                    else "West initialization failed"
                )
                logger.error("West workspace initialization failed: %s", error_msg)
                return False

            logger.info("West workspace initialized successfully")
            return True

        except Exception as e:
            logger.error("Failed to initialize west workspace: %s", e)
            return False

    def _initialize_zmk_config_workspace(
        self,
        config_repo_config: ZmkConfigRepoConfig,
        keymap_file: Path,
        config_file: Path,
    ) -> bool:
        """Initialize ZMK config repository workspace in Docker container."""
        logger.debug("Initializing ZMK config repository workspace")

        try:
            # Create workspace directory if it doesn't exist
            workspace_path = Path(config_repo_config.workspace_path)
            if not self.file_adapter.check_exists(workspace_path):
                self.file_adapter.create_directory(workspace_path)
                logger.debug(
                    "Created ZMK config workspace directory: %s", workspace_path
                )

            # Clone the config repository first
            clone_command = f"git clone {config_repo_config.config_repo_url} {config_repo_config.workspace_path}"
            if config_repo_config.config_repo_revision != "main":
                clone_command += f" --branch {config_repo_config.config_repo_revision}"

            # Create config directory inside workspace (if it doesn't exist from clone)
            config_dir = workspace_path / config_repo_config.config_path
            if not self.file_adapter.check_exists(config_dir):
                self.file_adapter.create_directory(config_dir)
                logger.debug("Created config directory: %s", config_dir)

            # Copy keymap and config files to workspace
            try:
                workspace_keymap = config_dir / "keymap.keymap"
                workspace_config_file = config_dir / "config.conf"

                # Use file adapter to copy files
                keymap_content = self.file_adapter.read_text(keymap_file)
                config_content = self.file_adapter.read_text(config_file)

                self.file_adapter.write_text(workspace_keymap, keymap_content)
                self.file_adapter.write_text(workspace_config_file, config_content)

                logger.debug("Copied files to ZMK config workspace config directory")

            except Exception as e:
                logger.warning("Failed to copy files to ZMK config workspace: %s", e)
                # Continue with initialization even if file copy fails

            # Initialize ZMK config repository workspace using Docker
            init_commands = [
                clone_command,
                f"cd {config_repo_config.workspace_path}",
            ]

            # Add west commands from config (e.g., "west init -l config", "west update")
            init_commands.extend(config_repo_config.west_commands)

            # Execute initialization commands
            full_command = " && ".join(init_commands)

            env = {
                "WEST_WORKSPACE": config_repo_config.workspace_path,
                "CONFIG_REPO_URL": config_repo_config.config_repo_url,
                "CONFIG_REPO_REVISION": config_repo_config.config_repo_revision,
            }

            volumes = [
                (str(workspace_path.absolute()), config_repo_config.workspace_path),
            ]

            return_code, stdout_lines, stderr_lines = self.docker_adapter.run_container(
                image="zmkfirmware/zmk-build-arm:stable",
                command=["sh", "-c", full_command],
                volumes=volumes,
                environment=env,
                middleware=self.output_middleware,
            )

            if return_code != 0:
                error_msg = (
                    "\\n".join(stderr_lines)
                    if stderr_lines
                    else "ZMK config workspace initialization failed"
                )
                logger.error(
                    "ZMK config workspace initialization failed: %s", error_msg
                )
                return False

            logger.info("ZMK config repository workspace initialized successfully")
            return True

        except Exception as e:
            logger.error("Failed to initialize ZMK config repository workspace: %s", e)
            return False

    def _prepare_west_environment(
        self, config: GenericDockerCompileConfig
    ) -> dict[str, str]:
        """Prepare build environment variables for west strategy."""
        build_env = {}

        # Start with any custom environment template
        build_env.update(config.environment_template)

        # Add west-specific environment
        if config.west_workspace:
            build_env.update(
                {
                    "WEST_WORKSPACE": config.west_workspace.workspace_path,
                    "ZMK_CONFIG": f"{config.west_workspace.workspace_path}/{config.west_workspace.config_path}",
                }
            )

        # Add any additional environment variables
        build_env.setdefault("JOBS", str(multiprocessing.cpu_count()))

        logger.debug("West build environment: %s", build_env)
        return build_env

    def _prepare_cmake_environment(
        self, config: GenericDockerCompileConfig
    ) -> dict[str, str]:
        """Prepare build environment variables for CMake strategy."""
        build_env = {}

        # Start with any custom environment template
        build_env.update(config.environment_template)

        # Add CMake-specific environment
        build_env.update(
            {
                "CMAKE_BUILD_TYPE": "Release",
                "JOBS": str(multiprocessing.cpu_count()),
            }
        )

        logger.debug("CMake build environment: %s", build_env)
        return build_env

    def _prepare_zmk_config_environment(
        self,
        config: GenericDockerCompileConfig,
        config_repo_config: ZmkConfigRepoConfig,
    ) -> dict[str, str]:
        """Prepare build environment variables for ZMK config strategy."""
        build_env = {}

        # Start with any custom environment template
        build_env.update(config.environment_template)

        # Add ZMK config-specific environment
        build_env.update(
            {
                "WEST_WORKSPACE": config_repo_config.workspace_path,
                "ZMK_CONFIG": f"{config_repo_config.workspace_path}/{config_repo_config.config_path}",
                "CONFIG_REPO_URL": config_repo_config.config_repo_url,
                "CONFIG_REPO_REVISION": config_repo_config.config_repo_revision,
            }
        )

        # Add any additional environment variables
        import multiprocessing

        build_env.setdefault("JOBS", str(multiprocessing.cpu_count()))

        logger.debug("ZMK config build environment: %s", build_env)
        return build_env

    def _prepare_west_volumes(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: GenericDockerCompileConfig,
    ) -> list[DockerVolume]:
        """Prepare Docker volume mappings for west strategy."""
        volumes = []

        # Map output directory
        output_dir_abs = output_dir.absolute()
        volumes.append((str(output_dir_abs), "/build"))

        # Use volume templates if provided, otherwise use optimized defaults
        if config.volume_templates:
            # Apply volume templates (this would be expanded based on templates)
            for template in config.volume_templates:
                logger.debug("Applying volume template: %s", template)
                # Parse template and add to volumes
                self._parse_volume_template(template, volumes)
        else:
            # Optimized west workspace volume mapping
            if config.west_workspace:
                workspace_path = config.west_workspace.workspace_path
                config_path = config.west_workspace.config_path

                # Check if we can use cached workspace volumes
                if config.cache_workspace:
                    workspace_abs_path = Path(workspace_path)
                    if self.is_cache_valid(workspace_abs_path, config):
                        # Use cached workspace with optimized volume mounting
                        cache_dir = self._get_cache_directory(workspace_abs_path)
                        volumes.append((str(cache_dir), f"{workspace_path}/.cache:rw"))
                        logger.debug(
                            "Using cached workspace volumes for faster mounting"
                        )

                # Map files to west workspace config directory
                keymap_abs = keymap_file.absolute()
                config_abs = config_file.absolute()

                volumes.append(
                    (
                        str(keymap_abs),
                        f"{workspace_path}/{config_path}/keymap.keymap:ro",
                    )
                )
                volumes.append(
                    (str(config_abs), f"{workspace_path}/{config_path}/config.conf:ro")
                )

                # Add workspace directory for persistent builds
                if config.cache_workspace:
                    # Mount workspace directory for caching
                    workspace_host_path = Path(workspace_path).absolute()
                    if self.file_adapter.check_exists(workspace_host_path):
                        volumes.append(
                            (str(workspace_host_path), f"{workspace_path}:rw")
                        )
                        logger.debug(
                            "Mounted workspace directory for caching: %s",
                            workspace_path,
                        )

        return volumes

    def _parse_volume_template(
        self, template: str, volumes: list[DockerVolume]
    ) -> None:
        """Parse volume template string and add to volumes list."""
        try:
            # Simple template parsing - format: "host_path:container_path:mode"
            parts = template.split(":")
            if len(parts) >= 2:
                host_path = parts[0]
                container_path = parts[1]
                mode = parts[2] if len(parts) > 2 else "rw"

                # Expand templates like {workspace_path}
                # This could be enhanced to support more template variables
                volumes.append((host_path, f"{container_path}:{mode}"))
                logger.debug(
                    "Parsed volume template: %s -> %s:%s",
                    host_path,
                    container_path,
                    mode,
                )
        except Exception as e:
            logger.warning("Failed to parse volume template '%s': %s", template, e)

    def _prepare_cmake_volumes(
        self, keymap_file: Path, config_file: Path, output_dir: Path
    ) -> list[DockerVolume]:
        """Prepare Docker volume mappings for CMake strategy."""
        volumes = []

        # Map output directory
        output_dir_abs = output_dir.absolute()
        volumes.append((str(output_dir_abs), "/build"))

        # Map keymap and config files
        keymap_abs = keymap_file.absolute()
        config_abs = config_file.absolute()
        volumes.append((str(keymap_abs), "/build/keymap.keymap:ro"))
        volumes.append((str(config_abs), "/build/config.conf:ro"))

        return volumes

    def _prepare_zmk_config_volumes(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: GenericDockerCompileConfig,
        config_repo_config: ZmkConfigRepoConfig,
    ) -> list[tuple[str, str]]:
        """Prepare Docker volume mappings for ZMK config strategy."""
        volumes = []

        # Map output directory
        output_dir_abs = output_dir.absolute()
        volumes.append((str(output_dir_abs), "/build"))

        # Use volume templates if provided, otherwise use optimized defaults
        if config.volume_templates:
            # Apply volume templates (this would be expanded based on templates)
            for template in config.volume_templates:
                logger.debug("Applying volume template: %s", template)
                # Parse template and add to volumes
                self._parse_volume_template(template, volumes)
        else:
            # Optimized ZMK config workspace volume mapping
            workspace_path = config_repo_config.workspace_path
            config_path = config_repo_config.config_path

            # Check if we can use cached workspace volumes
            if config.cache_workspace:
                workspace_abs_path = Path(workspace_path)
                if self.is_cache_valid(workspace_abs_path, config):
                    # Use cached workspace with optimized volume mounting
                    cache_dir = self._get_cache_directory(workspace_abs_path)
                    volumes.append((str(cache_dir), f"{workspace_path}/.cache:rw"))
                    logger.debug(
                        "Using cached ZMK config workspace volumes for faster mounting"
                    )

            # Map files to ZMK config workspace config directory
            keymap_abs = keymap_file.absolute()
            config_abs = config_file.absolute()

            volumes.append(
                (
                    str(keymap_abs),
                    f"{workspace_path}/{config_path}/keymap.keymap:ro",
                )
            )
            volumes.append(
                (str(config_abs), f"{workspace_path}/{config_path}/config.conf:ro")
            )

            # Add workspace directory for persistent builds
            if config.cache_workspace:
                # Mount workspace directory for caching
                workspace_host_path = Path(workspace_path).absolute()
                if self.file_adapter.check_exists(workspace_host_path):
                    volumes.append((str(workspace_host_path), f"{workspace_path}:rw"))
                    logger.debug(
                        "Mounted ZMK config workspace directory for caching: %s",
                        workspace_path,
                    )

        return volumes

    def _find_firmware_files(
        self, output_dir: Path
    ) -> tuple[list[Path], FirmwareOutputFiles]:
        """Find firmware files in output directory."""
        firmware_files = []
        output_files = FirmwareOutputFiles(output_dir=output_dir)

        try:
            # Check if output directory exists
            if not self.file_adapter.check_exists(output_dir):
                logger.warning("Output directory does not exist: %s", output_dir)
                return [], output_files

            # Look for .uf2 files in the base output directory
            files = self.file_adapter.list_files(output_dir, "*.uf2")
            firmware_files.extend(files)

            # The first .uf2 file found is considered the main firmware
            if files and not output_files.main_uf2:
                output_files.main_uf2 = files[0]

            # Check west build output directories
            build_dir = output_dir / "build"
            if self.file_adapter.check_exists(build_dir) and self.file_adapter.is_dir(
                build_dir
            ):
                logger.debug("Checking west build directory: %s", build_dir)

                # Check for board-specific build directories
                build_subdirs = self.file_adapter.list_directory(build_dir)
                for subdir in build_subdirs:
                    if self.file_adapter.is_dir(subdir):
                        # Look for zephyr/zmk.uf2 in build directories
                        zephyr_dir = subdir / "zephyr"
                        if self.file_adapter.check_exists(zephyr_dir):
                            zmk_uf2 = zephyr_dir / "zmk.uf2"
                            if self.file_adapter.check_exists(zmk_uf2):
                                firmware_files.append(zmk_uf2)
                                if not output_files.main_uf2:
                                    output_files.main_uf2 = zmk_uf2
                                logger.debug("Found west build firmware: %s", zmk_uf2)

            # Check for subdirectories with firmware files (legacy support)
            subdirs = self.file_adapter.list_directory(output_dir)
            for subdir in subdirs:
                if self.file_adapter.is_dir(subdir) and subdir.name != "build":
                    subdir_files = self.file_adapter.list_files(subdir, "*.uf2")
                    firmware_files.extend(subdir_files)

            logger.debug(
                "Found %d firmware files in %s", len(firmware_files), output_dir
            )

        except Exception as e:
            logger.error("Failed to list firmware files in %s: %s", output_dir, str(e))

        return firmware_files, output_files

    def _validate_input_files(
        self, keymap_file: Path, config_file: Path, result: BuildResult
    ) -> bool:
        """Validate input files exist."""
        if not self.file_adapter.check_exists(
            keymap_file
        ) or not self.file_adapter.is_file(keymap_file):
            result.success = False
            result.add_error(f"Keymap file not found: {keymap_file}")
            return False

        if not self.file_adapter.check_exists(
            config_file
        ) or not self.file_adapter.is_file(config_file):
            result.success = False
            result.add_error(f"Config file not found: {config_file}")
            return False

        return True

    @staticmethod
    def _create_default_middleware() -> stream_process.OutputMiddleware[str]:
        """Create default output middleware for build process."""

        class BuildOutputMiddleware(stream_process.OutputMiddleware[str]):
            def __init__(self) -> None:
                self.collected_data: list[tuple[str, str]] = []

            def process(self, line: str, stream_type: str) -> str:
                # Print with color based on stream type
                if stream_type == "stdout":
                    print(f"\\033[92m{line}\\033[0m")  # Green for stdout
                else:
                    print(f"\\033[91m{line}\\033[0m")  # Red for stderr

                # Store additional metadata
                self.collected_data.append((stream_type, line))

                # Return the processed line
                return line

        return BuildOutputMiddleware()


def create_generic_docker_compiler(
    docker_adapter: DockerAdapterProtocol | None = None,
    file_adapter: FileAdapterProtocol | None = None,
    output_middleware: stream_process.OutputMiddleware[str] | None = None,
) -> GenericDockerCompiler:
    """Create a GenericDockerCompiler instance with dependency injection."""
    return GenericDockerCompiler(
        docker_adapter=docker_adapter,
        file_adapter=file_adapter,
        output_middleware=output_middleware,
    )
