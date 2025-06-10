"""Configuration management CLI commands."""

import json
import logging
from pathlib import Path
from typing import Annotated, Any, Optional, cast

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from glovebox.cli.app import AppContext
from glovebox.cli.decorators import handle_errors
from glovebox.cli.helpers import (
    print_error_message,
    print_list_item,
    print_success_message,
)
from glovebox.config.keyboard_profile import (
    get_available_keyboards,
    load_keyboard_config,
)
from glovebox.config.user_config import DEFAULT_CONFIG


logger = logging.getLogger(__name__)

# Create a typer app for configuration commands
config_app = typer.Typer(
    name="config",
    help="Configuration management commands",
    no_args_is_help=True,
)


@config_app.command(name="set")
@handle_errors
def set_config(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Configuration key to set")],
    value: Annotated[str, typer.Argument(help="Value to set")],
    save: Annotated[
        bool, typer.Option("--save", help="Save configuration to file")
    ] = True,
) -> None:
    """Set a configuration value."""
    # Get app context with user config
    app_ctx: AppContext = ctx.obj

    # Define a flattened list of valid keys for both top-level and nested config
    valid_keys = list(DEFAULT_CONFIG.keys())
    valid_keys.extend(
        [
            "firmware.flash.timeout",
            "firmware.flash.count",
            "firmware.flash.track_flashed",
            "firmware.flash.skip_existing",
        ]
    )

    # Check if key is valid
    if key not in valid_keys:
        print_error_message(f"Unknown configuration key: {key}")
        print_error_message(f"Valid keys: {', '.join(sorted(valid_keys))}")
        raise typer.Exit(1)

    # Convert value to appropriate type based on default value
    default_value = DEFAULT_CONFIG[key]

    # Variable to hold the converted value with appropriate type
    typed_value: Any = None

    # Use a dictionary to map types to conversion functions
    # Define the conversion function type
    from collections.abc import Callable

    conversion_map: dict[type, Callable[[str], Any]] = {
        bool: lambda v: v.lower() in ("true", "yes", "1", "y"),
        int: lambda v: int(v),
        list: lambda v: [item.strip() for item in v.split(",")],
    }

    # Get the conversion function or use default string conversion
    converter: Callable[[str], Any] = conversion_map.get(
        type(default_value), lambda v: v
    )
    try:
        typed_value = converter(value)
    except ValueError as err:
        if isinstance(default_value, int):
            print_error_message(f"Invalid integer value: {value}")
            raise typer.Exit(1) from err
        raise

    # Set the value
    app_ctx.user_config.set(key, typed_value)
    print_success_message(f"Set {key} = {typed_value}")

    # Save configuration if requested
    if save:
        app_ctx.user_config.save()
        print_success_message("Configuration saved")


@config_app.command(name="show")
@handle_errors
def show_config(
    ctx: typer.Context,
    show_sources: Annotated[
        bool, typer.Option("--sources", help="Show configuration sources")
    ] = False,
) -> None:
    """Show current configuration settings."""
    # Get app context with user config
    app_ctx: AppContext = ctx.obj

    # Create a nice table display
    console = Console()
    table = Table(title="Glovebox Configuration")

    # Add columns based on what to show
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    if show_sources:
        table.add_column("Source", style="yellow")

    # Add rows for each configuration setting
    for key in sorted(DEFAULT_CONFIG.keys()):
        value = app_ctx.user_config.get(key)

        # Format list values for display
        if isinstance(value, list):
            if not value:
                value_str = "(empty list)"
            else:
                value_str = "\n".join(str(v) for v in value)
        else:
            value_str = str(value)

        if show_sources:
            source = app_ctx.user_config.get_source(key)
            table.add_row(key, value_str, source)
        else:
            table.add_row(key, value_str)

    # Print the table
    console.print(table)


