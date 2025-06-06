"""
Configuration module for Glovebox.

This module provides a simplified, direct approach to configuration management
using YAML files for keyboard configurations and user preferences.
"""

# Import configuration functions and modules
# Re-export models from models package for backward compatibility
from glovebox.models import (
    BuildConfig,
    BuildOptions,
    FirmwareConfig,
    FlashConfig,
    FormattingConfig,
    KConfigOption,
    KeyboardConfig,
    KeymapSection,
    VisualLayout,
)

from .keyboard_config import (
    clear_cache,
    create_keyboard_profile,
    get_available_firmwares,
    get_available_keyboards,
    get_firmware_config,
    load_keyboard_config,
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
    # Data models (re-exported from models package)
    "BuildConfig",
    "BuildOptions",
    "FirmwareConfig",
    "FlashConfig",
    "FormattingConfig",
    "KConfigOption",
    "KeyboardConfig",
    "KeymapSection",
    "VisualLayout",
]
