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
from glovebox.firmware import create_build_service
from glovebox.firmware.flash import create_flash_service
from glovebox.firmware.options import BuildServiceCompileOpts


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
    branch: Annotated[
        str | None,
        typer.Option("--branch", help="Git branch to use (overrides profile branch)"),
    ] = None,
    repo: Annotated[
        str | None,
        typer.Option("--repo", help="Git repository (overrides profile repo)"),
    ] = None,
    jobs: Annotated[
        int | None, typer.Option("--jobs", "-j", help="Number of parallel jobs")
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Enable verbose build output")
    ] = False,
) -> None:
    """Compile firmware from keymap and config files."""
    # Create KeyboardProfile if profile is specified
    keyboard_profile = None
    if profile:
        keyboard_profile = create_profile_from_option(profile)
    elif keyboard and firmware:
        # If no profile but keyboard and firmware are provided, create profile from them
        from glovebox.config.keyboard_config import create_keyboard_profile

        keyboard_profile = create_keyboard_profile(keyboard, firmware)

    # Use the branch and repo parameters if provided, otherwise use defaults
    branch_value = branch if branch is not None else "main"
    repo_value = repo if repo is not None else "moergo-sc/zmk"

    # Compile firmware using the file-based method with profile if available
    build_service = create_build_service()

    try:
        result = build_service.compile_from_files(
            keymap_file_path=keymap_file,
            kconfig_file_path=kconfig_file,
            output_dir=output_dir,
            profile=keyboard_profile,
            branch=branch_value,
            repo=repo_value,
            jobs=jobs,
            verbose=verbose,
        )

        if result.success:
            print_success_message("Firmware compiled successfully")
            for message in result.messages:
                print_list_item(message)
        else:
            print_error_message("Firmware compilation failed")
            for error in result.errors:
                print_list_item(error)
            raise typer.Exit(1)
    except Exception as e:
        print_error_message(f"Firmware compilation failed: {str(e)}")
        raise typer.Exit(1) from None


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
        str,
        typer.Option(
            "--query", "-q", help="Device query string (overrides profile query)"
        ),
    ] = "",
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
    skip_existing: Annotated[
        bool,
        typer.Option("--skip-existing", help="Skip devices already present at startup"),
    ] = False,
) -> None:
    """Flash firmware to keyboard(s)."""
    # Create KeyboardProfile if profile is specified
    keyboard_profile = None
    if profile:
        keyboard_profile = create_profile_from_option(profile)

    # Get user config to check default skip_existing behavior
    from glovebox.config.user_config import create_user_config

    user_config = create_user_config()

    # Use user config default if skip_existing wasn't explicitly set via CLI
    # Note: typer doesn't provide a way to detect if a flag was explicitly set,
    # so we can't differentiate between --skip-existing=False and not using the flag.
    # For now, we'll use the CLI value as-is, but users can set the default in config.
    effective_skip_existing = skip_existing or user_config.flash_skip_existing

    # Use the new file-based method which handles file existence checks
    flash_service = create_flash_service()
    try:
        result = flash_service.flash_from_file(
            firmware_file_path=firmware_file,
            profile=keyboard_profile,
            query=query,  # query parameter will override profile's query if provided
            timeout=timeout,
            count=count,
            track_flashed=not no_track,
            skip_existing=effective_skip_existing,
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
            print_error_message(
                f"Flash completed with {result.devices_failed} failure(s)"
            )
            if result.device_details:
                for device in result.device_details:
                    if device["status"] == "failed":
                        error_msg = device.get("error", "Unknown error")
                        print_list_item(f"{device['name']}: FAILED - {error_msg}")
            raise typer.Exit(1)
    except Exception as e:
        print_error_message(f"Flash operation failed: {str(e)}")
        raise typer.Exit(1) from None


@firmware_app.command()
@handle_errors
def list_devices(
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
    ] = "",
) -> None:
    """List available devices for flashing."""
    flash_service = create_flash_service()

    try:
        # Use profile-based method if profile is provided
        if profile:
            result = flash_service.list_devices_with_profile(
                profile_name=profile, query=query
            )
        else:
            # Use direct list_devices method if no profile
            result = flash_service.list_devices(
                profile=None, query=query or "removable=true"
            )

        if result.success and result.device_details:
            print_success_message(f"Found {len(result.device_details)} device(s)")
            for device in result.device_details:
                print_list_item(
                    f"{device['name']} - Serial: {device['serial']} - Path: {device['path']}"
                )
        else:
            print_error_message("No devices found matching criteria")
            for message in result.messages:
                print_list_item(message)
    except Exception as e:
        print_error_message(f"Error listing devices: {str(e)}")
        raise typer.Exit(1) from None


def register_commands(app: typer.Typer) -> None:
    """Register firmware commands with the main app.

    Args:
        app: The main Typer app
    """
    app.add_typer(firmware_app, name="firmware")
