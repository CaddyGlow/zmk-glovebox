"""Behavior package for ZMK behavior processing and management.

This package contains all behavior-related functionality within the layout domain:
- Behavior models and data structures
- Behavior analysis and registry
- Behavior formatting for DTSI output
- Behavior service for management
"""

from typing import TYPE_CHECKING

# Import and re-export behavior functions and services
from .analysis import (
    extract_behavior_codes_from_layout,
    get_required_includes_for_layout,
    register_layout_behaviors,
)

# Import and re-export all behavior models
from .models import (
    BehaviorCommand,
    BehaviorParameter,
    KeymapBehavior,
    ParameterType,
    ParamValue,
    SystemBehavior,
    SystemBehaviorParam,
    SystemParamList,
)
from .service import create_behavior_registry


if TYPE_CHECKING:
    from .formatter import BehaviorFormatterImpl
    from .service import BehaviorRegistryImpl

__all__ = [
    # Behavior models
    "BehaviorCommand",
    "BehaviorParameter",
    "KeymapBehavior",
    "ParameterType",
    "ParamValue",
    "SystemBehavior",
    "SystemBehaviorParam",
    "SystemParamList",
    # Behavior functions
    "extract_behavior_codes_from_layout",
    "get_required_includes_for_layout",
    "register_layout_behaviors",
    # Behavior services
    "create_behavior_registry",
]
