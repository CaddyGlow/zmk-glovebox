"""Workspace management protocols."""

from pathlib import Path
from typing import Protocol, runtime_checkable

from glovebox.config.compile_methods import (
    GenericDockerCompileConfig,
    WestWorkspaceConfig,
    ZmkConfigRepoConfig,
)


@runtime_checkable
class WorkspaceManagerProtocol(Protocol):
    """Protocol for workspace management."""

    def initialize_workspace(self, config: GenericDockerCompileConfig) -> bool:
        """Initialize workspace for compilation.

        Args:
            config: Compilation configuration

        Returns:
            bool: True if workspace initialization succeeded
        """
        ...

    def cleanup_workspace(self, workspace_path: Path) -> bool:
        """Clean up workspace after compilation.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            bool: True if cleanup succeeded
        """
        ...


@runtime_checkable
class WestWorkspaceManagerProtocol(WorkspaceManagerProtocol, Protocol):
    """Protocol for ZMK west workspace management."""

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
        ...


@runtime_checkable
class ZmkConfigWorkspaceManagerProtocol(WorkspaceManagerProtocol, Protocol):
    """Protocol for ZMK config repository workspace management."""

    def initialize_zmk_config_workspace(
        self,
        config_repo_config: ZmkConfigRepoConfig,
        keymap_file: Path,
        config_file: Path,
    ) -> bool:
        """Initialize ZMK config repository workspace.

        Args:
            config_repo_config: ZMK config repository configuration
            keymap_file: Path to keymap file
            config_file: Path to config file

        Returns:
            bool: True if initialization succeeded
        """
        ...

    def clone_config_repository(self, config: ZmkConfigRepoConfig) -> bool:
        """Clone ZMK config repository.

        Args:
            config: ZMK config repository configuration

        Returns:
            bool: True if clone succeeded
        """
        ...
