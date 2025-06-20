"""Unified theme system for consistent Rich styling across CLI commands."""

from typing import Any

from rich.console import Console
from rich.panel import Panel
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

    # Bookmark-specific icons
    BOOKMARK = "📑"
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
        "BOOKMARK": "\uf02e",  # nf-fa-bookmark
        "FACTORY": "\uf275",  # nf-fa-industry
        "CLONE": "\uf24d",  # nf-fa-clone
    }

    # Text fallbacks for emoji-disabled mode
    _TEXT_FALLBACKS = {
        # Status indicators - use minimal or no prefix for clean output
        "SUCCESS": "",  # For Yes/No status, just show "Yes"
        "ERROR": "",  # For Yes/No status, just show "No"
        "WARNING": "!",  # Keep warning indicator as it's important
        "INFO": "i",  # Minimal info indicator
        # Action indicators - keep these for clarity
        "CHECKMARK": "✓",  # Simple checkmark works well
        "CROSS": "✗",  # Simple X works well
        "BULLET": "•",  # Keep bullet point
        "ARROW": "→",  # Keep arrow for flow
        # Category icons - use shorter, cleaner prefixes
        "DEVICE": "",  # No prefix needed in context
        "KEYBOARD": "",  # No prefix needed in context
        "FIRMWARE": "",  # No prefix needed in context
        "LAYOUT": "",  # No prefix needed in context
        "DOCKER": "Docker",  # Keep for clarity in mixed contexts
        "SYSTEM": "",  # No prefix needed in context
        "CONFIG": "",  # No prefix needed in context
        "USB": "",  # No prefix needed in context
        "FLASH": "",  # No prefix needed in context
        "BUILD": "",  # No prefix needed in context
        # Process indicators - use minimal indicators
        "LOADING": "...",  # Simple loading indicator
        "COMPLETED": "✓",  # Reuse checkmark for completed
        "RUNNING": "▶",  # Simple play symbol
        "STOPPED": "■",  # Simple stop symbol
        # Additional icon fallbacks
        "UPLOAD": "",  # Clean for upload operations
        "DOWNLOAD": "",  # Clean for download operations
        "DOCUMENT": "",  # Clean for document references
        "LINK": "",  # Clean for links
        "CALENDAR": "",  # Clean for dates
        "USER": "",  # Clean for user references
        "TAG": "",  # Clean for tags
        "EYE": "",  # Clean for viewing
        "SEARCH": "",  # Clean for search
        "FAMILY": "",  # Clean for family/sharing
        "STATS": "",  # Clean for statistics
        "TREE": "",  # Clean for tree structures
        "CROWN": "",  # Clean for premium/important
        "SCROLL": "",  # Clean for documents
        "STAR": "",  # Clean for favorites
        "TRASH": "",  # Clean for deletion
        "QUESTION": "?",  # Keep question mark
        "GLOBE": "",  # Clean for network/web
        "SAVE": "",  # Clean for save operations
        "CLIPBOARD": "",  # Clean for clipboard
        "APPLE": "",  # Clean for platform
        "WINDOWS": "",  # Clean for platform
        "LINUX": "",  # Clean for platform
        "FOLDER": "",  # Clean for folders
        "MAILBOX": "",  # Clean for empty state
        "SHIELD": "",  # Clean for security
        "DIAMOND": "•",  # Use bullet for list items
        "LOCK": "",  # Clean for security
        "KEYSTORE": "",  # Clean for keystore
        "BOOKMARK": "",  # Clean for bookmarks
        "FACTORY": "",  # Clean for factory items
        "CLONE": "",  # Clean for clone operations
    }

    @classmethod
    def get_icon(cls, icon_name: str, icon_mode: str = "emoji") -> str:
        """Get icon based on the specified mode.

        Args:
            icon_name: Name of the icon (e.g., "SUCCESS", "ERROR")
            icon_mode: Icon mode - "emoji", "nerdfont", or "text"

        Returns:
            The appropriate icon based on mode
        """
        if icon_mode == "nerdfont":
            return cls._NERDFONT_ICONS.get(icon_name, "")
        elif icon_mode == "emoji":
            return getattr(cls, icon_name, "")
        else:  # text mode
            return cls._TEXT_FALLBACKS.get(icon_name, f"[{icon_name}]")

    @classmethod
    def format_with_icon(
        cls, icon_name: str, text: str, icon_mode: str = "emoji"
    ) -> str:
        """Format text with icon, handling empty icons gracefully.

        Args:
            icon_name: Name of the icon
            text: Text to format
            icon_mode: Icon mode - "emoji", "nerdfont", or "text"

        Returns:
            Formatted string with proper spacing
        """
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

    def __init__(self, icon_mode: str = "emoji") -> None:
        """Initialize themed console.

        Args:
            icon_mode: Icon mode - "emoji", "nerdfont", or "text"
        """
        self.console = Console(theme=GLOVEBOX_THEME)
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
        title: str = "", icon: str = "", icon_mode: str = "emoji"
    ) -> Table:
        """Create a basic styled table.

        Args:
            title: Table title
            icon: Icon to include in title
            icon_mode: Icon mode - "emoji", "nerdfont", or "text"

        Returns:
            Configured Table instance
        """
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
    def create_device_table(icon_mode: str = "emoji") -> Table:
        """Create table for device listings."""
        table = TableStyles.create_basic_table("USB Devices", "DEVICE", icon_mode)
        table.add_column("Device", style=Colors.PRIMARY, no_wrap=True)
        table.add_column("Serial", style=Colors.ACCENT)
        table.add_column("Path", style=Colors.MUTED)
        table.add_column("Status", style="bold")
        return table

    @staticmethod
    def create_status_table(icon_mode: str = "emoji") -> Table:
        """Create table for status information."""
        table = TableStyles.create_basic_table("System Status", "SYSTEM", icon_mode)
        table.add_column("Component", style=Colors.PRIMARY, no_wrap=True)
        table.add_column("Status", style="bold")
        table.add_column("Details", style=Colors.MUTED)
        return table

    @staticmethod
    def create_config_table(icon_mode: str = "emoji") -> Table:
        """Create table for configuration display."""
        table = TableStyles.create_basic_table("Configuration", "CONFIG", icon_mode)
        table.add_column("Setting", style=Colors.PRIMARY, no_wrap=True)
        table.add_column("Value", style=Colors.NORMAL)
        return table

    @staticmethod
    def create_keyboard_table(icon_mode: str = "emoji") -> Table:
        """Create table for keyboard listings."""
        table = TableStyles.create_basic_table("Keyboards", "KEYBOARD", icon_mode)
        table.add_column("Keyboard", style=Colors.PRIMARY, no_wrap=True)
        table.add_column("Firmwares", style=Colors.ACCENT)
        table.add_column("Description", style=Colors.MUTED)
        return table


