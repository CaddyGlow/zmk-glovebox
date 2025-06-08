"""Layout domain for keyboard layout processing.

This package contains all layout-related functionality including:
- Layout models and data structures
- Layout service for processing operations
- Component service for layer extraction/merging
- Display service for layout visualization
- Generator for layout formatting
"""


# Lazy imports to avoid circular dependencies
def create_layout_service(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Create a layout service instance."""
    from glovebox.layout.service import create_layout_service as _create_layout_service

    return _create_layout_service(*args, **kwargs)


def create_layout_component_service(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Create a layout component service instance."""
    from glovebox.layout.component_service import (
        create_layout_component_service as _create_layout_component_service,
    )

    return _create_layout_component_service(*args, **kwargs)


def create_layout_display_service(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Create a layout display service instance."""
    from glovebox.layout.display_service import (
        create_layout_display_service as _create_layout_display_service,
    )

    return _create_layout_display_service(*args, **kwargs)


def create_layout_generator(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Create a layout generator instance (backward compatibility)."""
    from glovebox.layout.generator import (
        create_layout_generator as _create_layout_generator,
    )

    return _create_layout_generator(*args, **kwargs)


def create_grid_layout_formatter(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Create a grid layout formatter instance."""
    from glovebox.layout.formatting import (
        create_grid_layout_formatter as _create_grid_layout_formatter,
    )

    return _create_grid_layout_formatter(*args, **kwargs)


def create_zmk_file_generator(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Create a ZMK file content generator instance."""
    from glovebox.layout.zmk_generator import (
        create_zmk_file_generator as _create_zmk_file_generator,
    )

    return _create_zmk_file_generator(*args, **kwargs)


def create_kconfig_generator(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Create a Kconfig generator instance."""
    from glovebox.layout.kconfig_generator import (
        create_kconfig_generator as _create_kconfig_generator,
    )

    return _create_kconfig_generator(*args, **kwargs)


__all__ = [
    # Factory functions
    "create_layout_service",
    "create_layout_component_service",
    "create_layout_display_service",
    # New factory functions
    "create_grid_layout_formatter",
    "create_zmk_file_generator",
    "create_kconfig_generator",
    # Backward compatibility
    "create_layout_generator",
]
