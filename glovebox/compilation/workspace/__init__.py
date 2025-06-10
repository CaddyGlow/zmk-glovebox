"""Workspace management for compilation builds."""

from glovebox.compilation.workspace.workspace_manager import (
    WorkspaceManager,
    create_workspace_manager,
)


# Additional workspace managers will be added in Phase 3 steps
# from glovebox.compilation.workspace.west_workspace_manager import WestWorkspaceManager
# from glovebox.compilation.workspace.zmk_config_workspace_manager import ZmkConfigWorkspaceManager
# from glovebox.compilation.workspace.cache_manager import CacheManager


def create_west_workspace_manager() -> None:
    """Create west workspace manager.

    Returns:
        WestWorkspaceManager: West workspace manager instance
    """
    # Implementation will be added in Phase 3
    pass


def create_zmk_config_workspace_manager() -> None:
    """Create ZMK config workspace manager.

    Returns:
        ZmkConfigWorkspaceManager: ZMK config workspace manager instance
    """
    # Implementation will be added in Phase 3
    pass


def create_cache_manager() -> None:
    """Create cache manager.

    Returns:
        CacheManager: Cache manager instance
    """
    # Implementation will be added in Phase 3
    pass


__all__: list[str] = [
    # Workspace managers
    "WorkspaceManager",
    # Additional managers (to be added in subsequent steps)
    # "WestWorkspaceManager",
    # "ZmkConfigWorkspaceManager",
    # "CacheManager",
    # Factory functions
    "create_workspace_manager",
    "create_west_workspace_manager",
    "create_zmk_config_workspace_manager",
    "create_cache_manager",
]
