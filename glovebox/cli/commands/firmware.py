"""Firmware-related CLI commands."""

import logging
from pathlib import Path
from typing import Annotated, Optional

import typer

from glovebox.cli.decorators import handle_errors, with_profile
from glovebox.cli.helpers import (
    print_error_message,
    print_list_item,
    print_success_message,
)
from glovebox.cli.helpers.parameters import ProfileOption
from glovebox.cli.helpers.profile import (
    create_profile_from_context,
    get_user_config_from_context,
)
from glovebox.config.profile import KeyboardProfile
from glovebox.firmware import create_build_service
from glovebox.firmware.flash import create_flash_service
from glovebox.firmware.options import BuildServiceCompileOpts


logger = logging.getLogger(__name__)

# Create a typer app for firmware commands
firmware_app = typer.Typer(
    name="firmware",
    help="""Firmware management commands.

Build ZMK firmware from keymap files using Docker, flash firmware to USB devices,
and manage firmware-related operations.""",
    no_args_is_help=True,
)


@firmware_app.command(name="compile")
@handle_errors
def firmware_compile(
    ctx: typer.Context,
    keymap_file: Annotated[Path, typer.Argument(help="Path to keymap (.keymap) file")],
    kconfig_file: Annotated[Path, typer.Argument(help="Path to kconfig (.conf) file")],
    output_dir: Annotated[
        Path, typer.Option("--output-dir", "-o", help="Build output directory")
    ] = Path("build"),
    profile: ProfileOption = None,
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
    """Build ZMK firmware from keymap and config files.

    Compiles .keymap and .conf files into a flashable .uf2 firmware file
    using Docker and the ZMK build system. Requires Docker to be running.

    Examples:
        glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05
        glovebox firmware compile keymap.keymap config.conf --keyboard glove80 --firmware v25.05
        glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --verbose
    """
    keyboard_profile = create_profile_from_context(ctx, profile)
    _ = get_user_config_from_context(ctx)

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
    ctx: typer.Context,
    firmware_file: Annotated[Path, typer.Argument(help="Path to firmware (.uf2) file")],
    profile: ProfileOption = None,
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
    """Flash firmware file to connected keyboard devices.

    Automatically detects USB keyboards in bootloader mode and flashes
    the firmware file. Supports flashing multiple devices simultaneously.

    Examples:
        glovebox firmware flash firmware.uf2 --profile glove80/v25.05
        glovebox firmware flash firmware.uf2 --count 2 --timeout 120
        glovebox firmware flash firmware.uf2 --query "vendor=Adafruit and serial~=GLV80-.*"
    """

    keyboard_profile = create_profile_from_context(ctx, profile)

    # Get user config from context (already loaded)
    user_config = get_user_config_from_context(ctx)

    # Apply user config defaults for flash parameters
    # CLI values override config values when explicitly provided
    if user_config:
        effective_timeout = (
            timeout if timeout != 60 else user_config._config.firmware.flash.timeout
        )
        effective_count = (
            count if count != 2 else user_config._config.firmware.flash.count
        )
        effective_track_flashed = (
            not no_track
            if no_track
            else user_config._config.firmware.flash.track_flashed
        )
        effective_skip_existing = (
            skip_existing or user_config._config.firmware.flash.skip_existing
        )
    else:
        # Fallback to CLI values if user config not available
        effective_timeout = timeout
        effective_count = count
        effective_track_flashed = not no_track
        effective_skip_existing = skip_existing

    # Use the new file-based method which handles file existence checks
    flash_service = create_flash_service()
    try:
        result = flash_service.flash_from_file(
            firmware_file_path=firmware_file,
            profile=keyboard_profile,
            query=query,  # query parameter will override profile's query if provided
            timeout=effective_timeout,
            count=effective_count,
            track_flashed=effective_track_flashed,
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
    ctx: typer.Context,
    profile: ProfileOption = None,
    query: Annotated[
        str, typer.Option("--query", "-q", help="Device query string")
    ] = "",
) -> None:
    """List available devices for flashing."""
    flash_service = create_flash_service()

    try:
        # Create profile using user config integration
        from glovebox.cli.helpers.profile import (
            get_effective_profile,
            get_user_config_from_context,
        )

        user_config = get_user_config_from_context(ctx)
        effective_profile = get_effective_profile(profile, user_config)

        # Use profile-based method with effective profile
        result = flash_service.list_devices_with_profile(
            profile_name=effective_profile, query=query
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
