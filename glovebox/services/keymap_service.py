"""Keymap service for all keymap-related operations."""

import json
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Optional, Protocol, cast, runtime_checkable

from glovebox.adapters.file_adapter import FileAdapter
from glovebox.adapters.template_adapter import TemplateAdapter
from glovebox.builders.template_context_builder import (
    create_template_context_builder,
)
from glovebox.config.profile import KeyboardProfile
from glovebox.core.errors import KeymapError
from glovebox.formatters.behavior_formatter import (
    BehaviorFormatterImpl,
)
from glovebox.formatters.behavior_formatter import (
    BehaviorRegistry as FormatterBehaviorRegistry,
)
from glovebox.generators.dtsi_generator import DTSIGenerator
from glovebox.models.keymap import (
    ComboBehavior,
    HoldTapBehavior,
    InputListener,
    KeymapBinding,
    KeymapData,
    LayerBindings,
    MacroBehavior,
)
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


@runtime_checkable
class BehaviorRegistryAdapter(FormatterBehaviorRegistry, Protocol):
    """Protocol to adapt between different BehaviorRegistry implementations."""

    pass


@runtime_checkable
class DTSIGeneratorAdapter(Protocol):
    """Protocol to adapt DTSIGenerator implementation."""

    def generate_layer_defines(
        self, profile: KeyboardProfile, layer_names: list[str]
    ) -> str:
        """Generate layer define statements."""
        ...

    def generate_keymap_node(
        self,
        profile: KeyboardProfile,
        layer_names: list[str],
        layers_data: list[LayerBindings],
    ) -> str:
        """Generate keymap node content."""
        ...

    def generate_behaviors_dtsi(
        self, profile: KeyboardProfile, hold_taps_data: Sequence[HoldTapBehavior]
    ) -> str:
        """Generate behaviors DTSI content."""
        ...

    def generate_combos_dtsi(
        self,
        profile: KeyboardProfile,
        combos_data: Sequence[ComboBehavior],
        layer_names: list[str],
    ) -> str:
        """Generate combos DTSI content."""
        ...

    def generate_macros_dtsi(
        self, profile: KeyboardProfile, macros_data: Sequence[MacroBehavior]
    ) -> str:
        """Generate macros DTSI content."""
        ...

    def generate_input_listeners_node(
        self, profile: KeyboardProfile, input_listeners_data: Sequence[InputListener]
    ) -> str:
        """Generate input listeners node content."""
        ...

    def generate_kconfig_conf(
        self, keymap_data: KeymapData, profile: KeyboardProfile
    ) -> tuple[str, dict[str, str]]:
        """Generate kconfig content and settings."""
        ...


