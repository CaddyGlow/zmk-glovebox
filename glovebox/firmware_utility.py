import json
import os
import argparse
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional


logger = logging.getLogger("layer_extractor")



def empty_fields(keymap: Dict[str, Any], fields_to_empty: List[str]) -> Dict[str, Any]:
    for field in fields_to_empty:
        if isinstance(field, list):
            keymap[field] = []
        elif isinstance(field, dict):
            keymap[field] = {}
        elif isinstance(field, str):
            keymap[field] = ""
        else:
            logger.warning(f"Unknown field type for {field}: {type(field)}")

    return keymap


def extract_base(keymap: Dict[str, Any], output_dir: str) -> None:
    """
    Extract a base.json file containing everything except layers, custom_defined_behaviors, and custom_devicetree.

    Args:
        keymap (Dict[str, Any]): The keymap dictionary
        output_dir (str): Directory to save the base.json file
    """

    # Create a copy of the keymap
    base_keymap = keymap.copy()

    # Remove layers, layer_names, custom_defined_behaviors, and custom_devicetree
    fields_to_remove = [
        "layers",
        "custom_defined_behaviors",
        "custom_devicetree",
    ]

    base_keymap = empty_fields(base_keymap, fields_to_remove)

    # Save the base keymap
    output_file = os.path.join(output_dir, "base.json")
    with open(output_file, "w") as f:
        json.dump(base_keymap, f, indent=2)

    logger.info(f"Extracted base configuration to {output_file}")


def extract_layers(keymap_file, output_dir):
    """
    Extract each layer from a keymap JSON file and save it to a separate file.
    Include Lower and Magic layers in each output file.
    Also extract a base.json file with everything except layers, custom_defined_behaviors, and custom_devicetree.

    Args:
        keymap_file (str): Path to the keymap JSON file
        output_dir (str): Directory to save the extracted layers
    """
    logger = setup_logger()
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Read the keymap JSON file
    with open(keymap_file, "r") as f:
        keymap = json.load(f)

    # Extract base.json
    extract_base(keymap, output_dir)

    # # Get the indices of Lower and Magic layers
    layer_names = keymap["layer_names"]
    # lower_index = layer_names.index("Lower") if "Lower" in layer_names else None
    # magic_index = layer_names.index("Magic") if "Magic" in layer_names else None

    # Compile regex pattern for layers to ignore
    # ignore_pattern = re.compile(r"^(Lower|Magic|Left|Right|Mouse(Slow|Fast|Warp))")
    ignore_pattern = re.compile(r"^(Lower|Magic)$")

    # Extract each layer except those matching the ignore pattern
    for i, layer_name in enumerate(layer_names):
        # Create a new keymap with this layer as the first layer
        new_keymap = keymap.copy()

        # Set empty values for specified fields
        fields_to_empty = [
            "uuid",
            "parent_uuid",
            "title",
            "notes",
            "custom_defined_behaviors",
            "custom_devicetree",
            "config_parameters",
        ]
        new_keymap = empty_fields(new_keymap, fields_to_empty)

        # Set tags with the layer name in lowercase
        new_keymap["tags"] = [layer_name.lower()]

        # Set layer names and layers
        new_keymap["layer_names"] = [layer_name]
        new_layers = [keymap["layers"][i]]

        # Add Lower and Magic layers if they exist
        # if lower_index is not None:
        #     new_keymap["layer_names"].append("Lower")
        #     new_layers.append(keymap["layers"][lower_index])
        #
        # if magic_index is not None:
        #     new_keymap["layer_names"].append("Magic")
        #     new_layers.append(keymap["layers"][magic_index])

        new_keymap["layers"] = new_layers

        # Save the new keymap to a file
        output_file = os.path.join(output_dir, f"{layer_name}.json")
        with open(output_file, "w") as f:
            json.dump(new_keymap, f, indent=2)

        logger.info(f"Extracted layer '{layer_name}' to {output_file}")


def finish(
    keymap_file: str,
    device_dtsi: Optional[str] = None,
    keymap_dtsi: Optional[str] = None,
    output_file: Optional[str] = None,
):
    """
    Add device.dtsi and keymap.dtsi contents to custom_devicetree and custom_defined_behaviors
    fields of a keymap.json file.

    Args:
        keymap_file (str): Path to the keymap JSON file
        device_dtsi (Optional[str]): Path to the device.dtsi file
        keymap_dtsi (Optional[str]): Path to the keymap.dtsi file
        output_file (Optional[str]): Path to save the updated keymap (defaults to keymap_file)
    """
    logger = setup_logger()

    # Read the keymap JSON file
    with open(keymap_file, "r") as f:
        keymap = json.load(f)

    # Update custom_devicetree if device_dtsi is provided
    if device_dtsi and os.path.exists(device_dtsi):
        logger.info(f"Reading device tree from {device_dtsi}")
        with open(device_dtsi, "r") as f:
            keymap["custom_devicetree"] = f.read()
    else:
        if device_dtsi:
            logger.warning(f"Device tree file not found: {device_dtsi}")

    # Update custom_defined_behaviors if keymap_dtsi is provided
    if keymap_dtsi and os.path.exists(keymap_dtsi):
        logger.info(f"Reading keymap behaviors from {keymap_dtsi}")
        with open(keymap_dtsi, "r") as f:
            keymap["custom_defined_behaviors"] = f.read()
    else:
        if keymap_dtsi:
            logger.warning(f"Keymap behaviors file not found: {keymap_dtsi}")

    # Save the updated keymap
    output = output_file if output_file else keymap_file
    with open(output, "w") as f:
        json.dump(keymap, f, indent=2)

    logger.info(f"Updated keymap saved to {output}")


