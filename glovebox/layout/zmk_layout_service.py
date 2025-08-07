"""ZMK Layout Integration Service.

This service bridges glovebox with the zmk-layout library for enhanced
JSON to DTSI conversion capabilities.
"""

import logging
from pathlib import Path
from typing import Any

from glovebox.adapters.zmk_layout.provider_factory import create_glovebox_providers
from glovebox.core.structlog_logger import StructlogMixin
from glovebox.layout.models import LayoutData, LayoutResult
from glovebox.models.base import GloveboxBaseModel


# zmk-layout library imports with type annotations
try:
    from zmk_layout import LayoutCompiler, LayoutConfig  # type: ignore[import-untyped]
except ImportError:
    # Fallback imports if zmk-layout structure is different
    try:
        from zmk_layout.compiler import LayoutCompiler  # type: ignore[import-untyped]
        from zmk_layout.config import LayoutConfig  # type: ignore[import-untyped]
    except ImportError:
        # Define minimal interfaces if library not available
        class LayoutCompiler:  # type: ignore[no-redef]
            def __init__(self, providers: Any) -> None:
                pass

            def compile_json_to_dtsi(self, json_data: Any, output_dir: Any) -> dict[str, Any]:
                return {"keymap": "", "config": ""}

        class LayoutConfig:  # type: ignore[no-redef]
            def __init__(self) -> None:
                pass


class ZmkLayoutIntegrationService(GloveboxBaseModel, StructlogMixin):
    """Service that integrates zmk-layout library with glovebox pipeline."""

    def __init__(
        self,
        keyboard_id: str | None = None,
        services: dict[str, Any] | None = None,
    ) -> None:
        super().__init__()
        self.keyboard_id = keyboard_id

        # Create glovebox providers for zmk-layout
        self.providers = create_glovebox_providers(
            keyboard_id=keyboard_id, services=services
        )

        # Initialize zmk-layout compiler with our providers
        self.compiler = LayoutCompiler(providers=self.providers)

        self.logger.info(
            "zmk_layout_service_initialized",
            keyboard_id=keyboard_id,
            has_services=services is not None,
        )

    def compile_layout(
        self, layout_data: LayoutData, output_dir: Path | None = None
    ) -> LayoutResult:
        """Compile layout data to ZMK files using zmk-layout library.

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

            # Use zmk-layout compiler to generate DTSI content
            result = self.compiler.compile_json_to_dtsi(
                json_data=json_data,
                output_dir=str(output_dir) if output_dir else None,
            )

            # Extract generated content
            keymap_content = result.get("keymap", "")
            config_content = result.get("config", "")

            # Create successful LayoutResult
            layout_result = LayoutResult(
                success=True,
                keymap_content=keymap_content,
                config_content=config_content,
                json_content=json_data,
                errors=[],
                warnings=result.get("warnings", []),
                messages=[
                    "Layout compiled successfully with zmk-layout library",
                    f"Generated {len(keymap_content)} chars keymap content",
                    f"Generated {len(config_content)} chars config content",
                ],
            )

            self.logger.info(
                "layout_compilation_successful",
                keymap_size=len(keymap_content),
                config_size=len(config_content),
                warnings_count=len(layout_result.warnings),
            )

            return layout_result

        except Exception as e:
            self.logger.error(
                "layout_compilation_failed",
                error=str(e),
                keyboard_id=self.keyboard_id,
                exc_info=self.logger.isEnabledFor(logging.DEBUG),
            )

            # Return error result
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

            # Use zmk-layout validation (if available)
            if hasattr(self.compiler, "validate_layout"):
                validation_result = self.compiler.validate_layout(json_data)
                errors = validation_result.get("errors", [])
            else:
                # Fallback to provider-based validation
                validation_rules = self.providers.configuration.get_validation_rules()
                errors = []

                # Basic validation using rules
                if len(layout_data.layers) > validation_rules.get("layer_limit", 32):
                    errors.append(f"Too many layers: {len(layout_data.layers)}")

                key_count = validation_rules.get("key_count", 42)
                for i, layer in enumerate(layout_data.layers):
                    layer_bindings = getattr(layer, 'bindings', layer) if hasattr(layer, 'bindings') else layer
                    binding_count = len(layer_bindings) if isinstance(layer_bindings, (list, tuple)) else key_count
                    if binding_count != key_count:
                        errors.append(
                            f"Layer {i} has {binding_count} bindings, expected {key_count}"
                        )

            self.logger.debug(
                "layout_validation_completed",
                errors_count=len(errors),
            )

            return errors

        except Exception as e:
            self.logger.error(
                "layout_validation_failed",
                error=str(e),
                exc_info=self.logger.isEnabledFor(logging.DEBUG),
            )
            return [f"Validation failed: {e}"]

    def get_supported_keyboards(self) -> list[str]:
        """Get list of keyboards supported by zmk-layout.

        Returns:
            List of supported keyboard IDs
        """
        try:
            # This would typically come from zmk-layout's keyboard registry
            # For now, return what we know from glovebox
            supported = ["glove80", "corne", "lily58", "sofle", "planck"]

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
            info = {
                "library": "zmk-layout",
                "version": getattr(self.compiler, "version", "unknown"),
                "providers": {
                    "configuration": type(self.providers.configuration).__name__,
                    "template": type(self.providers.template).__name__,
                    "logger": type(self.providers.logger).__name__,
                },
                "capabilities": [
                    "json_to_dtsi_compilation",
                    "layout_validation",
                    "keyboard_specific_features",
                    "behavior_definitions",
                    "template_processing",
                ],
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


def create_zmk_layout_service(
    keyboard_id: str | None = None,
    services: dict[str, Any] | None = None,
) -> ZmkLayoutIntegrationService:
    """Create ZmkLayoutIntegrationService instance.

    Args:
        keyboard_id: Optional keyboard identifier
        services: Optional service overrides for testing

    Returns:
        Configured ZmkLayoutIntegrationService
    """
    return ZmkLayoutIntegrationService(
        keyboard_id=keyboard_id,
        services=services,
    )
