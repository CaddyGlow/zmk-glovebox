import json
import re


def format_glove80_layout(layout_data, layer_name=None):
    """
    Format a specific layer of the Glove80 keyboard layout in a visual representation.

    Args:
        layout_data: The complete layout data structure
        layer_name: The name of the layer to display (if None, displays the first layer)

    Returns:
        A string with the formatted layout
    """
    # Find the requested layer
    layer = None
    if layer_name:
        for l in layout_data["layers"]:
            if l["name"].lower() == layer_name.lower():
                layer = l
                break
    else:
        layer = layout_data["layers"][0]

    if not layer:
        return f"Layer '{layer_name}' not found."

    # Glove80 has 80 keys in 6 rows
    # Create a mapping from key index to position in the grid
    # This mapping is based on the physical layout of the Glove80
    # fmt: off
    key_mapping = [
        # Row 1 (top row) - 10 keys
        [0, 1, 2, 3, 4, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, 5, 6, 7, 8, 9],
        # Row 2 - 12 keys 
        [10, 11, 12, 13, 14, 15, None, None, None, None, None, None, None, None, None, None, 16, 17, 18, 19, 20, 21],
        # Row 3 - 12 keys
        [22, 23, 24, 25, 26, 27, None, None, None, None, None, None, None, None, None, None, 28, 29, 30, 31, 32, 33],
        # Row 4 - 12 keys
        [34, 35, 36, 37, 38, 39, None, None, None, None, None, None, None, None, None, None, 40, 41, 42, 43, 44, 45],
        # Row 5 - 18 keys (including thumb keys)
        [46, 47, 48, 49, 50, 51, 52, 53, 54, None, None, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67],
        # Row 6 (bottom row) - 16 keys (including thumb keys)
        [68, 69, 70, 71, 72, None, 73, 74, 75, None, None, 76, 77, 78, None, 79]
    ]
    # fmt: on

    # Helper function to format a key
    def format_key(key, max_len=8):
        if key is None:
            return " " * max_len

        display = key.get("displayName", "")
        # Truncate long display names
        if len(display) > max_len:
            display = display[: max_len - 1] + "~"
        # Center and pad the display name
        return display.center(max_len)

    # Build the visual representation
    output = []
    output.append(f"\nLayer: {layer['name']}\n")

    for row_mapping in key_mapping:
        row_keys = []
        for key_idx in row_mapping:
            if key_idx is None:
                row_keys.append(None)
            else:
                if key_idx < len(layer["keys"]):
                    row_keys.append(layer["keys"][key_idx])
                else:
                    row_keys.append(None)

        row_text = ""
        for key in row_keys:
            row_text += format_key(key)

        output.append(row_text)

    return "\n".join(output)


def print_glove80_macro_summary(layout_data):
    """
    Print a summary of macros in the layout data
    """
    if "macros" not in layout_data or not layout_data["macros"]:
        return "No macros found."

    output = []
    output.append("\nMacros Summary:")

    for idx, macro in enumerate(layout_data["macros"], 1):
        name = macro.get("name", "Unnamed")
        definition = macro.get("definition", "")
        # Truncate long definitions
        if len(definition) > 60:
            definition = definition[:57] + "..."

        output.append(f"{idx}. {name}: {definition}")

    return "\n".join(output)


def print_glove80_combo_summary(layout_data):
    """
    Print a summary of combos in the layout data
    """
    if "combos" not in layout_data or not layout_data["combos"]:
        return "No combos found."

    output = []
    output.append("\nCombos Summary:")

    for idx, combo in enumerate(layout_data["combos"], 1):
        name = combo.get("name", "Unnamed")
        keys = ", ".join(combo.get("keyPositions", []))
        binding = combo.get("binding", "")
        layers = ", ".join(combo.get("layers", []))

        output.append(
            f"{idx}. {name}: Keys [{keys}] → {binding} (Layers: {layers or 'All'})"
        )

    return "\n".join(output)


