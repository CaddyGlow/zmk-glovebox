"""Grid layout formatting for keyboard layouts and visual displays."""

import enum
import logging
import os
import shutil
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from glovebox.layout.models import LayoutBinding, LayoutData


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile


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
        layout_data: LayoutData,
        layout_config: LayoutConfig,
        view_mode: ViewMode | None = None,
        layer_index: int | None = None,
    ) -> str:
        """Generate a formatted keymap display using the provided layout configuration.

        Args:
            layout_data: The parsed layout data to format
            layout_config: Layout configuration to use
            view_mode: Optional view mode to use
            layer_index: Optional specific layer to display

        Returns:
            Formatted keymap display
        """
        output_lines = []

        # Extract keymap data from LayoutData object
        title = layout_data.title or "Untitled Layout"
        creator = layout_data.creator or "N/A"
        locale = layout_data.locale or "N/A"
        notes = layout_data.notes or ""

        # Generate header
        header_width = 80
        output_lines.append("=" * header_width)
        output_lines.append(
            f"Keyboard: {layout_data.keyboard or 'N/A'} | Title: {title}"
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
        layer_names = layout_data.layer_names or []
        layers = layout_data.layers or []

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

        # Convert LayoutBinding objects to strings for display methods
        layers_to_display_str = [
            [self._format_binding_display(binding) for binding in layer]
            for layer in layers_to_display
        ]

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
        elif view_mode == ViewMode.COMPACT:
            # Compact mode shows layers in a condensed format
            self._generate_compact_view(
                output_lines,
                indices_to_display,
                layers_to_display_str,
                layer_names_to_display,
                layout_config,
            )
        else:
            # Default grid view (normal or split)
            # Custom grid rendering based on the keyboard layout
            self._generate_grid_view(
                output_lines,
                indices_to_display,
                layers_to_display_str,
                layer_names_to_display,
                layout_config,
                view_mode,
            )

        return "\n".join(output_lines)

    def _generate_grid_view(
        self,
        output_lines: list[str],
        layer_indices: list[int],
        layers: list[list[str]],
        layer_names: list[str],
        layout_config: LayoutConfig,
        view_mode: ViewMode | None = None,
    ) -> None:
        """Generate a grid view of the layout based on layout_config.

        Args:
            output_lines: List to append output lines to
            layer_indices: List of layer indices to display
            layers: List of layer data to display
            layer_names: List of layer names to display
            layout_config: Layout configuration
            view_mode: Optional view mode to control split behavior
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

        # Determine whether to use vertical split layout based on view_mode
        if view_mode == ViewMode.SPLIT:
            # User explicitly requested split view
            use_vertical_split = True
        elif view_mode == ViewMode.NORMAL:
            # User explicitly requested normal view (no split)
            use_vertical_split = False
        else:
            # Auto-detect based on console width (fallback for backward compatibility)
            use_vertical_split = self._should_use_vertical_split(layout_config)

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

            if use_vertical_split:
                self._render_vertical_split_layout(
                    output_lines,
                    row_structure,
                    layer_data,
                    num_keys_in_layer,
                    key_width,
                    key_gap,
                )
            else:
                self._render_horizontal_layout(
                    output_lines,
                    row_structure,
                    layer_data,
                    num_keys_in_layer,
                    key_width,
                    key_gap,
                )

    def _render_horizontal_layout(
        self,
        output_lines: list[str],
        row_structure: list[list[int]],
        layer_data: list[Any],
        num_keys_in_layer: int,
        key_width: int,
        key_gap: str,
    ) -> None:
        """Render layout in traditional horizontal split format.

        Args:
            output_lines: List to append output lines to
            row_structure: Row structure defining key positions
            layer_data: Layer data containing bindings
            num_keys_in_layer: Number of keys in the layer
            key_width: Width for displaying each key
            key_gap: Gap between keys
        """
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

    def _render_vertical_split_layout(
        self,
        output_lines: list[str],
        row_structure: list[list[int]],
        layer_data: list[Any],
        num_keys_in_layer: int,
        key_width: int,
        key_gap: str,
    ) -> None:
        """Render layout in vertical split format for narrow terminals.

        This splits the keyboard into left and right halves, showing them
        one above the other instead of side by side.

        Args:
            output_lines: List to append output lines to
            row_structure: Row structure defining key positions
            layer_data: Layer data containing bindings
            num_keys_in_layer: Number of keys in the layer
            key_width: Width for displaying each key
            key_gap: Gap between keys
        """
        # Separate rows into left and right halves
        left_rows = []
        right_rows = []

        for row_indices in row_structure:
            if len(row_indices) >= 6:  # Split rows that have enough keys
                # Find split point (look for -1 markers or use midpoint)
                split_idx = self._find_split_point(row_indices)
                left_indices = [idx for idx in row_indices[:split_idx] if idx >= 0]
                right_indices = [idx for idx in row_indices[split_idx:] if idx >= 0]

                if left_indices:
                    left_rows.append(left_indices)
                if right_indices:
                    right_rows.append(right_indices)
            else:
                # For smaller rows (like thumb clusters), put on both sides or split
                valid_indices = [idx for idx in row_indices if idx >= 0]
                if len(valid_indices) >= 4:
                    mid = len(valid_indices) // 2
                    left_rows.append(valid_indices[:mid])
                    right_rows.append(valid_indices[mid:])
                elif len(valid_indices) > 0:
                    # Add to left side for odd small rows
                    left_rows.append(valid_indices)

        # Calculate section width - use a generous width for better visual balance
        max_left_keys = max(len(row) for row in left_rows) if left_rows else 0
        max_right_keys = max(len(row) for row in right_rows) if right_rows else 0
        max_keys = max(max_left_keys, max_right_keys)

        # Use a more generous section width for better visual presentation
        # This ensures both halves have consistent, wider formatting
        base_width = (
            max_keys * key_width + (max_keys - 1) * len(key_gap) if max_keys > 0 else 40
        )
        # Calculate a wider section that can accommodate about 10-12 keys comfortably
        ideal_width = 12 * key_width + 11 * len(key_gap)
        section_width = max(base_width, ideal_width)

        # Render left half
        output_lines.append("Left Half:")
        output_lines.append("-" * section_width)

        for row_indices in left_rows:
            row_parts = []
            for idx in row_indices:
                binding = self._format_key(
                    idx, layer_data, num_keys_in_layer, key_width
                )
                row_parts.append(binding)

            row_str = key_gap.join(row_parts)
            output_lines.append(row_str)

        output_lines.append("-" * section_width)
        output_lines.append("")  # Spacing between halves

        # Render right half
        output_lines.append("Right Half:")
        output_lines.append("-" * section_width)

        for row_indices in right_rows:
            row_parts = []
            for idx in row_indices:
                binding = self._format_key(
                    idx, layer_data, num_keys_in_layer, key_width
                )
                row_parts.append(binding)

            row_str = key_gap.join(row_parts)
            # Right-align the right half within the section width
            aligned_row = row_str.rjust(section_width)
            output_lines.append(aligned_row)

        output_lines.append("-" * section_width)

    def _find_split_point(self, row_indices: list[int]) -> int:
        """Find the optimal split point in a row.

        Looks for -1 markers (gaps) to determine split, prioritizing gaps that
        have actual keys (>= 0) on both sides.

        Args:
            row_indices: List of key indices in the row

        Returns:
            Index where to split the row
        """
        # Find all valid key positions (not -1)
        valid_positions = [i for i, idx in enumerate(row_indices) if idx >= 0]

        if len(valid_positions) < 2:
            # Not enough keys to split meaningfully
            return len(row_indices) // 2

        # Look for gaps between valid keys
        for i in range(len(valid_positions) - 1):
            current_pos = valid_positions[i]
            next_pos = valid_positions[i + 1]

            # Check if there's a gap between these keys
            if next_pos - current_pos > 1:
                # Found a gap between valid keys, split after the gap
                gap_end = next_pos
                return gap_end

        # No meaningful gap found between keys, split at midpoint of valid keys
        mid_valid_key = len(valid_positions) // 2
        return valid_positions[mid_valid_key]

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

            # Handle LayoutBinding objects - show full behavior with params
            if isinstance(binding, LayoutBinding):
                binding_str = self._format_binding_display(binding)
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

    def _format_binding_display(self, binding: LayoutBinding) -> str:
        """Format a binding for display showing behavior and parameters.

        Args:
            binding: The LayoutBinding to format

        Returns:
            Formatted string showing behavior and key parameters
        """
        if not binding.params:
            return binding.value

        # For behaviors with parameters, show main parameter value
        if binding.value == "&kp" and binding.params:
            # Show key name for kp behaviors
            return str(binding.params[0].value)
        elif binding.value == "&mo" and binding.params:
            # Show layer number for momentary layer
            return f"L{binding.params[0].value}"
        elif binding.value == "&to" and binding.params:
            # Show layer number for layer switch
            return f"→L{binding.params[0].value}"
        elif binding.value == "&tog" and binding.params:
            # Show layer number for layer toggle
            return f"⇄L{binding.params[0].value}"
        elif binding.value == "&lt" and len(binding.params) >= 2:
            # Show layer and tap key for layer-tap
            return f"L{binding.params[0].value}/{binding.params[1].value}"
        elif binding.value == "&mt" and len(binding.params) >= 2:
            # Show modifier and tap key for mod-tap
            return f"{binding.params[0].value}/{binding.params[1].value}"
        elif binding.value == "&bt" and binding.params:
            # Show bluetooth command
            bt_cmd = str(binding.params[0].value)
            if len(binding.params) > 1:
                return f"BT{binding.params[1].value}"
            else:
                return bt_cmd.replace("BT_", "")
        elif binding.value == "&rgb_ug" and binding.params:
            # Show RGB command
            return str(binding.params[0].value).replace("RGB_", "")
        else:
            # For other behaviors, show behavior name with first param if available
            if binding.params:
                return f"{binding.value[1:]}({binding.params[0].value})"
            else:
                return binding.value

    def _get_console_width(self) -> int:
        """Get the current console width, with fallback to default.

        Returns:
            Console width in characters
        """
        try:
            # Try to get actual terminal width
            width = shutil.get_terminal_size().columns
            if width > 0:
                return width
        except (OSError, AttributeError):
            # Fallback if terminal size detection fails
            pass

        # Try environment variable
        try:
            width = int(os.environ.get("COLUMNS", "80"))
            if width > 0:
                return width
        except (ValueError, TypeError):
            pass

        # Final fallback
        return 80

    def _should_use_vertical_split(self, layout_config: LayoutConfig) -> bool:
        """Determine if layout should be split vertically due to width constraints.

        Args:
            layout_config: Layout configuration with formatting info

        Returns:
            True if vertical split should be used
        """
        console_width = self._get_console_width()

        # Calculate approximate layout width
        key_width = layout_config.key_width
        key_gap = layout_config.key_gap

        # Find the longest row to estimate total width
        max_keys_per_row = 0
        if layout_config.rows:
            for row in layout_config.rows:
                # Count non-empty keys (not -1)
                valid_keys = len([k for k in row if k >= 0])
                max_keys_per_row = max(max_keys_per_row, valid_keys)

        if max_keys_per_row == 0:
            return False

        # Estimate total width: keys + gaps + some margin
        estimated_width = (
            (max_keys_per_row * key_width)
            + ((max_keys_per_row - 1) * len(key_gap))
            + 10
        )

        # Get threshold from configuration (default 0.85 if not set)
        threshold_ratio = layout_config.formatting.get("vertical_split_threshold", 0.85)
        threshold = int(console_width * threshold_ratio)
        should_split = estimated_width > threshold

        logger.debug(
            f"Console width: {console_width}, estimated layout width: {estimated_width}, "
            f"threshold: {threshold} (ratio: {threshold_ratio}), will split: {should_split}"
        )

        return should_split

    def _generate_compact_view(
        self,
        output_lines: list[str],
        layer_indices: list[int],
        layers: list[list[str]],
        layer_names: list[str],
        layout_config: LayoutConfig,
    ) -> None:
        """Generate a compact view of the layout with minimal spacing.

        Args:
            output_lines: List to append output lines to
            layer_indices: List of layer indices to display
            layer_names: List of layer names to display
            layers: List of layer data to display
            layout_config: Layout configuration
        """
        key_width = max(
            4, layout_config.key_width - 2
        )  # Reduce key width for compactness
        key_gap = " "  # Single space gap for compact display

        # Use layout_config.rows if available, otherwise use default structure
        if layout_config.rows:
            row_structure = layout_config.rows
        else:
            # Default compact structure - fewer rows for readability
            row_structure = [
                [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],  # Row 0
                [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21],  # Row 1
                [22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33],  # Row 2
                [34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45],  # Row 3
                [46, 47, 48, 49, 50, 51, 58, 59, 60, 61, 62, 63],  # Row 4
                [69, 52, 57, 74, 70, 53, 56, 73, 71, 54, 55, 72],  # Combined thumb rows
            ]

        # Iterate through layers
        for i, (layer_idx, layer_data, layer_name) in enumerate(
            zip(layer_indices, layers, layer_names, strict=False)
        ):
            if i > 0:
                output_lines.append("")  # Single line spacing between layers

            output_lines.append(f"L{layer_idx}: {layer_name}")

            num_keys_in_layer = len(layer_data)
            expected_keys = layout_config.key_count or 80

            # Show fewer rows for compact display
            for _row_idx, row_indices in enumerate(
                row_structure[:4]
            ):  # Limit to first 4 rows
                row_parts = []
                for idx in row_indices:
                    if idx >= 0 and idx < num_keys_in_layer:
                        binding = self._format_key(
                            idx, layer_data, num_keys_in_layer, key_width
                        )
                        row_parts.append(binding)
                    elif idx == -1:
                        row_parts.append(" " * (key_width // 2))  # Small gap for splits
                    else:
                        row_parts.append(" " * key_width)  # Empty space

                # Only show non-empty rows
                if any(part.strip() for part in row_parts):
                    row_str = key_gap.join(row_parts)
                    output_lines.append(f"  {row_str}")  # Small indent

            # Show summary of remaining keys if any
            total_displayed = sum(
                len([k for k in row if k >= 0]) for row in row_structure[:4]
            )
            if total_displayed < num_keys_in_layer:
                remaining = num_keys_in_layer - total_displayed
                output_lines.append(f"  ... +{remaining} more keys")


def create_grid_layout_formatter() -> GridLayoutFormatter:
    """Create a new GridLayoutFormatter instance.

    Returns:
        Configured GridLayoutFormatter instance
    """
    return GridLayoutFormatter()
