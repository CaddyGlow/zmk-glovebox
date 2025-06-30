"""Firmware-related CLI commands."""

import logging
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Annotated, Any

import typer

from glovebox.cli.decorators import handle_errors, with_metrics, with_profile
from glovebox.cli.helpers import (
    print_error_message,
    print_list_item,
    print_success_message,
)
from glovebox.cli.helpers.auto_profile import (
    resolve_json_file_path,
    resolve_profile_with_auto_detection,
)
from glovebox.cli.helpers.parameters import OutputFormatOption, ProfileOption
from glovebox.cli.helpers.profile import (
    create_profile_from_option,
    get_keyboard_profile_from_context,
    get_user_config_from_context,
)
from glovebox.compilation.models import (
    CompilationConfigUnion,
    MoergoCompilationConfig,
    ZmkCompilationConfig,
)
from glovebox.config.profile import KeyboardProfile
from glovebox.core.file_operations import (
    CompilationProgress,
    CompilationProgressCallback,
)
from glovebox.firmware.flash import create_flash_service
from glovebox.firmware.flash.models import FlashResult


logger = logging.getLogger(__name__)


def _resolve_compilation_type(
    keyboard_profile: KeyboardProfile, strategy: str | None
) -> tuple[str, CompilationConfigUnion]:
    """Resolve compilation type and config from profile."""
    # Get the appropriate compile method config from the keyboard profile
    if not keyboard_profile.keyboard_config.compile_methods:
        print_error_message(
            f"No compile methods configured for keyboard '{keyboard_profile.keyboard_name}'"
        )
        raise typer.Exit(1)

    # Determine compilation strategy
    compile_config: MoergoCompilationConfig | ZmkCompilationConfig | None = None
    if strategy:
        compilation_strategy = strategy
        # Find the matching compile method config for our strategy
        for method_config in keyboard_profile.keyboard_config.compile_methods:
            if (
                isinstance(method_config, MoergoCompilationConfig)
                and compilation_strategy == "moergo"
            ):
                compile_config = method_config
                break
            if (
                isinstance(method_config, ZmkCompilationConfig)
                and compilation_strategy == "zmk_config"
            ):
                compile_config = method_config
                break
    else:
        # Use first available config if no specific match found
        compile_config = keyboard_profile.keyboard_config.compile_methods[0]
        logger.info("Using fallback compile config: %r", type(compile_config).__name__)

    if not compile_config:
        print_error_message(
            f"No compile methods configured for keyboard '{keyboard_profile.keyboard_name}'"
        )
        raise typer.Exit(1)

    # At this point, compile_config is guaranteed to be not None
    compilation_strategy = compile_config.method_type

    return compilation_strategy, compile_config


def _update_config_from_profile(
    compile_config: CompilationConfigUnion,
    keyboard_profile: KeyboardProfile,
) -> None:
    """Update compile config with firmware settings from profile."""
    if keyboard_profile.firmware_config is not None:
        compile_config.branch = keyboard_profile.firmware_config.build_options.branch
        compile_config.repository = (
            keyboard_profile.firmware_config.build_options.repository
        )


