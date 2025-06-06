"""Configuration management CLI commands."""

import json
import logging
from pathlib import Path
from typing import Annotated, Any, Optional

import typer

from glovebox.cli.decorators import handle_errors
from glovebox.cli.helpers import (
    print_error_message,
    print_list_item,
    print_success_message,
)
from glovebox.config.keyboard_config import (
    get_available_keyboards,
    load_keyboard_config_raw,
)


logger = logging.getLogger(__name__)

# Create a typer app for configuration commands
config_app = typer.Typer(
    name="config",
    help="Configuration management commands",
    no_args_is_help=True,
)


@config_app.command(name="list")
@handle_errors
def list_keyboards(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed information"
    ),
    format: str = typer.Option(
        "text", "--format", "-f", help="Output format (text, json)"
    ),
) -> None:
    """List available keyboard configurations."""
    keyboards = get_available_keyboards()

    if not keyboards:
        print("No keyboards found")
        return

    if format.lower() == "json":
        # JSON output
        output: dict[str, list[dict[str, Any]]] = {"keyboards": []}
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

        print(json.dumps(output, indent=2))
        return

    # Text output
    if verbose:
        print(f"Available Keyboard Configurations ({len(keyboards)}):")
        print("-" * 60)

        # Get and display detailed information for each keyboard
        for keyboard_name in keyboards:
            try:
                keyboard_config = load_keyboard_config_raw(keyboard_name)
                description = keyboard_config.get("description", "N/A")
                vendor = keyboard_config.get("vendor", "N/A")
                version = keyboard_config.get("version", "N/A")

                print(f"• {keyboard_name}")
                print(f"  Description: {description}")
                print(f"  Vendor: {vendor}")
                print(f"  Version: {version}")
                print("")
            except Exception as e:
                print(f"• {keyboard_name}")
                print(f"  Error: {e}")
                print("")
    else:
        print(f"Available keyboard configurations ({len(keyboards)}):")
        for keyboard in keyboards:
            print_list_item(keyboard)


@config_app.command(name="show")
@handle_errors
def show_keyboard(
    keyboard_name: str = typer.Argument(..., help="Keyboard name to show"),
    format: str = typer.Option(
        "text", "--format", "-f", help="Output format (text, json)"
    ),
) -> None:
    """Show details of a specific keyboard configuration."""
    # Get the keyboard configuration
    keyboard_config = load_keyboard_config_raw(keyboard_name)

    if format.lower() == "json":
        # JSON output
        print(json.dumps(keyboard_config, indent=2))
        return

    # Text output
    print(f"Keyboard: {keyboard_name}")
    print("-" * 60)

    # Display basic information
    description = keyboard_config.get("description", "N/A")
    vendor = keyboard_config.get("vendor", "N/A")
    version = keyboard_config.get("version", "N/A")

    print(f"Description: {description}")
    print(f"Vendor: {vendor}")
    print(f"Version: {version}")

    # Display flash configuration
    flash_config = keyboard_config.get("flash", {})
    if flash_config:
        print("\nFlash Configuration:")
        for key, value in flash_config.items():
            print(f"  {key}: {value}")

    # Display build configuration
    build_config = keyboard_config.get("build", {})
    if build_config:
        print("\nBuild Configuration:")
        for key, value in build_config.items():
            print(f"  {key}: {value}")

    # Display available firmware versions
    firmwares = keyboard_config.get("firmwares", {})
    if firmwares:
        print(f"\nAvailable Firmware Versions ({len(firmwares)}):")
        for name, firmware in firmwares.items():
            version = firmware.get("version", "N/A")
            description = firmware.get("description", "N/A")
            print_list_item(f"{name}: {version} - {description}")


@config_app.command(name="firmwares")
@handle_errors
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
    # Get keyboard configuration
    keyboard_config = load_keyboard_config_raw(keyboard_name)

    # Get firmwares from keyboard config
    firmwares = keyboard_config.get("firmwares", {})

    if not firmwares:
        print(f"No firmwares found for {keyboard_name}")
        return

    if format.lower() == "json":
        # JSON output
        output: dict[str, Any] = {"keyboard": keyboard_name, "firmwares": []}

        for firmware_name, firmware_config in firmwares.items():
            if verbose:
                output["firmwares"].append(
                    {"name": firmware_name, "config": firmware_config}
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
            version = firmware.get("version", "N/A")
            description = firmware.get("description", "N/A")

            print(f"• {firmware_name}")
            print(f"  Version: {version}")
            print(f"  Description: {description}")

            # Show build options if available
            build_options = firmware.get("build_options", {})
            if build_options:
                print("  Build Options:")
                for key, value in build_options.items():
                    print(f"    {key}: {value}")

            print("")
    else:
        print(f"Found {len(firmwares)} firmware(s) for {keyboard_name}:")
        for firmware_name in firmwares:
            print_list_item(firmware_name)


@config_app.command(name="firmware")
@handle_errors
def show_firmware(
    keyboard_name: str = typer.Argument(..., help="Keyboard name"),
    firmware_name: str = typer.Argument(..., help="Firmware name to show"),
    format: str = typer.Option(
        "text", "--format", "-f", help="Output format (text, json)"
    ),
) -> None:
    """Show details of a specific firmware configuration."""
    # Get keyboard configuration
    keyboard_config = load_keyboard_config_raw(keyboard_name)

    # Get firmware configuration
    firmwares = keyboard_config.get("firmwares", {})
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
            "config": firmware_config,
        }
        print(json.dumps(output, indent=2))
        return

    # Text output
    print(f"Firmware: {firmware_name} for {keyboard_name}")
    print("-" * 60)

    # Display basic information
    version = firmware_config.get("version", "N/A")
    description = firmware_config.get("description", "N/A")

    print(f"Version: {version}")
    print(f"Description: {description}")

    # Display build options
    build_options = firmware_config.get("build_options", {})
    if build_options:
        print("\nBuild Options:")
        for key, value in build_options.items():
            print(f"  {key}: {value}")

    # Display kconfig options
    kconfig = firmware_config.get("kconfig", {})
    if kconfig:
        print("\nKconfig Options:")
        for key, config in kconfig.items():
            if isinstance(config, dict):
                name = config.get("name", key)
                type_str = config.get("type", "N/A")
                default = config.get("default", "N/A")
                description = config.get("description", "")

                print(f"  • {name} ({type_str})")
                print(f"    Default: {default}")
                if description:
                    print(f"    Description: {description}")
            else:
                print(f"  • {key}: {config}")


def register_commands(app: typer.Typer) -> None:
    """Register config commands with the main app.

    Args:
        app: The main Typer app
    """
    app.add_typer(config_app, name="config")
