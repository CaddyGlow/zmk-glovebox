"""Unified output formatting system with Rich integration and multiple format support."""

import json
from typing import Any, Protocol

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


class FormattableData(Protocol):
    """Protocol for data that can be formatted for output."""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON/table formatting."""
        ...


class OutputFormatter:
    """Centralized output formatting with support for multiple formats."""

    def __init__(self, console: Console | None = None) -> None:
        """Initialize the formatter with optional console.

        Args:
            console: Rich console instance, creates new one if None
        """
        self.console = console or Console()

    def format(self, data: Any, format_type: str = "text") -> str:
        """Format data according to the specified format type.

        Args:
            data: Data to format
            format_type: Output format (text, json, markdown, table)

        Returns:
            Formatted string output
        """
        format_type = format_type.lower()

        if format_type == "json":
            return self._format_json(data)
        elif format_type in ("markdown", "md"):
            return self._format_markdown(data)
        elif format_type == "table":
            return self._format_table(data)
        else:  # text (default)
            return self._format_text(data)

    def print_formatted(self, data: Any, format_type: str = "text") -> None:
        """Print formatted data directly to console.

        Args:
            data: Data to format and print
            format_type: Output format (text, json, markdown, table)
        """
        if format_type.lower() == "table":
            # For table format, use Rich console directly
            self._print_table(data)
        else:
            # For other formats, get string and print
            output = self.format(data, format_type)
            if format_type.lower() == "text":
                # Use Rich console for text with potential styling
                self.console.print(output)
            else:
                # Use regular print for json/markdown
                print(output)

    def _format_json(self, data: Any) -> str:
        """Format data as JSON."""
        if hasattr(data, "model_dump"):
            # Pydantic model
            return json.dumps(data.model_dump(), indent=2)
        elif hasattr(data, "to_dict"):
            # Custom to_dict method
            return json.dumps(data.to_dict(), indent=2)
        elif isinstance(data, dict):
            return json.dumps(data, indent=2, default=str)
        elif isinstance(data, list):
            # Handle list of objects
            json_data = []
            for item in data:
                if hasattr(item, "model_dump"):
                    json_data.append(item.model_dump())
                elif hasattr(item, "to_dict"):
                    json_data.append(item.to_dict())
                else:
                    json_data.append(str(item))
            return json.dumps(json_data, indent=2)
        else:
            return json.dumps(str(data), indent=2)

    def _format_markdown(self, data: Any) -> str:
        """Format data as Markdown."""
        if isinstance(data, dict):
            return self._dict_to_markdown(data)
        elif isinstance(data, list):
            return self._list_to_markdown(data)
        else:
            return f"```\n{str(data)}\n```"

    def _format_text(self, data: Any) -> str:
        """Format data as plain text."""
        if isinstance(data, str):
            return data
        elif isinstance(data, dict):
            lines = []
            for key, value in data.items():
                lines.append(f"{key}: {value}")
            return "\n".join(lines)
        elif isinstance(data, list):
            return "\n".join(f"• {item}" for item in data)
        else:
            return str(data)

    def _format_table(self, data: Any) -> str:
        """Format data as Rich table (returns empty string, actual printing done separately)."""
        # Table formatting is handled by _print_table method
        return ""

    def _print_table(self, data: Any) -> None:
        """Print data as Rich table."""
        if isinstance(data, dict):
            self._print_dict_table(data)
        elif isinstance(data, list):
            self._print_list_table(data)
        else:
            # Simple single-value table
            table = Table(show_header=False)
            table.add_column("Value", style="cyan")
            table.add_row(str(data))
            self.console.print(table)

    def _print_dict_table(self, data: dict[str, Any]) -> None:
        """Print dictionary as Rich table."""
        table = Table(show_header=True, header_style="bold blue")
        table.add_column("Property", style="cyan", no_wrap=True)
        table.add_column("Value", style="white")

        for key, value in data.items():
            # Format complex values
            if isinstance(value, dict | list):
                value_str = json.dumps(value, indent=2)
            else:
                value_str = str(value)
            table.add_row(key, value_str)

        self.console.print(table)

    def _print_list_table(self, data: list[Any]) -> None:
        """Print list as Rich table."""
        if not data:
            self.console.print("No data to display")
            return

        # Handle list of dictionaries (common case)
        if isinstance(data[0], dict):
            self._print_dict_list_table(data)
        else:
            # Simple list
            table = Table(show_header=True, header_style="bold blue")
            table.add_column("Item", style="cyan")

            for item in data:
                table.add_row(str(item))

            self.console.print(table)

    def _print_dict_list_table(self, data: list[dict[str, Any]]) -> None:
        """Print list of dictionaries as Rich table."""
        if not data:
            return

        # Get all possible keys from all dictionaries
        all_keys: set[str] = set()
        for item in data:
            all_keys.update(item.keys())

        table = Table(show_header=True, header_style="bold blue")

        # Add columns for each key
        for key in sorted(all_keys):
            table.add_column(key.replace("_", " ").title(), style="cyan")

        # Add rows
        for item in data:
            row_values = []
            for key in sorted(all_keys):
                value = item.get(key, "")
                if isinstance(value, dict | list):
                    value_str = json.dumps(value)
                else:
                    value_str = str(value)
                row_values.append(value_str)
            table.add_row(*row_values)

        self.console.print(table)

    def _dict_to_markdown(self, data: dict[str, Any]) -> str:
        """Convert dictionary to Markdown format."""
        lines = ["| Property | Value |", "|----------|-------|"]

        for key, value in data.items():
            if isinstance(value, dict | list):
                value_str = f"`{json.dumps(value)}`"
            else:
                value_str = str(value)
            lines.append(f"| {key} | {value_str} |")

        return "\n".join(lines)

    def _list_to_markdown(self, data: list[Any]) -> str:
        """Convert list to Markdown format."""
        if not data:
            return "No items to display"

        # Handle list of dictionaries
        if isinstance(data[0], dict):
            return self._dict_list_to_markdown(data)
        else:
            # Simple list
            lines = []
            for item in data:
                lines.append(f"- {item}")
            return "\n".join(lines)

    def _dict_list_to_markdown(self, data: list[dict[str, Any]]) -> str:
        """Convert list of dictionaries to Markdown table."""
        if not data:
            return "No items to display"

        # Get all possible keys
        all_keys: set[str] = set()
        for item in data:
            all_keys.update(item.keys())

        # Header
        header_keys = sorted(all_keys)
        lines = [
            "| "
            + " | ".join(key.replace("_", " ").title() for key in header_keys)
            + " |",
            "|" + "|".join("-------" for _ in header_keys) + "|",
        ]

        # Rows
        for item in data:
            row_values = []
            for key in header_keys:
                value = item.get(key, "")
                if isinstance(value, dict | list):
                    value_str = f"`{json.dumps(value)}`"
                else:
                    value_str = str(value)
                row_values.append(value_str)
            lines.append("| " + " | ".join(row_values) + " |")

        return "\n".join(lines)


# Device list specific formatters
class DeviceListFormatter(OutputFormatter):
    """Specialized formatter for device lists."""

    def format_device_list(
        self,
        devices: list[dict[str, Any]],
        format_type: str = "text",
        use_emoji: bool = True,
    ) -> str:
        """Format device list with enhanced presentation.

        Args:
            devices: List of device dictionaries
            format_type: Output format
            use_emoji: Whether to use emoji icons

        Returns:
            Formatted device list
        """
        if format_type.lower() == "table":
            self._print_device_table(devices, use_emoji)
            return ""
        else:
            return self.format(devices, format_type)

    def _print_device_table(
        self, devices: list[dict[str, Any]], use_emoji: bool = True
    ) -> None:
        """Print devices as enhanced Rich table."""
        from glovebox.cli.helpers.theme import Icons

        device_icon = Icons.get_icon("DEVICE", use_emoji)
        table = Table(
            title=f"{device_icon} USB Devices",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Device", style="cyan", no_wrap=True)
        table.add_column("Serial", style="yellow")
        table.add_column("Path", style="dim")
        table.add_column("Status", style="bold")

        for device in devices:
            name = device.get("name", "Unknown")
            serial = device.get("serial", "N/A")
            path = device.get("path", "N/A")
            status = device.get("status", "unknown")

            # Color-code status with configurable icons
            if status == "available":
                icon = Icons.get_icon("SUCCESS", use_emoji)
                status_display = f"{icon} Available"
            elif status == "busy":
                icon = Icons.get_icon("LOADING", use_emoji)
                status_display = f"{icon} Busy"
            elif status == "error":
                icon = Icons.get_icon("ERROR", use_emoji)
                status_display = f"{icon} Error"
            else:
                icon = Icons.get_icon("WARNING", use_emoji)
                status_display = f"{icon} Unknown"

            table.add_row(name, serial, path, status_display)

        if not devices:
            table.add_row("No devices found", "", "", "")

        self.console.print(table)


# Layout display specific formatters
class LayoutDisplayFormatter(OutputFormatter):
    """Specialized formatter for layout display."""

    def format_layout_display(
        self, layout_data: dict[str, Any], format_type: str = "text"
    ) -> str:
        """Format layout display with enhanced presentation.

        Args:
            layout_data: Layout data dictionary
            format_type: Output format

        Returns:
            Formatted layout display
        """
        if format_type.lower() == "table":
            self._print_layout_table(layout_data)
            return ""
        else:
            return self.format(layout_data, format_type)

    def _print_layout_table(
        self, layout_data: dict[str, Any], use_emoji: bool = True
    ) -> None:
        """Print layout as enhanced Rich table."""
        from glovebox.cli.helpers.theme import Icons

        # Create header panel
        title = layout_data.get("name", "Keyboard Layout")
        header = Text(title, style="bold magenta")
        keyboard_icon = Icons.get_icon("KEYBOARD", use_emoji)
        self.console.print(
            Panel(header, title=f"{keyboard_icon} Layout Display", border_style="blue")
        )
        self.console.print()

        # Layout info table
        info_table = Table(
            title="Layout Information", show_header=True, header_style="bold green"
        )
        info_table.add_column("Property", style="cyan", no_wrap=True)
        info_table.add_column("Value", style="white")

        basic_info = {
            "Name": layout_data.get("name", "Unknown"),
            "Layers": len(layout_data.get("layers", [])),
            "Key Count": layout_data.get("key_count", "Unknown"),
            "Description": layout_data.get("description", "No description"),
        }

        for prop, value in basic_info.items():
            info_table.add_row(prop, str(value))

        self.console.print(info_table)


# Factory function for creating appropriate formatter
def create_output_formatter(formatter_type: str = "default") -> OutputFormatter:
    """Create appropriate output formatter.

    Args:
        formatter_type: Type of formatter (default, device, layout)

    Returns:
        OutputFormatter instance
    """
    if formatter_type == "device":
        return DeviceListFormatter()
    elif formatter_type == "layout":
        return LayoutDisplayFormatter()
    else:
        return OutputFormatter()
