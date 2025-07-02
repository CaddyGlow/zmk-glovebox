"""Firmware-related CLI commands."""

import logging
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Annotated, Any

import typer

from glovebox.cli.decorators import (
    handle_errors,
    with_cache,
    with_metrics,
    with_profile,
    with_tmpdir,
)
from glovebox.cli.decorators.profile import (
    get_compilation_cache_services_from_context,
    get_tmpdir_from_context,
)
from glovebox.cli.helpers import (
    print_error_message,
    print_list_item,
    print_success_message,
)
from glovebox.cli.helpers.auto_profile import (
    resolve_json_file_path,
    resolve_profile_with_auto_detection,
)
from glovebox.cli.helpers.parameter_factory import ParameterFactory
from glovebox.cli.helpers.parameter_helpers import resolve_firmware_input_file
from glovebox.cli.helpers.parameters import (
    ProfileOption,
    complete_config_flags,
)
from glovebox.cli.helpers.profile import (
    create_profile_from_option,
    get_keyboard_profile_from_context,
    get_user_config_from_context,
)
from glovebox.cli.helpers.theme import Icons
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
from glovebox.firmware.flash.models import BlockDevice, FlashResult


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


def _create_compilation_service_with_progress(
    compilation_strategy: str,
    user_config: Any,
    session_metrics: Any,
    progress_coordinator: Any,
    cache_manager: Any,
    workspace_cache_service: Any,
    build_cache_service: Any,
) -> Any:
    """Create compilation service with common setup."""
    from glovebox.adapters import create_docker_adapter, create_file_adapter
    from glovebox.compilation import create_compilation_service

    docker_adapter = create_docker_adapter()
    file_adapter = create_file_adapter()

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

    # If we have a progress coordinator, try to pass it directly
    if hasattr(compilation_service, "set_progress_coordinator"):
        compilation_service.set_progress_coordinator(progress_coordinator)

    return compilation_service


def _execute_compilation_service(
    compilation_strategy: str,
    keymap_file: Path,
    kconfig_file: Path,
    build_output_dir: Path,
    compile_config: CompilationConfigUnion,
    keyboard_profile: KeyboardProfile,
    session_metrics: Any = None,
    user_config: Any = None,
    progress_coordinator: Any = None,
    progress_callback: Any = None,
    cache_manager: Any = None,
    workspace_cache_service: Any = None,
    build_cache_service: Any = None,
) -> Any:
    """Execute the compilation service."""
    compilation_service = _create_compilation_service_with_progress(
        compilation_strategy,
        user_config,
        session_metrics,
        progress_coordinator,
        cache_manager,
        workspace_cache_service,
        build_cache_service,
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
    progress_coordinator: Any = None,
    progress_callback: Any = None,
    cache_manager: Any = None,
    workspace_cache_service: Any = None,
    build_cache_service: Any = None,
) -> Any:
    """Execute compilation from JSON layout file."""
    compilation_service = _create_compilation_service_with_progress(
        compilation_strategy,
        user_config,
        session_metrics,
        progress_coordinator,
        cache_manager,
        workspace_cache_service,
        build_cache_service,
    )

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


def _setup_progress_display(ctx: typer.Context, show_progress: bool) -> tuple[Any, Any, Any]:
    """Set up progress display components.
    
    Args:
        ctx: Typer context with user config
        show_progress: Whether to show progress
        
    Returns:
        Tuple of (progress_display, progress_coordinator, progress_callback)
    """
    if not show_progress:
        return None, None, None
        
    from rich.console import Console

    from glovebox.cli.helpers.theme import get_icon_mode_from_context
    from glovebox.compilation.simple_progress import (
        ProgressConfig,
        create_simple_compilation_display,
        create_simple_progress_coordinator,
    )

    # Get icon mode from context (which contains user config)
    icon_mode = get_icon_mode_from_context(ctx)

    # Create firmware compilation configuration
    firmware_config = ProgressConfig(
        operation_name="Firmware Build",
        icon_mode=icon_mode,
    )

    console = Console()
    progress_display = create_simple_compilation_display(
        console, firmware_config, icon_mode
    )
    progress_coordinator = create_simple_progress_coordinator(progress_display)
    progress_display.start()

    # Create a bridge callback that forwards to our coordinator
    def progress_callback(progress: Any) -> None:
        """Bridge callback that forwards progress updates to our simple coordinator."""
        if (
            hasattr(progress, "state")
            and progress.state
            and hasattr(progress, "compilation_phase")
        ):
            progress_coordinator.transition_to_phase(
                progress.compilation_phase, progress.description or ""
            )
            # Note: This is a basic bridge - more sophisticated mapping could be added
            
    return progress_display, progress_coordinator, progress_callback


