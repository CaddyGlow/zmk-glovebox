"""
Configuration module for Glovebox.

This module provides a simplified, direct approach to configuration management
using YAML files for keyboard configurations and JSON for user preferences.
"""

# Import and expose the keyboard configuration components
from .keyboard_config import (
    clear_cache,
    create_keyboard_profile,
    get_available_firmwares,
    get_available_keyboards,
    get_firmware_config,
    load_keyboard_config,
)
from .models import (
    BuildConfig,
    BuildOptions,
    FirmwareConfig,
    FlashConfig,
    FormattingConfig,
    KConfigOption,
    KeyboardConfig,
    KeymapSection,
    SystemBehavior,
    VisualLayout,
)
from .profile import KeyboardProfile
from .user_config import UserConfig, default_user_config


__all__ = [
    # Keyboard config functions
    "clear_cache",
    "create_keyboard_profile",
    "get_available_firmwares",
    "get_available_keyboards",
    "get_firmware_config",
    "load_keyboard_config",
    # Data models
    "BuildConfig",
    "BuildOptions",
    "FirmwareConfig",
    "FlashConfig",
    "FormattingConfig",
    "KConfigOption",
    "KeyboardConfig",
    "KeymapSection",
    "SystemBehavior",
    "VisualLayout",
    "KeyboardProfile",
    # User config
    "UserConfig",
    "default_user_config",
]
