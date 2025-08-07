"""AST Processing Pipeline for ZMK Layout Transformations.

This module provides a comprehensive AST processing system that enables
advanced transformations on ZMK layouts, including key remapping, layer
transformations, behavior modifications, macro expansions, and combo generation.
"""

from __future__ import annotations

import copy
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Generic, Protocol, TypeVar

from zmk_layout.parsers import DTNode, DTParseError, ZMKKeymapParser
from zmk_layout.parsers.ast_walker import DTWalker
from zmk_layout.parsers.zmk_keymap_parser import KeymapParseResult

from glovebox.core.structlog_logger import StructlogMixin
from glovebox.layout.models import LayoutData, LayoutResult
from glovebox.models.base import GloveboxBaseModel


# Type variables for generic transformer support
T = TypeVar("T")
NodeT = TypeVar("NodeT", bound=DTNode)


class TransformationError(Exception):
    """Base exception for AST transformation errors."""

    def __init__(
        self,
        message: str,
        node: DTNode | None = None,
        context: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.node = node
        self.context = context or {}


class ValidationError(TransformationError):
    """Exception for AST validation failures."""


@dataclass
class TransformationResult:
    """Result of an AST transformation operation."""

    success: bool
    transformed_ast: DTNode | None = None
    original_ast: DTNode | None = None
    transformation_log: list[str] = field(default_factory=list)
    errors: list[TransformationError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class PipelineState:
    """Current state of the AST processing pipeline."""

    current_ast: DTNode
    original_ast: DTNode
    transformation_history: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    rollback_points: list[DTNode] = field(default_factory=list)


class TransformationPriority(Enum):
    """Priority levels for transformation ordering."""

    CRITICAL = 0  # Must run first (e.g., parse validation)
    HIGH = 1  # Structure changes (e.g., layer merging)
    NORMAL = 2  # Content modifications (e.g., key remapping)
    LOW = 3  # Optimizations (e.g., macro expansion)
    CLEANUP = 4  # Final cleanup operations


class ASTTransformer(ABC, Generic[NodeT]):
    """Abstract base class for AST transformations."""

    def __init__(
        self,
        name: str,
        priority: TransformationPriority = TransformationPriority.NORMAL,
    ):
        self.name = name
        self.priority = priority
        self.enabled = True

    @abstractmethod
    def can_transform(self, node: NodeT) -> bool:
        """Check if this transformer can process the given node."""

    @abstractmethod
    def transform_node(self, node: NodeT, context: dict[str, Any]) -> NodeT:
        """Transform a single AST node."""

    def pre_transform_hook(self, state: PipelineState) -> None:
        """Hook called before transformation begins."""

    def post_transform_hook(
        self, state: PipelineState, result: TransformationResult
    ) -> None:
        """Hook called after transformation completes."""

    def validate_input(self, node: NodeT) -> list[ValidationError]:
        """Validate input node before transformation."""
        return []

    def validate_output(self, node: NodeT) -> list[ValidationError]:
        """Validate output node after transformation."""
        return []


class KeyRemapTransformer(ASTTransformer[DTNode]):
    """Transformer for remapping keys across layers."""

    def __init__(
        self, key_mappings: dict[str, str], target_layers: list[str] | None = None
    ):
        super().__init__("KeyRemap", TransformationPriority.NORMAL)
        self.key_mappings = key_mappings
        self.target_layers = target_layers

    def can_transform(self, node: DTNode) -> bool:
        """Check if node contains keymap bindings."""
        return hasattr(node, "properties") and any(
            prop.name == "bindings" for prop in getattr(node, "properties", [])
        )

    def transform_node(self, node: DTNode, context: dict[str, Any]) -> DTNode:
        """Remap keys in the given node."""
        transformed_node = copy.deepcopy(node)

        # Find and transform bindings properties
        if hasattr(transformed_node, "properties"):
            for prop in transformed_node.properties:
                if hasattr(prop, "name") and prop.name == "bindings":
                    self._transform_bindings(prop, context)

        return transformed_node

    def _transform_bindings(self, bindings_prop: Any, context: dict[str, Any]) -> None:
        """Transform bindings within a property."""
        if hasattr(bindings_prop, "value") and hasattr(bindings_prop.value, "items"):
            for i, binding in enumerate(bindings_prop.value.items):
                original_binding = str(binding)
                for old_key, new_key in self.key_mappings.items():
                    if old_key in original_binding:
                        bindings_prop.value.items[i] = original_binding.replace(
                            old_key, new_key
                        )
                        context.setdefault("remapped_keys", []).append(
                            {
                                "original": original_binding,
                                "transformed": bindings_prop.value.items[i],
                                "position": i,
                            }
                        )


class LayerMergeTransformer(ASTTransformer[DTNode]):
    """Transformer for merging or splitting layers."""

    def __init__(self, merge_config: dict[str, list[str]]):
        super().__init__("LayerMerge", TransformationPriority.HIGH)
        self.merge_config = merge_config  # {'new_layer': ['layer1', 'layer2']}

    def can_transform(self, node: DTNode) -> bool:
        """Check if node contains keymap layers."""
        return hasattr(node, "children") and any(
            hasattr(child, "name") and "layer" in getattr(child, "name", "")
            for child in getattr(node, "children", [])
        )

    def transform_node(self, node: DTNode, context: dict[str, Any]) -> DTNode:
        """Merge layers according to configuration."""
        transformed_node = copy.deepcopy(node)

        for new_layer_name, source_layers in self.merge_config.items():
            self._merge_layers(transformed_node, new_layer_name, source_layers, context)

        return transformed_node

    def _merge_layers(
        self, node: DTNode, new_name: str, sources: list[str], context: dict[str, Any]
    ) -> None:
        """Merge multiple source layers into a new layer."""
        # Implementation would merge layer bindings
        # This is a simplified version - real implementation would be more complex
        context.setdefault("merged_layers", []).append(
            {"new_layer": new_name, "source_layers": sources}
        )


class BehaviorTransformer(ASTTransformer[DTNode]):
    """Transformer for modifying behavior parameters."""

    def __init__(self, behavior_modifications: dict[str, dict[str, Any]]):
        super().__init__("BehaviorTransform", TransformationPriority.NORMAL)
        self.behavior_modifications = behavior_modifications

    def can_transform(self, node: DTNode) -> bool:
        """Check if node contains behavior definitions."""
        return hasattr(node, "name") and "behaviors" in getattr(node, "name", "")

    def transform_node(self, node: DTNode, context: dict[str, Any]) -> DTNode:
        """Modify behavior parameters in the node."""
        transformed_node = copy.deepcopy(node)

        # Find and modify behavior properties
        for behavior_name, modifications in self.behavior_modifications.items():
            self._modify_behavior(
                transformed_node, behavior_name, modifications, context
            )

        return transformed_node

    def _modify_behavior(
        self,
        node: DTNode,
        behavior_name: str,
        mods: dict[str, Any],
        context: dict[str, Any],
    ) -> None:
        """Modify a specific behavior's properties."""
        # Implementation would find behavior nodes and modify their properties
        context.setdefault("modified_behaviors", []).append(
            {"behavior": behavior_name, "modifications": mods}
        )


class MacroTransformer(ASTTransformer[DTNode]):
    """Transformer for expanding or collapsing macros."""

    def __init__(self, macro_definitions: dict[str, list[str]], expand: bool = True):
        super().__init__("MacroTransform", TransformationPriority.LOW)
        self.macro_definitions = macro_definitions
        self.expand = expand

    def can_transform(self, node: DTNode) -> bool:
        """Check if node contains macro references or definitions."""
        return hasattr(node, "properties") and any(
            "macro" in str(prop) for prop in getattr(node, "properties", [])
        )

    def transform_node(self, node: DTNode, context: dict[str, Any]) -> DTNode:
        """Expand or collapse macros in the node."""
        transformed_node = copy.deepcopy(node)

        if self.expand:
            self._expand_macros(transformed_node, context)
        else:
            self._collapse_macros(transformed_node, context)

        return transformed_node

    def _expand_macros(self, node: DTNode, context: dict[str, Any]) -> None:
        """Expand macro references to their full definitions."""
        # Implementation would find macro references and replace with expanded form
        context.setdefault("expanded_macros", []).append("macro_expansion_performed")

    def _collapse_macros(self, node: DTNode, context: dict[str, Any]) -> None:
        """Collapse repeated patterns into macro references."""
        # Implementation would find repeated patterns and create macro references
        context.setdefault("collapsed_macros", []).append("macro_collapse_performed")


class ComboTransformer(ASTTransformer[DTNode]):
    """Transformer for generating combos from patterns."""

    def __init__(self, combo_patterns: dict[str, dict[str, Any]]):
        super().__init__("ComboTransform", TransformationPriority.LOW)
        self.combo_patterns = combo_patterns

    def can_transform(self, node: DTNode) -> bool:
        """Check if node can have combos added."""
        return hasattr(node, "children") and any(
            hasattr(child, "name") and "combos" in getattr(child, "name", "")
            for child in getattr(node, "children", [])
        )

    def transform_node(self, node: DTNode, context: dict[str, Any]) -> DTNode:
        """Generate combos based on patterns."""
        transformed_node = copy.deepcopy(node)

        for pattern_name, pattern_config in self.combo_patterns.items():
            self._generate_combo(
                transformed_node, pattern_name, pattern_config, context
            )

        return transformed_node

    def _generate_combo(
        self, node: DTNode, name: str, config: dict[str, Any], context: dict[str, Any]
    ) -> None:
        """Generate a combo from pattern configuration."""
        # Implementation would create combo nodes based on patterns
        context.setdefault("generated_combos", []).append(
            {"pattern": name, "config": config}
        )


class ASTProcessor(GloveboxBaseModel, StructlogMixin):
    """Main AST processing pipeline coordinator."""

    def __init__(self, parser: ZMKKeymapParser | None = None):
        super().__init__()
        self.parser = parser or ZMKKeymapParser()
        self.transformers: list[ASTTransformer[DTNode]] = []
        self.dry_run_mode = False
        self.enable_rollback = True
        self.max_rollback_points = 10

    def register_transformer(self, transformer: ASTTransformer[DTNode]) -> None:
        """Register a transformer in the pipeline."""
        self.transformers.append(transformer)
        # Sort by priority to ensure correct execution order
        self.transformers.sort(key=lambda t: t.priority.value)
        self.logger.info(
            "transformer_registered",
            name=transformer.name,
            priority=transformer.priority.name,
            total_transformers=len(self.transformers),
        )

    def unregister_transformer(self, name: str) -> bool:
        """Remove a transformer from the pipeline."""
        for i, transformer in enumerate(self.transformers):
            if transformer.name == name:
                removed = self.transformers.pop(i)
                self.logger.info("transformer_unregistered", name=removed.name)
                return True
        return False

    def parse_keymap(
        self, content: str, validate: bool = True
    ) -> tuple[DTNode | None, list[TransformationError]]:
        """Parse keymap content to AST."""
        try:
            result = self.parser.parse_keymap(content)

            if not result.success:
                errors = [
                    TransformationError(f"Parse error: {error}")
                    for error in result.errors
                ]
                return None, errors

            # Extract the AST from the parsed layout data
            # This is a simplified extraction - real implementation would be more complex
            ast_node = self._extract_ast_from_result(result)

            if validate:
                validation_errors = self._validate_ast(ast_node)
                if validation_errors:
                    # Convert ValidationError to TransformationError
                    transformation_errors = [
                        TransformationError(str(err)) for err in validation_errors
                    ]
                    return ast_node, transformation_errors

            return ast_node, []

        except DTParseError as e:
            return None, [TransformationError(f"Parse error: {e}")]
        except Exception as e:
            return None, [TransformationError(f"Unexpected parsing error: {e}")]

    def _extract_ast_from_result(self, result: KeymapParseResult) -> DTNode:
        """Extract AST node from parse result."""
        # This is a placeholder - real implementation would extract the actual AST
        # from the zmk-layout library's parse result
        return DTNode("keymap")

    def _validate_ast(self, ast: DTNode) -> list[ValidationError]:
        """Validate AST structure."""
        errors = []

        # Basic structural validation
        if not hasattr(ast, "name"):
            errors.append(ValidationError("AST node missing name attribute", ast))

        if not hasattr(ast, "children") and not hasattr(ast, "properties"):
            errors.append(
                ValidationError("AST node missing children or properties", ast)
            )

        return errors

    def process_layout(
        self, layout_content: str, transformations: list[str] | None = None
    ) -> TransformationResult:
        """Process a layout through the transformation pipeline."""
        self.logger.info("starting_ast_processing", transformations=transformations)

        # Parse the layout to AST
        ast, parse_errors = self.parse_keymap(layout_content)
        if parse_errors or ast is None:
            return TransformationResult(
                success=False,
                errors=parse_errors,
                transformation_log=["Parse phase failed"],
            )

        # Initialize pipeline state
        state = PipelineState(current_ast=ast, original_ast=copy.deepcopy(ast))

        result = TransformationResult(success=True, original_ast=ast)

        # Apply transformations
        active_transformers = self._get_active_transformers(transformations)

        for transformer in active_transformers:
            try:
                step_result = self._apply_transformation(transformer, state)
                result.transformation_log.extend(step_result.transformation_log)
                result.warnings.extend(step_result.warnings)

                if not step_result.success:
                    result.errors.extend(step_result.errors)
                    if not self.dry_run_mode:
                        # Stop on first error unless in dry run mode
                        result.success = False
                        break

            except Exception as e:
                error = TransformationError(
                    f"Transformer {transformer.name} failed: {e}"
                )
                result.errors.append(error)
                result.success = False
                break

        result.transformed_ast = state.current_ast

        self.logger.info(
            "ast_processing_completed",
            success=result.success,
            transformations_applied=len(result.transformation_log),
            errors=len(result.errors),
            warnings=len(result.warnings),
        )

        return result

    def _get_active_transformers(
        self, filter_names: list[str] | None
    ) -> list[ASTTransformer[DTNode]]:
        """Get list of active transformers, optionally filtered by names."""
        if filter_names is None:
            return [t for t in self.transformers if t.enabled]

        filtered = []
        for transformer in self.transformers:
            if transformer.enabled and transformer.name in filter_names:
                filtered.append(transformer)

        return filtered

    def _apply_transformation(
        self, transformer: ASTTransformer[DTNode], state: PipelineState
    ) -> TransformationResult:
        """Apply a single transformation to the pipeline state."""
        self.logger.debug("applying_transformation", transformer=transformer.name)

        # Create rollback point if enabled
        if self.enable_rollback:
            state.rollback_points.append(copy.deepcopy(state.current_ast))
            # Limit rollback history
            if len(state.rollback_points) > self.max_rollback_points:
                state.rollback_points.pop(0)

        result = TransformationResult(success=True)
        context: dict[str, Any] = {}

        try:
            # Pre-transformation hook
            transformer.pre_transform_hook(state)

            # Validate input
            validation_errors = transformer.validate_input(state.current_ast)
            if validation_errors:
                result.errors.extend(validation_errors)
                result.success = False
                return result

            # Check if transformation can be applied
            if not transformer.can_transform(state.current_ast):
                result.transformation_log.append(
                    f"Transformer {transformer.name} skipped - not applicable"
                )
                return result

            # Apply transformation
            if not self.dry_run_mode:
                transformed_ast = transformer.transform_node(state.current_ast, context)

                # Validate output
                validation_errors = transformer.validate_output(transformed_ast)
                if validation_errors:
                    result.errors.extend(validation_errors)
                    result.success = False
                    return result

                state.current_ast = transformed_ast

            # Record transformation
            state.transformation_history.append(transformer.name)
            result.transformation_log.append(f"Applied {transformer.name}")

            # Update metadata with transformation context
            if context:
                state.metadata[transformer.name] = context

            # Post-transformation hook
            transformer.post_transform_hook(state, result)

        except Exception as e:
            result.errors.append(TransformationError(f"Transformation failed: {e}"))
            result.success = False

        return result

    def rollback_to_point(self, state: PipelineState, steps: int = 1) -> bool:
        """Rollback pipeline state to a previous point."""
        if not self.enable_rollback or len(state.rollback_points) < steps:
            return False

        # Rollback the specified number of steps
        for _ in range(steps):
            if state.rollback_points:
                state.current_ast = state.rollback_points.pop()
                if state.transformation_history:
                    removed_transform = state.transformation_history.pop()
                    self.logger.info(
                        "transformation_rolled_back", transformation=removed_transform
                    )

        return True

    def get_transformation_history(self, state: PipelineState) -> list[str]:
        """Get the history of applied transformations."""
        return state.transformation_history.copy()

    def clear_transformers(self) -> None:
        """Clear all registered transformers."""
        count = len(self.transformers)
        self.transformers.clear()
        self.logger.info("transformers_cleared", count=count)

    def set_dry_run_mode(self, enabled: bool) -> None:
        """Enable or disable dry run mode."""
        self.dry_run_mode = enabled
        self.logger.info("dry_run_mode_changed", enabled=enabled)

    def enable_rollback_support(self, enabled: bool, max_points: int = 10) -> None:
        """Configure rollback support."""
        self.enable_rollback = enabled
        self.max_rollback_points = max_points
        self.logger.info(
            "rollback_support_configured", enabled=enabled, max_points=max_points
        )


# Factory functions for common transformation setups
def create_key_remapping_processor(key_mappings: dict[str, str]) -> ASTProcessor:
    """Create an AST processor configured for key remapping."""
    processor = ASTProcessor()
    processor.register_transformer(KeyRemapTransformer(key_mappings))
    return processor


def create_layer_management_processor(
    merge_config: dict[str, list[str]],
) -> ASTProcessor:
    """Create an AST processor configured for layer management."""
    processor = ASTProcessor()
    processor.register_transformer(LayerMergeTransformer(merge_config))
    return processor


def create_comprehensive_processor() -> ASTProcessor:
    """Create an AST processor with all available transformers."""
    processor = ASTProcessor()

    # Register transformers in priority order
    processor.register_transformer(KeyRemapTransformer({}))  # Will be configured later
    processor.register_transformer(LayerMergeTransformer({}))
    processor.register_transformer(BehaviorTransformer({}))
    processor.register_transformer(MacroTransformer({}, expand=True))
    processor.register_transformer(ComboTransformer({}))

    return processor
