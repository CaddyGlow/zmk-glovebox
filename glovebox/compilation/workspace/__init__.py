"""Workspace management for compilation builds."""

from glovebox.compilation.workspace.cache_manager import (
    CacheManager,
    create_cache_manager,
)
from glovebox.compilation.workspace.west_workspace_manager import (
    WestWorkspaceManager,
    create_west_workspace_manager,
)
from glovebox.compilation.workspace.workspace_manager import (
    WorkspaceManager,
    create_workspace_manager,
)
from glovebox.compilation.workspace.zmk_config_workspace_manager import (
    ZmkConfigWorkspaceManager,
    create_zmk_config_workspace_manager,
)


# ZMK config workspace manager is now imported and available


# CacheManager is now imported and available


__all__: list[str] = [
    # Workspace managers
    "WorkspaceManager",
    "WestWorkspaceManager",
    "ZmkConfigWorkspaceManager",
    "CacheManager",
    # Factory functions
    "create_workspace_manager",
    "create_west_workspace_manager",
    "create_zmk_config_workspace_manager",
    "create_cache_manager",
]
