import json
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional
import re
import logging

logger = logging.getLogger(__name__)
DEFAULT_KEY_WIDTH = 20  # Default width for centering keys if not specified


def parse_key_position_defines(content: str) -> Dict[int, str]:
    """Parses C preprocessor defines like '#define KEY_POS_LH_T1 52' into a map."""
    mapping = {}
    # Regex to find #define KEY_POS_NAME INDEX (Updated to match the actual file format)
    define_pattern = re.compile(
        r"^\s*#define\s+(KEY_POS_\w+)\s+(\d+)\s*(//.*)?$", re.MULTILINE
    )
    for match in define_pattern.finditer(content):
        name = match.group(1)  # Keep the full name like KEY_POS_LH_T1
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
            if not isinstance(data["rows"], list) or not all(
                isinstance(r, list) for r in data["rows"]
            ):
                raise ValueError("'rows' must be a list of lists.")
            if not all(isinstance(i, int) for r in data["rows"] for i in r):
                raise ValueError(
                    "All elements within the 'rows' lists must be integers."
                )

            # Validate formatting structure (at least check it's a dict)
            if not isinstance(data["formatting"], dict):
                raise ValueError("'formatting' must be a dictionary.")

            return cls(
                keyboard_name=data["keyboard_name"],
                total_keys=data["total_keys"],
                rows=data["rows"],  # Assign the new structure
                formatting=data["formatting"],
                key_position_map=key_pos_map,  # Keep the parsed map
            )
        except ValueError as e:  # Catch validation errors specifically
            raise ValueError(
                f"Error validating layout config {config_path}: {e}"
            ) from e
        except Exception as e:
            raise ValueError(f"Error loading layout config {config_path}: {e}") from e


def format_layer_bindings_grid(bindings: List[str], config: LayoutConfig) -> List[str]:
    """
    Arranges formatted binding strings into a grid based on the list-of-lists
    row definition in LayoutConfig, using right justification.
    """
    output_lines = []
    fmt = config.formatting
    EMPTY_SLOT_MARKER = None  # Use None to mark empty slots in the matrix

    # --- Get formatting parameters ---
    base_indent = fmt.get("base_indent", "           ")  # 11 spaces default
    key_gap = fmt.get("key_gap", "  ")
    # default_width is not directly used for padding anymore, but good for logging
    default_width_log = fmt.get("default_key_width", DEFAULT_KEY_WIDTH)

    logger.debug(
        f"Formatting grid with: indent='{len(base_indent)} spaces', gap='{len(key_gap)} spaces', default_width_log={default_width_log}"
    )

    # --- Prepare map of index to binding string ---
    bindings_map: Dict[int, str] = {}
    num_bindings_available = len(bindings)

    # Ensure we have enough bindings, pad if necessary
    if num_bindings_available < config.total_keys:
        logger.warning(
            f"Layer has {num_bindings_available} bindings, expected {config.total_keys}. Padding missing indices with '&none'."
        )
        bindings.extend(["&none"] * (config.total_keys - num_bindings_available))

    for idx, binding_str in enumerate(bindings):
        if idx >= config.total_keys:
            logger.warning(
                f"Binding index {idx} exceeds total_keys ({config.total_keys}). Ignoring extra binding: {binding_str}"
            )
            continue
        bindings_map[idx] = str(binding_str)

    # --- Determine grid dimensions and initialize matrix ---
    if not isinstance(config.rows, list) or not all(
        isinstance(r, list) for r in config.rows
    ):
        logger.error(
            "Invalid 'rows' structure in LayoutConfig. Expected list of lists."
        )
        return [base_indent + "  // Error: Invalid 'rows' structure in config"]

    num_rows = len(config.rows)
    num_cols = max(len(r) for r in config.rows) if config.rows else 0
    grid_matrix: List[List[Optional[str]]] = [
        [EMPTY_SLOT_MARKER] * num_cols for _ in range(num_rows)
    ]

    # --- Populate the matrix ---
    for r, row_indices in enumerate(config.rows):
        if not isinstance(row_indices, list):
            logger.error(
                f"Invalid row data found at index {r}: {row_indices}. Skipping row."
            )
            continue  # Skip this malformed row
        for c, key_index in enumerate(row_indices):
            if c >= num_cols:  # Should not happen if num_cols is calculated correctly
                logger.warning(
                    f"Column index {c} exceeds calculated max columns {num_cols} in row {r}."
                )
                continue
            if key_index == -1:
                grid_matrix[r][c] = (
                    EMPTY_SLOT_MARKER  # Already initialized, but explicit
                )
            elif key_index in bindings_map:
                grid_matrix[r][c] = bindings_map[key_index]
            else:
                logger.warning(
                    f"Key index {key_index} (row {r}, col {c}) not found in bindings map. Using empty slot."
                )
                grid_matrix[r][c] = EMPTY_SLOT_MARKER  # Mark as empty

    # --- Calculate max width for each column based on matrix content ---
    max_col_widths = [0] * num_cols
    for c in range(num_cols):
        col_binding_lengths = []
        for r in range(num_rows):
            cell_content = grid_matrix[r][c]
            if cell_content is not EMPTY_SLOT_MARKER:
                col_binding_lengths.append(len(cell_content))

        if col_binding_lengths:
            max_col_widths[c] = max(col_binding_lengths)
        # If a column only contains EMPTY_SLOT_MARKER, its width remains 0

    logger.debug(
        f"Calculated max column widths from matrix (0 means empty column): {max_col_widths}"
    )

    # --- Iterate through the matrix and format output lines ---
    for r in range(num_rows):
        current_row_parts = []
        for c in range(num_cols):
            cell_content = grid_matrix[r][c]
            current_col_width = max_col_widths[c]

            if cell_content is EMPTY_SLOT_MARKER:
                # Append whitespace matching the column width for empty slots
                # rjust ensures correct width even if current_col_width is 0
                current_row_parts.append(" ".rjust(current_col_width))
            else:
                # Apply right alignment (rjust) using the calculated width for this column
                current_row_parts.append(cell_content.rjust(current_col_width))

        # Join the parts for this row with the key gap
        row_string = key_gap.join(current_row_parts)
        # Prepend the base indentation
        line = f"{base_indent}{row_string}"
        output_lines.append(line)

    return output_lines