class PanelStyles:
    """Predefined panel styling templates."""

    @staticmethod
    def create_header_panel(
        title: str, subtitle: str = "", icon: str = "", icon_mode: str = "emoji"
    ) -> Panel:
        """Create styled header panel.

        Args:
            title: Main title
            subtitle: Optional subtitle
            icon: Icon to include
            icon_mode: Icon mode - "emoji", "nerdfont", or "text"

        Returns:
            Configured Panel instance
        """
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
        content: str, title: str = "Information", icon_mode: str = "emoji"
    ) -> Panel:
        """Create styled information panel."""
        icon = Icons.get_icon("INFO", icon_mode)
        return Panel(
            content,
            title=f"{icon} {title}",
            border_style=Colors.INFO,
            padding=(0, 1),
        )

    @staticmethod
    def create_error_panel(
        content: str, title: str = "Error", icon_mode: str = "emoji"
    ) -> Panel:
        """Create styled error panel."""
        icon = Icons.get_icon("ERROR", icon_mode)
        return Panel(
            Text(content, style=Colors.ERROR),
            title=f"{icon} {title}",
            border_style=Colors.ERROR,
            padding=(0, 1),
        )

    @staticmethod
    def create_success_panel(
        content: str, title: str = "Success", icon_mode: str = "emoji"
    ) -> Panel:
        """Create styled success panel."""
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
def get_themed_console(icon_mode: str = "emoji") -> ThemedConsole:
    """Get a themed console instance.

    Args:
        icon_mode: Icon mode - "emoji", "nerdfont", or "text"

    Returns:
        Configured ThemedConsole instance
    """
    return ThemedConsole(icon_mode=icon_mode)


def get_themed_console_legacy(use_emoji: bool = True) -> ThemedConsole:
    """Legacy function for backward compatibility.

    Args:
        use_emoji: Whether to use emoji icons or text fallbacks

    Returns:
        Configured ThemedConsole instance
    """
    icon_mode = "emoji" if use_emoji else "text"
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


def get_icon_mode_from_config(user_config: Any = None) -> str:
    """Get icon mode from user configuration with fallback logic.

    Args:
        user_config: User configuration object

    Returns:
        Icon mode string: "emoji", "nerdfont", or "text"
    """
    if user_config is None:
        return "emoji"

    # Try new icon_mode field first
    if hasattr(user_config, "_config") and hasattr(user_config._config, "icon_mode"):
        return user_config._config.icon_mode
    elif hasattr(user_config, "icon_mode"):
        return user_config.icon_mode

    # Fall back to legacy emoji_mode for backward compatibility
    if hasattr(user_config, "_config") and hasattr(user_config._config, "emoji_mode"):
        return "emoji" if user_config._config.emoji_mode else "text"
    elif hasattr(user_config, "emoji_mode"):
        return "emoji" if user_config.emoji_mode else "text"

    # Default fallback
    return "emoji"
