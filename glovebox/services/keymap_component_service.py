"""Service for keymap component extraction and management."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, TypeAlias

from glovebox.core.errors import KeymapError
from glovebox.models.keymap import KeymapData, KeymapMetadata
from glovebox.models.results import KeymapResult
from glovebox.protocols.file_adapter_protocol import FileAdapterProtocol
from glovebox.services.base_service import BaseServiceImpl


logger = logging.getLogger(__name__)


# Type alias for result dictionaries
ResultDict: TypeAlias = dict[str, Any]


class KeymapComponentService(BaseServiceImpl):
    """Service for extracting and combining keymap components.

    Responsible for splitting keymaps into individual layers and files,
    and recombining those files into complete keymap data.
    """

    def __init__(self, file_adapter: FileAdapterProtocol):
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

            # Extract components directly using the Pydantic model
            # Our helper methods already support handling KeymapData objects
            self._extract_dtsi_snippets(keymap, output_dir)
            self._extract_metadata_config(keymap, output_dir)
            self._extract_individual_layers(keymap, output_layer_dir)

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
    ) -> KeymapData:
        """Combine extracted components into a complete keymap.

        Args:
            base_keymap: Base keymap data model without layers
            layers_dir: Directory containing individual layer files

        Returns:
            Combined keymap as KeymapData model

        Raises:
            KeymapError: If combination fails
        """
        logger.info("Combining layers from %s", layers_dir)

        layers_dir = layers_dir.resolve()

        # Validate directory existence
        if not self._file_adapter.is_dir(layers_dir):
            raise KeymapError(f"Layers directory not found: {layers_dir}")

        # Create a new combined keymap starting with metadata
        # We'll work directly with the Pydantic model throughout the process
        combined_keymap = KeymapData.model_validate(metadata_keymap)

        # Process layers and add them to the model
        self._process_layers_for_combination(combined_keymap, layers_dir)

        # Add DTSI content from separate files
        parent_dir = layers_dir.parent
        self._add_dtsi_content_from_files(combined_keymap, parent_dir)

        logger.info("Successfully combined %d layers", len(combined_keymap.layers))

        return combined_keymap

    # Private helper methods for extraction

    def _extract_dtsi_snippets(self, keymap: KeymapData, output_dir: Path) -> None:
        """Extract custom DTSI snippets to separate files.

        Args:
            keymap: Keymap data model
            output_dir: Directory to write snippet files
        """
        # Access the DTSI content directly from the model
        device_dtsi = keymap.custom_devicetree
        behaviors_dtsi = keymap.custom_defined_behaviors

        if device_dtsi:
            device_dtsi_path = output_dir / "device.dtsi"
            self._file_adapter.write_text(device_dtsi_path, device_dtsi)
            logger.info("Extracted custom_devicetree to %s", device_dtsi_path)

        if behaviors_dtsi:
            keymap_dtsi_path = output_dir / "keymap.dtsi"
            self._file_adapter.write_text(keymap_dtsi_path, behaviors_dtsi)
            logger.info("Extracted custom_defined_behaviors to %s", keymap_dtsi_path)

    def _extract_metadata_config(self, keymap: KeymapData, output_dir: Path) -> None:
        """Extract metadata configuration to metadata.json.

        Args:
            keymap: Keymap data model
            output_dir: Directory to write metadata configuration
        """
        # We use model_dump with include to only get the KeymapMetadata fields
        metadata_dict = keymap.model_dump(
            mode="json", by_alias=True, include=set(KeymapMetadata.model_fields.keys())
        )

        # Save with proper serialization
        output_file = output_dir / "metadata.json"
        self._file_adapter.write_json(output_file, metadata_dict)
        logger.info("Extracted metadata configuration to %s", output_file)

    def _extract_individual_layers(
        self, keymap: KeymapData, output_layer_dir: Path
    ) -> None:
        """Extract individual layers to separate JSON files.

        Args:
            keymap: Keymap data model
            output_layer_dir: Directory to write individual layer files
        """
        from glovebox.models.keymap import KeymapBinding

        # Access layer data directly from the model
        layer_names = keymap.layer_names
        layers_data = keymap.layers

        if not layer_names or not layers_data:
            logger.warning(
                "No layer names or data found. Cannot extract individual layers."
            )
            return

        logger.info("Extracting %d layers...", len(layer_names))

        for i, layer_name in enumerate(layer_names):
            # Sanitize layer name for filename
            safe_layer_name = self._file_adapter.sanitize_filename(layer_name)
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

            # Create a minimal KeymapData model for the single layer
            single_layer_keymap = KeymapData(
                # Copy metadata fields from the original keymap
                keyboard=keymap.keyboard,
                firmware_api_version=keymap.firmware_api_version,
                locale=keymap.locale,
                uuid="",  # New unique ID for the layer file
                parent_uuid=keymap.uuid,  # Reference original keymap as parent
                date=keymap.date,
                creator=keymap.creator,
                # Add layer-specific metadata
                title=f"Layer: {layer_name}",
                notes=f"Extracted layer '{layer_name}'",
                tags=[layer_name.lower().replace("_", "-").replace(" ", "-")],
                # Just this single layer
                layer_names=[layer_name],
                layers=[layer_bindings],
            )

            output_file = output_layer_dir / f"{safe_layer_name}.json"
            # Save as JSON using model_dump to ensure proper serialization with aliases
            self._file_adapter.write_json(
                output_file, single_layer_keymap.model_dump(mode="json", by_alias=True)
            )
            logger.info("Extracted layer '%s' to %s", layer_name, output_file)

    # Helper methods for layer combination

    def _process_layers_for_combination(
        self, combined_keymap: KeymapData, layers_dir: Path
    ) -> None:
        """Process and combine layer files.

        Args:
            combined_keymap: Base keymap data model to which layers will be added
            layers_dir: Directory containing layer files
        """
        from glovebox.models.keymap import KeymapBinding, LayerBindings

        # Clear existing layers while preserving layer names
        combined_keymap.layers = []
        layer_names = combined_keymap.layer_names

        logger.info(
            "Expecting %d layers based on metadata.json: %s",
            len(layer_names),
            layer_names,
        )

        # Determine expected number of keys per layer
        num_keys = 80  # Default for Glove80
        empty_binding = KeymapBinding(value="&none", params=[])
        empty_layer = [KeymapBinding(value="&none", params=[]) for _ in range(num_keys)]

        found_layer_count = 0

        for i, layer_name in enumerate(layer_names):
            safe_layer_name = self._file_adapter.sanitize_filename(layer_name)
            if not safe_layer_name:
                safe_layer_name = f"layer_{i}"
            layer_file = layers_dir / f"{safe_layer_name}.json"

            if not self._file_adapter.is_file(layer_file):
                logger.warning(
                    "Layer file '%s' not found for layer '%s'. Adding empty layer.",
                    layer_file.name,
                    layer_name,
                )
                combined_keymap.layers.append(empty_layer)
                continue

            logger.info(
                "Processing layer '%s' from file: %s", layer_name, layer_file.name
            )

            try:
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
                            "Layer '%s' from %s has %d keys, expected %d. "
                            "Padding/truncating.",
                            layer_name,
                            layer_file.name,
                            len(actual_layer_content),
                            num_keys,
                        )
                        # Pad or truncate the layer to match expected size
                        padded_content = actual_layer_content + [
                            {"value": "&none", "params": []} for _ in range(num_keys)
                        ]
                        actual_layer_content = padded_content[:num_keys]

                    # Convert layer content to properly typed KeymapBinding models
                    # This ensures proper validation of the layer data
                    typed_layer: list[KeymapBinding] = []
                    for binding_data in actual_layer_content:
                        try:
                            # Validate each binding with the model
                            binding = KeymapBinding.model_validate(binding_data)
                            typed_layer.append(binding)
                        except Exception as binding_err:
                            logger.warning(
                                f"Invalid binding in layer '{layer_name}': {binding_err}. "
                                f"Using empty binding."
                            )
                            typed_layer.append(empty_binding)

                    combined_keymap.layers.append(typed_layer)
                    logger.info("Added layer '%s' (index %d)", layer_name, i)
                    found_layer_count += 1
                else:
                    logger.warning(
                        "Layer data missing or invalid in %s for layer '%s'. "
                        "Using empty layer.",
                        layer_file.name,
                        layer_name,
                    )
                    combined_keymap.layers.append(empty_layer)

            except Exception as e:
                logger.error(
                    "Error processing layer file %s: %s. Adding empty layer.",
                    layer_file.name,
                    e,
                )
                combined_keymap.layers.append(empty_layer)

        logger.info(
            "Successfully processed %d out of %d expected layers.",
            found_layer_count,
            len(layer_names),
        )

    def _add_dtsi_content_from_files(
        self, combined_keymap: KeymapData, input_dir: Path
    ) -> None:
        """Add DTSI content from separate files to combined keymap.

        Args:
            combined_keymap: Keymap data model to which DTSI content will be added
            input_dir: Directory containing DTSI files
        """
        device_dtsi_path = input_dir / "device.dtsi"
        keymap_dtsi_path = input_dir / "keymap.dtsi"

        # Read device.dtsi if exists
        if self._file_adapter.is_file(device_dtsi_path):
            combined_keymap.custom_devicetree = self._file_adapter.read_text(
                device_dtsi_path
            )
            logger.info("Restored custom_devicetree from device.dtsi.")
        else:
            combined_keymap.custom_devicetree = ""

        # Read keymap.dtsi if exists
        if self._file_adapter.is_file(keymap_dtsi_path):
            combined_keymap.custom_defined_behaviors = self._file_adapter.read_text(
                keymap_dtsi_path
            )
            logger.info("Restored custom_defined_behaviors from keymap.dtsi.")
        else:
            combined_keymap.custom_defined_behaviors = ""


def create_keymap_component_service(
    file_adapter: FileAdapterProtocol | None = None,
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
