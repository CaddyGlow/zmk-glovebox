"""Layout service for all layout-related operations."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from glovebox.layout.formatting import ViewMode


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile

from glovebox.adapters.file_adapter import create_file_adapter
from glovebox.adapters.template_adapter import create_template_adapter

# Template context building moved to layout/utils.py as build_template_context()
from glovebox.core.errors import LayoutError
from glovebox.layout.behavior.analysis import register_layout_behaviors
from glovebox.layout.behavior.formatter import BehaviorFormatterImpl
from glovebox.layout.behavior.service import create_behavior_registry
from glovebox.layout.component_service import (
    LayoutComponentService,
    create_layout_component_service,
)
from glovebox.layout.display_service import (
    LayoutDisplayService,
    create_layout_display_service,
)
from glovebox.layout.models import LayoutData, LayoutResult
from glovebox.layout.utils import (
    generate_config_file,
    generate_keymap_file,
    prepare_output_paths,
    process_json_file,
)
from glovebox.layout.zmk_generator import ZmkFileContentGenerator
from glovebox.protocols import FileAdapterProtocol, TemplateAdapterProtocol
from glovebox.protocols.behavior_protocols import BehaviorRegistryProtocol
from glovebox.services.base_service import BaseService


logger = logging.getLogger(__name__)


class LayoutService(BaseService):
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

    def decompose_components_from_file(
        self,
        profile: "KeyboardProfile",
        json_file_path: Path,
        output_dir: Path,
        force: bool = False,
    ) -> LayoutResult:
        """Decompose keymap components from a JSON file into separate files."""
        return process_json_file(
            json_file_path,
            "Component decomposition",
            lambda data: self.decompose_components(profile, data, output_dir, force),
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
        combined_layout = self._component_service.compose_components(
            base_layout, layers_dir
        )

        # Generate the combined keymap files using the normal generate process
        return self.generate(profile, combined_layout, output_file_prefix, force)

    def show_from_file(
        self,
        json_file_path: Path,
        profile: "KeyboardProfile",
        layer_index: int | None = None,
        key_width: int = 12,
        view_mode: ViewMode = ViewMode.NORMAL,
    ) -> str:
        """Display keymap layout from a JSON file."""
        return process_json_file(
            json_file_path,
            "Layout display",
            lambda data: self.show(data, profile, layer_index, view_mode),
            self._file_adapter,
        )

    def validate_from_file(
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

        # Import metrics here to avoid circular dependencies
        try:
            from glovebox.metrics.collector import (  # type: ignore[import-untyped]
                layout_metrics,
            )

            metrics_enabled = True
        except ImportError:
            metrics_enabled = False

        if metrics_enabled:
            with layout_metrics() as metrics:
                metrics.set_context(
                    profile_name=f"{profile.keyboard_name}/{profile.firmware_version}"
                    if profile.firmware_version
                    else profile.keyboard_name,
                    keyboard_name=profile.keyboard_name,
                    firmware_version=profile.firmware_version,
                    layer_count=len(keymap_data.layers) if keymap_data.layers else 0,
                    binding_count=sum(len(layer) for layer in keymap_data.layers)
                    if keymap_data.layers
                    else 0,
                    output_directory=Path(output_file_prefix).parent,
                )
                return self._generate_with_metrics(
                    profile, keymap_data, output_file_prefix, force, metrics
                )
        else:
            return self._generate_core(profile, keymap_data, output_file_prefix, force)

    def _generate_with_metrics(
        self,
        profile: "KeyboardProfile",
        keymap_data: LayoutData,
        output_file_prefix: str | Path,
        force: bool,
        metrics: Any,
    ) -> LayoutResult:
        """Generate ZMK keymap and config files with metrics collection."""
        # Prepare output paths
        with metrics.time_operation("preparation"):
            output_paths = prepare_output_paths(output_file_prefix, profile)

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
            self._file_adapter.create_directory(output_paths.keymap.parent)

        # Initialize result
        result = LayoutResult(success=False)

        # Register behaviors needed for this layout
        with metrics.time_operation("behavior_registration"):
            register_layout_behaviors(profile, keymap_data, self._behavior_registry)

        # Generate config file (.conf)
        with metrics.time_operation("config_generation"):
            generate_config_file(
                self._file_adapter,
                profile,
                keymap_data,
                output_paths.conf,
            )
            result.conf_path = output_paths.conf

        # Generate keymap file (.keymap)
        with metrics.time_operation("keymap_generation"):
            generate_keymap_file(
                self._file_adapter,
                self._template_adapter,
                self._dtsi_generator,
                keymap_data,
                profile,
                output_paths.keymap,
            )
            result.keymap_path = output_paths.keymap

        # Save original JSON file for reference
        with metrics.time_operation("json_saving"):
            self._file_adapter.write_json(
                output_paths.json,
                keymap_data.model_dump(mode="json", by_alias=True, exclude_unset=True),
            )
            result.json_path = output_paths.json

        result.success = True
        logger.info("Keymap generation completed successfully")
        return result

    def _generate_core(
        self,
        profile: "KeyboardProfile",
        keymap_data: LayoutData,
        output_file_prefix: str | Path,
        force: bool = False,
    ) -> LayoutResult:
        """Generate ZMK keymap and config files from keymap data (core implementation without metrics)."""
        # Prepare output paths
        output_paths = prepare_output_paths(output_file_prefix, profile)

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
        self._file_adapter.create_directory(output_paths.keymap.parent)

        # Initialize result
        result = LayoutResult(success=False)

        try:
            # Register behaviors needed for this layout
            register_layout_behaviors(profile, keymap_data, self._behavior_registry)

            # Generate config file (.conf)
            generate_config_file(
                self._file_adapter,
                profile,
                keymap_data,
                output_paths.conf,
            )
            result.conf_path = output_paths.conf

            # Generate keymap file (.keymap)
            generate_keymap_file(
                self._file_adapter,
                self._template_adapter,
                self._dtsi_generator,
                keymap_data,
                profile,
                output_paths.keymap,
            )
            result.keymap_path = output_paths.keymap

            # Save original JSON file for reference
            self._file_adapter.write_json(
                output_paths.json,
                keymap_data.model_dump(mode="json", by_alias=True, exclude_unset=True),
            )
            result.json_path = output_paths.json

            result.success = True
            logger.info("Keymap generation completed successfully")

        except Exception as e:
            logger.error("Keymap generation failed: %s", e)
            result.errors.append(str(e))
            raise LayoutError(f"Keymap generation failed: {e}") from e

        return result

    def decompose_components(
        self,
        profile: "KeyboardProfile",
        keymap_data: LayoutData,
        output_dir: Path,
        force: bool = False,
    ) -> LayoutResult:
        """Decompose keymap components into separate files."""
        # The component service method doesn't need profile and force parameters
        return self._component_service.decompose_components(keymap_data, output_dir)

    def show(
        self,
        keymap_data: LayoutData,
        profile: "KeyboardProfile",
        layer_index: int | None = None,
        view_mode: ViewMode = ViewMode.NORMAL,
    ) -> str:
        """Display keymap layout as formatted text."""
        logger.debug("Displaying keymap layout")

        try:
            # Use the layout display service to generate the layout
            return self._layout_service.show(
                keymap_data, profile, view_mode, layer_index
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

            # Check layer count is reasonable using configurable limit
            validation_limits = profile.keyboard_config.zmk.validation_limits
            if len(keymap_data.layers) > validation_limits.warn_many_layers_threshold:
                logger.warning(
                    "High layer count detected: %d layers (threshold: %d)",
                    len(keymap_data.layers),
                    validation_limits.warn_many_layers_threshold,
                )

            logger.debug(
                "Keymap data validation successful for %s", profile.keyboard_name
            )
            return True
        except Exception as e:
            logger.error("Keymap data validation failed: %s", e)
            raise LayoutError(f"Keymap validation failed: {e}") from e

    def flatten_layout_from_file(
        self,
        json_file_path: Path,
        output_file_path: Path,
    ) -> None:
        """Flatten a layout file by resolving all variables and removing variables section.

        Args:
            json_file_path: Path to the input layout JSON file with variables
            output_file_path: Path to write the flattened layout JSON file

        Raises:
            LayoutError: If file processing fails
        """
        logger.info("Flattening layout from %s to %s", json_file_path, output_file_path)

        def flatten_process(keymap_data: LayoutData) -> None:
            # Get the flattened data
            flattened_data = keymap_data.to_flattened_dict()

            # Write the flattened JSON
            self._file_adapter.write_json(output_file_path, flattened_data)
            logger.info("Layout flattened successfully to %s", output_file_path)

        process_json_file(
            json_file_path,
            "Layout flattening",
            flatten_process,
            self._file_adapter,
        )

    def validate_variables_from_file(
        self,
        json_file_path: Path,
    ) -> list[str]:
        """Validate all variable references in a layout file.

        Args:
            json_file_path: Path to the layout JSON file to validate

        Returns:
            List of validation error messages (empty if all valid)

        Raises:
            LayoutError: If file processing fails
        """
        logger.info("Validating variables in %s", json_file_path)

        def validate_process(keymap_data: LayoutData) -> list[str]:
            # If no variables, return empty error list
            if not keymap_data.variables:
                return []

            # Get the original JSON data to validate variable usage
            json_data = self._file_adapter.read_json(json_file_path)

            from glovebox.layout.utils.variable_resolver import VariableResolver

            resolver = VariableResolver(keymap_data.variables)
            errors = resolver.validate_variables(json_data)

            if errors:
                logger.warning("Variable validation found %d issues", len(errors))
                for error in errors:
                    logger.warning("  - %s", error)
            else:
                logger.info("All variables validated successfully")

            return errors

        return process_json_file(
            json_file_path,
            "Variable validation",
            validate_process,
            self._file_adapter,
        )


def create_layout_service(
    file_adapter: FileAdapterProtocol,
    template_adapter: TemplateAdapterProtocol,
    behavior_registry: BehaviorRegistryProtocol,
    component_service: LayoutComponentService,
    layout_service: LayoutDisplayService,
    behavior_formatter: BehaviorFormatterImpl,
    dtsi_generator: ZmkFileContentGenerator,
) -> LayoutService:
    """Create a LayoutService instance with explicit dependency injection.

    All dependencies are required to ensure proper dependency management.
    Use other factory functions to create the required dependencies:
    - create_file_adapter() for file_adapter
    - create_template_adapter() for template_adapter
    - create_behavior_registry() for behavior_registry
    - create_layout_component_service() for component_service
    - create_layout_display_service() for layout_service
    - BehaviorFormatterImpl(behavior_registry) for behavior_formatter
    - ZmkFileContentGenerator(behavior_formatter) for dtsi_generator
    """
    return LayoutService(
        file_adapter=file_adapter,
        template_adapter=template_adapter,
        behavior_registry=behavior_registry,
        behavior_formatter=behavior_formatter,
        dtsi_generator=dtsi_generator,
        component_service=component_service,
        layout_service=layout_service,
    )
