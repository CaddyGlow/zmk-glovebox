"""DTSI generation service for creating ZMK device tree files."""

import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional  # UP035: Dict, List

from glovebox.formatters.behavior_formatter import BehaviorFormatterImpl
from glovebox.generators.layout_generator import DtsiLayoutGenerator, LayoutConfig


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile


logger = logging.getLogger(__name__)


class DTSIGenerator:
    """Service for generating DTSI content from JSON data."""

    def __init__(self, behavior_formatter: BehaviorFormatterImpl) -> None:
        """Initialize with behavior formatter dependency.

        Args:
            behavior_formatter: Formatter for converting bindings to DTSI format
        """
        self._behavior_formatter = behavior_formatter
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
        self, profile: "KeyboardProfile", hold_taps_data: list[dict[str, Any]]
    ) -> str:
        """Generate ZMK behaviors node string from hold-tap JSON data.

        Args:
            profile: Keyboard profile containing configuration
            hold_taps_data: List of hold-tap behavior definitions

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
            name = ht.get("name")
            if not name:
                logger.warning("Skipping hold-tap behavior with missing 'name'.")
                continue

            node_name = name[1:] if name.startswith("&") else name
            bindings = ht.get("bindings", [])
            tapping_term = ht.get("tappingTermMs")
            flavor = ht.get("flavor")
            quick_tap = ht.get("quickTapMs")
            require_idle = ht.get("requirePriorIdleMs")
            hold_on_release = ht.get("holdTriggerOnRelease")
            hold_key_positions_indices = ht.get("holdTriggerKeyPositions")

            if len(bindings) != 2:
                logger.warning(
                    f"Behavior '{name}' requires exactly 2 bindings (hold, tap). Found {len(bindings)}. Skipping."
                )
                continue

            # Register the behavior
            self._behavior_formatter._registry.register_behavior(
                name, 2, "user_hold_tap"
            )

            label = ht.get("description", node_name).split("\n")
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
                if isinstance(binding_ref, str):
                    formatted_bindings.append(binding_ref)
                elif isinstance(binding_ref, dict):
                    formatted_bindings.append(
                        self._behavior_formatter.format_binding(binding_ref)
                    )
                else:
                    logger.warning(
                        f"Unexpected binding format in hold-tap '{name}': {binding_ref}. Skipping."
                    )
                    formatted_bindings.append("&error /* Invalid HT Binding */")

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

            if hold_key_positions_indices is not None and isinstance(
                hold_key_positions_indices, list
            ):
                pos_numbers = [str(idx) for idx in hold_key_positions_indices]
                dtsi_parts.append(
                    f"    hold-trigger-key-positions = <{' '.join(pos_numbers)}>;"
                )

            if hold_on_release:
                dtsi_parts.append("    hold-trigger-on-release;")

            if ht.get("retroTap"):
                dtsi_parts.append("    retro-tap;")

            dtsi_parts.append("};")
            dtsi_parts.append("")

        dtsi_parts.pop()  # Remove last blank line
        return "\n".join(self._indent_array(dtsi_parts, " " * 8))

    def generate_macros_dtsi(
        self, profile: "KeyboardProfile", macros_data: list[dict[str, Any]]
    ) -> str:
        """Generate ZMK macros node string from JSON data.

        Args:
            profile: Keyboard profile containing configuration
            macros_data: List of macro definitions

        Returns:
            DTSI macros node content as string
        """
        if not macros_data:
            return ""

        dtsi_parts = [""]

        for macro in macros_data:
            name = macro.get("name")
            if not name:
                logger.warning("Skipping macro with missing 'name'.")
                continue

            node_name = name[1:] if name.startswith("&") else name
            description = macro.get("description", node_name).split("\n")
            description = [f"// {line}" for line in description]

            bindings = macro.get("bindings", [])
            params = macro.get("params", [])
            wait_ms = macro.get("waitMs")
            tap_ms = macro.get("tapMs")

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
            self._behavior_formatter._registry.register_behavior(
                name, int(binding_cells), "user_macro"
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
                bindings_str = "\n                , ".join(
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
        combos_data: list[dict[str, Any]],
        layer_names: list[str],
    ) -> str:
        """Generate ZMK combos node string from JSON data.

        Args:
            profile: Keyboard profile containing configuration
            combos_data: List of combo behavior definitions
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
            name = combo.get("name")
            if not name:
                logger.warning("Skipping combo with missing 'name'.")
                continue

            node_name = re.sub(r"\W|^(?=\d)", "_", name)
            binding_data = combo.get("binding")
            key_positions_indices = combo.get("keyPositions")
            timeout = combo.get("timeoutMs")
            layers_spec = combo.get("layers")

            if not binding_data or not key_positions_indices:
                logger.warning(
                    f"Combo '{name}' is missing binding or keyPositions. Skipping."
                )
                continue

            label = combo.get("description", node_name).split("\n")
            label = "\n".join([f"    // {line}" for line in label])

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
                valid_layer_spec = True
                for layer_id in layers_spec:
                    layer_define = None
                    if isinstance(layer_id, int):
                        layer_define = layer_defines.get(layer_id)
                    elif isinstance(layer_id, str):
                        layer_index = layer_name_to_index.get(layer_id)
                        if layer_index is not None:
                            layer_define = layer_defines.get(layer_index)

                    if layer_define:
                        combo_layer_defines.append(layer_define)
                    else:
                        logger.warning(
                            f"Combo '{name}' specifies unknown layer '{layer_id}'. Ignoring layer spec."
                        )
                        valid_layer_spec = False
                        break

                if valid_layer_spec and combo_layer_defines:
                    dtsi_parts.append(
                        f"        layers = <{' '.join(combo_layer_defines)}>;"
                    )

            dtsi_parts.append("    };")
            dtsi_parts.append("")

        dtsi_parts.pop()  # Remove last blank line
        dtsi_parts.append("};")
        return "\n".join(self._indent_array(dtsi_parts))

    def generate_input_listeners_node(
        self, profile: "KeyboardProfile", input_listeners_data: list[dict[str, Any]]
    ) -> str:
        """Generate input listener nodes string from JSON data.

        Args:
            profile: Keyboard profile containing configuration
            input_listeners_data: List of input listener definitions

        Returns:
            DTSI input listeners node content as string
        """
        if not input_listeners_data:
            return ""

        dtsi_parts = []
        for listener in input_listeners_data:
            listener_code = listener.get("code")
            if not listener_code:
                logger.warning("Skipping input listener with missing 'code'.")
                continue

            dtsi_parts.append(f"{listener_code} {{")

            global_processors = listener.get("inputProcessors", [])
            if global_processors:
                processors_str = " ".join(
                    f"{p.get('code', '')} {' '.join(map(str, p.get('params', [])))}".strip()
                    for p in global_processors
                )
                if processors_str:
                    dtsi_parts.append(f"    input-processors = <{processors_str}>;")

            nodes = listener.get("nodes", [])
            if not nodes:
                logger.warning(
                    f"Input listener '{listener_code}' has no nodes defined."
                )
            else:
                for node in nodes:
                    node_code = node.get("code")
                    if not node_code:
                        logger.warning(
                            f"Skipping node in listener '{listener_code}' with missing 'code'."
                        )
                        continue

                    dtsi_parts.append("")
                    dtsi_parts.append(f"    // {node.get('description', node_code)}")
                    dtsi_parts.append(f"    {node_code} {{")

                    layers = node.get("layers", [])
                    if layers:
                        layers_str = " ".join(map(str, layers))
                        dtsi_parts.append(f"        layers = <{layers_str}>;")

                    node_processors = node.get("inputProcessors", [])
                    if node_processors:
                        node_processors_str = " ".join(
                            f"{p.get('code', '')} {' '.join(map(str, p.get('params', [])))}".strip()
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
        layers_data: list[list[dict[str, Any]]],
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
