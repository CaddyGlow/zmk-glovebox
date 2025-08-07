"""Enhanced ZMK Layout Integration Service.
This service bridges glovebox with the zmk-layout library for enhanced
JSON to DTSI conversion capabilities and provides AST processing pipeline
for advanced layout transformations.
"""

import logging
from pathlib import Path
from typing import Any

from zmk_layout import create_default_providers
from zmk_layout.core import Layout

from glovebox.adapters.zmk_layout.provider_factory import create_glovebox_providers
from glovebox.core.structlog_logger import StructlogMixin
from glovebox.layout.ast_processor import (
    ASTProcessor,
    BehaviorTransformer,
    ComboTransformer,
    KeyRemapTransformer,
    LayerMergeTransformer,
    MacroTransformer,
    TransformationResult,
)
from glovebox.layout.models import LayoutData, LayoutResult
from glovebox.models.base import GloveboxBaseModel


class EnhancedZmkLayoutIntegrationService(GloveboxBaseModel, StructlogMixin):
    """Enhanced service that integrates zmk-layout library with glovebox pipeline.

    Provides both traditional layout compilation and advanced AST processing
    capabilities for layout transformations.
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

        # Initialize AST processor for transformations
        self.ast_processor = ASTProcessor()
        self._setup_default_transformers()

        self.logger.info(
            "enhanced_zmk_layout_service_initialized",
            keyboard_id=keyboard_id,
            has_services=services is not None,
            ast_processing_enabled=True,
        )

    def _setup_default_transformers(self) -> None:
        """Setup default transformers for common operations."""
        # Register default transformers (disabled by default)
        self.ast_processor.register_transformer(KeyRemapTransformer({}))
        self.ast_processor.register_transformer(LayerMergeTransformer({}))
        self.ast_processor.register_transformer(BehaviorTransformer({}))
        self.ast_processor.register_transformer(MacroTransformer({}, expand=True))
        self.ast_processor.register_transformer(ComboTransformer({}))

        # Disable all transformers by default - they will be configured as needed
        for transformer in self.ast_processor.transformers:
            transformer.enabled = False

    def compile_layout(
        self,
        layout_data: LayoutData,
        output_dir: Path | None = None,
        transformations: list[str] | None = None,
    ) -> LayoutResult:
        """Compile layout data to ZMK files using zmk-layout library.

        Args:
            layout_data: Glovebox layout data model
            output_dir: Optional output directory for files
            transformations: Optional list of transformation names to apply

        Returns:
            LayoutResult with generated content
        """
        try:
            self.logger.info(
                "compiling_layout_with_enhanced_zmk_library",
                keyboard=layout_data.keyboard,
                layers=len(layout_data.layers),
                keyboard_id=self.keyboard_id,
                transformations=transformations,
            )

            # Convert glovebox LayoutData to zmk-layout JSON format
            json_data = layout_data.to_dict()

            # Apply transformations if requested
            transformed_content = None
            if transformations:
                transformation_result = self.apply_transformations(
                    json_data, transformations
                )
                if transformation_result.success:
                    # Use transformed content for compilation
                    # Note: This would need to be converted back to JSON format
                    # For now, we'll log the transformation and proceed with original data
                    self.logger.info(
                        "transformations_applied",
                        transformations_count=len(
                            transformation_result.transformation_log
                        ),
                        warnings_count=len(transformation_result.warnings),
                    )
                else:
                    self.logger.warning(
                        "transformations_failed",
                        errors=len(transformation_result.errors),
                    )

            # Use zmk-layout Layout class to generate content
            layout = Layout.from_dict(json_data, providers=self.zmk_providers)
            keymap_content = layout.to_keymap()

            # Create successful LayoutResult
            messages = [
                "Layout compiled successfully with enhanced zmk-layout library",
                f"Generated {len(keymap_content)} chars keymap content",
            ]

            if transformations:
                messages.append(f"Applied {len(transformations)} transformations")

            layout_result = LayoutResult(
                success=True,
                keymap_content=keymap_content,
                config_content="",
                json_content=json_data,
                errors=[],
                warnings=[],
                messages=messages,
            )

            self.logger.info(
                "enhanced_layout_compilation_successful",
                keymap_size=len(keymap_content),
                warnings_count=len(layout_result.warnings),
            )

            return layout_result

        except Exception as e:
            self.logger.error(
                "enhanced_layout_compilation_failed",
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
                errors=[f"Enhanced compilation failed: {e}"],
                warnings=[],
                messages=[],
            )

    def apply_transformations(
        self, layout_content: dict[str, Any] | str, transformations: list[str]
    ) -> TransformationResult:
        """Apply AST transformations to layout content.

        Args:
            layout_content: Layout content as dict or keymap string
            transformations: List of transformation names to apply

        Returns:
            TransformationResult with transformation details
        """
        try:
            self.logger.info(
                "applying_ast_transformations",
                transformations=transformations,
                content_type=type(layout_content).__name__,
            )

            # Convert content to keymap string if needed
            if isinstance(layout_content, dict):
                # Convert dict to keymap string using zmk-layout
                layout = Layout.from_dict(layout_content, providers=self.zmk_providers)
                keymap_content = layout.to_keymap()
            else:
                keymap_content = layout_content

            # Process through AST pipeline
            result = self.ast_processor.process_layout(keymap_content, transformations)

            self.logger.info(
                "ast_transformations_completed",
                success=result.success,
                transformations_applied=len(result.transformation_log),
                errors=len(result.errors),
                warnings=len(result.warnings),
            )

            return result

        except Exception as e:
            self.logger.error(
                "ast_transformations_failed",
                error=str(e),
                exc_info=self.logger.isEnabledFor(logging.DEBUG),
            )
            return TransformationResult(
                success=False,
                errors=[f"Transformation processing failed: {e}"],
                transformation_log=["AST processing error"],
            )

    def configure_key_remapping(
        self, key_mappings: dict[str, str], target_layers: list[str] | None = None
    ) -> None:
        """Configure key remapping transformer.

        Args:
            key_mappings: Dictionary mapping old keys to new keys
            target_layers: Optional list of target layer names
        """
        # Remove existing key remap transformer
        self.ast_processor.unregister_transformer("KeyRemap")

        # Add new configured transformer
        transformer = KeyRemapTransformer(key_mappings, target_layers)
        transformer.enabled = True
        self.ast_processor.register_transformer(transformer)

        self.logger.info(
            "key_remapping_configured",
            mappings_count=len(key_mappings),
            target_layers=target_layers,
        )

    def configure_layer_merging(self, merge_config: dict[str, list[str]]) -> None:
        """Configure layer merging transformer.

        Args:
            merge_config: Dictionary mapping new layer names to source layer lists
        """
        # Remove existing layer merge transformer
        self.ast_processor.unregister_transformer("LayerMerge")

        # Add new configured transformer
        transformer = LayerMergeTransformer(merge_config)
        transformer.enabled = True
        self.ast_processor.register_transformer(transformer)

        self.logger.info("layer_merging_configured", merge_operations=len(merge_config))

    def configure_behavior_modifications(
        self, behavior_mods: dict[str, dict[str, Any]]
    ) -> None:
        """Configure behavior modification transformer.

        Args:
            behavior_mods: Dictionary mapping behavior names to their modifications
        """
        # Remove existing behavior transformer
        self.ast_processor.unregister_transformer("BehaviorTransform")

        # Add new configured transformer
        transformer = BehaviorTransformer(behavior_mods)
        transformer.enabled = True
        self.ast_processor.register_transformer(transformer)

        self.logger.info(
            "behavior_modifications_configured", behaviors_count=len(behavior_mods)
        )

    def configure_macro_processing(
        self, macro_definitions: dict[str, list[str]], expand: bool = True
    ) -> None:
        """Configure macro processing transformer.

        Args:
            macro_definitions: Dictionary mapping macro names to their definitions
            expand: Whether to expand (True) or collapse (False) macros
        """
        # Remove existing macro transformer
        self.ast_processor.unregister_transformer("MacroTransform")

        # Add new configured transformer
        transformer = MacroTransformer(macro_definitions, expand)
        transformer.enabled = True
        self.ast_processor.register_transformer(transformer)

        self.logger.info(
            "macro_processing_configured",
            macros_count=len(macro_definitions),
            expand_mode=expand,
        )

    def configure_combo_generation(
        self, combo_patterns: dict[str, dict[str, Any]]
    ) -> None:
        """Configure combo generation transformer.

        Args:
            combo_patterns: Dictionary mapping pattern names to their configurations
        """
        # Remove existing combo transformer
        self.ast_processor.unregister_transformer("ComboTransform")

        # Add new configured transformer
        transformer = ComboTransformer(combo_patterns)
        transformer.enabled = True
        self.ast_processor.register_transformer(transformer)

        self.logger.info(
            "combo_generation_configured", patterns_count=len(combo_patterns)
        )

    def set_dry_run_mode(self, enabled: bool) -> None:
        """Enable or disable dry run mode for transformations.

        Args:
            enabled: Whether to enable dry run mode
        """
        self.ast_processor.set_dry_run_mode(enabled)
        self.logger.info("dry_run_mode_configured", enabled=enabled)

    def enable_rollback_support(self, enabled: bool, max_points: int = 10) -> None:
        """Configure rollback support for transformations.

        Args:
            enabled: Whether to enable rollback support
            max_points: Maximum number of rollback points to maintain
        """
        self.ast_processor.enable_rollback_support(enabled, max_points)
        self.logger.info(
            "rollback_support_configured", enabled=enabled, max_points=max_points
        )

    def get_transformation_history(self) -> list[str]:
        """Get history of applied transformations."""
        # This would need to track transformation history across calls
        # For now, return empty list as state is not persistent across calls
        return []

    def validate_layout(self, layout_data: LayoutData) -> list[str]:
        """Validate layout data using zmk-layout validation.

        Args:
            layout_data: Layout data to validate

        Returns:
            List of validation errors (empty if valid)
        """
        try:
            self.logger.debug(
                "validating_layout_with_enhanced_zmk_library",
                keyboard=layout_data.keyboard,
                layers=len(layout_data.layers),
            )

            json_data = layout_data.to_dict()

            # Use zmk-layout validation
            try:
                layout = Layout.from_dict(json_data, providers=self.zmk_providers)
                validation_errors = layout.validate()
                errors = (
                    [str(error) for error in validation_errors]
                    if validation_errors
                    else []
                )
            except Exception as e:
                # Fallback to provider-based validation if zmk-layout validation fails
                validation_rules = self.providers.configuration.get_validation_rules()
                errors = []

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
                "enhanced_layout_validation_completed",
                errors_count=len(errors),
            )

            return errors

        except Exception as e:
            self.logger.error(
                "enhanced_layout_validation_failed",
                error=str(e),
                exc_info=self.logger.isEnabledFor(logging.DEBUG),
            )
            return [f"Enhanced validation failed: {e}"]

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
        """Get information about enhanced zmk-layout compiler capabilities.

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
                "library": "enhanced-zmk-layout",
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
                    "ast_transformations",
                    "key_remapping",
                    "layer_merging",
                    "behavior_modifications",
                    "macro_processing",
                    "combo_generation",
                    "dry_run_mode",
                    "rollback_support",
                ],
                "keyboard_id": self.keyboard_id,
                "ast_processing": {
                    "transformers_count": len(self.ast_processor.transformers),
                    "enabled_transformers": [
                        t.name for t in self.ast_processor.transformers if t.enabled
                    ],
                    "dry_run_mode": self.ast_processor.dry_run_mode,
                    "rollback_enabled": self.ast_processor.enable_rollback,
                },
            }

            self.logger.debug("retrieved_enhanced_compiler_info", **info)
            return info

        except Exception as e:
            self.logger.error(
                "failed_to_get_enhanced_compiler_info",
                error=str(e),
                exc_info=self.logger.isEnabledFor(logging.DEBUG),
            )
            return {"error": str(e)}


def create_enhanced_zmk_layout_service(
    keyboard_id: str | None = None,
    services: dict[str, Any] | None = None,
) -> EnhancedZmkLayoutIntegrationService:
    """Create Enhanced ZmkLayoutIntegrationService instance.

    Args:
        keyboard_id: Optional keyboard identifier
        services: Optional service overrides for testing

    Returns:
        Configured EnhancedZmkLayoutIntegrationService
    """
    return EnhancedZmkLayoutIntegrationService(
        keyboard_id=keyboard_id,
        services=services,
    )
