# glovebox/glovebox/keymap_utility.py

import json
import os
import argparse
import re
import logging
import shutil

# import importlib.resources # No longer used for default paths
import sys  # For stdin handling
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

# Import new config classes
from .config.resolver import ProfileResolver
from .config.profiles import Profile  # Import Profile for type hinting

from glovebox import layout
from . import dtsi_builder
from . import file_utils
from . import behaviors  # Import behaviors module for registry population

logger = logging.getLogger(__name__)


# --- Other functions (empty_fields, extract_base, extract_layers, finish, combine_layers) remain the same ---
# ... (paste the existing functions here) ...
def empty_fields(keymap: Dict[str, Any], fields_to_empty: List[str]) -> Dict[str, Any]:
    """Sets specified fields in the keymap dictionary to empty values."""
    for field in fields_to_empty:
        if field in keymap:
            if isinstance(keymap[field], list):
                keymap[field] = []
            elif isinstance(keymap[field], dict):
                keymap[field] = {}
            elif isinstance(keymap[field], str):
                keymap[field] = ""
            else:
                logger.debug(
                    f"Keeping original type for {field}: {type(keymap[field])}"
                )
        else:
            logger.warning(f"Field '{field}' not found in keymap to empty.")
    return keymap


def extract_base(keymap: Dict[str, Any], output_dir: Path) -> None:
    """Extract a base.json file containing everything except layers, custom_defined_behaviors, and custom_devicetree."""
    base_keymap = keymap.copy()
    fields_to_empty = ["layers", "custom_defined_behaviors", "custom_devicetree"]
    base_keymap = empty_fields(base_keymap, fields_to_empty)
    output_file = output_dir / "base.json"
    try:
        with open(output_file, "w") as f:
            json.dump(base_keymap, f, indent=2)
        logger.info(f"Extracted base configuration to {output_file}")
    except IOError as e:
        logger.error(f"Failed to write base file {output_file}: {e}")


def extract_layers(keymap_file: Path, output_dir: Path):
    """Extract each layer from a keymap JSON file and save it to a separate file."""
    if not keymap_file.is_file():
        logger.error(f"Keymap file not found: {keymap_file}")
        return
    output_layer_dir = output_dir / "layers"
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(output_layer_dir, exist_ok=True)
    try:
        with open(keymap_file, "r") as f:
            keymap = json.load(f)
    except Exception as e:
        logger.error(f"Error reading/parsing {keymap_file}: {e}")
        return
    devtree_dtsi = keymap.get("custom_devicetree", "")
    def_bev_dtsi = keymap.get("custom_defined_behaviors", "")
    try:
        with open(output_layer_dir / "device.dtsi", "w") as f:
            f.write(devtree_dtsi)
            logger.info(
                f"Extracted custom_devicetree to {output_layer_dir / 'device.dtsi'}"
            )
        with open(output_layer_dir / "keymap.dtsi", "w") as f:
            f.write(def_bev_dtsi)
            logger.info(
                f"Extracted custom_defined_behaviors to {output_layer_dir / 'keymap.dtsi'}"
            )
    except IOError as e:
        logger.error(f"Failed to write DTSI snippets: {e}")
    extract_base(keymap, output_dir)
    layer_names = keymap.get("layer_names", [])
    layers = keymap.get("layers", [])
    if not layer_names or not layers or len(layer_names) != len(layers):
        logger.error("Inconsistent layer data")
        return
    for i, layer_name in enumerate(layer_names):
        new_keymap = {
            "keyboard": keymap.get("keyboard", "unknown"),
            "firmware_api_version": keymap.get("firmware_api_version", "1"),
            "locale": keymap.get("locale", "en-US"),
            "uuid": "",
            "parent_uuid": keymap.get("uuid", ""),
            "date": keymap.get("date", 0),
            "creator": keymap.get("creator", ""),
            "title": f"Layer: {layer_name}",
            "notes": f"Extracted layer '{layer_name}' from {keymap_file.name}",
            "tags": [layer_name.lower().replace("_", "-")],
            "layer_names": [layer_name],
            "layers": [layers[i]],
            "custom_defined_behaviors": "",
            "custom_devicetree": "",
            "config_parameters": [],
            "macros": [],
            "inputListeners": [],
            "holdTaps": [],
            "combos": [],
        }
        output_file = output_layer_dir / f"{layer_name}.json"
        try:
            with open(output_file, "w") as f:
                json.dump(new_keymap, f, indent=2)
            logger.info(f"Extracted layer '{layer_name}' to {output_file}")
        except IOError as e:
            logger.error(f"Failed to write layer file {output_file}: {e}")


