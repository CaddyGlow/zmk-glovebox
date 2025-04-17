import re
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from .layout import LayoutConfig, format_layer_bindings_grid

# Import the registration function and formatting function
from .behaviors import format_binding, register_behavior

logger = logging.getLogger(__name__)

# Keycode and Behavior Mapping
KEYCODE_MAP = {}


# String Generation Functions
def generate_layer_defines(layer_names: List[str]) -> str:
    """Generates the #define statements for layers."""
    defines = []
    for i, name in enumerate(layer_names):
        define_name = re.sub(r"\W|^(?=\d)", "_", name)  # .upper()
        defines.append(f"#define LAYER_{define_name} {i}")
    return "\n".join(defines)


def generate_keymap_node(
    layer_names: List[str], layers_data: List[List[Dict]], config: LayoutConfig
) -> str:
    """Generates the ZMK keymap node string."""
    keymap_parts = []
    keymap_parts.append("keymap {")
    keymap_parts.append('    compatible = "zmk,keymap";')
    keymap_parts.append("")
    keymap_parts.append("")

    for i, layer_keys_data in enumerate(layers_data):
        if i >= len(layer_names):  # Safety check
            logger.warning(
                f"Layer data index {i} out of bounds for layer_names length {len(layer_names)}"
            )
            continue

        layer_name = layer_names[i]
        node_name = re.sub(r"\W|^(?=\d)", "_", layer_name)

        keymap_parts.append(f"    layer_{node_name} {{")
        keymap_parts.append("        bindings = <")

        # 1. Format bindings using Behavior classes (Phase 1)
        # Padding handled within format_layer_bindings_grid now based on config.total_keys

        # 2. Arrange formatted bindings using LayoutConfig

        # Format all bindings
        formatted_bindings = [format_binding(key_data) for key_data in layer_keys_data]

        # --- Restore Grid Formatting ---
        grid_lines = format_layer_bindings_grid(formatted_bindings, config)
        keymap_parts.extend(grid_lines)
        # --- End Restore ---

        keymap_parts.append("        >;")  # Keep the closing bracket
        keymap_parts.append("    };")
        keymap_parts.append("")

    keymap_parts.append("};")
    return "\n".join(indent_array(keymap_parts))


