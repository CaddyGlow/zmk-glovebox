"""Unified theme system for consistent Rich styling across CLI commands."""

# Color scheme constants
from enum import Enum
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme


if TYPE_CHECKING:
    import typer


class IconMode(str, Enum):
    """Icon display modes for CLI output."""

    EMOJI = "emoji"
    NERDFONT = "nerdfont"
    TEXT = "text"


class Colors:
    """Standardized color palette for CLI output."""

    # Core status colors (MANDATORY for all status messages)
    SUCCESS = "bold bright_green"  # Maximum visibility for success messages
    ERROR = "bold red"
    WARNING = "bold yellow"
    INFO = "bold blue"

    # Operational state colors
    RUNNING = "bold cyan"
    STOPPED = "dim red"
    PENDING = "yellow"
    COMPLETED = "green"
    FAILED = "bold red"

    # Availability states
    AVAILABLE = "green"
    UNAVAILABLE = "red"
    BUSY = "yellow"
    UNKNOWN = "dim yellow"

    # Priority levels
    CRITICAL = "bold red on yellow"
    HIGH = "bold red"
    MEDIUM = "yellow"
    LOW = "bright_black"  # Better visibility than "dim white"

    # Data states
    VALID = "green"
    INVALID = "red"
    MODIFIED = "yellow"
    UNCHANGED = "bright_black"  # Better visibility than "dim white"
    NEW = "bright_green"
    DELETED = "red"

    # Progress and loading
    PROGRESS_BAR = "bright_blue"
    PROGRESS_COMPLETE = "green"
    PROGRESS_PARTIAL = "yellow"
    PROGRESS_FAILED = "red"
    LOADING_SPINNER = "cyan"
    LOADING_TEXT = "dim cyan"

    # UI element colors
    PRIMARY = "cyan"
    SECONDARY = "blue"
    ACCENT = "magenta"
    MUTED = "bright_black"  # Better visibility than "dim" in most terminals
    SUBTLE = "white"  # Alternative for very dark terminals

    # Text hierarchy colors
    HEADER = "bold cyan"
    SUBHEADER = "bold blue"
    HIGHLIGHT = "bold white"
    NORMAL = "white"
    FIELD_NAME = "bold"
    FIELD_VALUE = "white"

    # Contextual colors
    BUILD = "blue"
    COMPILE = "cyan"
    FLASH = "magenta"
    CACHE = "green"
    NETWORK = "blue"
    FILE = "white"
    DIRECTORY = "cyan"


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

    # Additional icons for comprehensive coverage
    UPLOAD = "📤"
    DOWNLOAD = "📥"
    DOCUMENT = "📝"
    LINK = "🔗"
    CALENDAR = "📅"
    USER = "👤"
    TAG = "🏷️"
    EYE = "👁️"
    SEARCH = "🔍"
    FAMILY = "👨‍👩‍👧‍👦"
    STATS = "📊"
    TREE = "🌳"
    CROWN = "👑"
    SCROLL = "📜"
    STAR = "⭐"
    TRASH = "🗑️"
    QUESTION = "❓"
    GLOBE = "🌐"
    SAVE = "💾"
    CLIPBOARD = "📋"
    APPLE = "🍎"
    WINDOWS = "🪟"
    LINUX = "🐧"
    FOLDER = "📁"
    MAILBOX = "📭"
    SHIELD = "🛡️"
    DIAMOND = "🔸"
    LOCK = "🔒"
    KEYSTORE = "🔐"

    FACTORY = "🏭"
    CLONE = "📋"

    # Nerd Font icons for terminal environments with font support
    _NERDFONT_ICONS = {
        # Status indicators
        "SUCCESS": "\uf058",  # nf-fa-check_circle
        "ERROR": "\uf057",  # nf-fa-times_circle
        "WARNING": "\uf071",  # nf-fa-warning
        "INFO": "\uf05a",  # nf-fa-info_circle
        # Action indicators
        "CHECKMARK": "\uf00c",  # nf-fa-check
        "CROSS": "\uf00d",  # nf-fa-times
        "BULLET": "\uf111",  # nf-fa-circle
        "ARROW": "\uf061",  # nf-fa-arrow_right
        # Category icons
        "DEVICE": "\uf1e6",  # nf-fa-plug
        "KEYBOARD": "\uf11c",  # nf-fa-keyboard_o
        "FIRMWARE": "\uf2db",  # nf-fa-microchip
        "LAYOUT": "\uf00a",  # nf-fa-th
        "DOCKER": "\uf395",  # nf-fa-docker
        "SYSTEM": "\uf108",  # nf-fa-desktop
        "CONFIG": "\uf013",  # nf-fa-cog
        "USB": "\uf287",  # nf-fa-usb
        "FLASH": "\uf0e7",  # nf-fa-bolt
        "BUILD": "\uf6e3",  # nf-fa-hammer
        # Process indicators
        "LOADING": "\uf021",  # nf-fa-refresh
        "COMPLETED": "\uf14a",  # nf-fa-check_square
        "RUNNING": "\uf04b",  # nf-fa-play
        "STOPPED": "\uf04d",  # nf-fa-stop
        # Additional icons
        "UPLOAD": "\uf093",  # nf-fa-upload
        "DOWNLOAD": "\uf019",  # nf-fa-download
        "DOCUMENT": "\uf0f6",  # nf-fa-file_text_o
        "LINK": "\uf0c1",  # nf-fa-link
        "CALENDAR": "\uf073",  # nf-fa-calendar
        "USER": "\uf007",  # nf-fa-user
        "TAG": "\uf02b",  # nf-fa-tag
        "EYE": "\uf06e",  # nf-fa-eye
        "SEARCH": "\uf002",  # nf-fa-search
        "FAMILY": "\uf0c0",  # nf-fa-users
        "STATS": "\uf080",  # nf-fa-bar_chart
        "TREE": "\uf1bb",  # nf-fa-tree
        "CROWN": "\uf521",  # nf-fa-crown
        "SCROLL": "\uf70e",  # nf-fa-scroll
        "STAR": "\uf005",  # nf-fa-star
        "TRASH": "\uf1f8",  # nf-fa-trash
        "QUESTION": "\uf059",  # nf-fa-question_circle
        "GLOBE": "\uf0ac",  # nf-fa-globe
        "SAVE": "\uf0c7",  # nf-fa-save
        "CLIPBOARD": "\uf328",  # nf-fa-clipboard
        "APPLE": "\uf179",  # nf-fa-apple
        "WINDOWS": "\uf17a",  # nf-fa-windows
        "LINUX": "\uf17c",  # nf-fa-linux
        "FOLDER": "\uf07b",  # nf-fa-folder
        "MAILBOX": "\uf01c",  # nf-fa-inbox
        "SHIELD": "\uf132",  # nf-fa-shield
        "DIAMOND": "\uf219",  # nf-fa-diamond
        "LOCK": "\uf023",  # nf-fa-lock
        "KEYSTORE": "\uf084",  # nf-fa-key
        "FACTORY": "\uf275",  # nf-fa-industry
        "CLONE": "\uf24d",  # nf-fa-clone
    }

    # Professional ASCII/Unicode symbols (DEFAULT mode)
    _TEXT_FALLBACKS = {
        # Core status indicators (keep Unicode symbols for clarity)
        "SUCCESS": "✓",  # Check mark - clear success indicator
        "ERROR": "✗",  # X mark - clear error indicator
        "WARNING": "⚠",  # Warning triangle - important for visibility
        "INFO": "ℹ",  # Info symbol - standard information indicator
        # Action indicators (keep meaningful symbols)
        "CHECKMARK": "✓",  # Check mark for completion
        "CROSS": "✗",  # X mark for cancellation/failure
        "BULLET": "•",  # Bullet point for lists
        "ARROW": "→",  # Right arrow for flow/direction
        # Process flow indicators (professional ASCII/Unicode)
        "LOADING": "⋯",  # Horizontal ellipsis for loading
        "COMPLETED": "✓",  # Completed same as success
        "RUNNING": "▶",  # Play symbol for active processes
        "STOPPED": "■",  # Stop symbol for halted processes
        "PROCESSING": "→",  # Arrow for processing
        "EXPORTING": "↑",  # Up arrow for exports
        "IMPORTING": "↓",  # Down arrow for imports
        "CREATING": "+",  # Plus for creation
        "UPDATING": "↻",  # Refresh symbol for updates
        "BUILDING": "▶",  # Building same as running
        # Category indicators (minimal but recognizable)
        "DEVICE": "◦",  # Small circle for devices
        "KEYBOARD": "⌨",  # Keyboard symbol (if supported)
        "FIRMWARE": "◆",  # Diamond for firmware
        "LAYOUT": "▣",  # Square with pattern for layouts
        "DOCKER": "◈",  # Diamond pattern for containers
        "SYSTEM": "●",  # Filled circle for system
        "CONFIG": "⚙",  # Gear for configuration
        "USB": "◦",  # Circle for USB devices
        "FLASH": "⚡",  # Lightning for flash operations
        "BUILD": "▣",  # Square for build operations
        # Data and file operations
        "UPLOAD": "↑",  # Up arrow for uploads
        "DOWNLOAD": "↓",  # Down arrow for downloads
        "DOCUMENT": "▤",  # Document symbol
        "LINK": "∞",  # Infinity for links/connections
        "CALENDAR": "▦",  # Calendar representation
        "USER": "◉",  # Filled circle with dot for users
        "TAG": "▢",  # Empty square for tags
        "EYE": "◎",  # Circle with dot for viewing
        "SEARCH": "◯",  # Empty circle for search
        "FAMILY": "◈",  # Diamond for groups/families
        "STATS": "▬",  # Bar for statistics
        "TREE": "┬",  # Tree branch character
        "CROWN": "◆",  # Diamond for premium/important
        "SCROLL": "▤",  # Document scroll
        "STAR": "★",  # Star for favorites
        "TRASH": "◌",  # Empty circle for deletion
        "QUESTION": "?",  # Question mark
        "GLOBE": "◯",  # Circle for network/web
        "SAVE": "▫",  # Small square for save
        "CLIPBOARD": "▤",  # Rectangle for clipboard
        "APPLE": "●",  # Circle for Apple platform
        "WINDOWS": "▣",  # Square for Windows platform
        "LINUX": "◆",  # Diamond for Linux platform
        "FOLDER": "▢",  # Empty square for folders
        "MAILBOX": "▫",  # Small square for empty state
        "SHIELD": "◊",  # Diamond for security
        "DIAMOND": "◆",  # Diamond shape
        "LOCK": "▫",  # Small square for security
        "KEYSTORE": "◈",  # Diamond pattern for keystore
        "FACTORY": "▣",  # Square pattern for factory items
        "CLONE": "◈",  # Diamond pattern for clone operations
        # Progress and status visualization
        "PROGRESS_FULL": "█",  # Full block for progress bars
        "PROGRESS_PARTIAL": "▌",  # Half block for progress bars
        "PROGRESS_EMPTY": "░",  # Light shade for empty progress
        "PROGRESS_QUARTER": "▎",  # Quarter block
        "PROGRESS_HALF": "▌",  # Half block
        "PROGRESS_THREE_QUARTER": "▊",  # Three quarter block
    }

    @classmethod
    def get_icon(cls, icon_name: str, icon_mode: IconMode | str = IconMode.TEXT) -> str:
        """Get icon based on the specified mode.

        Args:
            icon_name: Name of the icon (e.g., "SUCCESS", "ERROR")
            icon_mode: Icon mode - IconMode enum or string

        Returns:
            The appropriate icon based on mode
        """
        # Convert string to enum for backward compatibility
        if isinstance(icon_mode, str):
            icon_mode = IconMode(icon_mode)

        if icon_mode == IconMode.NERDFONT:
            return cls._NERDFONT_ICONS.get(icon_name, "")
        elif icon_mode == IconMode.EMOJI:
            return getattr(cls, icon_name, "")
        else:  # text mode
            return cls._TEXT_FALLBACKS.get(icon_name, f"[{icon_name}]")

    @classmethod
    def format_with_icon(
        cls, icon_name: str, text: str, icon_mode: IconMode | str = IconMode.TEXT
    ) -> str:
        """Format text with icon, handling empty icons gracefully.

        Args:
            icon_name: Name of the icon
            text: Text to format
            icon_mode: Icon mode - IconMode enum or string

        Returns:
            Formatted string with proper spacing
        """
        # Convert string to enum for backward compatibility
        if isinstance(icon_mode, str):
            icon_mode = IconMode(icon_mode)

        icon = cls.get_icon(icon_name, icon_mode)
        if icon:
            return f"{icon} {text}"
        else:
            return text

    # Legacy methods for backward compatibility
    @classmethod
    def get_icon_legacy(cls, icon_name: str, use_emoji: bool = True) -> str:
        """Legacy method for backward compatibility.

        Args:
            icon_name: Name of the icon
            use_emoji: Whether to use emoji or text fallback

        Returns:
            The icon based on legacy boolean preference
        """
        icon_mode = "emoji" if use_emoji else "text"
        return cls.get_icon(icon_name, icon_mode)

    @classmethod
    def format_with_icon_legacy(
        cls, icon_name: str, text: str, use_emoji: bool = True
    ) -> str:
        """Legacy method for backward compatibility.

        Args:
            icon_name: Name of the icon
            text: Text to format
            use_emoji: Whether to use emoji or text fallback

        Returns:
            Formatted string with proper spacing
        """
        icon_mode = "emoji" if use_emoji else "text"
        return cls.format_with_icon(icon_name, text, icon_mode)


