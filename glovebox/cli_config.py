"""CLI commands for configuration management."""

import json
from pathlib import Path
from typing import Optional

import typer

from glovebox.config.keyboard_config import (
    get_available_keyboards,
    load_keyboard_config_raw,
)
from glovebox.core.errors import ConfigError


# Create a typer app for configuration commands
config_app = typer.Typer(
    name="config",
    help="Configuration management commands",
    no_args_is_help=True,
)


@config_app.command(name="list")
def list_keyboards(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed information"
    ),
    format: str = typer.Option(
        "text", "--format", "-f", help="Output format (text, json)"
    ),
) -> None:
    """List available keyboard configurations."""
    try:
        keyboards = get_available_keyboards()

        if not keyboards:
            typer.echo("No keyboards found")
            return

        if format.lower() == "json":
            # JSON output
            output = {"keyboards": []}
            for keyboard_name in keyboards:
                # Get detailed information if verbose
                if verbose:
                    try:
                        keyboard_config = load_keyboard_config_raw(keyboard_name)
                        output["keyboards"].append(keyboard_config)
                    except Exception:
                        output["keyboards"].append({"name": keyboard_name})
                else:
                    output["keyboards"].append({"name": keyboard_name})

            typer.echo(json.dumps(output, indent=2))
            return

        # Text output
        if verbose:
            typer.echo(f"Available Keyboard Configurations ({len(keyboards)}):")
            typer.echo("-" * 60)

            # Get and display detailed information for each keyboard
            for keyboard_name in keyboards:
                try:
                    keyboard_config = load_keyboard_config_raw(keyboard_name)
                    description = keyboard_config.get("description", "N/A")
                    vendor = keyboard_config.get("vendor", "N/A")
                    version = keyboard_config.get("version", "N/A")

                    typer.echo(f"• {keyboard_name}")
                    typer.echo(f"  Description: {description}")
                    typer.echo(f"  Vendor: {vendor}")
                    typer.echo(f"  Version: {version}")
                    typer.echo("")
                except Exception as e:
                    typer.echo(f"• {keyboard_name}")
                    typer.echo(f"  Error: {e}")
                    typer.echo("")
        else:
            typer.echo(f"Available keyboard configurations ({len(keyboards)}):")
            for keyboard in keyboards:
                typer.echo(f"  • {keyboard}")
    except Exception as e:
        typer.echo(f"Error listing keyboards: {e}")
        raise typer.Exit(1) from e


@config_app.command(name="show")
def show_keyboard(
    keyboard_name: str = typer.Argument(..., help="Keyboard name to show"),
    format: str = typer.Option(
        "text", "--format", "-f", help="Output format (text, json)"
    ),
) -> None:
    """Show details of a specific keyboard configuration."""
    try:
        # Get the keyboard configuration
        keyboard_config = load_keyboard_config_raw(keyboard_name)

        if format.lower() == "json":
            # JSON output
            typer.echo(json.dumps(keyboard_config, indent=2))
            return

        # Text output
        typer.echo(f"Keyboard: {keyboard_name}")
        typer.echo("-" * 60)

        # Display basic information
        description = keyboard_config.get("description", "N/A")
        vendor = keyboard_config.get("vendor", "N/A")
        version = keyboard_config.get("version", "N/A")

        typer.echo(f"Description: {description}")
        typer.echo(f"Vendor: {vendor}")
        typer.echo(f"Version: {version}")

        # Display flash configuration
        flash_config = keyboard_config.get("flash", {})
        if flash_config:
            typer.echo("\nFlash Configuration:")
            for key, value in flash_config.items():
                typer.echo(f"  {key}: {value}")

        # Display build configuration
        build_config = keyboard_config.get("build", {})
        if build_config:
            typer.echo("\nBuild Configuration:")
            for key, value in build_config.items():
                typer.echo(f"  {key}: {value}")

        # Display available firmware versions
        firmwares = keyboard_config.get("firmwares", {})
        if firmwares:
            typer.echo(f"\nAvailable Firmware Versions ({len(firmwares)}):")
            for name, firmware in firmwares.items():
                version = firmware.get("version", "N/A")
                description = firmware.get("description", "N/A")
                typer.echo(f"  • {name}: {version} - {description}")

    except Exception as e:
        typer.echo(f"Error: Keyboard not found: {keyboard_name} - {e}")
        keyboards = get_available_keyboards()
        typer.echo("Available keyboards:")
        for keyboard in keyboards:
            typer.echo(f"  • {keyboard}")
        raise typer.Exit(1) from e


