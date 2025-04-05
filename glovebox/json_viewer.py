#!/usr/bin/env python3

import json
import argparse
import textwrap
import re
import os

# Mapping for simpler key names (can be expanded)
KEY_ALIASES = {
    "LSHFT": "Shift", "RSHFT": "Shift",
    "LCTRL": "Ctrl", "RCTRL": "Ctrl",
    "LALT": "Alt", "RALT": "Alt",
    "LGUI": "Gui", "RGUI": "Gui",
    "N1": "1", "N2": "2", "N3": "3", "N4": "4", "N5": "5",
    "N6": "6", "N7": "7", "N8": "8", "N9": "9", "N0": "0",
    "SPACE": "Space", "ENTER": "Enter", "TAB": "Tab", "ESC": "Esc",
    "BSPC": "Bksp", "BACKSPACE": "Bksp",
    "DEL": "Del", "DELETE": "Del",
    "INS": "Ins", "INSERT": "Ins",
    "HOME": "Home", "END": "End",
    "PG_UP": "PgUp", "PAGE_UP": "PgUp",
    "PG_DN": "PgDn", "PAGE_DOWN": "PgDn",
    "UP": "↑", "DOWN": "↓", "LEFT": "←", "RIGHT": "→",
    "K_UP": "↑", "K_DOWN": "↓", "K_LEFT": "←", "K_RIGHT": "→", # Keypad arrows
    "MINUS": "-", "EQUAL": "=", "GRAVE": "`", "SQT": "'", "APOS": "'",
    "SEMI": ";", "SEMICOLON": ";",
    "COMMA": ",", "DOT": ".", "FSLH": "/", "SLASH": "/",
    "BSLH": "\\", "BACKSLASH": "\\",
    "LBKT": "[", "LEFT_BRACKET": "[",
    "RBKT": "]", "RIGHT_BRACKET": "]",
    "PSCRN": "PrtSc", "PRINTSCREEN": "PrtSc",
    "SCROLLLOCK": "ScLck", "PAUSE_BREAK": "Pause",
    "LBRC": "{", "LEFT_BRACE": "{",
    "RBRC": "}", "RIGHT_BRACE": "}",
    "PIPE": "|", "TILDE": "~", "EXCLAMATION": "!", "AT": "@",
    "HASH": "#", "POUND": "#",
    "DLLR": "$", "DOLLAR": "$",
    "PRCNT": "%", "PERCENT": "%",
    "CARET": "^", "AMPERSAND": "&", "ASTRK": "*", "ASTERISK": "*",
    "LPAR": "(", "LEFT_PARENTHESIS": "(",
    "RPAR": ")", "RIGHT_PARENTHESIS": ")",
    "PLUS": "+", "UNDERSCORE": "_",
    "F1": "F1", "F2": "F2", "F3": "F3", "F4": "F4", "F5": "F5", "F6": "F6",
    "F7": "F7", "F8": "F8", "F9": "F9", "F10": "F10", "F11": "F11", "F12": "F12",
    # Add more as needed
}

