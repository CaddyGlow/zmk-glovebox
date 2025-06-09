"""Helper functions for working with keyboard profiles in CLI commands."""

import logging
from typing import TYPE_CHECKING

import typer

from glovebox.config.keyboard_profile import (
    create_keyboard_profile,
    get_available_firmwares,
    get_available_keyboards,
)
from glovebox.config.profile import KeyboardProfile


if TYPE_CHECKING:
    from glovebox.config.user_config import UserConfig

logger = logging.getLogger(__name__)

# Default fallback profile (aligned with user config default)
DEFAULT_PROFILE = "glove80/v25.05"


def get_user_config_from_context(ctx: typer.Context) -> "UserConfig | None":
    """Get UserConfig from Typer context.

    Args:
        ctx: Typer context

    Returns:
        UserConfig instance if available, None otherwise
    """
    try:
        from glovebox.cli.app import AppContext

        app_ctx: AppContext = ctx.obj
        return app_ctx.user_config if app_ctx else None
    except (AttributeError, ImportError):
        logger.debug("Could not get user config from context")
        return None


def get_effective_profile(
    profile_option: str | None, user_config: "UserConfig | None" = None
) -> str:
    """Get the effective profile to use based on precedence rules.

    Precedence (highest to lowest):
    1. CLI explicit profile option
    2. User config profile setting
    3. Hardcoded fallback default

    Args:
        profile_option: Profile option from CLI (highest precedence)
        user_config: User configuration instance (middle precedence)

    Returns:
        Profile string to use
    """
    # 1. CLI explicit profile has highest precedence
    if profile_option is not None:
        return profile_option

    # 2. User config profile has middle precedence
    if user_config is not None:
        try:
            return user_config._config.profile
        except AttributeError:
            logger.debug("User config profile not available, using fallback")

    # 3. Hardcoded fallback has lowest precedence
    return DEFAULT_PROFILE


def create_profile_from_option(
    profile_option: str | None, user_config: "UserConfig | None" = None
) -> KeyboardProfile:
    """Create a KeyboardProfile from a profile option string.

    Args:
        profile_option: Profile option string in format "keyboard" or "keyboard/firmware"
                        If None, uses user config profile or fallback default.
        user_config: User configuration instance for default profile

    Returns:
        KeyboardProfile instance

    Raises:
        typer.Exit: If profile creation fails
    """
    # Get effective profile using centralized precedence logic
    effective_profile = get_effective_profile(profile_option, user_config)

    # Parse profile to get keyboard name and firmware version
    if "/" in effective_profile:
        keyboard_name, firmware_name = effective_profile.split("/", 1)
    else:
        keyboard_name = effective_profile
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


def create_profile_from_context(
    ctx: typer.Context, profile_option: str | None
) -> KeyboardProfile:
    """Create a KeyboardProfile from context and profile option.

    Convenience function that automatically gets user config from context.

    Args:
        ctx: Typer context containing user config
        profile_option: Profile option string or None

    Returns:
        KeyboardProfile instance

    Raises:
        typer.Exit: If profile creation fails
    """
    user_config = get_user_config_from_context(ctx)
    return create_profile_from_option(profile_option, user_config)
