"""Keymap service for all keymap-related operations."""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, cast
from unittest.mock import Mock

from glovebox.adapters.file_adapter import FileAdapter
from glovebox.adapters.template_adapter import TemplateAdapter
from glovebox.config.models import KConfigOption
from glovebox.config.profile import KeyboardProfile
from glovebox.core.errors import KeymapError
from glovebox.formatters.behavior_formatter import BehaviorFormatterImpl
from glovebox.generators.config_generator import ConfigGenerator
from glovebox.generators.dtsi_generator import DTSIGenerator
from glovebox.models.keymap import KeymapData, KeymapLayer
from glovebox.models.results import KeymapResult
from glovebox.services.base_service import BaseServiceImpl
from glovebox.services.behavior_service import BehaviorRegistry
from glovebox.utils.file_utils import prepare_output_paths, sanitize_filename
from glovebox.utils.serialization import make_json_serializable


logger = logging.getLogger(__name__)


# Templates are now accessed directly from keyboard_config.keymap


class KeymapService(BaseServiceImpl):
    """Service for all keymap operations including building, validation, and export.

    Responsible for processing keyboard layout files, generating ZMK configuration
    files, and managing keyboard layers and behaviors.

    Attributes:
        _file_adapter: Adapter for file system operations
        _template_adapter: Adapter for template rendering
        _behavior_registry: Registry for keyboard behaviors
        _behavior_formatter: Formatter for behavior rendering
        _dtsi_generator: Generator for device tree files
        _config_generator: Generator for config files
    """

    def __init__(
        self,
        file_adapter: FileAdapter,
        template_adapter: TemplateAdapter,
    ):
        """Initialize keymap service with adapter dependencies.

        Args:
            file_adapter: Adapter for file system operations
            template_adapter: Adapter for template rendering
        """
        super().__init__(service_name="KeymapService", service_version="1.0.0")
        self._file_adapter = file_adapter
        self._template_adapter = template_adapter

        # Initialize internal components
        # Use factory functions where available
        from glovebox.generators.config_generator import create_config_generator
        from glovebox.services.behavior_service import create_behavior_registry

        # Define typed variables before assignment
        self._behavior_registry: BehaviorRegistry
        self._behavior_formatter: BehaviorFormatterImpl
        self._dtsi_generator: DTSIGenerator
        self._config_generator: ConfigGenerator

        # Initialize components with type annotations
        behavior_registry = create_behavior_registry()
        self._behavior_registry = behavior_registry
        self._behavior_formatter = BehaviorFormatterImpl(behavior_registry)
        self._dtsi_generator = DTSIGenerator(self._behavior_formatter)
        self._config_generator = create_config_generator()

    def compile(
        self,
        profile: KeyboardProfile,
        json_data: dict[str, Any] | KeymapData,
        target_prefix: str,
        source_json_path: Path | None = None,
    ) -> KeymapResult:
        """Compile ZMK keymap files from JSON data.

        Args:
            json_data: Raw keymap JSON data or validated KeymapData
            source_json_path: Optional path to source JSON file
            target_prefix: Base path and name for output files
            keyboard_name: Name of the keyboard to build for
            firmware_version: Version of firmware to use

        Returns:
            KeymapResult with paths to generated files and build metadata

        Raises:
            KeymapError: If compilation process fails
        """
        # Use provided keyboard profile
        profile_name = f"{profile.keyboard_name}/{profile.firmware_version}"
        logger.info(f"Starting keymap build using profile: {profile_name}")

        result = KeymapResult(success=False)
        result.profile_name = profile_name

        try:
            # Validate and prepare input data
            validated_data = self._validate_data(json_data)
            result.layer_count = len(validated_data.get("layers", []))

            # Prepare output paths
            output_paths = self._prepare_output_paths(target_prefix)

            # Create output directory
            self._file_adapter.mkdir(output_paths["keymap"].parent)

            # Register system behaviors
            self._register_system_behaviors(profile)

            # Generate configuration file
            kconfig_settings = self._generate_config_file(
                validated_data,
                profile.keyboard_config.keymap.kconfig_options,
                output_paths["conf"],
            )

            # Generate keymap file
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
                f"Keymap build completed successfully for target '{target_prefix}'."
            )

            return result

        except Exception as e:
            result.add_error(f"Keymap build failed: {e}")
            logger.error(f"Keymap build failed: {e}")
            raise KeymapError(f"Keymap build failed: {e}") from e

    def split(
        self,
        profile: KeyboardProfile,
        keymap_file: Path,
        output_dir: Path,
    ) -> KeymapResult:
        """Split each layer from a keymap JSON file into separate files.

        Creates a directory structure with:
        - base.json: Base keymap configuration without layers
        - device.dtsi: Custom device tree snippets (if present)
        - keymap.dtsi: Custom defined behaviors (if present)
        - layers/: Directory containing individual layer files

        Args:
            keymap_file: Path to the input keymap JSON file
            output_dir: Directory where the extracted structure will be created

        Returns:
            KeymapResult with extraction information

        Raises:
            KeymapError: If splitting fails
        """
        logger.info(
            f"Extracting layers from {keymap_file} to {output_dir} for {profile.keyboard_name}"
        )

        result = KeymapResult(success=False)

        try:
            if not self._file_adapter.is_file(keymap_file):
                raise KeymapError(f"Keymap file not found: {keymap_file}")

            # Load and validate keymap data
            keymap_data = self._file_adapter.read_json(keymap_file)
            validated_data = self._validate_data(keymap_data)

            # Create output directories
            output_dir = output_dir.resolve()
            output_layer_dir = output_dir / "layers"
            self._file_adapter.mkdir(output_dir)
            self._file_adapter.mkdir(output_layer_dir)

            # Extract components
            self._extract_dtsi_snippets(validated_data, output_dir)
            self._extract_base_config(validated_data, output_dir)
            self._extract_individual_layers(
                validated_data, output_layer_dir, keymap_file
            )

            result.success = True
            result.layer_count = len(validated_data.get("layers", []))
            result.add_message(f"Successfully extracted layers to {output_dir}")
            result.add_message(
                f"Created base.json and {result.layer_count} layer files"
            )

            return result

        except Exception as e:
            result.add_error(f"Layer extraction failed: {e}")
            logger.error(f"Layer extraction failed: {e}")
            raise KeymapError(f"Layer extraction failed: {e}") from e

    def merge(
        self,
        profile: KeyboardProfile,
        input_dir: Path,
        output_file: Path,
    ) -> KeymapResult:
        """Merge layer files from a directory structure back into a single keymap JSON file.

        Expects an input directory containing:
        - base.json: The base keymap configuration (metadata, macros, combos, etc.)
        - layers/: A subdirectory containing individual JSON files for each layer
        - device.dtsi (optional): Contains custom device tree snippets
        - keymap.dtsi (optional): Contains custom defined behaviors snippets

        Args:
            input_dir: Directory containing base.json and layers/ subdirectory
            output_file: Path where the merged keymap JSON file will be saved

        Returns:
            KeymapResult with merge information

        Raises:
            KeymapError: If merging fails
        """
        logger.info(
            f"Combining layers from {input_dir} into {output_file} for {profile.keyboard_name}"
        )

        result = KeymapResult(success=False)

        try:
            input_dir = input_dir.resolve()
            output_file = output_file.resolve()

            # Validate input structure
            base_file = input_dir / "base.json"
            layers_dir = input_dir / "layers"

            if not self._file_adapter.is_file(base_file):
                raise KeymapError(f"Base file not found: {base_file}")
            if not self._file_adapter.is_dir(layers_dir):
                raise KeymapError(f"Layers directory not found: {layers_dir}")

            # Load and validate base configuration
            combined_keymap = self._file_adapter.read_json(base_file)
            validated_base = self._validate_data(combined_keymap)

            # Validate base structure
            if "layer_names" not in validated_base or not isinstance(
                validated_base["layer_names"], list
            ):
                raise KeymapError("Invalid or missing 'layer_names' list in base.json")

            # Create output directory if needed
            self._file_adapter.mkdir(output_file.parent)

            # Process layers
            self._process_layers_for_combination(validated_base, layers_dir)

            # Add DTSI content from separate files
            self._add_dtsi_content_from_files(validated_base, input_dir)

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
            logger.error(f"Layer combination failed: {e}")
            raise KeymapError(f"Layer combination failed: {e}") from e

    def show(
        self,
        profile_or_keymap_data: KeyboardProfile | dict[str, Any] | KeymapData,
        keymap_data_or_key_width: dict[str, Any] | KeymapData | int = 10,
        key_width: int = 10,
    ) -> str:
        """Show the keyboard layout from keymap data.

        This method supports both the new interface with KeyboardProfile and
        the legacy interface for testing.

        New interface:
            show(profile: KeyboardProfile, keymap_data: dict[str, Any] | KeymapData, key_width: int = 10)

        Legacy interface for tests:
            show(keymap_data: dict[str, Any] | KeymapData, key_width: int = 10)
        """
        # Handle the legacy interface for tests
        if not isinstance(profile_or_keymap_data, KeyboardProfile):
            # In this case, profile_or_keymap_data is actually the keymap_data
            # and keymap_data_or_key_width is either key_width or KeymapData
            keymap_data = profile_or_keymap_data

            if isinstance(keymap_data_or_key_width, int):
                # Legacy call: show(keymap_data, key_width)
                key_width = keymap_data_or_key_width
            else:
                # This shouldn't typically happen, but handle it just in case
                keymap_data = keymap_data_or_key_width

            # Create a minimal KeyboardProfile for backwards compatibility
            keyboard_name = (
                keymap_data.get("keyboard", "unknown")
                if isinstance(keymap_data, dict)
                else "unknown"
            )

            # Create a mock KeyboardProfile
            profile = Mock(spec=KeyboardProfile)
            profile.keyboard_name = keyboard_name
            profile.firmware_version = "default"
        else:
            # New interface
            profile = profile_or_keymap_data
            keymap_data = keymap_data_or_key_width

        # Proceed with display generation
        logger.info("Generating keyboard layout display")

        try:
            # Validate and normalize keymap data
            validated_data = self._validate_data(keymap_data)

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

            if not layer_names:
                logger.warning("No layer names found, using default names")
                layer_names = [f"Layer {i}" for i in range(len(layers))]
            elif len(layer_names) != len(layers):
                logger.warning(
                    f"Mismatch between layer names ({len(layer_names)}) and layer data ({len(layers)}). Using available names."
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
            logger.error(f"Error generating layout display: {e}")
            raise KeymapError(f"Failed to generate layout display: {e}") from e

    def validate(
        self,
        profile: KeyboardProfile,
        keymap_data: dict[str, Any] | KeymapData,
    ) -> bool:
        """Validate keymap data structure and content.

        Args:
            keymap_data: Keymap data to validate (dict or KeymapData model)

        Returns:
            True if validation passes

        Raises:
            KeymapError: If validation fails
        """
        logger.debug("Validating keymap data structure")

        try:
            # Use internal validation method
            self._validate_data(keymap_data)
            logger.debug(
                f"Keymap data validation successful for {profile.keyboard_name}"
            )
            return True
        except Exception as e:
            logger.error(f"Keymap data validation failed: {e}")
            raise KeymapError(f"Keymap validation failed: {e}") from e

    def validate_config(
        self,
        profile_or_keymap_data: KeyboardProfile | dict[str, Any] | KeymapData,
        keymap_data_or_config: dict[str, Any] | KeymapData | None = None,
    ) -> bool:
        """Validate that keymap data is compatible with the given keyboard configuration.

        This method supports both the new interface with KeyboardProfile and
        the legacy interface for testing.

        New interface:
            validate_config(profile: KeyboardProfile, keymap_data: dict[str, Any] | KeymapData)

        Legacy interface for tests:
            validate_config(keymap_data: dict[str, Any] | KeymapData, keyboard_config: dict[str, Any])
        """
        # Handle the legacy interface for tests
        if not isinstance(profile_or_keymap_data, KeyboardProfile):
            # In this case, profile_or_keymap_data is actually the keymap_data
            # and keymap_data_or_config is the keyboard_config
            if keymap_data_or_config is None:
                raise ValueError(
                    "Missing required keyboard_config parameter for legacy interface"
                )

            keymap_data = profile_or_keymap_data
            keyboard_config = keymap_data_or_config

            # Create a minimal KeyboardProfile for backwards compatibility
            from glovebox.config.keyboard_config import KeyboardConfig

            # Make a simple profile from the keyboard_config
            if isinstance(keyboard_config, dict):
                keyboard_name = keyboard_config.get("keyboard", "unknown")
                config = KeyboardConfig(
                    name=keyboard_name,
                    description="Test keyboard",
                    key_count=80,
                    keymap=keyboard_config.get("keymap", {}),
                )
                profile = Mock(spec=KeyboardProfile)
                profile.keyboard_name = keyboard_name
                profile.keyboard_config = config
            else:
                # It's already a mocked KeyboardConfig
                profile = Mock(spec=KeyboardProfile)
                profile.keyboard_name = getattr(keyboard_config, "name", "unknown")
                profile.keyboard_config = keyboard_config
        else:
            # New interface
            profile = profile_or_keymap_data
            keymap_data = keymap_data_or_config
        # Proceed with validation
        keyboard_name = profile.keyboard_name
        logger.debug(f"Validating keymap compatibility with keyboard: {keyboard_name}")

        try:
            validated_data = self._validate_data(keymap_data)

            # Check keyboard type compatibility
            keymap_keyboard = validated_data.get("keyboard", "")
            if keymap_keyboard and keyboard_name and keymap_keyboard != keyboard_name:
                logger.warning(
                    f"Keyboard type mismatch: keymap has '{keymap_keyboard}', config has '{keyboard_name}'"
                )

            # Check layer count is reasonable
            layers = validated_data.get("layers", [])
            if len(layers) > 10:  # Arbitrary reasonable limit
                logger.warning(f"High layer count detected: {len(layers)} layers")

            return True

        except Exception as e:
            logger.error(f"Keymap-config compatibility validation failed: {e}")
            raise KeymapError(f"Compatibility validation failed: {e}") from e

    # Private helper methods

    def _validate_data(self, json_data: dict[str, Any] | KeymapData) -> dict[str, Any]:
        """Validate and normalize keymap data. Following Moergo JSON schema"""
        if isinstance(json_data, KeymapData):
            return json_data.to_dict()
        else:
            # Validate using Pydantic model
            keymap_model = KeymapData.model_validate(json_data)
            return keymap_model.to_dict()

    def _prepare_output_paths(self, target_prefix: str) -> dict[str, Path]:
        """Prepare output file paths."""
        return prepare_output_paths(target_prefix)

    def _register_system_behaviors(self, profile: KeyboardProfile) -> None:
        """Register system behaviors from keyboard profile.

        Args:
            profile: KeyboardProfile instance with system behaviors
        """
        keyboard_name = profile.keyboard_name
        logger.debug(f"Registering system behaviors for keyboard: {keyboard_name}")

        # Get system behaviors from the profile
        behaviors = profile.system_behaviors

        # Register each behavior
        for behavior in behaviors:
            name = behavior.name
            expected_params = behavior.expected_params
            origin = behavior.origin

            if name:
                logger.debug(
                    f"Registering behavior {name} with {expected_params} params from {origin}"
                )
                self._behavior_registry.register_behavior(name, expected_params, origin)
            else:
                logger.warning(f"Skipping behavior without name: {behavior}")

        # Register fallbacks for essential behaviors
        # For the moment, we'll just comment out the fallbacks
        # fallback_behaviors = {
        #     "&bl": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&bootloader": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&bt": {"expected_params": -1, "origin": "zmk_fallback"},
        #     "&caps_lock": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&caps_word": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&cc": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&cp": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&ext_power": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&hml": {"expected_params": 2, "origin": "zmk_fallback"},
        #     "&hmr": {"expected_params": 2, "origin": "zmk_fallback"},
        #     "&hm": {"expected_params": 2, "origin": "zmk_fallback"},
        #     "&inc_dec_cc": {"expected_params": 2, "origin": "zmk_fallback"},
        #     "&inc_dec_cp": {"expected_params": 2, "origin": "zmk_fallback"},
        #     "&inc_dec_kp": {"expected_params": 2, "origin": "zmk_fallback"},
        #     "&key_repeat": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&kp": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&led_off": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&led_on": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&led_temp_on": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&led_toggle": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&lt": {"expected_params": 2, "origin": "zmk_fallback"},
        #     "&macro_param_1to1": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&macro_param_1to2": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&macro_param_2to1": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&macro_param_2to2": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&macro_pause_for_release": {
        #         "expected_params": 0,
        #         "origin": "zmk_fallback",
        #     },
        #     "&macro_press": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&macro_release": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&macro_tap": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&macro_wait_time": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&mkp": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&mmv": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&mo": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&msc": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&mt": {"expected_params": 2, "origin": "zmk_fallback"},
        #     "&none": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&num_lock": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&out": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&prof": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&reset": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&rgb_ug": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&scroll_lock": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&sensor_rotate": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&sk": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&sl": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&sys_reset": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&tog": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&to": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&trans": {"expected_params": 0, "origin": "zmk_fallback"},
        # }

        # # Add fallbacks only for behaviors not already registered
        # for name, info in fallback_behaviors.items():
        #     if name not in self._behavior_registry._behaviors:
        #         logger.debug(f"Adding fallback behavior: {name}")
        #         self._behavior_registry._behaviors[name] = info
        #
        logger.debug(f"Registered behaviors for {profile.keyboard_name}")

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
        logger.info(f"Successfully generated config and saved to {output_path}")
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
        logger.info(f"Successfully built keymap and saved to {output_path}")

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
        from datetime import datetime

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

        # Create layout configuration from profile
        from glovebox.generators.layout_generator import LayoutConfig, LayoutMetadata

        # Create a layout config from the keyboard configuration
        layout_metadata = LayoutMetadata(
            keyboard_type=profile.keyboard_name,
            description=profile.keyboard_config.description,
            keyboard=profile.keyboard_name,
        )

        # Use a default key position map
        key_position_map = {}
        for i in range(profile.keyboard_config.key_count):
            key_position_map[f"KEY_{i}"] = i

        # Create the layout config
        # Get rows from formatting, defaulting to empty list if None
        config_rows = profile.keyboard_config.keymap.formatting.rows or []

        layout_config = LayoutConfig(
            keyboard_name=profile.keyboard_name,
            key_width=profile.keyboard_config.keymap.formatting.default_key_width,
            key_gap=profile.keyboard_config.keymap.formatting.key_gap,
            key_position_map=key_position_map,
            total_keys=profile.keyboard_config.key_count,
            key_count=profile.keyboard_config.key_count,
            rows=config_rows,
            metadata=layout_metadata,
            formatting={
                "default_key_width": profile.keyboard_config.keymap.formatting.default_key_width,
                "key_gap": profile.keyboard_config.keymap.formatting.key_gap,
                "base_indent": profile.keyboard_config.keymap.formatting.base_indent,
            },
        )

        # Generate layer defines
        layer_defines = self._dtsi_generator.generate_layer_defines(
            profile, layer_names
        )

        # Generate DTSI components
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

        # Get key position header from profile if available
        key_position_header = (
            profile.keyboard_config.keymap.key_position_header
            if hasattr(profile.keyboard_config.keymap, "key_position_header")
            else ""
        )

        # Get system behaviors DTS from profile if available
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
        """Extract custom DTSI snippets to separate files."""
        device_dtsi = keymap.get("custom_devicetree", "")
        behaviors_dtsi = keymap.get("custom_defined_behaviors", "")

        if device_dtsi:
            device_dtsi_path = output_dir / "device.dtsi"
            self._file_adapter.write_text(device_dtsi_path, device_dtsi)
            logger.info(f"Extracted custom_devicetree to {device_dtsi_path}")

        if behaviors_dtsi:
            keymap_dtsi_path = output_dir / "keymap.dtsi"
            self._file_adapter.write_text(keymap_dtsi_path, behaviors_dtsi)
            logger.info(f"Extracted custom_defined_behaviors to {keymap_dtsi_path}")

    def _extract_base_config(self, keymap: dict[str, Any], output_dir: Path) -> None:
        """Extract base configuration to base.json."""
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
        from datetime import datetime

        if isinstance(base_keymap.get("date"), datetime):
            base_keymap["date"] = base_keymap["date"].isoformat()
        elif "date" not in base_keymap:
            base_keymap["date"] = datetime.now().isoformat()

        output_file = output_dir / "base.json"
        self._file_adapter.write_json(output_file, base_keymap)
        logger.info(f"Extracted base configuration to {output_file}")

    def _extract_individual_layers(
        self, keymap: dict[str, Any], output_layer_dir: Path, keymap_file: Path
    ) -> None:
        """Extract individual layers to separate JSON files."""
        layer_names = keymap.get("layer_names", [])
        layers_data = keymap.get("layers", [])

        if not layer_names or not layers_data:
            logger.warning(
                "No layer names or data found. Cannot extract individual layers."
            )
            return

        logger.info(f"Extracting {len(layer_names)} layers...")
        original_date_str = keymap.get("date", "")
        if not original_date_str:
            from datetime import datetime

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
                    f"Could not find data for layer index {i} ('{layer_name}'). Skipping."
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
            self._file_adapter.write_json(output_file, layer_keymap)
            logger.info(f"Extracted layer '{layer_name}' to {output_file}")

    # Helper methods for combination

    def _process_layers_for_combination(
        self, combined_keymap: dict[str, Any], layers_dir: Path
    ) -> None:
        """Process and combine layer files."""
        combined_keymap["layers"] = []
        layer_names = combined_keymap["layer_names"]
        logger.info(
            f"Expecting {len(layer_names)} layers based on base.json: {layer_names}"
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
                    f"Layer file '{layer_file.name}' not found for layer '{layer_name}'. Adding empty layer."
                )
                combined_keymap["layers"].append(empty_layer)
                continue

            logger.info(f"Processing layer '{layer_name}' from file: {layer_file.name}")

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
                            f"Layer '{layer_name}' from {layer_file.name} has {len(actual_layer_content)} keys, "
                            f"expected {num_keys}. Padding/truncating."
                        )
                        # Pad or truncate the layer to match expected size
                        actual_layer_content = (actual_layer_content + empty_layer)[
                            :num_keys
                        ]

                    combined_keymap["layers"].append(actual_layer_content)
                    logger.info(f"Added layer '{layer_name}' (index {i})")
                    found_layer_count += 1
                else:
                    logger.warning(
                        f"Layer data missing or invalid in {layer_file.name} for layer '{layer_name}'. Using empty layer."
                    )
                    combined_keymap["layers"].append(empty_layer)

            except Exception as e:
                logger.error(
                    f"Error processing layer file {layer_file.name}: {e}. Adding empty layer."
                )
                combined_keymap["layers"].append(empty_layer)

        logger.info(
            f"Successfully processed {found_layer_count} out of {len(layer_names)} expected layers."
        )

    def _add_dtsi_content_from_files(
        self, combined_keymap: dict[str, Any], input_dir: Path
    ) -> None:
        """Add DTSI content from separate files to combined keymap."""
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

    def _generate_layout_display(
        self,
        title: str,
        creator: str,
        locale: str,
        notes: str,
        keyboard: str,
        layer_names: list[str],
        layers: list[list[dict[str, Any]]],
        key_width: int,
    ) -> str:
        """Generate formatted layout display text using DtsiLayoutGenerator."""
        from glovebox.generators.layout_generator import (
            DtsiLayoutGenerator,
            LayoutConfig,
            LayoutMetadata,
            ViewMode,
        )

        # Create a layout generator
        layout_generator = DtsiLayoutGenerator()

        # Prepare keymap data for the generator
        keymap_data = {
            "title": title,
            "creator": creator,
            "locale": locale,
            "notes": notes,
            "keyboard": keyboard,
            "layer_names": layer_names,
            "layers": layers,
        }

        # Get Glove80 layout structure for rows
        layout_structure = self._get_glove80_layout_structure()

        # Flatten the structure to get all row indices
        all_rows = []
        for indices_pair in layout_structure.values():
            row = []
            row.extend(indices_pair[0])  # Left side
            row.extend(indices_pair[1])  # Right side
            all_rows.append(row)

        # Create a layout config
        layout_metadata = LayoutMetadata(
            keyboard_type=keyboard,
            description=f"{keyboard} layout",
            keyboard=keyboard,
        )

        # Create a key position map
        key_position_map = {}
        for i in range(80):  # Glove80 default
            key_position_map[f"KEY_{i}"] = i

        # Create the layout config
        layout_config = LayoutConfig(
            keyboard_name=keyboard,
            key_width=key_width,
            key_gap=" ",
            key_position_map=key_position_map,
            total_keys=80,
            key_count=80,
            rows=all_rows,
            metadata=layout_metadata,
            formatting={
                "default_key_width": key_width,
                "key_gap": " ",
                "base_indent": "",
            },
        )

        # Generate the layout display
        return layout_generator.generate_keymap_display(
            keymap_data, layout_config, ViewMode.NORMAL
        )

    def _get_glove80_layout_structure(self) -> dict[str, list[list[int]]]:
        """Get the Glove80 keyboard layout structure."""
        return {
            "row0": [[0, 1, 2, 3, 4], [5, 6, 7, 8, 9]],
            "row1": [[10, 11, 12, 13, 14, 15], [16, 17, 18, 19, 20, 21]],
            "row2": [[22, 23, 24, 25, 26, 27], [28, 29, 30, 31, 32, 33]],
            "row3": [[34, 35, 36, 37, 38, 39], [40, 41, 42, 43, 44, 45]],
            "row4": [[46, 47, 48, 49, 50, 51], [58, 59, 60, 61, 62, 63]],
            "row5": [[64, 65, 66, 67, 68], [75, 76, 77, 78, 79]],
            "thumb1": [[69, 52], [57, 74]],
            "thumb2": [[70, 53], [56, 73]],
            "thumb3": [[71, 54], [55, 72]],
        }

    # These methods were replaced by DtsiLayoutGenerator functionality


def create_keymap_service(
    file_adapter: FileAdapter | None = None,
    template_adapter: TemplateAdapter | None = None,
) -> KeymapService:
    """Create a KeymapService instance with optional dependency injection.

    This factory function provides a consistent way to create service instances
    with proper dependency injection. It allows for easier testing and
    configuration of services.

    Args:
        file_adapter: Optional file adapter (creates default if None)
        template_adapter: Optional template adapter (creates default if None)

    Returns:
        Configured KeymapService instance

    Example:
        >>> service = create_keymap_service()
        >>> result = service.compile(profile, json_data, target_prefix, source_path)
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
