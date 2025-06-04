"""
KeyboardProfile class for accessing keyboard configuration.

This module provides a class that encapsulates keyboard configuration and
provides convenient methods for accessing and manipulating that configuration.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any

from glovebox.config.models import (
    FirmwareConfig,
    KConfigOption,
    KeyboardConfig,
    SystemBehavior,
)
from glovebox.core.errors import ConfigError
from glovebox.core.logging import get_logger


# Handle circular import using TYPE_CHECKING
if TYPE_CHECKING:
    from glovebox.services.behavior_service import BehaviorRegistryImpl


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
        from glovebox.config.keyboard_config import load_keyboard_config_typed

        keyboard_config = load_keyboard_config_typed(keyboard_name)
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

    def resolve_kconfig_with_user_options(
        self, user_options: dict[str, Any]
    ) -> dict[str, str]:
        """
        Resolve kconfig settings with user-provided options.

        Args:
            user_options: User-provided kconfig settings

        Returns:
            Dictionary mapping kconfig names to their resolved values
        """
        options = self.kconfig_options
        resolved: dict[str, str] = {}

        # Apply defaults
        for _, config in options.items():
            resolved[config.name] = str(config.default)

        # Apply user overrides
        for key, value in user_options.items():
            if key in options:
                resolved[options[key].name] = str(value)

        return resolved

    def register_behaviors(self, behavior_registry: "BehaviorRegistryImpl") -> None:
        """
        Register all behaviors from this profile with a behavior registry.

        Args:
            behavior_registry: The registry to register behaviors with
        """
        for behavior in self.system_behaviors:
            behavior_registry.register_behavior(
                behavior.name, behavior.expected_params, behavior.origin
            )

    def resolve_includes(self, behaviors_used: list[str]) -> list[str]:
        """
        Resolve all necessary includes based on behaviors used.

        Args:
            behaviors_used: List of behavior codes used in the keymap

        Returns:
            List of include statements needed for the behaviors
        """
        base_includes: set[str] = set(self.keyboard_config.keymap.includes)

        # Add includes for each behavior
        for behavior in self.system_behaviors:
            if behavior.code in behaviors_used and behavior.includes:
                base_includes.update(behavior.includes)
