"""Firmware-related CLI commands."""

import logging
from dataclasses import dataclass
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
from glovebox.compilation import create_compilation_service
from glovebox.compilation.models.build_matrix import BuildYamlConfig
from glovebox.config.compile_methods import (
    CacheConfig,
    DockerUserConfig,
    MoergoCompilationConfig,
    ZmkCompilationConfig,
)
from glovebox.firmware.flash import create_flash_service


if TYPE_CHECKING:
    from glovebox.config.keyboard_profile import KeyboardProfile
logger = logging.getLogger(__name__)


@dataclass
class FirmwareCompileParams:
    """Container for firmware compile parameters."""

    keymap_file: Path
    kconfig_file: Path
    output_dir: Path
    strategy: str
    branch: str | None
    repo: str | None
    jobs: int | None
    verbose: bool
    no_cache: bool
    clear_cache: bool
    board_targets: str | None

    # Docker overrides
    docker_uid: int | None
    docker_gid: int | None
    docker_username: str | None
    docker_home: str | None
    docker_container_home: str | None
    no_docker_user_mapping: bool

    # Workspace options
    workspace_dir: Path | None
    preserve_workspace: bool
    force_cleanup: bool
    build_matrix: Path | None
    output_format: str


def _build_docker_user_config(
    params: FirmwareCompileParams, strategy: str
) -> DockerUserConfig:
    """Build Docker user configuration from CLI parameters."""
    # Start with strategy-specific defaults
    if strategy == "moergo":
        # Use MoergoCompilationConfig defaults
        docker_user_config = DockerUserConfig(enable_user_mapping=False)
        logger.debug(
            "Using MoergoCompilationConfig docker_user defaults: enable_user_mapping=False"
        )
    else:
        # Use standard defaults for other strategies
        docker_user_config = DockerUserConfig()
        logger.debug(
            "Using standard DockerUserConfig defaults: enable_user_mapping=True"
        )

    # Override with CLI parameters if provided
    if params.docker_uid is not None:
        docker_user_config.manual_uid = params.docker_uid
        logger.debug("CLI override: manual_uid=%s", params.docker_uid)
    if params.docker_gid is not None:
        docker_user_config.manual_gid = params.docker_gid
        logger.debug("CLI override: manual_gid=%s", params.docker_gid)
    if params.docker_username is not None:
        docker_user_config.manual_username = params.docker_username
        logger.debug("CLI override: manual_username=%s", params.docker_username)
    if params.docker_home is not None:
        docker_user_config.host_home_dir = Path(params.docker_home)
        logger.debug("CLI override: host_home_dir=%s", params.docker_home)
    if params.docker_container_home is not None:
        docker_user_config.container_home_dir = params.docker_container_home
        logger.debug(
            "CLI override: container_home_dir=%s", params.docker_container_home
        )
    if params.no_docker_user_mapping:
        docker_user_config.enable_user_mapping = False
        logger.debug(
            "CLI override: enable_user_mapping=False (--no-docker-user-mapping)"
        )

    logger.debug("Final docker_user_config: %r", docker_user_config)
    return docker_user_config


def _extract_docker_image(keyboard_profile: Any, strategy: str) -> str:
    """Extract Docker image from keyboard profile configuration."""
    image_value = "zmkfirmware/zmk-build-arm:stable"  # Default fallback

    if keyboard_profile and keyboard_profile.keyboard_config:
        for compile_method in keyboard_profile.keyboard_config.compile_methods:
            # Check by strategy attribute if available
            method_identifier = getattr(
                compile_method, "strategy", getattr(compile_method, "method_type", None)
            )

            # For MoergoCompilationConfig, check by type since it doesn't have strategy attribute
            is_moergo_method = hasattr(compile_method, "repository") and hasattr(
                compile_method, "branch"
            )

            method_matches = method_identifier == strategy or (
                strategy == "moergo" and is_moergo_method
            )

            if (
                method_matches
                and hasattr(compile_method, "image")
                and compile_method.image
            ):
                image_value = compile_method.image
                break

    return image_value


