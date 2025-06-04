"""Helper functions for working with keyboard profiles in CLI commands."""

import logging
from typing import Optional

import typer

from glovebox.config.keyboard_config import (
    create_keyboard_profile,
    get_available_firmwares,
    get_available_keyboards,
)
from glovebox.config.profile import KeyboardProfile


logger = logging.getLogger(__name__)


def create_profile_from_option(profile_option: str | None) -> KeyboardProfile:
    """Create a KeyboardProfile from a profile option string.

    Args:
        profile_option: Profile option string in format "keyboard" or "keyboard/firmware"
                        If None, uses the default profile.

    Returns:
        KeyboardProfile instance

    Raises:
        typer.Exit: If profile creation fails
    """
    if profile_option is None:
        profile_option = "glove80/default"

    # Parse profile to get keyboard name and firmware version
    if "/" in profile_option:
        keyboard_name, firmware_name = profile_option.split("/", 1)
    else:
        keyboard_name = profile_option
        firmware_name = "default"

    logger.debug(f"Using keyboard: {keyboard_name}, firmware: {firmware_name}")

    # Create KeyboardProfile
    try:
        keyboard_profile = create_keyboard_profile(keyboard_name, firmware_name)
        logger.debug(f"Created keyboard profile for {keyboard_name}/{firmware_name}")
        return keyboard_profile
    except Exception as e:
        # Handle profile creation errors with helpful feedback
        if "not found for keyboard" in str(e):
            # Show available firmwares if the firmware wasn't found
            print(
                f"Error: Firmware '{firmware_name}' not found for keyboard: {keyboard_name}"
            )
            try:
                firmwares = get_available_firmwares(keyboard_name)
                if firmwares:
                    print("Available firmwares:")
                    for fw_name in firmwares:
                        print(f"  • {fw_name}")
            except Exception:
                pass
        else:
            # General configuration error
            print(f"Error: Failed to load keyboard configuration: {e}")
            keyboards = get_available_keyboards()
            print("Available keyboards:")
            for kb in keyboards:
                print(f"  • {kb}")
        raise typer.Exit(1) from e