# Rich theme configuration
GLOVEBOX_THEME = Theme(
    {
        # Core status colors
        "success": Colors.SUCCESS,
        "error": Colors.ERROR,
        "warning": Colors.WARNING,
        "info": Colors.INFO,
        # Operational states
        "running": Colors.RUNNING,
        "stopped": Colors.STOPPED,
        "pending": Colors.PENDING,
        "completed": Colors.COMPLETED,
        "failed": Colors.FAILED,
        # Availability states
        "available": Colors.AVAILABLE,
        "unavailable": Colors.UNAVAILABLE,
        "busy": Colors.BUSY,
        "unknown": Colors.UNKNOWN,
        # Priority levels
        "critical": Colors.CRITICAL,
        "high": Colors.HIGH,
        "medium": Colors.MEDIUM,
        "low": Colors.LOW,
        # Data states
        "valid": Colors.VALID,
        "invalid": Colors.INVALID,
        "modified": Colors.MODIFIED,
        "unchanged": Colors.UNCHANGED,
        "new": Colors.NEW,
        "deleted": Colors.DELETED,
        # Progress colors
        "progress_bar": Colors.PROGRESS_BAR,
        "progress_complete": Colors.PROGRESS_COMPLETE,
        "progress_partial": Colors.PROGRESS_PARTIAL,
        "progress_failed": Colors.PROGRESS_FAILED,
        "loading_spinner": Colors.LOADING_SPINNER,
        "loading_text": Colors.LOADING_TEXT,
        # UI elements
        "primary": Colors.PRIMARY,
        "secondary": Colors.SECONDARY,
        "accent": Colors.ACCENT,
        "muted": Colors.MUTED,
        # Text hierarchy
        "header": Colors.HEADER,
        "subheader": Colors.SUBHEADER,
        "highlight": Colors.HIGHLIGHT,
        "field_name": Colors.FIELD_NAME,
        "field_value": Colors.FIELD_VALUE,
        # Contextual colors
        "build": Colors.BUILD,
        "compile": Colors.COMPILE,
        "flash": Colors.FLASH,
        "cache": Colors.CACHE,
        "network": Colors.NETWORK,
        "file": Colors.FILE,
        "directory": Colors.DIRECTORY,
    }
)


