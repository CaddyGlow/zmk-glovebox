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
from glovebox.cli.helpers.parameters import OutputFormatOption, ProfileOption
from glovebox.cli.helpers.profile import (
    get_keyboard_profile_from_context,
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

Build ZMK firmware from keymap files using Docker with multiple build strategies,
flash firmware to USB devices, and manage firmware-related operations.

Supports modern ZMK west workspace builds (recommended) as well as traditional
cmake, make, and ninja build systems for custom keyboards.""",
    no_args_is_help=True,
)


@firmware_app.command(name="compile")
@handle_errors
@with_profile()
def firmware_compile(
    ctx: typer.Context,
    keymap_file: Annotated[Path, typer.Argument(help="Path to keymap (.keymap) file")],
    kconfig_file: Annotated[Path, typer.Argument(help="Path to kconfig (.conf) file")],
    output_dir: Annotated[
        Path, typer.Option("--output-dir", "-d", help="Build output directory")
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
    build_strategy: Annotated[
        str | None,
        typer.Option(
            "--build-strategy",
            help="Build strategy: west (ZMK), cmake, make, ninja, custom (overrides profile strategy)",
        ),
    ] = None,
    cache_workspace: Annotated[
        bool | None,
        typer.Option(
            "--cache-workspace/--no-cache-workspace",
            help="Enable/disable workspace caching for faster builds (overrides profile setting)",
        ),
    ] = None,
    board_targets: Annotated[
        str | None,
        typer.Option(
            "--board-targets",
            help="Comma-separated board targets for split keyboards (e.g., 'glove80_lh,glove80_rh')",
        ),
    ] = None,
    # Docker user context override options
    docker_uid: Annotated[
        int | None,
        typer.Option(
            "--docker-uid",
            help="Manual Docker UID override (takes precedence over auto-detection and config)",
            min=0,
        ),
    ] = None,
    docker_gid: Annotated[
        int | None,
        typer.Option(
            "--docker-gid",
            help="Manual Docker GID override (takes precedence over auto-detection and config)",
            min=0,
        ),
    ] = None,
    docker_username: Annotated[
        str | None,
        typer.Option(
            "--docker-username",
            help="Manual Docker username override (takes precedence over auto-detection and config)",
        ),
    ] = None,
    docker_home: Annotated[
        str | None,
        typer.Option(
            "--docker-home",
            help="Custom Docker home directory override (host path to map as container home)",
        ),
    ] = None,
    docker_container_home: Annotated[
        str | None,
        typer.Option(
            "--docker-container-home",
            help="Custom container home directory path (default: /tmp)",
        ),
    ] = None,
    no_docker_user_mapping: Annotated[
        bool,
        typer.Option(
            "--no-docker-user-mapping",
            help="Disable Docker user mapping entirely (overrides all user context settings)",
        ),
    ] = False,
    output_format: OutputFormatOption = "text",
) -> None:
    """Build ZMK firmware from keymap and config files.

    Compiles .keymap and .conf files into a flashable .uf2 firmware file
    using Docker and the ZMK build system. Requires Docker to be running.

    Supports multiple build strategies:
    - west: ZMK west workspace builds (default, recommended)
    - cmake: Direct CMake builds
    - make: Traditional make builds
    - ninja: Ninja build system
    - custom: Custom build commands

    Examples:
        # Basic ZMK west workspace build (recommended)
        glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05

        # ZMK build with caching for faster subsequent builds
        glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --cache-workspace

        # Split keyboard build with specific board targets
        glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --board-targets glove80_lh,glove80_rh

        # Manual Docker user context (solves permission issues)
        glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --docker-uid 1000 --docker-gid 1000

        # Custom Docker home directory (instead of /tmp)
        glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --docker-home /home/builder

        # Full manual Docker user context
        glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 \\
            --docker-uid 1000 --docker-gid 1000 --docker-username builder --docker-home /workspace

        # Disable Docker user mapping entirely
        glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --no-docker-user-mapping

        # CMake build strategy (for custom builds)
        glovebox firmware compile keymap.keymap config.conf --profile custom/board --build-strategy cmake

        # Verbose output with build details
        glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --verbose
    """
    keyboard_profile = get_keyboard_profile_from_context(ctx)
    user_config = get_user_config_from_context(ctx)

    # Use the branch and repo parameters if provided, otherwise use defaults
    branch_value = branch if branch is not None else "main"
    repo_value = repo if repo is not None else "moergo-sc/zmk"

    # Parse board targets if provided
    board_targets_list = None
    if board_targets:
        board_targets_list = [target.strip() for target in board_targets.split(",")]

    # Collect Docker user context overrides from CLI
    docker_overrides: dict[str, str | int | None] = {}
    if docker_uid is not None:
        docker_overrides["manual_uid"] = docker_uid
    if docker_gid is not None:
        docker_overrides["manual_gid"] = docker_gid
    if docker_username is not None:
        docker_overrides["manual_username"] = docker_username
    if docker_home is not None:
        docker_overrides["host_home_dir"] = docker_home
    if docker_container_home is not None:
        docker_overrides["container_home_dir"] = docker_container_home
    if no_docker_user_mapping:
        docker_overrides["enable_user_mapping"] = False

    # Compile firmware using the file-based method with Docker overrides
    build_service = create_build_service()

    try:
        result = build_service.compile_from_files(
            keymap_file_path=keymap_file,
            kconfig_file_path=kconfig_file,
            output_dir=output_dir,
            keyboard_profile=keyboard_profile,
            branch=branch_value,
            repo=repo_value,
            jobs=jobs,
            verbose=verbose,
            docker_user_overrides=docker_overrides,
        )

        if result.success:
            if output_format.lower() == "json":
                # JSON output for automation
                result_data = {
                    "success": True,
                    "message": "Firmware compiled successfully",
                    "messages": result.messages,
                    "output_dir": str(output_dir),
                }
                from glovebox.cli.helpers.output_formatter import OutputFormatter

                formatter = OutputFormatter()
                print(formatter.format(result_data, "json"))
            else:
                # Rich text output (default)
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
@with_profile()
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
    wait: Annotated[
        bool | None,
        typer.Option(
            "--wait/--no-wait",
            help="Wait for devices to connect before flashing (uses config default if not specified)",
        ),
    ] = None,
    poll_interval: Annotated[
        float | None,
        typer.Option(
            "--poll-interval",
            help="Polling interval in seconds when waiting for devices (uses config default if not specified)",
            min=0.1,
            max=5.0,
        ),
    ] = None,
    show_progress: Annotated[
        bool | None,
        typer.Option(
            "--show-progress/--no-show-progress",
            help="Show real-time device detection progress (uses config default if not specified)",
        ),
    ] = None,
    output_format: OutputFormatOption = "text",
) -> None:
    """Flash firmware file to connected keyboard devices.

    Automatically detects USB keyboards in bootloader mode and flashes
    the firmware file. Supports flashing multiple devices simultaneously.

    Wait mode uses real-time USB device monitoring for immediate detection
    when devices are connected. Configure defaults in user config file.

    Examples:
        # Basic flash (uses config defaults)
        glovebox firmware flash firmware.uf2 --profile glove80/v25.05

        # Enable wait mode with CLI flags
        glovebox firmware flash firmware.uf2 --wait --timeout 120

        # Configure multiple devices with custom polling
        glovebox firmware flash firmware.uf2 --wait --count 2 --poll-interval 1.0

        # Use specific device query
        glovebox firmware flash firmware.uf2 --query "vendor=Adafruit and serial~=GLV80-.*"

    Configuration:
        Set defaults in ~/.config/glovebox/config.yaml:
            firmware:
              flash:
                wait: true
                timeout: 120
                poll_interval: 0.5
                show_progress: true
    """

    keyboard_profile = get_keyboard_profile_from_context(ctx)

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

        # NEW: Wait-related settings with precedence
        effective_wait = (
            wait if wait is not None else user_config._config.firmware.flash.wait
        )
        effective_poll_interval = (
            poll_interval
            if poll_interval is not None
            else user_config._config.firmware.flash.poll_interval
        )
        effective_show_progress = (
            show_progress
            if show_progress is not None
            else user_config._config.firmware.flash.show_progress
        )
    else:
        # Fallback to CLI values if user config not available
        effective_timeout = timeout
        effective_count = count
        effective_track_flashed = not no_track
        effective_skip_existing = skip_existing
        effective_wait = wait if wait is not None else False
        effective_poll_interval = poll_interval if poll_interval is not None else 0.5
        effective_show_progress = show_progress if show_progress is not None else True

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
            # NEW: Add wait parameters
            wait=effective_wait,
            poll_interval=effective_poll_interval,
            show_progress=effective_show_progress,
        )

        if result.success:
            if output_format.lower() == "json":
                # JSON output for automation
                result_data = {
                    "success": True,
                    "devices_flashed": result.devices_flashed,
                    "device_details": result.device_details,
                }
                from glovebox.cli.helpers.output_formatter import OutputFormatter

                formatter = OutputFormatter()
                print(formatter.format(result_data, "json"))
            else:
                # Rich text output (default)
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
@with_profile()
def list_devices(
    ctx: typer.Context,
    profile: ProfileOption = None,
    query: Annotated[
        str, typer.Option("--query", "-q", help="Device query string")
    ] = "",
    output_format: OutputFormatOption = "text",
) -> None:
    """List available devices for flashing."""
    flash_service = create_flash_service()

    try:
        # Get the keyboard profile from context
        keyboard_profile = get_keyboard_profile_from_context(ctx)

        # Use profile-based method with keyboard profile
        result = flash_service.list_devices(
            profile=keyboard_profile,
            query=query,
        )

        if result.success and result.device_details:
            if output_format.lower() == "json":
                # JSON output for automation
                result_data = {
                    "success": True,
                    "device_count": len(result.device_details),
                    "devices": result.device_details,
                }
                from glovebox.cli.helpers.output_formatter import OutputFormatter

                formatter = OutputFormatter()
                print(formatter.format(result_data, "json"))
            elif output_format.lower() == "table":
                # Enhanced table output using DeviceListFormatter
                from glovebox.cli.helpers.output_formatter import DeviceListFormatter

                formatter = DeviceListFormatter()
                formatter.format_device_list(result.device_details, "table")
            else:
                # Text output (default)
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
