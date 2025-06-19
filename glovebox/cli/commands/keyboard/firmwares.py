"""Keyboard firmware management commands."""

import json
import logging
from typing import Annotated, Any

import typer

from glovebox.cli.app import AppContext
from glovebox.cli.decorators import handle_errors
from glovebox.cli.helpers import (
    print_error_message,
    print_list_item,
    print_success_message,
)
from glovebox.config.keyboard_profile import load_keyboard_config


logger = logging.getLogger(__name__)


def complete_keyboard_names(incomplete: str) -> list[str]:
    """Tab completion for keyboard names."""
    try:
        from glovebox.config import create_user_config
        from glovebox.config.keyboard_profile import get_available_keyboards

        user_config = create_user_config()
        keyboards = get_available_keyboards(user_config)
        return [keyboard for keyboard in keyboards if keyboard.startswith(incomplete)]
    except Exception:
        # If completion fails, return empty list
        return []


def complete_firmware_names(ctx: typer.Context, incomplete: str) -> list[str]:
    """Tab completion for firmware names based on keyboard context."""
    try:
        from glovebox.cli.app import AppContext

        # Try to get keyboard name from command line args
        # This is a bit tricky since we need to parse the current command context
        app_ctx = getattr(ctx, "obj", None)
        if not app_ctx or not isinstance(app_ctx, AppContext):
            return []

        # Get keyboard from command line arguments - this is contextual
        # In practice, we need the keyboard parameter which should be before this
        params = getattr(ctx, "params", {})
        keyboard_name = params.get("keyboard_name")

        if not keyboard_name:
            return []

        keyboard_config = load_keyboard_config(keyboard_name, app_ctx.user_config)

        if not keyboard_config.firmwares:
            return []

        firmwares = list(keyboard_config.firmwares.keys())
        return [firmware for firmware in firmwares if firmware.startswith(incomplete)]
    except Exception:
        # If completion fails, return empty list
        return []


@handle_errors
def list_firmwares(
    ctx: typer.Context,
    keyboard_name: str = typer.Argument(
        ..., help="Keyboard name", autocompletion=complete_keyboard_names
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed information"
    ),
    format: str = typer.Option(
        "text", "--format", "-f", help="Output format (text, json)"
    ),
) -> None:
    """List available firmware configurations for a keyboard."""
    # Get app context with user config
    app_ctx: AppContext = ctx.obj
    # Get keyboard configuration
    keyboard_config = load_keyboard_config(keyboard_name, app_ctx.user_config)

    # Get firmwares from keyboard config
    firmwares = keyboard_config.firmwares

    if not firmwares:
        print(f"No firmwares found for {keyboard_name}")
        return

    if format.lower() == "json":
        # JSON output
        output: dict[str, Any] = {"keyboard": keyboard_name, "firmwares": []}

        for firmware_name, firmware_config in firmwares.items():
            if verbose:
                output["firmwares"].append(
                    {
                        "name": firmware_name,
                        "config": firmware_config.model_dump(
                            mode="json", by_alias=True
                        ),
                    }
                )
            else:
                output["firmwares"].append({"name": firmware_name})

        print(json.dumps(output, indent=2))
        return

    # Text output
    if verbose:
        print(f"Available Firmware Versions for {keyboard_name} ({len(firmwares)}):")
        print("-" * 60)

        for firmware_name, firmware in firmwares.items():
            version = firmware.version
            description = firmware.description

            print(f"• {firmware_name}")
            print(f"  Version: {version}")
            print(f"  Description: {description}")

            # Show build options if available
            build_options = firmware.build_options
            if build_options:
                print("  Build Options:")
                print(f"    repository: {build_options.repository}")
                print(f"    branch: {build_options.branch}")

            print("")
    else:
        print(f"Found {len(firmwares)} firmware(s) for {keyboard_name}:")
        for firmware_name in firmwares:
            print_list_item(firmware_name)


@handle_errors
def show_firmware(
    ctx: typer.Context,
    keyboard_name: str = typer.Argument(
        ..., help="Keyboard name", autocompletion=complete_keyboard_names
    ),
    firmware_name: str = typer.Argument(
        ..., help="Firmware name to show", autocompletion=complete_firmware_names
    ),
    format: str = typer.Option(
        "text", "--format", "-f", help="Output format (text, json)"
    ),
) -> None:
    """Show details of a specific firmware configuration."""
    # Get app context with user config
    app_ctx: AppContext = ctx.obj
    # Get keyboard configuration
    keyboard_config = load_keyboard_config(keyboard_name, app_ctx.user_config)

    # Get firmware configuration
    firmwares = keyboard_config.firmwares
    if firmware_name not in firmwares:
        print_error_message(f"Firmware {firmware_name} not found for {keyboard_name}")
        print("Available firmwares:")
        for name in firmwares:
            print_list_item(name)
        raise typer.Exit(1)

    firmware_config = firmwares[firmware_name]

    if format.lower() == "json":
        # JSON output
        output = {
            "keyboard": keyboard_name,
            "firmware": firmware_name,
            "config": firmware_config.model_dump(mode="json", by_alias=True),
        }
        print(json.dumps(output, indent=2))
        return

    # Text output
    print(f"Firmware: {firmware_name} for {keyboard_name}")
    print("-" * 60)

    # Display basic information
    version = firmware_config.version
    description = firmware_config.description

    print(f"Version: {version}")
    print(f"Description: {description}")

    # Display build options
    build_options = firmware_config.build_options
    if build_options:
        print("\nBuild Options:")
        print(f"  repository: {build_options.repository}")
        print(f"  branch: {build_options.branch}")

    # Display kconfig options
    kconfig = (
        firmware_config.kconfig
        if hasattr(firmware_config, "kconfig") and firmware_config.kconfig is not None
        else {}
    )
    if kconfig:
        print("\nKconfig Options:")
        for _key, config in kconfig.items():
            # config is always a KConfigOption instance
            name = config.name
            type_str = config.type
            default = config.default
            description = config.description

            print(f"  • {name} ({type_str})")
            print(f"    Default: {default}")
            if description:
                print(f"    Description: {description}")