def _build_compilation_config(
    params: FirmwareCompileParams, keyboard_profile: "KeyboardProfile"
) -> ZmkCompilationConfig | MoergoCompilationConfig:
    """Build compilation configuration from parameters and profile."""
    # Find matching compile method from profile
    profile_compile_method = None
    if keyboard_profile and keyboard_profile.keyboard_config:
        for compile_method in keyboard_profile.keyboard_config.compile_methods:
            profile_compile_method = compile_method
            logger.debug("Found matching compile method in profile: %r", compile_method)
            break

    # logger.debug("Compile method from profile: %r", keyboard_profile.keyboard_config)
    logger.debug("Compile method from profile: %r", profile_compile_method)
    # Start with profile config if found, otherwise use defaults
    if profile_compile_method and params.strategy == "moergo":
        # Start with the profile's MoergoCompilationConfig
        if isinstance(profile_compile_method, MoergoCompilationConfig):
            config = profile_compile_method.model_copy()
            logger.debug("Using profile MoergoCompilationConfig as base")
        else:
            # Create from profile attributes, preserving all available fields
            config_dict = {
                "image": getattr(
                    profile_compile_method, "image", "glove80-zmk-config-docker"
                ),
                "repository": getattr(
                    profile_compile_method, "repository", "moergo-sc/zmk"
                ),
                "branch": getattr(profile_compile_method, "branch", "v25.05"),
            }

            # Copy all profile attributes that exist in MoergoCompilationConfig
            for field in [
                "jobs",
                "build_commands",
                "environment_template",
                "volume_templates",
                "workspace_path",
                "entrypoint_command",
            ]:
                if hasattr(profile_compile_method, field):
                    config_dict[field] = getattr(profile_compile_method, field)
                    logger.debug(
                        "Copied profile field: %s=%r", field, config_dict[field]
                    )

            config = MoergoCompilationConfig(**config_dict)
            logger.debug("Created MoergoCompilationConfig from profile attributes")
    elif profile_compile_method and params.strategy != "moergo":
        # Start with the profile's ZmkCompilationConfig
        if isinstance(profile_compile_method, ZmkCompilationConfig):
            config = profile_compile_method.model_copy()
            logger.debug("Using profile ZmkCompilationConfig as base")
        else:
            # Create from profile attributes, preserving all available fields
            config_dict = {
                "image": getattr(
                    profile_compile_method, "image", "zmkfirmware/zmk-build-arm:stable"
                ),
                "artifact_naming": "zmk_github_actions",
            }

            # Copy all profile attributes that exist in ZmkCompilationConfig
            for field in [
                "repository",
                "branch",
                "build_config",
                "cache",
                "workspace",
                "jobs",
                "build_commands",
                "environment_template",
                "volume_templates",
            ]:
                if hasattr(profile_compile_method, field):
                    config_dict[field] = getattr(profile_compile_method, field)
                    logger.debug(
                        "Copied profile field: %s=%r", field, config_dict[field]
                    )

            config = ZmkCompilationConfig(**config_dict)
            logger.debug("Created ZmkCompilationConfig from profile attributes")
    else:
        # No profile config found, use defaults
        if params.strategy == "moergo":
            config = MoergoCompilationConfig()
            logger.debug("Using default MoergoCompilationConfig")
        else:
            config = ZmkCompilationConfig(artifact_naming="zmk_github_actions")
            logger.debug("Using default ZmkCompilationConfig")

    # Apply CLI overrides
    if params.branch is not None and hasattr(config, "branch"):
        config.branch = params.branch
        logger.debug("CLI override: branch=%s", params.branch)

    if params.repo is not None and hasattr(config, "repository"):
        config.repository = params.repo
        logger.debug("CLI override: repository=%s", params.repo)

    if params.jobs is not None:
        config.jobs = params.jobs
        logger.debug("CLI override: jobs=%s", params.jobs)

    # Build Docker user configuration
    docker_user_config = _build_docker_user_config(params, params.strategy)
    config.docker_user = docker_user_config

    # Apply workspace settings
    config.cleanup_workspace = (
        not params.preserve_workspace if not params.force_cleanup else True
    )
    config.preserve_on_failure = params.preserve_workspace and not params.force_cleanup

    # Apply cache settings for ZMK configs
    if isinstance(config, ZmkCompilationConfig):
        config.cache = CacheConfig(enabled=not params.no_cache)

    logger.debug("Final compilation config: %r", config)
    return config


def _execute_compilation(
    params: FirmwareCompileParams,
    config: ZmkCompilationConfig | MoergoCompilationConfig,
    keyboard_profile: Any,
) -> Any:
    """Execute the compilation and return result."""
    # Clear cache if requested
    if params.clear_cache:
        logger.info("Cache clearing requested (will be implemented in Phase 7)")

    # Create compilation service
    compilation_service = create_compilation_service(params.strategy)

    return compilation_service.compile(
        keymap_file=params.keymap_file,
        config_file=params.kconfig_file,
        output_dir=params.output_dir,
        config=config,
        keyboard_profile=keyboard_profile,
    )


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
            help="Compilation strategy: zmk_config (default), west",
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
    # Workspace configuration options
    workspace_dir: Annotated[
        Path | None,
        typer.Option("--workspace-dir", help="Custom workspace root directory"),
    ] = None,
    preserve_workspace: Annotated[
        bool,
        typer.Option("--preserve-workspace", help="Don't delete workspace after build"),
    ] = False,
    force_cleanup: Annotated[
        bool,
        typer.Option("--force-cleanup", help="Force workspace cleanup even on failure"),
    ] = False,
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
    # Build parameter container
    params = FirmwareCompileParams(
        keymap_file=keymap_file,
        kconfig_file=kconfig_file,
        output_dir=output_dir,
        strategy=strategy,
        branch=branch,
        repo=repo,
        jobs=jobs,
        verbose=verbose,
        no_cache=no_cache,
        clear_cache=clear_cache,
        board_targets=board_targets,
        docker_uid=docker_uid,
        docker_gid=docker_gid,
        docker_username=docker_username,
        docker_home=docker_home,
        docker_container_home=docker_container_home,
        no_docker_user_mapping=no_docker_user_mapping,
        workspace_dir=workspace_dir,
        preserve_workspace=preserve_workspace,
        force_cleanup=force_cleanup,
        build_matrix=build_matrix,
        output_format=output_format,
    )

    # Get profile and user config
    keyboard_profile = get_keyboard_profile_from_context(ctx)
    user_config = get_user_config_from_context(ctx)

    logger.info("KeyboardProfile available in context: %r", keyboard_profile)
    # Build compilation configuration
    config = _build_compilation_config(params, keyboard_profile)

    # Execute compilation
    try:
        result = _execute_compilation(params, config, keyboard_profile)
        _format_compilation_output(result, params.output_format, params.output_dir)
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