def generate_behaviors_dtsi(
    hold_taps_data: List[Dict], key_position_map: Dict[int, str]
) -> str:
    """Generates the ZMK behaviors node string from hold-tap JSON data."""
    if not hold_taps_data:
        return ""

    dtsi_parts = []

    for ht in hold_taps_data:
        name = ht.get("name")
        if not name:
            logger.warning("Skipping hold-tap behavior with missing 'name'.")
            continue

        # Ensure name starts with '&' for referencing, remove it for node definition
        node_name = name[1:] if name.startswith("&") else name

        bindings = ht.get(
            "bindings", []
        )  # Expected: ["&hold_behavior", "&tap_behavior"]
        tapping_term = ht.get("tappingTermMs")
        flavor = ht.get("flavor")
        quick_tap = ht.get("quickTapMs")
        require_idle = ht.get("requirePriorIdleMs")
        hold_on_release = ht.get("holdTriggerOnRelease")  # Boolean
        hold_key_positions_indices = ht.get(
            "holdTriggerKeyPositions"
        )  # List of numbers

        if len(bindings) != 2:
            logger.warning(
                f"Behavior '{name}' requires exactly 2 bindings (hold, tap). Found {len(bindings)}. Skipping."
            )
            continue

        # escaped_label = escape_string(label)  # Escape quotes for label
        # Use description for label, fallback to node_name
        label = ht.get("description", node_name).split("\n")
        label = [f"// {line}" for line in label]

        # Assume hold-tap behavior type based on structure

        # Register the hold-tap behavior itself. It always takes 2 params in the keymap.
        register_behavior(name, 2, "user_hold_tap")

        dtsi_parts.extend(label)
        dtsi_parts.append(f"{node_name}: {node_name} {{")
        dtsi_parts.append('    compatible = "zmk,behavior-hold-tap";')
        # dtsi_parts.append(f'        label = "{escaped_label}";')
        dtsi_parts.append("    #binding-cells = <2>;")  # This defines the node itself

        # Optional properties
        if tapping_term is not None:
            dtsi_parts.append(f"    tapping-term-ms = <{tapping_term}>;")

        # Format bindings - Treat elements in the JSON 'bindings' array as behavior references
        # Example JSON: "bindings": ["&kp", "&caps_word"] -> DTSI: bindings = <&kp>, <&caps_word>;
        # Example JSON: "bindings": [{"value": "&kp", "params": ["A"]}, {"value": "&macro_name", "params": []}] -> DTSI: bindings = <&kp A>, <&macro_name>;
        formatted_bindings = []
        for binding_ref in bindings:
            if isinstance(binding_ref, str):  # Simple reference like "&kp"
                # Basic formatting for simple string references, assuming they are valid behavior names
                # Might need enhancement if params are ever passed with simple refs this way
                formatted_bindings.append(binding_ref)
            elif isinstance(binding_ref, dict):  # Complex binding object
                formatted_bindings.append(format_binding(binding_ref))
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
            # This case should be caught earlier, but as a safeguard:
            dtsi_parts.append("    bindings = <&error>, <&error>;")

        if flavor is not None:
            # Ensure flavor is one of the allowed ZMK values
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
            # Use raw numbers directly as per ZMK standard
            pos_numbers = [str(idx) for idx in hold_key_positions_indices]
            dtsi_parts.append(
                f"    hold-trigger-key-positions = <{' '.join(pos_numbers)}>;"
            )

        if hold_on_release:  # Check if True
            dtsi_parts.append("    hold-trigger-on-release;")

        # Add retro-tap property if present and true
        if ht.get("retroTap"):
            dtsi_parts.append("    retro-tap;")

        dtsi_parts.append("};")
        dtsi_parts.append("")  # Blank line between behaviors

    dtsi_parts.pop()  # remove last blank line
    return "\n".join(indent_array(dtsi_parts, " " * 8))


def indent_array(lines: List[str], indent: str = "    ") -> List[str]:
    """
    Indents all lines in an array with the specified indent string.

    Args:
        lines: List of strings to indent
        indent: The string to use for indentation (default: 4 spaces)

    Returns:
        A new list with all lines indented
    """
    return [f"{indent}{line}" for line in lines]


def escape_string(input: str) -> str:
    input_escape = ""
    if isinstance(input, str):
        input_escape = json.dumps(input)
    else:
        logger.warning("escape_string input is not a string", input)

    if input_escape.startswith('"') and input_escape.endswith('"'):
        input_escape = input_escape[1:-1]  # Remove quotes

    return input_escape


def generate_macros_dtsi(macros_data: List[Dict]) -> str:
    """Generates the ZMK macros node string from JSON data."""
    if not macros_data:
        return ""

    dtsi_parts = [""]

    for macro in macros_data:
        name = macro.get("name")
        if not name:
            logger.warning("Skipping macro with missing 'name'.")
            continue

        # Ensure name starts with '&' for referencing, remove it for node definition
        node_name = name[1:] if name.startswith("&") else name

        # Use description for comment, fallback to node_name
        description = macro.get("description", node_name).split("\n")
        description = [f"// {line}" for line in description]

        # Get bindings and parameters
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

        # Register the macro behavior before generating its node
        register_behavior(name, int(binding_cells), "user_macro")

        # Start building the macro node
        macro_parts = []

        if description:
            macro_parts.extend(description)
        macro_parts.append(f"{node_name}: {node_name} {{")
        # --- Property Order Must Match wanted.keymap ---
        macro_parts.append(f'    label = "{name.upper()}";')  # Get label
        macro_parts.append(
            f'    compatible = "{compatible}";'
        )  # Get compatible based on params
        macro_parts.append(f"    #binding-cells = <{binding_cells}>;")  # Get cells
        if tap_ms is not None:
            macro_parts.append(f"    tap-ms = <{tap_ms}>;")
        if wait_ms is not None:
            macro_parts.append(f"    wait-ms = <{wait_ms}>;")
        if bindings:
            bindings_str = "\n                , ".join(
                f"<{format_binding(b)}>"
                for b in bindings  # Use refactored format_binding
            )
            macro_parts.append(f"    bindings = {bindings_str};")
        # --- End Property Order ---
        macro_parts.append("};")
        dtsi_parts.extend(
            indent_array(macro_parts, "        ")
        )  # Adjust indent level as needed
        dtsi_parts.append("")  # Blank line separator? Check wanted.keymap

    # dtsi_parts.append("};")
    dtsi_parts.pop()  # Remove last blank line
    return "\n".join(dtsi_parts)  # Remove last blank line