def combine_layers(input_dir: str, output_file: str):
    """
    Combine layers from a directory into a single file based on base.json structure.

    Args:
        input_dir (str): Directory containing base.json and layer files
        output_file (str): Path to save the combined keymap
    """
    logger = setup_logger()

    # Read the base.json file
    base_file = os.path.join(input_dir, "base.json")
    if not os.path.exists(base_file):
        logger.error(f"Base file not found: {base_file}")
        return

    with open(base_file, "r") as f:
        combined_keymap = json.load(f)

    # Get the layer order from base.json
    if "layer_names" not in combined_keymap:
        logger.error("No layer_names found in base.json")
        return

    # Initialize layers array
    combined_keymap["layers"] = []

    # Process each layer in the order specified in layer_names
    for layer_name in combined_keymap["layer_names"]:
        layer_file = os.path.join(input_dir, f"{layer_name}.json")

        if not os.path.exists(layer_file):
            logger.warning(f"Layer file not found: {layer_file}")
            # Add an empty layer as placeholder
            combined_keymap["layers"].append([])
            continue

        logger.info(f"Processing layer: {layer_name}")
        with open(layer_file, "r") as f:
            layer_data = json.load(f)

        # Find the index of this layer in the layer file
        try:
            layer_index = layer_data["layer_names"].index(layer_name)
            # Add the layer to the combined keymap
            combined_keymap["layers"].append(layer_data["layers"][layer_index])
            logger.info(f"Added layer '{layer_name}' from {layer_file}")
        except (ValueError, IndexError):
            logger.warning(f"Layer '{layer_name}' not found in {layer_file}")
            # Add an empty layer as placeholder
            combined_keymap["layers"].append([])

    # Set tags with all layer names in lowercase
    combined_keymap["tags"] = [
        name.lower()
        for name in combined_keymap["layer_names"]
        if name not in ["Lower", "Magic"]
    ]

    # Save the combined keymap
    with open(output_file, "w") as f:
        json.dump(combined_keymap, f, indent=2)

    logger.info(f"Combined keymap saved to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Extract, combine, or finish keymap JSON files"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Extract command
    extract_parser = subparsers.add_parser(
        "extract", help="Extract layers from a keymap file"
    )
    extract_parser.add_argument("keymap_file", help="Path to the keymap JSON file")
    extract_parser.add_argument(
        "output_dir", help="Directory to save the extracted layers"
    )

    # Combine command
    combine_parser = subparsers.add_parser(
        "combine", help="Combine layers from a directory based on base.json structure"
    )
    combine_parser.add_argument(
        "input_dir", help="Directory containing base.json and layer files"
    )
    combine_parser.add_argument(
        "--output", "-o", required=True, help="Path to save the combined keymap"
    )

    # Finish command
    finish_parser = subparsers.add_parser(
        "finish", help="Add device tree and keymap behaviors to a keymap file"
    )
    finish_parser.add_argument(
        "keymap_file",
        help="Path to the keymap JSON file",
        nargs="?",  # Make the argument optional
        default="keymap.json",  # Default to keymap.json if not provided
    )
    finish_parser.add_argument(
        "--device", "-d", help="Path to the device.dtsi file", default="device.dtsi"
    )
    finish_parser.add_argument(
        "--keymap", "-k", help="Path to the keymap.dtsi file", default="keymap.dtsi"
    )
    finish_parser.add_argument(
        "--output", "-o", help="Path to save the updated keymap", default="keymap.json"
    )

    # Common options
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Set logging level based on verbose flag
    if args.verbose:
        logging.getLogger("layer_extractor").setLevel(logging.DEBUG)

    if args.command == "extract":
        extract_layers(args.keymap_file, args.output_dir)
    elif args.command == "combine":
        combine_layers(args.input_dir, args.output)
    elif args.command == "finish":
        finish(args.keymap_file, args.device, args.keymap, args.output)
    else:
        parser.print_help()


if __name__ == "__main__":
    main(
