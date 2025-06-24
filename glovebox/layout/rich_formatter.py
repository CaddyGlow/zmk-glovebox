"""Rich-based layout formatter for enhanced keyboard layout displays."""

import logging
from typing import TYPE_CHECKING, Any

from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from glovebox.layout.models import LayoutBinding, LayoutData


if TYPE_CHECKING:
    from glovebox.layout.formatting import LayoutConfig

logger = logging.getLogger(__name__)


class BehaviorColors:
    """Color scheme for different behavior types."""

    # Key behaviors
    ALPHANUMERIC = "cyan"
    MODIFIERS = "yellow"
    FUNCTION_KEYS = "green"

    # Layer behaviors
    LAYER_SWITCH = "blue"
    LAYER_TAP = "red"
    MOD_TAP = "magenta"

    # System behaviors
    SYSTEM = "bright_red"
    BLUETOOTH = "bright_blue"
    RGB = "bright_magenta"

    # Special
    TRANS = "dim white"
    NONE = "dim red"
    DEFAULT = "white"


class RichLayoutFormatter:
    """Rich-based formatter for keyboard layout displays."""

    def __init__(self, console: Console | None = None) -> None:
        """Initialize the Rich layout formatter.

        Args:
            console: Optional Rich console instance
        """
        self.console = console or Console()
        logger.debug("RichLayoutFormatter initialized")

    def format_keymap_display(
        self,
        layout_data: LayoutData,
        layout_config: "LayoutConfig",
        format_type: str = "rich-table",
        layer_index: int | None = None,
    ) -> None:
        """Generate a Rich-formatted keymap display.

        Args:
            layout_data: The parsed layout data to format
            layout_config: Layout configuration to use
            format_type: Rich format type (rich-table, rich-panel, rich-grid)
            layer_index: Optional specific layer to display
        """
        # Generate header
        self._print_header(layout_data)

        # Process layers
        layer_names = layout_data.layer_names or []
        layers = layout_data.layers or []

        if not layers:
            self.console.print("[red]No layers found in the keymap data.[/red]")
            return

        # Handle layer filtering
        if layer_index is not None:
            if 0 <= layer_index < len(layers):
                layers_to_display = [layers[layer_index]]
                layer_names_to_display = [
                    layer_names[layer_index]
                    if layer_index < len(layer_names)
                    else f"Layer {layer_index}"
                ]
                indices_to_display = [layer_index]
            else:
                self.console.print(
                    f"[red]Layer index {layer_index} is out of range (0-{len(layers) - 1}).[/red]"
                )
                return
        else:
            layers_to_display = layers
            layer_names_to_display = layer_names[: len(layers)]
            indices_to_display = list(range(len(layers)))

            # Pad layer names if needed
            while len(layer_names_to_display) < len(layers_to_display):
                layer_names_to_display.append(f"Layer {len(layer_names_to_display)}")

        # Render based on format type
        if format_type == "rich-table":
            self._render_table_format(
                layers_to_display,
                layer_names_to_display,
                indices_to_display,
                layout_config,
            )
        elif format_type == "rich-panel":
            self._render_panel_format(
                layers_to_display,
                layer_names_to_display,
                indices_to_display,
                layout_config,
            )
        elif format_type == "rich-grid":
            self._render_grid_format(
                layers_to_display,
                layer_names_to_display,
                indices_to_display,
                layout_config,
            )
        else:
            # Default to table format
            self._render_table_format(
                layers_to_display,
                layer_names_to_display,
                indices_to_display,
                layout_config,
            )

    def _print_header(self, layout_data: LayoutData) -> None:
        """Print the keymap header with Rich styling."""
        title = layout_data.title or "Untitled Layout"
        keyboard = layout_data.keyboard or "N/A"
        creator = layout_data.creator or "N/A"
        locale = layout_data.locale or "N/A"
        notes = layout_data.notes or ""

        # Create header content
        header_text = Text()
        header_text.append("Keyboard: ", style="bold")
        header_text.append(f"{keyboard}", style="cyan")
        header_text.append(" | ")
        header_text.append("Title: ", style="bold")
        header_text.append(f"{title}", style="green")
        header_text.append(f"\nCreator: {creator} | Locale: {locale}", style="dim")

        if notes:
            header_text.append(f"\nNotes: {notes}", style="italic")

        panel = Panel(
            header_text,
            title="[bold blue]Keyboard Layout[/bold blue]",
            border_style="blue",
            padding=(1, 2),
        )

        self.console.print(panel)
        self.console.print()  # Add spacing

    def _render_table_format(
        self,
        layers: list[list[Any]],
        layer_names: list[str],
        layer_indices: list[int],
        layout_config: "LayoutConfig",
    ) -> None:
        """Render layout in Rich table format."""
        for i, (layer_data, layer_name, layer_idx) in enumerate(
            zip(layers, layer_names, layer_indices, strict=False)
        ):
            # Create table for this layer
            table = Table(
                title=f"[bold blue]Layer {layer_idx}: {layer_name}[/bold blue]",
                border_style="blue",
                header_style="bold cyan",
                show_header=False,
                pad_edge=False,
                collapse_padding=True,
            )

            # Use layout_config.rows for structure
            if layout_config.rows:
                self._add_rows_to_table(table, layer_data, layout_config)
            else:
                # Default structure
                self._add_default_rows_to_table(table, layer_data, layout_config)

            self.console.print(table)
            if i < len(layers) - 1:  # Add spacing between layers
                self.console.print()

    def _render_panel_format(
        self,
        layers: list[list[Any]],
        layer_names: list[str],
        layer_indices: list[int],
        layout_config: "LayoutConfig",
    ) -> None:
        """Render layout in Rich panel format."""
        for layer_data, layer_name, layer_idx in zip(
            layers, layer_names, layer_indices, strict=False
        ):
            # Create content for this layer
            content = Text()

            if layout_config.rows:
                self._add_rows_to_content(content, layer_data, layout_config)
            else:
                self._add_default_rows_to_content(content, layer_data, layout_config)

            panel = Panel(
                content,
                title=f"[bold blue]Layer {layer_idx}: {layer_name}[/bold blue]",
                border_style="blue",
                padding=(1, 2),
            )

            self.console.print(panel)

    def _render_grid_format(
        self,
        layers: list[list[Any]],
        layer_names: list[str],
        layer_indices: list[int],
        layout_config: "LayoutConfig",
    ) -> None:
        """Render layout in Rich grid format using Columns for compact display."""
        for i, (layer_data, layer_name, layer_idx) in enumerate(
            zip(layers, layer_names, layer_indices, strict=False)
        ):
            # Create layer header
            header_text = Text(f"Layer {layer_idx}: {layer_name}", style="bold blue")
            self.console.print(header_text)
            self.console.print()

            # Create grid using Rich Columns
            if layout_config.rows:
                self._render_grid_with_layout(layer_data, layout_config)
            else:
                self._render_grid_default(layer_data, layout_config)

            if i < len(layers) - 1:  # Add spacing between layers
                self.console.print()
                self.console.print()

    def _render_grid_with_layout(
        self, layer_data: list[Any], layout_config: "LayoutConfig"
    ) -> None:
        """Render keyboard layout using configured row structure in grid format."""
        for row_indices in layout_config.rows:
            # Create key panels for this row
            key_panels = []
            for key_idx in row_indices:
                if key_idx >= 0 and key_idx < len(layer_data):
                    # Create styled text for the key
                    key_text = self._create_styled_key_text(layer_data[key_idx])
                    key_panel = Panel(
                        key_text,
                        padding=(0, 0),
                        border_style="dim",
                        width=10,
                    )
                    key_panels.append(key_panel)
                elif key_idx == -1:
                    # Empty space - create transparent panel
                    key_panel = Panel(
                        Text("", justify="center"),
                        padding=(0, 0),
                        border_style="dim",
                        style="dim",
                        width=10,
                    )
                    key_panels.append(key_panel)
                else:
                    # Invalid key
                    key_panel = Panel(
                        Text("???", justify="center", style="dim red"),
                        padding=(0, 0),
                        border_style="red",
                        width=10,
                    )
                    key_panels.append(key_panel)

            # Display row using Columns for proper spacing
            if key_panels:
                columns = Columns(key_panels, padding=(0, 1))
                self.console.print(columns)

    def _render_grid_default(
        self, layer_data: list[Any], layout_config: "LayoutConfig"
    ) -> None:
        """Render layout in default grid format when no specific row structure."""
        keys_per_row = 10
        num_rows = (len(layer_data) + keys_per_row - 1) // keys_per_row

        for row in range(num_rows):
            key_panels = []
            for col in range(keys_per_row):
                key_idx = row * keys_per_row + col
                if key_idx < len(layer_data):
                    # Create styled text for the key
                    key_text = self._create_styled_key_text(layer_data[key_idx])
                    key_panel = Panel(
                        key_text,
                        padding=(0, 0),
                        border_style="dim",
                        width=10,
                    )
                    key_panels.append(key_panel)
                else:
                    # Empty space for incomplete rows
                    key_panel = Panel(
                        Text("", justify="center"),
                        padding=(0, 0),
                        border_style="dim",
                        style="dim",
                        width=10,
                    )
                    key_panels.append(key_panel)

            # Display row using Columns
            columns = Columns(key_panels, padding=(0, 1))
            self.console.print(columns)

    def _create_styled_key_text(self, binding: Any) -> Text:
        """Create a Rich Text object with proper styling for grid display."""
        if isinstance(binding, LayoutBinding):
            # Get display value and color
            display_value = self._get_display_value(binding)
            color = self._get_key_color(binding, display_value)

            # Create centered text with color
            text = Text(display_value, style=color, justify="center")
            return text
        else:
            # For non-LayoutBinding objects, just display as string
            text = Text(str(binding), justify="center")
            return text

    def _add_rows_to_table(
        self, table: Table, layer_data: list[Any], layout_config: "LayoutConfig"
    ) -> None:
        """Add keyboard rows to Rich table based on layout configuration."""
        max_cols = (
            max(len(row) for row in layout_config.rows) if layout_config.rows else 0
        )

        # Add columns
        for _col in range(max_cols):
            table.add_column(justify="center", min_width=8, no_wrap=False)

        # Add rows
        for row_indices in layout_config.rows:
            table_row = []
            for _col_idx, key_idx in enumerate(row_indices):
                if key_idx >= 0 and key_idx < len(layer_data):
                    formatted_key = self._format_key_rich(layer_data[key_idx])
                    table_row.append(formatted_key)
                elif key_idx == -1:
                    table_row.append("")  # Empty space
                else:
                    table_row.append("[dim red]???[/dim red]")  # Invalid key

            # Pad row to match max columns
            while len(table_row) < max_cols:
                table_row.append("")

            table.add_row(*table_row)

    def _add_default_rows_to_table(
        self, table: Table, layer_data: list[Any], layout_config: "LayoutConfig"
    ) -> None:
        """Add default keyboard rows when no specific row structure is defined."""
        # Create a simple grid layout
        keys_per_row = 10
        num_rows = (len(layer_data) + keys_per_row - 1) // keys_per_row

        # Add columns
        for _col in range(keys_per_row):
            table.add_column(justify="center", min_width=8)

        # Add rows
        for row in range(num_rows):
            table_row = []
            for col in range(keys_per_row):
                key_idx = row * keys_per_row + col
                if key_idx < len(layer_data):
                    formatted_key = self._format_key_rich(layer_data[key_idx])
                    table_row.append(formatted_key)
                else:
                    table_row.append("")
            table.add_row(*table_row)

    def _add_rows_to_content(
        self, content: Text, layer_data: list[Any], layout_config: "LayoutConfig"
    ) -> None:
        """Add keyboard rows to Text content for panel format with proper alignment."""
        key_width = layout_config.key_width or 8

        for row_idx, row_indices in enumerate(layout_config.rows):
            # Create a list of formatted key strings for this row
            row_parts = []
            for key_idx in row_indices:
                if key_idx >= 0 and key_idx < len(layer_data):
                    # Get the display value and color
                    if isinstance(layer_data[key_idx], LayoutBinding):
                        display_value = self._get_display_value(layer_data[key_idx])
                        color = self._get_key_color(layer_data[key_idx], display_value)
                    else:
                        display_value = str(layer_data[key_idx])
                        color = "white"

                    # Pad the key to consistent width
                    padded_key = display_value.center(key_width)
                    row_parts.append((padded_key, color))
                elif key_idx == -1:
                    # Empty space - create larger gap for split keyboard
                    gap_width = (
                        key_width // 2
                    )  # Smaller gap between left and right halves
                    row_parts.append((" " * gap_width, "dim"))
                else:
                    # Invalid key
                    padded_key = "???".center(key_width)
                    row_parts.append((padded_key, "dim red"))

            # Build the row with proper styling
            for _i, (key_text, color) in enumerate(row_parts):
                styled_text = Text(key_text, style=color)
                content.append_text(styled_text)

            if row_idx < len(layout_config.rows) - 1:
                content.append("\n")

    def _add_default_rows_to_content(
        self, content: Text, layer_data: list[Any], layout_config: "LayoutConfig"
    ) -> None:
        """Add default keyboard rows to content when no specific structure is defined."""
        keys_per_row = 10
        num_rows = (len(layer_data) + keys_per_row - 1) // keys_per_row
        key_width = layout_config.key_width or 8

        for row in range(num_rows):
            row_parts = []
            for col in range(keys_per_row):
                key_idx = row * keys_per_row + col
                if key_idx < len(layer_data):
                    # Get the display value and color
                    if isinstance(layer_data[key_idx], LayoutBinding):
                        display_value = self._get_display_value(layer_data[key_idx])
                        color = self._get_key_color(layer_data[key_idx], display_value)
                    else:
                        display_value = str(layer_data[key_idx])
                        color = "white"

                    # Pad the key to consistent width
                    padded_key = display_value.center(key_width)
                    row_parts.append((padded_key, color))
                else:
                    # Empty space
                    row_parts.append((" " * key_width, "dim"))

            # Build the row with proper styling
            for _i, (key_text, color) in enumerate(row_parts):
                styled_text = Text(key_text, style=color)
                content.append_text(styled_text)

            if row < num_rows - 1:
                content.append("\n")

    def _format_key_rich(self, binding: Any) -> str:
        """Format a key binding with Rich styling."""
        if isinstance(binding, LayoutBinding):
            return self._format_binding_rich(binding)
        else:
            return str(binding)

    def _format_binding_rich(self, binding: LayoutBinding) -> str:
        """Format a LayoutBinding with Rich color coding."""
        if not binding.params:
            return f"[{self._get_behavior_color(binding.value)}]{binding.value}[/]"

        # Get formatted display value (without behavior name)
        display_value = self._get_display_value(binding)
        color = self._get_key_color(binding, display_value)

        return f"[{color}]{display_value}[/]"

    def _get_display_value(self, binding: LayoutBinding) -> str:
        """Get the display value for a binding (similar to existing logic)."""
        if binding.value == "&kp" and binding.params:
            return str(binding.params[0].value)
        elif binding.value == "&mo" and binding.params:
            return f"L{binding.params[0].value}"
        elif binding.value == "&to" and binding.params:
            return f"→L{binding.params[0].value}"
        elif binding.value == "&tog" and binding.params:
            return f"⇄L{binding.params[0].value}"
        elif binding.value == "&lt" and len(binding.params) >= 2:
            return f"L{binding.params[0].value}/{binding.params[1].value}"
        elif binding.value == "&mt" and len(binding.params) >= 2:
            return f"{binding.params[0].value}/{binding.params[1].value}"
        elif binding.value == "&bt" and binding.params:
            bt_cmd = str(binding.params[0].value)
            if len(binding.params) > 1:
                return f"BT{binding.params[1].value}"
            else:
                return bt_cmd.replace("BT_", "")
        elif binding.value == "&rgb_ug" and binding.params:
            return str(binding.params[0].value).replace("RGB_", "")
        else:
            if binding.params:
                return f"{binding.value[1:]}({binding.params[0].value})"
            else:
                return binding.value

    def _get_behavior_color(self, behavior: str) -> str:
        """Get color for behavior name."""
        if behavior == "&trans":
            return BehaviorColors.TRANS
        elif behavior == "&none":
            return BehaviorColors.NONE
        elif behavior in ["&sys_reset", "&bootloader", "&reset"]:
            return BehaviorColors.SYSTEM
        elif behavior.startswith("&bt"):
            return BehaviorColors.BLUETOOTH
        elif behavior.startswith("&rgb"):
            return BehaviorColors.RGB
        elif behavior in ["&mo", "&to", "&tog"]:
            return BehaviorColors.LAYER_SWITCH
        elif behavior == "&lt":
            return BehaviorColors.LAYER_TAP
        elif behavior == "&mt":
            return BehaviorColors.MOD_TAP
        else:
            return BehaviorColors.DEFAULT

    def _get_key_color(self, binding: LayoutBinding, display_value: str) -> str:
        """Get color for the displayed key value."""
        # Special cases first
        if binding.value == "&trans":
            return BehaviorColors.TRANS
        elif binding.value == "&none":
            return BehaviorColors.NONE
        elif binding.value in ["&sys_reset", "&bootloader", "&reset"]:
            return BehaviorColors.SYSTEM
        elif binding.value.startswith("&bt"):
            return BehaviorColors.BLUETOOTH
        elif binding.value.startswith("&rgb"):
            return BehaviorColors.RGB
        elif binding.value in ["&mo", "&to", "&tog"]:
            return BehaviorColors.LAYER_SWITCH
        elif binding.value == "&lt":
            return BehaviorColors.LAYER_TAP
        elif binding.value == "&mt":
            return BehaviorColors.MOD_TAP
        elif binding.value == "&kp" and binding.params:
            # Color code based on key type
            key_name = str(binding.params[0].value)
            return self._get_key_type_color(key_name)
        else:
            return BehaviorColors.DEFAULT

    def _get_key_type_color(self, key_name: str) -> str:
        """Get color based on key type."""
        # Function keys
        if key_name.startswith("F") and key_name[1:].isdigit():
            return BehaviorColors.FUNCTION_KEYS

        # Modifier keys
        modifiers = [
            "LCTRL",
            "RCTRL",
            "LSHIFT",
            "RSHIFT",
            "LALT",
            "RALT",
            "LGUI",
            "RGUI",
            "LSHFT",
            "RSHFT",
            "LCTL",
            "RCTL",
            "LCMD",
            "RCMD",
        ]
        if key_name in modifiers:
            return BehaviorColors.MODIFIERS

        # Alphanumeric keys (default cyan)
        if (key_name.isalnum() and len(key_name) == 1) or key_name.startswith("N"):
            return BehaviorColors.ALPHANUMERIC

        # Special keys get function key color
        special_keys = ["SPACE", "ENTER", "TAB", "ESC", "BSPC", "DEL", "RET"]
        if key_name in special_keys:
            return BehaviorColors.FUNCTION_KEYS

        # Default
        return BehaviorColors.DEFAULT


def create_rich_layout_formatter(console: Console | None = None) -> RichLayoutFormatter:
    """Create a new RichLayoutFormatter instance.

    Args:
        console: Optional Rich console instance

    Returns:
        Configured RichLayoutFormatter instance
    """
    return RichLayoutFormatter(console)
