import json
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict
import re
import logging

logger = logging.getLogger(__name__)
DEFAULT_KEY_WIDTH = 20  # Default width for centering keys if not specified


def parse_key_position_defines(content: str) -> Dict[int, str]:
    """Parses C preprocessor defines like '#define KEY_POS_LH_THUMB_T1 69' into a map."""
    mapping = {}
    # Regex to find #define KEY_POS_NAME INDEX
    define_pattern = re.compile(
        r"^\s*#define\s+(KEY_POS_\w+)\s+(\d+)\s*(//.*)?$", re.MULTILINE
    )
    for match in define_pattern.finditer(content):
        name = match.group(1)
        index = int(match.group(2))
        mapping[index] = name
    if not mapping:
        logger.warning(
            "Could not parse any KEY_POS defines from key_position_defines_content."
        )
    return mapping


# Helper function to calculate padding based on alignment rules
def calculate_left_padding(row_type: str, formatting: Dict) -> str:
    """Calculates the left-side padding string based on alignment rules."""
    rules = formatting.get("alignment_rules", {})
    rule = rules.get(row_type)
    # Only apply padding if the rule is for 'inner' alignment relative to 'main_6'
    if not rule or rule.get("align_to") != "main_6" or rule.get("side") != "inner":
        # Default: no padding if rule missing, not relative to main_6, or not inner align
        return ""

    offset_keys = rule.get("offset_keys", 0)
    # Fetch formatting params needed for calculation
    # Use the actual width configured or the default fallback
    default_key_width = formatting.get("default_key_width", DEFAULT_KEY_WIDTH)
    key_gap = formatting.get("key_gap", " ")  # Assuming key_gap is always defined

    # Calculate padding amount in spaces
    # This represents the empty space created by offsetting inwards
    padding_amount = offset_keys * (default_key_width + len(key_gap))
    return " " * padding_amount


@dataclass
class LayoutConfig:
    """Holds keyboard layout structure and formatting info."""

    keyboard_name: str
    total_keys: int
    # Updated rows type to match the new JSON structure
    rows: List[List[int]]
    formatting: Dict
    # key_position_map can still be useful for other parts like combo/behavior generation
    key_position_map: Dict[int, str]

    @classmethod
    def from_file(
        cls, config_path: Path, key_pos_header_content: str
    ) -> "LayoutConfig":
        if not config_path.is_file():
            raise FileNotFoundError(f"Layout config file not found: {config_path}")
        try:
            with open(config_path, "r") as f:
                data = json.load(f)

            # --- Key Position Map Parsing ---
            # Still useful, even if grid format changes. Parse *before* validating main structure.
            key_pos_map = parse_key_position_defines(key_pos_header_content)

            # --- Validation ---
            required_keys = ["keyboard_name", "total_keys", "rows", "formatting"]
            for key in required_keys:
                 if key not in data:
                     raise ValueError(f"Layout config missing required key: '{key}'.")

            # Validate rows structure (list of lists of ints)
            if not isinstance(data["rows"], list) or not all(isinstance(r, list) for r in data["rows"]):
                 raise ValueError("'rows' must be a list of lists.")
            if not all(isinstance(i, int) for r in data["rows"] for i in r):
                 raise ValueError("All elements within the 'rows' lists must be integers.")

            # Validate formatting structure (at least check it's a dict)
            if not isinstance(data["formatting"], dict):
                 raise ValueError("'formatting' must be a dictionary.")

            return cls(
                keyboard_name=data["keyboard_name"],
                total_keys=data["total_keys"],
                rows=data["rows"], # Assign the new structure
                formatting=data["formatting"],
                key_position_map=key_pos_map, # Keep the parsed map
            )
        except ValueError as e: # Catch validation errors specifically
            raise ValueError(f"Error validating layout config {config_path}: {e}") from e
        except Exception as e:
            raise ValueError(f"Error loading layout config {config_path}: {e}") from e


def format_layer_bindings_grid(bindings: List[str], config: LayoutConfig) -> List[str]:
    """
    Arranges formatted binding strings into a grid based on the list-of-lists
    row definition in LayoutConfig.
    """
    output_lines = []
    fmt = config.formatting

    # --- Get formatting parameters ---
    base_indent = fmt.get("base_indent", "           ") # 11 spaces default
    key_gap = fmt.get("key_gap", " ")
    default_width = fmt.get("default_key_width", DEFAULT_KEY_WIDTH) # Use config or default

    logger.debug(f"Formatting grid with: indent='{len(base_indent)} spaces', gap='{len(key_gap)} spaces', width={default_width}")

    # --- Prepare map of index to binding string (not padded yet) ---
    bindings_map: Dict[int, str] = {}
    num_bindings_available = len(bindings)

    # Ensure we have enough bindings, pad if necessary (using config.total_keys for reference)
    if num_bindings_available < config.total_keys:
         logger.warning(f"Layer has {num_bindings_available} bindings, expected around {config.total_keys}. Padding missing indices with '&none'.")
         # Pad the original list first before creating the map
         bindings.extend(["&none"] * (config.total_keys - num_bindings_available))
         num_bindings_available = len(bindings) # Update count

    for idx, binding_str in enumerate(bindings):
         # Check if idx exceeds total_keys expected? Might not be necessary if list is correct length
         if idx >= config.total_keys:
              logger.warning(f"Binding index {idx} exceeds total_keys ({config.total_keys}). Ignoring extra binding: {binding_str}")
              continue
         bindings_map[idx] = str(binding_str)

    # --- Calculate max width for column 0 ---
    col0_width = default_width
    if config.rows and isinstance(config.rows, list):
        col0_indices = [row[0] for row in config.rows if row and len(row) > 0 and row[0] != -1]
        col0_bindings = [len(bindings_map[idx]) for idx in col0_indices if idx in bindings_map]
        if col0_bindings:
            col0_width = max(col0_bindings)

    # --- Prepare map of index to padded binding string ---
    padded_bindings_map: Dict[int, str] = {}
    for idx, binding_str in bindings_map.items():
        padded_bindings_map[idx] = binding_str

    # String representing an empty slot in the grid
    empty_slot_str = " " * default_width

    # --- Add framing ---
    # output_lines.append(base_indent + "<")

    # --- Iterate through the row definitions ---
    if not isinstance(config.rows, list) or not all(isinstance(r, list) for r in config.rows):
         logger.error("Invalid 'rows' structure in LayoutConfig. Expected list of lists.")
         output_lines.append(base_indent + "// Error: Invalid 'rows' structure in config")
         # output_lines.append(base_indent + ">;")
         return output_lines

    for row_indices in config.rows:
        current_row_parts = []
        for col_idx, key_index in enumerate(row_indices):
            if key_index == -1:
                current_row_parts.append(empty_slot_str)
            elif key_index in padded_bindings_map:
                # Apply special padding for column 0
                if col_idx == 0:
                    current_row_parts.append(padded_bindings_map[key_index].rjust(col0_width))
                else:
                    current_row_parts.append(padded_bindings_map[key_index].rjust(default_width))
            else:
                # Index is not -1 and not found in the map (shouldn't happen if padding worked)
                logger.warning(f"Key index {key_index} not found in bindings map (max index: {num_bindings_available-1}). Using empty slot.")
                current_row_parts.append(empty_slot_str) # Append empty slot for missing indices

        # Join the parts for this row with the key gap
        row_string = key_gap.join(current_row_parts)
        # Prepend the base indentation
        line = f"{base_indent}{row_string}"
        output_lines.append(line)

    # --- Add closing frame ---
    # output_lines.append(base_indent + ">;")

    return output_lines


