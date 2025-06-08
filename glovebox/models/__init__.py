"""Models package for Glovebox."""

# Layout models moved to glovebox.layout.models
# Import them here for backward compatibility
# Flash models moved to glovebox.flash.models
# Import them here for backward compatibility
from glovebox.flash.models import (
    BlockDeviceDict,
    BlockDevicePathMap,
    BlockDeviceSymlinks,
    FlashResult,
)
from glovebox.layout.models import (
    ComboBehavior,
    ConfigParameter,
    HoldTapBehavior,
    InputListener,
    InputListenerNode,
    InputProcessor,
    MacroBehavior,
)
from glovebox.layout.models import (
    LayoutBinding as KeymapBinding,  # Keep old name for compatibility
)
from glovebox.layout.models import (
    LayoutData as KeymapData,  # Keep old name for compatibility
)
from glovebox.layout.models import (
    LayoutLayer as KeymapLayer,  # Keep old name for compatibility
)

from .behavior import (
    BehaviorCommand,
    BehaviorParameter,
    KeymapBehavior,
    ParameterType,
    RegistryBehavior,
    SystemBehavior,
    SystemBehaviorParam,
)
from .config import (
    BuildConfig,
    BuildOptions,
    FirmwareConfig,
    FlashConfig,
    FormattingConfig,
    KConfigOption,
    KeyboardConfig,
    KeymapSection,
    UserConfigData,
    VisualLayout,
)
from .results import BuildResult, KeymapResult, LayoutResult


__all__ = [
    # Result models
    "BuildResult",
    "FlashResult",
    "KeymapResult",
    "LayoutResult",
    # Keymap models
    "KeymapData",
    "KeymapBinding",
    "KeymapLayer",
    "HoldTapBehavior",
    "ComboBehavior",
    "MacroBehavior",
    "ConfigParameter",
    "InputProcessor",
    "InputListenerNode",
    "InputListener",
    # Behavior models
    "BehaviorCommand",
    "BehaviorParameter",
    "KeymapBehavior",
    "ParameterType",
    "RegistryBehavior",
    "SystemBehavior",
    "SystemBehaviorParam",
    # Config models
    "BuildConfig",
    "BuildOptions",
    "FirmwareConfig",
    "FlashConfig",
    "FormattingConfig",
    "KConfigOption",
    "KeyboardConfig",
    "KeymapSection",
    "UserConfigData",
    "VisualLayout",
    # Flash models
    "BlockDeviceDict",
    "BlockDevicePathMap",
    "BlockDeviceSymlinks",
]