def format_key(key_data, max_width=10):
    """Formats a key definition object into a readable string."""
    if not isinstance(key_data, dict):
        return "INVALID".center(max_width)

    value = key_data.get("value", "&none")
    params = key_data.get("params", [])

    if value == "&none":
        # Represent 'none' as blank space, easier to read layout
        return " " * max_width

    param_values = [p.get("value", "") for p in params]

    formatted = ""
    try:
        if value == "&kp":
            key_code = str(param_values[0]) if param_values else "???"
            formatted = KEY_ALIASES.get(key_code, key_code)
        elif value == "&mt":
            mod = KEY_ALIASES.get(str(param_values[0]), str(param_values[0])) if len(param_values) > 0 else "?"
            tap = KEY_ALIASES.get(str(param_values[1]), str(param_values[1])) if len(param_values) > 1 else "?"
            # Use M/T abbreviation consistent with web UI
            formatted = f"M/T({mod},{tap})"
        elif value == "&lt":
            layer = str(param_values[0]) if len(param_values) > 0 else "?"
            tap = KEY_ALIASES.get(str(param_values[1]), str(param_values[1])) if len(param_values) > 1 else "?"
            # Use L/T abbreviation consistent with web UI
            formatted = f"L/T({layer},{tap})"
        elif value == "&mo":
            layer = str(param_values[0]) if param_values else "?"
            # Use MO abbreviation consistent with web UI
            formatted = f"MO({layer})"
        elif value == "&to":
            layer = str(param_values[0]) if param_values else "?"
            # Use TO abbreviation consistent with web UI
            formatted = f"TO({layer})"
        elif value == "&tog":
            layer = str(param_values[0]) if param_values else "?"
            # Use TG abbreviation consistent with web UI
            formatted = f"TG({layer})"
        elif value == "&bt":
            cmd = str(param_values[0]) if param_values else "?"
            param = str(param_values[1]) if len(param_values) > 1 else ""
            # Keep BT format, maybe shorten cmd if needed
            cmd_short = cmd[:3] if len(cmd) > 3 else cmd
            formatted = f"BT.{cmd_short}({param})" if param else f"BT.{cmd_short}"
        elif value == "&sys_reset":
            formatted = "Sys Rst"
        elif value == "&bootloader":
            formatted = "Bootldr"
        elif value == "&rgb_ug":
            cmd = str(param_values[0]) if param_values else "?"
            # Keep RGB format, maybe shorten cmd if needed
            cmd_short = cmd[:3] if len(cmd) > 3 else cmd
            formatted = f"RGB.{cmd_short}"
        elif value == "&out":
            cmd = str(param_values[0]) if param_values else "?"
            # Keep OUT format, maybe shorten cmd if needed
            cmd_short = cmd[:3] if len(cmd) > 3 else cmd
            formatted = f"OUT.{cmd_short}"
        elif value == "&magic":
             formatted = "Magic" # Specific to QWERTY example?
        elif value == "Custom":
            # Extract the core part of the custom behavior name if possible
            custom_name = str(param_values[0]) if param_values else "Custom"
            custom_name = custom_name.replace("&", "") # Remove leading &

            # Simplify common custom patterns found in the example QWERTY.json
            if custom_name.startswith("thumb "):
                 parts = custom_name.split(" ", 2)
                 p1 = KEY_ALIASES.get(parts[1], parts[1]) if len(parts)>1 else "?"
                 p2 = KEY_ALIASES.get(parts[2], parts[2]) if len(parts)>2 else "?"
                 formatted = f"Th({p1},{p2})"
            elif custom_name.startswith("crumb "):
                 parts = custom_name.split(" ", 2)
                 p1 = KEY_ALIASES.get(parts[1], parts[1]) if len(parts)>1 else "?"
                 p2 = KEY_ALIASES.get(parts[2], parts[2]) if len(parts)>2 else "?"
                 formatted = f"Cr({p1},{p2})"
            elif custom_name.startswith("space "):
                 parts = custom_name.split(" ", 2)
                 p1 = KEY_ALIASES.get(parts[1], parts[1]) if len(parts)>1 else "?"
                 p2 = KEY_ALIASES.get(parts[2], parts[2]) if len(parts)>2 else "?"
                 formatted = f"Sp({p1},{p2})"
            elif custom_name.startswith("sticky_key_modtap "):
                 parts = custom_name.split(" ", 2)
                 p1 = KEY_ALIASES.get(parts[1], parts[1]) if len(parts)>1 else "?"
                 p2 = KEY_ALIASES.get(parts[2], parts[2]) if len(parts)>2 else "?"
                 formatted = f"St({p1},{p2})"
            elif custom_name.startswith("parang_"):
                 formatted = f"Par{custom_name[7:].capitalize()}" # ParLeft/ParRight
            elif "(" in custom_name and ")" in custom_name:
                 # Extract name before parenthesis for home row mods like LeftPinky(A, ...)
                 match = re.match(r"(\w+)\s*\(", custom_name)
                 if match:
                     # Extract key from params like LeftPinky(A, LAYER_QWERTY) -> A
                     param_match = re.search(r"\(([^,]+),", custom_name)
                     key_param = param_match.group(1).strip() if param_match else ""
                     key_param_fmt = KEY_ALIASES.get(key_param, key_param)
                     formatted = f"HRM:{key_param_fmt}" # e.g., HRM:A
                 else:
                     formatted = f"C:{custom_name[:max_width-2]}" # Fallback
            else:
                formatted = f"C:{custom_name}" # General custom behavior

        else:
            # General case for other behaviors like &bt, &sys_reset etc.
            param_str = ",".join(map(str, param_values))
            behavior_name = value.replace("&", "") # Remove '&' prefix
            # Use first 3 chars as abbreviation if name is long
            abbr = behavior_name[:3] if len(behavior_name) > 3 else behavior_name
            formatted = f"{abbr}({param_str})" if param_str else abbr

    except IndexError:
        formatted = "ERR:Idx"
    except Exception:
        formatted = "ERR:Fmt" # Catch unexpected formatting errors

    # Truncate if too long and center
    if len(formatted) > max_width:
        # Prioritize showing the start of the string
        formatted = formatted[:max_width-1] + "…"
    # Pad with spaces to ensure consistent width
    return formatted.center(max_width)