def _execute_compilation_service(
    compilation_strategy: str,
    keymap_file: Path,
    kconfig_file: Path,
    build_output_dir: Path,
    compile_config: CompilationConfigUnion,
    keyboard_profile: KeyboardProfile,
    session_metrics: Any = None,
    user_config: Any = None,
    progress_callback: Any = None,
) -> Any:
    """Execute the compilation service."""
    from glovebox.adapters import create_docker_adapter, create_file_adapter
    from glovebox.compilation import create_compilation_service

    docker_adapter = create_docker_adapter()
    file_adapter = create_file_adapter()

    # Create cache services if strategy requires them
    cache_manager = None
    workspace_cache_service = None
    build_cache_service = None

    if compilation_strategy == "zmk_config":
        # Update progress for cache service initialization
        if progress_callback:
            cache_progress = CompilationProgress(
                repositories_downloaded=35,
                total_repositories=100,
                current_repository="Setting up cache services...",
                compilation_phase="initialization",
            )
            progress_callback(cache_progress)

        from glovebox.compilation.cache import create_compilation_cache_service

        cache_manager, workspace_cache_service, build_cache_service = (
            create_compilation_cache_service(user_config, session_metrics)
        )

    compilation_service = create_compilation_service(
        compilation_strategy,
        user_config=user_config,
        docker_adapter=docker_adapter,
        file_adapter=file_adapter,
        cache_manager=cache_manager,
        workspace_cache_service=workspace_cache_service,
        build_cache_service=build_cache_service,
        session_metrics=session_metrics,
    )

    # Use unified config directly - no conversion needed
    return compilation_service.compile(
        keymap_file=keymap_file,
        config_file=kconfig_file,
        output_dir=build_output_dir,
        config=compile_config,
        keyboard_profile=keyboard_profile,
        progress_callback=progress_callback,
    )


# Auto-profile detection functions moved to glovebox.cli.helpers.auto_profile
# for shared use between firmware and layout commands


