"""ZMK Layout Integration Service.

This service bridges glovebox with the zmk-layout library for enhanced
JSON to DTSI conversion capabilities.
"""

import logging
from pathlib import Path
from typing import Any

from zmk_layout import create_default_providers
from zmk_layout.core import Layout

from glovebox.adapters.zmk_layout.provider_factory import create_glovebox_providers
from glovebox.core.structlog_logger import StructlogMixin
from glovebox.layout.models import LayoutData, LayoutResult
from glovebox.models.base import GloveboxBaseModel


class ZmkLayoutIntegrationService(GloveboxBaseModel, StructlogMixin):
    """Service that integrates zmk-layout library with glovebox pipeline."""

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

            # Use zmk-layout Layout class to generate content
            layout = Layout.from_dict(json_data, providers=self.zmk_providers)
            keymap_content = layout.export.keymap().generate()

            # Try to generate config content if available
            try:
                config_result = layout.export.config().generate()
                config_content = (
                    config_result[0]
                    if isinstance(config_result, tuple)
                    else config_result
                )
            except Exception:
                # Config generation may not be available for all layouts
                config_content = ""
            # config_content = result.get("config_content", result.get("config", ""))

            # Create successful LayoutResult
            layout_result = LayoutResult(
                success=True,
                keymap_content=keymap_content,
                config_content="",
                json_content=json_data,
                errors=[],
                # warnings=result.get("warnings", []),
                messages=[
                    "Layout compiled successfully with zmk-layout library",
                    f"Generated {len(keymap_content)} chars keymap content",
                    # f"Generated {len(config_content)} chars config content",
                ],
            )

            self.logger.info(
                "layout_compilation_successful",
                keymap_size=len(keymap_content),
                # config_size=len(config_content),
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

            # Use zmk-layout validation
            errors: list[str] = []
            try:
                layout = Layout.from_dict(json_data, providers=self.zmk_providers)
                layout.validate()  # This raises ValidationError if invalid
            except Exception as e:
                # Fallback to provider-based validation if zmk-layout validation fails
                validation_rules = self.providers.configuration.get_validation_rules()

                # Basic validation using rules
                if len(layout_data.layers) > validation_rules.get("layer_limit", 32):
                    errors.append(f"Too many layers: {len(layout_data.layers)}")

                key_count = validation_rules.get("key_count", 42)
                for i, layer in enumerate(layout_data.layers):
                    layer_bindings = (
                        getattr(layer, "bindings", layer)
                        if hasattr(layer, "bindings")
                        else layer
                    )
                    binding_count = (
                        len(layer_bindings)
                        if isinstance(layer_bindings, list | tuple)
                        else key_count
                    )
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

    def parse_keymap(
        self, keymap_content: str, profile: str | None = None
    ) -> LayoutResult:
        """Parse ZMK keymap file content to JSON using zmk-layout library.

        Args:
            keymap_content: Raw ZMK keymap file content
            profile: Optional keyboard profile for parsing context

        Returns:
            LayoutResult with parsed JSON content
        """
        try:
            self.logger.info(
                "parsing_keymap_with_zmk_library",
                content_length=len(keymap_content),
                keyboard_id=self.keyboard_id,
                profile=profile,
            )

            # Use zmk-layout Library's Layout.from_string() method to parse keymap
            layout = Layout.from_string(keymap_content, providers=self.zmk_providers)

            # Convert to JSON format
            json_data = layout.to_dict()

            # Create successful LayoutResult
            layout_result = LayoutResult(
                success=True,
                keymap_content=keymap_content,  # Original content
                config_content="",  # Parsing doesn't generate config
                json_content=json_data,
                errors=[],
                warnings=[],
                messages=[
                    "Keymap parsed successfully with zmk-layout library",
                    f"Parsed {len(keymap_content)} chars of keymap content",
                    f"Generated {len(json_data.get('layers', []))} layers",
                ],
            )

            self.logger.info(
                "keymap_parsing_successful",
                layers_count=len(json_data.get("layers", [])),
                keyboard=json_data.get("keyboard", "unknown"),
            )
            return layout_result

        except Exception as e:
            self.logger.error(
                "keymap_parsing_failed",
                error=str(e),
                keyboard_id=self.keyboard_id,
                content_length=len(keymap_content),
                exc_info=self.logger.isEnabledFor(logging.DEBUG),
            )

            # Return error result
            return LayoutResult(
                success=False,
                keymap_content=keymap_content,
                config_content="",
                json_content={},
                errors=[f"Parsing failed: {e}"],
                warnings=[],
                messages=[],
            )

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
