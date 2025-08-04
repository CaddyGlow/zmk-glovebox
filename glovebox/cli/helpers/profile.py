"""Helper functions for working with keyboard profiles in CLI commands."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import typer
from click.core import Context as ClickContext
from rich.console import Console
from rich.table import Table

from glovebox.cli.helpers.output import print_error_message
from glovebox.config.keyboard_profile import (
    create_keyboard_profile,
    get_available_keyboards,
)
from glovebox.config.profile import KeyboardProfile
from glovebox.config.user_config import UserConfig


if TYPE_CHECKING:
    from glovebox.cli.helpers.theme import IconMode


def _get_icon_mode_safe(user_config: UserConfig | None = None) -> "IconMode":
    """Safely get icon mode from user config with fallback to emoji.

    Args:
        user_config: User configuration instance

    Returns:
        IconMode enum value, defaulting to IconMode.EMOJI if config unavailable
    """
    try:
        if user_config is None:
            from glovebox.cli.helpers.theme import IconMode

            return IconMode.EMOJI

        from glovebox.cli.helpers.theme import get_icon_mode_from_config

        return get_icon_mode_from_config(user_config)
    except Exception:
        # Fallback to emoji if anything goes wrong
        from glovebox.cli.helpers.theme import IconMode

        return IconMode.EMOJI


logger = logging.getLogger(__name__)

# Default fallback profile (aligned with user config default)
DEFAULT_PROFILE = "glove80/v25.05"


def get_user_config_from_context(
    ctx: typer.Context | ClickContext,
) -> UserConfig | None:
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


def get_keyboard_profile_from_context_hard(
    ctx: typer.Context | ClickContext,
) -> KeyboardProfile:
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


def get_keyboard_profile_from_context(
    ctx: typer.Context | ClickContext,
) -> KeyboardProfile | None:
    """Get KeyboardProfile from Typer context.

    Args:
        ctx: Typer context

    Returns:
       KeyboardProfile instance or None if not available

    """
    from glovebox.cli.app import AppContext

    app_ctx: AppContext = ctx.obj
    keyboard_profile = app_ctx.keyboard_profile
    return keyboard_profile


def set_keyboard_profile_in_context(
    ctx: typer.Context | ClickContext,
    keyboard_profile: KeyboardProfile,
) -> None:
    """Set KeyboardProfile in Typer context.

    Args:
        ctx: Typer context
        keyboard_profile: KeyboardProfile instance to set
    """
    from glovebox.cli.app import AppContext

    app_ctx: AppContext = ctx.obj
    app_ctx.keyboard_profile = keyboard_profile


def get_keyboard_profile_from_kwargs(**kwargs: Any) -> KeyboardProfile:
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
    return cast(KeyboardProfile, keyboard_profile)


def get_effective_profile(
    profile_option: str | None, user_config: UserConfig | None = None
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
            profile = user_config._config.profile
            return profile
        except AttributeError:
            logger.debug("Config profile not accessible, using fallback")

    # 3. Hardcoded fallback has lowest precedence
    return DEFAULT_PROFILE


def _handle_firmware_not_found_error(
    keyboard_name: str, firmware_name: str, user_config: UserConfig | None
) -> None:
    """Handle firmware not found error with helpful feedback."""
    from glovebox.cli.helpers.theme import Colors, Icons

    icon_mode = _get_icon_mode_safe(user_config)
    console = Console()
    console.print(
        f"[red]{Icons.get_icon('ERROR', icon_mode)} Error: Firmware '{firmware_name}' not found for keyboard: {keyboard_name}[/red]"
    )
    try:
        from glovebox.config.keyboard_profile import load_keyboard_config

        config = load_keyboard_config(keyboard_name, user_config)
        firmwares = config.firmwares
        if firmwares:
            table = Table(
                title=f"{Icons.get_icon('FIRMWARE', icon_mode)} Available Firmwares for {keyboard_name}",
                show_header=True,
                header_style=Colors.HEADER,
            )
            table.add_column("Firmware", style=Colors.PRIMARY, no_wrap=True)
            table.add_column("Description", style=Colors.FIELD_VALUE)

            for fw_name, fw_config in firmwares.items():
                table.add_row(fw_name, fw_config.description)

            console.print(table)
        else:
            console.print("[yellow]No firmwares available for this keyboard[/yellow]")
    except Exception:
        pass


def _handle_keyboard_not_found_error(
    keyboard_name: str, user_config: UserConfig | None
) -> None:
    """Handle keyboard not found error with helpful feedback."""
    from glovebox.cli.helpers.theme import Colors, Icons

    icon_mode = _get_icon_mode_safe(user_config)
    console = Console()
    console.print(
        f"[red]{Icons.get_icon('ERROR', icon_mode)} Error: Keyboard configuration not found: {keyboard_name}[/red]"
    )
    keyboards = get_available_keyboards(user_config)
    if keyboards:
        table = Table(
            title=f"{Icons.get_icon('KEYBOARD', icon_mode)} Available Keyboards",
            show_header=True,
            header_style=Colors.HEADER,
        )
        table.add_column("Keyboard", style=Colors.PRIMARY)

        for kb in keyboards:
            table.add_row(kb)

        console.print(table)


def _handle_general_config_error(
    error_message: str, user_config: UserConfig | None
) -> None:
    """Handle general configuration error with helpful feedback."""
    from glovebox.cli.helpers.theme import Colors, Icons

    icon_mode = _get_icon_mode_safe(user_config)
    console = Console()
    console.print(
        f"[red]{Icons.get_icon('ERROR', icon_mode)} Error: Failed to load keyboard configuration: {error_message}[/red]"
    )
    keyboards = get_available_keyboards(user_config)
    if keyboards:
        table = Table(
            title=f"{Icons.get_icon('KEYBOARD', icon_mode)} Available Keyboards",
            show_header=True,
            header_style=Colors.HEADER,
        )
        table.add_column("Keyboard", style=Colors.PRIMARY)

        for kb in keyboards:
            table.add_row(kb)

        console.print(table)


def create_profile_from_option(
    profile_option: str | None, user_config: UserConfig | None = None
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
        firmware_name = None  # Keyboard-only profile

    # Create KeyboardProfile
    try:
        keyboard_profile = create_keyboard_profile(
            keyboard_name, firmware_name, user_config
        )

        return keyboard_profile

    except Exception as e:
        exc_info = logger.isEnabledFor(logging.DEBUG)
        logger.error(
            "Failed to create profile '%s': %s", effective_profile, e, exc_info=exc_info
        )
        print_error_message(f"Failed to create profile '{effective_profile}': {e}")
        raise typer.Exit(1) from e


def create_profile_from_context(
    ctx: typer.Context | ClickContext, profile_option: str | None
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


def resolve_and_create_profile_unified(
    ctx: typer.Context | ClickContext,
    profile_option: str | None = None,
    default_profile: str | None = None,
    json_file_path: Path | None = None,
    no_auto: bool = False,
) -> KeyboardProfile:
    """Unified profile resolution and creation function.

    This function consolidates all profile handling logic used across
    the CLI, including default resolution, auto-detection, and creation.

    Args:
        ctx: Typer context containing user config
        profile_option: Profile option from CLI parameter (can be None)
        default_profile: Default profile to use if none provided
        json_file_path: JSON file path for auto-detection
        no_auto: Disable auto-detection from JSON file

    Returns:
        KeyboardProfile instance

    Raises:
        typer.Exit: If profile creation fails
    """
    from glovebox.cli.helpers.auto_profile import resolve_profile_with_auto_detection

    # Get user config from context
    user_config = get_user_config_from_context(ctx)

    # If we have a JSON file and auto-detection is enabled, use the unified auto-detection logic
    if json_file_path and not no_auto:
        effective_profile = resolve_profile_with_auto_detection(
            profile_option, json_file_path, no_auto, user_config
        )
    else:
        # Use standard profile resolution
        if profile_option is None:
            # Apply default profile if provided
            profile_option = default_profile

        effective_profile = get_effective_profile(profile_option, user_config)

    # Create the keyboard profile
    keyboard_profile = create_profile_from_option(effective_profile, user_config)

    # Store profile in context for consistency with decorator pattern
    if hasattr(ctx.obj, "__dict__"):
        ctx.obj.keyboard_profile = keyboard_profile

    return keyboard_profile
