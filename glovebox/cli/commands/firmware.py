"""Firmware-related CLI commands."""

import logging
from pathlib import Path
from typing import Annotated, Optional

import typer

from glovebox.cli.decorators import handle_errors, with_profile
from glovebox.cli.helpers import (
    create_profile_from_option,
    print_error_message,
    print_list_item,
    print_success_message,
)
from glovebox.config.profile import KeyboardProfile
from glovebox.models.options import BuildServiceCompileOpts
from glovebox.services import create_build_service, create_flash_service


logger = logging.getLogger(__name__)

# Create a typer app for firmware commands
firmware_app = typer.Typer(
    name="firmware",
    help="Firmware management commands",
    no_args_is_help=True,
)


@firmware_app.command(name="compile")
@handle_errors
def firmware_compile(
    keymap_file: Annotated[Path, typer.Argument(help="Path to keymap (.keymap) file")],
    kconfig_file: Annotated[Path, typer.Argument(help="Path to kconfig (.conf) file")],
    output_dir: Annotated[
        Path, typer.Option("--output-dir", "-o", help="Build output directory")
    ] = Path("build"),
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            "-p",
            help="Profile to use (e.g., 'glove80/v25.05')",
        ),
    ] = None,
    keyboard: Annotated[
        str | None,
        typer.Option("--keyboard", "-k", help="Keyboard name (e.g., 'glove80')"),
    ] = None,
    firmware: Annotated[
        str | None,
        typer.Option("--firmware", "-f", help="Firmware version (e.g., 'v25.05')"),
    ] = None,
    branch: Annotated[str, typer.Option("--branch", help="Git branch to use")] = "main",
    repo: Annotated[
        str, typer.Option("--repo", help="Git repository")
    ] = "moergo-sc/zmk",
    jobs: Annotated[
        int | None, typer.Option("--jobs", "-j", help="Number of parallel jobs")
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Enable verbose build output")
    ] = False,
) -> None:
    """Compile firmware from keymap and config files."""
    # Validate input files
    if not keymap_file.exists():
        raise typer.BadParameter(f"Keymap file not found: {keymap_file}")
    if not kconfig_file.exists():
        raise typer.BadParameter(f"Kconfig file not found: {kconfig_file}")

    # Initialize build configuration
    build_config = BuildServiceCompileOpts(
        **{
            "keymap_path": keymap_file,
            "kconfig_path": kconfig_file,
            "output_dir": output_dir,
            "branch": branch,
            "repo": repo,
            "jobs": jobs,
            "verbose": verbose,
        }
    )

    # Create KeyboardProfile if profile is specified
    keyboard_profile = None
    if profile:
        keyboard_profile = create_profile_from_option(profile)
    elif keyboard and firmware:
        # If no profile but keyboard and firmware are provided, create profile from them
        from glovebox.config.keyboard_config import create_keyboard_profile

        keyboard_profile = create_keyboard_profile(keyboard, firmware)

    # Compile firmware using the build service with profile if available
    build_service = create_build_service()
    result = build_service.compile(build_config, profile=keyboard_profile)

    if result.success:
        print_success_message("Firmware compiled successfully")
        for message in result.messages:
            print_list_item(message)
    else:
        print_error_message("Firmware compilation failed")
        for error in result.errors:
            print_list_item(error)
        raise typer.Exit(1)


@firmware_app.command()
@handle_errors
def flash(
    firmware_file: Annotated[Path, typer.Argument(help="Path to firmware (.uf2) file")],
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            "-p",
            help="Profile to use (e.g., 'glove80/v25.05')",
        ),
    ] = None,
    query: Annotated[
        str, typer.Option("--query", "-q", help="Device query string")
    ] = "vendor=Adafruit and serial~=GLV80-.* and removable=true",
    timeout: Annotated[int, typer.Option("--timeout", help="Timeout in seconds")] = 60,
    count: Annotated[
        int,
        typer.Option(
            "--count", "-n", help="Number of devices to flash (0 for infinite)"
        ),
    ] = 2,
    no_track: Annotated[
        bool, typer.Option("--no-track", help="Disable device tracking")
    ] = False,
) -> None:
    """Flash firmware to keyboard(s)."""
    if not firmware_file.exists():
        raise typer.BadParameter(f"Firmware file not found: {firmware_file}")

    # Create KeyboardProfile if profile is specified
    keyboard_profile = None
    if profile:
        keyboard_profile = create_profile_from_option(profile)

    flash_service = create_flash_service()
    result = flash_service.flash(
        firmware_file=firmware_file,
        profile=keyboard_profile,
        query=query,  # query parameter will override profile's query if provided
        timeout=timeout,
        count=count,
        track_flashed=not no_track,
    )

    if result.success:
        print_success_message(
            f"Successfully flashed {result.devices_flashed} device(s)"
        )
        if result.device_details:
            for device in result.device_details:
                if device["status"] == "success":
                    print_list_item(f"{device['name']}: SUCCESS")
    else:
        print_error_message(f"Flash completed with {result.devices_failed} failure(s)")
        if result.device_details:
            for device in result.device_details:
                if device["status"] == "failed":
                    error_msg = device.get("error", "Unknown error")
                    print_list_item(f"{device['name']}: FAILED - {error_msg}")
        raise typer.Exit(1)


def register_commands(app: typer.Typer) -> None:
    """Register firmware commands with the main app.

    Args:
        app: The main Typer app
    """
    app.add_typer(firmware_app, name="firmware")