class KeymapService(BaseServiceImpl):
    """Service for all keymap operations including building, validation, and export.

    Responsible for processing keyboard layout files, generating ZMK configuration
    files, and managing keyboard layers and behaviors.
    """

    def __init__(
        self,
        file_adapter: FileAdapter,
        template_adapter: TemplateAdapter,
        behavior_registry: FormatterBehaviorRegistry,
        behavior_formatter: BehaviorFormatterImpl,
        dtsi_generator: DTSIGeneratorAdapter,
        component_service: KeymapComponentService,
        layout_service: LayoutDisplayService,
        context_builder: Any,
    ):
        """Initialize keymap service with all dependencies explicitly provided.

        Args:
            file_adapter: Adapter for file system operations
            template_adapter: Adapter for template rendering
            behavior_registry: Registry for keyboard behaviors
            behavior_formatter: Formatter for behavior definitions
            dtsi_generator: Generator for device tree source include files
            component_service: Service for keymap component operations
            layout_service: Service for keyboard layout display
            context_builder: Builder for template context
        """
        super().__init__(service_name="KeymapService", service_version="1.0.0")

        # Store all dependencies
        self._file_adapter = file_adapter
        self._template_adapter = template_adapter
        self._behavior_registry = behavior_registry
        self._behavior_formatter = behavior_formatter
        self._dtsi_generator = dtsi_generator
        self._component_service = component_service
        self._layout_service = layout_service
        self._context_builder = context_builder

    def compile_from_file(
        self,
        profile: KeyboardProfile,
        json_file_path: Path,
        target_prefix: str,
        force: bool = False,
    ) -> KeymapResult:
        """Compile ZMK keymap files from a JSON file path.

        This method handles file existence checks, JSON parsing and validation.

        Args:
            profile: Keyboard profile containing configuration
            json_file_path: Path to keymap JSON file
            target_prefix: Base path and name for output files
            force: Whether to overwrite existing files

        Returns:
            KeymapResult with paths to generated files and build metadata

        Raises:
            KeymapError: If compilation process fails
        """
        logger.info("Reading keymap JSON from %s...", json_file_path)

        result = KeymapResult(success=False)

        try:
            # Check if the file exists
            if not json_file_path.exists():
                raise KeymapError(f"Input file not found: {json_file_path}")

            # Load JSON data
            json_data = self._load_json_file(json_file_path)

            # Validate as KeymapData
            keymap_data = self._validate_keymap_data(json_data)

            # Compile using the validated data
            return self.compile(profile, keymap_data, target_prefix, force)

        except Exception as e:
            result.add_error(f"Keymap compilation failed: {e}")
            logger.error("Keymap compilation failed: %s", e)
            raise KeymapError(f"Keymap compilation failed: {e}") from e

    def validate_file(
        self,
        profile: KeyboardProfile,
        json_file_path: Path,
    ) -> bool:
        """Validate a keymap file including file existence and JSON parsing.

        Args:
            profile: Keyboard profile containing configuration
            json_file_path: Path to keymap JSON file

        Returns:
            True if validation passes

        Raises:
            KeymapError: If validation fails
        """
        logger.info("Validating keymap file %s...", json_file_path)

        try:
            # Check if the file exists
            if not json_file_path.exists():
                raise KeymapError(f"Input file not found: {json_file_path}")

            # Load JSON data
            json_data = self._load_json_file(json_file_path)

            # Validate as KeymapData
            keymap_data = self._validate_keymap_data(json_data)

            # Validate against profile
            return self.validate(profile, keymap_data)

        except Exception as e:
            logger.error("Keymap validation failed: %s", e)
            raise KeymapError(f"Keymap validation failed: {e}") from e

    def show_from_file(
        self,
        profile: KeyboardProfile | None,
        json_file_path: Path,
        key_width: int = 10,
    ) -> str:
        """Show the keyboard layout from a keymap file.

        Args:
            profile: Keyboard profile containing configuration (optional)
            json_file_path: Path to keymap JSON file
            key_width: Width of keys in the display

        Returns:
            Formatted string representation of the keyboard layout

        Raises:
            KeymapError: If display generation fails
        """
        logger.info("Generating keyboard layout display from %s...", json_file_path)

        try:
            # Check if the file exists
            if not json_file_path.exists():
                raise KeymapError(f"Input file not found: {json_file_path}")

            # Load JSON data
            json_data = self._load_json_file(json_file_path)

            # Validate as KeymapData
            keymap_data = self._validate_keymap_data(json_data)

            # Show using the validated data
            return self.show(profile, keymap_data, key_width)

        except Exception as e:
            logger.error("Error generating layout display: %s", e)
            raise KeymapError(f"Failed to generate layout display: {e}") from e

    def split_keymap_from_file(
        self,
        profile: KeyboardProfile,
        keymap_file_path: Path,
        output_dir: Path,
        force: bool = False,
    ) -> KeymapResult:
        """Split a keymap file into individual layer files.

        Args:
            profile: Keyboard profile containing configuration
            keymap_file_path: Path to keymap JSON file
            output_dir: Directory to save extracted files
            force: Whether to overwrite existing files

        Returns:
            KeymapResult with extraction information

        Raises:
            KeymapError: If splitting fails
        """
        logger.info("Extracting layers from %s to %s...", keymap_file_path, output_dir)

        try:
            # Check if the file exists
            if not keymap_file_path.exists():
                raise KeymapError(f"Input file not found: {keymap_file_path}")

            # Load JSON data
            json_data = self._load_json_file(keymap_file_path)

            # Validate as KeymapData
            keymap_data = self._validate_keymap_data(json_data)

            # Create output directory if needed
            if not output_dir.exists():
                self._file_adapter.mkdir(output_dir)

            # Split keymap using the validated data
            return self.split_keymap(profile, keymap_data, output_dir)

        except Exception as e:
            logger.error("Layer extraction failed: %s", e)
            raise KeymapError(f"Layer extraction failed: {e}") from e

    def merge_layers_from_files(
        self,
        profile: KeyboardProfile,
        input_dir: Path,
        output_file: Path,
        force: bool = False,
    ) -> KeymapResult:
        """Merge layer files into a single keymap file.

        Args:
            profile: Keyboard profile containing configuration
            input_dir: Directory with metadata.json and layers/ subdirectory
            output_file: Path where the merged keymap will be saved
            force: Whether to overwrite existing files

        Returns:
            KeymapResult with merge information

        Raises:
            KeymapError: If merging fails
        """
        logger.info("Combining layers from %s to %s...", input_dir, output_file)

        try:
            # Check if the input directory exists
            if not input_dir.exists():
                raise KeymapError(f"Input directory not found: {input_dir}")

            # Check for metadata.json
            metadata_json_path = input_dir / "metadata.json"
            if not metadata_json_path.exists():
                raise KeymapError(f"Metadata JSON file not found: {metadata_json_path}")

            # Load metadata data
            metadata_json = self._load_json_file(metadata_json_path)
            metadata_data = self._validate_keymap_data(metadata_json)

            # Check for layers directory
            layers_dir = input_dir / "layers"
            if not layers_dir.exists():
                raise KeymapError(f"Layers directory not found: {layers_dir}")

            # Check if output file exists and force is not set
            if output_file.exists() and not force:
                raise KeymapError(
                    f"Output file already exists: {output_file}. Use --force to overwrite."
                )

            # Merge layers using the validated data
            return self.merge_layers(profile, metadata_data, layers_dir, output_file)

        except Exception as e:
            logger.error("Layer combination failed: %s", e)
            raise KeymapError(f"Layer combination failed: {e}") from e

    def compile(
        self,
        profile: KeyboardProfile,
        keymap_data: KeymapData,
        target_prefix: str,
        force: bool = False,
    ) -> KeymapResult:
        """Compile ZMK keymap files from keymap data.

        Args:
            profile: Keyboard profile containing configuration
            keymap_data: Validated keymap data model
            target_prefix: Base path and name for output files
            force: Whether to overwrite existing files

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
            # Get layer count for result
            result.layer_count = len(keymap_data.layers)

            # Prepare output paths and create directory
            output_paths = prepare_output_paths(target_prefix)

            # Check if files exist and force is not set
            for path_type, path in output_paths.items():
                if path.exists() and not force:
                    raise KeymapError(
                        f"{path_type} file already exists: {path}. Use --force to overwrite."
                    )

            # Create output directory
            self._file_adapter.mkdir(output_paths["keymap"].parent)

            # Register system behaviors directly from profile
            from glovebox.services.behavior_service import BehaviorRegistry

            profile.register_behaviors(cast(BehaviorRegistry, self._behavior_registry))

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
            # Delegate to component service
            return self._component_service.extract_components(keymap_data, output_dir)

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
        """Merge layer files into a single keymap JSON file.

        Combines base keymap with layer files and outputs a complete keymap.

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
            # Create output directory if needed
            self._file_adapter.mkdir(output_file.parent)

            # Delegate to component service
            combined_keymap = self._component_service.combine_components(
                base_data, layers_dir
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
        profile: KeyboardProfile | None,
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
            # Delegate to the layout display service
            keyboard_name = profile.keyboard_name if profile else "unknown"
            return self._layout_service.generate_display(
                keymap_data, keyboard_name, key_width
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

    def _load_json_file(self, file_path: Path) -> dict[str, Any]:
        """Load and parse JSON from a file.

        Args:
            file_path: Path to the JSON file

        Returns:
            Parsed JSON data as a dictionary

        Raises:
            KeymapError: If JSON parsing fails
        """
        try:
            json_text = file_path.read_text()
            result = json.loads(json_text)
            if not isinstance(result, dict):
                raise KeymapError(
                    f"Expected JSON object in file {file_path}, got {type(result)}"
                )
            return result
        except json.JSONDecodeError as e:
            raise KeymapError(f"Invalid JSON in file {file_path}: {e}") from e
        except Exception as e:
            raise KeymapError(f"Error reading file {file_path}: {e}") from e

    def _validate_keymap_data(self, json_data: dict[str, Any]) -> KeymapData:
        """Validate JSON data as KeymapData.

        Args:
            json_data: JSON data to validate

        Returns:
            Validated KeymapData model

        Raises:
            KeymapError: If validation fails
        """
        try:
            from glovebox.models.keymap import KeymapData

            return KeymapData.model_validate(json_data)
        except Exception as e:
            raise KeymapError(f"Invalid keymap data: {e}") from e

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

        # Use the DTSIGenerator to generate the config
        conf_content, kconfig_settings = self._dtsi_generator.generate_kconfig_conf(
            keymap_data, profile
        )

        # Write the config file
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
        logger.info(
            "Building .keymap file for %s/%s",
            profile.keyboard_name,
            profile.firmware_version,
        )

        # Build template context using the context builder
        context = self._context_builder.build_context(keymap_data, profile)

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
    behavior_registry: FormatterBehaviorRegistry | None = None,
    component_service: KeymapComponentService | None = None,
    layout_service: LayoutDisplayService | None = None,
    behavior_formatter: BehaviorFormatterImpl | None = None,
    dtsi_generator: DTSIGenerator | None = None,
    context_builder: Any | None = None,
) -> KeymapService:
    """Create a KeymapService instance with optional dependency injection.

    Args:
        file_adapter: Optional file adapter (creates default if None)
        template_adapter: Optional template adapter (creates default if None)
        behavior_registry: Optional behavior registry (creates default if None)
        component_service: Optional component service (creates default if None)
        layout_service: Optional layout service (creates default if None)
        behavior_formatter: Optional behavior formatter (creates default if None)
        dtsi_generator: Optional DTSI generator (creates default if None)
        context_builder: Optional template context builder (creates default if None)

    Returns:
        Configured KeymapService instance
    """
    logger.debug(
        "Creating KeymapService with dependencies (using defaults where None provided)",
    )

    # Create default file adapter if not provided
    if file_adapter is None:
        from glovebox.adapters.file_adapter import create_file_adapter

        file_adapter = create_file_adapter()

    # Create default template adapter if not provided
    if template_adapter is None:
        from glovebox.adapters.template_adapter import create_template_adapter

        template_adapter = create_template_adapter()

    # Create default behavior registry if not provided
    if behavior_registry is None:
        temp_registry = create_behavior_registry()
        behavior_registry = cast(FormatterBehaviorRegistry, temp_registry)

    # Create behavior formatter if not provided
    if behavior_formatter is None:
        behavior_formatter = BehaviorFormatterImpl(behavior_registry)

    # Create DTSI generator if not provided
    if dtsi_generator is None:
        dtsi_generator = DTSIGenerator(behavior_formatter)

    # Create component service if not provided
    if component_service is None:
        component_service = create_keymap_component_service(file_adapter)

    # Create layout service if not provided
    if layout_service is None:
        layout_service = create_layout_display_service()

    # Create template context builder if not provided
    if context_builder is None:
        context_builder = create_template_context_builder(
            cast(DTSIGeneratorAdapter, dtsi_generator)
        )

    # Create a new service instance with all dependencies explicitly provided
    return KeymapService(
        file_adapter=file_adapter,
        template_adapter=template_adapter,
        behavior_registry=behavior_registry,
        behavior_formatter=behavior_formatter,
        dtsi_generator=cast(DTSIGeneratorAdapter, dtsi_generator),
        component_service=component_service,
        layout_service=layout_service,
        context_builder=context_builder,
    )