def generate_combos_dtsi(
    combos_data: List[Dict], key_position_map: Dict[int, str], layer_names: List[str]
) -> str:
    """Generates the ZMK combos node string from JSON data."""
    if not combos_data:
        return ""

    dtsi_parts = ["combos {"]
    dtsi_parts.append('    compatible = "zmk,combos";')

    # Create a map from layer name to its index for layer filtering
    layer_name_to_index = {name: i for i, name in enumerate(layer_names)}
    # Generate layer defines used in combos (e.g., LAYER_QWERTY)
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

        node_name = re.sub(r"\W|^(?=\d)", "_", name)  # Sanitize name for DTSI node
        binding_data = combo.get("binding")  # This is a binding object
        key_positions_indices = combo.get("keyPositions")  # List of numbers
        timeout = combo.get("timeoutMs")
        # Layers can be indices or names in JSON? Assume indices for now. [-1] means all.
        layers_spec = combo.get(
            "layers"
        )  # e.g., [-1] or [0, 2] or ["QWERTY", "NUMPAD"]

        if not binding_data or not key_positions_indices:
            logger.warning(
                f"Combo '{name}' is missing binding or keyPositions. Skipping."
            )
            continue

        # label_escape = escape_string(label)  # Escape quotes for label
        label = combo.get("description", node_name).split("\n")
        label = "\n".join([f"    // {line}" for line in label])

        dtsi_parts.append(f"{label}")
        dtsi_parts.append(f"    combo_{node_name} {{")
        # dtsi_parts.append(
        #     f'        label = "{label_escape}";'  # Use json.dumps to escape quotes
        # )  # Escape quotes

        if timeout is not None:
            dtsi_parts.append(f"        timeout-ms = <{timeout}>;")

        # Format key positions using the map
        key_pos_defines = [
            key_position_map.get(idx, f"{idx}") for idx in key_positions_indices
        ]
        dtsi_parts.append(f"        key-positions = <{' '.join(key_pos_defines)}>;")

        # Format binding using the main recursive function
        formatted_binding = format_binding(binding_data)
        dtsi_parts.append(f"        bindings = <{formatted_binding}>;")

        # Format layers (omit if [-1], empty, or null)
        if layers_spec and layers_spec != [-1]:
            combo_layer_defines = []
            valid_layer_spec = True
            for layer_id in layers_spec:
                layer_define = None
                if isinstance(layer_id, int):
                    # If spec is index
                    layer_define = layer_defines.get(layer_id)
                elif isinstance(layer_id, str):
                    # If spec is name
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
                    break  # Stop processing layers for this combo if one is invalid

            if valid_layer_spec and combo_layer_defines:
                dtsi_parts.append(
                    f"        layers = <{' '.join(combo_layer_defines)}>;"
                )

        dtsi_parts.append("    };")
        dtsi_parts.append("")  # Blank line between combos

    dtsi_parts.pop()  # Remove last blank line
    dtsi_parts.append("};")
    return "\n".join(indent_array(dtsi_parts))


