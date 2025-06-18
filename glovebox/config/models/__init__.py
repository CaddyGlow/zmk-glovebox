"""Configuration models organized by domain."""

# Export commonly used models that are referenced throughout the codebase
from .behavior import BehaviorConfig, BehaviorMapping, ModifierMapping
from .display import DisplayConfig, DisplayFormatting, LayoutStructure
from .firmware import (
    BuildOptions,
    FirmwareConfig,
    FirmwareFlashConfig,
    KConfigOption,
    UserFirmwareConfig,
)
from .keyboard import FormattingConfig, KeyboardConfig, KeymapSection
from .user import UserConfigData
from .zmk import (
    FileExtensions,
    ValidationLimits,
    ZmkCompatibleStrings,
    ZmkConfig,
    ZmkPatterns,
)


__all__ = [
    "BehaviorConfig",
    "BehaviorMapping",
    "BuildOptions",
    "DisplayConfig",
    "DisplayFormatting",
    "FileExtensions",
    "FirmwareConfig",
    "FirmwareFlashConfig",
    "FormattingConfig",
    "KConfigOption",
    "KeyboardConfig",
    "KeymapSection",
    "LayoutStructure",
    "ModifierMapping",
    "UserConfigData",
    "UserFirmwareConfig",
    "ValidationLimits",
    "ZmkCompatibleStrings",
    "ZmkConfig",
    "ZmkPatterns",
]