@config_app.command(name="firmwares")
def list_firmwares(
    keyboard_name: str = typer.Argument(..., help="Keyboard name"),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed information"
    ),
    format: str = typer.Option(
        "text", "--format", "-f", help="Output format (text, json)"
    ),
) -> None:
    """List available firmware configurations for a keyboard."""
    try:
        # Get keyboard configuration
        keyboard_config = load_keyboard_config_raw(keyboard_name)

        # Get firmwares from keyboard config
        firmwares = keyboard_config.get("firmwares", {})

        if not firmwares:
            typer.echo(f"No firmwares found for {keyboard_name}")
            return

        if format.lower() == "json":
            # JSON output
            output = {"keyboard": keyboard_name, "firmwares": []}

            for firmware_name, firmware_config in firmwares.items():
                if verbose:
                    output["firmwares"].append(
                        {"name": firmware_name, "config": firmware_config}
                    )
                else:
                    output["firmwares"].append({"name": firmware_name})

            typer.echo(json.dumps(output, indent=2))
            return

        # Text output
        if verbose:
            typer.echo(
                f"Available Firmware Versions for {keyboard_name} ({len(firmwares)}):"
            )
            typer.echo("-" * 60)

            for firmware_name, firmware in firmwares.items():
                version = firmware.get("version", "N/A")
                description = firmware.get("description", "N/A")

                typer.echo(f"• {firmware_name}")
                typer.echo(f"  Version: {version}")
                typer.echo(f"  Description: {description}")

                # Show build options if available
                build_options = firmware.get("build_options", {})
                if build_options:
                    typer.echo("  Build Options:")
                    for key, value in build_options.items():
                        typer.echo(f"    {key}: {value}")

                typer.echo("")
        else:
            typer.echo(f"Found {len(firmwares)} firmware(s) for {keyboard_name}:")
            for firmware_name in firmwares:
                typer.echo(f"  • {firmware_name}")

    except Exception as e:
        typer.echo(f"Error listing firmwares for {keyboard_name}: {e}")
        raise typer.Exit(1) from e


@config_app.command(name="firmware")
def show_firmware(
    keyboard_name: str = typer.Argument(..., help="Keyboard name"),
    firmware_name: str = typer.Argument(..., help="Firmware name to show"),
    format: str = typer.Option(
        "text", "--format", "-f", help="Output format (text, json)"
    ),
) -> None:
    """Show details of a specific firmware configuration."""
    try:
        # Get keyboard configuration
        keyboard_config = load_keyboard_config_raw(keyboard_name)

        # Get firmware configuration
        firmwares = keyboard_config.get("firmwares", {})
        if firmware_name not in firmwares:
            typer.echo(f"Error: Firmware {firmware_name} not found for {keyboard_name}")
            typer.echo("Available firmwares:")
            for name in firmwares:
                typer.echo(f"  • {name}")
            raise typer.Exit(1)

        firmware_config = firmwares[firmware_name]

        if format.lower() == "json":
            # JSON output
            output = {
                "keyboard": keyboard_name,
                "firmware": firmware_name,
                "config": firmware_config,
            }
            typer.echo(json.dumps(output, indent=2))
            return

        # Text output
        typer.echo(f"Firmware: {firmware_name} for {keyboard_name}")
        typer.echo("-" * 60)

        # Display basic information
        version = firmware_config.get("version", "N/A")
        description = firmware_config.get("description", "N/A")

        typer.echo(f"Version: {version}")
        typer.echo(f"Description: {description}")

        # Display build options
        build_options = firmware_config.get("build_options", {})
        if build_options:
            typer.echo("\nBuild Options:")
            for key, value in build_options.items():
                typer.echo(f"  {key}: {value}")

        # Display kconfig options
        kconfig = firmware_config.get("kconfig", {})
        if kconfig:
            typer.echo("\nKconfig Options:")
            for key, config in kconfig.items():
                if isinstance(config, dict):
                    name = config.get("name", key)
                    type_str = config.get("type", "N/A")
                    default = config.get("default", "N/A")
                    description = config.get("description", "")

                    typer.echo(f"  • {name} ({type_str})")
                    typer.echo(f"    Default: {default}")
                    if description:
                        typer.echo(f"    Description: {description}")
                else:
                    typer.echo(f"  • {key}: {config}")

    except Exception as e:
        typer.echo(f"Error: {e}")
        raise typer.Exit(1) from e


# Since the user config functionality is not part of the new system yet,
# we'll provide simplified placeholder commands that inform users about
# the migration in progress


@config_app.command(name="user")
def show_user_config() -> None:
    """Show user configuration."""
    typer.echo("User configuration system is being migrated to the new format.")
    typer.echo("This functionality is not yet available in the current version.")
    typer.echo("Please use keyboard configurations instead.")
    typer.echo("\nAvailable commands:")
    typer.echo("  glovebox config list       - List available keyboard configurations")
    typer.echo(
        "  glovebox config show NAME  - Show details of a keyboard configuration"
    )


@config_app.command(name="update")
def update_user_config() -> None:
    """Update user configuration."""
    typer.echo("User configuration update is being migrated to the new format.")
    typer.echo("This functionality is not yet available in the current version.")
    typer.echo("Please use keyboard configurations instead.")
    typer.echo("\nAvailable commands:")
    typer.echo("  glovebox config list       - List available keyboard configurations")
    typer.echo(
        "  glovebox config show NAME  - Show details of a keyboard configuration"
    )
