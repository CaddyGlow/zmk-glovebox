"""Custom Textual widgets for the TUI application."""

from .compilation_progress_widget import (
    CompilationProgressWidget,
    create_compilation_progress_widget,
)
from .log_viewer import LogViewer
from .progress_widget import ProgressWidget, StandaloneProgressApp
from .settings_panel import SettingsPanel
from .system_info import SystemInfo
from .workspace_progress_widget import (
    WorkspaceProgressWidget,
    create_workspace_progress_widget,
)


__all__ = [
    # Base progress components
    "ProgressWidget",
    "StandaloneProgressApp",
    # Specialized progress widgets
    "WorkspaceProgressWidget",
    "create_workspace_progress_widget",
    "CompilationProgressWidget",
    "create_compilation_progress_widget",
    # Existing widgets
    "LogViewer",
    "SettingsPanel",
    "SystemInfo",
]