def _execute_compilation_from_json(
    compilation_strategy: str,
    json_file: Path,
    build_output_dir: Path,
    compile_config: CompilationConfigUnion,
    keyboard_profile: KeyboardProfile,
    session_metrics: Any = None,
    user_config: Any = None,
    progress_callback: Any = None,
) -> Any:
    """Execute compilation from JSON layout file."""
    from glovebox.adapters import create_docker_adapter, create_file_adapter
    from glovebox.compilation import create_compilation_service

    docker_adapter = create_docker_adapter()
    file_adapter = create_file_adapter()

    # Create cache services if strategy requires them
    cache_manager = None
    workspace_cache_service = None
    build_cache_service = None

    if compilation_strategy == "zmk_config":
        # Update progress for cache service initialization
        if progress_callback:
            cache_progress = CompilationProgress(
                repositories_downloaded=35,
                total_repositories=100,
                current_repository="Setting up cache services...",
                compilation_phase="initialization",
            )
            progress_callback(cache_progress)

        from glovebox.compilation.cache import create_compilation_cache_service

        cache_manager, workspace_cache_service, build_cache_service = (
            create_compilation_cache_service(user_config, session_metrics)
        )

    compilation_service = create_compilation_service(
        compilation_strategy,
        user_config=user_config,
        docker_adapter=docker_adapter,
        file_adapter=file_adapter,
        cache_manager=cache_manager,
        workspace_cache_service=workspace_cache_service,
        build_cache_service=build_cache_service,
        session_metrics=session_metrics,
    )

    # Use the new compile_from_json method
    return compilation_service.compile_from_json(
        json_file=json_file,
        output_dir=build_output_dir,
        config=compile_config,
        keyboard_profile=keyboard_profile,
        progress_callback=progress_callback,
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


def _determine_firmware_outputs(
    result: Any,
    base_filename: str,
    templates: Any = None,
    layout_data: dict[str, Any] | None = None,
    original_filename: str | None = None,
) -> list[tuple[Path, Path]]:
    """Determine which firmware files to create based on build result.

    Args:
        result: BuildResult object from compilation
        base_filename: Base filename without extension for output files (fallback)
        templates: Filename template configuration (optional)
        layout_data: Layout data for template generation (optional)
        original_filename: Original input filename (optional)

    Returns:
        List of tuples (source_path, target_path) for firmware files to copy
    """
    outputs: list[tuple[Path, Path]] = []

    if not result.success or not result.output_files:
        return outputs

    # Process all UF2 files
    for uf2_file in result.output_files.uf2_files:
        if not uf2_file.exists():
            continue

        filename_lower = uf2_file.name.lower()

        # Determine board suffix and generate appropriate filename
        if "lh" in filename_lower or "lf" in filename_lower:
            # Left hand/front firmware
            if templates and layout_data:
                from glovebox.utils.filename_generator import (
                    FileType,
                    generate_default_filename,
                )

                target_filename = generate_default_filename(
                    FileType.FIRMWARE_UF2,
                    templates,
                    layout_data=layout_data,
                    original_filename=original_filename,
                    board="lf",
                )
            else:
                target_filename = f"{base_filename}_lf.uf2"
            outputs.append((uf2_file, Path(target_filename)))

        elif "rh" in filename_lower:
            # Right hand firmware
            if templates and layout_data:
                from glovebox.utils.filename_generator import (
                    FileType,
                    generate_default_filename,
                )

                target_filename = generate_default_filename(
                    FileType.FIRMWARE_UF2,
                    templates,
                    layout_data=layout_data,
                    original_filename=original_filename,
                    board="rh",
                )
            else:
                target_filename = f"{base_filename}_rh.uf2"
            outputs.append((uf2_file, Path(target_filename)))

        else:
            # Main/unified firmware or first available firmware
            if templates and layout_data:
                from glovebox.utils.filename_generator import (
                    FileType,
                    generate_default_filename,
                )

                target_filename = generate_default_filename(
                    FileType.FIRMWARE_UF2,
                    templates,
                    layout_data=layout_data,
                    original_filename=original_filename,
                )
            else:
                target_filename = f"{base_filename}.uf2"
            outputs.append((uf2_file, Path(target_filename)))

    return outputs


def _process_compilation_output(
    result: Any, input_file: Path, output_dir: Path | None
) -> None:
    """Process compilation output based on --output flag.

    Args:
        result: BuildResult object from compilation
        input_file: Original input file path for base naming
        output_dir: Output directory if --output flag provided, None otherwise
    """
    if not result.success or not result.output_files:
        return

    if output_dir is not None:
        # --output flag provided: keep existing behavior (files already in output_dir)
        return

    # No --output flag: create smart default filenames using templates
    from glovebox.config import create_user_config
    from glovebox.utils.filename_generator import FileType, generate_default_filename
    from glovebox.utils.filename_helpers import extract_layout_dict_data

    user_config = create_user_config()

    # Extract layout data if input is JSON
    layout_data = None
    if input_file.suffix.lower() == ".json":
        try:
            import json

            layout_dict = json.loads(input_file.read_text())
            layout_data = extract_layout_dict_data(layout_dict)
        except Exception:
            # Fallback if JSON parsing fails
            pass

    # Generate base filename (without extension) for firmware files
    firmware_filename = generate_default_filename(
        FileType.FIRMWARE_UF2,
        user_config._config.filename_templates,
        layout_data=layout_data,
        original_filename=str(input_file),
    )
    base_filename = Path(firmware_filename).stem

    try:
        # Determine firmware files to create
        firmware_outputs = _determine_firmware_outputs(
            result,
            base_filename,
            templates=user_config._config.filename_templates,
            layout_data=layout_data,
            original_filename=str(input_file),
        )

        # Copy firmware files to current directory
        for source_path, target_path in firmware_outputs:
            if source_path.exists():
                shutil.copy2(source_path, target_path)
                logger.info("Created firmware file: %s", target_path)

        # Create artifacts zip file using smart filename generation
        artifacts_filename = generate_default_filename(
            FileType.ARTIFACTS_ZIP,
            user_config._config.filename_templates,
            layout_data=layout_data,
            original_filename=str(input_file),
        )
        artifacts_zip_path = Path(artifacts_filename)
        if (
            result.output_files.artifacts_dir
            and result.output_files.artifacts_dir.exists()
        ):
            with zipfile.ZipFile(
                artifacts_zip_path, "w", zipfile.ZIP_DEFLATED
            ) as zip_file:
                for file_path in result.output_files.artifacts_dir.rglob("*"):
                    if file_path.is_file():
                        # Store relative path within artifacts directory
                        arcname = file_path.relative_to(
                            result.output_files.artifacts_dir
                        )
                        zip_file.write(file_path, arcname)
            logger.info("Created artifacts archive: %s", artifacts_zip_path)
        elif result.output_files.output_dir and result.output_files.output_dir.exists():
            # Fallback: archive entire output directory if no specific artifacts_dir
            with zipfile.ZipFile(
                artifacts_zip_path, "w", zipfile.ZIP_DEFLATED
            ) as zip_file:
                for file_path in result.output_files.output_dir.rglob("*"):
                    if file_path.is_file():
                        # Store relative path within output directory
                        arcname = file_path.relative_to(result.output_files.output_dir)
                        zip_file.write(file_path, arcname)
            logger.info(
                "Created artifacts archive from output directory: %s",
                artifacts_zip_path,
            )

    except Exception as e:
        exc_info = logger.isEnabledFor(logging.DEBUG)
        logger.error("Failed to process compilation output: %s", e, exc_info=exc_info)
        print_error_message(f"Failed to create output files: {str(e)}")


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
@with_profile(required=True, firmware_optional=False, support_auto_detection=True)
@with_metrics("compile")
def firmware_compile(
    ctx: typer.Context,
    input_file: Annotated[
        Path | None,
        typer.Argument(
            help="Path to keymap (.keymap) or layout (.json) file. Can use GLOVEBOX_JSON_FILE env var for JSON files."
        ),
    ] = None,
    config_file: Annotated[
        Path | None,
        typer.Argument(help="Path to kconfig (.conf) file (optional for JSON input)"),
    ] = None,
    profile: ProfileOption = None,
    strategy: Annotated[
        str | None,
        typer.Option(
            "--strategy",
            help="Compilation strategy: auto-detect by profile if not specified",
        ),
    ] = None,
    no_auto: Annotated[
        bool,
        typer.Option(
            "--no-auto",
            help="Disable automatic profile detection from JSON keyboard field",
        ),
    ] = False,
    output_format: OutputFormatOption = "text",
    progress: Annotated[
        bool | None,
        typer.Option(
            "--progress/--no-progress",
            help="Show compilation progress with repository downloads (default: enabled)",
        ),
    ] = None,
    show_logs: Annotated[
        bool,
        typer.Option(
            "--show-logs/--no-show-logs",
            help="Show compilation logs in progress display (default: enabled when progress is shown)",
        ),
    ] = True,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            help="Show debug-level application logs in TUI progress display",
        ),
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output directory for build files. If not specified, creates {filename}.uf2 and {filename}_artefacts.zip in current directory",
        ),
    ] = None,
) -> None:
    """Build ZMK firmware from keymap/config files or JSON layout.

    Compiles .keymap and .conf files, or a .json layout file, into a flashable
    .uf2 firmware file using Docker and the ZMK build system. Requires Docker to be running.

    \b
    For JSON input, the layout is automatically converted to .keymap and .conf files
    before compilation. The config_file argument is optional for JSON input.

    \b
    Output behavior:
    - With --output: Creates build files in specified directory (traditional behavior)
    - Without --output: Creates {filename}.uf2 and {filename}_artefacts.zip in current directory
    - Split keyboards: Creates {filename}_lh.uf2 and {filename}_rh.uf2 for left/right hands
    - Unified firmware: Creates {filename}.uf2 file (when available)
    - Both unified and split files can be created simultaneously

    \b
    Profile precedence (highest to lowest):
    1. CLI --profile flag (overrides all)
    2. Auto-detection from JSON keyboard field (unless --no-auto)
    3. User config default profile
    4. Hardcoded fallback profile

    \b
    Supports multiple compilation strategies:
    - zmk_config: ZMK config repository builds (default, recommended)
    - moergo: Moergo-specific compilation strategy
    \b
    Configuration options like Docker settings, workspace management, and build
    parameters are managed through profile configurations and user config files.
    \b
    Examples:
        # Default behavior: Creates my_layout.uf2 and my_layout_artefacts.zip
        glovebox firmware compile my_layout.json

        # Traditional behavior: Creates files in build/ directory
        glovebox firmware compile my_layout.json --output build/

        # Specify custom output directory
        glovebox firmware compile keymap.keymap config.conf --output /path/to/output --profile glove80/v25.05

        # Disable auto-profile detection
        glovebox firmware compile layout.json --no-auto --profile glove80/v25.05

        # Specify compilation strategy explicitly
        glovebox firmware compile layout.json --profile glove80/v25.05 --strategy zmk_config

        # Show debug logs in TUI progress display
        glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05 --debug

        # JSON output for automation
        glovebox firmware compile layout.json --profile glove80/v25.05 --output-format json
    """

    # Access user config and icon mode from CLI context
    from glovebox.cli.helpers.theme import get_icon_mode_from_context

    icon_mode = get_icon_mode_from_context(ctx)

    try:
        # Determine if progress should be shown (default: enabled)
        show_progress = progress if progress is not None else True

        # Create progress display and callback if progress is enabled
        progress_display = None
        progress_callback = None
        # if show_progress:
        #     progress_display, progress_callback = _create_compilation_progress_display(
        #         show_logs=show_logs, debug=debug
        #     )
        #
        # # Resolve input file path (supports environment variable for JSON files)
        # if progress_callback:
        #     early_progress = CompilationProgress(
        #         repositories_downloaded=5,
        #         total_repositories=100,
        #         current_repository="Resolving input file path...",
        #         compilation_phase="initialization",
        #     )
        #     progress_callback(early_progress)

        resolved_input_file = resolve_json_file_path(input_file, "GLOVEBOX_JSON_FILE")

        if resolved_input_file is None:
            if progress_callback and hasattr(progress_callback, "cleanup"):
                progress_callback.cleanup()
            print_error_message(
                "Input file is required. Provide as argument or set GLOVEBOX_JSON_FILE environment variable."
            )
            raise typer.Exit(1)

        # Profile is already handled by the @with_profile decorator
        keyboard_profile = get_keyboard_profile_from_context(ctx)

        # Detect input file type and validate arguments
        is_json_input = resolved_input_file.suffix.lower() == ".json"

        if not is_json_input and config_file is None:
            if progress_callback and hasattr(progress_callback, "cleanup"):
                progress_callback.cleanup()
            print_error_message("Config file is required when input is a .keymap file")
            raise typer.Exit(1)

        if is_json_input and config_file is not None:
            logger.info(
                "Config file provided for JSON input will be ignored (generated automatically)"
            )

        # Set output directory based on --output flag
        if output is not None:
            # --output flag provided: use specified directory (existing behavior)
            build_output_dir = output
            build_output_dir.mkdir(parents=True, exist_ok=True)
        else:
            # No --output flag: use temporary directory for compilation
            build_output_dir = Path(tempfile.mkdtemp(prefix="glovebox_build_"))

        compilation_type, compile_config = _resolve_compilation_type(
            keyboard_profile, strategy
        )

        # Update config with profile firmware settings
        _update_config_from_profile(compile_config, keyboard_profile)

        # Execute compilation
        logger.info("🚀 Starting firmware compilation...")

        from glovebox.cli.progress.displays.staged_with_logs import (
            StagedProgressWithLogsDisplay,
        )

        progress_display = StagedProgressWithLogsDisplay(progress_callback)
        # Use progress display as context manager if enabled
        if progress_display is not None:
            with progress_display:
                # Execute compilation based on input type
                if is_json_input:
                    result = _execute_compilation_from_json(
                        compilation_type,
                        resolved_input_file,
                        build_output_dir,
                        compile_config,
                        keyboard_profile,
                        session_metrics=ctx.obj.session_metrics,
                        user_config=get_user_config_from_context(ctx),
                        progress_callback=progress_callback,
                    )
                else:
                    assert config_file is not None  # Already validated above
                    result = _execute_compilation_service(
                        compilation_type,
                        resolved_input_file,  # keymap_file
                        config_file,  # kconfig_file
                        build_output_dir,
                        compile_config,
                        keyboard_profile,
                        session_metrics=ctx.obj.session_metrics,
                        user_config=get_user_config_from_context(ctx),
                        progress_callback=progress_callback,
                    )
        else:
            # Execute compilation without progress display
            if is_json_input:
                result = _execute_compilation_from_json(
                    compilation_type,
                    resolved_input_file,
                    build_output_dir,
                    compile_config,
                    keyboard_profile,
                    session_metrics=ctx.obj.session_metrics,
                    user_config=get_user_config_from_context(ctx),
                    progress_callback=progress_callback,
                )
            else:
                assert config_file is not None  # Already validated above
                result = _execute_compilation_service(
                    compilation_type,
                    resolved_input_file,  # keymap_file
                    config_file,  # kconfig_file
                    build_output_dir,
                    compile_config,
                    keyboard_profile,
                    session_metrics=ctx.obj.session_metrics,
                    user_config=get_user_config_from_context(ctx),
                    progress_callback=progress_callback,
                )

        # Clean up temporary build directory if --output was not provided
        temp_cleanup_needed = output is None

        # Progress display cleanup is handled by context manager

        if result.success:
            # Process compilation output (create .uf2 and _artefacts.zip if --output not provided)
            _process_compilation_output(result, resolved_input_file, output)

            # Format and display results
            _format_compilation_output(result, output_format, build_output_dir)
        else:
            # Format and display results
            _format_compilation_output(result, output_format, build_output_dir)

        # Clean up temporary build directory if needed
        if temp_cleanup_needed and build_output_dir.exists():
            try:
                shutil.rmtree(build_output_dir)
                logger.debug(
                    "Cleaned up temporary build directory: %s", build_output_dir
                )
            except Exception as cleanup_error:
                logger.warning(
                    "Failed to clean up temporary build directory: %s", cleanup_error
                )

    except Exception as e:
        # Clean up progress display if it was used
        if progress_callback and hasattr(progress_callback, "cleanup"):
            progress_callback.cleanup()

        print_error_message(f"Firmware compilation failed: {str(e)}")
        logger.exception("Compilation error details")

        # Clean up temporary build directory if needed
        if (
            "temp_cleanup_needed" in locals()
            and temp_cleanup_needed
            and "build_output_dir" in locals()
            and build_output_dir.exists()
        ):
            try:
                shutil.rmtree(build_output_dir)
                logger.debug(
                    "Cleaned up temporary build directory after error: %s",
                    build_output_dir,
                )
            except Exception as cleanup_error:
                logger.warning(
                    "Failed to clean up temporary build directory after error: %s",
                    cleanup_error,
                )

        raise typer.Exit(1) from None


