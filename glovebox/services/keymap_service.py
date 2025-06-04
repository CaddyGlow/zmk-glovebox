"""Keymap service for all keymap-related operations."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from glovebox.adapters.file_adapter import FileAdapter
from glovebox.adapters.template_adapter import TemplateAdapter
from glovebox.config.models import KConfigOption
from glovebox.config.profile import KeyboardProfile
from glovebox.core.errors import KeymapError
from glovebox.formatters.behavior_formatter import BehaviorFormatterImpl
from glovebox.generators.config_generator import (
    ConfigGenerator,
    create_config_generator,
)
from glovebox.generators.dtsi_generator import DTSIGenerator
from glovebox.generators.layout_generator import (
    DtsiLayoutGenerator,
    LayoutConfig,
    LayoutMetadata,
    ViewMode,
)
from glovebox.models.keymap import KeymapData, KeymapLayer
from glovebox.models.results import KeymapResult
from glovebox.services.base_service import BaseServiceImpl
from glovebox.services.behavior_service import (
    BehaviorRegistry,
    create_behavior_registry,
)
from glovebox.utils.file_utils import prepare_output_paths, sanitize_filename


logger = logging.getLogger(__name__)


class KeymapService(BaseServiceImpl):
    """Service for all keymap operations including building, validation, and export.

    Responsible for processing keyboard layout files, generating ZMK configuration
    files, and managing keyboard layers and behaviors.
    """

    def __init__(
        self,
        file_adapter: FileAdapter,
        template_adapter: TemplateAdapter,
    ):
        """Initialize keymap service with adapter dependencies."""
        super().__init__(service_name="KeymapService", service_version="1.0.0")
        self._file_adapter = file_adapter
        self._template_adapter = template_adapter

        # Initialize component services
        self._behavior_registry = create_behavior_registry()
        self._behavior_formatter = BehaviorFormatterImpl(self._behavior_registry)
        self._dtsi_generator = DTSIGenerator(self._behavior_formatter)
        self._config_generator = create_config_generator()
        self._layout_generator = DtsiLayoutGenerator()

    def compile(
        self,
        profile: KeyboardProfile,
        keymap_data: KeymapData,
        target_prefix: str,
    ) -> KeymapResult:
        """Compile ZMK keymap files from keymap data.

        Args:
            profile: Keyboard profile containing configuration
            keymap_data: Validated keymap data model
            target_prefix: Base path and name for output files

        Returns:
            KeymapResult with paths to generated files and build metadata

        Raises:
            KeymapError: If compilation process fails
        """
        profile_name = f"{profile.keyboard_name}/{profile.firmware_version}"
        logger.info("Starting keymap build using profile: %s", profile_name)

        result = KeymapResult(success=False)
        result.profile_name = profile_name

        try:
            # Convert to dictionary for internal processing
            validated_data = keymap_data.model_dump()
            result.layer_count = len(validated_data.get("layers", []))

            # Prepare output paths and create directory
            output_paths = prepare_output_paths(target_prefix)
            self._file_adapter.mkdir(output_paths["keymap"].parent)

            # Register system behaviors
            self._register_system_behaviors(profile)

            # Generate files
            self._generate_config_file(
                validated_data,
                profile.keyboard_config.keymap.kconfig_options,
                output_paths["conf"],
            )

            self._generate_keymap_file(validated_data, profile, output_paths["keymap"])

            # Save JSON file to output directory
            self._file_adapter.write_json(output_paths["json"], validated_data)

            # Set result paths
            result.keymap_path = output_paths["keymap"]
            result.conf_path = output_paths["conf"]
            result.json_path = output_paths["json"]
            result.success = True

            result.add_message(f"Keymap built successfully for {profile_name}")
            logger.info(
                "Keymap build completed successfully for target '%s'", target_prefix
            )

            return result

        except Exception as e:
            result.add_error(f"Keymap build failed: {e}")
            logger.error("Keymap build failed: %s", e)
            raise KeymapError(f"Keymap build failed: {e}") from e

    def split_keymap(
        self,
        profile: KeyboardProfile,
        keymap_data: KeymapData,
        output_dir: Path,
    ) -> KeymapResult:
        """Split each layer from a keymap into separate files.

        Args:
            profile: Keyboard profile containing configuration
            keymap_data: Validated keymap data model
            output_dir: Directory where the extracted structure will be created

        Returns:
            KeymapResult with extraction information

        Raises:
            KeymapError: If splitting fails
        """
        logger.info("Extracting layers for %s to %s", profile.keyboard_name, output_dir)

        result = KeymapResult(success=False)

        try:
            # Convert to dictionary for internal processing
            validated_data = keymap_data.model_dump()

            # Create output directories
            output_dir = output_dir.resolve()
            output_layer_dir = output_dir / "layers"
            self._file_adapter.mkdir(output_dir)
            self._file_adapter.mkdir(output_layer_dir)

            # Extract components
            self._extract_dtsi_snippets(validated_data, output_dir)
            self._extract_base_config(validated_data, output_dir)
            self._extract_individual_layers(validated_data, output_layer_dir)

            result.success = True
            result.layer_count = len(validated_data.get("layers", []))
            result.add_message(f"Successfully extracted layers to {output_dir}")
            result.add_message(
                f"Created base.json and {result.layer_count} layer files"
            )

            return result

        except Exception as e:
            result.add_error(f"Layer extraction failed: {e}")
            logger.error("Layer extraction failed: %s", e)
            raise KeymapError(f"Layer extraction failed: {e}") from e

    def merge_layers(
        self,
        profile: KeyboardProfile,
        base_data: KeymapData,
        layers_dir: Path,
        output_file: Path,
    ) -> KeymapResult:
        """Merge layer files from a directory structure back into a single keymap JSON file.

        Args:
            profile: Keyboard profile containing configuration
            base_data: Base keymap data without layers
            layers_dir: Directory containing individual layer files
            output_file: Path where the merged keymap will be saved

        Returns:
            KeymapResult with merge information

        Raises:
            KeymapError: If merging fails
        """
        logger.info(
            "Combining layers from %s for %s", layers_dir, profile.keyboard_name
        )

        result = KeymapResult(success=False)

        try:
            layers_dir = layers_dir.resolve()
            output_file = output_file.resolve()

            # Validate directory existence
            if not self._file_adapter.is_dir(layers_dir):
                raise KeymapError(f"Layers directory not found: {layers_dir}")

            # Validate and convert to dictionary
            validated_base = base_data.model_dump()

            # Create output directory if needed
            self._file_adapter.mkdir(output_file.parent)

            # Process layers
            self._process_layers_for_combination(validated_base, layers_dir)

            # Add DTSI content from separate files
            parent_dir = layers_dir.parent
            self._add_dtsi_content_from_files(validated_base, parent_dir)

            # Write the final combined keymap
            self._file_adapter.write_json(output_file, validated_base)

            result.success = True
            result.json_path = output_file
            result.layer_count = len(validated_base.get("layers", []))
            result.add_message(
                f"Successfully combined keymap and saved to {output_file}"
            )
            result.add_message(
                f"Combined {result.layer_count} layers from {layers_dir}"
            )

            return result

        except Exception as e:
            result.add_error(f"Layer combination failed: {e}")
            logger.error("Layer combination failed: %s", e)
            raise KeymapError(f"Layer combination failed: {e}") from e

    def show(
        self,
        profile: KeyboardProfile,
        keymap_data: KeymapData,
        key_width: int = 10,
    ) -> str:
        """Show the keyboard layout from keymap data.

        Args:
            profile: Keyboard profile containing configuration
            keymap_data: Validated keymap data model
            key_width: Width of keys in the display (default: 10)

        Returns:
            Formatted string representation of the keyboard layout

        Raises:
            KeymapError: If display generation fails
        """
        logger.info("Generating keyboard layout display")

        try:
            # Convert to dictionary for internal processing
            validated_data = keymap_data.model_dump()

            # Extract layout information
            title = (
                validated_data.get("title")
                or validated_data.get("name")
                or "Untitled Layout"
            )
            creator = validated_data.get("creator", "N/A")
            locale = validated_data.get("locale", "N/A")
            notes = validated_data.get("notes", "")
            keyboard = validated_data.get("keyboard", "N/A")
            layer_names = validated_data.get("layer_names", [])
            layers = validated_data.get("layers", [])

            if not layers:
                raise KeymapError("No layers found in the keymap data")

            # Handle missing or mismatched layer names
            if not layer_names:
                logger.warning("No layer names found, using default names")
                layer_names = [f"Layer {i}" for i in range(len(layers))]
            elif len(layer_names) != len(layers):
                logger.warning(
                    "Mismatch between layer names (%d) and layer data (%d). Using available names.",
                    len(layer_names),
                    len(layers),
                )
                if len(layer_names) < len(layers):
                    layer_names = layer_names + [
                        f"Layer {i}" for i in range(len(layer_names), len(layers))
                    ]
                else:
                    layer_names = layer_names[: len(layers)]

            # Generate formatted layout
            layout_text = self._generate_layout_display(
                title, creator, locale, notes, keyboard, layer_names, layers, key_width
            )

            logger.info("Successfully generated keyboard layout display")
            return layout_text

        except Exception as e:
            logger.error("Error generating layout display: %s", e)
            raise KeymapError(f"Failed to generate layout display: {e}") from e

    def validate(
        self,
        profile: KeyboardProfile,
        keymap_data: KeymapData,
    ) -> bool:
        """Validate keymap data structure and content.

        Args:
            profile: Keyboard profile containing configuration
            keymap_data: Keymap data to validate

        Returns:
            True if validation passes

        Raises:
            KeymapError: If validation fails
        """
        logger.debug("Validating keymap data structure")

        try:
            # Keymap data is already validated through Pydantic
            # We just need to check that it matches the profile requirements
            keyboard_name = profile.keyboard_name
            keymap_keyboard = keymap_data.keyboard

            # Check keyboard type compatibility
            if keymap_keyboard and keyboard_name and keymap_keyboard != keyboard_name:
                logger.warning(
                    "Keyboard type mismatch: keymap has '%s', config has '%s'",
                    keymap_keyboard,
                    keyboard_name,
                )

            # Check layer count is reasonable
            if len(keymap_data.layers) > 10:  # Arbitrary reasonable limit
                logger.warning(
                    "High layer count detected: %d layers", len(keymap_data.layers)
                )

            logger.debug(
                "Keymap data validation successful for %s", profile.keyboard_name
            )
            return True
        except Exception as e:
            logger.error("Keymap data validation failed: %s", e)
            raise KeymapError(f"Keymap validation failed: {e}") from e

    # Private helper methods

    def _register_system_behaviors(self, profile: KeyboardProfile) -> None:
        """Register system behaviors from keyboard profile.

        Args:
            profile: KeyboardProfile instance with system behaviors
        """
        keyboard_name = profile.keyboard_name
        logger.debug("Registering system behaviors for keyboard: %s", keyboard_name)

        # Get system behaviors from the profile
        behaviors = profile.system_behaviors

        # Register each behavior
        for behavior in behaviors:
            name = behavior.name
            expected_params = behavior.expected_params
            origin = behavior.origin

            if name:
                logger.debug(
                    "Registering behavior %s with %s params from %s",
                    name,
                    expected_params,
                    origin,
                )
                self._behavior_registry.register_behavior(name, expected_params, origin)
            else:
                logger.warning("Skipping behavior without name: %s", behavior)

        logger.debug("Registered behaviors for %s", profile.keyboard_name)

    def _generate_config_file(
        self,
        json_data: dict[str, Any],
        kconfig_options: dict[str, KConfigOption],
        output_path: Path,
    ) -> dict[str, str]:
        """Generate configuration file and return settings.

        Args:
            json_data: Keymap data containing config parameters
            kconfig_options: Mapping of kconfig options
            output_path: Path to save the config file

        Returns:
            Dictionary of kconfig settings
        """
        logger.info("Generating Kconfig .conf file...")

        # Create a kconfig map from the options
        kconfig_map = {}
        for name, option in kconfig_options.items():
            kconfig_map[name] = {
                "config_key": f"CONFIG_{name.upper()}",  # Default naming convention
                "type": option.type,
            }

        conf_content, kconfig_settings = self._config_generator.generate_kconfig(
            json_data, kconfig_map
        )
        self._file_adapter.write_text(output_path, conf_content)
        logger.info("Successfully generated config and saved to %s", output_path)
        return kconfig_settings

    def _generate_keymap_file(
        self,
        json_data: dict[str, Any],
        profile: KeyboardProfile,
        output_path: Path,
    ) -> None:
        """Generate keymap file.

        Args:
            json_data: Keymap data with layers and behaviors
            profile: KeyboardProfile instance with configuration
            output_path: Path to save the generated keymap file
        """
        profile_name = f"{profile.keyboard_name}/{profile.firmware_version}"
        logger.info("Building .keymap file")

        # Prepare template context
        context = self._build_template_context(json_data, profile)

        # Get template content directly from keymap configuration
        template_content = profile.keyboard_config.keymap.keymap_dtsi

        # Render template
        if template_content:
            keymap_content = self._template_adapter.render_string(
                template_content, context
            )
        else:
            raise KeymapError(
                "No keymap_dtsi template available in keyboard configuration"
            )

        self._file_adapter.write_text(output_path, keymap_content)
        logger.info("Successfully built keymap and saved to %s", output_path)

    def _build_template_context(
        self,
        json_data: dict[str, Any],
        profile: KeyboardProfile,
    ) -> dict[str, Any]:
        """Build template context with generated DTSI content.

        Args:
            json_data: Keymap data
            profile: Keyboard profile with configuration

        Returns:
            Dictionary with template context
        """
        # Extract data for generation
        layer_names = json_data.get("layer_names", [])
        layers_data = json_data.get("layers", [])
        hold_taps_data = json_data.get("holdTaps", [])
        combos_data = json_data.get("combos", [])
        macros_data = json_data.get("macros", [])
        input_listeners_data = json_data.get("inputListeners", [])

        # Get resolved includes from the profile
        resolved_includes = (
            profile.keyboard_config.keymap.includes
            if hasattr(profile.keyboard_config.keymap, "includes")
            else []
        )

        # Generate DTSI components
        layer_defines = self._dtsi_generator.generate_layer_defines(
            profile, layer_names
        )
        keymap_node = self._dtsi_generator.generate_keymap_node(
            profile, layer_names, layers_data
        )
        behaviors_dtsi = self._dtsi_generator.generate_behaviors_dtsi(
            profile, hold_taps_data
        )
        combos_dtsi = self._dtsi_generator.generate_combos_dtsi(
            profile, combos_data, layer_names
        )
        macros_dtsi = self._dtsi_generator.generate_macros_dtsi(profile, macros_data)
        input_listeners_dtsi = self._dtsi_generator.generate_input_listeners_node(
            profile, input_listeners_data
        )

        # Get template elements from the keyboard profile
        key_position_header = (
            profile.keyboard_config.keymap.key_position_header
            if hasattr(profile.keyboard_config.keymap, "key_position_header")
            else ""
        )
        system_behaviors_dts = (
            profile.keyboard_config.keymap.system_behaviors_dts
            if hasattr(profile.keyboard_config.keymap, "system_behaviors_dts")
            else ""
        )

        # Profile identifiers
        profile_name = f"{profile.keyboard_name}/{profile.firmware_version}"
        firmware_version = profile.firmware_version

        return {
            "keyboard": json_data.get("keyboard", "unknown"),
            "layer_names": layer_names,
            "layers": layers_data,
            "layer_defines": layer_defines,
            "keymap_node": keymap_node,
            "user_behaviors_dtsi": behaviors_dtsi,
            "combos_dtsi": combos_dtsi,
            "input_listeners_dtsi": input_listeners_dtsi,
            "user_macros_dtsi": macros_dtsi,
            "resolved_includes": "\n".join(resolved_includes),
            "key_position_header": key_position_header,
            "system_behaviors_dts": system_behaviors_dts,
            "custom_defined_behaviors": json_data.get("custom_defined_behaviors", ""),
            "custom_devicetree": json_data.get("custom_devicetree", ""),
            "profile_name": profile_name,
            "firmware_version": firmware_version,
            "generation_timestamp": datetime.now().isoformat(),
        }

    # Helper methods for extraction

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

    def _extract_base_config(self, keymap: dict[str, Any], output_dir: Path) -> None:
        """Extract base configuration to base.json.

        Args:
            keymap: Keymap data
            output_dir: Directory to write base configuration
        """
        base_keymap = keymap.copy()

        # Remove layer-specific and custom code fields
        fields_to_empty = ["layers", "custom_defined_behaviors", "custom_devicetree"]
        for field in fields_to_empty:
            if field in base_keymap:
                if isinstance(base_keymap[field], list):
                    base_keymap[field] = []
                elif isinstance(base_keymap[field], dict):
                    base_keymap[field] = {}
                elif isinstance(base_keymap[field], str):
                    base_keymap[field] = ""

        # Ensure essential fields exist
        essential_fields: dict[str, list[Any] | dict[str, Any]] = {
            "layer_names": [],
            "macros": [],
            "combos": [],
            "holdTaps": [],
            "kconfig": {},
        }
        for field, default_value in essential_fields.items():
            if field not in base_keymap:
                base_keymap[field] = default_value

        # Handle date field
        if isinstance(base_keymap.get("date"), datetime):
            base_keymap["date"] = base_keymap["date"].isoformat()
        elif "date" not in base_keymap:
            base_keymap["date"] = datetime.now().isoformat()

        output_file = output_dir / "base.json"
        self._file_adapter.write_json(output_file, base_keymap)
        logger.info("Extracted base configuration to %s", output_file)

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
        original_date_str = keymap.get("date", "")
        if not original_date_str:
            original_date_str = datetime.now().isoformat()

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
            layer_keymap = {
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
        layer_names = combined_keymap["layer_names"]
        logger.info(
            "Expecting %d layers based on base.json: %s", len(layer_names), layer_names
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
                            "Layer '%s' from %s has %d keys, expected %d. Padding/truncating.",
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
                        "Layer data missing or invalid in %s for layer '%s'. Using empty layer.",
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


def create_keymap_service(
    file_adapter: FileAdapter | None = None,
    template_adapter: TemplateAdapter | None = None,
) -> KeymapService:
    """Create a KeymapService instance with optional dependency injection.

    Args:
        file_adapter: Optional file adapter (creates default if None)
        template_adapter: Optional template adapter (creates default if None)

    Returns:
        Configured KeymapService instance
    """
    logger.debug(
        "Creating KeymapService with%s file adapter, %s template adapter",
        "" if file_adapter else " default",
        "" if template_adapter else " default",
    )

    if file_adapter is None:
        from glovebox.adapters.file_adapter import create_file_adapter

        file_adapter = create_file_adapter()

    if template_adapter is None:
        from glovebox.adapters.template_adapter import create_template_adapter

        template_adapter = create_template_adapter()

    return KeymapService(file_adapter, template_adapter)
