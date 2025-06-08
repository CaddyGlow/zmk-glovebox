"""Layout domain for keyboard layout processing.

This package contains all layout-related functionality including:
- Layout models and data structures
- Layout service for processing operations
- Component service for layer extraction/merging
"""

from glovebox.layout.component_service import (
    LayoutComponentService,
    create_layout_component_service,
)
from glovebox.layout.models import (
    LayoutBinding,
    LayoutData,
    LayoutLayer,
    LayoutMetadata,
    LayoutParam,
)
from glovebox.layout.service import LayoutService, create_layout_service

__all__ = [
    # Models
    "LayoutData",
    "LayoutMetadata",
    "LayoutLayer",
    "LayoutBinding",
    "LayoutParam",
    # Services
    "LayoutService",
    "LayoutComponentService",
    # Factory functions
    "create_layout_service",
    "create_layout_component_service",
]