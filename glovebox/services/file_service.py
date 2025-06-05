"""File service for keymap file manipulation operations."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from glovebox.adapters.file_adapter import FileAdapter
from glovebox.config.profile import KeyboardProfile
from glovebox.core.errors import KeymapError
from glovebox.models.keymap import (
    KeymapBinding,
    KeymapData,
    KeymapLayer,
    KeymapMetadata,
    LayerBindings,
)
from glovebox.models.results import KeymapResult
from glovebox.services.base_service import BaseServiceImpl


logger = logging.getLogger(__name__)


class KeymapFileService(BaseServiceImpl):
    """Service for keymap file operations including loading, saving, extraction and combination."""

    def __init__(self, file_adapter: FileAdapter):
        """Initialize keymap file service with adapter dependencies."""
        super().__init__(service_name="KeymapFileService", service_version="1.0.0")
        self._file_adapter = file_adapter

    def load_keymap(
        self, file_path: Path, profile: KeyboardProfile | None = None
    ) -> KeymapData:
        """Load keymap data from a file.

        Args:
            file_path: Path to the keymap file (JSON or keymap format)
            profile: Optional keyboard profile for validation

        Returns:
            KeymapData model instance

        Raises:
            KeymapError: If file cannot be loaded or parsed
        """
        try:
            logger.info("Loading keymap from %s", file_path)

            # Determine file type from extension
            file_ext = file_path.suffix.lower()

            if file_ext == ".json":
                return self._load_json_keymap(file_path)
            elif file_ext == ".keymap":
                # If profile is not provided, we can't parse .keymap files
                if not profile:
                    raise KeymapError(
                        f"Cannot load .keymap file without a keyboard profile: {file_path}"
                    )
                # This would be implemented in a real system to parse keymap files
                raise KeymapError("Loading from .keymap files not yet implemented")
            else:
                raise KeymapError(f"Unsupported keymap file type: {file_ext}")

        except Exception as e:
            if not isinstance(e, KeymapError):
                logger.error("Error loading keymap file %s: %s", file_path, e)
                raise KeymapError(f"Failed to load keymap file: {e}") from e
            raise

    def save_keymap(
        self,
        keymap_data: KeymapData,
        file_path: Path,
        format_type: Literal["json", "keymap", "conf"] = "json",
    ) -> Path:
        """Save keymap data to a file.

        Args:
            keymap_data: Keymap data model to save
            file_path: Target file path
            format_type: Output format (json, keymap, or conf)

        Returns:
            Path to the saved file

        Raises:
            KeymapError: If file cannot be saved
        """
        try:
            logger.info("Saving keymap to %s", file_path)

            # Create parent directory if it doesn't exist
            self._file_adapter.mkdir(file_path.parent)

            if format_type == "json":
                return self._save_json_keymap(keymap_data, file_path)
            elif format_type in ("keymap", "conf"):
                # These would be implemented in a real system
                raise KeymapError(f"Saving to {format_type} format not yet implemented")
            else:
                raise KeymapError(f"Unsupported output format: {format_type}")

        except Exception as e:
            if not isinstance(e, KeymapError):
                logger.error("Error saving keymap to %s: %s", file_path, e)
                raise KeymapError(f"Failed to save keymap file: {e}") from e
            raise

    def _load_json_keymap(self, file_path: Path) -> KeymapData:
        """Load keymap data from a JSON file.

        Args:
            file_path: Path to the JSON file

        Returns:
            KeymapData model instance

        Raises:
            KeymapError: If file cannot be loaded or parsed
        """
        try:
            # Read JSON file using the file adapter
            json_data = self._file_adapter.read_json(file_path)

            # Parse into KeymapData model
            keymap_data = KeymapData.model_validate(json_data)

            logger.info(
                "Successfully loaded keymap with %d layers from %s",
                len(keymap_data.layers),
                file_path,
            )

            return keymap_data

        except Exception as e:
            logger.error("Error parsing keymap JSON from %s: %s", file_path, e)
            raise KeymapError(f"Failed to parse keymap JSON: {e}") from e

    def _save_json_keymap(self, keymap_data: KeymapData, file_path: Path) -> Path:
        """Save keymap data to a JSON file.

        Args:
            keymap_data: Keymap data model to save
            file_path: Target JSON file path

        Returns:
            Path to the saved file

        Raises:
            KeymapError: If file cannot be saved
        """
        try:
            # Convert model to dictionary with proper field names
            json_data = keymap_data.model_dump(mode="json", by_alias=True)

            # Write JSON file using the file adapter
            self._file_adapter.write_json(file_path, json_data)

            logger.info("Successfully saved keymap to %s", file_path)

            return file_path

        except Exception as e:
            logger.error("Error saving keymap to JSON %s: %s", file_path, e)
            raise KeymapError(f"Failed to save keymap to JSON: {e}") from e

    def extract_layers(self, keymap_file: Path, output_dir: Path) -> KeymapResult:
        """
        Extracts each layer from a keymap JSON file into separate files within a 'layers'
        subdirectory. Also extracts a 'metadata.json' file containing the remaining configuration
        and saves any 'custom_devicetree' and 'custom_defined_behaviors' content into
        'device.dtsi' and 'keymap.dtsi' respectively.

        Structure created in output_dir:
        - metadata.json
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
                "Creating output directories: %s and %s", output_dir, output_layer_dir
            )
            self._file_adapter.mkdir(output_dir)
            self._file_adapter.mkdir(output_layer_dir)
        except Exception as e:
            raise KeymapError(f"Failed to create output directories: {e}") from e

        try:
            logger.info("Loading keymap data from %s", keymap_file)

            # Load keymap data using the typed model
            keymap_model = self._load_json_keymap(keymap_file)
            logger.debug("Keymap data loaded and validated successfully.")

        except Exception as e:
            if "validation error" in str(e).lower():
                raise KeymapError(
                    f"Invalid keymap data structure in {keymap_file}: {e}"
                ) from e
            raise KeymapError(
                f"Unexpected error loading or validating keymap file {keymap_file}: {e}"
            ) from e

        # Extract custom DTSI snippets
        self._extract_dtsi_snippets(keymap_model, output_dir)

        # Extract metadata configuration to metadata.json
        self._extract_metadata(keymap_model, output_dir)

        # Extract individual layers to separate files
        self._extract_individual_layers(keymap_model, output_layer_dir, keymap_file)

        result.success = True
        result.layer_count = len(keymap_model.layers)
        result.add_message(f"Successfully extracted layers to {output_dir}")
        result.add_message(
            f"Created metadata.json and {result.layer_count} layer files"
        )

        logger.info("Finished extracting layers to %s", output_dir)
        return result

    def combine_layers(self, input_dir: Path, output_file: Path) -> KeymapResult:
        """
        Combines layer files from a specified directory structure back into a single
        keymap JSON file. It expects an input directory containing:
        - metadata.json: The keymap metadata configuration (macros, combos, etc.).
                         Must contain the 'layer_names' list defining the order.
        - layers/: A subdirectory containing individual JSON files for each layer,
                   named according to the sanitized layer names (e.g., 'DEFAULT.json', 'LOWER.json').
        - device.dtsi (optional): Contains custom device tree snippets.
        - keymap.dtsi (optional): Contains custom defined behaviors snippets.

        Args:
            input_dir: Path to the directory containing the 'metadata.json' and 'layers/' subdirectory.
            output_file: Path where the combined keymap JSON file will be saved.

        Returns:
            KeymapResult with combination information

        Raises:
            KeymapError: If required files/directories are missing, data is invalid, or writing fails.
        """
        result = KeymapResult(success=False)

        input_dir = input_dir.resolve()
        output_file = output_file.resolve()
        metadata_file = input_dir / "metadata.json"
        device_dtsi_path = input_dir / "device.dtsi"
        keymap_dtsi_path = input_dir / "keymap.dtsi"
        layers_dir = input_dir / "layers"

        logger.info("Combining layers from %s into %s", input_dir, output_file)

        if not self._file_adapter.is_file(metadata_file):
            raise KeymapError(f"Metadata file not found: {metadata_file}")
        if not self._file_adapter.is_dir(layers_dir):
            raise KeymapError(f"Layers directory not found: {layers_dir}")

        # Load metadata configuration
        metadata_keymap = self._load_metadata_config(metadata_file)

        # Process layers
        combined_keymap = self._process_layers(metadata_keymap, layers_dir)

        # Add DTSI content
        combined_keymap = self._add_dtsi_content(
            combined_keymap, device_dtsi_path, keymap_dtsi_path
        )

        # Write the final combined keymap
        self._save_json_keymap(combined_keymap, output_file)

        result.success = True
        result.json_path = output_file
        result.layer_count = len(combined_keymap.layers)
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
        logger.info("Finishing keymap: %s -> %s", keymap_file, output_path)

        # Load keymap
        keymap_data = self._load_json_keymap(keymap_file)

        # Add device tree content
        keymap_data = self._add_device_tree_content(keymap_data, device_dtsi)

        # Add keymap behaviors content
        keymap_data = self._add_keymap_behaviors_content(keymap_data, keymap_dtsi)

        # Write the updated keymap
        self._save_json_keymap(keymap_data, output_path)

        result.success = True
        result.json_path = output_path
        result.add_message(f"Successfully finished keymap and saved to {output_path}")

        return result

    # Private helper methods for extraction
    def _extract_dtsi_snippets(self, keymap: KeymapData, output_dir: Path) -> None:
        """Extract custom DTSI snippets to separate files.

        Args:
            keymap: Keymap data model
            output_dir: Directory to write snippet files
        """
        try:
            device_dtsi_path = output_dir / "device.dtsi"
            if keymap.custom_devicetree:
                self._file_adapter.write_text(
                    device_dtsi_path, keymap.custom_devicetree
                )
                logger.info("Extracted custom_devicetree to %s", device_dtsi_path)
            else:
                logger.info("No custom_devicetree found to extract.")

            keymap_dtsi_path = output_dir / "keymap.dtsi"
            if keymap.custom_defined_behaviors:
                self._file_adapter.write_text(
                    keymap_dtsi_path, keymap.custom_defined_behaviors
                )
                logger.info(
                    "Extracted custom_defined_behaviors to %s", keymap_dtsi_path
                )
            else:
                logger.info("No custom_defined_behaviors found to extract.")

        except Exception as e:
            logger.warning("Failed to write DTSI snippets: %s", e)

    def _extract_metadata(self, keymap: KeymapData, output_dir: Path) -> None:
        """Extract metadata configuration to metadata.json.

        Args:
            keymap: Keymap data model
            output_dir: Directory to write metadata configuration
        """
        # Extract just the KeymapMetadata portion from the KeymapData
        # Since KeymapData inherits from KeymapMetadata, we can use model_dump
        # with include to get just the base class fields
        metadata_dict = keymap.model_dump(
            mode="json", by_alias=True, include=set(KeymapMetadata.model_fields.keys())
        )

        # Add empty layers list
        metadata_dict["layers"] = []

        # Empty custom snippets as they are stored separately
        metadata_dict["custom_defined_behaviors"] = ""
        metadata_dict["custom_devicetree"] = ""

        output_file = output_dir / "metadata.json"
        try:
            self._file_adapter.write_json(output_file, metadata_dict)
            logger.info("Extracted metadata to %s", output_file)
        except Exception as e:
            raise KeymapError(
                f"Failed to write metadata file {output_file}: {e}"
            ) from e

    def _extract_individual_layers(
        self, keymap: KeymapData, output_layer_dir: Path, keymap_file: Path
    ) -> None:
        """Extract individual layers to separate JSON files.

        Args:
            keymap: Keymap data model
            output_layer_dir: Directory to write individual layer files
            keymap_file: Original keymap file path for reference
        """
        # Pydantic already validates that layer_names and layers match in length
        logger.info("Extracting %d layers...", len(keymap.layer_names))

        # Get structured layers using the model's helper method
        structured_layers = keymap.get_structured_layers()

        for i, layer in enumerate(structured_layers):
            layer_name = layer.name

            # Sanitize layer name for use as filename
            from glovebox.utils.file_utils import sanitize_filename

            safe_layer_name = sanitize_filename(layer_name) or f"layer_{i}"

            # Create a minimal keymap structure for the single layer
            # Let Pydantic set most defaults automatically
            layer_data = KeymapData(
                keyboard=keymap.keyboard,
                title=f"Layer: {layer_name}",
                date=keymap.date,
                uuid="",
                parent_uuid=keymap.uuid,
                creator=keymap.creator,
                notes=f"Extracted layer '{layer_name}' from {keymap_file.name}",
                tags=[layer_name.lower().replace("_", "-").replace(" ", "-")],
                layer_names=[layer_name],
                layers=[layer.bindings],
            )

            output_file = output_layer_dir / f"{safe_layer_name}.json"
            try:
                self._save_json_keymap(layer_data, output_file)
                logger.info("Extracted layer '%s' to %s", layer_name, output_file)
            except Exception as e:
                logger.error("Failed to write layer file %s: %s", output_file, e)

    # Private helper methods for combination
    def _load_metadata_config(self, metadata_file: Path) -> KeymapData:
        """Load metadata configuration from file.

        Args:
            metadata_file: Path to the metadata.json file

        Returns:
            KeymapData model with metadata configuration

        Raises:
            KeymapError: If the file cannot be loaded or parsed
        """
        try:
            # Read metadata.json file and parse directly into KeymapData model
            # Pydantic will handle validation of required fields
            metadata_dict = self._file_adapter.read_json(metadata_file)
            metadata_keymap = KeymapData.model_validate(metadata_dict)

            # Reset layers to be filled by _process_layers
            metadata_keymap.layers = []

            return metadata_keymap
        except Exception as e:
            logger.error("Error reading metadata file %s: %s", metadata_file, e)
            raise KeymapError(
                f"Error reading metadata file {metadata_file}: {e}"
            ) from e

    def _process_layers(
        self, metadata_keymap: KeymapData, layers_dir: Path
    ) -> KeymapData:
        """Process and combine layer files.

        Args:
            metadata_keymap: KeymapData model with metadata fields
            layers_dir: Directory containing layer files

        Returns:
            KeymapData model with layers added
        """
        # Initialize empty layers list
        metadata_keymap.layers = []
        layer_names = metadata_keymap.layer_names

        logger.info("Processing %d layers from %s", len(layer_names), layers_dir)

        # Standard number of keys for Glove80
        # this should come from the profile
        num_keys = 80

        # Create empty layer
        empty_layer: list[KeymapBinding] = [
            KeymapBinding(value="&none") for _ in range(num_keys)
        ]

        # Process each layer defined in metadata.json
        from glovebox.utils.file_utils import sanitize_filename

        for i, layer_name in enumerate(layer_names):
            safe_layer_name = sanitize_filename(layer_name) or f"layer_{i}"
            layer_file = layers_dir / f"{safe_layer_name}.json"

            if not self._file_adapter.is_file(layer_file):
                logger.warning(
                    "Layer file '%s' not found for layer '%s'. Using empty layer.",
                    layer_file.name,
                    layer_name,
                )
                metadata_keymap.layers.append(empty_layer)
                continue

            try:
                # Load the layer file
                layer_keymap = self._load_json_keymap(layer_file)

                # Extract bindings or use empty layer if missing
                if layer_keymap.layers and layer_keymap.layers[0]:
                    # Get the layer bindings, padding if needed
                    layer_bindings = layer_keymap.layers[0]
                    if len(layer_bindings) != num_keys:
                        # Pad or truncate to expected size
                        layer_bindings = (layer_bindings + empty_layer)[:num_keys]

                    metadata_keymap.layers.append(layer_bindings)
                    logger.info("Added layer '%s'", layer_name)
                else:
                    logger.warning(
                        "No bindings found in %s. Using empty layer.", layer_file.name
                    )
                    metadata_keymap.layers.append(empty_layer)

            except Exception as e:
                logger.error("Error loading layer file %s: %s", layer_file.name, e)
                metadata_keymap.layers.append(empty_layer)

        return metadata_keymap

    def _add_dtsi_content(
        self,
        keymap_data: KeymapData,
        device_dtsi_path: Path,
        keymap_dtsi_path: Path,
    ) -> KeymapData:
        """Add DTSI content to keymap.

        Args:
            keymap_data: Keymap data model
            device_dtsi_path: Path to device.dtsi file
            keymap_dtsi_path: Path to keymap.dtsi file

        Returns:
            Updated KeymapData model
        """
        # Read device.dtsi if exists
        if self._file_adapter.is_file(device_dtsi_path):
            try:
                keymap_data.custom_devicetree = self._file_adapter.read_text(
                    device_dtsi_path
                )
                logger.info("Restored custom_devicetree from device.dtsi.")
            except Exception as e:
                logger.warning("Error reading %s: %s", device_dtsi_path, e)

        # Read keymap.dtsi if exists
        if self._file_adapter.is_file(keymap_dtsi_path):
            try:
                keymap_data.custom_defined_behaviors = self._file_adapter.read_text(
                    keymap_dtsi_path
                )
                logger.info("Restored custom_defined_behaviors from keymap.dtsi.")
            except Exception as e:
                logger.warning("Error reading %s: %s", keymap_dtsi_path, e)

        return keymap_data

    # Private helper methods for finish operation
    def _add_device_tree_content(
        self, keymap_data: KeymapData, device_dtsi: Path | None
    ) -> KeymapData:
        """Add device tree content to keymap.

        Args:
            keymap_data: Keymap data model
            device_dtsi: Path to the device tree file

        Returns:
            Updated KeymapData model
        """
        if device_dtsi and self._file_adapter.is_file(device_dtsi):
            device_dtsi = device_dtsi.resolve()
            logger.info("Reading device tree from %s", device_dtsi)
            try:
                keymap_data.custom_devicetree = self._file_adapter.read_text(
                    device_dtsi
                )
            except Exception as e:
                logger.warning("Error reading device tree file %s: %s", device_dtsi, e)
        else:
            if device_dtsi:
                logger.warning("Device tree file not found, skipping: %s", device_dtsi)

        return keymap_data

    def _add_keymap_behaviors_content(
        self, keymap_data: KeymapData, keymap_dtsi: Path | None
    ) -> KeymapData:
        """Add keymap behaviors content to keymap.

        Args:
            keymap_data: Keymap data model
            keymap_dtsi: Path to the keymap behaviors file

        Returns:
            Updated KeymapData model
        """
        if keymap_dtsi and self._file_adapter.is_file(keymap_dtsi):
            keymap_dtsi = keymap_dtsi.resolve()
            logger.info("Reading keymap behaviors from %s", keymap_dtsi)
            try:
                keymap_data.custom_defined_behaviors = self._file_adapter.read_text(
                    keymap_dtsi
                )
            except Exception as e:
                logger.warning(
                    "Error reading keymap behaviors file %s: %s", keymap_dtsi, e
                )
        else:
            if keymap_dtsi:
                logger.warning(
                    "Keymap behaviors file not found, skipping: %s", keymap_dtsi
                )

        return keymap_data


def create_file_service(
    file_adapter: FileAdapter | None = None,
) -> KeymapFileService:
    """Create a KeymapFileService instance.

    Args:
        file_adapter: Optional file adapter (creates default if None)

    Returns:
        KeymapFileService instance
    """
    logger.debug(
        "Creating KeymapFileService with%s file adapter",
        "" if file_adapter else " default",
    )

    if file_adapter is None:
        from glovebox.adapters.file_adapter import create_file_adapter

        file_adapter = create_file_adapter()
