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

    def __init__(
        self, keyboard_config: KeyboardConfig, firmware_version: str | None = None
    ):
        """
        Initialize the keyboard profile.

        Args:
            keyboard_config: The keyboard configuration
            firmware_version: The firmware version to use (optional)

        Raises:
            ConfigError: If the firmware version is specified but not found in the keyboard config
        """
        self.keyboard_config = keyboard_config
        self.keyboard_name = keyboard_config.keyboard
        self.firmware_version = firmware_version
        self.firmware_config: FirmwareConfig | None = None

        # Handle firmware configuration
        if firmware_version is not None:
            if not keyboard_config.firmwares:
                raise ConfigError(
                    f"No firmware configurations available for keyboard '{self.keyboard_name}', but firmware version '{firmware_version}' was requested"
                )

            if firmware_version not in keyboard_config.firmwares:
                raise ConfigError(
                    f"Firmware '{firmware_version}' not found in keyboard '{self.keyboard_name}'"
                )

            self.firmware_config = keyboard_config.firmwares[firmware_version]
        else:
            # No specific firmware requested
            if keyboard_config.firmwares:
                # Use the first available firmware if any exist
                first_firmware = next(iter(keyboard_config.firmwares.keys()))
                self.firmware_version = first_firmware
                self.firmware_config = keyboard_config.firmwares[first_firmware]
                logger.debug(
                    "No firmware version specified, using first available: %s",
                    first_firmware,
                )
            else:
                # No firmware configurations available - create a minimal default
                logger.debug("No firmware configurations available, using defaults")
                self.firmware_version = "default"
                self.firmware_config = self._create_default_firmware_config()

    def _create_default_firmware_config(self) -> FirmwareConfig:
        """Create a minimal default firmware configuration for keyboards without firmware definitions."""
        # Create default build options using keyboard build config
        build_options = BuildOptions(
            repository=self.keyboard_config.build.repository,
            branch=self.keyboard_config.build.branch,
        )

        return FirmwareConfig(
            version="default",
            description="Default firmware configuration",
            build_options=build_options,
            kconfig=None,
        )

    @classmethod
    def from_names(
        cls, keyboard_name: str, firmware_version: str | None = None
    ) -> "KeyboardProfile":
        """
        Create a profile from keyboard name and firmware version.

        Args:
            keyboard_name: Name of the keyboard
            firmware_version: Version of firmware to use (optional)

        Returns:
            Configured KeyboardProfile instance

        Raises:
            ConfigError: If configuration cannot be found
        """
        from glovebox.config.keyboard_profile import load_keyboard_config

        keyboard_config = load_keyboard_config(keyboard_name)
        return cls(keyboard_config, firmware_version)

    @classmethod
    def for_flashing(cls, keyboard_name: str) -> "KeyboardProfile":
        """
        Create a profile specifically for flashing operations.

        This method creates a profile optimized for flash operations, which only requires
        the keyboard's flash configuration. It doesn't require keymap or firmware definitions.

        Args:
            keyboard_name: Name of the keyboard

        Returns:
            KeyboardProfile configured for flashing operations

        Raises:
            ConfigError: If keyboard configuration cannot be found
        """
        from glovebox.config.keyboard_profile import load_keyboard_config

        keyboard_config = load_keyboard_config(keyboard_name)
        return cls(keyboard_config, firmware_version=None)

    @property
    def system_behaviors(self) -> list[SystemBehavior]:
        """
        Get system behaviors for this profile.

        Returns:
            List of system behaviors (empty if no keymap configured)
        """
        if not self.keyboard_config.keymap:
            return []
        return self.keyboard_config.keymap.system_behaviors

    @property
    def kconfig_options(self) -> dict[str, KConfigOption]:
        """
        Get combined kconfig options from keyboard and firmware.

        Returns:
            Dictionary of kconfig option name to KConfigOption
        """
        # Start with keyboard kconfig options (if keymap exists)
        combined = {}
        if self.keyboard_config.keymap:
            combined = dict(self.keyboard_config.keymap.kconfig_options)

        # Add firmware kconfig options (overriding where they exist)
        if self.firmware_config and self.firmware_config.kconfig:
            for key, value in self.firmware_config.kconfig.items():
                combined[key] = value

        return combined
