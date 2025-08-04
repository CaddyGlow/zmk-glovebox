"""Profile firmware management commands."""

import json
import logging
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from glovebox.cli.app import AppContext
from glovebox.cli.decorators import handle_errors
from glovebox.cli.helpers import (
    print_error_message,
    print_list_item,
)
from glovebox.cli.helpers.theme import Colors, Icons
from glovebox.config.keyboard_profile import load_keyboard_config


logger = logging.getLogger(__name__)


def complete_profile_names(incomplete: str) -> list[str]:
    """Tab completion for profile names."""
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
        profile_name = params.get("profile_name")

        if not profile_name:
            return []

        keyboard_config = load_keyboard_config(profile_name, app_ctx.user_config)

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
    profile_name: str = typer.Argument(
        ..., help="Profile name", autocompletion=complete_profile_names
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed information"
    ),
    format: str = typer.Option(
        "text", "--format", "-f", help="Output format (text, json)"
    ),
) -> None:
    """List available firmware configurations for a profile."""
    # Get app context with user config
    app_ctx: AppContext = ctx.obj
    # Get keyboard configuration
    keyboard_config = load_keyboard_config(profile_name, app_ctx.user_config)

    # Get firmwares from keyboard config
    firmwares = keyboard_config.firmwares

    if not firmwares:
        console = Console()
        error_icon = Icons.get_icon("ERROR", app_ctx.icon_mode)
        console.print(
            f"\n[bold red]{error_icon} No firmwares found for {profile_name}[/bold red]\n"
        )
        return

    if format.lower() == "json":
        # JSON output
        output: dict[str, Any] = {"keyboard": profile_name, "firmwares": []}

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

    # Text output with rich formatting
    console = Console()

    if verbose:
        # Create header panel
        firmware_icon = Icons.get_icon("FIRMWARE", app_ctx.icon_mode)
        header = Text(
            f"Available Firmware Versions for {profile_name} ({len(firmwares)})",
            style=Colors.HEADER,
        )
        console.print(
            Panel(
                header,
                title=f"{firmware_icon} Firmware Configurations",
                border_style=Colors.SECONDARY,
            )
        )
        console.print()

        # Create detailed firmware table
        table = Table(
            title=f"{firmware_icon} Firmware Details",
            show_header=True,
            header_style=Colors.HEADER,
        )
        table.add_column("Firmware", style=Colors.PRIMARY, no_wrap=True)
        table.add_column("Version", style=Colors.SUCCESS)
        table.add_column("Description", style=Colors.FIELD_VALUE)
        table.add_column("Repository", style=Colors.WARNING)
        table.add_column("Branch", style=Colors.ACCENT)

        for firmware_name, firmware in firmwares.items():
            version = firmware.version
            description = firmware.description

            # Get build options if available
            build_options = firmware.build_options
            repository = "N/A"
            branch = "N/A"
            if build_options:
                repository = build_options.repository or "N/A"
                branch = build_options.branch or "N/A"

            table.add_row(firmware_name, version, description, repository, branch)

        console.print(table)
    else:
        # Simple list format with rich styling
        firmware_icon = Icons.get_icon("FIRMWARE", app_ctx.icon_mode)
        console.print(
            f"\n[bold cyan]{firmware_icon} Found {len(firmwares)} firmware(s) for {profile_name}:[/bold cyan]\n"
        )

        for firmware_name in firmwares:
            bullet_icon = Icons.get_icon("BULLET", app_ctx.icon_mode)
            console.print(f"  {bullet_icon} [cyan]{firmware_name}[/cyan]")


@handle_errors
def show_firmware(
    ctx: typer.Context,
    profile_name: str = typer.Argument(
        ..., help="Profile name", autocompletion=complete_profile_names
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
    keyboard_config = load_keyboard_config(profile_name, app_ctx.user_config)

    # Get firmware configuration
    firmwares = keyboard_config.firmwares
    if firmware_name not in firmwares:
        print_error_message(f"Firmware {firmware_name} not found for {profile_name}")
        print("Available firmwares:")
        for name in firmwares:
            print_list_item(name)
        raise typer.Exit(1)

    firmware_config = firmwares[firmware_name]

    if format.lower() == "json":
        # JSON output
        output = {
            "keyboard": profile_name,
            "firmware": firmware_name,
            "config": firmware_config.model_dump(mode="json", by_alias=True),
        }
        print(json.dumps(output, indent=2))
        return

    # Text output with rich formatting
    console = Console()

    # Create header panel
    firmware_icon = Icons.get_icon("FIRMWARE", app_ctx.icon_mode)
    header = Text(f"Firmware: {firmware_name} for {profile_name}", style=Colors.HEADER)
    console.print(
        Panel(
            header,
            title=f"{firmware_icon} Firmware Details",
            border_style=Colors.SECONDARY,
        )
    )
    console.print()

    # Basic information table
    basic_table = Table(
        title=f"{Icons.get_icon('INFO', app_ctx.icon_mode)} Basic Information",
        show_header=True,
        header_style=Colors.HEADER,
    )
    basic_table.add_column("Property", style=Colors.PRIMARY, no_wrap=True)
    basic_table.add_column("Value", style=Colors.FIELD_VALUE)

    # Display basic information
    version = firmware_config.version
    description = firmware_config.description

    basic_table.add_row("Firmware Name", firmware_name)
    basic_table.add_row("Version", version)
    basic_table.add_row("Description", description)
    basic_table.add_row("Keyboard", profile_name)

    console.print(basic_table)
    console.print()

    # Build options table
    build_options = firmware_config.build_options
    if build_options:
        build_table = Table(
            title=f"{Icons.get_icon('BUILD', app_ctx.icon_mode)} Build Options",
            show_header=True,
            header_style=Colors.HEADER,
        )
        build_table.add_column("Option", style=Colors.PRIMARY, no_wrap=True)
        build_table.add_column("Value", style=Colors.FIELD_VALUE)

        build_table.add_row("Repository", build_options.repository or "N/A")
        build_table.add_row("Branch", build_options.branch or "N/A")

        console.print(build_table)
        console.print()

    # Kconfig options table
    kconfig = (
        firmware_config.kconfig
        if hasattr(firmware_config, "kconfig") and firmware_config.kconfig is not None
        else {}
    )
    if kconfig:
        kconfig_table = Table(
            title=f"{Icons.get_icon('CONFIG', app_ctx.icon_mode)} Kconfig Options ({len(kconfig)})",
            show_header=True,
            header_style=Colors.HEADER,
        )
        kconfig_table.add_column("Option", style=Colors.PRIMARY, no_wrap=True)
        kconfig_table.add_column("Type", style=Colors.WARNING)
        kconfig_table.add_column("Default", style=Colors.SUCCESS)
        kconfig_table.add_column("Description", style=Colors.FIELD_VALUE)

        for _key, config in kconfig.items():
            # config is always a KConfigOption instance
            name = config.name
            type_str = config.type
            default = str(config.default)
            description = config.description or "No description"

            kconfig_table.add_row(name, type_str, default, description)

        console.print(kconfig_table)