def finish(
    keymap_file: Path,
    device_dtsi: Optional[Path] = None,
    keymap_dtsi: Optional[Path] = None,
    output_file: Optional[Path] = None,
):
    """Add device.dtsi and keymap.dtsi contents to a keymap JSON file."""
    if not keymap_file.is_file():
        logger.error(f"Keymap file not found: {keymap_file}")
        return
    try:
        with open(keymap_file, "r") as f:
            keymap = json.load(f)
    except Exception as e:
        logger.error(f"Error reading/parsing {keymap_file}: {e}")
        return
    if device_dtsi:
        if device_dtsi.is_file():
            logger.info(f"Reading device tree from {device_dtsi}")
            try:
                with open(device_dtsi, "r") as f:
                    keymap["custom_devicetree"] = f.read()
            except IOError as e:
                logger.error(f"Error reading device tree file {device_dtsi}: {e}")
        else:
            logger.warning(f"Device tree file not found: {device_dtsi}")
    if keymap_dtsi:
        if keymap_dtsi.is_file():
            logger.info(f"Reading keymap behaviors from {keymap_dtsi}")
            try:
                with open(keymap_dtsi, "r") as f:
                    keymap["custom_defined_behaviors"] = f.read()
            except IOError as e:
                logger.error(f"Error reading keymap behaviors file {keymap_dtsi}: {e}")
        else:
            logger.warning(f"Keymap behaviors file not found: {keymap_dtsi}")
    output_path = output_file if output_file else keymap_file
    try:
        with open(output_path, "w") as f:
            json.dump(keymap, f, indent=2)
        logger.info(f"Updated keymap saved to {output_path}")
    except IOError as e:
        logger.error(f"Failed to write updated keymap file {output_path}: {e}")


def combine_layers(input_dir: Path, output_file: Path):
    """Combine layers from a directory into a single file based on base.json structure."""
    base_file = input_dir / "base.json"
    layers_dir = input_dir / "layers"
    if not base_file.is_file():
        logger.error(f"Base file not found: {base_file}")
        return
    if not layers_dir.is_dir():
        logger.error(f"Layers directory not found: {layers_dir}")
        return
    try:
        with open(base_file, "r") as f:
            combined_keymap = json.load(f)
    except Exception as e:
        logger.error(f"Error reading/parsing {base_file}: {e}")
        return
    if "layer_names" not in combined_keymap or not isinstance(
        combined_keymap["layer_names"], list
    ):
        logger.error("Invalid 'layer_names' in base.json")
        return
    combined_keymap["layers"] = []
    num_keys = 80
    empty_layer = [{"value": "&none", "params": []} for _ in range(num_keys)]
    for layer_name in combined_keymap["layer_names"]:
        layer_file = layers_dir / f"{layer_name}.json"
        if not layer_file.is_file():
            logger.warning(f"Layer file not found, adding empty layer: {layer_file}")
            combined_keymap["layers"].append(empty_layer)
            continue
        logger.info(f"Processing layer: {layer_name}")
        try:
            with open(layer_file, "r") as f:
                layer_data = json.load(f)
            layer_index = (
                layer_data.get("layer_names", []).index(layer_name)
                if layer_name in layer_data.get("layer_names", [])
                else 0
            )
            if "layers" in layer_data and len(layer_data["layers"]) > layer_index:
                combined_keymap["layers"].append(layer_data["layers"][layer_index])
                logger.info(f"Added layer '{layer_name}' from {layer_file}")
            else:
                logger.warning(
                    f"Layer data missing in {layer_file}, adding empty layer."
                )
                combined_keymap["layers"].append(empty_layer)
        except Exception as e:
            logger.error(
                f"Error processing layer file {layer_file}: {e}. Adding empty layer."
            )
            combined_keymap["layers"].append(empty_layer)
    device_dtsi_path = layers_dir / "device.dtsi"
    keymap_dtsi_path = layers_dir / "keymap.dtsi"
    if device_dtsi_path.is_file():
        try:
            with open(device_dtsi_path, "r") as f:
                combined_keymap["custom_devicetree"] = f.read()
                logger.info("Restored custom_devicetree.")
        except IOError as e:
            logger.error(f"Error reading {device_dtsi_path}: {e}")
    if keymap_dtsi_path.is_file():
        try:
            with open(keymap_dtsi_path, "r") as f:
                combined_keymap["custom_defined_behaviors"] = f.read()
                logger.info("Restored custom_defined_behaviors.")
        except IOError as e:
            logger.error(f"Error reading {keymap_dtsi_path}: {e}")
    try:
        with open(output_file, "w") as f:
            json.dump(combined_keymap, f, indent=2)
            logger.info(f"Combined keymap saved to {output_file}")
    except IOError as e:
        logger.error(f"Failed to write combined keymap file {output_file}: {e}")


