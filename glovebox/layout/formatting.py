"""Grid layout formatting for keyboard layouts and visual displays."""

import enum
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from glovebox.layout.models import LayoutBinding


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile
    from glovebox.layout.models import LayoutData


logger = logging.getLogger(__name__)


class ViewMode(enum.Enum):
    """View modes for layout display."""

    NORMAL = "normal"
    COMPACT = "compact"
    SPLIT = "split"
    FLAT = "flat"


@dataclass
class LayoutMetadata:
    """Metadata for a layout."""

    keyboard_type: str
    description: str = ""
    keyboard: str = ""
    version: str = "1.0"
    author: str = ""


@dataclass
class LayoutConfig:
    """Configuration for a layout."""

    keyboard_name: str
    key_width: int
    key_gap: str
    key_position_map: dict[str, int]
    total_keys: int = 0
    key_count: int = 0
    rows: list[list[int]] = field(default_factory=list)
    metadata: LayoutMetadata | None = None
    formatting: dict[str, Any] = field(default_factory=dict)


class GridLayoutFormatter:
    """Formatter for grid-based keyboard layout displays."""

    def __init__(self) -> None:
        """Initialize the layout formatter."""
        logger.debug("GridLayoutFormatter initialized")

    def generate_layer_layout(
        self,
        bindings: list[str],
        profile: "KeyboardProfile",
        base_indent: str | None = None,
    ) -> list[str]:
        """Generate formatted binding strings into a grid based on LayoutConfig.

        Args:
            bindings: List of binding strings to format
            profile: Keyboard profile containing formatting information
            base_indent: Optional override for base indentation

        Returns:
            List of formatted layout lines for DTSI
        """
        output_lines = []
        empty_slot_marker = None

        config = profile.keyboard_config
        fmt = profile.keyboard_config.keymap.formatting
        actual_base_indent = base_indent if base_indent is not None else fmt.base_indent
        key_gap = fmt.key_gap

        bindings_map: dict[int, str] = {}
        num_bindings_available = len(bindings)

        # Ensure we have enough bindings, pad if necessary
        if num_bindings_available < config.key_count:
            logger.warning(
                f"Layer has {num_bindings_available} bindings, expected {config.key_count}. "
                f"Padding missing indices with '&none'."
            )
            bindings.extend(["&none"] * (config.key_count - num_bindings_available))

        for idx, binding_str in enumerate(bindings):
            if idx >= config.key_count:
                logger.warning(
                    f"Binding index {idx} exceeds key_count ({config.key_count}). "
                    f"Ignoring extra binding: {binding_str}"
                )
                continue
            bindings_map[idx] = str(binding_str)

        if not isinstance(fmt.rows, list) or not all(
            isinstance(r, list) for r in fmt.rows
        ):
            logger.error(
                "Invalid 'rows' structure in LayoutConfig. Expected list of lists."
            )
            return [
                actual_base_indent + "  // Error: Invalid 'rows' structure in config"
            ]

        num_rows = len(fmt.rows)
        num_cols = max(len(r) for r in fmt.rows) if fmt.rows else 0
        grid_matrix: list[list[str | None]] = [
            [empty_slot_marker] * num_cols for _ in range(num_rows)
        ]

        # Populate the matrix
        for r, row_indices in enumerate(fmt.rows):
            # Each row_indices is already guaranteed to be a list by the type definition
            for c, key_index in enumerate(row_indices):
                if c >= num_cols:
                    logger.warning(
                        f"Column index {c} exceeds calculated max columns {num_cols} in row {r}."
                    )
                    continue
                if key_index == -1:
                    grid_matrix[r][c] = empty_slot_marker
                elif key_index in bindings_map:
                    grid_matrix[r][c] = bindings_map[key_index]
                else:
                    logger.warning(
                        f"Key index {key_index} (row {r}, col {c}) not found in bindings map. Using empty slot."
                    )
                    grid_matrix[r][c] = empty_slot_marker

        # Calculate max width for each column
        max_col_widths = [0] * num_cols
        for c in range(num_cols):
            col_binding_lengths = []
            for r in range(num_rows):
                cell_content = grid_matrix[r][c]
                if cell_content is not empty_slot_marker:
                    col_binding_lengths.append(len(cell_content))

            if col_binding_lengths:
                max_col_widths[c] = max(col_binding_lengths)

        # Format output lines
        for r in range(num_rows):
            current_row_parts = []
            for c in range(num_cols):
                cell_content = grid_matrix[r][c]
                current_col_width = max_col_widths[c]

                if cell_content is empty_slot_marker:
                    current_row_parts.append(" ".rjust(current_col_width))
                else:
                    current_row_parts.append(cell_content.rjust(current_col_width))

            row_string = key_gap.join(current_row_parts)
            line = f"{actual_base_indent}{row_string}"
            output_lines.append(line)

        return output_lines

    def format_keymap_display(
        self,
        keymap_data: dict[str, Any],
        layout_config: LayoutConfig,
        view_mode: ViewMode | None = None,
        layer_index: int | None = None,
    ) -> str:
        """Generate a formatted keymap display using the provided layout configuration.

        Args:
            keymap_data: The keymap data to format
            layout_config: Layout configuration to use
            view_mode: Optional view mode to use
            layer_index: Optional specific layer to display

        Returns:
            Formatted keymap display
        """
        output_lines = []

        # Extract keymap data
        title = keymap_data.get("title") or keymap_data.get("name") or "Untitled Layout"
        creator = keymap_data.get("creator", "N/A")
        locale = keymap_data.get("locale", "N/A")
        notes = keymap_data.get("notes", "")

        # Generate header
        header_width = 80
        output_lines.append("=" * header_width)
        output_lines.append(
            f"Keyboard: {keymap_data.get('keyboard', 'N/A')} | Title: {title}"
        )
        output_lines.append(f"Creator: {creator} | Locale: {locale}")
        if notes:
            import textwrap

            wrapped_notes = textwrap.wrap(notes, width=header_width - len("Notes: "))
            output_lines.append(f"Notes: {wrapped_notes[0]}")
            for line in wrapped_notes[1:]:
                output_lines.append(f"        {line}")
        output_lines.append("=" * header_width)

        # Process layers
        layer_names = keymap_data.get("layer_names", [])
        layers = keymap_data.get("layers", [])

        if not layers:
            return "No layers found in the keymap data."

        if not layer_names:
            logger.warning("No layer names found, using default names.")
            layer_names = [f"Layer {i}" for i in range(len(layers))]
        elif len(layer_names) != len(layers):
            logger.warning(
                f"Mismatch between layer names ({len(layer_names)}) and layer data ({len(layers)}). Using available names."
            )
            if len(layer_names) < len(layers):
                layer_names = layer_names + [
                    f"Layer {i}" for i in range(len(layer_names), len(layers))
                ]
            else:
                layer_names = layer_names[: len(layers)]

        # If layer_index is specified, only display that layer
        if layer_index is not None:
            if 0 <= layer_index < len(layers):
                layers_to_display = [layers[layer_index]]
                layer_names_to_display = [layer_names[layer_index]]
                indices_to_display = [layer_index]
            else:
                return (
                    f"Layer index {layer_index} is out of range (0-{len(layers) - 1})."
                )
        else:
            layers_to_display = layers
            layer_names_to_display = layer_names
            indices_to_display = list(range(len(layers)))

        # Generate layout view based on view_mode
        view_mode = view_mode or ViewMode.NORMAL

        # Implementation for different view modes
        if view_mode == ViewMode.FLAT:
            # Flat mode just lists all bindings sequentially
            for _i, (layer_idx, layer, name) in enumerate(
                zip(
                    indices_to_display,
                    layers_to_display,
                    layer_names_to_display,
                    strict=False,
                )
            ):
                output_lines.append(f"\n--- Layer {layer_idx}: {name} ---")
                for j, binding in enumerate(layer):
                    if binding:
                        output_lines.append(f"Key {j}: {binding}")
        else:
            # Default grid view
            # Custom grid rendering based on the keyboard layout (Glove80 in this example)
            self._generate_grid_view(
                output_lines,
                indices_to_display,
                layers_to_display,
                layer_names_to_display,
                layout_config,
            )

        return "\n".join(output_lines)

    def _generate_grid_view(
        self,
        output_lines: list[str],
        layer_indices: list[int],
        layers: list[list[str]],
        layer_names: list[str],
        layout_config: LayoutConfig,
    ) -> None:
        """Generate a grid view of the layout based on layout_config.

        Args:
            output_lines: List to append output lines to
            layer_indices: List of layer indices to display
            layers: List of layer data to display
            layer_names: List of layer names to display
            layout_config: Layout configuration
        """
        key_width = layout_config.key_width
        key_gap = layout_config.key_gap

        # Use layout_config.rows if available, otherwise use default Glove80 layout
        if layout_config.rows:
            row_structure = layout_config.rows
        else:
            # Default Glove80 layout structure
            row_structure = [
                [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],  # Row 0
                [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21],  # Row 1
                [22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33],  # Row 2
                [34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45],  # Row 3
                [46, 47, 48, 49, 50, 51, 58, 59, 60, 61, 62, 63],  # Row 4
                [64, 65, 66, 67, 68, 75, 76, 77, 78, 79],  # Row 5
                [69, 52, 57, 74],  # Thumb row 1
                [70, 53, 56, 73],  # Thumb row 2
                [71, 54, 55, 72],  # Thumb row 3
            ]

        # Iterate through layers
        for _i, (layer_idx, layer_data, layer_name) in enumerate(
            zip(layer_indices, layers, layer_names, strict=False)
        ):
            output_lines.append(f"\n--- Layer {layer_idx}: {layer_name} ---")

            num_keys_in_layer = len(layer_data)
            expected_keys = layout_config.key_count or 80
            if num_keys_in_layer != expected_keys:
                logger.warning(
                    f"Layer '{layer_name}' has {num_keys_in_layer} keys, expected {expected_keys}. Display may be incomplete."
                )

            # Format grid lines based on row structure
            h_spacer = " | "
            total_width = 0

            # Calculate total width based on first row structure
            if row_structure:
                first_split_idx = len(row_structure[0]) // 2
                left_width = first_split_idx * (key_width + len(key_gap)) - len(key_gap)
                right_width = (len(row_structure[0]) - first_split_idx) * (
                    key_width + len(key_gap)
                ) - len(key_gap)
                total_width = left_width + len(h_spacer) + right_width
            else:
                total_width = 80  # Default width

            output_lines.append("-" * total_width)

            for row_indices in row_structure:
                # For split layouts, find the midpoint to insert the spacer
                if len(row_indices) >= 10:  # Assuming rows with 10+ keys are split rows
                    split_idx = len(row_indices) // 2
                    left_indices = row_indices[:split_idx]
                    right_indices = row_indices[split_idx:]

                    left_parts = []
                    for idx in left_indices:
                        binding = self._format_key(
                            idx, layer_data, num_keys_in_layer, key_width
                        )
                        left_parts.append(binding)

                    right_parts = []
                    for idx in right_indices:
                        binding = self._format_key(
                            idx, layer_data, num_keys_in_layer, key_width
                        )
                        right_parts.append(binding)

                    left_str = key_gap.join(left_parts)
                    right_str = key_gap.join(right_parts)
                    output_lines.append(f"{left_str}{h_spacer}{right_str}")
                else:
                    # Non-split rows (like thumb clusters)
                    row_parts = []
                    for idx in row_indices:
                        binding = self._format_key(
                            idx, layer_data, num_keys_in_layer, key_width
                        )
                        row_parts.append(binding)

                    # Center smaller rows
                    row_str = key_gap.join(row_parts)
                    padding = (total_width - len(row_str)) // 2
                    output_lines.append(" " * padding + row_str)

            output_lines.append("-" * total_width)

    def _format_key(
        self, idx: int, layer_data: list[Any], layer_size: int, key_width: int
    ) -> str:
        """Format a single key for display.

        Args:
            idx: Key index
            layer_data: Layer data containing bindings
            layer_size: Size of the layer
            key_width: Width for the key display

        Returns:
            Formatted key string
        """
        if 0 <= idx < layer_size:
            binding = layer_data[idx]

            # Handle LayoutBinding objects
            if isinstance(binding, LayoutBinding):
                binding_str = binding.value
            else:
                binding_str = str(binding)

            if binding_str == "&none":
                return "&none".center(key_width)
            elif binding_str == "&trans":
                return "▽".center(key_width)
            elif len(binding_str) > key_width:
                # Truncate with ellipsis
                return (binding_str[: key_width - 1] + "…").center(key_width)
            else:
                return binding_str.center(key_width)
        return " " * key_width


def create_grid_layout_formatter() -> GridLayoutFormatter:
    """Create a new GridLayoutFormatter instance.

    Returns:
        Configured GridLayoutFormatter instance
    """
    return GridLayoutFormatter()
