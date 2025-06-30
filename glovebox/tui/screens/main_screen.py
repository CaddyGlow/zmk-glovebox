"""Main screen for the Glovebox TUI application."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Footer, Header, Static, TabbedContent, TabPane

from ..services.log_service import LogService
from ..services.system_service import SystemService
from ..widgets.log_viewer import LogViewer
from ..widgets.settings_panel import SettingsPanel
from ..widgets.system_info import SystemInfo


class MainScreen(Screen[None]):
    """Main application screen with tabbed interface."""

    def __init__(self, log_service: LogService, system_service: SystemService):
        """Initialize the main screen with services."""
        super().__init__()
        self.log_service = log_service
        self.system_service = system_service

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        yield Header()

        with Container(id="main-container"), TabbedContent(initial="logs"):
            with TabPane("Logs", id="logs"):
                yield LogViewer(id="log-viewer")

            with TabPane("System", id="system"):
                yield SystemInfo(id="system-info")

            with TabPane("Settings", id="settings"):
                yield SettingsPanel(id="settings-panel")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize screen when mounted."""
        # Connect log service to log viewer
        log_viewer = self.query_one("#log-viewer", LogViewer)
        self.log_service.set_log_callback(log_viewer.add_log)

        # Connect system service to system info widget
        system_info = self.query_one("#system-info", SystemInfo)
        self.system_service.set_metrics_callback(self._handle_system_metrics)

        # Add initial log message
        self.log_service.add_custom_log("Main screen initialized", "INFO")

    def _handle_system_metrics(self, metrics: dict[str, Any]) -> None:
        """Handle system metrics updates."""
        try:
            system_info = self.query_one("#system-info", SystemInfo)

            # Update CPU and memory metrics
            if "cpu" in metrics:
                system_info.cpu_percent = metrics["cpu"].get("percent", 0.0)

            if "memory" in metrics:
                system_info.memory_percent = metrics["memory"].get("percent", 0.0)

        except Exception:
            # Handle errors gracefully
            pass

    def switch_tab(self, tab_name: str) -> None:
        """Switch to the specified tab."""
        tabbed_content = self.query_one(TabbedContent)
        tabbed_content.active = tab_name

        # Log tab switch
        self.log_service.add_custom_log(f"Switched to {tab_name} tab", "DEBUG")