class ThemedConsole:
    """Console wrapper with Glovebox theme applied."""

    def __init__(self, icon_mode: IconMode | str = IconMode.TEXT) -> None:
        """Initialize themed console.

        Args:
            icon_mode: Icon mode - IconMode enum or string
        """
        self.console = Console(theme=GLOVEBOX_THEME)
        # Convert string to enum for backward compatibility
        if isinstance(icon_mode, str):
            icon_mode = IconMode(icon_mode)
        self.icon_mode = icon_mode

    def print_success(self, message: str) -> None:
        """Print success message with icon and styling."""
        icon = Icons.get_icon("SUCCESS", self.icon_mode)
        self.console.print(f"{icon} {message}", style="success")

    def print_error(self, message: str) -> None:
        """Print error message with icon and styling."""
        icon = Icons.get_icon("ERROR", self.icon_mode)
        self.console.print(f"{icon} {message}", style="error")

    def print_warning(self, message: str) -> None:
        """Print warning message with icon and styling."""
        icon = Icons.get_icon("WARNING", self.icon_mode)
        self.console.print(f"{icon} {message}", style="warning")

    def print_info(self, message: str) -> None:
        """Print info message with icon and styling."""
        icon = Icons.get_icon("INFO", self.icon_mode)
        self.console.print(f"{icon} {message}", style="info")

    def print_list_item(self, message: str, indent: int = 1) -> None:
        """Print list item with bullet and styling."""
        spacing = "  " * indent
        bullet = Icons.get_icon("BULLET", self.icon_mode)
        self.console.print(f"{spacing}{bullet} {message}", style="primary")


