"""Service for layout component extraction and management."""

import logging
from pathlib import Path
from typing import Any, TypeAlias

from glovebox.core.errors import LayoutError
from glovebox.layout.models import (
    BehaviorData,
    LayoutData,
    LayoutMetadata,
    LayoutResult,
)
from glovebox.protocols.file_adapter_protocol import FileAdapterProtocol
from glovebox.services.base_service import BaseService


logger = logging.getLogger(__name__)


# Type alias for result dictionaries
ResultDict: TypeAlias = dict[str, Any]


class LayoutComponentService(BaseService):
    """Service for decomposing and composing layout components.

    Responsible for decomposing layouts into individual layers and files,
    and composing those files into complete layout data.
    """

    def __init__(self, file_adapter: FileAdapterProtocol):
        """Initialize layout component service with adapter dependencies."""
        super().__init__(service_name="LayoutComponentService", service_version="1.0.0")
        self._file_adapter = file_adapter

    def decompose_components(
        self, layout: LayoutData, output_dir: Path
    ) -> LayoutResult:
        """Decompose layout into individual components and layers.

        Args:
            layout: Layout data model
            output_dir: Directory to write extracted components

        Returns:
            LayoutResult with extraction information

        Raises:
            LayoutError: If extraction fails
        """
        logger.info("Extracting layout components to %s", output_dir)

        result = LayoutResult(success=False)

        try:
            # Create output directories
            output_dir = output_dir.resolve()
            output_layer_dir = output_dir / "layers"
            self._file_adapter.create_directory(output_dir)
            self._file_adapter.create_directory(output_layer_dir)

            # Extract components directly using the Pydantic model
            # Our helper methods already support handling LayoutData objects
            self._extract_dtsi_snippets(layout, output_dir)
            self._extract_behavior_data(layout, output_dir)
            self._extract_metadata_config(layout, output_dir)
            self._extract_individual_layers(layout, output_layer_dir)

            result.success = True
            result.layer_count = len(layout.layers)
            result.add_message(f"Successfully extracted layers to {output_dir}")
            result.add_message(
                f"Created metadata.json and {result.layer_count} layer files"
            )

            return result

        except Exception as e:
            result.add_error(f"Layer extraction failed: {e}")
            logger.error("Layer extraction failed: %s", e)
            raise LayoutError(f"Layer extraction failed: {e}") from e

    def compose_components(
        self, metadata_layout: LayoutData, layers_dir: Path
    ) -> LayoutData:
        """Compose extracted components into a complete layout.

        Args:
            base_layout: Base layout data model without layers
            layers_dir: Directory containing individual layer files

        Returns:
            Combined layout as LayoutData model

        Raises:
            LayoutError: If combination fails
        """
        logger.info("Combining layers from %s", layers_dir)

        layers_dir = layers_dir.resolve()

        # Validate directory existence
        if not self._file_adapter.is_dir(layers_dir):
            raise LayoutError(f"Layers directory not found: {layers_dir}")

        # Create a new combined layout starting with metadata
        # We'll work directly with the Pydantic model throughout the process
        combined_layout = LayoutData.model_validate(metadata_layout)

        # Process layers and add them to the model
        self._process_layers_for_combination(combined_layout, layers_dir)

        # Add DTSI content from separate files
        parent_dir = layers_dir.parent
        self._add_dtsi_content_from_files(combined_layout, parent_dir)

        # Add behavior data from behaviors.json if it exists
        self._add_behavior_data_from_file(combined_layout, parent_dir)

        logger.info("Successfully combined %d layers", len(combined_layout.layers))

        return combined_layout

    # Private helper methods for extraction

    def _extract_dtsi_snippets(self, layout: LayoutData, output_dir: Path) -> None:
        """Extract custom DTSI snippets to separate files.

        Args:
            layout: Keymap data model
            output_dir: Directory to write snippet files
        """
        # Access the DTSI content directly from the model
        device_dtsi = layout.custom_devicetree
        behaviors_dtsi = layout.custom_defined_behaviors

        if device_dtsi:
            device_dtsi_path = output_dir / "device.dtsi"
            self._file_adapter.write_text(device_dtsi_path, device_dtsi)
            logger.info("Extracted custom_devicetree to %s", device_dtsi_path)

        if behaviors_dtsi:
            keymap_dtsi_path = output_dir / "keymap.dtsi"
            self._file_adapter.write_text(keymap_dtsi_path, behaviors_dtsi)
            logger.info("Extracted custom_defined_behaviors to %s", keymap_dtsi_path)

    def _extract_behavior_data(self, layout: LayoutData, output_dir: Path) -> None:
        """Extract behavior data to behaviors.json.

        Args:
            layout: Layout data model
            output_dir: Directory to write behavior data
        """
        # Extract behavior fields from the layout
        behavior_data = BehaviorData(
            variables=layout.variables,
            holdTaps=layout.hold_taps,
            combos=layout.combos,
            macros=layout.macros,
            inputListeners=layout.input_listeners,
            config_parameters=layout.config_parameters,
        )

        # Only write behaviors.json if there are actual behaviors defined
        if not behavior_data.is_empty():
            behaviors_file = output_dir / "behaviors.json"
            self._file_adapter.write_json(behaviors_file, behavior_data.to_dict())
            logger.info("Extracted behavior definitions to %s", behaviors_file)
        else:
            logger.debug("No behavior definitions found, skipping behaviors.json")

    def _extract_metadata_config(self, layout: LayoutData, output_dir: Path) -> None:
        """Extract metadata configuration to metadata.json.

        Args:
            layout: Keymap data model
            output_dir: Directory to write metadata configuration
        """
        # Get all LayoutMetadata fields but exclude behavior-related fields that go to behaviors.json
        behavior_fields = {
            "variables",
            "holdTaps",
            "combos",
            "macros",
            "inputListeners",
            "config_parameters",
            "hold_taps",
            "input_listeners",  # Include both alias and field names
        }

        metadata_fields = set(LayoutMetadata.model_fields.keys()) - behavior_fields

        # Use model_dump with include to only get the non-behavior metadata fields
        metadata_dict = layout.model_dump(
            mode="json", by_alias=True, include=metadata_fields
        )

        # Save with proper serialization
        output_file = output_dir / "metadata.json"
        self._file_adapter.write_json(output_file, metadata_dict)
        logger.info("Extracted metadata configuration to %s", output_file)

    def _extract_individual_layers(
        self, layout: LayoutData, output_layer_dir: Path
    ) -> None:
        """Extract individual layers to separate JSON files.

        Args:
            layout: Keymap data model
            output_layer_dir: Directory to write individual layer files
        """

        # Access layer data directly from the model
        layer_names = layout.layer_names
        layers_data = layout.layers

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

            # Create a minimal LayoutData model for the single layer
            single_layer_layout = LayoutData(
                # Copy metadata fields from the original layout
                keyboard=layout.keyboard,
                firmware_api_version=layout.firmware_api_version,
                locale=layout.locale,
                uuid="",  # New unique ID for the layer file
                parent_uuid=layout.uuid,  # Reference original layout as parent
                date=layout.date,
                creator=layout.creator,
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
                output_file, single_layer_layout.model_dump(mode="json", by_alias=True)
            )
            logger.info("Extracted layer '%s' to %s", layer_name, output_file)

    # Helper methods for layer combination

    def _process_layers_for_combination(
        self, combined_layout: LayoutData, layers_dir: Path
    ) -> None:
        """Process and combine layer files.

        Args:
            combined_layout: Base layout data model to which layers will be added
            layers_dir: Directory containing layer files
        """
        from glovebox.layout.models import LayoutBinding

        # Clear existing layers while preserving layer names
        combined_layout.layers = []
        layer_names = combined_layout.layer_names

        logger.info(
            "Expecting %d layers based on metadata.json: %s",
            len(layer_names),
            layer_names,
        )

        # Determine expected number of keys per layer
        num_keys = 80  # Default for Glove80
        empty_binding = LayoutBinding(value="&none", params=[])
        empty_layer = [LayoutBinding(value="&none", params=[]) for _ in range(num_keys)]

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
                combined_layout.layers.append(empty_layer)
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

                    # Convert layer content to properly typed LayoutBinding models
                    # This ensures proper validation of the layer data
                    typed_layer: list[LayoutBinding] = []
                    for binding_data in actual_layer_content:
                        try:
                            # Validate each binding with the model
                            binding = LayoutBinding.model_validate(binding_data)
                            typed_layer.append(binding)
                        except Exception as binding_err:
                            logger.warning(
                                f"Invalid binding in layer '{layer_name}': {binding_err}. "
                                f"Using empty binding."
                            )
                            typed_layer.append(empty_binding)

                    combined_layout.layers.append(typed_layer)
                    logger.info("Added layer '%s' (index %d)", layer_name, i)
                    found_layer_count += 1
                else:
                    logger.warning(
                        "Layer data missing or invalid in %s for layer '%s'. "
                        "Using empty layer.",
                        layer_file.name,
                        layer_name,
                    )
                    combined_layout.layers.append(empty_layer)

            except Exception as e:
                logger.error(
                    "Error processing layer file %s: %s. Adding empty layer.",
                    layer_file.name,
                    e,
                )
                combined_layout.layers.append(empty_layer)

        logger.info(
            "Successfully processed %d out of %d expected layers.",
            found_layer_count,
            len(layer_names),
        )

    def _add_dtsi_content_from_files(
        self, combined_layout: LayoutData, input_dir: Path
    ) -> None:
        """Add DTSI content from separate files to combined layout.

        Args:
            combined_layout: Keymap data model to which DTSI content will be added
            input_dir: Directory containing DTSI files
        """
        device_dtsi_path = input_dir / "device.dtsi"
        keymap_dtsi_path = input_dir / "keymap.dtsi"

        # Read device.dtsi if exists
        if self._file_adapter.is_file(device_dtsi_path):
            combined_layout.custom_devicetree = self._file_adapter.read_text(
                device_dtsi_path
            )
            logger.info("Restored custom_devicetree from device.dtsi.")
        else:
            combined_layout.custom_devicetree = ""

        # Read keymap.dtsi if exists
        if self._file_adapter.is_file(keymap_dtsi_path):
            combined_layout.custom_defined_behaviors = self._file_adapter.read_text(
                keymap_dtsi_path
            )
            logger.info("Restored custom_defined_behaviors from keymap.dtsi.")
        else:
            combined_layout.custom_defined_behaviors = ""

    def _add_behavior_data_from_file(
        self, combined_layout: LayoutData, input_dir: Path
    ) -> None:
        """Add behavior data from behaviors.json file to combined layout.

        Args:
            combined_layout: Layout data model to which behavior data will be added
            input_dir: Directory containing behaviors.json file
        """
        behaviors_file = input_dir / "behaviors.json"

        if self._file_adapter.is_file(behaviors_file):
            try:
                behavior_dict = self._file_adapter.read_json(behaviors_file)
                behavior_data = BehaviorData.model_validate(behavior_dict)

                # Apply behavior data to the combined layout
                combined_layout.variables = behavior_data.variables
                combined_layout.hold_taps = behavior_data.hold_taps
                combined_layout.combos = behavior_data.combos
                combined_layout.macros = behavior_data.macros
                combined_layout.input_listeners = behavior_data.input_listeners
                combined_layout.config_parameters = behavior_data.config_parameters

                logger.info("Restored behavior definitions from behaviors.json")
            except Exception as e:
                logger.error(
                    "Failed to load behavior data from %s: %s", behaviors_file, e
                )
                # Continue without behavior data rather than failing
        else:
            logger.debug("No behaviors.json file found, using empty behavior data")
            # Initialize with empty behavior data
            combined_layout.variables = {}
            combined_layout.hold_taps = []
            combined_layout.combos = []
            combined_layout.macros = []
            combined_layout.input_listeners = []
            combined_layout.config_parameters = []


def create_layout_component_service(
    file_adapter: FileAdapterProtocol,
) -> LayoutComponentService:
    """Create a LayoutComponentService instance with explicit dependency injection.

    Args:
        file_adapter: Required file adapter for file operations

    Returns:
        Configured LayoutComponentService instance
    """
    return LayoutComponentService(file_adapter)
