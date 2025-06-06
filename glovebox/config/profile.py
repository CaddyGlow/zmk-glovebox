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
)
from glovebox.core.errors import ConfigError
from glovebox.core.logging import get_logger
from glovebox.models import SystemBehavior
from glovebox.models.keymap import KeymapData


# Handle circular import using TYPE_CHECKING
if TYPE_CHECKING:
    from glovebox.services.behavior_service import BehaviorRegistry


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
        from glovebox.config.keyboard_config import load_keyboard_config

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

    # We are keeping this methods but commented out
    # we should move it else where
    # def _format_kconfig_value(self, value: Any, value_type: str) -> str:
    #     """
    #     Format a kconfig value based on its type.
    #
    #     Args:
    #         value: The value to format
    #         value_type: The type of the value (bool, int, string)
    #
    #     Returns:
    #         Formatted string value for kconfig
    #     """
    #     if value_type == "bool":
    #         # Handle boolean values
    #         if isinstance(value, bool):
    #             return "y" if value else "n"
    #         if isinstance(value, str):
    #             return "y" if value.lower() in ["true", "yes", "y", "1"] else "n"
    #         return "y" if value else "n"
    #     elif value_type == "int":
    #         # Handle integer values
    #         return str(int(value))
    #     else:
    #         # Default to string type
    #         return str(value)

    def extract_behavior_codes(self, keymap_data: KeymapData) -> list[str]:
        """
        Extract behavior codes used in a keymap.

        Args:
            keymap_data: KeymapData object with layers and behaviors

        Returns:
            List of behavior codes used in the keymap
        """
        behavior_codes = set()

        # Get structured layers with properly converted KeymapBinding objects
        structured_layers = keymap_data.get_structured_layers()

        # Extract behavior codes from structured layers
        for layer in structured_layers:
            for binding in layer.bindings:
                if binding and binding.value:
                    # Extract base behavior code (e.g., "&kp" from "&kp SPACE")
                    code = binding.value.split()[0]
                    behavior_codes.add(code)

        # Extract behavior codes from hold-taps
        for ht in keymap_data.hold_taps:
            if ht.tap_behavior:
                code = ht.tap_behavior.split()[0]
                behavior_codes.add(code)
            if ht.hold_behavior:
                code = ht.hold_behavior.split()[0]
                behavior_codes.add(code)

        # Extract behavior codes from combos
        for combo in keymap_data.combos:
            if combo.behavior:
                code = combo.behavior.split()[0]
                behavior_codes.add(code)

        # Extract behavior codes from macros
        for macro in keymap_data.macros:
            if macro.bindings:
                for binding in macro.bindings:
                    code = binding.value.split()[0]
                    behavior_codes.add(code)

        return list(behavior_codes)

    def register_behaviors(self, behavior_registry: "BehaviorRegistry") -> None:
        """
        Register all behaviors from this profile with a behavior registry.

        Args:
            behavior_registry: The registry to register behaviors with
        """
        for behavior in self.system_behaviors:
            behavior_registry.register_behavior(behavior)

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

        return sorted(base_includes)