def print_glove80_layout_summary(layout_data):
    """
    Print a summary of the entire keyboard layout
    """
    output = []
    output.append("\nGlove80 Keyboard Layout Summary")
    output.append("=" * 50)

    # Layers summary
    output.append("\nLayers:")
    for idx, layer in enumerate(layout_data.get("layers", []), 0):
        output.append(f"{idx}. {layer['name']}")

    # Add macro summary
    output.append(print_glove80_macro_summary(layout_data))

    # Add combo summary
    output.append(print_glove80_combo_summary(layout_data))

    # RGB settings summary if available
    if "rgbSettings" in layout_data and layout_data["rgbSettings"]:
        output.append("\nRGB Settings:")
        rgb = layout_data["rgbSettings"]

        if "experimentalRgbLayer" in rgb:
            output.append(
                f"- Experimental RGB Layer: {'Enabled' if rgb['experimentalRgbLayer'] else 'Disabled'}"
            )

        if "underglowAutoOff" in rgb:
            output.append(
                f"- Underglow Auto-Off: {'Enabled' if rgb['underglowAutoOff'] else 'Disabled'}"
            )

        if "colorDefinitions" in rgb:
            output.append(f"- Custom Colors: {len(rgb['colorDefinitions'])}")

        if "layerConfigurations" in rgb:
            output.append(
                f"- RGB Layer Configurations: {len(rgb['layerConfigurations'])}"
            )

    return "\n".join(output)


# Example usage:
# print(format_glove80_layout(layout_data, "QWERTY"))
# print(print_glove80_layout_summary(layout_data))


def extract_macros(dtsi_content):
    """Extract macro definitions from dtsi file with complete content"""
    macros = []

    # First try to extract the complete ZMK_MACRO blocks
    macro_blocks = re.finditer(
        r"ZMK_MACRO\(([\w_]+),\s*([^)]*?\);)\s*\)", dtsi_content, re.DOTALL
    )

    for match in macro_blocks:
        macro_name = match.group(1)
        macro_definition = match.group(2).strip()
        macros.append({"name": macro_name, "definition": macro_definition})

    # Second approach for nested parentheses
    start_pattern = r"ZMK_MACRO\(([\w_]+),"
    for match in re.finditer(start_pattern, dtsi_content):
        macro_name = match.group(1)

        # Skip if we already found this macro
        if any(m["name"] == macro_name for m in macros):
            continue

        # Find the closing parenthesis by counting open/close
        start_pos = match.end()
        nesting_level = 1  # We're already inside one level
        body_start = start_pos
        body_end = start_pos

        for i in range(start_pos, len(dtsi_content)):
            if dtsi_content[i] == "(":
                nesting_level += 1
            elif dtsi_content[i] == ")":
                nesting_level -= 1

            if nesting_level == 0:  # Found the matching closing parenthesis
                body_end = i
                break

        if body_end > body_start:
            macro_definition = dtsi_content[body_start:body_end].strip()
            macros.append({"name": macro_name, "definition": macro_definition})

    return macros


def extract_behaviors(dtsi_content):
    """Extract behavior definitions from dtsi file"""
    # Find the behaviors section
    behaviors_section_match = re.search(
        r"behaviors\s*{([^}]+)}", dtsi_content, re.DOTALL
    )
    if not behaviors_section_match:
        return []

    behaviors_section = behaviors_section_match.group(1)

    # Extract individual behavior blocks - improved regex
    behavior_blocks = re.findall(
        r"(\w+(?:[-_]\w+)*)\s*:\s*[\w-]+\s*{([^{]*(?:{[^}]*}[^{]*)*)}",
        behaviors_section,
        re.DOTALL,
    )
    behaviors = []

    for name, body in behavior_blocks:
        # Extract behavior type
        type_match = re.search(
            r":\s*([\w-]+)\s*{", behaviors_section[behaviors_section.find(name) :]
        )
        type_name = type_match.group(1) if type_match else ""

        # Extract common behavior properties
        compatible_match = re.search(r'compatible\s*=\s*"([^"]+)"', body)
        binding_cells_match = re.search(r"#binding-cells\s*=\s*<([^>]+)>", body)
        bindings_match = re.search(r"bindings\s*=\s*<([^>]+)>", body)

        behavior = {
            "name": name,
            "type": type_name,
            "compatible": compatible_match.group(1) if compatible_match else "",
            "binding_cells": binding_cells_match.group(1)
            if binding_cells_match
            else "",
            "bindings": bindings_match.group(1).strip() if bindings_match else "",
            "properties": {},
        }

        # Extract all other properties
        property_regex = r"(\w+(?:[-]\w+)*)\s*=\s*<([^>]+)>"
        for prop_match in re.finditer(property_regex, body):
            prop_name = prop_match.group(1)
            prop_value = prop_match.group(2).strip()
            if prop_name not in ["compatible", "bindings", "#binding-cells"]:
                behavior["properties"][prop_name] = prop_value

        # Extract boolean properties
        bool_props = ["quick-release", "ignore-modifiers", "hold-trigger-on-release"]
        for prop in bool_props:
            if prop in body:
                behavior["properties"][prop] = True

        behaviors.append(behavior)

    return behaviors