def generate_input_listeners_node(input_listeners_data: List[Dict]) -> str:
    """Generates the input listener nodes string from JSON data."""
    if not input_listeners_data:
        return ""

    dtsi_parts = []
    for listener in input_listeners_data:
        listener_code = listener.get("code")
        if not listener_code:
            logger.warning("Skipping input listener with missing 'code'.")
            continue

        dtsi_parts.append(f"{listener_code} {{")

        # Global input processors for the listener (if any)
        global_processors = listener.get("inputProcessors", [])
        if global_processors:
            processors_str = " ".join(
                f"{p.get('code', '')} {' '.join(map(str, p.get('params', [])))}".strip()
                for p in global_processors
            )
            if processors_str:
                dtsi_parts.append(f"    input-processors = <{processors_str}>;")

        # Listener nodes
        nodes = listener.get("nodes", [])
        if not nodes:
            logger.warning(f"Input listener '{listener_code}' has no nodes defined.")
        else:
            for node in nodes:
                node_code = node.get("code")
                if not node_code:
                    logger.warning(
                        f"Skipping node in listener '{listener_code}' with missing 'code'."
                    )
                    continue

                dtsi_parts.append("")  # Blank line before node
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

                dtsi_parts.append("    };")  # Close node

        dtsi_parts.append("};")  # Close listener
        dtsi_parts.append("")  # Blank line after listener
        dtsi_parts.append("")  # Blank line to match the moergod style

    return "\n".join(indent_array(dtsi_parts))


def generate_kconfig_conf(
    json_data: Dict[str, Any], kconfig_map: Dict[str, Dict[str, str]]
) -> str:
    """
    Generates Kconfig (.conf) content using an external mapping file, including descriptions.

    Args:
        json_data: The loaded keymap JSON data.
        kconfig_map: The loaded mapping dictionary {json_param: {"kconfig_name": ..., "type": ..., "description": ...}}.

    Returns:
        The generated .conf string content.
    """
    conf_lines = [
        "# Kconfig settings generated by Glovebox",
        f"# Generated on: {datetime.now().isoformat()}",
        "# Based on keymap.json config_parameters",
        "",
    ]
    config_params = json_data.get("config_parameters", [])

    if not config_params:
        conf_lines.append("# No config_parameters found in JSON.")
        return "\n".join(conf_lines) + "\n"

    processed_kconfig_names = set()

    for param in config_params:
        param_name = param.get("paramName")
        param_value_orig = param.get("value")
        param_value_str = str(param_value_orig).lower()

        if not param_name:
            continue

        if param_name.startswith("CONFIG_"):
            kconfig_name = param_name
            mapping_info = {}
        else:
            mapping_info = kconfig_map.get(param_name, {})
            kconfig_name = mapping_info.get("kconfig_name", f"CONFIG_{param_name}")
            if "kconfig_name" not in mapping_info:
                f"No Kconfig mapping found for paramName: {param_name}. Fallback to {kconfig_name}."
                continue

        expected_type = mapping_info.get("type", "unknown")
        default_value = mapping_info.get("type", None)

        if kconfig_name in processed_kconfig_names:
            logger.warning(
                f"Duplicate Kconfig entry for '{kconfig_name}' (from '{param_name}'). Skipping."
            )
            continue

        line = (
            f"# {kconfig_name} is not set (JSON value: '{param_value_orig}')"  # Default
        )

        if expected_type == "bool":
            if param_value_str == "y":
                line = f"{kconfig_name}=y"
            elif param_value_str == "n":
                line = f"{kconfig_name}=n"
            else:
                logger.warning(
                    f"Invalid boolean value for {param_name} ('{param_value_orig}'). Expected 'y' or 'n'. Commenting out {kconfig_name}."
                )
        elif expected_type == "int":
            try:
                int_val = int(float(param_value_orig))
                line = f"{kconfig_name}={int_val}"
            except (ValueError, TypeError, OverflowError):
                logger.warning(
                    f"Invalid integer value for {param_name} ('{param_value_orig}'). Commenting out {kconfig_name}."
                )
        elif expected_type == "string":
            line = f'{kconfig_name}="{str(param_value_orig)}"'
        else:  # Unknown type
            logger.warning(
                f"Unknown Kconfig type '{expected_type}' for {kconfig_name}. Treating as string."
            )
            line = f"{kconfig_name}={param_value_orig}"

        conf_lines.append(line)
        conf_lines.append("")  # Add a blank line for readability after each entry
        processed_kconfig_names.add(kconfig_name)

    return "\n".join(conf_lines) + "\n"


