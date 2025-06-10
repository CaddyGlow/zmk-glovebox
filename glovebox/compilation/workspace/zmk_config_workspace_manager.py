"""ZMK config repository workspace manager."""

import logging
from pathlib import Path
from typing import Any

from glovebox.compilation.workspace.workspace_manager import (
    WorkspaceManager,
    WorkspaceManagerError,
)
from glovebox.config.compile_methods import ZmkConfigRepoConfig


logger = logging.getLogger(__name__)


class ZmkConfigWorkspaceManagerError(WorkspaceManagerError):
    """Error in ZMK config workspace management."""


class ZmkConfigWorkspaceManager(WorkspaceManager):
    """Manage ZMK config repository workspaces following GitHub Actions pattern.

    Handles ZMK config repository cloning, west workspace initialization,
    and user configuration integration for GitHub Actions-style builds.
    """

    def __init__(self, workspace_root: Path | None = None) -> None:
        """Initialize ZMK config workspace manager.

        Args:
            workspace_root: Root directory for workspace operations
        """
        super().__init__(workspace_root)

    def initialize_workspace(self, **context: Any) -> bool:
        """Initialize ZMK config workspace for compilation.

        Args:
            **context: Context including config_repo_config, keymap_file, config_file

        Returns:
            bool: True if workspace was initialized successfully

        Raises:
            ZmkConfigWorkspaceManagerError: If workspace initialization fails
        """
        try:
            config_repo_config = context.get("config_repo_config")
            if not isinstance(config_repo_config, ZmkConfigRepoConfig):
                raise ZmkConfigWorkspaceManagerError(
                    "config_repo_config is required for ZMK config workspace initialization"
                )

            workspace_path = context.get("workspace_path")
            if not workspace_path:
                workspace_path = self.workspace_root / "zmk_config"

            keymap_file = context.get("keymap_file")
            config_file = context.get("config_file")

            self.logger.info("Initializing ZMK config workspace: %s", workspace_path)

            # Create workspace directory
            self.ensure_workspace_directory(workspace_path)

            # Clone config repository
            if not self.clone_config_repository(config_repo_config, workspace_path):
                return False

            # Initialize west workspace
            if not self.initialize_west_workspace(workspace_path):
                return False

            # Copy user files if provided
            if (
                keymap_file
                and config_file
                and not self.copy_user_configuration(
                    workspace_path, keymap_file, config_file
                )
            ):
                return False

            self.logger.info("ZMK config workspace initialized successfully")
            return True

        except Exception as e:
            msg = f"Failed to initialize ZMK config workspace: {e}"
            self.logger.error(msg)
            raise ZmkConfigWorkspaceManagerError(msg) from e

    def validate_workspace(self, workspace_path: Path) -> bool:
        """Validate ZMK config workspace is ready for compilation.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            bool: True if workspace is valid

        Raises:
            ZmkConfigWorkspaceManagerError: If workspace validation fails
        """
        try:
            self.logger.debug("Validating ZMK config workspace: %s", workspace_path)

            # Check basic workspace requirements
            if not workspace_path.exists() or not workspace_path.is_dir():
                self.logger.warning(
                    "Workspace directory does not exist: %s", workspace_path
                )
                return False

            # Check for west workspace
            west_yml = workspace_path / "west.yml"
            if not west_yml.exists():
                self.logger.warning(
                    "west.yml not found in workspace: %s", workspace_path
                )
                return False

            # Check for config directory
            config_dir = workspace_path / "config"
            if not config_dir.exists() or not config_dir.is_dir():
                self.logger.warning("config directory not found: %s", config_dir)
                return False

            # Check for build.yaml (GitHub Actions pattern)
            build_yaml = workspace_path / "build.yaml"
            if not build_yaml.exists():
                self.logger.warning("build.yaml not found: %s", build_yaml)
                return False

            self.logger.debug("ZMK config workspace validation successful")
            return True

        except Exception as e:
            msg = f"Failed to validate ZMK config workspace: {e}"
            self.logger.error(msg)
            raise ZmkConfigWorkspaceManagerError(msg) from e

    def cleanup_workspace(self, workspace_path: Path) -> bool:
        """Clean up ZMK config workspace after compilation.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            bool: True if cleanup was successful

        Raises:
            ZmkConfigWorkspaceManagerError: If cleanup fails
        """
        try:
            if not workspace_path.exists():
                self.logger.debug("Workspace already cleaned up: %s", workspace_path)
                return True

            self.logger.debug("Cleaning up ZMK config workspace: %s", workspace_path)

            # Remove build artifacts
            build_dir = workspace_path / "build"
            if build_dir.exists():
                import shutil

                shutil.rmtree(build_dir)
                self.logger.debug("Removed build directory: %s", build_dir)

            # Clean west workspace artifacts
            west_dir = workspace_path / ".west"
            if west_dir.exists():
                import shutil

                shutil.rmtree(west_dir)
                self.logger.debug("Removed west directory: %s", west_dir)

            self.logger.debug("ZMK config workspace cleanup completed")
            return True

        except Exception as e:
            msg = f"Failed to cleanup ZMK config workspace: {e}"
            self.logger.error(msg)
            raise ZmkConfigWorkspaceManagerError(msg) from e

    def clone_config_repository(
        self, config: ZmkConfigRepoConfig, workspace_path: Path
    ) -> bool:
        """Clone ZMK config repository.

        Args:
            config: ZMK config repository configuration
            workspace_path: Target workspace directory

        Returns:
            bool: True if clone succeeded

        Raises:
            ZmkConfigWorkspaceManagerError: If cloning fails
        """
        try:
            self.logger.info(
                "Cloning ZMK config repository: %s", config.config_repo_url
            )

            # Use git command to clone repository
            import subprocess

            # Prepare git clone command
            cmd = ["git", "clone"]

            # Add branch/tag if specified
            if config.config_repo_revision and config.config_repo_revision.strip():
                cmd.extend(["--branch", config.config_repo_revision])

            # Add depth limit for faster clones
            cmd.extend(["--depth", "1"])

            # Add repository URL and target directory
            cmd.extend([config.config_repo_url, str(workspace_path)])

            # Execute git clone
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            if result.returncode != 0:
                raise ZmkConfigWorkspaceManagerError(
                    f"Git clone failed: {result.stderr}"
                )

            self.logger.info("Successfully cloned config repository")
            return True

        except subprocess.TimeoutExpired as e:
            msg = f"Git clone timed out after 5 minutes: {e}"
            self.logger.error(msg)
            raise ZmkConfigWorkspaceManagerError(msg) from e
        except Exception as e:
            msg = f"Failed to clone config repository: {e}"
            self.logger.error(msg)
            raise ZmkConfigWorkspaceManagerError(msg) from e

    def initialize_west_workspace(self, workspace_path: Path) -> bool:
        """Initialize west workspace in config repository.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            bool: True if initialization succeeded

        Raises:
            ZmkConfigWorkspaceManagerError: If west initialization fails
        """
        try:
            self.logger.info("Initializing west workspace: %s", workspace_path)

            import subprocess

            # Initialize west workspace
            result = subprocess.run(
                ["west", "init", "-l", str(workspace_path)],
                capture_output=True,
                text=True,
                cwd=workspace_path.parent,
                timeout=120,  # 2 minute timeout
            )

            if result.returncode != 0:
                raise ZmkConfigWorkspaceManagerError(
                    f"West init failed: {result.stderr}"
                )

            # Update west workspace
            result = subprocess.run(
                ["west", "update"],
                capture_output=True,
                text=True,
                cwd=workspace_path,
                timeout=300,  # 5 minute timeout
            )

            if result.returncode != 0:
                raise ZmkConfigWorkspaceManagerError(
                    f"West update failed: {result.stderr}"
                )

            self.logger.info("West workspace initialized successfully")
            return True

        except subprocess.TimeoutExpired as e:
            msg = f"West command timed out: {e}"
            self.logger.error(msg)
            raise ZmkConfigWorkspaceManagerError(msg) from e
        except Exception as e:
            msg = f"Failed to initialize west workspace: {e}"
            self.logger.error(msg)
            raise ZmkConfigWorkspaceManagerError(msg) from e

    def copy_user_configuration(
        self, workspace_path: Path, keymap_file: Path, config_file: Path
    ) -> bool:
        """Copy user configuration files to workspace.

        Args:
            workspace_path: Path to workspace directory
            keymap_file: Source keymap file
            config_file: Source config file

        Returns:
            bool: True if copy succeeded

        Raises:
            ZmkConfigWorkspaceManagerError: If copying fails
        """
        try:
            self.logger.debug("Copying user configuration to workspace")

            config_dir = workspace_path / "config"
            if not config_dir.exists():
                config_dir.mkdir(parents=True)

            # Copy keymap file
            if keymap_file.exists():
                import shutil

                target_keymap = config_dir / keymap_file.name
                shutil.copy2(keymap_file, target_keymap)
                self.logger.debug("Copied keymap: %s -> %s", keymap_file, target_keymap)

            # Copy config file
            if config_file.exists():
                import shutil

                target_config = config_dir / config_file.name
                shutil.copy2(config_file, target_config)
                self.logger.debug("Copied config: %s -> %s", config_file, target_config)

            return True

        except Exception as e:
            msg = f"Failed to copy user configuration: {e}"
            self.logger.error(msg)
            raise ZmkConfigWorkspaceManagerError(msg) from e


def create_zmk_config_workspace_manager() -> ZmkConfigWorkspaceManager:
    """Create ZMK config workspace manager instance.

    Returns:
        ZmkConfigWorkspaceManager: New ZMK config workspace manager
    """
    return ZmkConfigWorkspaceManager()
