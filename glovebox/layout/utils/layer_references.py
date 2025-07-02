"""Utilities for tracking and updating layer references in keyboard bindings."""

import logging
from collections.abc import Mapping
from typing import Any

from glovebox.layout.models import LayoutBinding, LayoutData, LayoutParam


logger = logging.getLogger(__name__)

# ZMK behaviors that reference layer indices
LAYER_REFERENCING_BEHAVIORS = frozenset(["&lt", "&mo", "&to", "&tog"])


class LayerReference:
    """Represents a reference to a layer index in a binding."""

    def __init__(
        self,
        layer_index: int,
        binding_index: int,
        layer_id: int,
        behavior: str,
        full_binding: LayoutBinding,
    ):
        """Initialize a layer reference.

        Args:
            layer_index: The layer containing this binding
            binding_index: The index of the binding within the layer
            layer_id: The referenced layer ID
            behavior: The behavior type (e.g., "&mo", "&lt")
            full_binding: The complete LayoutBinding object
        """
        self.layer_index = layer_index
        self.binding_index = binding_index
        self.layer_id = layer_id
        self.behavior = behavior
        self.full_binding = full_binding

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"LayerReference(layer={self.layer_index}, "
            f"binding={self.binding_index}, references={self.layer_id}, "
            f"behavior={self.behavior})"
        )


def find_layer_references(layout_data: LayoutData) -> list[LayerReference]:
    """Find all bindings that reference layer indices.

    Args:
        layout_data: The layout data to scan

    Returns:
        List of LayerReference objects describing all layer references
    """
    references = []

    for layer_idx, layer_bindings in enumerate(layout_data.layers):
        for binding_idx, binding in enumerate(layer_bindings):
            if binding.value in LAYER_REFERENCING_BEHAVIORS:
                # Extract the layer ID from the binding parameters
                layer_id = _extract_layer_id(binding)
                if layer_id is not None:
                    references.append(
                        LayerReference(
                            layer_index=layer_idx,
                            binding_index=binding_idx,
                            layer_id=layer_id,
                            behavior=binding.value,
                            full_binding=binding,
                        )
                    )

    return references


def _extract_layer_id(binding: LayoutBinding) -> int | None:
    """Extract the layer ID from a binding's parameters.

    Args:
        binding: The binding to extract from

    Returns:
        The layer ID if found and valid, None otherwise
    """
    if not binding.params:
        return None

    # For &lt (layer-tap), the layer is the first parameter
    # For &mo, &to, &tog, the layer is the only parameter
    if binding.value == "&lt" and len(binding.params) >= 1:
        # Layer-tap has layer as first param, key as second
        param = binding.params[0]
    elif binding.value in ("&mo", "&to", "&tog") and len(binding.params) == 1:
        # These behaviors have layer as the only parameter
        param = binding.params[0]
    else:
        return None

    # Extract integer value from the parameter
    if isinstance(param.value, int):
        return param.value
    elif isinstance(param.value, str) and param.value.isdigit():
        return int(param.value)

    return None


def update_layer_references(
    layout_data: LayoutData, layer_mapping: Mapping[int, int | None]
) -> tuple[LayoutData, list[str]]:
    """Update all layer references based on a mapping.

    Args:
        layout_data: The layout data to update
        layer_mapping: Mapping from old layer indices to new indices
                      (None means the layer was removed)

    Returns:
        Tuple of (updated layout data, list of warnings)
    """
    warnings = []
    references = find_layer_references(layout_data)

    for ref in references:
        new_layer_id = layer_mapping.get(ref.layer_id)

        if new_layer_id is None:
            # Layer was removed - add warning
            layer_name = (
                layout_data.layer_names[ref.layer_index]
                if ref.layer_index < len(layout_data.layer_names)
                else f"Layer {ref.layer_index}"
            )
            warnings.append(
                f"Warning: {ref.behavior} in layer '{layer_name}' references "
                f"removed layer {ref.layer_id}"
            )
            # Optionally, we could change it to &none or &trans
            # For now, we'll leave it as-is and let the user handle it
        elif new_layer_id != ref.layer_id:
            # Update the reference to the new layer ID
            _update_binding_layer_id(
                layout_data.layers[ref.layer_index][ref.binding_index], new_layer_id
            )
            logger.debug(
                "Updated %s reference from layer %d to %d",
                ref.behavior,
                ref.layer_id,
                new_layer_id,
            )

    return layout_data, warnings


def _update_binding_layer_id(binding: LayoutBinding, new_layer_id: int) -> None:
    """Update the layer ID in a binding's parameters.

    Args:
        binding: The binding to update (modified in place)
        new_layer_id: The new layer ID to set
    """
    if not binding.params:
        return

    # Update the appropriate parameter based on behavior type
    if binding.value == "&lt" and len(binding.params) >= 1:
        # Layer-tap: update first parameter
        binding.params[0].value = new_layer_id
    elif binding.value in ("&mo", "&to", "&tog") and len(binding.params) == 1:
        # Other layer behaviors: update only parameter
        binding.params[0].value = new_layer_id


def create_layer_mapping_for_add(original_count: int, position: int) -> dict[int, int]:
    """Create a layer mapping for adding a layer at a position.

    Args:
        original_count: Number of layers before addition
        position: Position where layer is being added

    Returns:
        Mapping from old indices to new indices
    """
    mapping = {}
    for i in range(original_count):
        if i >= position:
            # Layers at or after insertion point shift up
            mapping[i] = i + 1
        else:
            # Layers before insertion point stay the same
            mapping[i] = i
    return mapping


def create_layer_mapping_for_remove(
    original_count: int, removed_indices: list[int]
) -> dict[int, int | None]:
    """Create a layer mapping for removing layers.

    Args:
        original_count: Number of layers before removal
        removed_indices: List of indices being removed (must be sorted)

    Returns:
        Mapping from old indices to new indices (None for removed)
    """
    mapping: dict[int, int | None] = {}
    removed_set = set(removed_indices)
    shift = 0

    for i in range(original_count):
        if i in removed_set:
            mapping[i] = None
            shift += 1
        else:
            mapping[i] = i - shift

    return mapping


def create_layer_mapping_for_move(
    original_count: int, from_index: int, to_index: int
) -> dict[int, int]:
    """Create a layer mapping for moving a layer.

    Args:
        original_count: Number of layers
        from_index: Original position
        to_index: Target position

    Returns:
        Mapping from old indices to new indices
    """
    mapping = {}

    for i in range(original_count):
        if i == from_index:
            # The moved layer goes to the target position
            mapping[i] = to_index
        elif from_index < to_index:
            # Moving down: layers in between shift up
            if from_index < i <= to_index:
                mapping[i] = i - 1
            else:
                mapping[i] = i
        else:
            # Moving up: layers in between shift down
            if to_index <= i < from_index:
                mapping[i] = i + 1
            else:
                mapping[i] = i

    return mapping
