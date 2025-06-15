"""Firmware-related CLI commands."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

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
from glovebox.firmware.flash import create_flash_service


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile

logger = logging.getLogger(__name__)


def _format_compilation_output(
    result: Any, output_format: str, output_dir: Path
) -> None:
    """Format and display compilation results."""
    if result.success:
        if output_format.lower() == "json":
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
            print_success_message("Firmware compiled successfully")
            for message in result.messages:
                print_list_item(message)
    else:
        print_error_message("Firmware compilation failed")
        for error in result.errors:
            print_list_item(error)
        raise typer.Exit(1)


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
        Path | None, typer.Option("--output-dir", "-d", help="Build output directory")
    ] = None,
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
        bool | None, typer.Option("--verbose", "-v", help="Enable verbose build output")
    ] = None,
    strategy: Annotated[
        str | None,
        typer.Option(
            "--strategy",
            help="Compilation strategy: auto-detect by profile if not specified",
        ),
    ] = None,
    no_cache: Annotated[
        bool | None,
        typer.Option(
            "--no-cache",
            help="Disable workspace caching for this build",
        ),
    ] = None,
    clear_cache: Annotated[
        bool | None,
        typer.Option(
            "--clear-cache",
            help="Clear cache before starting build",
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
        bool | None,
        typer.Option(
            "--no-docker-user-mapping",
            help="Disable Docker user mapping entirely (overrides all user context settings)",
        ),
    ] = None,
    # Workspace configuration options
    workspace_dir: Annotated[
        Path | None,
        typer.Option("--workspace-dir", help="Custom workspace root directory"),
    ] = None,
    preserve_workspace: Annotated[
        bool | None,
        typer.Option("--preserve-workspace", help="Don't delete workspace after build"),
    ] = None,
    force_cleanup: Annotated[
        bool | None,
        typer.Option("--force-cleanup", help="Force workspace cleanup even on failure"),
    ] = None,
    build_matrix: Annotated[
        Path | None,
        typer.Option(
            "--build-matrix",
            help="Path to build.yaml file (auto-detected if not specified)",
        ),
    ] = None,
    output_format: OutputFormatOption = "text",
) -> None:
    """Build ZMK firmware from keymap and config files.

    Compiles .keymap and .conf files into a flashable .uf2 firmware file
    using Docker and the ZMK build system. Requires Docker to be running.

    Supports multiple compilation strategies:
    - zmk_config: ZMK config repository builds (default, recommended)
    - west: Traditional ZMK west workspace builds

    Examples:
        # Basic ZMK config build (default strategy)
        glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05

        # West workspace build strategy
        glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --strategy west

        # Build without caching for clean build
        glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --no-cache

        # Clear cache before building
        glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --clear-cache

        # Split keyboard build with specific board targets
        glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --board-targets glove80_lh,glove80_rh

        # Manual Docker user context (solves permission issues)
        glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --docker-uid 1000 --docker-gid 1000


        # Verbose output with build details
        glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --verbose
    """
    # Get profile and user config
    keyboard_profile = get_keyboard_profile_from_context(ctx)
    user_config = get_user_config_from_context(ctx)

    logger.info("KeyboardProfile available in context: %r", keyboard_profile)

    # Set default output directory to 'build'
    build_output_dir = Path("build")
    build_output_dir.mkdir(parents=True, exist_ok=True)

    # Determine compilation strategy
    if strategy:
        compilation_strategy = strategy
    # else:
    # Auto-detect strategy based on keyboard name
    # if keyboard_profile.keyboard_name == "glove80":
    #     compilation_strategy = "moergo"
    # else:
    compilation_strategy = "zmk_config"

    logger.info("Using compilation strategy: %s", compilation_strategy)

    # Get the appropriate compile method config from the keyboard profile
    if not keyboard_profile.keyboard_config.compile_methods:
        print_error_message(
            f"No compile methods configured for keyboard '{keyboard_profile.keyboard_name}'"
        )
        raise typer.Exit(1)

    # Find the matching compile method config for our strategy
    compile_config = None
    for method_config in keyboard_profile.keyboard_config.compile_methods:
        if (
            compilation_strategy == "moergo"
            and hasattr(method_config, "docker_image")
            and "moergo" in str(method_config.docker_image).lower()
        ) or (
            compilation_strategy == "zmk_config"
            and hasattr(method_config, "docker_image")
            and "zmk" in str(method_config.docker_image).lower()
        ):
            compile_config = method_config
            break

    # Fallback to first available config if no specific match found
    if compile_config is None:
        compile_config = keyboard_profile.keyboard_config.compile_methods[0]
        logger.info("Using fallback compile config: %r", type(compile_config).__name__)

    try:
        # Import and create compilation service
        from glovebox.compilation import create_compilation_service

        compilation_service = create_compilation_service(compilation_strategy)

        # Execute compilation
        result = compilation_service.compile(
            keymap_file=keymap_file,
            config_file=kconfig_file,
            output_dir=build_output_dir,
            config=compile_config,
            keyboard_profile=keyboard_profile,
        )

        _format_compilation_output(result, output_format, build_output_dir)

    except Exception as e:
        print_error_message(f"Firmware compilation failed: {str(e)}")
        logger.exception("Compilation error details")
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
