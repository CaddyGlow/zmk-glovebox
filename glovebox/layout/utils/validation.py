"""Validation utilities for layout operations."""

from pathlib import Path

from glovebox.layout.models import LayoutData


def validate_layer_exists(layout_data: LayoutData, layer_name: str) -> int:
    """Validate that a layer exists and return its index.

    Args:
        layout_data: Layout data to check
        layer_name: Name of layer to validate

    Returns:
        Index of the layer

    Raises:
        ValueError: If layer is not found
    """
    if layer_name not in layout_data.layer_names:
        available_layers = ", ".join(layout_data.layer_names)
        raise ValueError(
            f"Layer '{layer_name}' not found. Available layers: {available_layers}"
        )

    return layout_data.layer_names.index(layer_name)


def validate_layer_has_bindings(
    layout_data: LayoutData, layer_name: str, layer_idx: int
) -> None:
    """Validate that a layer has binding data.

    Args:
        layout_data: Layout data to check
        layer_name: Name of layer for error messages
        layer_idx: Index of layer to check

    Raises:
        ValueError: If layer has no binding data
    """
    if layer_idx >= len(layout_data.layers):
        raise ValueError(f"Layer '{layer_name}' has no binding data")


def validate_output_path(
    output_path: Path, source_path: Path | None = None, force: bool = False
) -> None:
    """Validate output file path and check for overwrites.

    Args:
        output_path: Path where file will be written
        source_path: Original file path (if overwriting is allowed)
        force: Whether to allow overwriting existing files

    Raises:
        ValueError: If output file exists and overwrite not allowed
    """
    if output_path.exists() and output_path != source_path and not force:
        raise ValueError(
            f"Output file already exists: {output_path}. Use --force to overwrite."
        )


def validate_position_index(
    position: int | None, total_items: int, allow_append: bool = True
) -> int:
    """Validate and normalize a position index.

    Args:
        position: Position index (can be negative or None)
        total_items: Total number of items in collection
        allow_append: Whether to allow appending at end if position is None

    Returns:
        Normalized position index

    Raises:
        ValueError: If position is invalid
    """
    if position is None:
        if allow_append:
            return total_items
        else:
            raise ValueError("Position must be specified")

    # Handle negative indices
    if position < 0:
        normalized = max(0, total_items + position + 1)
    else:
        normalized = min(position, total_items)

    return normalized


def validate_layer_name_unique(layout_data: LayoutData, layer_name: str) -> None:
    """Validate that a layer name is unique.

    Args:
        layout_data: Layout data to check
        layer_name: Proposed layer name

    Raises:
        ValueError: If layer name already exists
    """
    if layer_name in layout_data.layer_names:
        raise ValueError(f"Layer '{layer_name}' already exists")
