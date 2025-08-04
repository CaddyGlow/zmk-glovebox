"""Layout domain for keyboard layout processing.

This package contains all layout-related functionality including:
- Layout models and data structures
- Layout service for processing operations
- Component service for layer extraction/merging
- Display service for layout visualization
- Generator for layout formatting
- Behavior analysis utilities
"""

from typing import TYPE_CHECKING

# Import and re-export behavior functionality from behavior package
from glovebox.layout.behavior import (
    BehaviorCommand,
    BehaviorManagementService,
    BehaviorParameter,
    KeymapBehavior,
    ParameterType,
    ParamValue,
    SystemBehavior,
    SystemBehaviorParam,
    SystemParamList,
    create_behavior_management_service,
    create_behavior_registry,
    extract_behavior_codes_from_layout,
    get_required_includes_for_layout,
    register_layout_behaviors,
)

# Import and re-export service factory functions and classes
from glovebox.layout.component_service import (
    LayoutComponentService,
    create_layout_component_service,
)
from glovebox.layout.display_service import (
    LayoutDisplayService,
    create_layout_display_service,
)
from glovebox.layout.formatting import (
    GridLayoutFormatter,
    ViewMode,
    create_grid_layout_formatter,
)
from glovebox.layout.models import (
    BehaviorList,
    ComboBehavior,
    ConfigParameter,
    ConfigValue,
    HoldTapBehavior,
    InputListener,
    InputListenerNode,
    InputProcessor,
    LayerBindings,
    LayerIndex,
    LayoutBinding,
    LayoutData,
    LayoutLayer,
    LayoutMetadata,
    LayoutParam,
    LayoutResult,
    MacroBehavior,
)

# Import parser factory functions
from glovebox.layout.parsers import (
    create_zmk_keymap_parser,
    create_zmk_keymap_parser_from_profile,
)
from glovebox.layout.service import LayoutService, create_layout_service
from glovebox.layout.template_service import (
    create_jinja2_template_service,
    create_template_service,
)
from glovebox.layout.zmk_generator import (
    ZmkFileContentGenerator,
    create_zmk_file_generator,
)


if TYPE_CHECKING:
    from glovebox.layout.behavior.formatter import BehaviorFormatterImpl


__all__ = [
    # Layout models
    "LayoutData",
    "LayoutBinding",
    "LayoutLayer",
    "LayoutParam",
    "LayoutMetadata",
    "LayoutResult",
    "LayerBindings",
    "LayerIndex",
    "ConfigValue",
    "ConfigParameter",
    "BehaviorList",
    # Behavior models
    "HoldTapBehavior",
    "ComboBehavior",
    "MacroBehavior",
    "InputListener",
    "InputListenerNode",
    "InputProcessor",
    "SystemBehavior",
    "SystemBehaviorParam",
    "SystemParamList",
    "KeymapBehavior",
    "BehaviorCommand",
    "BehaviorParameter",
    "ParameterType",
    "ParamValue",
    "BehaviorManagementService",
    # Service classes
    "LayoutService",
    "LayoutComponentService",
    "LayoutDisplayService",
    "GridLayoutFormatter",
    "ViewMode",
    "ZmkFileContentGenerator",
    # Factory functions
    "create_layout_service",
    "create_layout_component_service",
    "create_layout_display_service",
    "create_grid_layout_formatter",
    "create_zmk_file_generator",
    "create_behavior_registry",
    "create_behavior_management_service",
    "create_template_service",
    "create_jinja2_template_service",
    "create_zmk_keymap_parser",
    "create_zmk_keymap_parser_from_profile",
    # Behavior analysis functions
    "extract_behavior_codes_from_layout",
    "get_required_includes_for_layout",
    "register_layout_behaviors",
]
