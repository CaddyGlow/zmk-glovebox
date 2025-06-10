"""Configuration models organized by domain."""

# Import all models for backward compatibility
from .behavior import BehaviorConfig, BehaviorMapping, ModifierMapping
from .display import DisplayConfig, DisplayFormatting, LayoutStructure
from .firmware import (
    BuildOptions,
    FirmwareConfig,
    FirmwareFlashConfig,
    KConfigOption,
    UserFirmwareConfig,
)
from .keyboard import (
    FormattingConfig,
    KeyboardConfig,
    KeymapSection,
    VisualLayout,
)
from .user import UserConfigData
from .zmk import (
    FileExtensions,
    ValidationLimits,
    ZmkCompatibleStrings,
    ZmkConfig,
    ZmkPatterns,
)


__all__ = [
    # Behavior models
    "BehaviorConfig",
    "BehaviorMapping",
    "ModifierMapping",
    # Display models
    "DisplayConfig",
    "DisplayFormatting",
    "LayoutStructure",
    # Firmware models
    "BuildOptions",
    "FirmwareConfig",
    "FirmwareFlashConfig",
    "KConfigOption",
    "UserFirmwareConfig",
    # Keyboard models
    "FormattingConfig",
    "KeyboardConfig",
    "KeymapSection",
    "VisualLayout",
    # User models
    "UserConfigData",
    # ZMK models
    "FileExtensions",
    "ValidationLimits",
    "ZmkCompatibleStrings",
    "ZmkConfig",
    "ZmkPatterns",
]
