"""Layout domain for keyboard layout processing.

This package contains all layout-related functionality including:
- Layout models and data structures
- Layout service for processing operations
- Component service for layer extraction/merging
"""


# Lazy imports to avoid circular dependencies
def create_layout_service(*args, **kwargs):
    """Create a layout service instance."""
    from glovebox.layout.service import create_layout_service as _create_layout_service

    return _create_layout_service(*args, **kwargs)


def create_layout_component_service(*args, **kwargs):
    """Create a layout component service instance."""
    from glovebox.layout.component_service import (
        create_layout_component_service as _create_layout_component_service,
    )

    return _create_layout_component_service(*args, **kwargs)


__all__ = [
    # Factory functions
    "create_layout_service",
    "create_layout_component_service",
]
