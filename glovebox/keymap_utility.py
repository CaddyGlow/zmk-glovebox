# glovebox/glovebox/keymap_utility.py

import json
import os
import argparse
import re
import logging
import shutil
import importlib.resources  # Now used for template AND map
import sys  # For stdin handling
from pathlib import Path
from typing import List, Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from glovebox import layout

from . import dtsi_builder
from . import file_utils

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


def find_default_file(package: str, resource_name: str) -> Optional[Path]:
    """Tries to find a default file within the package."""
    try:
        # Use 'files()' for Python 3.9+ recomme
        template_res = importlib.resources.files(package).joinpath(resource_name)
        with importlib.resources.as_file(template_res) as f:
            return f
    except FileNotFoundError:
        logger.warning(
            f"Default resource '{resource_name}' not found in package '{package}'."
        )
        return None
    except Exception as e:
        logger.warning(f"Error finding default resource '{resource_name}': {e}")
        return None


def find_default_config_dir() -> Optional[Path]:
    """Tries to find the default config directory within the package."""
    try:
        # Navigate through the package structure
        config_res = importlib.resources.files("glovebox").joinpath(
            "config/glove80/v25.05"
        )
        # Ensure it's treated as a file path context
        with importlib.resources.as_file(config_res) as f:
            if f.is_dir():
                return f
            else:
                logger.warning(
                    f"Default config resource found but is not a directory: {f}"
                )
                return None
    except FileNotFoundError:
        logger.warning(
            "Default config directory 'glovebox/config/glove80/v25.05' not found in package."
        )
        return None
    except Exception as e:
        logger.warning(f"Error finding default config directory: {e}")
        return None


def load_kconfig_mapping(map_file: Path) -> Dict:
    """Loads the Kconfig mapping JSON file."""
    if not map_file or not map_file.is_file():
        logger.error(f"Kconfig mapping file not found: {map_file}")
        return {}
    try:
        with open(map_file, "r") as f:
            mapping = json.load(f)
        logger.info(f"Loaded Kconfig mapping from: {map_file}")
        return mapping
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from Kconfig mapping file {map_file}: {e}")
        return {}
    except IOError as e:
        logger.error(f"Error reading Kconfig mapping file {map_file}: {e}")
        return {}