# --- Build Command Logic ---


def load_and_register_behaviors(profile: Profile):
    """Loads system behaviors from the profile and registers them."""
    behaviors_data = profile.load_system_behaviors()
    if not behaviors_data:
        logger.warning("No system behaviors found or loaded for the profile.")
        return

    logger.info(f"Registering {len(behaviors_data)} system behaviors...")
    for behavior_def in behaviors_data:
        name = behavior_def.get("name")
        expected_params = behavior_def.get("expected_params")
        # Use profile name as origin, or fallback if not defined
        origin = behavior_def.get("origin", f"system_{profile.name}")

        if not name or not name.startswith("&") or expected_params is None:
            logger.warning(
                f"Skipping invalid system behavior definition: {behavior_def}"
            )
            continue

        # TODO: Handle conditional registration based on 'condition' field if needed
        behaviors.register_behavior(name, expected_params, origin)


def check_and_prompt_overwrite(files: List[Path]) -> bool:
    """Checks if any file in the list exists and prompts user to overwrite."""
    # (Keep this function as is)
    existing_files = [f for f in files if f.exists()]
    if not existing_files:
        return True
    print("Warning: The following output files already exist:")
    for f in existing_files:
        print(f" - {f}")
    response = input("Do you want to overwrite these files? (y/N): ").strip().lower()
    if response == "y":
        return True
    else:
        logger.warning("Operation cancelled by user.")
        return False


# Removed find_default_file - template path comes from profile
# Removed find_default_config_dir - config paths come from profile
# Removed load_kconfig_mapping - loading is handled by profile instance