@config_app.command(name="list")
@handle_errors
def list_keyboards(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed information"
    ),
    format: str = typer.Option(
        "text", "--format", "-f", help="Output format (text, json)"
    ),
) -> None:
    """List available keyboard configurations."""
    # Get app context with user config
    app_ctx: AppContext = ctx.obj
    keyboards = get_available_keyboards(app_ctx.user_config)

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
                    typed_config = load_keyboard_config(
                        keyboard_name, app_ctx.user_config
                    )
                    # Convert to dict for JSON serialization
                    keyboard_dict = {
                        "name": typed_config.keyboard,
                        "description": typed_config.description,
                        "vendor": typed_config.vendor,
                        "key_count": typed_config.key_count,
                    }
                    output["keyboards"].append(keyboard_dict)
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
                keyboard_config = load_keyboard_config(
                    keyboard_name, app_ctx.user_config
                )
                description = (
                    keyboard_config.description
                    if hasattr(keyboard_config, "description")
                    else "N/A"
                )
                vendor = (
                    keyboard_config.vendor
                    if hasattr(keyboard_config, "vendor")
                    else "N/A"
                )
                version = (
                    "N/A"  # Version is not a top-level attribute in KeyboardConfig
                )

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


@config_app.command(name="show-keyboard")
@handle_errors
def show_keyboard(
    ctx: typer.Context,
    keyboard_name: str = typer.Argument(..., help="Keyboard name to show"),
    format: str = typer.Option(
        "text", "--format", "-f", help="Output format (text, json)"
    ),
) -> None:
    """Show details of a specific keyboard configuration."""
    # Get app context with user config
    app_ctx: AppContext = ctx.obj
    # Get the keyboard configuration
    keyboard_config = load_keyboard_config(keyboard_name, app_ctx.user_config)

    if format.lower() == "json":
        # Convert the typed object to a dictionary for JSON serialization
        config_dict = {
            "keyboard": keyboard_config.keyboard,
            "description": keyboard_config.description,
            "vendor": keyboard_config.vendor,
            "key_count": keyboard_config.key_count,
            "flash": {
                "method": keyboard_config.flash.method
                if keyboard_config.flash
                else None,
                "query": keyboard_config.flash.query if keyboard_config.flash else None,
                "usb_vid": keyboard_config.flash.usb_vid
                if keyboard_config.flash
                else None,
                "usb_pid": keyboard_config.flash.usb_pid
                if keyboard_config.flash
                else None,
            },
            "build": {
                "method": keyboard_config.build.method
                if keyboard_config.build
                else None,
                "docker_image": keyboard_config.build.docker_image
                if keyboard_config.build
                else None,
                "repository": keyboard_config.build.repository
                if keyboard_config.build
                else None,
                "branch": keyboard_config.build.branch
                if keyboard_config.build
                else None,
            },
            "firmwares": {
                name: {
                    "version": fw.version,
                    "description": fw.description,
                }
                for name, fw in keyboard_config.firmwares.items()
            },
        }
        # JSON output
        print(json.dumps(config_dict, indent=2))
        return

    # Text output
    print(f"Keyboard: {keyboard_name}")
    print("-" * 60)

    # Display basic information
    description = keyboard_config.description
    vendor = keyboard_config.vendor
    version = "N/A"  # Version is not a top-level attribute in KeyboardConfig

    print(f"Description: {description}")
    print(f"Vendor: {vendor}")
    print(f"Version: {version}")

    # Display flash configuration
    flash_config = keyboard_config.flash
    if flash_config:
        print("\nFlash Configuration:")
        print(f"  method: {flash_config.method}")
        print(f"  query: {flash_config.query}")
        print(f"  usb_vid: {flash_config.usb_vid}")
        print(f"  usb_pid: {flash_config.usb_pid}")

    # Display build configuration
    build_config = keyboard_config.build
    if build_config:
        print("\nBuild Configuration:")
        print(f"  method: {build_config.method}")
        print(f"  docker_image: {build_config.docker_image}")
        print(f"  repository: {build_config.repository}")
        print(f"  branch: {build_config.branch}")

    # Display available firmware versions
    firmwares = keyboard_config.firmwares
    if firmwares:
        print(f"\nAvailable Firmware Versions ({len(firmwares)}):")
        for name, firmware in firmwares.items():
            version = firmware.version
            description = firmware.description
            print_list_item(f"{name}: {version} - {description}")


@config_app.command(name="firmwares")
@handle_errors
def list_firmwares(
    ctx: typer.Context,
    keyboard_name: str = typer.Argument(..., help="Keyboard name"),
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


@config_app.command(name="firmware")
@handle_errors
def show_firmware(
    ctx: typer.Context,
    keyboard_name: str = typer.Argument(..., help="Keyboard name"),
    firmware_name: str = typer.Argument(..., help="Firmware name to show"),
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


def register_commands(app: typer.Typer) -> None:
    """Register config commands with the main app.

    Args:
        app: The main Typer app
    """
    app.add_typer(config_app, name="config")
