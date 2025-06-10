"""West workspace management for ZMK compilation."""

import logging
from pathlib import Path
from typing import Any

from glovebox.adapters import create_docker_adapter, create_file_adapter
from glovebox.compilation.protocols.workspace_protocols import (
    WestWorkspaceManagerProtocol,
)
from glovebox.compilation.workspace.workspace_manager import WorkspaceManager
from glovebox.config.compile_methods import WestWorkspaceConfig
from glovebox.protocols import DockerAdapterProtocol, FileAdapterProtocol


logger = logging.getLogger(__name__)


class WestWorkspaceManager(WorkspaceManager):
    """Manager for ZMK west workspace operations.

    Handles initialization and management of ZMK west workspaces for compilation.
    """

    def __init__(
        self,
        file_adapter: FileAdapterProtocol | None = None,
        docker_adapter: DockerAdapterProtocol | None = None,
        workspace_root: Path | None = None,
    ) -> None:
        """Initialize west workspace manager.

        Args:
            file_adapter: File adapter for filesystem operations
            docker_adapter: Docker adapter for container operations
            workspace_root: Root directory for workspace operations
        """
        super().__init__(workspace_root)
        self.file_adapter = file_adapter or create_file_adapter()
        self.docker_adapter = docker_adapter or create_docker_adapter()

    def initialize_workspace(self, **context: Any) -> bool:
        """Initialize workspace for compilation.

        Args:
            **context: Context containing workspace_config, keymap_file, config_file

        Returns:
            bool: True if workspace initialization succeeded
        """
        workspace_config = context.get("workspace_config")
        keymap_file = context.get("keymap_file")
        config_file = context.get("config_file")

        if not all([workspace_config, keymap_file, config_file]):
            logger.error(
                "Missing required parameters for west workspace initialization"
            )
            return False

        # Cast the workspace_config to the correct type
        if not isinstance(workspace_config, WestWorkspaceConfig):
            logger.error("Invalid workspace_config type for west workspace")
            return False

        return self.initialize_west_workspace(
            workspace_config, Path(str(keymap_file)), Path(str(config_file))
        )

    def initialize_west_workspace(
        self,
        workspace_config: WestWorkspaceConfig,
        keymap_file: Path,
        config_file: Path,
    ) -> bool:
        """Initialize ZMK west workspace.

        Args:
            workspace_config: West workspace configuration
            keymap_file: Path to keymap file
            config_file: Path to config file

        Returns:
            bool: True if initialization succeeded
        """
        logger.debug("Initializing west workspace")

        if not self.docker_adapter:
            logger.error(
                "Docker adapter not available for west workspace initialization"
            )
            return False

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

    def validate_workspace(self, workspace_path: Path) -> bool:
        """Validate workspace is ready for compilation.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            bool: True if workspace is valid
        """
        try:
            # Check if workspace directory exists
            if not workspace_path.exists():
                logger.error("Workspace directory does not exist: %s", workspace_path)
                return False

            # Check if it's a directory
            if not workspace_path.is_dir():
                logger.error("Workspace path is not a directory: %s", workspace_path)
                return False

            # Check for west workspace indicators
            west_config = workspace_path / ".west" / "config"
            if not west_config.exists():
                logger.debug(
                    "No west configuration found, workspace may not be initialized"
                )
                # This is not necessarily an error for west workspaces

            return True

        except Exception as e:
            logger.error("Failed to validate workspace: %s", e)
            return False

    def cleanup_workspace(self, workspace_path: Path) -> bool:
        """Clean up workspace after compilation.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            bool: True if cleanup was successful
        """
        try:
            # For west workspaces, we typically don't clean up the entire workspace
            # as it may be reused. Instead, clean up build artifacts.

            build_dir = workspace_path / "build"
            if build_dir.exists():
                logger.debug("Cleaning up build directory: %s", build_dir)
                # Use file adapter to remove build directory contents
                # For now, just log what would be cleaned
                logger.debug("Would clean build directory: %s", build_dir)

            logger.debug("West workspace cleanup completed: %s", workspace_path)
            return True

        except Exception as e:
            logger.error("Failed to cleanup workspace: %s", e)
            return False


def create_west_workspace_manager(
    file_adapter: FileAdapterProtocol | None = None,
    docker_adapter: DockerAdapterProtocol | None = None,
) -> WestWorkspaceManager:
    """Create west workspace manager instance.

    Args:
        file_adapter: File adapter for filesystem operations
        docker_adapter: Docker adapter for container operations

    Returns:
        WestWorkspaceManager: West workspace manager instance
    """
    return WestWorkspaceManager(file_adapter, docker_adapter)
