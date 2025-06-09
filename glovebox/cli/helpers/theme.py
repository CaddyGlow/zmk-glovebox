"""Unified theme system for consistent Rich styling across CLI commands."""

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.style import Style
from rich.table import Table
from rich.text import Text
from rich.theme import Theme


# Color scheme constants
class Colors:
    """Standardized color palette for CLI output."""

    # Status colors
    SUCCESS = "bold green"
    ERROR = "bold red"
    WARNING = "bold yellow"
    INFO = "bold blue"

    # UI element colors
    PRIMARY = "cyan"
    SECONDARY = "blue"
    ACCENT = "magenta"
    MUTED = "dim"

    # Semantic colors
    AVAILABLE = "green"
    UNAVAILABLE = "red"
    UNKNOWN = "yellow"
    BUSY = "yellow"

    # Text colors
    HEADER = "bold cyan"
    SUBHEADER = "bold blue"
    HIGHLIGHT = "bold white"
    NORMAL = "white"


# Icon/emoji standards
class Icons:
    """Standardized icons for different message types."""

    # Status indicators
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"

    # Action indicators
    CHECKMARK = "✓"
    CROSS = "✗"
    BULLET = "•"
    ARROW = "→"

    # Category icons
    DEVICE = "🔌"
    KEYBOARD = "⌨️"
    FIRMWARE = "🔧"
    LAYOUT = "📐"
    DOCKER = "🐳"
    SYSTEM = "🖥️"
    CONFIG = "⚙️"
    USB = "🔌"
    FLASH = "⚡"
    BUILD = "🔨"

    # Process indicators
    LOADING = "🔄"
    COMPLETED = "✨"
    RUNNING = "▶️"
    STOPPED = "⏹️"


# Rich theme configuration
GLOVEBOX_THEME = Theme(
    {
        "success": Colors.SUCCESS,
        "error": Colors.ERROR,
        "warning": Colors.WARNING,
        "info": Colors.INFO,
        "primary": Colors.PRIMARY,
        "secondary": Colors.SECONDARY,
        "accent": Colors.ACCENT,
        "muted": Colors.MUTED,
        "header": Colors.HEADER,
        "subheader": Colors.SUBHEADER,
        "highlight": Colors.HIGHLIGHT,
        "available": Colors.AVAILABLE,
        "unavailable": Colors.UNAVAILABLE,
        "unknown": Colors.UNKNOWN,
        "busy": Colors.BUSY,
    }
)


class ThemedConsole:
    """Console wrapper with Glovebox theme applied."""

    def __init__(self) -> None:
        """Initialize themed console."""
        self.console = Console(theme=GLOVEBOX_THEME)

    def print_success(self, message: str) -> None:
        """Print success message with icon and styling."""
        self.console.print(f"{Icons.SUCCESS} {message}", style="success")

    def print_error(self, message: str) -> None:
        """Print error message with icon and styling."""
        self.console.print(f"{Icons.ERROR} {message}", style="error")

    def print_warning(self, message: str) -> None:
        """Print warning message with icon and styling."""
        self.console.print(f"{Icons.WARNING} {message}", style="warning")

    def print_info(self, message: str) -> None:
        """Print info message with icon and styling."""
        self.console.print(f"{Icons.INFO} {message}", style="info")

    def print_list_item(self, message: str, indent: int = 1) -> None:
        """Print list item with bullet and styling."""
        spacing = "  " * indent
        self.console.print(f"{spacing}{Icons.BULLET} {message}", style="primary")


class TableStyles:
    """Predefined table styling templates."""

    @staticmethod
    def create_basic_table(title: str = "", icon: str = "") -> Table:
        """Create a basic styled table.

        Args:
            title: Table title
            icon: Icon to include in title

        Returns:
            Configured Table instance
        """
        full_title = f"{icon} {title}" if icon and title else title
        return Table(
            title=full_title,
            show_header=True,
            header_style=Colors.HEADER,
            border_style=Colors.SECONDARY,
        )

    @staticmethod
    def create_device_table() -> Table:
        """Create table for device listings."""
        table = TableStyles.create_basic_table("USB Devices", Icons.DEVICE)
        table.add_column("Device", style=Colors.PRIMARY, no_wrap=True)
        table.add_column("Serial", style=Colors.ACCENT)
        table.add_column("Path", style=Colors.MUTED)
        table.add_column("Status", style="bold")
        return table

    @staticmethod
    def create_status_table() -> Table:
        """Create table for status information."""
        table = TableStyles.create_basic_table("System Status", Icons.SYSTEM)
        table.add_column("Component", style=Colors.PRIMARY, no_wrap=True)
        table.add_column("Status", style="bold")
        table.add_column("Details", style=Colors.MUTED)
        return table

    @staticmethod
    def create_config_table() -> Table:
        """Create table for configuration display."""
        table = TableStyles.create_basic_table("Configuration", Icons.CONFIG)
        table.add_column("Setting", style=Colors.PRIMARY, no_wrap=True)
        table.add_column("Value", style=Colors.NORMAL)
        return table

    @staticmethod
    def create_keyboard_table() -> Table:
        """Create table for keyboard listings."""
        table = TableStyles.create_basic_table("Keyboards", Icons.KEYBOARD)
        table.add_column("Keyboard", style=Colors.PRIMARY, no_wrap=True)
        table.add_column("Firmwares", style=Colors.ACCENT)
        table.add_column("Description", style=Colors.MUTED)
        return table


