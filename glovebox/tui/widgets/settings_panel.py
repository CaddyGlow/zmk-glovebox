"""Settings panel widget with interactive controls."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Grid, Horizontal, Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Label, Select, Static, Switch


class SettingsPanel(Widget):
    """Widget for application settings and configuration."""

    auto_scroll_enabled: reactive[bool] = reactive(True)
    log_level: reactive[str] = reactive("INFO")
    refresh_rate: reactive[int] = reactive(4)

    BINDINGS = [
        Binding("a", "toggle_auto_scroll", "Toggle Auto-scroll"),
        Binding("l", "cycle_log_level", "Cycle Log Level"),
        Binding("r", "adjust_refresh_rate", "Adjust Refresh Rate"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the settings panel layout."""
        # # with Vertical(id="settings-container"):
        # yield Static("[bold cyan]Application Settings[/bold cyan]")
        # yield Static("")  # spacer
        #
        # # Auto-scroll setting
        # with Horizontal():

        # Log level setting
        with Grid(id="settings-grid"):
            yield Label("[bold cyan]Application Settings[/bold cyan]", id="title")
            yield Static("Auto-scroll logs:")
            yield Switch(value=self.auto_scroll_enabled, id="auto-scroll-switch")
            yield Static("Log level:")
            yield Select(
                options=[
                    ("DEBUG", "DEBUG"),
                    ("INFO", "INFO"),
                    ("WARNING", "WARNING"),
                    ("ERROR", "ERROR"),
                ],
                value="INFO",
                id="log-level-select",
            )
            yield Static(
                f"Refresh rate: {self.refresh_rate} FPS", id="refresh-rate-label"
            )
            yield Vertical(
                Button("Decrease", id="refresh-decrease"),
                Button("Increase", id="refresh-increase"),
            )

        yield Static("")  # spacer
        yield Static("[bold yellow]Keyboard Controls:[/bold yellow]")
        yield Static("• Press 'a' to toggle auto-scroll")
        yield Static("• Press 'l' to cycle log level")
        yield Static("• Press 'r' to adjust refresh rate")
        yield Static("• Use 1/2/3 to switch tabs")
        yield Static("• Press 'q' to quit")

    def on_mount(self) -> None:
        """Initialize settings when mounted."""
        self.auto_scroll_switch = self.query_one("#auto-scroll-switch", Switch)
        self.log_level_select = self.query_one("#log-level-select", Select)
        self.refresh_rate_label = self.query_one("#refresh-rate-label", Static)

        # Update initial values
        self.update_refresh_rate_display()

    def on_switch_changed(self, event: Switch.Changed) -> None:
        """Handle switch changes."""
        if event.switch.id == "auto-scroll-switch":
            self.auto_scroll_enabled = event.value
            self.notify_setting_changed("auto_scroll", event.value)

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle select changes."""
        if event.select.id == "log-level-select":
            self.log_level = str(event.value)
            self.notify_setting_changed("log_level", event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "refresh-decrease":
            self.refresh_rate = max(1, self.refresh_rate - 1)
            self.update_refresh_rate_display()
            self.notify_setting_changed("refresh_rate", self.refresh_rate)
        elif event.button.id == "refresh-increase":
            self.refresh_rate = min(10, self.refresh_rate + 1)
            self.update_refresh_rate_display()
            self.notify_setting_changed("refresh_rate", self.refresh_rate)

    def update_refresh_rate_display(self) -> None:
        """Update the refresh rate display."""
        if hasattr(self, "refresh_rate_label"):
            self.refresh_rate_label.update(f"Refresh rate: {self.refresh_rate} FPS")

    def notify_setting_changed(self, setting: str, value) -> None:
        """Notify about setting changes."""
        # In a real app, this would update the actual application settings
        # For now, we'll just show a notification
        self.app.notify(f"Setting '{setting}' changed to: {value}")

    def action_toggle_auto_scroll(self) -> None:
        """Toggle auto-scroll setting."""
        self.auto_scroll_enabled = not self.auto_scroll_enabled
        self.auto_scroll_switch.value = self.auto_scroll_enabled
        self.notify_setting_changed("auto_scroll", self.auto_scroll_enabled)

    def action_cycle_log_level(self) -> None:
        """Cycle through log levels."""
        levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        current_index = levels.index(self.log_level)
        next_index = (current_index + 1) % len(levels)
        self.log_level = levels[next_index]
        self.log_level_select.value = self.log_level
        self.notify_setting_changed("log_level", self.log_level)

    def action_adjust_refresh_rate(self) -> None:
        """Adjust refresh rate (cycle through common values)."""
        rates = [1, 2, 4, 8, 10]
        try:
            current_index = rates.index(self.refresh_rate)
            next_index = (current_index + 1) % len(rates)
        except ValueError:
            next_index = 0

        self.refresh_rate = rates[next_index]
        self.update_refresh_rate_display()
        self.notify_setting_changed("refresh_rate", self.refresh_rate)
