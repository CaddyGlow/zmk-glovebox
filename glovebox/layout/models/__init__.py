"""Layout models for keyboard layouts."""

# Import behavior models that are now part of the layout domain
from glovebox.layout.behavior.models import (
    BehaviorCommand,
    BehaviorParameter,
    KeymapBehavior,
    ParameterType,
    ParamValue,
    SystemBehavior,
    SystemBehaviorParam,
    SystemParamList,
)

from .behavior_data import BehaviorData
from .behaviors import (
    BehaviorList,
    CapsWordBehavior,
    ComboBehavior,
    HoldTapBehavior,
    InputListener,
    InputListenerNode,
    InputProcessor,
    MacroBehavior,
    ModMorphBehavior,
    StickyKeyBehavior,
    TapDanceBehavior,
)
from .bookmarks import BookmarkCollection, BookmarkSource, LayoutBookmark
from .config import ConfigParameter
from .core import LayoutBinding, LayoutLayer, LayoutParam
from .keymap import (
    ConfigDirective,
    DependencyInfo,
    KeymapComment,
    KeymapInclude,
    KeymapMetadata,
)
from .metadata import LayoutData, LayoutMetadata
from .results import KeymapResult, LayoutResult
from .types import (
    ConfigParamList,
    ConfigValue,
    LayerBindings,
    LayerIndex,
    TemplateNumeric,
)


# Re-export all models for external use
__all__ = [
    # Type aliases
    "ConfigValue",
    "LayerIndex",
    "TemplateNumeric",
    "LayerBindings",
    "BehaviorList",
    "ConfigParamList",
    # Layout models
    "LayoutParam",
    "LayoutBinding",
    "LayoutLayer",
    "LayoutData",
    "LayoutMetadata",
    # Behavior models
    "BehaviorData",
    "HoldTapBehavior",
    "ComboBehavior",
    "MacroBehavior",
    "TapDanceBehavior",
    "StickyKeyBehavior",
    "CapsWordBehavior",
    "ModMorphBehavior",
    "InputProcessor",
    "InputListenerNode",
    "InputListener",
    "ConfigParameter",
    # Re-exported behavior models from behavior_models
    "BehaviorCommand",
    "BehaviorParameter",
    "KeymapBehavior",
    "ParameterType",
    "ParamValue",
    "SystemBehavior",
    "SystemBehaviorParam",
    "SystemParamList",
    # Keymap parsing models
    "KeymapComment",
    "KeymapInclude",
    "ConfigDirective",
    "DependencyInfo",
    "KeymapMetadata",
    # Result models
    "KeymapResult",
    "LayoutResult",
    # Bookmark models
    "LayoutBookmark",
    "BookmarkCollection",
    "BookmarkSource",
]