def build_keymap(
    json_data: Dict[str, Any],
    source_json_path: Optional[Path],  # Path to original file, or None if stdin
    target_prefix: str,
    resolved_profile: Profile,  # Pass the resolved profile instance
):
    """
    Builds .keymap and .conf files from JSON data using a resolved configuration profile.

    Args:
        json_data (Dict[str, Any]): The loaded keymap JSON data.
        source_json_path (Optional[Path]): Path to the original input JSON file, or None if from stdin.
        target_prefix (str): The base path and name for output files (e.g., "config/glove80").
        resolved_profile (Profile): The resolved profile instance containing config paths and settings.
    """
    # --- Get paths and data from the resolved profile ---
    template_path = resolved_profile.get_absolute_path("template_file")
    kconfig_map_path = resolved_profile.get_absolute_path("kconfig_map_file")
    layout_path = resolved_profile.get_absolute_path("layout_file")
    key_pos_header_path = resolved_profile.get_absolute_path("key_position_header_file")
    system_behaviors_dts_path = resolved_profile.get_absolute_path(
        "system_behaviors_dts_file"
    )

    if not template_path or not template_path.is_file():
        logger.error(
            f"Template file '{resolved_profile.template_file}' not found via profile '{resolved_profile.name}'. Searched at: {template_path}"
        )
        return
    if not kconfig_map_path or not kconfig_map_path.is_file():
        logger.error(
            f"Kconfig mapping file '{resolved_profile.kconfig_map_file}' not found via profile '{resolved_profile.name}'. Searched at: {kconfig_map_path}"
        )
        return
    if not layout_path or not layout_path.is_file():
        logger.error(
            f"Layout file '{resolved_profile.layout_file}' not found via profile '{resolved_profile.name}'. Searched at: {layout_path}"
        )
        return
    # key_pos_header and system_behaviors_dts are optional files, loaded later if path exists

    logger.info(f"Using configuration profile: {resolved_profile.name}")
    logger.info(f"  Template: {template_path}")
    logger.info(f"  Kconfig Map: {kconfig_map_path}")
    logger.info(f"  Layout: {layout_path}")
    logger.info(
        f"  Key Position Header: {key_pos_header_path or 'Not specified/found'}"
    )
    logger.info(
        f"  System Behaviors DTS: {system_behaviors_dts_path or 'Not specified/found'}"
    )

    # --- Load data using profile methods ---
    kconfig_map = resolved_profile.load_kconfig_map()
    if not kconfig_map:
        logger.error("Failed to load Kconfig map. Aborting build.")
        return

    # Load system behaviors JSON and register them *before* generating keymap
    load_and_register_behaviors(resolved_profile)

    # Load optional content files
    key_position_header_content = resolved_profile.load_key_position_header()
    system_behaviors_dts_content = resolved_profile.load_system_behaviors_dts()

    # --- Derive output paths ---
    target_prefix_path = Path(target_prefix)
    output_dir = target_prefix_path.parent
    base_name = target_prefix_path.name
    keymap_output_path = output_dir / f"{base_name}.keymap"
    conf_output_path = output_dir / f"{base_name}.conf"
    json_copy_path = output_dir / f"{base_name}.json"

    # Check for overwrite
    files_to_check = [
        keymap_output_path,
        conf_output_path,
        json_copy_path,
    ]
    if not check_and_prompt_overwrite(files_to_check):
        return

    # Create output directory
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Ensured output directory exists: {output_dir}")
    except OSError as e:
        logger.error(f"Failed to create output directory {output_dir}: {e}")
        return

    # --- Load Layout Config ---
    # Use the layout path from the profile and the loaded key position header content
    logger.info(f"Loading layout configuration from: {layout_path}")
    layout_config = layout.LayoutConfig.from_file(
        layout_path,
        key_position_header_content,  # Pass loaded content
    )
    if not layout_config:
        logger.error(
            f"Failed to load layout config from {layout_path}. Aborting build."
        )
        return

    # --- Generate .conf first (needed for conditional includes) ---
    logger.info(f"Generating Kconfig .conf file using map {kconfig_map_path}...")
    conf_content = ""
    kconfig_settings: Dict[str, str] = {}  # Store generated settings for include check
    try:
        conf_content, kconfig_settings = dtsi_builder.generate_kconfig_conf(
            json_data, kconfig_map
        )
        with open(conf_output_path, "w") as f:
            f.write(conf_content)
        logger.info(f"Successfully generated config and saved to {conf_output_path}")
    except Exception as e:
        logger.error(f"Failed to generate or write .conf file: {e}")
        # Continue to attempt keymap generation? Or return? Let's return for now.
        return

    # --- Resolve Includes based on generated Kconfig ---
    resolved_includes = resolved_profile.get_resolved_includes(kconfig_settings)
    logger.debug(f"Final resolved includes for template: {resolved_includes}")

    # --- Generate .keymap ---
    template_dir = template_path.parent
    template_name = template_path.name
    logger.info(f"Building .keymap using template {template_path}")
    try:
        # Pass necessary resolved data to the builder
        keymap_content = dtsi_builder.build_dtsi_from_json(
            json_data=json_data,
            template_dir=template_dir,
            template_name=template_name,
            layout_config=layout_config,
            resolved_includes=resolved_includes,
            key_position_header_content=key_position_header_content,  # Pass loaded content
            system_behaviors_dts_content=system_behaviors_dts_content,  # Pass loaded content
            # Pass the profile name for potential use in comments/headers
            profile_name=resolved_profile.name,
        )
        with open(keymap_output_path, "w") as f:
            f.write(keymap_content)
        logger.info(f"Successfully built keymap and saved to {keymap_output_path}")
    except Exception as e:
        logger.error(
            f"Failed to generate or write .keymap file: {e}", exc_info=True
        )  # Add traceback
        return

    # --- Save/Copy JSON to target directory ---
    if source_json_path:
        logger.info(f"Copying input JSON from {source_json_path} to {json_copy_path}")
        try:
            shutil.copy2(source_json_path, json_copy_path)
            logger.info("JSON file copied successfully.")
        except Exception as e:
            logger.error(f"Failed to copy JSON file: {e}")
    else:
        # Input was from stdin, write the processed data
        logger.info(f"Writing processed JSON data to {json_copy_path}")
        try:
            with open(json_copy_path, "w") as f:
                json.dump(json_data, f, indent=2)
            logger.info("JSON data written successfully.")
        except Exception as e:
            logger.error(f"Failed to write JSON data: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Extract, combine, finish, or build ZMK keymap files."
    )
    subparsers = parser.add_subparsers(
        dest="command", help="Command to execute", required=True
    )

    # --- Extract command ---
    extract_parser = subparsers.add_parser(
        "extract", help="Extract layers and base config from a keymap file"
    )
    extract_parser.add_argument(
        "keymap_file", type=Path, help="Path to the input keymap JSON file"
    )
    extract_parser.add_argument(
        "output_dir", type=Path, help="Directory to save the extracted files"
    )

    # --- Combine command ---
    combine_parser = subparsers.add_parser(
        "combine", help="Combine layers from a directory based on base.json structure"
    )
    combine_parser.add_argument(
        "input_dir",
        type=Path,
        help="Directory containing base.json and layers/ subdirectory",
    )
    combine_parser.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="Path to save the combined keymap JSON file",
    )

    # --- Finish command ---
    finish_parser = subparsers.add_parser(
        "finish",
        help="Add device tree and keymap behaviors (DTSI files) to a keymap JSON file",
    )
    finish_parser.add_argument(
        "keymap_file",
        type=Path,
        help="Path to the keymap JSON file (defaults to keymap.json)",
        nargs="?",
        default=Path("keymap.json"),
    )
    finish_parser.add_argument(
        "--device",
        "-d",
        type=Path,
        help="Path to the device.dtsi file (optional)",
        default=None,
    )
    finish_parser.add_argument(
        "--keymap",
        "-k",
        type=Path,
        help="Path to the keymap.dtsi file (optional)",
        default=None,
    )
    finish_parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Path to save the updated keymap JSON file (defaults to overwriting input)",
        default=None,
    )

    # --- List Profiles command ---
    list_parser = subparsers.add_parser(
        "list-profiles",
        help="List available firmware profile names that can be used with the build command.",
    )
    # No arguments needed for list-profiles

    # --- Build command (Updated) ---
    build_parser = subparsers.add_parser(
        "build",
        help="Build .keymap, .conf, and default.nix files from JSON using a configuration profile.",
    )
    build_parser.add_argument(
        "json_file",
        type=str,  # Accept string to handle '-' for stdin easily
        nargs="?",
        help="Path to the input keymap JSON file. Use '-' or omit to read from stdin.",
        default=None,
    )
    build_parser.add_argument(
        "target_prefix",
        type=str,
        help='Target directory and base filename for output (e.g., "config/my_glove80"). The directory will be created if it doesn\'t exist.',
    )
    build_parser.add_argument(
        "--firmware-name",
        "-f",
        type=str,
        required=True,
        help="Firmware name to match against profile patterns (e.g., 'v25.05', 'glove80/mybranch'). Determines which configuration profile to use.",
    )
    # Removed --template and --config-dir arguments

    # Common options
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Set logging level
    log_level = logging.DEBUG if args.verbose else logging.INFO
    if not logger.hasHandlers():
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
    else:
        logger.setLevel(log_level)
        [h.setLevel(log_level) for h in logger.handlers]

    if args.command == "extract":
        extract_layers(args.keymap_file, args.output_dir)
    elif args.command == "combine":
        combine_layers(args.input_dir, args.output)
    elif args.command == "finish":
        finish(args.keymap_file, args.device, args.keymap, args.output)
    elif args.command == "build":
        # --- Resolve Profile ---
        resolver = ProfileResolver()  # Use default base package
        resolved_profile = resolver.resolve(args.firmware_name)

        if not resolved_profile:
            logger.error(
                f"Could not find or resolve a profile for firmware '{args.firmware_name}'."
            )
            logger.info(f"Available profiles: {resolver.list_available_profiles()}")
            exit(1)

        # --- Load JSON data (from file or stdin) ---
        json_data = None
        source_json_path: Optional[Path] = None  # Path object or None

        if args.json_file is None or args.json_file == "-":
            logger.info("Reading keymap JSON from stdin...")
            source_json_path = None
            try:
                json_data = json.load(sys.stdin)
                logger.info("Successfully parsed JSON from stdin.")
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding JSON from stdin: {e}")
                exit(1)
            except Exception as e:
                logger.error(f"Error reading from stdin: {e}")
                exit(1)
        else:
            source_json_path = Path(args.json_file)
            if not source_json_path.is_file():
                logger.error(f"Input JSON file not found: {source_json_path}")
                exit(1)
            logger.info(f"Reading keymap JSON from file: {source_json_path}")
            try:
                with open(source_json_path, "r") as f:
                    json_data = json.load(f)
                logger.info("Successfully parsed JSON from file.")
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding JSON from file {source_json_path}: {e}")
                exit(1)
            except IOError as e:
                logger.error(f"Error reading file {source_json_path}: {e}")
                exit(1)

        # --- Call build_keymap ---
        build_keymap(
            json_data=json_data,
            source_json_path=source_json_path,
            target_prefix=args.target_prefix,
            resolved_profile=resolved_profile,  # Pass the instance
        )
    elif args.command == "list-profiles":
        resolver = ProfileResolver()
        available_profiles = resolver.list_available_profiles()
        if available_profiles:
            print("Available firmware profile names:")
            for name in sorted(available_profiles):
                print(f"  - {name}")
        else:
            print("No configuration profiles found.")
    else:
        # This should not be reachable if a command is required, but good practice
        parser.print_help()


if __name__ == "__main__":
    main()