class TableStyles:
    """Predefined table styling templates."""

    @staticmethod
    def create_basic_table(
        title: str = "",
        icon: str = "",
        icon_mode: IconMode | str | None = None,
        ctx: "typer.Context | None" = None,
    ) -> Table:
        """Create a basic styled table.

        Args:
            title: Table title
            icon: Icon to include in title
            icon_mode: Icon mode - IconMode enum or string. If None, will auto-detect from context.
            ctx: Typer context for auto-detecting icon mode from user config

        Returns:
            Configured Table instance
        """
        # Auto-detect icon mode from context if not provided
        if icon_mode is None and ctx is not None:
            icon_mode = get_icon_mode_from_context(ctx)

        # Fallback to default if still None
        if icon_mode is None:
            icon_mode = IconMode.TEXT

        # Convert string to enum for backward compatibility
        if isinstance(icon_mode, str):
            icon_mode = IconMode(icon_mode)

        if icon and title:
            # Get the appropriate icon based on mode
            display_icon = (
                Icons.get_icon(icon.upper(), icon_mode)
                if hasattr(Icons, icon.upper())
                else icon
            )
            full_title = f"{display_icon} {title}"
        else:
            full_title = title
        return Table(
            title=full_title,
            show_header=True,
            header_style=Colors.HEADER,
            border_style=Colors.SECONDARY,
        )

    @staticmethod
    def create_device_table(
        icon_mode: IconMode | str | None = None, ctx: "typer.Context | None" = None
    ) -> Table:
        """Create table for device listings."""
        table = TableStyles.create_basic_table("USB Devices", "DEVICE", icon_mode, ctx)
        table.add_column("Device", style=Colors.PRIMARY, no_wrap=True)
        table.add_column("Serial", style=Colors.ACCENT)
        table.add_column("Path", style=Colors.MUTED)
        table.add_column("Status", style="bold")
        return table

    @staticmethod
    def create_status_table(
        icon_mode: IconMode | str | None = None, ctx: "typer.Context | None" = None
    ) -> Table:
        """Create table for status information."""
        table = TableStyles.create_basic_table(
            "System Status", "SYSTEM", icon_mode, ctx
        )
        table.add_column("Component", style=Colors.PRIMARY, no_wrap=True)
        table.add_column("Status", style="bold")
        table.add_column("Details", style=Colors.MUTED)
        return table

    @staticmethod
    def create_config_table(
        icon_mode: IconMode | str | None = None, ctx: "typer.Context | None" = None
    ) -> Table:
        """Create table for configuration display."""
        table = TableStyles.create_basic_table(
            "Configuration", "CONFIG", icon_mode, ctx
        )
        table.add_column("Setting", style=Colors.PRIMARY, no_wrap=True)
        table.add_column("Value", style=Colors.NORMAL)
        return table

    @staticmethod
    def create_keyboard_table(
        icon_mode: IconMode | str | None = None, ctx: "typer.Context | None" = None
    ) -> Table:
        """Create table for keyboard listings."""
        table = TableStyles.create_basic_table("Keyboards", "KEYBOARD", icon_mode, ctx)
        table.add_column("Keyboard", style=Colors.PRIMARY, no_wrap=True)
        table.add_column("Firmwares", style=Colors.ACCENT)
        table.add_column("Description", style=Colors.MUTED)
        return table


