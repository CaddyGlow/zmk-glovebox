"""Layout service for all layout-related operations."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile

from glovebox.adapters.file_adapter import create_file_adapter
from glovebox.adapters.template_adapter import create_template_adapter
from glovebox.builders.template_context_builder import create_template_context_builder
from glovebox.core.errors import LayoutError
from glovebox.layout.behavior_analysis import register_layout_behaviors
from glovebox.layout.behavior_formatter import BehaviorFormatterImpl
from glovebox.layout.behavior_service import create_behavior_registry
from glovebox.layout.component_service import (
    LayoutComponentService,
    create_layout_component_service,
)
from glovebox.layout.display_service import (
    LayoutDisplayService,
    create_layout_display_service,
)
from glovebox.layout.models import LayoutData
from glovebox.layout.utils import (
    generate_config_file,
    generate_keymap_file,
    prepare_output_paths,
    process_json_file,
)
from glovebox.layout.zmk_generator import ZmkFileContentGenerator
from glovebox.models.results import LayoutResult
from glovebox.protocols import FileAdapterProtocol, TemplateAdapterProtocol
from glovebox.protocols.behavior_protocols import BehaviorRegistryProtocol
from glovebox.services.base_service import BaseServiceImpl


logger = logging.getLogger(__name__)


class LayoutService(BaseServiceImpl):
    """Service for all layout operations including building, validation, and export.

    Responsible for processing keyboard layout files, generating ZMK configuration
    files, and managing keyboard layers and behaviors.
    """

    def __init__(
        self,
        file_adapter: FileAdapterProtocol,
        template_adapter: TemplateAdapterProtocol,
        behavior_registry: BehaviorRegistryProtocol,
        behavior_formatter: BehaviorFormatterImpl,
        dtsi_generator: ZmkFileContentGenerator,
        component_service: LayoutComponentService,
        layout_service: LayoutDisplayService,
        context_builder: Any,
    ):
        """Initialize layout service with all dependencies explicitly provided."""
        super().__init__(service_name="LayoutService", service_version="1.0.0")

        # Store all dependencies
        self._file_adapter = file_adapter
        self._template_adapter = template_adapter
        self._behavior_registry = behavior_registry
        self._behavior_formatter = behavior_formatter
        self._dtsi_generator = dtsi_generator
        self._component_service = component_service
        self._layout_service = layout_service
        self._context_builder = context_builder

    # File-based public methods

    def generate_from_file(
        self,
        profile: "KeyboardProfile",
        json_file_path: Path,
        output_file_prefix: str | Path,
        force: bool = False,
    ) -> LayoutResult:
        """Generate ZMK keymap files from a JSON file path."""
        return process_json_file(
            json_file_path,
            "Keymap generation",
            lambda data: self.generate(profile, data, output_file_prefix, force),
            self._file_adapter,
        )

    def extract_components_from_file(
        self,
        profile: "KeyboardProfile",
        json_file_path: Path,
        output_dir: Path,
        force: bool = False,
    ) -> LayoutResult:
        """Extract keymap components from a JSON file into separate files."""
        return process_json_file(
            json_file_path,
            "Component extraction",
            lambda data: self.extract_components(profile, data, output_dir, force),
            self._file_adapter,
        )

    def generate_from_directory(
        self,
        profile: "KeyboardProfile",
        components_dir: Path,
        output_file_prefix: str | Path,
        force: bool = False,
    ) -> LayoutResult:
        """Generate keymap components from a directory into a complete keymap."""
        # Read metadata file to get base layout structure
        metadata_file = components_dir / "metadata.json"
        if not metadata_file.exists():
            raise LayoutError(f"Metadata file not found: {metadata_file}")

        metadata_data = self._file_adapter.read_json(metadata_file)
        base_layout = LayoutData.model_validate(metadata_data)

        # Combine components using the component service
        layers_dir = components_dir / "layers"
        combined_layout = self._component_service.combine_components(
            base_layout, layers_dir
        )

        # Generate the combined keymap files using the normal generate process
        return self.generate(profile, combined_layout, output_file_prefix, force)

    def show_from_file(
        self,
        json_file_path: Path,
        profile: "KeyboardProfile",
        layer_index: int | None = None,
        key_width: int
        | None = None,  # Accept but ignore this parameter for CLI compatibility
    ) -> str:
        """Display keymap layout from a JSON file."""
        return process_json_file(
            json_file_path,
            "Layout display",
            lambda data: self.show(data, profile, layer_index),
            self._file_adapter,
        )

    def validate_file(
        self,
        profile: "KeyboardProfile",
        json_file_path: Path,
    ) -> bool:
        """Validate a keymap JSON file."""
        return process_json_file(
            json_file_path,
            "Keymap validation",
            lambda data: self.validate(profile, data),
            self._file_adapter,
        )

    # Data-based public methods

    def generate(
        self,
        profile: "KeyboardProfile",
        keymap_data: LayoutData,
        output_file_prefix: str | Path,
        force: bool = False,
    ) -> LayoutResult:
        """Generate ZMK keymap and config files from keymap data."""
        logger.info("Starting keymap generation for %s", profile.keyboard_name)

        # Prepare output paths
        output_paths = prepare_output_paths(output_file_prefix)

        # Check if output files already exist (unless force=True)
        if not force:
            existing_files = [
                path
                for path in [output_paths.keymap, output_paths.conf]
                if path.exists()
            ]
            if existing_files:
                existing_names = [f.name for f in existing_files]
                raise LayoutError(
                    f"Output files already exist: {existing_names}. Use force=True to overwrite."
                )

        # Ensure output directory exists
        self._file_adapter.mkdir(output_paths.keymap.parent)

        # Initialize result
        result = LayoutResult(success=False)

        try:
            # Register behaviors needed for this layout
            register_layout_behaviors(profile, keymap_data, self._behavior_registry)

            # Generate config file (.conf)
            generate_config_file(
                self._file_adapter,
                self._dtsi_generator,
                profile,
                keymap_data,
                output_paths.conf,
            )
            result.conf_path = output_paths.conf

            # Generate keymap file (.keymap)
            generate_keymap_file(
                self._file_adapter,
                self._template_adapter,
                self._context_builder,
                keymap_data,
                profile,
                output_paths.keymap,
            )
            result.keymap_path = output_paths.keymap

            # Save original JSON file for reference
            self._file_adapter.write_json(
                output_paths.json, keymap_data.model_dump(mode="json", by_alias=True)
            )
            result.json_path = output_paths.json

            result.success = True
            logger.info("Keymap generation completed successfully")

        except Exception as e:
            logger.error("Keymap generation failed: %s", e)
            result.errors.append(str(e))
            raise LayoutError(f"Keymap generation failed: {e}") from e

        return result

    def extract_components(
        self,
        profile: "KeyboardProfile",
        keymap_data: LayoutData,
        output_dir: Path,
        force: bool = False,
    ) -> LayoutResult:
        """Extract keymap components into separate files."""
        # The component service method doesn't need profile and force parameters
        return self._component_service.extract_components(keymap_data, output_dir)

    def show(
        self,
        keymap_data: LayoutData,
        profile: "KeyboardProfile",
        layer_index: int | None = None,
    ) -> str:
        """Display keymap layout as formatted text."""
        logger.debug("Displaying keymap layout")

        try:
            # Use the layout display service to generate the layout
            return self._layout_service.generate_display(
                keymap_data, profile.keyboard_name
            )
        except Exception as e:
            logger.error("Layout display failed: %s", e)
            raise LayoutError(f"Failed to generate layout display: {e}") from e

    def validate(
        self,
        profile: "KeyboardProfile",
        keymap_data: LayoutData,
    ) -> bool:
        """Validate keymap data structure and content."""
        logger.debug("Validating keymap data structure")

        try:
            # Keymap data is already validated through Pydantic
            # We just need to check that it matches the profile requirements
            profile_keyboard_type = profile.keyboard_name
            keymap_keyboard_type = keymap_data.keyboard

            # Check keyboard type compatibility
            if (
                keymap_keyboard_type
                and profile_keyboard_type
                and keymap_keyboard_type != profile_keyboard_type
            ):
                logger.warning(
                    "Keyboard type mismatch: keymap has '%s', config has '%s'",
                    keymap_keyboard_type,
                    profile_keyboard_type,
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
            raise LayoutError(f"Keymap validation failed: {e}") from e


def create_layout_service(
    file_adapter: FileAdapterProtocol | None = None,
    template_adapter: TemplateAdapterProtocol | None = None,
    behavior_registry: BehaviorRegistryProtocol | None = None,
    component_service: LayoutComponentService | None = None,
    layout_service: LayoutDisplayService | None = None,
    behavior_formatter: BehaviorFormatterImpl | None = None,
    dtsi_generator: ZmkFileContentGenerator | None = None,
    context_builder: Any | None = None,
) -> LayoutService:
    """Create a LayoutService instance with optional dependency injection."""
    logger.debug(
        "Creating LayoutService with dependencies (using defaults where None provided)",
    )

    # Create default dependencies if not provided
    if file_adapter is None:
        file_adapter = create_file_adapter()

    if template_adapter is None:
        template_adapter = create_template_adapter()

    if behavior_registry is None:
        temp_registry = create_behavior_registry()
        behavior_registry = temp_registry

    if behavior_formatter is None:
        behavior_formatter = BehaviorFormatterImpl(behavior_registry)

    if dtsi_generator is None:
        dtsi_generator = ZmkFileContentGenerator(behavior_formatter)

    if component_service is None:
        component_service = create_layout_component_service(file_adapter)

    if layout_service is None:
        layout_service = create_layout_display_service()

    if context_builder is None:
        context_builder = create_template_context_builder(dtsi_generator)

    # Create service instance with all dependencies
    return LayoutService(
        file_adapter=file_adapter,
        template_adapter=template_adapter,
        behavior_registry=behavior_registry,
        behavior_formatter=behavior_formatter,
        dtsi_generator=dtsi_generator,
        component_service=component_service,
        layout_service=layout_service,
        context_builder=context_builder,
    )
