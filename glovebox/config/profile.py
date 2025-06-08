"""
KeyboardProfile class for accessing keyboard configuration.

This module provides a class that encapsulates keyboard configuration and
provides convenient methods for accessing and manipulating that configuration.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from glovebox.config.models import (
    BuildOptions,
    FirmwareConfig,
    KConfigOption,
    KeyboardConfig,
)
from glovebox.core.errors import ConfigError
from glovebox.core.logging import get_logger
from glovebox.layout.models import SystemBehavior


logger = get_logger(__name__)


class KeyboardProfile:
    """
    Profile for a keyboard with a specific firmware.

    This class encapsulates the configuration for a keyboard with a specific
    firmware version, providing convenient methods for accessing the configuration.
    """

    def __init__(self, keyboard_config: KeyboardConfig, firmware_version: str):
        """
        Initialize the keyboard profile.

        Args:
            keyboard_config: The keyboard configuration
            firmware_version: The firmware version to use

        Raises:
            ConfigError: If the firmware version is not found in the keyboard config
        """
        self.keyboard_config = keyboard_config
        self.keyboard_name = keyboard_config.keyboard
        self.firmware_version = firmware_version

        # Validate firmware version exists
        if firmware_version not in keyboard_config.firmwares:
            raise ConfigError(
                f"Firmware '{firmware_version}' not found in keyboard '{self.keyboard_name}'"
            )

        self.firmware_config = keyboard_config.firmwares[firmware_version]

    @classmethod
    def from_names(cls, keyboard_name: str, firmware_version: str) -> "KeyboardProfile":
        """
        Create a profile from keyboard name and firmware version.

        Args:
            keyboard_name: Name of the keyboard
            firmware_version: Version of firmware to use

        Returns:
            Configured KeyboardProfile instance

        Raises:
            ConfigError: If configuration cannot be found
        """
        from glovebox.config.keyboard_profile import load_keyboard_config

        keyboard_config = load_keyboard_config(keyboard_name)
        return cls(keyboard_config, firmware_version)

    @property
    def system_behaviors(self) -> list[SystemBehavior]:
        """
        Get system behaviors for this profile.

        Returns:
            List of system behaviors
        """
        return self.keyboard_config.keymap.system_behaviors

    @property
    def kconfig_options(self) -> dict[str, KConfigOption]:
        """
        Get combined kconfig options from keyboard and firmware.

        Returns:
            Dictionary of kconfig option name to KConfigOption
        """
        # Start with keyboard kconfig options
        combined = dict(self.keyboard_config.keymap.kconfig_options)

        # Add firmware kconfig options (overriding where they exist)
        if self.firmware_config.kconfig:
            for key, value in self.firmware_config.kconfig.items():
                combined[key] = value

        return combined
