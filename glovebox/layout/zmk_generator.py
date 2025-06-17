"""ZMK file content generation for keyboard layouts and behaviors."""

import logging
import re
from collections.abc import Sequence
from typing import TYPE_CHECKING

from glovebox.layout.behavior.formatter import BehaviorFormatterImpl
from glovebox.layout.formatting import GridLayoutFormatter
from glovebox.layout.models import (
    ComboBehavior,
    HoldTapBehavior,
    InputListener,
    LayerBindings,
    MacroBehavior,
    SystemBehavior,
)
from glovebox.layout.utils import generate_kconfig_conf


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile
    from glovebox.layout.models import LayoutData


logger = logging.getLogger(__name__)


class ZmkFileContentGenerator:
    """Generator for complete ZMK file content from layout data."""

    def __init__(self, behavior_formatter: BehaviorFormatterImpl) -> None:
        """Initialize with behavior formatter dependency.

        Args:
            behavior_formatter: Formatter for converting bindings to DTSI format
        """
        self._behavior_formatter = behavior_formatter
        self._behavior_registry = behavior_formatter._registry
        self._layout_formatter = GridLayoutFormatter()

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
        layer_define_pattern = profile.keyboard_config.zmk.patterns.layer_define
        for i, name in enumerate(layer_names):
            define_name = re.sub(r"\W|^(?=\d)", "_", name)
            define_line = layer_define_pattern.format(
                layer_name=define_name, layer_index=i
            )
            defines.append(define_line)
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

            required_bindings = (
                profile.keyboard_config.zmk.validation_limits.required_holdtap_bindings
            )
            if len(bindings) != required_bindings:
                logger.warning(
                    f"Behavior '{name}' requires exactly {required_bindings} bindings (hold, tap). Found {len(bindings)}. Skipping."
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
            compatible_string = profile.keyboard_config.zmk.compatible_strings.hold_tap
            dtsi_parts.append(f'    compatible = "{compatible_string}";')
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

            if len(formatted_bindings) == required_bindings:
                if required_bindings == 2:
                    dtsi_parts.append(
                        f"    bindings = <{formatted_bindings[0]}>, <{formatted_bindings[1]}>;"
                    )
                else:
                    # Handle other cases if required_bindings is configurable to other values
                    bindings_str = ", ".join(f"<{b}>" for b in formatted_bindings)
                    dtsi_parts.append(f"    bindings = {bindings_str};")
            else:
                # Generate error placeholders based on required count
                error_bindings = ", ".join("<&error>" for _ in range(required_bindings))
                dtsi_parts.append(f"    bindings = {error_bindings};")

            if flavor is not None:
                allowed_flavors = profile.keyboard_config.zmk.hold_tap_flavors
                if flavor in allowed_flavors:
                    dtsi_parts.append(f'    flavor = "{flavor}";')
                else:
                    logger.warning(
                        f"Invalid flavor '{flavor}' for behavior '{name}'. Allowed: {allowed_flavors}. Omitting."
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

            # ZMK macro binding specification only supports #binding-cells = <0>
            # Parameters are handled at keymap invocation level, not macro definition level
            compatible_strings = profile.keyboard_config.zmk.compatible_strings
            compatible = compatible_strings.macro
            binding_cells = "0"
            
            # NOTE: Previous logic attempted to set binding-cells based on macro params,
            # but ZMK binding spec (zmk,behavior-macro.yaml) includes zero_param.yaml
            # which enforces #binding-cells = <0> regardless of conceptual parameters.
            # Keeping old logic commented for reference in case binding spec changes:
            #
            # if not params:
            #     compatible = compatible_strings.macro
            #     binding_cells = "0"
            # elif len(params) == 1:
            #     compatible = compatible_strings.macro  
            #     binding_cells = "1"
            # elif len(params) == 2:
            #     compatible = compatible_strings.macro
            #     binding_cells = "2"
            # else:
            #     max_params = profile.keyboard_config.zmk.validation_limits.max_macro_params
            #     logger.warning(f"Macro '{name}' has {len(params)} params, not supported. Max: {max_params}.")
            #     continue

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
        combos_compatible = profile.keyboard_config.zmk.compatible_strings.combos
        dtsi_parts.append(f'    compatible = "{combos_compatible}";')

        layer_name_to_index = {name: i for i, name in enumerate(layer_names)}
        layer_define_pattern = profile.keyboard_config.zmk.patterns.layer_define
        sanitize_pattern = profile.keyboard_config.zmk.patterns.node_name_sanitize
        layer_defines = {
            i: layer_define_pattern.format(
                layer_name=re.sub(sanitize_pattern, "_", name.upper()),
                layer_index=i
            )
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
        keymap_compatible = profile.keyboard_config.zmk.compatible_strings.keymap
        dtsi_parts = ["keymap {", f'    compatible = "{keymap_compatible}";']

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

            # Format the bindings using the layout formatter with custom indent for DTSI
            formatted_grid = self._layout_formatter.generate_layer_layout(
                formatted_bindings, profile, base_indent="            "
            )

            # Add the formatted grid
            dtsi_parts.extend(formatted_grid)

            # Add layer closing
            dtsi_parts.append("        >;")
            dtsi_parts.append("    };")

        # Add keymap closing
        dtsi_parts.append("};")

        return "\n".join(dtsi_parts)

    def generate_kconfig_conf(
        self, keymap_data: "LayoutData", profile: "KeyboardProfile"
    ) -> tuple[str, dict[str, str]]:
        """Generate kconfig content and settings from keymap data.

        Args:
            keymap_data: Keymap data with configuration parameters
            profile: Keyboard profile with kconfig options

        Returns:
            Tuple of (kconfig_content, kconfig_settings)
        """
        return generate_kconfig_conf(keymap_data, profile)

    def _indent_array(self, lines: list[str], indent: str = "    ") -> list[str]:
        """Indent all lines in an array with the specified indent string."""
        return [f"{indent}{line}" for line in lines]


def create_zmk_file_generator(
    behavior_formatter: BehaviorFormatterImpl,
) -> ZmkFileContentGenerator:
    """Create a new ZmkFileContentGenerator instance.

    Args:
        behavior_formatter: Behavior formatter for DTSI generation

    Returns:
        Configured ZmkFileContentGenerator instance
    """
    return ZmkFileContentGenerator(behavior_formatter)
