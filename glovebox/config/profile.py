"""
KeyboardProfile class for accessing keyboard configuration.

This module provides a class that encapsulates keyboard configuration and
provides convenient methods for accessing and manipulating that configuration.
"""

from pathlib import Path

from glovebox.config.models import (
    FirmwareConfig,
    KConfigOption,
    KeyboardConfig,
)
from glovebox.core.errors import ConfigError
from glovebox.core.structlog_logger import get_struct_logger
from glovebox.layout.models import SystemBehavior


logger = get_struct_logger(__name__)


class KeyboardProfile:
    """
    Profile for a keyboard with a specific firmware.

    This class encapsulates the configuration for a keyboard with a specific
    firmware version, providing convenient methods for accessing the configuration.
    """

    def __init__(
        self,
        keyboard_config: KeyboardConfig,
        firmware_version: str | None = None,
        config_path: Path | None = None,
    ):
        """
        Initialize the keyboard profile.

        Args:
            keyboard_config: The keyboard configuration
            firmware_version: The firmware version to use (optional for keyboard-only profiles)
            config_path: Path to the config file this profile was loaded from (optional)

        Raises:
            ConfigError: If the firmware version is specified but not found in the keyboard config
        """
        self.keyboard_config = keyboard_config
        self.keyboard_name = keyboard_config.keyboard
        self.firmware_version = firmware_version
        self.config_path = config_path

        # Handle firmware configuration
        if firmware_version is not None:
            # Validate firmware version exists
            if firmware_version not in keyboard_config.firmwares:
                raise ConfigError(
                    f"Firmware '{firmware_version}' not found in keyboard '{self.keyboard_name}'"
                )
            self.firmware_config: FirmwareConfig | None = keyboard_config.firmwares[
                firmware_version
            ]
        else:
            # No firmware specified - use None
            self.firmware_config = None

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
            List of system behaviors merge with the one from firmware.
        """
        return self.keyboard_config.keymap.system_behaviors + (
            self.firmware_config.system_behaviors if self.firmware_config else []
        )

    @property
    def kconfig_options(self) -> dict[str, KConfigOption]:
        """
        Get combined kconfig options from keyboard and firmware.

        Returns:
            Dictionary of kconfig option name to KConfigOption. Returns empty dict if no firmware is specified.
        """

        # Start with keyboard kconfig options
        combined = dict(self.keyboard_config.keymap.kconfig_options)

        # Add firmware kconfig options (overriding where they exist)
        if self.firmware_config is not None and self.firmware_config.kconfig:
            for key, value in self.firmware_config.kconfig.items():
                combined[key] = value

        return combined

    def get_keyboard_directory(self) -> Path | None:
        """Get the keyboard's profile directory path.

        Returns:
            Path to the keyboard's directory, or None if not found
        """
        from glovebox.config.keyboard_profile import _find_keyboard_config_file

        config_file = _find_keyboard_config_file(self.keyboard_name)
        if config_file:
            # Check if there's a directory with the same name as the keyboard
            keyboard_dir = config_file.parent / self.keyboard_name
            if keyboard_dir.exists() and keyboard_dir.is_dir():
                return keyboard_dir
            # Fall back to config file's parent directory
            return config_file.parent
        return None

    def load_file(self, relative_path: str) -> str | None:
        """Load a file from the keyboard's profile directory.

        Args:
            relative_path: Path relative to the keyboard's directory (e.g., "toolchain/default.nix")

        Returns:
            File content as string, or None if file not found
        """
        keyboard_dir = self.get_keyboard_directory()
        if not keyboard_dir:
            logger.warning(
                "Could not find keyboard directory for %s", self.keyboard_name
            )
            return None

        file_path = keyboard_dir / relative_path
        if not file_path.exists():
            logger.warning("File not found: %s", file_path)
            return None

        try:
            return file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error("Failed to read file %s: %s", file_path, e)
            return None

    def load_toolchain_file(self, filename: str) -> str | None:
        """Load a file from the keyboard's toolchain directory.

        Args:
            filename: Name of the file in the toolchain directory (e.g., "default.nix")

        Returns:
            File content as string, or None if file not found
        """
        return self.load_file(f"toolchain/{filename}")

    def __str__(self) -> str:
        return f"{self.keyboard_name}/{self.firmware_version}"
