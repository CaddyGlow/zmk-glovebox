"""DTSI layout generation service for creating ZMK device tree layout sections."""

import enum
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional, Protocol, TypeAlias, Union, cast

from glovebox.config.profile import KeyboardProfile
from glovebox.layout.behavior_formatter import BehaviorFormatterImpl
from glovebox.layout.models import (
    ComboBehavior,
    HoldTapBehavior,
    InputListener,
    LayerBindings,
    LayoutBinding,
    MacroBehavior,
)
from glovebox.models.behavior import SystemBehavior
from glovebox.protocols.behavior_protocols import BehaviorRegistryProtocol


logger = logging.getLogger(__name__)


# Type alias for kconfig settings
KConfigSettings: TypeAlias = dict[str, str]


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile
    from glovebox.layout.models import LayoutData


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


class DtsiLayoutGenerator:
    """Generator for DTSI layout sections from keymap data."""

    def __init__(self) -> None:
        """Initialize the layout generator."""
        logger.debug("DtsiLayoutGenerator initialized")

    def generate_layer_layout(
        self, bindings: list[str], profile: KeyboardProfile
    ) -> list[str]:
        """Generate formatted binding strings into a grid based on LayoutConfig.

        Args:
            bindings: List of binding strings to format
            profile: Keyboard profile containing formatting information

        Returns:
            List of formatted layout lines for DTSI
        """
        output_lines = []
        EMPTY_SLOT_MARKER = None

        config = profile.keyboard_config
        fmt = profile.keyboard_config.keymap.formatting
        base_indent = fmt.base_indent
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
            return [base_indent + "  // Error: Invalid 'rows' structure in config"]

        num_rows = len(fmt.rows)
        num_cols = max(len(r) for r in fmt.rows) if fmt.rows else 0
        grid_matrix: list[list[str | None]] = [
            [EMPTY_SLOT_MARKER] * num_cols for _ in range(num_rows)
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
                    grid_matrix[r][c] = EMPTY_SLOT_MARKER
                elif key_index in bindings_map:
                    grid_matrix[r][c] = bindings_map[key_index]
                else:
                    logger.warning(
                        f"Key index {key_index} (row {r}, col {c}) not found in bindings map. Using empty slot."
                    )
                    grid_matrix[r][c] = EMPTY_SLOT_MARKER

        # Calculate max width for each column
        max_col_widths = [0] * num_cols
        for c in range(num_cols):
            col_binding_lengths = []
            for r in range(num_rows):
                cell_content = grid_matrix[r][c]
                if cell_content is not EMPTY_SLOT_MARKER:
                    col_binding_lengths.append(len(cell_content))

            if col_binding_lengths:
                max_col_widths[c] = max(col_binding_lengths)

        # Format output lines
        for r in range(num_rows):
            current_row_parts = []
            for c in range(num_cols):
                cell_content = grid_matrix[r][c]
                current_col_width = max_col_widths[c]

                if cell_content is EMPTY_SLOT_MARKER:
                    current_row_parts.append(" ".rjust(current_col_width))
                else:
                    current_row_parts.append(cell_content.rjust(current_col_width))

            row_string = key_gap.join(current_row_parts)
            line = f"{base_indent}{row_string}"
            output_lines.append(line)

        return output_lines

    def generate_keymap_display(
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


class DTSIGenerator:
    """Service for generating DTSI content from JSON data."""

    def __init__(self, behavior_formatter: BehaviorFormatterImpl) -> None:
        """Initialize with behavior formatter dependency.

        Args:
            behavior_formatter: Formatter for converting bindings to DTSI format
        """
        self._behavior_formatter = behavior_formatter
        self._behavior_registry = behavior_formatter._registry
        self._layout_generator = DtsiLayoutGenerator()

    def generate_layer_defines(
        self, profile: "KeyboardProfile", layer_names: list[str]
    ) -> str:
        """Generate #define statements for layers.

        Args:
            profile: Keyboard profile containing configuration
            layer_names: List of layer names

        Returns:
            String with #define statements for each layer
        """
        defines = []
        for i, name in enumerate(layer_names):
            define_name = re.sub(r"\W|^(?=\d)", "_", name)
            defines.append(f"#define LAYER_{define_name} {i}")
        return "\n".join(defines)

    def generate_behaviors_dtsi(
        self, profile: "KeyboardProfile", hold_taps_data: Sequence[HoldTapBehavior]
    ) -> str:
        """Generate ZMK behaviors node string from hold-tap behavior models.

        Args:
            profile: Keyboard profile containing configuration
            hold_taps_data: List of hold-tap behavior models

        Returns:
            DTSI behaviors node content as string
        """
        if not hold_taps_data:
            return ""

        # Extract key position map from profile for use with hold-tap positions
        key_position_map = {}
        # Build a default key position map if needed
        for i in range(profile.keyboard_config.key_count):
            key_position_map[f"KEY_{i}"] = i

        dtsi_parts = []

        for ht in hold_taps_data:
            name = ht.name
            if not name:
                logger.warning("Skipping hold-tap behavior with missing 'name'.")
                continue

            node_name = name[1:] if name.startswith("&") else name
            bindings = ht.bindings
            tapping_term = ht.tapping_term_ms
            flavor = ht.flavor
            quick_tap = ht.quick_tap_ms
            require_idle = ht.require_prior_idle_ms
            hold_on_release = ht.hold_trigger_on_release
            hold_key_positions_indices = ht.hold_trigger_key_positions

            if len(bindings) != 2:
                logger.warning(
                    f"Behavior '{name}' requires exactly 2 bindings (hold, tap). Found {len(bindings)}. Skipping."
                )
                continue

            # Register the behavior
            self._behavior_registry.register_behavior(
                SystemBehavior(
                    code=ht.name,
                    name=ht.name,
                    description=ht.description,
                    expected_params=2,
                    origin="user_hold_tap",
                    params=[],
                )
            )

            label = (ht.description or node_name).split("\n")
            label = [f"// {line}" for line in label]

            dtsi_parts.extend(label)
            dtsi_parts.append(f"{node_name}: {node_name} {{")
            dtsi_parts.append('    compatible = "zmk,behavior-hold-tap";')
            dtsi_parts.append("    #binding-cells = <2>;")

            if tapping_term is not None:
                dtsi_parts.append(f"    tapping-term-ms = <{tapping_term}>;")

            # Format bindings
            formatted_bindings = []
            for binding_ref in bindings:
                # Always use format_binding for consistent handling
                formatted_bindings.append(
                    self._behavior_formatter.format_binding(binding_ref)
                )

            if len(formatted_bindings) == 2:
                dtsi_parts.append(
                    f"    bindings = <{formatted_bindings[0]}>, <{formatted_bindings[1]}>;"
                )
            else:
                dtsi_parts.append("    bindings = <&error>, <&error>;")

            if flavor is not None:
                allowed_flavors = [
                    "tap-preferred",
                    "hold-preferred",
                    "balanced",
                    "tap-unless-interrupted",
                ]
                if flavor in allowed_flavors:
                    dtsi_parts.append(f'    flavor = "{flavor}";')
                else:
                    logger.warning(
                        f"Invalid flavor '{flavor}' for behavior '{name}'. Omitting."
                    )

            if quick_tap is not None:
                dtsi_parts.append(f"    quick-tap-ms = <{quick_tap}>;")

            if require_idle is not None:
                dtsi_parts.append(f"    require-prior-idle-ms = <{require_idle}>;")

            if (
                hold_key_positions_indices is not None
                and len(hold_key_positions_indices) > 0
            ):
                pos_numbers = [str(idx) for idx in hold_key_positions_indices]
                dtsi_parts.append(
                    f"    hold-trigger-key-positions = <{' '.join(pos_numbers)}>;"
                )

            if hold_on_release:
                dtsi_parts.append("    hold-trigger-on-release;")

            if ht.retro_tap:
                dtsi_parts.append("    retro-tap;")

            dtsi_parts.append("};")
            dtsi_parts.append("")

        dtsi_parts.pop()  # Remove last blank line
        return "\n".join(self._indent_array(dtsi_parts, " " * 8))

    def generate_macros_dtsi(
        self, profile: "KeyboardProfile", macros_data: Sequence[MacroBehavior]
    ) -> str:
        """Generate ZMK macros node string from macro behavior models.

        Args:
            profile: Keyboard profile containing configuration
            macros_data: List of macro behavior models

        Returns:
            DTSI macros node content as string
        """
        if not macros_data:
            return ""

        dtsi_parts = [""]

        for macro in macros_data:
            name = macro.name
            if not name:
                logger.warning("Skipping macro with missing 'name'.")
                continue

            node_name = name[1:] if name.startswith("&") else name
            description = (macro.description or node_name).split("\n")
            description = [f"// {line}" for line in description]

            bindings = macro.bindings
            params = macro.params or []
            wait_ms = macro.wait_ms
            tap_ms = macro.tap_ms

            # Determine compatible and binding-cells based on params
            if not params:
                compatible = "zmk,behavior-macro"
                binding_cells = "0"
            elif len(params) == 1:
                compatible = "zmk,behavior-macro-one-param"
                binding_cells = "1"
            elif len(params) == 2:
                compatible = "zmk,behavior-macro-two-param"
                binding_cells = "2"
            else:
                logger.warning(
                    f"Macro '{name}' has {len(params)} params, which is not supported. Maximum is 2."
                )
                continue

            # Register the macro behavior
            self._behavior_registry.register_behavior(
                SystemBehavior(
                    code=macro.name,
                    name=macro.name,
                    description=macro.description,
                    expected_params=2,
                    origin="user_macro",
                    params=[],
                )
            )

            macro_parts = []

            if description:
                macro_parts.extend(description)
            macro_parts.append(f"{node_name}: {node_name} {{")
            macro_parts.append(f'    label = "{name.upper()}";')
            macro_parts.append(f'    compatible = "{compatible}";')
            macro_parts.append(f"    #binding-cells = <{binding_cells}>;")
            if tap_ms is not None:
                macro_parts.append(f"    tap-ms = <{tap_ms}>;")
            if wait_ms is not None:
                macro_parts.append(f"    wait-ms = <{wait_ms}>;")
            if bindings:
                bindings_str = "\n                      , ".join(
                    f"<{self._behavior_formatter.format_binding(b)}>" for b in bindings
                )
                macro_parts.append(f"    bindings = {bindings_str};")
            macro_parts.append("};")
            dtsi_parts.extend(self._indent_array(macro_parts, "        "))
            dtsi_parts.append("")

        dtsi_parts.pop()  # Remove last blank line
        return "\n".join(dtsi_parts)

    def generate_combos_dtsi(
        self,
        profile: "KeyboardProfile",
        combos_data: Sequence[ComboBehavior],
        layer_names: list[str],
    ) -> str:
        """Generate ZMK combos node string from combo behavior models.

        Args:
            profile: Keyboard profile containing configuration
            combos_data: List of combo behavior models
            layer_names: List of layer names

        Returns:
            DTSI combos node content as string
        """
        if not combos_data:
            return ""

        # Extract key position map from profile for use with combo positions
        key_position_map = {}
        # Build a default key position map if needed
        for i in range(profile.keyboard_config.key_count):
            key_position_map[f"KEY_{i}"] = i

        dtsi_parts = ["combos {"]
        dtsi_parts.append('    compatible = "zmk,combos";')

        layer_name_to_index = {name: i for i, name in enumerate(layer_names)}
        layer_defines = {
            i: f"LAYER_{re.sub(r'[^A-Z0-9_]', '_', name.upper())}"
            for i, name in enumerate(layer_names)
        }

        for combo in combos_data:
            logger.info(f"Processing combo: {combo}")
            name = combo.name
            if not name:
                logger.warning("Skipping combo with missing 'name'.")
                continue

            node_name = re.sub(r"\W|^(?=\d)", "_", name)
            binding_data = combo.binding
            key_positions_indices = combo.key_positions
            timeout = combo.timeout_ms
            layers_spec = combo.layers

            if not binding_data or not key_positions_indices:
                logger.warning(
                    f"Combo '{name}' is missing binding or keyPositions. Skipping."
                )
                continue

            description_lines = (combo.description or node_name).split("\n")
            label = "\n".join([f"    // {line}" for line in description_lines])

            dtsi_parts.append(f"{label}")
            dtsi_parts.append(f"    combo_{node_name} {{")

            if timeout is not None:
                dtsi_parts.append(f"        timeout-ms = <{timeout}>;")

            key_pos_defines = [
                str(key_position_map.get(str(idx), idx))
                for idx in key_positions_indices
            ]
            dtsi_parts.append(f"        key-positions = <{' '.join(key_pos_defines)}>;")

            formatted_binding = self._behavior_formatter.format_binding(binding_data)
            dtsi_parts.append(f"        bindings = <{formatted_binding}>;")

            # Format layers
            if layers_spec and layers_spec != [-1]:
                combo_layer_defines = []
                for layer_id in layers_spec:
                    # Get layer define directly using the layer index
                    layer_define = layer_defines.get(layer_id)

                    if layer_define:
                        combo_layer_defines.append(layer_define)
                    else:
                        logger.warning(
                            f"Combo '{name}' specifies unknown layer '{layer_id}'. Ignoring this layer."
                        )

                if combo_layer_defines:
                    dtsi_parts.append(
                        f"        layers = <{' '.join(combo_layer_defines)}>;"
                    )

            dtsi_parts.append("    };")
            dtsi_parts.append("")

        dtsi_parts.pop()  # Remove last blank line
        dtsi_parts.append("};")
        return "\n".join(self._indent_array(dtsi_parts))

    def generate_input_listeners_node(
        self, profile: "KeyboardProfile", input_listeners_data: Sequence[InputListener]
    ) -> str:
        """Generate input listener nodes string from input listener models.

        Args:
            profile: Keyboard profile containing configuration
            input_listeners_data: List of input listener models

        Returns:
            DTSI input listeners node content as string
        """
        if not input_listeners_data:
            return ""

        dtsi_parts = []
        for listener in input_listeners_data:
            listener_code = listener.code
            if not listener_code:
                logger.warning("Skipping input listener with missing 'code'.")
                continue

            dtsi_parts.append(f"{listener_code} {{")

            global_processors = listener.input_processors
            if global_processors:
                processors_str = " ".join(
                    f"{p.code} {' '.join(map(str, p.params))}".strip()
                    for p in global_processors
                )
                if processors_str:
                    dtsi_parts.append(f"    input-processors = <{processors_str}>;")

            nodes = listener.nodes
            if not nodes:
                logger.warning(
                    f"Input listener '{listener_code}' has no nodes defined."
                )
            else:
                for node in nodes:
                    node_code = node.code
                    if not node_code:
                        logger.warning(
                            f"Skipping node in listener '{listener_code}' with missing 'code'."
                        )
                        continue

                    dtsi_parts.append("")
                    dtsi_parts.append(f"    // {node.description or node_code}")
                    dtsi_parts.append(f"    {node_code} {{")

                    layers = node.layers
                    if layers:
                        layers_str = " ".join(map(str, layers))
                        dtsi_parts.append(f"        layers = <{layers_str}>;")

                    node_processors = node.input_processors
                    if node_processors:
                        node_processors_str = " ".join(
                            f"{p.code} {' '.join(map(str, p.params))}".strip()
                            for p in node_processors
                        )
                        if node_processors_str:
                            dtsi_parts.append(
                                f"        input-processors = <{node_processors_str}>;"
                            )

                    dtsi_parts.append("    };")

            dtsi_parts.append("};")
            dtsi_parts.append("")
            dtsi_parts.append("")

        return "\n".join(self._indent_array(dtsi_parts))

    def generate_keymap_node(
        self,
        profile: "KeyboardProfile",
        layer_names: list[str],
        layers_data: list[LayerBindings],
    ) -> str:
        """Generate ZMK keymap node string from layer data.

        Args:
            profile: Keyboard profile containing all configuration
            layer_names: List of layer names
            layers_data: List of layer bindings

        Returns:
            DTSI keymap node content as string
        """
        if not layers_data:
            return ""

        logger.info(f"Generating keymap node with {len(layers_data)} layers")

        # Create the keymap opening
        dtsi_parts = ["keymap {", '    compatible = "zmk,keymap";']

        # Process each layer
        for i, (layer_name, layer_bindings) in enumerate(
            zip(layer_names, layers_data, strict=False)
        ):
            # Format layer comment and opening
            define_name = re.sub(r"\W|^(?=\d)", "_", layer_name)
            dtsi_parts.append("")
            dtsi_parts.append(f"    // Layer {i}: {layer_name}")
            dtsi_parts.append(f"    {define_name.lower()}_layer {{")
            dtsi_parts.append(f'        label = "{layer_name}";')
            dtsi_parts.append("        bindings = <")

            # Format layer bindings
            formatted_bindings = []
            for binding in layer_bindings:
                formatted_binding = self._behavior_formatter.format_binding(binding)
                formatted_bindings.append(formatted_binding)

            # Use the provided profile directly
            # Just use a different indentation setting for grid formatting
            # Store original base_indent
            original_base_indent = profile.keyboard_config.keymap.formatting.base_indent
            # Set specific indentation for DTSI output
            profile.keyboard_config.keymap.formatting.base_indent = "            "

            # Format the bindings using the layout generator
            formatted_grid = self._layout_generator.generate_layer_layout(
                formatted_bindings, profile
            )

            # Restore original base_indent
            profile.keyboard_config.keymap.formatting.base_indent = original_base_indent

            # Add the formatted grid
            dtsi_parts.extend(formatted_grid)

            # Add layer closing
            dtsi_parts.append("        >;")
            dtsi_parts.append("    };")

        # Add keymap closing
        dtsi_parts.append("};")

        return "\n".join(dtsi_parts)

    def _indent_array(self, lines: list[str], indent: str = "    ") -> list[str]:
        """Indent all lines in an array with the specified indent string."""
        return [f"{indent}{line}" for line in lines]

    def generate_kconfig_conf(
        self,
        keymap_data: "LayoutData",
        profile: "KeyboardProfile",
    ) -> tuple[str, KConfigSettings]:
        """Generate kconfig content and settings from keymap data.

        Args:
            keymap_data: Keymap data with configuration parameters
            profile: Keyboard profile with kconfig options

        Returns:
            Tuple of (kconfig_content, kconfig_settings)
        """
        logger.info("Generating kconfig configuration")

        kconfig_options = profile.kconfig_options
        user_options: dict[str, str] = {}

        lines = []

        # Extract user config_parameters (kconfig) options from LayoutData
        for opt in keymap_data.config_parameters:
            line = ""
            if opt.param_name in kconfig_options:
                # get the real option name
                name = kconfig_options[opt.param_name].name
                if opt.value == kconfig_options[opt.param_name].default:
                    # check if the user is setting same value as default
                    # in that case, we set it but in comment
                    # that allows the user to switch more easily firmware
                    # without changing the kconfig
                    line = "# "
            else:
                name = opt.param_name
                if not name.startswith("CONFIG_"):
                    name = "CONFIG_" + name

            line += f"{name}={opt.value}"
            lines.append(line)

        # Generate formatted kconfig content
        lines.append("# Generated ZMK configuration")
        lines.append("")

        kconfig_content = "\n".join(lines)
        return kconfig_content, user_options


def create_layout_generator() -> DtsiLayoutGenerator:
    """
    Create a DtsiLayoutGenerator instance.

    Returns:
        DtsiLayoutGenerator instance
    """
    # This factory function is now a bit misleading since DTSIGenerator is also here.
    # For now, it will just create the visual layout generator.
    return DtsiLayoutGenerator()
