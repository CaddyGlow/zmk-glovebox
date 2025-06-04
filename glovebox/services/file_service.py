"""File service for keymap file manipulation operations."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from glovebox.adapters.file_adapter import FileAdapter
from glovebox.core.errors import KeymapError
from glovebox.models.keymap import KeymapData
from glovebox.models.results import KeymapResult


logger = logging.getLogger(__name__)


class KeymapFileService:
    """Service for keymap file extraction and combination operations."""

    def __init__(self, file_adapter: FileAdapter | None = None):
        """Initialize with file adapter dependency."""
        if file_adapter is None:
            from glovebox.adapters.file_adapter import create_file_adapter

            file_adapter = create_file_adapter()
        self._file_adapter = file_adapter

    def extract_layers(self, keymap_file: Path, output_dir: Path) -> KeymapResult:
        """
        Extracts each layer from a keymap JSON file into separate files within a 'layers'
        subdirectory. Also extracts a 'base.json' file containing the remaining configuration
        and saves any 'custom_devicetree' and 'custom_defined_behaviors' content into
        'device.dtsi' and 'keymap.dtsi' respectively.

        Structure created in output_dir:
        - base.json
        - device.dtsi (if custom_devicetree exists)
        - keymap.dtsi (if custom_defined_behaviors exists)
        - layers/
            - <layer_name_0>.json
            - <layer_name_1>.json
            - ...

        Args:
            keymap_file: Path to the input keymap JSON file.
            output_dir: Directory where the extracted structure will be created.

        Returns:
            KeymapResult with extraction information

        Raises:
            KeymapError: If the input file is invalid, data is inconsistent, or writing fails.
        """
        result = KeymapResult(success=False)

        if not self._file_adapter.is_file(keymap_file):
            raise KeymapError(f"Keymap file not found: {keymap_file}")

        output_dir = output_dir.resolve()
        output_layer_dir = output_dir / "layers"

        try:
            logger.info(
                f"Creating output directories: {output_dir} and {output_layer_dir}"
            )
            self._file_adapter.mkdir(output_dir)
            self._file_adapter.mkdir(output_layer_dir)
        except Exception as e:
            raise KeymapError(f"Failed to create output directories: {e}") from e

        try:
            logger.info(f"Loading keymap data from {keymap_file}")
            keymap_dict = self._file_adapter.read_json(keymap_file)

            # Validate the loaded dictionary using the Pydantic model
            logger.info("Validating loaded keymap data structure...")
            keymap_model = KeymapData.model_validate(keymap_dict)
            logger.debug("Keymap data validated successfully.")

            # Use the validated model's dict representation for further processing
            keymap = keymap_model.to_dict()

        except Exception as e:
            if "validation error" in str(e).lower():
                raise KeymapError(
                    f"Invalid keymap data structure in {keymap_file}: {e}"
                ) from e
            raise KeymapError(
                f"Unexpected error loading or validating keymap file {keymap_file}: {e}"
            ) from e

        # Extract custom DTSI snippets
        self._extract_dtsi_snippets(keymap, output_dir)

        # Extract base configuration
        self._extract_base(keymap, output_dir)

        # Extract individual layers
        self._extract_individual_layers(keymap, output_layer_dir, keymap_file)

        result.success = True
        result.layer_count = len(keymap.get("layers", []))
        result.add_message(f"Successfully extracted layers to {output_dir}")
        result.add_message(f"Created base.json and {result.layer_count} layer files")

        logger.info(f"Finished extracting layers to {output_dir}")
        return result

    def combine_layers(self, input_dir: Path, output_file: Path) -> KeymapResult:
        """
        Combines layer files from a specified directory structure back into a single
        keymap JSON file. It expects an input directory containing:
        - base.json: The base keymap configuration (metadata, macros, combos, etc.).
                     Must contain the 'layer_names' list defining the order.
        - layers/: A subdirectory containing individual JSON files for each layer,
                   named according to the sanitized layer names (e.g., 'DEFAULT.json', 'LOWER.json').
        - device.dtsi (optional): Contains custom device tree snippets.
        - keymap.dtsi (optional): Contains custom defined behaviors snippets.

        Args:
            input_dir: Path to the directory containing the 'base.json' and 'layers/' subdirectory.
            output_file: Path where the combined keymap JSON file will be saved.

        Returns:
            KeymapResult with combination information

        Raises:
            KeymapError: If required files/directories are missing, data is invalid, or writing fails.
        """
        result = KeymapResult(success=False)

        input_dir = input_dir.resolve()
        output_file = output_file.resolve()
        base_file = input_dir / "base.json"
        device_dtsi_path = input_dir / "device.dtsi"
        keymap_dtsi_path = input_dir / "keymap.dtsi"
        layers_dir = input_dir / "layers"

        logger.info(f"Combining layers from {input_dir} into {output_file}")

        if not self._file_adapter.is_file(base_file):
            raise KeymapError(f"Base file not found: {base_file}")
        if not self._file_adapter.is_dir(layers_dir):
            raise KeymapError(f"Layers directory not found: {layers_dir}")

        # Load base configuration
        combined_keymap = self._load_base_config(base_file)

        # Process layers
        self._process_layers(combined_keymap, layers_dir)

        # Add DTSI content
        self._add_dtsi_content(combined_keymap, device_dtsi_path, keymap_dtsi_path)

        # Write the final combined keymap
        self._write_combined_keymap(combined_keymap, output_file)

        result.success = True
        result.json_path = output_file
        result.layer_count = len(combined_keymap.get("layers", []))
        result.add_message(f"Successfully combined keymap and saved to {output_file}")
        result.add_message(f"Combined {result.layer_count} layers from {layers_dir}")

        return result

    def finish(
        self,
        keymap_file: Path,
        device_dtsi: Path | None = None,
        keymap_dtsi: Path | None = None,
        output_file: Path | None = None,
    ) -> KeymapResult:
        """
        Reads content from optional device.dtsi and keymap.dtsi files and adds it
        to the 'custom_devicetree' and 'custom_defined_behaviors' fields of a
        target keymap JSON file.

        Args:
            keymap_file: Path to the keymap JSON file to update.
            device_dtsi: Optional path to the file containing custom device tree snippets.
            keymap_dtsi: Optional path to the file containing custom defined behaviors snippets.
            output_file: Optional path to save the updated file. If None, overwrites the input keymap_file.

        Returns:
            KeymapResult with finish information

        Raises:
            KeymapError: If the input keymap file cannot be read/parsed or the output cannot be written.
        """
        result = KeymapResult(success=False)

        if not self._file_adapter.is_file(keymap_file):
            raise KeymapError(f"Keymap file not found: {keymap_file}")

        output_path = (output_file if output_file else keymap_file).resolve()
        logger.info(f"Finishing keymap: {keymap_file} -> {output_path}")

        # Load keymap
        keymap = self._load_keymap_file(keymap_file)

        # Add device tree content
        self._add_device_tree_content(keymap, device_dtsi)

        # Add keymap behaviors content
        self._add_keymap_behaviors_content(keymap, keymap_dtsi)

        # Write the updated keymap
        self._write_keymap_file(keymap, output_path)

        result.success = True
        result.json_path = output_path
        result.add_message(f"Successfully finished keymap and saved to {output_path}")

        return result

    # Private helper methods for extraction
    def _extract_dtsi_snippets(self, keymap: dict[str, Any], output_dir: Path) -> None:
        """Extract custom DTSI snippets to separate files."""
        devtree_dtsi = keymap.get("custom_devicetree", "")
        def_bev_dtsi = keymap.get("custom_defined_behaviors", "")

        try:
            device_dtsi_path = output_dir / "device.dtsi"
            if devtree_dtsi:
                self._file_adapter.write_text(device_dtsi_path, devtree_dtsi)
                logger.info(f"Extracted custom_devicetree to {device_dtsi_path}")
            else:
                logger.info("No custom_devicetree found to extract.")

            keymap_dtsi_path = output_dir / "keymap.dtsi"
            if def_bev_dtsi:
                self._file_adapter.write_text(keymap_dtsi_path, def_bev_dtsi)
                logger.info(f"Extracted custom_defined_behaviors to {keymap_dtsi_path}")
            else:
                logger.info("No custom_defined_behaviors found to extract.")

        except Exception as e:
            logger.warning(f"Failed to write DTSI snippets: {e}")

    def _extract_base(self, keymap: dict[str, Any], output_dir: Path) -> None:
        """Extract base configuration to base.json."""
        base_keymap = keymap.copy()

        # Define fields specific to layers or custom code that should be in layer files or separate snippets
        fields_to_empty = ["layers", "custom_defined_behaviors", "custom_devicetree"]
        base_keymap = self._empty_fields(base_keymap, fields_to_empty)

        # Ensure essential base fields exist, even if empty, for clarity
        if "layer_names" not in base_keymap:
            base_keymap["layer_names"] = []
        if "macros" not in base_keymap:
            base_keymap["macros"] = []
        if "combos" not in base_keymap:
            base_keymap["combos"] = []
        if "holdTaps" not in base_keymap:
            base_keymap["holdTaps"] = []
        if "kconfig" not in base_keymap:
            base_keymap["kconfig"] = {}

        # Explicitly convert datetime to ISO string for JSON serialization
        if isinstance(base_keymap.get("date"), datetime):
            base_keymap["date"] = base_keymap["date"].isoformat()
        elif "date" not in base_keymap:
            base_keymap["date"] = datetime.now().isoformat()

        output_file = output_dir / "base.json"
        try:
            self._file_adapter.write_json(output_file, base_keymap)
            logger.info(f"Extracted base configuration to {output_file}")
        except Exception as e:
            raise KeymapError(f"Failed to write base file {output_file}: {e}") from e

    def _extract_individual_layers(
        self, keymap: dict[str, Any], output_layer_dir: Path, keymap_file: Path
    ) -> None:
        """Extract individual layers to separate JSON files."""
        layer_names = keymap.get("layer_names", [])
        layers_structured = keymap.get("layers", [])

        if not layer_names:
            logger.warning(
                "No 'layer_names' found in keymap. Cannot extract individual layers."
            )
            return

        if not layers_structured:
            logger.warning(
                "No 'layers' data found in keymap. Cannot extract individual layers."
            )
            return

        logger.info(f"Extracting {len(layer_names)} layers...")
        original_date_str = keymap.get("date", datetime.now().isoformat())

        for i, layer_name in enumerate(layer_names):
            # Sanitize layer name for use as filename
            safe_layer_name = "".join(
                c if c.isalnum() or c in ["-", "_"] else "_" for c in layer_name
            )
            if not safe_layer_name:
                safe_layer_name = f"layer_{i}"

            # Get the corresponding layer data (bindings) from the structured list
            layer_bindings = []
            if i < len(layers_structured) and isinstance(layers_structured[i], list):
                layer_bindings = layers_structured[i]
            else:
                logger.error(
                    f"Could not find valid data for layer index {i} ('{layer_name}'). Skipping."
                )
                continue

            # Create a minimal keymap structure for the single layer
            layer_keymap = {
                "keyboard": keymap.get("keyboard", "unknown"),
                "firmware_api_version": keymap.get("firmware_api_version", "1"),
                "locale": keymap.get("locale", "en-US"),
                "uuid": "",
                "parent_uuid": keymap.get("uuid", ""),
                "date": original_date_str,
                "creator": keymap.get("creator", ""),
                "title": f"Layer: {layer_name}",
                "notes": f"Extracted layer '{layer_name}' from {keymap_file.name}",
                "tags": [layer_name.lower().replace("_", "-").replace(" ", "-")],
                "layer_names": [layer_name],
                "layers": [layer_bindings],
                "custom_defined_behaviors": "",
                "custom_devicetree": "",
                "kconfig": {},
                "macros": [],
                "combos": [],
                "holdTaps": [],
            }

            output_file = output_layer_dir / f"{safe_layer_name}.json"
            try:
                self._file_adapter.write_json(output_file, layer_keymap)
                logger.info(f"Extracted layer '{layer_name}' to {output_file}")
            except Exception as e:
                logger.error(f"Failed to write layer file {output_file}: {e}")

    # Private helper methods for combination
    def _load_base_config(self, base_file: Path) -> dict[str, Any]:
        """Load base configuration from file."""
        try:
            combined_keymap = self._file_adapter.read_json(base_file)
        except Exception as e:
            raise KeymapError(f"Error reading base file {base_file}: {e}") from e

        # Validate base structure
        if "layer_names" not in combined_keymap or not isinstance(
            combined_keymap["layer_names"], list
        ):
            raise KeymapError("Invalid or missing 'layer_names' list in base.json")

        return combined_keymap

    def _process_layers(
        self, combined_keymap: dict[str, Any], layers_dir: Path
    ) -> None:
        """Process and combine layer files."""
        combined_keymap["layers"] = []
        layer_names = combined_keymap["layer_names"]
        logger.info(
            f"Expecting {len(layer_names)} layers based on base.json: {layer_names}"
        )

        # Determine expected number of keys per layer
        num_keys = self._determine_key_count(layer_names, layers_dir)
        empty_layer = [{"value": "&none", "params": []} for _ in range(num_keys)]

        found_layer_count = 0

        # Process each layer defined in base.json
        for i, layer_name in enumerate(layer_names):
            safe_layer_name = "".join(
                c if c.isalnum() or c in ["-", "_"] else "_" for c in layer_name
            )
            if not safe_layer_name:
                safe_layer_name = f"layer_{i}"
            layer_file = layers_dir / f"{safe_layer_name}.json"

            if not self._file_adapter.is_file(layer_file):
                logger.warning(
                    f"Layer file '{layer_file.name}' not found for layer '{layer_name}'. Adding empty layer."
                )
                combined_keymap["layers"].append(empty_layer)
                continue

            logger.info(f"Processing layer '{layer_name}' from file: {layer_file.name}")

            try:
                layer_content = self._load_layer_file(
                    layer_file, layer_name, num_keys, empty_layer
                )
                combined_keymap["layers"].append(layer_content)
                logger.info(f"Added layer '{layer_name}' (index {i})")
                found_layer_count += 1
            except Exception as e:
                logger.error(
                    f"Error processing layer file {layer_file.name}: {e}. Adding empty layer."
                )
                combined_keymap["layers"].append(empty_layer)

        logger.info(
            f"Successfully processed {found_layer_count} out of {len(layer_names)} expected layers."
        )

    def _determine_key_count(self, layer_names: list, layers_dir: Path) -> int:
        """Determine expected number of keys per layer."""
        num_keys = 80  # Default for Glove80

        if layer_names:
            first_layer_name = layer_names[0]
            safe_first_layer_name = "".join(
                c if c.isalnum() or c in ["-", "_"] else "_" for c in first_layer_name
            )
            if not safe_first_layer_name:
                safe_first_layer_name = "layer_0"
            first_layer_file = layers_dir / f"{safe_first_layer_name}.json"

            if self._file_adapter.is_file(first_layer_file):
                try:
                    first_layer_data = self._file_adapter.read_json(first_layer_file)
                    if (
                        first_layer_data.get("layers")
                        and isinstance(first_layer_data["layers"], list)
                        and first_layer_data["layers"]
                    ):
                        num_keys = len(first_layer_data["layers"][0])
                        logger.info(
                            f"Determined expected key count per layer: {num_keys} (from {first_layer_file})"
                        )
                except Exception as e:
                    logger.warning(
                        f"Could not determine key count from {first_layer_file}, using default {num_keys}. Error: {e}"
                    )
            else:
                logger.warning(
                    f"First layer file {first_layer_file} not found, using default key count {num_keys}."
                )

        return num_keys

    def _load_layer_file(
        self, layer_file: Path, layer_name: str, num_keys: int, empty_layer: list
    ) -> list:
        """Load and process a single layer file."""
        layer_data = self._file_adapter.read_json(layer_file)

        # Find the actual layer data within the layer file
        if (
            "layers" in layer_data
            and isinstance(layer_data["layers"], list)
            and layer_data["layers"]
        ):
            actual_layer_content = layer_data["layers"][0]

            if len(actual_layer_content) != num_keys:
                logger.warning(
                    f"Layer '{layer_name}' from {layer_file.name} has {len(actual_layer_content)} keys, "
                    f"expected {num_keys}. Padding/truncating."
                )
                # Pad or truncate the layer to match expected size
                actual_layer_content = (actual_layer_content + empty_layer)[:num_keys]

            return actual_layer_content
        else:
            logger.warning(
                f"Layer data missing or invalid in {layer_file.name} for layer '{layer_name}'. Using empty layer."
            )
            return empty_layer

    def _add_dtsi_content(
        self,
        combined_keymap: dict[str, Any],
        device_dtsi_path: Path,
        keymap_dtsi_path: Path,
    ) -> None:
        """Add DTSI content to combined keymap."""
        # Read device.dtsi if exists
        if self._file_adapter.is_file(device_dtsi_path):
            try:
                combined_keymap["custom_devicetree"] = self._file_adapter.read_text(
                    device_dtsi_path
                )
                logger.info("Restored custom_devicetree from device.dtsi.")
            except Exception as e:
                logger.warning(f"Error reading {device_dtsi_path}: {e}")
        else:
            if "custom_devicetree" not in combined_keymap:
                combined_keymap["custom_devicetree"] = ""

        # Read keymap.dtsi if exists
        if self._file_adapter.is_file(keymap_dtsi_path):
            try:
                combined_keymap["custom_defined_behaviors"] = (
                    self._file_adapter.read_text(keymap_dtsi_path)
                )
                logger.info("Restored custom_defined_behaviors from keymap.dtsi.")
            except Exception as e:
                logger.warning(f"Error reading {keymap_dtsi_path}: {e}")
        else:
            if "custom_defined_behaviors" not in combined_keymap:
                combined_keymap["custom_defined_behaviors"] = ""

    def _write_combined_keymap(
        self, combined_keymap: dict[str, Any], output_file: Path
    ) -> None:
        """Write the final combined keymap to file."""
        try:
            self._file_adapter.mkdir(output_file.parent)
            self._file_adapter.write_json(output_file, combined_keymap)
            logger.info(f"Combined keymap saved successfully to {output_file}")
        except Exception as e:
            raise KeymapError(
                f"Failed to write combined keymap file {output_file}: {e}"
            ) from e

    # Private helper methods for finish operation
    def _load_keymap_file(self, keymap_file: Path) -> dict[str, Any]:
        """Load keymap from file."""
        try:
            return self._file_adapter.read_json(keymap_file)
        except Exception as e:
            raise KeymapError(f"Error reading keymap file {keymap_file}: {e}") from e

    def _add_device_tree_content(
        self, keymap: dict[str, Any], device_dtsi: Path | None
    ) -> None:
        """Add device tree content to keymap."""
        if device_dtsi:
            device_dtsi = device_dtsi.resolve()
            if self._file_adapter.is_file(device_dtsi):
                logger.info(f"Reading device tree from {device_dtsi}")
                try:
                    keymap["custom_devicetree"] = self._file_adapter.read_text(
                        device_dtsi
                    )
                except Exception as e:
                    logger.warning(f"Error reading device tree file {device_dtsi}: {e}")
                    keymap["custom_devicetree"] = ""
            else:
                logger.warning(f"Device tree file not found, skipping: {device_dtsi}")
                keymap["custom_devicetree"] = ""
        elif "custom_devicetree" not in keymap:
            keymap["custom_devicetree"] = ""

    def _add_keymap_behaviors_content(
        self, keymap: dict[str, Any], keymap_dtsi: Path | None
    ) -> None:
        """Add keymap behaviors content to keymap."""
        if keymap_dtsi:
            keymap_dtsi = keymap_dtsi.resolve()
            if self._file_adapter.is_file(keymap_dtsi):
                logger.info(f"Reading keymap behaviors from {keymap_dtsi}")
                try:
                    keymap["custom_defined_behaviors"] = self._file_adapter.read_text(
                        keymap_dtsi
                    )
                except Exception as e:
                    logger.warning(
                        f"Error reading keymap behaviors file {keymap_dtsi}: {e}"
                    )
                    keymap["custom_defined_behaviors"] = ""
            else:
                logger.warning(
                    f"Keymap behaviors file not found, skipping: {keymap_dtsi}"
                )
                keymap["custom_defined_behaviors"] = ""
        elif "custom_defined_behaviors" not in keymap:
            keymap["custom_defined_behaviors"] = ""

    def _write_keymap_file(self, keymap: dict[str, Any], output_path: Path) -> None:
        """Write keymap to file."""
        try:
            if output_path.parent != Path():
                self._file_adapter.mkdir(output_path.parent)

            self._file_adapter.write_json(output_path, keymap)
            logger.info(f"Updated keymap saved to {output_path}")
        except Exception as e:
            raise KeymapError(
                f"Failed to write updated keymap file {output_path}: {e}"
            ) from e

    # Shared utility methods
    def _empty_fields(
        self, keymap_data: dict[str, Any], fields_to_empty: list[str]
    ) -> dict[str, Any]:
        """Sets specified fields in the keymap dictionary to empty values."""
        keymap_dict = keymap_data.copy()

        for field in fields_to_empty:
            if field in keymap_dict:
                if isinstance(keymap_dict[field], list):
                    keymap_dict[field] = []
                elif isinstance(keymap_dict[field], dict):
                    keymap_dict[field] = {}
                elif isinstance(keymap_dict[field], str):
                    keymap_dict[field] = ""

        return keymap_dict


def create_file_service(
    file_adapter: FileAdapter | None = None,
) -> KeymapFileService:
    """Create a KeymapFileService instance.

    Args:
        file_adapter: Optional file adapter (creates default if None)

    Returns:
        KeymapFileService instance
    """
    return KeymapFileService(file_adapter)
