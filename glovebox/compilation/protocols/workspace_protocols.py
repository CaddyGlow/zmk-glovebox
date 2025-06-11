"""Workspace management protocols."""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from glovebox.config.compile_methods import (
    WestWorkspaceConfig,
    ZmkConfigRepoConfig,
)


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile


@runtime_checkable
class WorkspaceManagerProtocol(Protocol):
    """Protocol for workspace management."""

    def initialize_workspace(self, **context: Any) -> bool:
        """Initialize workspace for compilation.

        Args:
            **context: Context for workspace initialization

        Returns:
            bool: True if workspace initialization succeeded
        """
        ...

    def validate_workspace(self, workspace_path: Path) -> bool:
        """Validate workspace is ready for compilation.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            bool: True if workspace is valid
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

    def initialize_dynamic_workspace(
        self,
        workspace_path: Path,
        keymap_file: Path,
        config_file: Path,
        keyboard_profile: "KeyboardProfile",
        shield_name: str | None = None,
        board_name: str = "nice_nano_v2",
    ) -> bool:
        """Initialize dynamic ZMK config workspace without external repository.

        Args:
            workspace_path: Path to workspace directory
            keymap_file: Source keymap file
            config_file: Source config file
            keyboard_profile: Keyboard profile for configuration
            shield_name: Shield name (defaults to keyboard name)
            board_name: Board name for builds

        Returns:
            bool: True if workspace initialized successfully
        """
        ...