@firmware_app.command()
@handle_errors
@with_profile(required=True, firmware_optional=False)
@with_metrics("flash")
def flash(
    ctx: typer.Context,
    firmware_files: Annotated[
        list[Path], typer.Argument(help="Path(s) to firmware (.uf2) file(s)")
    ],
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
    """Flash firmware file(s) to connected keyboard devices.

    Automatically detects USB keyboards in bootloader mode and flashes
    the firmware file(s) sequentially. Supports flashing multiple devices
    simultaneously and multiple firmware files one after the other.

    Wait mode uses real-time USB device monitoring for immediate detection
    when devices are connected. Configure defaults in user config file.

    Examples:
        # Basic flash (uses config defaults)
        glovebox firmware flash firmware.uf2 --profile glove80/v25.05

        # Flash multiple firmwares sequentially (e.g., left and right halves)
        glovebox firmware flash left.uf2 right.uf2 --profile glove80/v25.05

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

    # Access icon mode from CLI context
    from glovebox.cli.helpers.theme import get_icon_mode_from_context

    icon_mode = get_icon_mode_from_context(ctx)

    try:
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
            effective_poll_interval = (
                poll_interval if poll_interval is not None else 0.5
            )
            effective_show_progress = (
                show_progress if show_progress is not None else True
            )

        # Use the new file-based method which handles file existence checks
        from glovebox.adapters import create_file_adapter
        from glovebox.firmware.flash.device_wait_service import (
            create_device_wait_service,
        )

        file_adapter = create_file_adapter()
        device_wait_service = create_device_wait_service()
        flash_service = create_flash_service(file_adapter, device_wait_service)

        # Flash multiple firmware files sequentially
        all_results = []
        total_devices_flashed = 0
        total_devices_failed = 0

        for i, firmware_file in enumerate(firmware_files):
            print_success_message(
                f"Flashing firmware {i + 1}/{len(firmware_files)}: {firmware_file.name}"
            )

            result = flash_service.flash_from_file(
                firmware_file_path=firmware_file,
                profile=keyboard_profile,
                query=query,  # query parameter will override profile's query if provided
                timeout=effective_timeout,
                count=effective_count,
                track_flashed=effective_track_flashed,
                skip_existing=effective_skip_existing,
                wait=effective_wait,
                poll_interval=effective_poll_interval,
                show_progress=effective_show_progress,
            )

            all_results.append(result)
            total_devices_flashed += result.devices_flashed
            total_devices_failed += result.devices_failed

            # Show result for this firmware file
            if result.success:
                print_success_message(
                    f"Firmware {firmware_file.name}: {result.devices_flashed} device(s) flashed"
                )
            else:
                print_error_message(
                    f"Firmware {firmware_file.name}: {result.devices_failed} device(s) failed"
                )

        # Create combined result
        result = FlashResult(success=True)
        result.devices_flashed = total_devices_flashed
        result.devices_failed = total_devices_failed

        # Combine all device details
        for individual_result in all_results:
            result.device_details.extend(individual_result.device_details)
            result.messages.extend(individual_result.messages)
            result.errors.extend(individual_result.errors)

        # Overall success if we flashed any devices and no failures
        if total_devices_flashed == 0 or total_devices_failed > 0:
            result.success = False

        if result.success:
            if output_format.lower() == "json":
                # JSON output for automation
                result_data = {
                    "success": True,
                    "devices_flashed": result.devices_flashed,
                    "firmware_files_processed": len(firmware_files),
                    "device_details": result.device_details,
                }
                from glovebox.cli.helpers.output_formatter import OutputFormatter

                formatter = OutputFormatter()
                print(formatter.format(result_data, "json"))
            else:
                # Rich text output (default)
                print_success_message(
                    f"Successfully flashed {len(firmware_files)} firmware file(s) to {result.devices_flashed} device(s) total"
                )
                if result.device_details:
                    for device in result.device_details:
                        if device["status"] == "success":
                            print_list_item(f"{device['name']}: SUCCESS")
        else:
            print_error_message(
                f"Flash completed with {result.devices_failed} failure(s) across {len(firmware_files)} firmware file(s)"
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


@firmware_app.command(name="devices")
@handle_errors
@with_profile(required=False, firmware_optional=True)
def list_devices(
    ctx: typer.Context,
    profile: ProfileOption = None,
    query: Annotated[
        str, typer.Option("--query", "-q", help="Device query string")
    ] = "",
    output_format: OutputFormatOption = "text",
) -> None:
    """List available devices for firmware flashing.

    Detects and displays USB devices that can be used for flashing firmware.
    Shows device information including name, vendor, mount status, and connection
    details. Supports filtering by device query string and multiple output formats.

    \\b
    Device information displayed:
    - Device name and vendor identification
    - Mount point and connection status
    - Device query string for targeting specific devices
    - Compatibility with keyboard profile flash methods

    Examples:
        # List all available devices
        glovebox firmware devices

        # Filter devices by query string
        glovebox firmware devices --query "nice_nano"

        # Show device list in JSON format
        glovebox firmware devices --output-format json --profile glove80
    """
    from glovebox.adapters import create_file_adapter
    from glovebox.firmware.flash.device_wait_service import create_device_wait_service

    file_adapter = create_file_adapter()
    device_wait_service = create_device_wait_service()
    flash_service = create_flash_service(file_adapter, device_wait_service)

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
