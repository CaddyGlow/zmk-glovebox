"""Keymap service for all keymap-related operations."""

import logging
from pathlib import Path
from typing import Any, TypeAlias

from glovebox.adapters.file_adapter import FileAdapter
from glovebox.adapters.template_adapter import TemplateAdapter
from glovebox.builders.template_context_builder import (
    create_template_context_builder,
)
from glovebox.config.models import KConfigOption
from glovebox.config.profile import KeyboardProfile
from glovebox.core.errors import KeymapError
from glovebox.formatters.behavior_formatter import BehaviorFormatterImpl
from glovebox.generators.config_generator import create_config_generator
from glovebox.generators.dtsi_generator import DTSIGenerator
from glovebox.models.keymap import KeymapData
from glovebox.models.results import KeymapResult
from glovebox.services.base_service import BaseServiceImpl
from glovebox.services.behavior_service import create_behavior_registry
from glovebox.services.keymap_component_service import (
    KeymapComponentService,
    create_keymap_component_service,
)
from glovebox.services.layout_display_service import (
    LayoutDisplayService,
    create_layout_display_service,
)
from glovebox.utils.file_utils import prepare_output_paths


logger = logging.getLogger(__name__)


# Type alias for internal config mapping
KConfigMap: TypeAlias = dict[str, dict[str, str]]


class KeymapService(BaseServiceImpl):
    """Service for all keymap operations including building, validation, and export.

    Responsible for processing keyboard layout files, generating ZMK configuration
    files, and managing keyboard layers and behaviors.
    """

    def __init__(
        self,
        file_adapter: FileAdapter,
        template_adapter: TemplateAdapter,
        component_service: KeymapComponentService | None = None,
        layout_service: LayoutDisplayService | None = None,
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

        # Initialize delegated services
        self._component_service = component_service or create_keymap_component_service(
            file_adapter
        )
        self._layout_service = layout_service or create_layout_display_service()

        # Initialize builder objects
        self._context_builder = create_template_context_builder(self._dtsi_generator)

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
            result.layer_count = len(keymap_data.layers)

            # Prepare output paths and create directory
            output_paths = prepare_output_paths(target_prefix)
            self._file_adapter.mkdir(output_paths["keymap"].parent)

            # Register system behaviors directly from profile
            profile.register_behaviors(self._behavior_registry)

            # Generate files
            self._generate_config_file(
                profile,
                keymap_data,
                output_paths["conf"],
            )

            self._generate_keymap_file(keymap_data, profile, output_paths["keymap"])

            # Save JSON file to output directory
            self._file_adapter.write_json(
                output_paths["json"], keymap_data.model_dump(mode="json")
            )

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

        try:
            # TODO: Refactor KeymapComponentService to accept KeymapData instead of dict
            # For now, we need to convert to dict because KeymapComponentService expects dict
            validated_data = keymap_data.model_dump()

            # Delegate to component service
            return self._component_service.extract_components(
                validated_data, output_dir
            )

        except Exception as e:
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
            # TODO: Refactor KeymapComponentService to accept KeymapData instead of dict
            # For now, we need to convert to dict because KeymapComponentService expects dict
            validated_base = base_data.model_dump()

            # Create output directory if needed
            self._file_adapter.mkdir(output_file.parent)

            # Delegate to component service
            combined_keymap = self._component_service.combine_components(
                validated_base, layers_dir
            )

            # Write the final combined keymap
            self._file_adapter.write_json(output_file, combined_keymap)

            result.success = True
            result.json_path = output_file
            result.layer_count = len(combined_keymap.get("layers", []))
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
            # TODO: Refactor LayoutDisplayService to accept KeymapData instead of dict
            # For now, we need to convert to dict because LayoutDisplayService expects dict
            validated_data = keymap_data.model_dump()

            # Delegate to the layout display service
            return self._layout_service.generate_display(
                validated_data, profile.keyboard_name, key_width
            )

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

    def _generate_config_file(
        self,
        profile: KeyboardProfile,
        keymap_data: KeymapData,
        output_path: Path,
    ) -> dict[str, str]:
        """Generate configuration file and return settings.

        Args:
            profile: Keyboard profile with configuration options
            keymap_data: Keymap data containing config parameters
            output_path: Path to save the config file

        Returns:
            Dictionary of kconfig settings
        """
        logger.info("Generating Kconfig .conf file...")

        # Get kconfig options from the profile
        kconfig_options = profile.kconfig_options

        # Create a kconfig map from the options
        kconfig_map: KConfigMap = {}
        for name, option in kconfig_options.items():
            kconfig_map[name] = {
                "config_key": f"CONFIG_{name.upper()}",  # Default naming convention
                "type": option.type,
            }

        # TODO: Refactor ConfigGenerator to accept KeymapData instead of dict
        # For now, we need to convert to dict because ConfigGenerator expects dict
        keymap_dict = keymap_data.model_dump()

        conf_content, kconfig_settings = self._config_generator.generate_kconfig(
            keymap_dict, kconfig_map
        )
        self._file_adapter.write_text(output_path, conf_content)
        logger.info("Successfully generated config and saved to %s", output_path)
        return kconfig_settings

    def _generate_keymap_file(
        self,
        keymap_data: KeymapData,
        profile: KeyboardProfile,
        output_path: Path,
    ) -> None:
        """Generate keymap file.

        Args:
            keymap_data: Keymap data with layers and behaviors
            profile: KeyboardProfile instance with configuration
            output_path: Path to save the generated keymap file
        """
        profile_name = f"{profile.keyboard_name}/{profile.firmware_version}"
        logger.info("Building .keymap file")

        # TODO: Refactor TemplateContextBuilder to accept KeymapData instead of dict
        # For now, we need to convert to dict because TemplateContextBuilder expects KeymapDict
        keymap_dict = keymap_data.model_dump()

        # Build template context using the context builder
        context = self._context_builder.build_context(keymap_dict, profile)

        # Get template content from keymap configuration
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


def create_keymap_service(
    file_adapter: FileAdapter | None = None,
    template_adapter: TemplateAdapter | None = None,
    component_service: KeymapComponentService | None = None,
    layout_service: LayoutDisplayService | None = None,
) -> KeymapService:
    """Create a KeymapService instance with optional dependency injection.

    Args:
        file_adapter: Optional file adapter (creates default if None)
        template_adapter: Optional template adapter (creates default if None)
        component_service: Optional component service (creates default if None)
        layout_service: Optional layout service (creates default if None)

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

    return KeymapService(
        file_adapter, template_adapter, component_service, layout_service
    )