class PanelStyles:
    """Predefined panel styling templates."""

    @staticmethod
    def create_header_panel(title: str, subtitle: str = "", icon: str = "") -> Panel:
        """Create styled header panel.

        Args:
            title: Main title
            subtitle: Optional subtitle
            icon: Icon to include

        Returns:
            Configured Panel instance
        """
        panel_title = f"{icon} {title}" if icon else title
        content = (
            Text(subtitle, style=Colors.SUBHEADER)
            if subtitle
            else Text(title, style=Colors.HEADER)
        )

        return Panel(
            content,
            title=panel_title,
            border_style=Colors.SECONDARY,
            padding=(0, 1),
        )

    @staticmethod
    def create_info_panel(content: str, title: str = "Information") -> Panel:
        """Create styled information panel."""
        return Panel(
            content,
            title=f"{Icons.INFO} {title}",
            border_style=Colors.INFO,
            padding=(0, 1),
        )

    @staticmethod
    def create_error_panel(content: str, title: str = "Error") -> Panel:
        """Create styled error panel."""
        return Panel(
            Text(content, style=Colors.ERROR),
            title=f"{Icons.ERROR} {title}",
            border_style=Colors.ERROR,
            padding=(0, 1),
        )

    @staticmethod
    def create_success_panel(content: str, title: str = "Success") -> Panel:
        """Create styled success panel."""
        return Panel(
            Text(content, style=Colors.SUCCESS),
            title=f"{Icons.SUCCESS} {title}",
            border_style=Colors.SUCCESS,
            padding=(0, 1),
        )


class StatusIndicators:
    """Standardized status indicator formatting."""

    @staticmethod
    def format_availability_status(available: bool) -> str:
        """Format availability status with icon and color."""
        if available:
            return f"{Icons.SUCCESS} Available"
        else:
            return f"{Icons.ERROR} Unavailable"

    @staticmethod
    def format_device_status(status: str) -> str:
        """Format device status with appropriate icon and styling."""
        status_map = {
            "available": f"{Icons.SUCCESS} Available",
            "busy": f"{Icons.LOADING} Busy",
            "error": f"{Icons.ERROR} Error",
            "unknown": f"{Icons.WARNING} Unknown",
        }
        return status_map.get(status.lower(), f"{Icons.WARNING} {status}")

    @staticmethod
    def format_service_status(status: str) -> str:
        """Format service status with appropriate icon."""
        status_map = {
            "running": f"{Icons.RUNNING} Running",
            "stopped": f"{Icons.STOPPED} Stopped",
            "error": f"{Icons.ERROR} Error",
            "unknown": f"{Icons.WARNING} Unknown",
        }
        return status_map.get(status.lower(), f"{Icons.WARNING} {status}")

    @staticmethod
    def format_boolean_status(
        value: bool, true_label: str = "Yes", false_label: str = "No"
    ) -> str:
        """Format boolean as status indicator."""
        if value:
            return f"{Icons.SUCCESS} {true_label}"
        else:
            return f"{Icons.ERROR} {false_label}"


# Utility functions for quick access
def get_themed_console() -> ThemedConsole:
    """Get a themed console instance."""
    return ThemedConsole()


def create_status_indicator(status: str, status_type: str = "general") -> str:
    """Create status indicator with appropriate formatting.

    Args:
        status: Status value
        status_type: Type of status (device, service, availability, boolean)

    Returns:
        Formatted status string
    """
    if status_type == "device":
        return StatusIndicators.format_device_status(status)
    elif status_type == "service":
        return StatusIndicators.format_service_status(status)
    elif status_type == "availability":
        return StatusIndicators.format_availability_status(
            status.lower() in ("true", "available", "yes")
        )
    elif status_type == "boolean":
        return StatusIndicators.format_boolean_status(
            status.lower() in ("true", "yes", "1")
        )
    else:
        return f"{Icons.INFO} {status}"


def apply_glovebox_theme(console: Console) -> Console:
    """Apply Glovebox theme to existing console.

    Args:
        console: Console instance to theme

    Returns:
        Console with theme applied
    """
    # Create a new console with the theme instead of modifying internal attributes
    return Console(theme=GLOVEBOX_THEME)
