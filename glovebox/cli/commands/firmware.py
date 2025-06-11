"""Firmware-related CLI commands."""

import logging
from pathlib import Path
from typing import Annotated

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
from glovebox.compilation import create_compilation_service
from glovebox.config.compile_methods import (
    CacheConfig,
    CompilationConfig,
    DockerUserConfig,
)
from glovebox.firmware.flash import create_flash_service


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
    strategy: Annotated[
        str,
        typer.Option(
            "--strategy",
            help="Compilation strategy: zmk_config (default), west, cmake, make, ninja, custom",
        ),
    ] = "zmk_config",
    no_cache: Annotated[
        bool,
        typer.Option(
            "--no-cache",
            help="Disable workspace caching for this build",
        ),
    ] = False,
    clear_cache: Annotated[
        bool,
        typer.Option(
            "--clear-cache",
            help="Clear cache before starting build",
        ),
    ] = False,
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

    Supports multiple compilation strategies:
    - zmk_config: ZMK config repository builds (default, recommended)
    - west: Traditional ZMK west workspace builds
    - cmake: Direct CMake builds
    - make: Traditional make builds
    - ninja: Ninja build system
    - custom: Custom build commands

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

        # CMake build strategy (for custom builds)
        glovebox firmware compile keymap.keymap config.conf --profile custom/board --strategy cmake

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

    # Create unified compilation configuration
    cache_config = CacheConfig(enabled=not no_cache)

    # Create DockerUserConfig with proper field mapping
    docker_user_config = DockerUserConfig()
    if docker_overrides:
        # Map CLI parameters to DockerUserConfig fields with type checking
        if "manual_uid" in docker_overrides and isinstance(
            docker_overrides["manual_uid"], int
        ):
            docker_user_config.manual_uid = docker_overrides["manual_uid"]
        if "manual_gid" in docker_overrides and isinstance(
            docker_overrides["manual_gid"], int
        ):
            docker_user_config.manual_gid = docker_overrides["manual_gid"]
        if "manual_username" in docker_overrides and isinstance(
            docker_overrides["manual_username"], str
        ):
            docker_user_config.manual_username = docker_overrides["manual_username"]
        if "host_home_dir" in docker_overrides and isinstance(
            docker_overrides["host_home_dir"], str
        ):
            docker_user_config.host_home_dir = Path(docker_overrides["host_home_dir"])
        if "container_home_dir" in docker_overrides and isinstance(
            docker_overrides["container_home_dir"], str
        ):
            docker_user_config.container_home_dir = docker_overrides[
                "container_home_dir"
            ]
        if "enable_user_mapping" in docker_overrides and isinstance(
            docker_overrides["enable_user_mapping"], bool
        ):
            docker_user_config.enable_user_mapping = docker_overrides[
                "enable_user_mapping"
            ]

    # Extract Docker image from keyboard profile configuration
    image_value = "moergo-zmk-build:latest"  # Default fallback
    if keyboard_profile and keyboard_profile.keyboard_config:
        # Find the compile method that matches the strategy
        for compile_method in keyboard_profile.keyboard_config.compile_methods:
            if compile_method.strategy == strategy:
                if hasattr(compile_method, "image") and compile_method.image:
                    image_value = compile_method.image
                    break

    config = CompilationConfig(
        strategy=strategy,  # type: ignore[arg-type]
        image=image_value,
        repository=repo_value,
        branch=branch_value,
        jobs=jobs,
        board_targets=board_targets_list or [],
        cache=cache_config,
        docker_user=docker_user_config,
    )

    # Clear cache if requested
    if clear_cache:
        # TODO: Implement cache clearing in Phase 7
        logger.info("Cache clearing requested (will be implemented in Phase 7)")

    # Create compilation service for the specified strategy
    compilation_service = create_compilation_service(strategy)

    try:
        result = compilation_service.compile(
            keymap_file=keymap_file,
            config_file=kconfig_file,
            output_dir=output_dir,
            config=config,
            keyboard_profile=keyboard_profile,
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