def _get_cache_services_with_fallback(ctx: typer.Context) -> tuple[Any, Any, Any]:
    """Get cache services from context with fallback creation.
    
    Args:
        ctx: Typer context
        
    Returns:
        Tuple of (cache_manager, workspace_service, build_service)
    """
    try:
        return get_compilation_cache_services_from_context(ctx)
    except RuntimeError:
        # Fallback: create cache services manually
        logger.warning("Creating fallback cache services due to decorator issue")
        from glovebox.compilation.cache import create_compilation_cache_service
        from glovebox.config import create_user_config

        user_config = get_user_config_from_context(ctx) or create_user_config()
        return create_compilation_cache_service(user_config)


def _get_build_output_dir(output: Path | None, ctx: typer.Context) -> tuple[Path, bool]:
    """Get build output directory with proper cleanup tracking.
    
    Args:
        output: User-specified output directory or None
        ctx: Typer context
        
    Returns:
        Tuple of (build_output_dir, manual_cleanup_needed)
    """
    if output is not None:
        # --output flag provided: use specified directory (existing behavior)
        build_output_dir = output
        build_output_dir.mkdir(parents=True, exist_ok=True)
        return build_output_dir, False
    else:
        # No --output flag: use temporary directory from decorator
        try:
            build_output_dir = get_tmpdir_from_context(ctx)
            return build_output_dir, False
        except RuntimeError:
            # Fallback: create a temporary directory manually
            import tempfile

            temp_dir = tempfile.mkdtemp(prefix="glovebox_build_")
            build_output_dir = Path(temp_dir)
            logger.warning(
                "Using fallback temporary directory due to decorator issue: %s",
                build_output_dir,
            )
            return build_output_dir, True


def _prepare_config_file(
    is_json_input: bool,
    config_file: Path | None,
    config_flags: list[str] | None,
    build_output_dir: Path,
) -> Path | None:
    """Prepare config file for compilation, handling flags and defaults.
    
    Args:
        is_json_input: Whether input is JSON (doesn't need config file)
        config_file: User-provided config file
        config_flags: Additional config flags
        build_output_dir: Directory for temporary files
        
    Returns:
        Path to effective config file or None for JSON input
    """
    if is_json_input:
        return None
        
    effective_config_flags = config_flags or []
    
    # Need to create or augment config file
    if config_file is None or effective_config_flags:
        # Create temporary config file with flags
        temp_config_file = build_output_dir / "temp_config.conf"
        config_content = ""

        # Include existing config file content if provided
        if config_file is not None and config_file.exists():
            config_content = config_file.read_text()
            if not config_content.endswith("\n"):
                config_content += "\n"

        # Add config flags
        for flag in effective_config_flags:
            if "=" in flag:
                config_content += f"CONFIG_{flag}\n"
            else:
                config_content += f"CONFIG_{flag}=y\n"

        temp_config_file.write_text(config_content)
        logger.info(
            "Created temporary config file with %d flags",
            len(effective_config_flags),
        )
        return temp_config_file
        
    # Use provided config file as-is
    if config_file is not None:
        return config_file
        
    # Create empty config file as fallback
    temp_config_file = build_output_dir / "empty_config.conf"
    temp_config_file.write_text("")
    logger.info("Created empty config file for keymap compilation")
    return temp_config_file


