"""Main Textual application for Glovebox TUI."""

from typing import cast

from textual.app import App
from textual.binding import Binding

from .screens.main_screen import MainScreen
from .services.log_service import LogService
from .services.system_service import SystemService


class GloveboxTUIApp(App[None]):
    """Main Textual application class."""

    TITLE = "Glovebox TUI"
    CSS_PATH = "styles/main.tcss"  # Disabled - causes tabs content to not display

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("1", "switch_tab('logs')", "Logs", priority=True),
        Binding("2", "switch_tab('system')", "System", priority=True),
        Binding("3", "switch_tab('settings')", "Settings", priority=True),
    ]

    def __init__(self):
        """Initialize the application."""
        super().__init__()
        self.log_service = LogService()
        self.system_service = SystemService()

    def on_mount(self) -> None:
        """Initialize the application when mounted."""
        main_screen = MainScreen(self.log_service, self.system_service)
        self.push_screen(main_screen)

    async def on_ready(self) -> None:
        """Start background services when app is ready."""
        await self.log_service.start()
        await self.system_service.start()

    async def on_unmount(self) -> None:
        """Clean up when application is unmounted."""
        await self.log_service.stop()
        await self.system_service.stop()

    def action_switch_tab(self, tab_name: str) -> None:
        """Switch to the specified tab."""
        # if hasattr(self.screen, "switch_tab"):
        #     cast(MainScreen, self.screen).switch_tab(tab_name)
        if isinstance(self.screen, MainScreen):
            self.screen.switch_tab(tab_name)