def build_keymap(
    json_data: Dict[str, Any],
    source_json_path: Optional[Path],  # Path to original file, or None if stdin
    target_prefix: str,
    template_file: Path,
    config_dir: Path,
):
    """
    Builds .keymap and .conf files from JSON data and template, copies original JSON (if applicable), using config files from config_dir.

    Args:
        json_data (Dict[str, Any]): The loaded keymap JSON data.
        source_json_path (Optional[Path]): Path to the original input JSON file, or None if from stdin.
        target_prefix (str): The base path and name for output files (e.g., "config/glove80").
        template_file (Path): Path to the Jinja2 template file.
        config_dir (Path): Path to the directory containing config files (kconfig_mapping.json, etc.).
    """
    # Input JSON data is already loaded
    if not template_file.is_file():
        logger.error(f"Template file not found: {template_file}")
        return
    if not config_dir.is_dir():
        logger.error(
            f"Configuration directory not found or not a directory: {config_dir}"
        )
        return
    # Kconfig map existence checked later in load_kconfig_mapping

    # Derive output paths
    target_prefix_path = Path(target_prefix)
    output_dir = target_prefix_path.parent
    base_name = target_prefix_path.name
    keymap_output_path = output_dir / f"{base_name}.keymap"
    conf_output_path = output_dir / f"{base_name}.conf"
    json_copy_path = output_dir / f"{base_name}.json"
    nix_output_path = output_dir / "default.nix"  # Nix output file

    # Check for overwrite
    files_to_check = [
        keymap_output_path,
        conf_output_path,
        json_copy_path,
        nix_output_path,
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

    # --- Read Optional Configuration Files (using the provided config_dir) ---
    system_behaviors_content = file_utils.read_optional_file(
        config_dir / "system_behaviors.dts", "system behaviors"
    )
    key_position_defines_content = file_utils.read_optional_file(
        config_dir / "key_position.h", "key position defines"
    )

    # Read LayoutConfig
    layout_map_file = config_dir / ".." / ".." / "layout" / "glove80.json"
    layout_config = layout.LayoutConfig.from_file(
        layout_map_file, key_position_defines_content
    )

    # Read Kconfig map (JSON data is already passed in)
    kconfig_map_file = config_dir / "kconfig_mapping.json"
    kconfig_map = load_kconfig_mapping(kconfig_map_file)
    if not kconfig_map:  # Exit if map loading failed
        logger.error(
            f"Kconfig mapping could not be loaded from {kconfig_map_file}. Aborting build."
        )
        return

    # Input listeners are generated from JSON, not read from a file.

    # --- Generate .keymap ---
    template_dir = template_file.parent
    template_name = template_file.name
    logger.info(f"Building .keymap from using template {template_file}")
    try:
        keymap_content = dtsi_builder.build_dtsi_from_json(
            json_data,
            template_dir,
            template_name,
            layout_config,
            system_behaviors_content, # Pass the read content
            key_position_defines_content,
            # input_listeners_content is removed, generated internally now
        )
        with open(keymap_output_path, "w") as f:
            f.write(keymap_content)
        logger.info(f"Successfully built keymap and saved to {keymap_output_path}")
    except Exception as e:
        logger.error(f"Failed to generate or write .keymap file: {e}", e)
        return

    # --- Generate .conf ---
    logger.info(f"Generating Kconfig .conf file using map {kconfig_map_file}...")
    try:
        conf_content = dtsi_builder.generate_kconfig_conf(
            json_data, kconfig_map
        )  # Pass loaded map
        with open(conf_output_path, "w") as f:
            f.write(conf_content)
        logger.info(f"Successfully generated config and saved to {conf_output_path}")
    except Exception as e:
        logger.error(f"Failed to generate or write .conf file: {e}")

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

    # --- Generate default.nix ---
    nix_template_path = template_dir / "default.nix.j2"
    if nix_template_path.is_file():
        logger.info(
            f"Found Nix template: {nix_template_path}. Generating default.nix..."
        )
        try:
            # Setup Jinja env specifically for this template

            env = Environment(
                loader=FileSystemLoader(template_dir),
                trim_blocks=True,
                lstrip_blocks=True,
            )
            nix_template = env.get_template("default.nix.j2")
            nix_context = {"base_name": base_name}
            nix_content = nix_template.render(nix_context)
            with open(nix_output_path, "w") as f:
                f.write(nix_content)
            logger.info(
                f"Successfully generated Nix file and saved to {nix_output_path}"
            )
        except TemplateNotFound:
            # Should not happen due to is_file() check, but good practice
            logger.error(
                f"Nix template '{nix_template_path.name}' disappeared unexpectedly."
            )
        except Exception as e:
            logger.error(f"Failed to generate or write default.nix file: {e}")
    else:
        logger.info(
            f"Optional Nix template not found at {nix_template_path}. Skipping default.nix generation."
        )


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

    # --- Build command (Updated with --kconfig-map) ---
    build_parser = subparsers.add_parser(
        "build",
        help="Build .keymap, .conf, and default.nix files from JSON.",
    )
    build_parser.add_argument(
        "json_file",
        type=Path,
        nargs="?",  # Make it optional
        help="Path to the input keymap JSON file. Use '-' or omit to read from stdin.",
        default=None,  # Default to None if omitted
    )
    build_parser.add_argument(
        "target_prefix",
        type=str,
        help='Target directory and base filename (e.g., "config/my_glove80")',
    )
    build_parser.add_argument(
        "--template",
        "-t",
        type=Path,
        help="Path to the Jinja2 template file (e.g., zmk_keymap.dtsi.j2). Defaults to internal template.",
        default=None,
    )
    build_parser.add_argument(
        "--config-dir",
        "-c",
        type=Path,
        help="Path to the directory containing configuration files (kconfig_mapping.json, system_behaviors.dts, etc.). Defaults to internal glove80/v25.05 config.",
        default=None,
    )

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
        # Resolve template path
        template_path = args.template
        if not template_path:
            logger.info("Template path not specified, searching for default...")
            # Assumes templates are in 'glovebox/templates' relative to package
            template_path = find_default_file(
                "glovebox.templates", "zmk_keymap.dtsi.j2"
            )
            if not template_path or not template_path.is_file():
                logger.error(
                    "Default template could not be found or is not a file. Please specify one with --template."
                )
                exit(1)
            logger.info(f"Using default template: {template_path}")

        # Resolve Config Directory path
        config_dir_path = args.config_dir
        if not config_dir_path:
            logger.info("Config directory not specified, searching for default...")
            config_dir_path = find_default_config_dir()
            if not config_dir_path or not config_dir_path.is_dir():
                logger.error(
                    "Default config directory could not be found or is not a directory. Please specify one with --config-dir."
                )
                exit(1)
            logger.info(f"Using default config directory: {config_dir_path}")
        elif not config_dir_path.is_dir():
            logger.error(
                f"Specified config directory not found or is not a directory: {config_dir_path}"
            )
            exit(1)

        # Load JSON data (from file or stdin)
        json_data = None
        source_json_path = args.json_file  # Keep track of original path or None

        if source_json_path is None or str(source_json_path) == "-":
            logger.info("Reading keymap JSON from stdin...")
            source_json_path = None  # Explicitly set to None for stdin case
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

        # Call build_keymap with loaded data and source path
        build_keymap(
            json_data,
            source_json_path,
            args.target_prefix,
            template_path,
            config_dir_path,
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