def display_layout(keymap_data):
    """Displays the keyboard layout from the parsed JSON data using Glove80 index mapping."""
    print("=" * 80)
    title = keymap_data.get('title') or keymap_data.get('name') or "Untitled"
    print(f"Keyboard: {keymap_data.get('keyboard', 'N/A')} | Title: {title}")
    print(f"Creator: {keymap_data.get('creator', 'N/A')} | Locale: {keymap_data.get('locale', 'N/A')}")
    notes = keymap_data.get('notes', '')
    if notes:
        print(f"Notes: {notes}")
    print("=" * 80)

    layer_names = keymap_data.get("layer_names", [])
    layers = keymap_data.get("layers", [])

    if not layers:
        print("No layers found in the keymap data.")
        return

    # Key width for formatting - adjust if needed
    key_width = 10
    h_spacer = " | " # Horizontal space between left and right halves with separator
    key_gap = " " # Space between keys in a row

    for i, layer_data in enumerate(layers):
        layer_name = layer_names[i] if i < len(layer_names) else f"Layer {i}"
        print(f"\n--- Layer {i}: {layer_name} ---")

        num_keys = len(layer_data)
        expected_keys = 80 # Standard Glove80 count
        if num_keys != expected_keys:
            print(f"Note: Expected {expected_keys} keys for Glove80 layout, but found {num_keys}.")
            # Continue rendering based on expected indices, missing keys will be blank

        # Helper to get formatted key or blank padding string
        def get_fmt_key(idx):
            if 0 <= idx < num_keys:
                return format_key(layer_data[idx], key_width)
            # Return blank space if index is out of bounds or beyond expected count
            return " " * key_width

        # Define key indices based on the preferred layout structure
        # |--------------------------|---|--------------------------|
        # | LEFT_HAND_KEYS           |   |        RIGHT_HAND_KEYS   |
        # |                          |   |                          |
        # |    0  1  2  3  4         |   |          5  6  7  8  9   |
        # | 10 11 12 13 14 15        |   |      16 17 18 19 20 21   |
        # | 22 23 24 25 26 27        |   |      28 29 30 31 32 33   |
        # | 34 35 36 37 38 39        |   |      40 41 42 43 44 45   |
        # | 46 47 48 49 50 51        |   |      58 59 60 61 62 63   |
        # |    64 65 66 67 68        |   |         75 76 77 78 79   |
        # |--------------------------|---|--------------------------|
        # |                  69 52   |   |   57 74                  |
        # |                   70 53  |   |  56 73                   |
        # |                    71 54 |   | 55 72                    |
        # |--------------------------|---|--------------------------|

        l_row0_idx = [ 0,  1,  2,  3,  4]
        r_row0_idx = [ 5,  6,  7,  8,  9]
        l_row1_idx = [10, 11, 12, 13, 14, 15]
        r_row1_idx = [16, 17, 18, 19, 20, 21]
        l_row2_idx = [22, 23, 24, 25, 26, 27]
        r_row2_idx = [28, 29, 30, 31, 32, 33]
        l_row3_idx = [34, 35, 36, 37, 38, 39]
        r_row3_idx = [40, 41, 42, 43, 44, 45]
        l_row4_idx = [46, 47, 48, 49, 50, 51]
        r_row4_idx = [58, 59, 60, 61, 62, 63] # Note the index jump
        l_row5_idx = [64, 65, 66, 67, 68]
        r_row5_idx = [75, 76, 77, 78, 79]

        # Thumb Cluster Indices (arranged for printing)
        thumb_l1 = [69, 52]
        thumb_r1 = [57, 74]
        thumb_l2 = [70, 53]
        thumb_r2 = [56, 73]
        thumb_l3 = [71, 54]
        thumb_r3 = [55, 72]

        # --- Calculate widths and padding ---
        # Width of the main 6-key block section per hand
        main_block_width = key_width * 6 + len(key_gap) * 5
        # Width of the 5-key block section per hand (top/bottom rows)
        five_key_block_width = key_width * 5 + len(key_gap) * 4
        # Total width based on the widest part (main block) including the spacer
        total_width = main_block_width * 2 + len(h_spacer)

        # Padding for the 5-key rows to align with the 6-key rows
        # Assuming alignment to the inner side (closer to the center split)
        pad_5_key_left = key_width + len(key_gap)
        pad_5_key_right = 0 # Right side aligns naturally when left-padding the left block

        print("Layout (Glove80 Indices):")
        print("-" * total_width)

        # Row 0 (Top pinky cluster)
        l_row0 = key_gap.join([get_fmt_key(i) for i in l_row0_idx])
        r_row0 = key_gap.join([get_fmt_key(i) for i in r_row0_idx])
        print(f"{' ' * pad_5_key_left}{l_row0}{h_spacer}{r_row0}{' ' * pad_5_key_right}")

        # Row 1 (Number row)
        l_row1 = key_gap.join([get_fmt_key(i) for i in l_row1_idx])
        r_row1 = key_gap.join([get_fmt_key(i) for i in r_row1_idx])
        print(f"{l_row1}{h_spacer}{r_row1}")

        # Row 2 (Top alpha row)
        l_row2 = key_gap.join([get_fmt_key(i) for i in l_row2_idx])
        r_row2 = key_gap.join([get_fmt_key(i) for i in r_row2_idx])
        print(f"{l_row2}{h_spacer}{r_row2}")

        # Row 3 (Home row)
        l_row3 = key_gap.join([get_fmt_key(i) for i in l_row3_idx])
        r_row3 = key_gap.join([get_fmt_key(i) for i in r_row3_idx])
        print(f"{l_row3}{h_spacer}{r_row3}")

        # Row 4 (Bottom alpha row)
        l_row4 = key_gap.join([get_fmt_key(i) for i in l_row4_idx])
        r_row4 = key_gap.join([get_fmt_key(i) for i in r_row4_idx])
        print(f"{l_row4}{h_spacer}{r_row4}")

        # Row 5 (Bottom pinky cluster)
        l_row5 = key_gap.join([get_fmt_key(i) for i in l_row5_idx])
        r_row5 = key_gap.join([get_fmt_key(i) for i in r_row5_idx])
        print(f"{' ' * pad_5_key_left}{l_row5}{h_spacer}{r_row5}{' ' * pad_5_key_right}")

        print("-" * total_width)
        # print() # Spacer - removed to keep thumbs closer to main block

        # --- Print Thumb Clusters ---
        # Calculate padding to align thumb clusters under inner columns
        thumb_width = key_width * 2 + len(key_gap) # Width of a 2-key thumb part

        # Left thumb cluster: Align its right edge with the right edge of the left main block
        thumb_pad_l = main_block_width - thumb_width

        # Right thumb cluster: Align its left edge with the left edge of the right main block
        # The space between the end of the left thumb cluster and the start of the right one
        # should be exactly the horizontal spacer width.
        mid_thumb_spacer = h_spacer
        # No right padding needed as the alignment is based on the left side start.
        thumb_pad_r = 0

        # Thumb Row 1
        l_thumb1 = key_gap.join([get_fmt_key(i) for i in thumb_l1])
        r_thumb1 = key_gap.join([get_fmt_key(i) for i in thumb_r1])
        print(f"{' ' * thumb_pad_l}{l_thumb1}{mid_thumb_spacer}{r_thumb1}{' ' * thumb_pad_r}")

        # Thumb Row 2
        l_thumb2 = key_gap.join([get_fmt_key(i) for i in thumb_l2])
        r_thumb2 = key_gap.join([get_fmt_key(i) for i in thumb_r2])
        print(f"{' ' * thumb_pad_l}{l_thumb2}{mid_thumb_spacer}{r_thumb2}{' ' * thumb_pad_r}")

        # Thumb Row 3
        l_thumb3 = key_gap.join([get_fmt_key(i) for i in thumb_l3])
        r_thumb3 = key_gap.join([get_fmt_key(i) for i in thumb_r3])
        print(f"{' ' * thumb_pad_l}{l_thumb3}{mid_thumb_spacer}{r_thumb3}{' ' * thumb_pad_r}")

        print("-" * total_width)


def main():
    parser = argparse.ArgumentParser(
        description="Display a Glove80 (or similar ZMK) keyboard layout JSON file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent('''\
            Example:
              python glovebox/src/json_viewer.py glovebox/QWERTY.json

            Displays the layers defined in the JSON file using the standard
            Glove80 key index mapping for visual layout in the terminal.
            Key codes are simplified for readability. Includes a visual separator
            between keyboard halves.
            Warns if the key count in the JSON differs from the expected 80.
            ''')
        )
    parser.add_argument("json_file", help="Path to the keyboard layout JSON file")
    args = parser.parse_args()

    if not os.path.exists(args.json_file):
        print(f"Error: File not found - {args.json_file}")
        exit(1)

    try:
        with open(args.json_file, 'r', encoding='utf-8') as f:
            keymap_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON file - {args.json_file}\nDetails: {e}")
        exit(1)
    except Exception as e:
        print(f"An unexpected error occurred loading the file: {e}")
        exit(1)

    try:
        display_layout(keymap_data)
    except Exception as e:
        print(f"\nAn unexpected error occurred during display: {e}")
        # Optionally add more detailed error logging/traceback here
        # import traceback
        # traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    main()