def build_dtsi_from_json(
    json_data: Dict[str, Any],
    template_dir: Path,
    template_name: str,
    layout_config: LayoutConfig,
    system_behaviors_content: str = "", # Add back the argument
    key_position_defines_content: str = "",
) -> str:
    """
    Builds the .keymap or other DTSI content using Jinja2, incorporating generated nodes.

    Args:
        json_data: The loaded keymap JSON data.
        template_dir: The directory containing the Jinja2 template.
        template_name: The name of the Jinja2 template file.
        system_behaviors_content: The content of the system_behaviors.dts file.
        key_position_defines_content: The content of the key_position.h file.
        # input_listeners_content is removed

    Returns:
        The rendered DTSI content as a string.
    """
    try:
        env = Environment(
            loader=FileSystemLoader(template_dir), trim_blocks=True, lstrip_blocks=True
        )
        template = env.get_template(template_name)
    except TemplateNotFound:
        logger.error(f"Template '{template_name}' not found in '{template_dir}'")
        raise
    except Exception as e:
        logger.error(f"Error setting up Jinja2 environment: {e}")
        raise

    # Prepare data for generation
    layer_names = json_data.get("layer_names", [])
    layers_data = json_data.get("layers", [])
    hold_taps_data = json_data.get("holdTaps", [])  # Use "holdTaps" from JSON
    combos_data = json_data.get("combos", [])
    input_listeners_data = json_data.get("inputListeners", [])
    config_params_dict = {
        p["paramName"]: p.get("value", "")
        for p in json_data.get("config_parameters", [])
    }

    # Parse key position defines - Already done in LayoutConfig

    # --- Generate DTSI components ---
    # IMPORTANT: Generate macros and behaviors FIRST to populate the registry
    # before the keymap node uses format_binding.

    # Generate macros (and register them)
    macros_data = json_data.get("macros", [])
    macros_dtsi_str = generate_macros_dtsi(macros_data)

    # Generate behaviors from holdTaps (and register them)
    behaviors_dtsi_str = generate_behaviors_dtsi(
        hold_taps_data, layout_config.key_position_map
    )

    # Now generate other components that might use the registry
    layer_defines_str = generate_layer_defines(layer_names)
    keymap_node_str = (
        generate_keymap_node(layer_names, layers_data, layout_config)
        if layer_names and layers_data
        else ""  # Return empty string if no layers, avoid logging warning here
    )
    if not keymap_node_str:
        logger.warning("Keymap node not generated (no layers found in JSON)")

    # Generate combos
    combos_dtsi_str = generate_combos_dtsi(
        combos_data, layout_config.key_position_map, layer_names
    )

    # Generate input listeners
    input_listeners_dtsi_str = generate_input_listeners_node(input_listeners_data)

    # --- Build Jinja context ---
    context = {
        "layer_defines": layer_defines_str,
        "keymap_node": keymap_node_str,
        "behaviors_dtsi": behaviors_dtsi_str,
        "combos_dtsi": combos_dtsi_str,
        "input_listeners_dtsi": input_listeners_dtsi_str,
        "macros_dtsi": macros_dtsi_str
        or json_data.get(
            "custom_defined_macros", ""
        ),  # Use generated macros or fallback to custom field
        "custom_defined_behaviors": json_data.get(
            "custom_defined_behaviors", ""
        ),  # Keep for other custom behaviors
        "custom_devicetree": json_data.get("custom_devicetree", ""),
        "config_params": config_params_dict,
        "system_behaviors": system_behaviors_content, # Add back to context
        "key_position_defines": key_position_defines_content,  # Pass through included content
        # Add other json data if needed by the template
        "json_data": json_data,
    }

    # Render template
    try:
        rendered_content = template.render(context)
        # Post-processing: Add header comment
        header = f"// Generated by Glovebox from JSON on {datetime.now().isoformat()}\n"
        return header + rendered_content
    except Exception as e:
        logger.error(f"Error rendering Jinja2 template: {e}")
        raise
