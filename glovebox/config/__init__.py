"""
Configuration module for Glovebox.

This module provides a simplified, direct approach to configuration management
using YAML files for keyboard configurations and user preferences.
"""

# Import configuration functions and modules

from .keyboard_profile import (
    clear_cache,
    create_keyboard_profile,
    get_available_firmwares,
    get_available_keyboards,
    get_firmware_config,
    load_keyboard_config,
)
from .models import (
    BehaviorConfig,
    BehaviorMapping,
    BuildOptions,
    DisplayConfig,
    DisplayFormatting,
    FirmwareConfig,
    FormattingConfig,
    KConfigOption,
    KeyboardConfig,
    KeymapSection,
    LayoutStructure,
    ModifierMapping,
    UserConfigData,
    VisualLayout,
)
from .profile import KeyboardProfile
from .user_config import UserConfig, create_user_config


__all__ = [
    # Keyboard config functions
    "clear_cache",
    "create_keyboard_profile",
    "get_available_firmwares",
    "get_available_keyboards",
    "get_firmware_config",
    "load_keyboard_config",
    # Config module classes
    "KeyboardProfile",
    "UserConfig",
    "create_user_config",
    # Config models
    "BehaviorConfig",
    "BehaviorMapping",
    "BuildOptions",
    "DisplayConfig",
    "DisplayFormatting",
    "FirmwareConfig",
    "FormattingConfig",
    "KConfigOption",
    "KeyboardConfig",
    "KeymapSection",
    "LayoutStructure",
    "ModifierMapping",
    "UserConfigData",
    "VisualLayout",
]