def extract_combos(dtsi_content):
    """Extract combo definitions from dtsi file"""
    combo_section_match = re.search(r"combos\s*{([^}]+)}", dtsi_content, re.DOTALL)
    if not combo_section_match:
        return []

    combo_section = combo_section_match.group(1)
    combo_regex = r"combo_([^\s{]+)\s*{([^}]+)}"
    combos = []

    for match in re.finditer(combo_regex, combo_section):
        name = match.group(1)
        body = match.group(2)

        positions_match = re.search(r"key-positions\s*=\s*<([^>]+)>", body)
        bindings_match = re.search(r"bindings\s*=\s*<([^>]+)>", body)
        layers_match = re.search(r"layers\s*=\s*<([^>]+)>", body)
        timeout_match = re.search(r"timeout-ms\s*=\s*<([^>]+)>", body)

        combos.append(
            {
                "name": name,
                "keyPositions": positions_match.group(1).split()
                if positions_match
                else [],
                "binding": bindings_match.group(1).strip() if bindings_match else "",
                "layers": layers_match.group(1).split() if layers_match else [],
                "timeout": timeout_match.group(1) if timeout_match else None,
            }
        )

    return combos


def extract_layer_switches(keymap_data):
    """Extract layer switching mechanisms"""
    layer_switches = []

    for layer_index, layer in enumerate(keymap_data["layers"]):
        for key_index, key in enumerate(layer):
            layer_switch_mechanisms = ["&mo", "&to", "&tog", "&lt", "&lower", "&raise"]

            if key["value"] in layer_switch_mechanisms or (
                key["value"] == "Custom"
                and key["params"]
                and isinstance(key["params"][0]["value"], str)
                and any(
                    term in key["params"][0]["value"].lower()
                    for term in ["layer", "thumb", "crumb", "space", "stumb"]
                )
            ):
                target_layer = ""

                if key["params"]:
                    param = key["params"][0]["value"]
                    if isinstance(param, int):
                        target_layer = (
                            keymap_data["layer_names"][param]
                            if param < len(keymap_data["layer_names"])
                            else str(param)
                        )
                    elif isinstance(param, str) and "LAYER_" in param:
                        target_layer = param.replace("LAYER_", "")

                layer_switches.append(
                    {
                        "sourceLayerIndex": layer_index,
                        "sourceLayerName": keymap_data["layer_names"][layer_index],
                        "keyIndex": key_index,
                        "mechanism": key["value"],
                        "targetLayer": target_layer,
                        "description": get_layer_switch_description(key),
                    }
                )

    return layer_switches


def extract_rgb_settings(device_dtsi_content):
    """Extract RGB settings and configuration from device.dtsi"""
    rgb_settings = {}

    # Extract RGB color definitions
    color_defs = {}
    color_regex = r"#define\s+RGB_(\w+)\s+0x([0-9A-Fa-f]+)\s+//\s+#([0-9A-Fa-f]+)"
    for match in re.finditer(color_regex, device_dtsi_content):
        color_name = match.group(1)
        hex_code = match.group(3)
        color_defs[color_name] = f"#{hex_code}"

    rgb_settings["colorDefinitions"] = color_defs

    # Extract layer RGB configurations
    layer_configs = []
    layer_regex = r"(\w+)\s+{([^}]+)layer-id\s*=\s*<([^>]+)>"
    for match in re.finditer(layer_regex, device_dtsi_content, re.DOTALL):
        layer_name = match.group(1)
        layer_content = match.group(2)
        layer_id = match.group(3).strip()

        # Extract the bindings matrix (if present)
        bindings_match = re.search(
            r"bindings\s*=\s*<([^>]+)>", layer_content, re.DOTALL
        )
        bindings = bindings_match.group(1).strip() if bindings_match else ""

        # Parse the bindings into a grid
        if bindings:
            rows = []
            for row in bindings.split(";"):
                if not row.strip():
                    continue
                cells = []
                for cell in re.finditer(r"(\w+)", row):
                    cells.append(cell.group(1))
                if cells:
                    rows.append(cells)

            layer_configs.append({"name": layer_name, "id": layer_id, "bindings": rows})

    rgb_settings["layerConfigurations"] = layer_configs

    # Extract other settings

    # Check if RGB underglow auto-off is enabled
    if "EXPERIMENTAL_RGB_UNDERGLOW_AUTO_OFF_IDLE" in device_dtsi_content:
        rgb_settings["underglowAutoOff"] = True

    # Check if experimental RGB layer is enabled
    if "EXPERIMENTAL_RGB_LAYER" in device_dtsi_content:
        rgb_settings["experimentalRgbLayer"] = True

    return rgb_settings


