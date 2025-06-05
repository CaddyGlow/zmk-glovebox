"""Service for keymap component extraction and management."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, TypeAlias

from glovebox.adapters.file_adapter import FileAdapter
from glovebox.core.errors import KeymapError
from glovebox.models.keymap import KeymapData, KeymapMetadata
from glovebox.models.results import KeymapResult
from glovebox.services.base_service import BaseServiceImpl
from glovebox.utils.file_utils import sanitize_filename


logger = logging.getLogger(__name__)


# Type alias for result dictionaries
ResultDict: TypeAlias = dict[str, Any]


class KeymapComponentService(BaseServiceImpl):
    """Service for extracting and combining keymap components.

    Responsible for splitting keymaps into individual layers and files,
    and recombining those files into complete keymap data.
    """

    def __init__(self, file_adapter: FileAdapter):
        """Initialize keymap component service with adapter dependencies."""
        super().__init__(service_name="KeymapComponentService", service_version="1.0.0")
        self._file_adapter = file_adapter

    def extract_components(self, keymap: KeymapData, output_dir: Path) -> KeymapResult:
        """Extract keymap into individual components and layers.

        Args:
            keymap: Keymap data model
            output_dir: Directory to write extracted components

        Returns:
            KeymapResult with extraction information

        Raises:
            KeymapError: If extraction fails
        """
        logger.info("Extracting keymap components to %s", output_dir)

        result = KeymapResult(success=False)

        try:
            # Create output directories
            output_dir = output_dir.resolve()
            output_layer_dir = output_dir / "layers"
            self._file_adapter.mkdir(output_dir)
            self._file_adapter.mkdir(output_layer_dir)

            # Convert to dictionary for processing (future: refactor internal methods)
            keymap_dict = keymap.model_dump()

            # Extract components
            self._extract_dtsi_snippets(keymap_dict, output_dir)
            self._extract_metadata_config(keymap_dict, output_dir)
            self._extract_individual_layers(keymap_dict, output_layer_dir)

            result.success = True
            result.layer_count = len(keymap.layers)
            result.add_message(f"Successfully extracted layers to {output_dir}")
            result.add_message(
                f"Created metadata.json and {result.layer_count} layer files"
            )

            return result

        except Exception as e:
            result.add_error(f"Layer extraction failed: {e}")
            logger.error("Layer extraction failed: %s", e)
            raise KeymapError(f"Layer extraction failed: {e}") from e

    def combine_components(
        self, metadata_keymap: KeymapData, layers_dir: Path
    ) -> ResultDict:
        """Combine extracted components into a complete keymap.

        Args:
            base_keymap: Base keymap data model without layers
            layers_dir: Directory containing individual layer files

        Returns:
            Combined keymap dictionary

        Raises:
            KeymapError: If combination fails
        """
        logger.info("Combining layers from %s", layers_dir)

        layers_dir = layers_dir.resolve()

        # Validate directory existence
        if not self._file_adapter.is_dir(layers_dir):
            raise KeymapError(f"Layers directory not found: {layers_dir}")

        # Make a copy of the metadata keymap as dictionary for processing
        combined_keymap = metadata_keymap.model_dump()

        # Process layers
        self._process_layers_for_combination(combined_keymap, layers_dir)

        # Add DTSI content from separate files
        parent_dir = layers_dir.parent
        self._add_dtsi_content_from_files(combined_keymap, parent_dir)

        logger.info(
            "Successfully combined %d layers", len(combined_keymap.get("layers", []))
        )

        return combined_keymap

    # Private helper methods for extraction

    def _extract_dtsi_snippets(self, keymap: dict[str, Any], output_dir: Path) -> None:
        """Extract custom DTSI snippets to separate files.

        Args:
            keymap: Keymap data
            output_dir: Directory to write snippet files
        """
        device_dtsi = keymap.get("custom_devicetree", "")
        behaviors_dtsi = keymap.get("custom_defined_behaviors", "")

        if device_dtsi:
            device_dtsi_path = output_dir / "device.dtsi"
            self._file_adapter.write_text(device_dtsi_path, device_dtsi)
            logger.info("Extracted custom_devicetree to %s", device_dtsi_path)

        if behaviors_dtsi:
            keymap_dtsi_path = output_dir / "keymap.dtsi"
            self._file_adapter.write_text(keymap_dtsi_path, behaviors_dtsi)
            logger.info("Extracted custom_defined_behaviors to %s", keymap_dtsi_path)

    def _extract_metadata_config(
        self, keymap: dict[str, Any], output_dir: Path
    ) -> None:
        """Extract metadata configuration to metadata.json.

        Args:
            keymap: Keymap data
            output_dir: Directory to write metadata configuration
        """
        # Create a KeymapData model from the keymap data, which includes all metadata fields
        full_keymap = KeymapData.model_validate(keymap)

        # Extract just the KeymapMetadata portion
        # Since KeymapData inherits from KeymapMetadata, we can use model_dump
        # with include to get just the base class fields
        metadata_dict = full_keymap.model_dump(
            mode="json", by_alias=True, include=set(KeymapMetadata.model_fields.keys())
        )

        # Add empty layers list
        metadata_dict["layers"] = []

        output_file = output_dir / "metadata.json"
        self._file_adapter.write_json(output_file, metadata_dict)
        logger.info("Extracted metadata configuration to %s", output_file)

    def _extract_individual_layers(
        self, keymap: dict[str, Any], output_layer_dir: Path
    ) -> None:
        """Extract individual layers to separate JSON files.

        Args:
            keymap: Keymap data
            output_layer_dir: Directory to write individual layer files
        """
        layer_names = keymap.get("layer_names", [])
        layers_data = keymap.get("layers", [])

        if not layer_names or not layers_data:
            logger.warning(
                "No layer names or data found. Cannot extract individual layers."
            )
            return

        logger.info("Extracting %d layers...", len(layer_names))

        # Get original date or use current date
        original_date_str = keymap.get("date") or datetime.now().isoformat()

        for i, layer_name in enumerate(layer_names):
            # Sanitize layer name for filename
            safe_layer_name = sanitize_filename(layer_name)
            if not safe_layer_name:
                safe_layer_name = f"layer_{i}"

            # Get layer bindings
            layer_bindings = []
            if i < len(layers_data):
                layer_bindings = layers_data[i]
            else:
                logger.error(
                    "Could not find data for layer index %d ('%s'). Skipping.",
                    i,
                    layer_name,
                )
                continue

            # Create minimal keymap structure for the single layer
            layer_keymap: dict[str, Any] = {
                "keyboard": keymap.get("keyboard", "unknown"),
                "firmware_api_version": keymap.get("firmware_api_version", "1"),
                "locale": keymap.get("locale", "en-US"),
                "uuid": "",
                "parent_uuid": keymap.get("uuid", ""),
                "date": original_date_str,
                "creator": keymap.get("creator", ""),
                "title": f"Layer: {layer_name}",
                "notes": f"Extracted layer '{layer_name}'",
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
            self._file_adapter.write_json(output_file, layer_keymap)
            logger.info("Extracted layer '%s' to %s", layer_name, output_file)

    # Helper methods for layer combination

    def _process_layers_for_combination(
        self, combined_keymap: dict[str, Any], layers_dir: Path
    ) -> None:
        """Process and combine layer files.

        Args:
            combined_keymap: Base keymap data to which layers will be added
            layers_dir: Directory containing layer files
        """
        combined_keymap["layers"] = []
        layer_names = combined_keymap.get("layer_names", [])
        logger.info(
            "Expecting %d layers based on metadata.json: %s",
            len(layer_names),
            layer_names,
        )

        # Determine expected number of keys per layer
        num_keys = 80  # Default for Glove80
        empty_layer = [{"value": "&none", "params": []} for _ in range(num_keys)]

        found_layer_count = 0

        for i, layer_name in enumerate(layer_names):
            safe_layer_name = sanitize_filename(layer_name)
            if not safe_layer_name:
                safe_layer_name = f"layer_{i}"
            layer_file = layers_dir / f"{safe_layer_name}.json"

            if not self._file_adapter.is_file(layer_file):
                logger.warning(
                    "Layer file '%s' not found for layer '%s'. Adding empty layer.",
                    layer_file.name,
                    layer_name,
                )
                combined_keymap["layers"].append(empty_layer)
                continue

            logger.info(
                "Processing layer '%s' from file: %s", layer_name, layer_file.name
            )

            try:
                layer_data: dict[str, Any] = self._file_adapter.read_json(layer_file)

                # Find the actual layer data within the layer file
                if (
                    "layers" in layer_data
                    and isinstance(layer_data["layers"], list)
                    and layer_data["layers"]
                ):
                    actual_layer_content = layer_data["layers"][0]

                    if len(actual_layer_content) != num_keys:
                        logger.warning(
                            "Layer '%s' from %s has %d keys, expected %d. "
                            "Padding/truncating.",
                            layer_name,
                            layer_file.name,
                            len(actual_layer_content),
                            num_keys,
                        )
                        # Pad or truncate the layer to match expected size
                        actual_layer_content = (actual_layer_content + empty_layer)[
                            :num_keys
                        ]

                    combined_keymap["layers"].append(actual_layer_content)
                    logger.info("Added layer '%s' (index %d)", layer_name, i)
                    found_layer_count += 1
                else:
                    logger.warning(
                        "Layer data missing or invalid in %s for layer '%s'. "
                        "Using empty layer.",
                        layer_file.name,
                        layer_name,
                    )
                    combined_keymap["layers"].append(empty_layer)

            except Exception as e:
                logger.error(
                    "Error processing layer file %s: %s. Adding empty layer.",
                    layer_file.name,
                    e,
                )
                combined_keymap["layers"].append(empty_layer)

        logger.info(
            "Successfully processed %d out of %d expected layers.",
            found_layer_count,
            len(layer_names),
        )

    def _add_dtsi_content_from_files(
        self, combined_keymap: dict[str, Any], input_dir: Path
    ) -> None:
        """Add DTSI content from separate files to combined keymap.

        Args:
            combined_keymap: Keymap data to which DTSI content will be added
            input_dir: Directory containing DTSI files
        """
        device_dtsi_path = input_dir / "device.dtsi"
        keymap_dtsi_path = input_dir / "keymap.dtsi"

        # Read device.dtsi if exists
        if self._file_adapter.is_file(device_dtsi_path):
            combined_keymap["custom_devicetree"] = self._file_adapter.read_text(
                device_dtsi_path
            )
            logger.info("Restored custom_devicetree from device.dtsi.")
        else:
            combined_keymap["custom_devicetree"] = ""

        # Read keymap.dtsi if exists
        if self._file_adapter.is_file(keymap_dtsi_path):
            combined_keymap["custom_defined_behaviors"] = self._file_adapter.read_text(
                keymap_dtsi_path
            )
            logger.info("Restored custom_defined_behaviors from keymap.dtsi.")
        else:
            combined_keymap["custom_defined_behaviors"] = ""


def create_keymap_component_service(
    file_adapter: FileAdapter | None = None,
) -> KeymapComponentService:
    """Create a KeymapComponentService instance with optional dependency injection.

    Args:
        file_adapter: Optional file adapter (creates default if None)

    Returns:
        Configured KeymapComponentService instance
    """
    logger.debug(
        "Creating KeymapComponentService with%s file adapter",
        "" if file_adapter else " default",
    )

    if file_adapter is None:
        from glovebox.adapters.file_adapter import create_file_adapter

        file_adapter = create_file_adapter()

    return KeymapComponentService(file_adapter)