def _cleanup_temp_directory(build_output_dir: Path, manual_cleanup_needed: bool) -> None:
    """Clean up temporary build directory if needed.
    
    Args:
        build_output_dir: Directory to clean up
        manual_cleanup_needed: Whether manual cleanup is required
    """
    if manual_cleanup_needed and build_output_dir.exists():
        try:
            shutil.rmtree(build_output_dir)
            logger.debug(
                "Cleaned up temporary build directory: %s", build_output_dir
            )
        except Exception as cleanup_error:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.warning(
                "Failed to clean up temporary build directory: %s", 
                cleanup_error,
                exc_info=exc_info
            )


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
@with_cache("compilation", compilation_cache=True)
@with_tmpdir(prefix="glovebox_build_", cleanup=True)
def firmware_compile(
    ctx: typer.Context,
    input_file: ParameterFactory.input_file_with_stdin_optional(  # type: ignore[valid-type]
        env_var="GLOVEBOX_JSON_FILE",
        help_text="Path to keymap (.keymap) or layout (.json) file, @library-name/uuid, or '-' for stdin. Can use GLOVEBOX_JSON_FILE env var for JSON files.",
        library_resolvable=True,
    ),
    config_file: Annotated[
        Path | None,
        typer.Argument(
            help="Path to kconfig (.conf) file (optional for JSON input)",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
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
    output_format: ParameterFactory.output_format() = "text",  # type: ignore[valid-type]
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
    output: ParameterFactory.output_directory_optional(  # type: ignore[valid-type]
        help_text="Output directory for build files. If not specified, creates {filename}.uf2 and {filename}_artefacts.zip in current directory"
    ) = None,
    config_flags: Annotated[
        list[str] | None,
        typer.Option(
            "-D",
            "--define",
            help="Config flags to add to build (e.g., -D CONFIG_ZMK_SLEEP=y -D CONFIG_BT_CTLR_TX_PWR_PLUS_8=y)",
            autocompletion=complete_config_flags,
        ),
    ] = None,
) -> None:
    """Build ZMK firmware from keymap/config files or JSON layout.

    Compiles .keymap and .conf files, or a .json layout file, into a flashable
    .uf2 firmware file using Docker and the ZMK build system. Requires Docker to be running.

    \b
    For JSON input, the layout is automatically converted to .keymap and .conf files
    before compilation. The config_file argument is optional for both JSON and keymap input.
    Config flags can be added using -D options (e.g., -D ZMK_SLEEP=y).

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

        # Compile keymap without config file using flags
        glovebox firmware compile keymap.keymap --profile glove80/v25.05 -D ZMK_SLEEP=y -D BT_CTLR_TX_PWR_PLUS_8=y

        # Combine existing config file with additional flags
        glovebox firmware compile keymap.keymap config.conf -D ZMK_RGB_UNDERGLOW=y --profile glove80/v25.05

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

    # Debug: Check what's in the context
    logger.debug(
        "Context obj attributes: %s", dir(ctx.obj) if hasattr(ctx, "obj") else "No obj"
    )
    logger.debug(
        "Has tmpdir: %s", hasattr(ctx.obj, "tmpdir") if hasattr(ctx, "obj") else False
    )

    # Initialize variables that might be referenced in error handlers
    progress_display = None
    build_output_dir = None
    manual_cleanup_needed = False

    try:
        # Determine if progress should be shown (default: enabled)
        show_progress = progress if progress is not None else True

        # Create progress display components
        progress_display, progress_coordinator, progress_callback = _setup_progress_display(
            ctx, show_progress
        )

        # Resolve input file path - handles both keymap and JSON files
        try:
            resolved_input_file = resolve_firmware_input_file(
                input_file,
                env_var="GLOVEBOX_JSON_FILE",
                allowed_extensions=[".json", ".keymap"],
            )
        except (FileNotFoundError, ValueError) as e:
            if progress_display:
                progress_display.stop()
            print_error_message(str(e))
            raise typer.Exit(1) from e

        if resolved_input_file is None:
            if progress_display:
                progress_display.stop()
            print_error_message(
                "Input file is required. Provide as argument or set GLOVEBOX_JSON_FILE environment variable."
            )
            raise typer.Exit(1)

        # Profile is already handled by the @with_profile decorator
        keyboard_profile = get_keyboard_profile_from_context(ctx)

        # Ensure we have a valid keyboard profile
        if keyboard_profile is None:
            if progress_display:
                progress_display.stop()
            print_error_message(
                "No keyboard profile available. Profile is required for firmware compilation."
            )
            raise typer.Exit(1)

        # Detect input file type and validate arguments
        is_json_input = resolved_input_file.suffix.lower() == ".json"

        if is_json_input and config_file is not None:
            logger.info(
                "Config file provided for JSON input will be ignored (generated automatically)"
            )

        # Set output directory based on --output flag
        build_output_dir, manual_cleanup_needed = _get_build_output_dir(output, ctx)

        compilation_type, compile_config = _resolve_compilation_type(
            keyboard_profile, strategy
        )

        # Update config with profile firmware settings
        _update_config_from_profile(compile_config, keyboard_profile)

        # Get cache services from context (provided by @with_cache decorator)
        cache_manager, workspace_service, build_service = _get_cache_services_with_fallback(ctx)

        # Execute compilation
        logger.info(
            "%s Starting firmware compilation...", Icons.get_icon("BUILD", "text")
        )

        # Handle config file creation for keymap files
        effective_config_file = _prepare_config_file(
            is_json_input, config_file, config_flags, build_output_dir
        )

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
                progress_coordinator=progress_coordinator,
                progress_callback=progress_callback,
                cache_manager=cache_manager,
                workspace_cache_service=workspace_service,
                build_cache_service=build_service,
            )
        else:
            assert effective_config_file is not None, (
                "Config file should be created for keymap compilation"
            )
            result = _execute_compilation_service(
                compilation_type,
                resolved_input_file,  # keymap_file
                effective_config_file,  # kconfig_file (could be temp file or original)
                build_output_dir,
                compile_config,
                keyboard_profile,
                session_metrics=ctx.obj.session_metrics,
                user_config=get_user_config_from_context(ctx),
                progress_coordinator=progress_coordinator,
                progress_callback=progress_callback,
                cache_manager=cache_manager,
                workspace_cache_service=workspace_service,
                build_cache_service=build_service,
            )

        if result.success:
            # Process compilation output (create .uf2 and _artefacts.zip if --output not provided)
            _process_compilation_output(result, resolved_input_file, output)

        # Format and display results
        _format_compilation_output(result, output_format, build_output_dir)

        # Clean up progress display after completion (success or failure)
        if progress_display:
            progress_display.stop()

        # Clean up temporary build directory if needed (only for manual temp dirs)
        _cleanup_temp_directory(build_output_dir, manual_cleanup_needed)

    except Exception as e:
        # Clean up progress display if it was used
        if progress_display:
            progress_display.stop()

        print_error_message(f"Firmware compilation failed: {str(e)}")
        logger.exception("Compilation error details")

        # Clean up temporary build directory if needed (only for manual temp dirs)
        if "build_output_dir" in locals() and "manual_cleanup_needed" in locals():
            _cleanup_temp_directory(build_output_dir, manual_cleanup_needed)

        raise typer.Exit(1) from None


@firmware_app.command()
@handle_errors
@with_profile(required=True, firmware_optional=False)
@with_metrics("flash")
def flash(
    ctx: typer.Context,
    firmware_files: ParameterFactory.input_multiple_files(  # type: ignore[valid-type]
        help_text="Path(s) to firmware (.uf2) file(s)", file_extensions=[".uf2"]
    ),
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
    output_format: ParameterFactory.output_format() = "text",  # type: ignore[valid-type]
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
    all_devices: Annotated[
        bool,
        typer.Option(
            "--all",
            "-a",
            help="Show all devices (bypass default removable=true filtering)",
        ),
    ] = False,
    wait: Annotated[
        bool,
        typer.Option(
            "--wait",
            "-w",
            help="Continuously monitor for device connections/disconnections",
        ),
    ] = False,
    output_format: ParameterFactory.output_format() = "text",  # type: ignore[valid-type]
) -> None:
    """List available devices for firmware flashing.

    Detects and displays USB devices that can be used for flashing firmware.
    Shows device information including name, vendor, mount status, and connection
    details. Supports filtering by device query string and multiple output formats.

    \b
    Device information displayed:
    - Device name and vendor identification
    - Mount point and connection status
    - Device query string for targeting specific devices
    - Compatibility with keyboard profile flash methods

    Examples:
        # List all available devices (default: only removable devices)
        glovebox firmware devices

        # Show all devices including non-removable ones
        glovebox firmware devices --all

        # Filter devices by query string
        glovebox firmware devices --query "nice_nano"

        # Show device list in JSON format
        glovebox firmware devices --output-format json --profile glove80

        # Continuously monitor for device connections/disconnections
        glovebox firmware devices --wait

        # Monitor with specific query filter
        glovebox firmware devices --wait --query "vendor=Adafruit"
    """
    from glovebox.adapters import create_file_adapter
    from glovebox.firmware.flash.device_wait_service import create_device_wait_service

    file_adapter = create_file_adapter()
    device_wait_service = create_device_wait_service()
    flash_service = create_flash_service(file_adapter, device_wait_service)

    # Get icon mode from context for consistent theming
    from glovebox.cli.helpers.theme import get_icon_mode_from_context

    icon_mode = get_icon_mode_from_context(ctx)

    try:
        # Get the keyboard profile from context
        keyboard_profile = get_keyboard_profile_from_context(ctx)

        # Handle --all/-a flag to bypass default filtering
        if all_devices and not query:
            # --all flag bypasses default removable=true filtering by using empty query
            effective_query = ""
        elif query:
            # Explicit query provided
            effective_query = query
        else:
            # No query provided and --all not specified, use None to trigger defaults
            effective_query = None

        # Check if wait mode is requested
        if wait:
            # Continuous monitoring mode using real-time callbacks
            import signal
            import sys
            import threading
            import time
            from collections import deque

            print_success_message(
                "Starting continuous device monitoring (Ctrl+C to stop)..."
            )
            print_list_item(
                f"Query filter: {effective_query or 'None (showing all devices)'}"
            )
            print()

            # Track known devices to show add/remove events
            known_devices: dict[str, dict[str, Any]] = {}  # device_path -> device_info
            monitoring = True
            event_queue: deque[tuple[str, dict[str, Any]]] = (
                deque()
            )  # Thread-safe queue for device events
            event_lock = threading.Lock()
            detector_ref: Any = None  # Will be set after we access the detector

            def format_device_display(device_info: dict[str, Any]) -> str:
                """Format device info for display."""
                vendor_id = device_info.get("vendor_id", "N/A")
                product_id = device_info.get("product_id", "N/A")
                volume_name = device_info.get("name", "N/A")
                return f"{device_info['name']} - Serial: {device_info['serial']} - VID: {vendor_id} - PID: {product_id} - Path: {device_info['path']}"

            def matches_query(device: Any) -> bool:
                """Check if device matches the current query filter."""
                if not effective_query:
                    return True

                # Parse and evaluate query conditions
                try:
                    # Use the detector instance we have to evaluate the query
                    if (
                        detector_ref
                        and hasattr(detector_ref, "parse_query")
                        and hasattr(detector_ref, "evaluate_condition")
                    ):
                        conditions = detector_ref.parse_query(effective_query)

                        for field, operator, value in conditions:
                            if not detector_ref.evaluate_condition(
                                device, field, operator, value
                            ):
                                return False
                        return True
                    else:
                        # Fallback if detector not available
                        return True
                except Exception:
                    # If query parsing fails, include the device
                    return True

            def device_callback(action: str, device: BlockDevice) -> None:
                """Callback for real-time device events."""
                if not monitoring:
                    return

                # Check if device matches query filter
                if not matches_query(device):
                    return

                # Convert BlockDevice to device_info dict for display
                device_info = {
                    "name": getattr(device, "name", "Unknown"),
                    "serial": getattr(device, "serial", "Unknown"),
                    "vendor_id": getattr(device, "vendor_id", "N/A"),
                    "product_id": getattr(device, "product_id", "N/A"),
                    "path": getattr(device, "device_node", None)
                    or getattr(device, "sys_path", "Unknown"),
                    "vendor": getattr(device, "vendor", "Unknown"),
                    "model": getattr(device, "model", "Unknown"),
                }

                # Queue the event for processing in main thread
                with event_lock:
                    event_queue.append((action, device_info))

            # Handle Ctrl+C gracefully
            def signal_handler(sig: int, frame: Any) -> None:
                nonlocal monitoring
                print()
                print_success_message("Stopping device monitoring...")
                monitoring = False
                sys.exit(0)

            signal.signal(signal.SIGINT, signal_handler)

            try:
                # Access the device detector through the USB adapter
                usb_adapter = getattr(flash_service, "usb_adapter", None)
                if not usb_adapter:
                    print_error_message("USB adapter not available")
                    raise typer.Exit(1)

                detector = getattr(usb_adapter, "detector", None)
                if not detector:
                    print_error_message(
                        "Device monitoring not available in this environment"
                    )
                    raise typer.Exit(1)

                # Set the detector reference for use in matches_query
                detector_ref = detector

                # Register our callback for real-time events
                detector.register_callback(device_callback)

                # Start monitoring if not already started
                detector.start_monitoring()

                # Show initial devices
                initial_result = flash_service.list_devices(
                    profile=keyboard_profile,
                    query=effective_query,
                )

                if initial_result.success and initial_result.device_details:
                    print_success_message(
                        f"Currently connected devices: {len(initial_result.device_details)}"
                    )
                    for device_info in initial_result.device_details:
                        known_devices[device_info["path"]] = device_info
                        print_list_item(format_device_display(device_info))
                    print()
                else:
                    print_list_item("No devices currently connected")
                    print()

                print_list_item("Monitoring for device changes (real-time)...")

                # Main loop - process events from the queue
                while monitoring:
                    # Process any queued events
                    events_to_process = []
                    with event_lock:
                        while event_queue:
                            events_to_process.append(event_queue.popleft())

                    for action, device_info in events_to_process:
                        timestamp = time.strftime("%H:%M:%S")
                        path = device_info["path"]

                        if action == "add" and path not in known_devices:
                            print(
                                f"[{timestamp}] {Icons.get_icon('SUCCESS', icon_mode)} Device connected: {format_device_display(device_info)}"
                            )
                            known_devices[path] = device_info
                        elif action == "remove" and path in known_devices:
                            print(
                                f"[{timestamp}] {Icons.get_icon('ERROR', icon_mode)} Device disconnected: {format_device_display(device_info)}"
                            )
                            del known_devices[path]

                    # Small sleep to prevent busy-waiting
                    time.sleep(0.1)

            except KeyboardInterrupt:
                # This should be caught by signal handler, but just in case
                pass
            finally:
                monitoring = False
                # Unregister callback and stop monitoring
                if detector:
                    detector.unregister_callback(device_callback)
                    # Note: We don't stop monitoring here as other parts of the app might be using it

        else:
            # Normal one-time listing mode
            result = flash_service.list_devices(
                profile=keyboard_profile,
                query=effective_query,
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
                    from glovebox.cli.helpers.output_formatter import (
                        DeviceListFormatter,
                    )

                    formatter = DeviceListFormatter()
                    formatter.format_device_list(result.device_details, "table")
                else:
                    # Text output (default)
                    print_success_message(
                        f"Found {len(result.device_details)} device(s)"
                    )
                    for device in result.device_details:
                        vendor_id = device.get("vendor_id", "N/A")
                        product_id = device.get("product_id", "N/A")
                        print_list_item(
                            f"{device['name']} - Serial: {device['serial']} - VID: {vendor_id} - PID: {product_id} - Path: {device['path']}"
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
