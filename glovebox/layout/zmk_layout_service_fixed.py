"""ZMK Layout Integration Service.
This service bridges glovebox with the zmk-layout library for enhanced
JSON to DTSI conversion capabilities using the complete fluent API.
"""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, Optional, Union

from zmk_layout import create_default_providers
from zmk_layout.core import Layout
from zmk_layout.core.exceptions import LayoutError, ValidationError

from glovebox.adapters.zmk_layout.provider_factory import create_glovebox_providers
from glovebox.core.structlog_logger import StructlogMixin
from glovebox.layout.models import LayoutData, LayoutResult
from glovebox.models.base import GloveboxBaseModel


class ZmkLayoutIntegrationService(GloveboxBaseModel, StructlogMixin):
    """Service that integrates zmk-layout library with glovebox pipeline.

    This service provides complete zmk-layout API integration including:
    - Fluent layout creation and manipulation
    - Layer management with chaining
    - Behavior definitions (hold-taps, combos, macros)
    - Multiple export formats (keymap, config, JSON)
    - Comprehensive validation and error handling
    """

    def __init__(
        self,
        keyboard_id: str | None = None,
        services: dict[str, Any] | None = None,
    ) -> None:
        # Initialize both parent classes properly
        GloveboxBaseModel.__init__(self)
        StructlogMixin.__init__(self)

        self.keyboard_id = keyboard_id

        # Create glovebox providers for zmk-layout
        self.providers = create_glovebox_providers(
            keyboard_id=keyboard_id, services=services
        )

        # Create default zmk-layout providers as fallback
        self.zmk_providers = create_default_providers()

        self.logger.info(
            "zmk_layout_service_initialized",
            keyboard_id=keyboard_id,
            has_services=services is not None,
        )

    def compile_layout(
        self, layout_data: LayoutData, output_dir: Path | None = None
    ) -> LayoutResult:
        """Compile layout data to ZMK files using zmk-layout library fluent API.
        Args:
            layout_data: Glovebox layout data model
            output_dir: Optional output directory for files
        Returns:
            LayoutResult with generated content
        """
        try:
            self.logger.info(
                "compiling_layout_with_zmk_library",
                keyboard=layout_data.keyboard,
                layers=len(layout_data.layers),
                keyboard_id=self.keyboard_id,
            )

            # Convert glovebox LayoutData to zmk-layout JSON format
            json_data = layout_data.to_dict()

            # Create layout using zmk-layout fluent API
            layout = Layout.from_dict(json_data, providers=self.zmk_providers)

            # Validate the layout before compilation
            try:
                layout.validate()
            except ValidationError as e:
                self.logger.warning(
                    "layout_validation_warnings",
                    validation_error=str(e),
                )

            # Generate keymap content using fluent export API
            keymap_content = (
                layout.export.keymap()
                .with_headers(True)
                .with_behaviors(True)
                .with_combos(True)
                .with_macros(True)
                .with_tap_dances(True)
                .generate()
            )

            # Generate config content
            config_result = layout.export.config().with_defaults(True).generate()
            config_content = (
                config_result[0] if isinstance(config_result, tuple) else config_result
            )

            # Get layout statistics for reporting
            stats = layout.get_statistics()

            # Write files if output directory specified
            if output_dir:
                output_dir = Path(output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)

                # Write keymap file
                keymap_file = output_dir / f"{layout_data.keyboard}.keymap"
                keymap_file.write_text(keymap_content)

                # Write config file
                config_file = output_dir / f"{layout_data.keyboard}.conf"
                config_file.write_text(config_content)

                # Write JSON file
                json_file = output_dir / f"{layout_data.keyboard}.json"
                json_file.write_text(layout.export.to_json(indent=2))

                self.logger.info(
                    "files_written_to_output_dir",
                    output_dir=str(output_dir),
                    files=["keymap", "conf", "json"],
                )

            # Create successful LayoutResult
            layout_result = LayoutResult(
                success=True,
                keymap_content=keymap_content,
                config_content=config_content,
                json_content=json_data,
                errors=[],
                warnings=[],
                messages=[
                    "Layout compiled successfully with zmk-layout fluent API",
                    f"Generated keymap: {len(keymap_content)} chars",
                    f"Generated config: {len(config_content)} chars",
                    f"Layers: {stats['layer_count']}, Bindings: {stats['total_bindings']}",
                    f"Behaviors: {stats['total_behaviors']} (hold-taps: {stats['behavior_counts']['hold_taps']}, combos: {stats['behavior_counts']['combos']})",
                ],
            )

            self.logger.info(
                "layout_compilation_successful",
                keymap_size=len(keymap_content),
                config_size=len(config_content),
                layer_count=stats["layer_count"],
                behavior_count=stats["total_behaviors"],
                warnings_count=len(layout_result.warnings),
            )

            return layout_result

        except LayoutError as e:
            self.logger.error(
                "layout_export_failed",
                error=str(e),
                keyboard_id=self.keyboard_id,
                exc_info=self.logger.isEnabledFor(logging.DEBUG),
            )
            return LayoutResult(
                success=False,
                keymap_content="",
                config_content="",
                json_content=layout_data.to_dict(),
                errors=[f"Export failed: {e}"],
                warnings=[],
                messages=[],
            )
        except ValidationError as e:
            self.logger.error(
                "layout_validation_failed",
                error=str(e),
                keyboard_id=self.keyboard_id,
                exc_info=self.logger.isEnabledFor(logging.DEBUG),
            )
            return LayoutResult(
                success=False,
                keymap_content="",
                config_content="",
                json_content=layout_data.to_dict(),
                errors=[f"Validation failed: {e}"],
                warnings=[],
                messages=[],
            )
        except Exception as e:
            self.logger.error(
                "layout_compilation_failed",
                error=str(e),
                keyboard_id=self.keyboard_id,
                exc_info=self.logger.isEnabledFor(logging.DEBUG),
            )
            return LayoutResult(
                success=False,
                keymap_content="",
                config_content="",
                json_content=layout_data.to_dict(),
                errors=[f"Compilation failed: {e}"],
                warnings=[],
                messages=[],
            )

    def validate_layout(self, layout_data: LayoutData) -> list[str]:
        """Validate layout data using zmk-layout validation.
        Args:
            layout_data: Layout data to validate
        Returns:
            List of validation errors (empty if valid)
        """
        try:
            self.logger.debug(
                "validating_layout_with_zmk_library",
                keyboard=layout_data.keyboard,
                layers=len(layout_data.layers),
            )

            json_data = layout_data.to_dict()

            # Use zmk-layout fluent validation
            try:
                layout = Layout.from_dict(json_data, providers=self.zmk_providers)
                # The validate() method returns self and raises ValidationError if invalid
                layout.validate()
                errors = []

                # Additional validation using layout statistics
                stats = layout.get_statistics()

                # Check for reasonable limits
                if stats["layer_count"] > 32:
                    errors.append(
                        f"Too many layers: {stats['layer_count']} (limit: 32)"
                    )

                if stats["total_behaviors"] > 100:
                    errors.append(
                        f"Too many behaviors: {stats['total_behaviors']} (limit: 100)"
                    )

                # Check layer sizes are consistent
                if stats.get("min_layer_size", 0) != stats.get("max_layer_size", 0):
                    errors.append(
                        f"Inconsistent layer sizes: min={stats.get('min_layer_size')}, "
                        f"max={stats.get('max_layer_size')}"
                    )

                self.logger.debug(
                    "layout_validation_completed",
                    errors_count=len(errors),
                    layer_count=stats["layer_count"],
                    behavior_count=stats["total_behaviors"],
                )

                return errors

            except ValidationError as ve:
                # Convert ValidationError to list of error strings
                errors = [str(ve)]
                self.logger.debug(
                    "layout_validation_failed",
                    validation_errors=errors,
                )
                return errors

        except Exception as e:
            self.logger.error(
                "layout_validation_failed",
                error=str(e),
                exc_info=self.logger.isEnabledFor(logging.DEBUG),
            )
            return [f"Validation failed: {e}"]

    def create_fluent_layout(self, keyboard: str, title: str = "") -> Layout:
        """Create a new empty layout using zmk-layout fluent API.

        Args:
            keyboard: Keyboard identifier (e.g., "glove80", "corne")
            title: Optional layout title

        Returns:
            Layout instance ready for fluent manipulation
        """
        try:
            self.logger.debug(
                "creating_fluent_layout",
                keyboard=keyboard,
                title=title,
            )

            # Create empty layout using fluent API
            layout = Layout.create_empty(
                keyboard=keyboard,
                title=title or f"New {keyboard} Layout",
                providers=self.zmk_providers,
            )

            self.logger.info(
                "fluent_layout_created",
                keyboard=keyboard,
                title=layout.data.title,
            )

            return layout

        except Exception as e:
            self.logger.error(
                "fluent_layout_creation_failed",
                error=str(e),
                keyboard=keyboard,
                exc_info=self.logger.isEnabledFor(logging.DEBUG),
            )
            raise LayoutError(f"Failed to create fluent layout: {e}") from e

    def manipulate_layers(
        self, layout: Layout, operations: list[dict[str, Any]]
    ) -> Layout:
        """Manipulate layout layers using fluent API operations.

        Args:
            layout: Layout instance to modify
            operations: List of operation dictionaries with keys:
                - action: "add", "remove", "set", "get"
                - layer: layer name
                - position: position for bindings (for "set")
                - binding: binding value (for "set")

        Returns:
            Modified layout instance
        """
        try:
            self.logger.debug(
                "manipulating_layers",
                operations_count=len(operations),
            )

            for op in operations:
                action = op.get("action")
                layer_name = op.get("layer")

                if action == "add":
                    position = op.get("position")
                    layer_proxy = layout.layers.add(str(layer_name), position=position)
                    self.logger.debug(
                        "layer_added",
                        layer=layer_name,
                        position=position,
                    )

                elif action == "remove":
                    layout.layers.remove(str(layer_name))
                    self.logger.debug(
                        "layer_removed",
                        layer=layer_name,
                    )

                elif action == "set":
                    position = op.get("position")
                    binding = op.get("binding")
                    if position is not None and binding is not None:
                        layout.layers.get(str(layer_name)).set(int(position), binding)
                    self.logger.debug(
                        "binding_set",
                        layer=layer_name,
                        position=position,
                        binding=binding,
                    )

                elif action == "get":
                    layer_proxy = layout.layers.get(str(layer_name))
                    self.logger.debug(
                        "layer_accessed",
                        layer=layer_name,
                    )

                else:
                    self.logger.warning(
                        "unknown_layer_operation",
                        action=action,
                        operation=op,
                    )

            return layout

        except Exception as e:
            self.logger.error(
                "layer_manipulation_failed",
                error=str(e),
                exc_info=self.logger.isEnabledFor(logging.DEBUG),
            )
            raise LayoutError(f"Layer manipulation failed: {e}") from e

    def add_behaviors(
        self, layout: Layout, behaviors: dict[str, dict[str, Any]]
    ) -> Layout:
        """Add behavior definitions using fluent API.

        Args:
            layout: Layout instance to modify
            behaviors: Dictionary mapping behavior types to definitions:
                - "hold_taps": {name: {tap: binding, hold: binding, ...}}
                - "combos": {name: {key_positions: [pos], bindings: binding, ...}}
                - "macros": {name: {bindings: [bindings], ...}}

        Returns:
            Modified layout instance
        """
        try:
            self.logger.debug(
                "adding_behaviors",
                behavior_types=list(behaviors.keys()),
            )

            # Add hold-tap behaviors
            if "hold_taps" in behaviors:
                for name, config in behaviors["hold_taps"].items():
                    layout.behaviors.add_hold_tap(
                        name=name,
                        tap=config["tap"],
                        hold=config["hold"],
                        tapping_term_ms=config.get("tapping_term_ms", 200),
                        quick_tap_ms=config.get("quick_tap_ms", 150),
                        flavor=config.get("flavor", "tap-preferred"),
                    )
                    self.logger.debug(
                        "hold_tap_added",
                        name=name,
                        tap=config["tap"],
                        hold=config["hold"],
                    )

            # Add combo behaviors
            if "combos" in behaviors:
                for name, config in behaviors["combos"].items():
                    layout.behaviors.add_combo(
                        name=name,
                        keys=config["key_positions"],
                        binding=config["bindings"],
                        timeout_ms=config.get("timeout_ms", 50),
                        layers=config.get("layers"),
                    )
                    self.logger.debug(
                        "combo_added",
                        name=name,
                        key_positions=config["key_positions"],
                        bindings=config["bindings"],
                    )

            # Add macro behaviors
            if "macros" in behaviors:
                for name, config in behaviors["macros"].items():
                    layout.behaviors.add_macro(
                        name=name,
                        sequence=config["bindings"],
                        tap_ms=config.get("tap_ms", 30),
                        wait_ms=config.get("wait_ms", 30),
                    )
                    self.logger.debug(
                        "macro_added",
                        name=name,
                        bindings=config["bindings"],
                    )

            # Add tap dance behaviors
            if "tap_dances" in behaviors:
                for name, config in behaviors["tap_dances"].items():
                    layout.behaviors.add_tap_dance(
                        name=name,
                        bindings=config["bindings"],
                        tapping_term_ms=config.get("tapping_term_ms", 200),
                    )
                    self.logger.debug(
                        "tap_dance_added",
                        name=name,
                        bindings=config["bindings"],
                    )

            return layout

        except Exception as e:
            self.logger.error(
                "behavior_addition_failed",
                error=str(e),
                exc_info=self.logger.isEnabledFor(logging.DEBUG),
            )
            raise LayoutError(f"Behavior addition failed: {e}") from e

    def export_multiple_formats(
        self, layout: Layout, formats: list[str]
    ) -> dict[str, str | tuple[str, dict[str, Any]]]:
        """Export layout to multiple formats using fluent API.

        Args:
            layout: Layout to export
            formats: List of format names ("keymap", "config", "json", "dict")

        Returns:
            Dictionary mapping format names to exported content
        """
        try:
            self.logger.debug(
                "exporting_multiple_formats",
                formats=formats,
            )

            results: dict[str, str | tuple[str, dict[str, Any]]] = {}

            if "keymap" in formats:
                results["keymap"] = (
                    layout.export.keymap()
                    .with_headers(True)
                    .with_behaviors(True)
                    .with_combos(True)
                    .with_macros(True)
                    .with_tap_dances(True)
                    .generate()
                )

            if "config" in formats:
                config_result = (
                    layout.export.config()
                    .with_defaults(True)
                    .generate()  # Returns tuple (content, settings)
                )
                results["config"] = config_result

            if "json" in formats:
                results["json"] = layout.export.to_json(indent=2)

            if "dict" in formats:
                results["dict"] = str(layout.export.to_dict())

            self.logger.info(
                "multiple_formats_exported",
                formats=list(results.keys()),
                sizes={
                    fmt: len(content)
                    if isinstance(content, str)
                    else len(content[0])
                    if isinstance(content, tuple)
                    else len(str(content))
                    for fmt, content in results.items()
                },
            )

            return results

        except Exception as e:
            self.logger.error(
                "multiple_format_export_failed",
                error=str(e),
                exc_info=self.logger.isEnabledFor(logging.DEBUG),
            )
            raise LayoutError(f"Multiple format export failed: {e}") from e

    def get_supported_keyboards(self) -> list[str]:
        """Get list of keyboards supported by zmk-layout.
        Returns:
            List of supported keyboard IDs
        """
        try:
            # This would typically come from zmk-layout's keyboard registry
            # For now, return what we know from glovebox
            supported = [
                "glove80",
                "corne",
                "lily58",
                "sofle",
                "planck",
                "crkbd",
                "kyria",
            ]

            self.logger.debug(
                "retrieved_supported_keyboards",
                count=len(supported),
                keyboards=supported,
            )
            return supported

        except Exception as e:
            self.logger.error(
                "failed_to_get_supported_keyboards",
                error=str(e),
                exc_info=self.logger.isEnabledFor(logging.DEBUG),
            )
            return []

    def get_compiler_info(self) -> dict[str, Any]:
        """Get information about zmk-layout compiler capabilities.
        Returns:
            Dictionary with compiler information
        """
        try:
            # Try to get zmk-layout version
            try:
                import zmk_layout

                version = getattr(zmk_layout, "__version__", "unknown")
            except ImportError:
                version = "not installed"

            info = {
                "library": "zmk-layout",
                "version": version,
                "providers": {
                    "configuration": type(self.providers.configuration).__name__,
                    "template": type(self.providers.template).__name__,
                    "logger": type(self.providers.logger).__name__,
                },
                "capabilities": [
                    "fluent_api_layout_creation",
                    "layer_management_chaining",
                    "behavior_definitions",
                    "multiple_export_formats",
                    "comprehensive_validation",
                    "statistics_reporting",
                    "template_processing",
                    "hold_tap_behaviors",
                    "combo_behaviors",
                    "macro_behaviors",
                    "tap_dance_behaviors",
                ],
                "export_formats": ["keymap", "config", "json", "dict"],
                "supported_behaviors": ["hold_tap", "combo", "macro", "tap_dance"],
                "keyboard_id": self.keyboard_id,
            }

            self.logger.debug("retrieved_compiler_info", **info)
            return info

        except Exception as e:
            self.logger.error(
                "failed_to_get_compiler_info",
                error=str(e),
                exc_info=self.logger.isEnabledFor(logging.DEBUG),
            )
            return {"error": str(e)}

    def batch_operations(
        self, layout: Layout, operations: list[Callable[[Layout], Layout]]
    ) -> Layout:
        """Execute multiple operations using zmk-layout's batch_operation method.

        Args:
            layout: Layout to modify
            operations: List of callable functions that take Layout as argument

        Returns:
            Modified layout instance
        """
        try:
            self.logger.debug(
                "executing_batch_operations",
                operation_count=len(operations),
            )

            # Use zmk-layout's native batch operation method
            result_layout = layout.batch_operation(operations)

            self.logger.info(
                "batch_operations_completed",
                operation_count=len(operations),
            )

            return result_layout

        except Exception as e:
            self.logger.error(
                "batch_operations_failed",
                error=str(e),
                exc_info=self.logger.isEnabledFor(logging.DEBUG),
            )
            raise LayoutError(f"Batch operations failed: {e}") from e


def create_zmk_layout_service(
    keyboard_id: str | None = None,
    services: dict[str, Any] | None = None,
) -> ZmkLayoutIntegrationService:
    """Create ZmkLayoutIntegrationService instance.
    Args:
        keyboard_id: Optional keyboard identifier
        services: Optional service overrides for testing
    Returns:
        Configured ZmkLayoutIntegrationService with full fluent API support
    """
    return ZmkLayoutIntegrationService(
        keyboard_id=keyboard_id,
        services=services,
    )
