"""Firmware compile command implementation."""

import logging
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
from glovebox.cli.helpers import print_error_message
from glovebox.cli.helpers.parameter_factory import ParameterFactory
from glovebox.cli.helpers.parameter_helpers import resolve_firmware_input_file
from glovebox.cli.helpers.parameters import ProfileOption, complete_config_flags
from glovebox.cli.helpers.profile import (
    get_keyboard_profile_from_context,
    get_user_config_from_context,
)
from glovebox.cli.helpers.theme import Icons
from glovebox.compilation.models import CompilationConfigUnion

from .helpers import (
    cleanup_temp_directory,
    create_compilation_service_with_progress,
    format_compilation_output,
    get_build_output_dir,
    get_cache_services_with_fallback,
    prepare_config_file,
    process_compilation_output,
    resolve_compilation_type,
    setup_progress_display,
    update_config_from_profile,
)


logger = logging.getLogger(__name__)


def execute_compilation_service(
    compilation_strategy: str,
    keymap_file: Path,
    kconfig_file: Path,
    build_output_dir: Path,
    compile_config: CompilationConfigUnion,
    keyboard_profile: Any,
    session_metrics: Any = None,
    user_config: Any = None,
    progress_coordinator: Any = None,
    progress_callback: Any = None,
    cache_manager: Any = None,
    workspace_cache_service: Any = None,
    build_cache_service: Any = None,
) -> Any:
    """Execute the compilation service."""
    compilation_service = create_compilation_service_with_progress(
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


def execute_compilation_from_json(
    compilation_strategy: str,
    json_file: Path,
    build_output_dir: Path,
    compile_config: CompilationConfigUnion,
    keyboard_profile: Any,
    session_metrics: Any = None,
    user_config: Any = None,
    progress_coordinator: Any = None,
    progress_callback: Any = None,
    cache_manager: Any = None,
    workspace_cache_service: Any = None,
    build_cache_service: Any = None,
) -> Any:
    """Execute compilation from JSON layout file."""
    compilation_service = create_compilation_service_with_progress(
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


@handle_errors
@with_profile(required=True, firmware_optional=False, support_auto_detection=True)
@with_metrics("compile")
@with_cache("compilation", compilation_cache=True)
@with_tmpdir(prefix="glovebox_build_", cleanup=True)
def compile(
    ctx: typer.Context,
    input_file: ParameterFactory.input_file_with_stdin_optional(  # type: ignore[valid-type]
        env_var="GLOVEBOX_JSON_FILE",
        help_text="Path to keymap (.keymap) or layout (.json) file, @library-name/uuid, or '-' for stdin. Can use GLOVEBOX_JSON_FILE env var for JSON files.",
        library_resolvable=True,
    ) = None,
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
    # Initialize variables that might be referenced in error handlers
    progress_display = None
    build_output_dir = None
    manual_cleanup_needed = False

    try:
        # Determine if progress should be shown (default: enabled)
        show_progress = progress if progress is not None else True

        # Create progress display components
        progress_display, progress_coordinator, progress_callback = (
            setup_progress_display(ctx, show_progress)
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
        build_output_dir, manual_cleanup_needed = get_build_output_dir(output, ctx)

        compilation_type, compile_config = resolve_compilation_type(
            keyboard_profile, strategy
        )

        # Update config with profile firmware settings
        update_config_from_profile(compile_config, keyboard_profile)

        # Get cache services from context (provided by @with_cache decorator)
        cache_manager, workspace_service, build_service = (
            get_cache_services_with_fallback(ctx)
        )

        # Execute compilation
        logger.info(
            "%s Starting firmware compilation...", Icons.get_icon("BUILD", "text")
        )

        # Handle config file creation for keymap files
        effective_config_file = prepare_config_file(
            is_json_input, config_file, config_flags, build_output_dir
        )

        # Execute compilation based on input type
        if is_json_input:
            result = execute_compilation_from_json(
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
            result = execute_compilation_service(
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
            process_compilation_output(result, resolved_input_file, output)

        # Format and display results
        format_compilation_output(result, output_format, build_output_dir)

        # Clean up progress display after completion (success or failure)
        if progress_display:
            progress_display.stop()

        # Clean up temporary build directory if needed (only for manual temp dirs)
        cleanup_temp_directory(build_output_dir, manual_cleanup_needed)

    except Exception as e:
        # Clean up progress display if it was used
        if progress_display:
            progress_display.stop()

        print_error_message(f"Firmware compilation failed: {str(e)}")
        logger.exception("Compilation error details")

        # Clean up temporary build directory if needed (only for manual temp dirs)
        if (
            "build_output_dir" in locals()
            and build_output_dir is not None
            and "manual_cleanup_needed" in locals()
        ):
            cleanup_temp_directory(build_output_dir, manual_cleanup_needed)

        raise typer.Exit(1) from None