def get_layer_switch_description(key):
    """Get human-readable description of layer switch mechanism"""
    if key["value"] == "&mo":
        return "Momentary layer activation"
    if key["value"] == "&to":
        return "Switch to layer"
    if key["value"] == "&tog":
        return "Toggle layer"
    if key["value"] == "&lt":
        return "Layer-tap: layer when held, keypress when tapped"
    if key["value"] == "&lower":
        return "Activate lower layer"
    if key["value"] == "&raise":
        return "Activate raise layer"

    # Handle custom behaviors
    if (
        key["value"] == "Custom"
        and key["params"]
        and isinstance(key["params"][0]["value"], str)
    ):
        custom_behavior = key["params"][0]["value"]
        if "thumb" in custom_behavior:
            return "Thumb key accessing layer"
        if "crumb" in custom_behavior:
            return "Retro-tap layer access"
        if "space" in custom_behavior:
            return "Space key accessing layer"
        if "stumb" in custom_behavior:
            return "Sticky key layer access"

    return "Layer switch"


def get_keycode_display_name(keycode):
    """Convert ZMK keycode to display name"""
    keycode_map = {
        "N0": "0",
        "N1": "1",
        "N2": "2",
        "N3": "3",
        "N4": "4",
        "N5": "5",
        "N6": "6",
        "N7": "7",
        "N8": "8",
        "N9": "9",
        "SEMI": ";",
        "COMMA": ",",
        "DOT": ".",
        "FSLH": "/",
        "GRAVE": "`",
        "LBKT": "[",
        "RBKT": "]",
        "EQUAL": "=",
        "MINUS": "-",
        "BSLH": "\\",
        "SQT": "'",
        "BSPC": "⌫",
        "SPACE": "␣",
        "TAB": "⇥",
        "RET": "↵",
        "ESC": "Esc",
        "DEL": "Del",
        "INS": "Ins",
        "LSHFT": "⇧",
        "RSHFT": "⇧",
        "LCTRL": "Ctrl",
        "RCTRL": "Ctrl",
        "LALT": "Alt",
        "RALT": "Alt",
        "LGUI": "⌘",
        "RGUI": "⌘",
        "UP": "↑",
        "DOWN": "↓",
        "LEFT": "←",
        "RIGHT": "→",
        "HOME": "Home",
        "END": "End",
        "PG_UP": "PgUp",
        "PG_DN": "PgDn",
    }

    return keycode_map.get(keycode, keycode)


def get_human_readable_key_name(key):
    """Generate human-readable name for a key"""
    if key["value"] == "&none":
        return "None"
    if key["value"] == "&trans":
        return "Trans"

    if key["value"] == "&kp" and key["params"]:
        keycode = key["params"][0]["value"]
        return get_keycode_display_name(keycode)

    if key["value"] == "Custom" and key["params"]:
        behavior = key["params"][0]["value"]
        if isinstance(behavior, str):
            parts = behavior.split(" ")
            behavior_name = parts[0].replace("&", "")
            params = " ".join(parts[1:])
            return f"{behavior_name} {params}"

    # All other key types
    return key["value"].replace("&", "")


def generate_keyboard_layout_data(keymap_json, dtsi_content, device_dtsi_content):
    """Generate comprehensive keyboard layout data"""
    keymap_data = json.loads(keymap_json)

    return {
        "layers": [
            {
                "name": name,
                "keys": [
                    {
                        "index": key_index,
                        "value": key["value"],
                        "params": [p["value"] for p in key["params"]],
                        "displayName": get_human_readable_key_name(key),
                    }
                    for key_index, key in enumerate(keymap_data["layers"][layer_index])
                ],
            }
            for layer_index, name in enumerate(keymap_data["layer_names"])
        ],
        "macros": extract_macros(dtsi_content),
        "combos": extract_combos(dtsi_content),
        "behaviors": extract_behaviors(dtsi_content),
        "layerSwitches": extract_layer_switches(keymap_data),
        "rgbSettings": extract_rgb_settings(device_dtsi_content),
    }


# Example usage:
with open("keymap.json", "r") as f:
    keymap_json = f.read()
with open("processed.dtsi.txt", "r") as f:
    dtsi_content = f.read()
with open("device.dtsi", "r") as f:
    device_dtsi_content = f.read()
layout_data = generate_keyboard_layout_data(
    keymap_json, dtsi_content, device_dtsi_content
)
print(json.dumps(layout_data, indent=2))

print(format_glove80_layout(layout_data, "QWERTY"))
