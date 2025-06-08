"""DTSI layout generation service - transitional compatibility layer.

This module provides backward compatibility imports while the codebase
migrates to the new split structure.
"""

# Re-export from new modules for backward compatibility
from glovebox.layout.formatting import (
    GridLayoutFormatter,
    LayoutConfig,
    LayoutMetadata,
    ViewMode,
    create_grid_layout_formatter,
)
from glovebox.layout.kconfig_generator import (
    KConfigGenerator,
    KConfigSettings,
    create_kconfig_generator,
)
from glovebox.layout.zmk_generator import (
    ZmkFileContentGenerator,
    create_zmk_file_generator,
)


# Backward compatibility aliases
DtsiLayoutGenerator = GridLayoutFormatter
DTSIGenerator = ZmkFileContentGenerator


def create_layout_generator() -> GridLayoutFormatter:
    """Create a GridLayoutFormatter instance for backward compatibility.

    Note: This factory function name is misleading and will be deprecated.
    Use create_grid_layout_formatter() instead.

    Returns:
        GridLayoutFormatter instance
    """
    return create_grid_layout_formatter()


__all__ = [
    # New names (preferred)
    "GridLayoutFormatter",
    "ZmkFileContentGenerator",
    "KConfigGenerator",
    "LayoutConfig",
    "LayoutMetadata",
    "ViewMode",
    "KConfigSettings",
    "create_grid_layout_formatter",
    "create_zmk_file_generator",
    "create_kconfig_generator",
    # Backward compatibility (deprecated)
    "DtsiLayoutGenerator",
    "DTSIGenerator",
    "create_layout_generator",
]
