"""Log viewer widget with real-time updates and scrolling."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import RichLog


class LogViewer(Vertical):
    """Widget for displaying and managing log messages."""

    auto_scroll: reactive[bool] = reactive(True)

    BINDINGS = [
        Binding("j", "scroll_down", "Scroll Down"),
        Binding("k", "scroll_up", "Scroll Up"),
        Binding("g", "scroll_home", "Go to Top"),
        Binding("G", "scroll_end", "Go to Bottom"),
        Binding("space", "page_down", "Page Down"),
        Binding("a", "toggle_auto_scroll", "Toggle Auto-scroll"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the log viewer layout."""
        yield RichLog(
            id="log-display",
            highlight=True,
            markup=True,
            auto_scroll=self.auto_scroll,
            max_lines=1000,
        )

    def on_mount(self) -> None:
        """Initialize the log viewer when mounted."""
        self.log_display = self.query_one("#log-display", RichLog)
        self.add_initial_logs()

    def add_initial_logs(self) -> None:
        """Add some initial log messages."""
        self.log_display.write("Application started")
        self.log_display.write("[green]Log viewer initialized[/green]")
        self.log_display.write("[blue]Press 'a' to toggle auto-scroll[/blue]")
        self.log_display.write(
            "[yellow]Use j/k for scrolling, g/G for top/bottom[/yellow]"
        )

    def add_log(self, message: str) -> None:
        """Add a new log message."""
        self.log_display.write(message)

    def action_scroll_down(self) -> None:
        """Scroll down in the log display."""
        self.log_display.scroll_down()

    def action_scroll_up(self) -> None:
        """Scroll up in the log display."""
        self.log_display.scroll_up()

    def action_scroll_home(self) -> None:
        """Scroll to the top of the log display."""
        self.log_display.scroll_home()

    def action_scroll_end(self) -> None:
        """Scroll to the bottom of the log display."""
        self.log_display.scroll_end()

    def action_page_down(self) -> None:
        """Scroll down by one page."""
        self.log_display.scroll_page_down()

    def action_toggle_auto_scroll(self) -> None:
        """Toggle auto-scroll mode."""
        self.auto_scroll = not self.auto_scroll
        self.log_display.auto_scroll = self.auto_scroll
        status = "enabled" if self.auto_scroll else "disabled"
        self.add_log(f"[cyan]Auto-scroll {status}[/cyan]")

    def watch_auto_scroll(self, auto_scroll: bool) -> None:
        """React to auto_scroll changes."""
        if hasattr(self, "log_display"):
            self.log_display.auto_scroll = auto_scroll
