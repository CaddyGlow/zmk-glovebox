"""
Configuration module for Glovebox.

This module provides a simplified, direct approach to configuration management
using YAML files for keyboard configurations and user preferences.
"""

# Import configuration functions and modules

from .keyboard_profile import (
    clear_cache,
    create_keyboard_profile,
    create_keyboard_profile_with_includes,
    get_available_firmwares,
    get_available_keyboards,
    get_firmware_config,
    load_keyboard_config,
    load_keyboard_config_with_includes,
)
from .minimal_compile_config import (
    MinimalCompileConfig,
    MinimalCompileConfigUnion,
    MinimalMoergoConfig,
    MinimalZmkConfig,
)
from .profile import KeyboardProfile
from .user_config import UserConfig, create_user_config


__all__ = [
    # Keyboard config functions
    "clear_cache",
    "create_keyboard_profile",
    "create_keyboard_profile_with_includes",
    "get_available_firmwares",
    "get_available_keyboards",
    "get_firmware_config",
    "load_keyboard_config",
    "load_keyboard_config_with_includes",
    # Config module classes
    "KeyboardProfile",
    "UserConfig",
    "create_user_config",
    # Minimal compilation configurations
    "MinimalCompileConfig",
    "MinimalCompileConfigUnion",
    "MinimalMoergoConfig",
    "MinimalZmkConfig",
]