class PanelStyles:
    """Predefined panel styling templates."""

    @staticmethod
    def create_header_panel(
        title: str,
        subtitle: str = "",
        icon: str = "",
        icon_mode: IconMode | str | None = None,
        ctx: "typer.Context | None" = None,
    ) -> Panel:
        """Create styled header panel.

        Args:
            title: Main title
            subtitle: Optional subtitle
            icon: Icon to include
            icon_mode: Icon mode - IconMode enum or string. If None, will auto-detect from context.
            ctx: Typer context for auto-detecting icon mode from user config

        Returns:
            Configured Panel instance
        """
        # Auto-detect icon mode from context if not provided
        if icon_mode is None and ctx is not None:
            icon_mode = get_icon_mode_from_context(ctx)

        # Fallback to default if still None
        if icon_mode is None:
            icon_mode = IconMode.TEXT

        # Convert string to enum for backward compatibility
        if isinstance(icon_mode, str):
            icon_mode = IconMode(icon_mode)

        if icon:
            display_icon = (
                Icons.get_icon(icon.upper(), icon_mode)
                if hasattr(Icons, icon.upper())
                else icon
            )
            panel_title = f"{display_icon} {title}"
        else:
            panel_title = title
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
    def create_info_panel(
        content: str,
        title: str = "Information",
        icon_mode: IconMode | str | None = None,
        ctx: "typer.Context | None" = None,
    ) -> Panel:
        """Create styled information panel."""
        # Auto-detect icon mode from context if not provided
        if icon_mode is None and ctx is not None:
            icon_mode = get_icon_mode_from_context(ctx)

        # Fallback to default if still None
        if icon_mode is None:
            icon_mode = IconMode.TEXT

        icon = Icons.get_icon("INFO", icon_mode)
        return Panel(
            content,
            title=f"{icon} {title}",
            border_style=Colors.INFO,
            padding=(0, 1),
        )

    @staticmethod
    def create_error_panel(
        content: str,
        title: str = "Error",
        icon_mode: IconMode | str | None = None,
        ctx: "typer.Context | None" = None,
    ) -> Panel:
        """Create styled error panel."""
        # Auto-detect icon mode from context if not provided
        if icon_mode is None and ctx is not None:
            icon_mode = get_icon_mode_from_context(ctx)

        # Fallback to default if still None
        if icon_mode is None:
            icon_mode = IconMode.TEXT

        icon = Icons.get_icon("ERROR", icon_mode)
        return Panel(
            Text(content, style=Colors.ERROR),
            title=f"{icon} {title}",
            border_style=Colors.ERROR,
            padding=(0, 1),
        )

    @staticmethod
    def create_success_panel(
        content: str,
        title: str = "Success",
        icon_mode: IconMode | str | None = None,
        ctx: "typer.Context | None" = None,
    ) -> Panel:
        """Create styled success panel."""
        # Auto-detect icon mode from context if not provided
        if icon_mode is None and ctx is not None:
            icon_mode = get_icon_mode_from_context(ctx)

        # Fallback to default if still None
        if icon_mode is None:
            icon_mode = IconMode.TEXT

        icon = Icons.get_icon("SUCCESS", icon_mode)
        return Panel(
            Text(content, style=Colors.SUCCESS),
            title=f"{icon} {title}",
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
def get_themed_console(
    icon_mode: IconMode | str | None = None, ctx: "typer.Context | None" = None
) -> ThemedConsole:
    """Get a themed console instance with automatic icon mode detection.

    Args:
        icon_mode: Icon mode - IconMode enum or string. If None, will auto-detect from context.
        ctx: Typer context containing AppContext with user configuration.
             If provided and icon_mode is None, will automatically load icon_mode from user config.

    Returns:
        Configured ThemedConsole instance with appropriate icon mode
    """
    # Auto-detect icon mode from context if not provided
    if icon_mode is None and ctx is not None:
        icon_mode = get_icon_mode_from_context(ctx)

    # Fallback to default if still None
    if icon_mode is None:
        icon_mode = IconMode.TEXT

    # Convert string to enum for backward compatibility
    if isinstance(icon_mode, str):
        icon_mode = IconMode(icon_mode)

    return ThemedConsole(icon_mode=icon_mode)


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


def get_icon_mode_from_config(user_config: Any = None) -> IconMode:
    """Get icon mode from user configuration with fallback logic.

    Args:
        user_config: User configuration object

    Returns:
        IconMode enum value: IconMode.EMOJI, IconMode.NERDFONT, or IconMode.TEXT
    """
    if user_config is None:
        return IconMode.TEXT

    # Try new icon_mode field first
    if hasattr(user_config, "_config") and hasattr(user_config._config, "icon_mode"):
        icon_mode = user_config._config.icon_mode
        if icon_mode is not None:
            # Handle both enum and string values
            if isinstance(icon_mode, IconMode):
                return icon_mode
            return IconMode(str(icon_mode))
    elif hasattr(user_config, "icon_mode"):
        icon_mode = user_config.icon_mode
        if icon_mode is not None:
            # Handle both enum and string values
            if isinstance(icon_mode, IconMode):
                return icon_mode
            return IconMode(str(icon_mode))

    # Fall back to legacy emoji_mode for backward compatibility
    if hasattr(user_config, "_config") and hasattr(user_config._config, "emoji_mode"):
        emoji_mode = user_config._config.emoji_mode
        return IconMode.EMOJI if bool(emoji_mode) else IconMode.TEXT
    elif hasattr(user_config, "emoji_mode"):
        emoji_mode = user_config.emoji_mode
        return IconMode.EMOJI if bool(emoji_mode) else IconMode.TEXT

    # Default fallback - TEXT mode is now default
    return IconMode.TEXT


def get_icon_mode_from_context(ctx: "typer.Context") -> IconMode:
    """Get icon_mode from app context safely.

    Args:
        ctx: Typer context containing AppContext

    Returns:
        IconMode enum value from user configuration, or TEXT as fallback
    """
    try:
        app_ctx = ctx.obj
        if app_ctx is None:
            return IconMode.TEXT

        if not hasattr(app_ctx, "icon_mode"):
            return IconMode.TEXT

        icon_mode_value = app_ctx.icon_mode
        if isinstance(icon_mode_value, IconMode):
            return icon_mode_value
        elif isinstance(icon_mode_value, str):
            try:
                return IconMode(icon_mode_value)
            except ValueError:
                return IconMode.TEXT
        else:
            return IconMode.TEXT
    except Exception:
        # Default fallback
        return IconMode.TEXT


# Enhanced status formatting functions
def format_status_message(
    message: str, status: str, icon_mode: IconMode | str = IconMode.TEXT
) -> str:
    """Format message with appropriate color and symbol based on status.

    Args:
        message: The message text
        status: Status type (success, error, warning, info, running, etc.)
        icon_mode: Icon mode for symbol selection

    Returns:
        Formatted string with Rich markup for color and icon
    """
    if isinstance(icon_mode, str):
        icon_mode = IconMode(icon_mode)

    status_map = {
        "success": (Icons.get_icon("SUCCESS", icon_mode), Colors.SUCCESS),
        "error": (Icons.get_icon("ERROR", icon_mode), Colors.ERROR),
        "warning": (Icons.get_icon("WARNING", icon_mode), Colors.WARNING),
        "info": (Icons.get_icon("INFO", icon_mode), Colors.INFO),
        "running": (Icons.get_icon("RUNNING", icon_mode), Colors.RUNNING),
        "stopped": (Icons.get_icon("STOPPED", icon_mode), Colors.STOPPED),
        "pending": (Icons.get_icon("LOADING", icon_mode), Colors.PENDING),
        "completed": (Icons.get_icon("COMPLETED", icon_mode), Colors.COMPLETED),
        "failed": (Icons.get_icon("ERROR", icon_mode), Colors.FAILED),
    }

    symbol, color = status_map.get(
        status.lower(), (Icons.get_icon("INFO", icon_mode), Colors.INFO)
    )

    if symbol:
        return f"[{color}]{symbol} {message}[/]"
    else:
        return f"[{color}]{message}[/]"


def format_operation_status(
    operation: str, status: str, icon_mode: IconMode | str = IconMode.TEXT
) -> str:
    """Format operation with status-specific styling.

    Args:
        operation: The operation name (e.g., "Build", "Cache", "Export")
        status: Status type
        icon_mode: Icon mode for symbol selection

    Returns:
        Formatted string for operation status display
    """
    if isinstance(icon_mode, str):
        icon_mode = IconMode(icon_mode)

    # Map operations to specific icons
    operation_icons = {
        "build": "BUILD",
        "cache": "SAVE",
        "export": "UPLOAD",
        "import": "DOWNLOAD",
        "flash": "FLASH",
        "compile": "BUILD",
        "process": "RUNNING",
        "create": "CREATING",
        "update": "UPDATING",
    }

    icon_name = operation_icons.get(operation.lower(), "RUNNING")
    icon = Icons.get_icon(icon_name, icon_mode)

    # Map status to colors
    status_colors = {
        "success": Colors.SUCCESS,
        "completed": Colors.COMPLETED,
        "error": Colors.ERROR,
        "failed": Colors.FAILED,
        "running": Colors.RUNNING,
        "pending": Colors.PENDING,
        "warning": Colors.WARNING,
    }

    color = status_colors.get(status.lower(), Colors.INFO)

    if icon:
        return f"[{color}]{icon} {operation}[/]"
    else:
        return f"[{color}]{operation}[/]"


def format_progress_bar(
    current: int, total: int, width: int = 20, icon_mode: IconMode | str = IconMode.TEXT
) -> str:
    """Create a text-based progress bar using Unicode block characters.

    Args:
        current: Current progress value
        total: Total progress value
        width: Width of progress bar in characters
        icon_mode: Icon mode (affects bar style)

    Returns:
        Formatted progress bar string
    """
    if isinstance(icon_mode, str):
        icon_mode = IconMode(icon_mode)

    if total == 0:
        percentage: float = 0.0
    else:
        percentage = min(current / total, 1.0)

    filled_width = int(percentage * width)
    empty_width = width - filled_width

    # Use appropriate progress characters based on mode
    if icon_mode == IconMode.TEXT:
        filled_char = Icons.get_icon("PROGRESS_FULL", icon_mode) or "█"
        empty_char = Icons.get_icon("PROGRESS_EMPTY", icon_mode) or "░"
    else:
        filled_char = "█"  # Full block
        empty_char = "░"  # Light shade

    progress_bar = filled_char * filled_width + empty_char * empty_width

    # Color the progress bar
    if percentage == 1.0:
        color = Colors.PROGRESS_COMPLETE
    elif percentage > 0.5:
        color = Colors.PROGRESS_BAR
    elif percentage > 0:
        color = Colors.PROGRESS_PARTIAL
    else:
        color = Colors.MUTED

    return f"[{color}]{progress_bar}[/] {percentage:.0%}"


def format_file_operation(
    operation: str, filename: str, icon_mode: IconMode | str = IconMode.TEXT
) -> str:
    """Format file operation messages with consistent styling.

    Args:
        operation: File operation (create, read, write, delete, etc.)
        filename: File name or path
        icon_mode: Icon mode for symbol selection

    Returns:
        Formatted string for file operation
    """
    if isinstance(icon_mode, str):
        icon_mode = IconMode(icon_mode)

    operation_map = {
        "create": ("SAVE", Colors.NEW),
        "read": ("DOCUMENT", Colors.INFO),
        "write": ("SAVE", Colors.MODIFIED),
        "delete": ("TRASH", Colors.DELETED),
        "copy": ("CLONE", Colors.INFO),
        "move": ("ARROW", Colors.MODIFIED),
        "upload": ("UPLOAD", Colors.RUNNING),
        "download": ("DOWNLOAD", Colors.RUNNING),
    }

    icon_name, color = operation_map.get(operation.lower(), ("DOCUMENT", Colors.INFO))
    icon = Icons.get_icon(icon_name, icon_mode)

    if icon:
        return f"[{color}]{icon} {operation.title()} {filename}[/]"
    else:
        return f"[{color}]{operation.title()} {filename}[/]"
