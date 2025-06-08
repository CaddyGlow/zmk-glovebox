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

# Import other factory functions
from glovebox.layout.behavior_analysis import (
    extract_behavior_codes_from_layout,
    get_required_includes_for_layout,
    register_layout_behaviors,
)

# Import and re-export all models from layout domain
from glovebox.layout.behavior_models import (
    BehaviorCommand,
    BehaviorParameter,
    KeymapBehavior,
    ParameterType,
    ParamValue,
    RegistryBehavior,
    SystemBehavior,
    SystemBehaviorParam,
    SystemParamList,
)
from glovebox.layout.behavior_service import create_behavior_registry

# Import and re-export service factory functions
from glovebox.layout.component_service import create_layout_component_service
from glovebox.layout.display_service import create_layout_display_service
from glovebox.layout.formatting import create_grid_layout_formatter

# from glovebox.layout.generator import create_layout_generator  # Module missing
from glovebox.layout.kconfig_generator import create_kconfig_generator
from glovebox.layout.models import (
    BehaviorList,
    ComboBehavior,
    ConfigParameter,
    ConfigParamList,
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
    MacroBehavior,
)
from glovebox.layout.service import create_layout_service
from glovebox.layout.zmk_generator import create_zmk_file_generator


if TYPE_CHECKING:
    from glovebox.layout.behavior_formatter import BehaviorFormatterImpl
    from glovebox.layout.display_service import LayoutDisplayService

    # from glovebox.layout.generator import LayoutGenerator  # Module missing
    from glovebox.layout.service import LayoutService


__all__ = [
    # Layout models
    "LayoutData",
    "LayoutBinding",
    "LayoutLayer",
    "LayoutParam",
    "LayoutMetadata",
    "LayerBindings",
    "LayerIndex",
    "ConfigValue",
    "ConfigParameter",
    "ConfigParamList",
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
    "RegistryBehavior",
    "KeymapBehavior",
    "BehaviorCommand",
    "BehaviorParameter",
    "ParameterType",
    "ParamValue",
    # Factory functions
    "create_layout_service",
    "create_layout_component_service",
    "create_layout_display_service",
    # "create_layout_generator",  # Module missing
    "create_grid_layout_formatter",
    "create_zmk_file_generator",
    "create_kconfig_generator",
    "create_behavior_registry",
    # Behavior analysis functions
    "extract_behavior_codes_from_layout",
    "get_required_includes_for_layout",
    "register_layout_behaviors",
]
