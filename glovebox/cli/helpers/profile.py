"""Helper functions for working with keyboard profiles in CLI commands."""

import logging
from typing import TYPE_CHECKING, Any, cast

import typer
from click.core import Context as ClickContext
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from glovebox.config.keyboard_profile import (
    create_keyboard_profile,
    get_available_firmwares,
    get_available_keyboards,
)


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile
    from glovebox.config.user_config import UserConfig

logger = logging.getLogger(__name__)

# Default fallback profile (aligned with user config default)
DEFAULT_PROFILE = "glove80/v25.05"


def get_user_config_from_context(
    ctx: typer.Context | ClickContext,
) -> "UserConfig | None":
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


def get_keyboard_profile_from_context(
    ctx: typer.Context | ClickContext,
) -> "KeyboardProfile":
    """Get KeyboardProfile from Typer context.

    Args:
        ctx: Typer context

    Returns:
       KeyboardProfile instance

    Raises:
        RuntimeError: If keyboard_profile is not available in context
    """
    from glovebox.cli.app import AppContext

    app_ctx: AppContext = ctx.obj
    keyboard_profile = app_ctx.keyboard_profile
    if keyboard_profile is None:
        raise RuntimeError(
            "KeyboardProfile not available in context. Ensure @with_profile decorator is used."
        )
    return keyboard_profile


def get_keyboard_profile_from_kwargs(**kwargs: Any) -> "KeyboardProfile":
    """Get KeyboardProfile from function kwargs.

    This helper function extracts the keyboard_profile that was injected
    by the @with_profile decorator, eliminating the need for manual imports
    and assertions in command functions.

    Args:
        **kwargs: Function keyword arguments containing 'keyboard_profile'

    Returns:
        KeyboardProfile instance

    Raises:
        RuntimeError: If keyboard_profile is not available in kwargs
    """
    keyboard_profile = kwargs.get("keyboard_profile")
    if keyboard_profile is None:
        raise RuntimeError(
            "KeyboardProfile not available in kwargs. Ensure @with_profile decorator is used."
        )
    return cast("KeyboardProfile", keyboard_profile)


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
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Determining effective profile...")
        logger.debug("  CLI profile option: %s", profile_option)
        logger.debug("  User config available: %s", user_config is not None)
        if user_config:
            try:
                logger.debug("  User config profile: %s", user_config._config.profile)
            except AttributeError:
                logger.debug("  User config profile: <not accessible>")
        logger.debug("  Default fallback: %s", DEFAULT_PROFILE)

    # 1. CLI explicit profile has highest precedence
    if profile_option is not None:
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("  ✓ Using CLI profile option: %s", profile_option)
        return profile_option

    # 2. User config profile has middle precedence
    if user_config is not None:
        try:
            profile = user_config._config.profile
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("  ✓ Using user config profile: %s", profile)
            return profile
        except AttributeError:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("  ⚠ User config profile not available, using fallback")

    # 3. Hardcoded fallback has lowest precedence
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("  ✓ Using default fallback profile: %s", DEFAULT_PROFILE)
    return DEFAULT_PROFILE


def create_profile_from_option(
    profile_option: str | None, user_config: "UserConfig | None" = None
) -> "KeyboardProfile":
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
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Creating profile from option: %s", profile_option)

    # Get effective profile using centralized precedence logic
    effective_profile = get_effective_profile(profile_option, user_config)

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Effective profile: %s", effective_profile)
        logger.debug("Parsing profile format...")

    # Parse profile to get keyboard name and firmware version
    if "/" in effective_profile:
        keyboard_name, firmware_name = effective_profile.split("/", 1)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "  ✓ Keyboard/firmware format: keyboard='%s', firmware='%s'",
                keyboard_name,
                firmware_name,
            )
    else:
        keyboard_name = effective_profile
        firmware_name = None  # Keyboard-only profile
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("  ✓ Keyboard-only format: keyboard='%s'", keyboard_name)

    # Create KeyboardProfile
    try:
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Creating KeyboardProfile...")

        keyboard_profile = create_keyboard_profile(
            keyboard_name, firmware_name, user_config
        )

        if logger.isEnabledFor(logging.DEBUG):
            if firmware_name:
                logger.debug(
                    "  ✓ Created keyboard profile for %s/%s",
                    keyboard_name,
                    firmware_name,
                )
            else:
                logger.debug("  ✓ Created keyboard-only profile for %s", keyboard_name)
        return keyboard_profile
    except Exception as e:
        # Handle profile creation errors with helpful feedback
        console = Console()

        if (
            "not found for keyboard" in str(e) or "not found in keyboard" in str(e)
        ) and firmware_name:
            # Show available firmwares if the firmware wasn't found
            console.print(
                f"[red]❌ Error: Firmware '{firmware_name}' not found for keyboard: {keyboard_name}[/red]"
            )
            try:
                from glovebox.config.keyboard_profile import load_keyboard_config

                config = load_keyboard_config(keyboard_name, user_config)
                firmwares = config.firmwares
                if firmwares:
                    table = Table(
                        title=f"📦 Available Firmwares for {keyboard_name}",
                        show_header=True,
                        header_style="bold green",
                    )
                    table.add_column("Firmware", style="cyan", no_wrap=True)
                    table.add_column("Description", style="white")

                    for fw_name, fw_config in firmwares.items():
                        table.add_row(fw_name, fw_config.description)

                    console.print(table)
                else:
                    console.print(
                        "[yellow]No firmwares available for this keyboard[/yellow]"
                    )
            except Exception:
                pass
        elif "Keyboard configuration not found" in str(e):
            # Keyboard not found error
            console.print(
                f"[red]❌ Error: Keyboard configuration not found: {keyboard_name}[/red]"
            )
            keyboards = get_available_keyboards(user_config)
            if keyboards:
                table = Table(
                    title="⌨️ Available Keyboards",
                    show_header=True,
                    header_style="bold green",
                )
                table.add_column("Keyboard", style="cyan")

                for kb in keyboards:
                    table.add_row(kb)

                console.print(table)
        else:
            # General configuration error
            console.print(
                f"[red]❌ Error: Failed to load keyboard configuration: {e}[/red]"
            )
            keyboards = get_available_keyboards(user_config)
            if keyboards:
                table = Table(
                    title="⌨️ Available Keyboards",
                    show_header=True,
                    header_style="bold green",
                )
                table.add_column("Keyboard", style="cyan")

                for kb in keyboards:
                    table.add_row(kb)

                console.print(table)
        raise typer.Exit(1) from e


def create_profile_from_context(
    ctx: typer.Context | ClickContext, profile_option: str | None
) -> "KeyboardProfile":
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
