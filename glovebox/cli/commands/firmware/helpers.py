"""Helper functions for firmware commands."""

import logging
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile

import typer

from glovebox.cli.decorators.profile import (
    get_compilation_cache_services_from_context,
    get_tmpdir_from_context,
)
from glovebox.cli.helpers import (
    print_error_message,
    print_list_item,
    print_success_message,
)
from glovebox.cli.helpers.profile import get_user_config_from_context
from glovebox.compilation.cache.compilation_build_cache_service import (
    CompilationBuildCacheService,
)
from glovebox.compilation.cache.workspace_cache_service import ZmkWorkspaceCacheService
from glovebox.compilation.models import CompilationConfigUnion
from glovebox.config.models.filename_templates import FilenameTemplateConfig
from glovebox.config.profile import KeyboardProfile
from glovebox.core.cache.cache_manager import CacheManager
from glovebox.core.file_operations.models import (
    CompilationProgress,
    CompilationProgressCallback,
)
from glovebox.core.structlog_logger import get_struct_logger
from glovebox.firmware.models import BuildResult


logger = get_struct_logger(__name__)


def resolve_compilation_type(
    keyboard_profile: KeyboardProfile, strategy: str | None, ctx: typer.Context
) -> tuple[str, CompilationConfigUnion]:
    """Resolve compilation type and config from profile."""
    # Get the appropriate compile method config from the keyboard profile
    if not keyboard_profile.keyboard_config.compile_methods:
        print_error_message(
            f"No compile methods configured for keyboard '{keyboard_profile.keyboard_name}'"
        )
        ctx.exit(1)

    # Determine compilation strategy
    from glovebox.compilation.models import (
        MoergoCompilationConfig,
        ZmkCompilationConfig,
    )

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
        ctx.exit(1)

    # At this point, compile_config is guaranteed to be not None
    compilation_strategy = compile_config.method_type

    return compilation_strategy, compile_config


def update_config_from_profile(
    compile_config: CompilationConfigUnion,
    keyboard_profile: KeyboardProfile,
) -> None:
    """Update compile config with firmware settings from profile."""
    if keyboard_profile.firmware_config is not None:
        compile_config.branch = keyboard_profile.firmware_config.build_options.branch
        compile_config.repository = (
            keyboard_profile.firmware_config.build_options.repository
        )


def format_compilation_output(
    result: BuildResult, output_format: str, output_dir: Path, ctx: typer.Context
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
        ctx.exit(1)


def determine_firmware_outputs(
    result: BuildResult,
    base_filename: str,
    templates: FilenameTemplateConfig | None = None,
    layout_data: dict[str, str] | None = None,
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


def process_compilation_output(
    result: BuildResult, input_file: Path, output_dir: Path | None
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
        firmware_outputs = determine_firmware_outputs(
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
        logger.error(
            "failed_to_process_compilation_output", error=str(e), exc_info=exc_info
        )
        print_error_message(f"Failed to create output files: {str(e)}")


def setup_progress_display(
    ctx: typer.Context, show_progress: bool
) -> tuple[None, None, CompilationProgressCallback | None]:
    """Set up progress display components.

    Args:
        ctx: Typer context with user config
        show_progress: Whether to show progress

    Returns:
        Tuple of (progress_display, progress_coordinator, progress_callback)
    """
    if not show_progress:
        return None, None, None

    # New progress system: Let compilation services handle their own progress management
    # by providing a simple callback that signals progress is enabled

    def progress_callback(progress: CompilationProgress) -> None:
        """Simple progress callback that enables progress tracking in compilation services."""
        # The compilation services now handle their own progress display using progress managers
        # This callback just needs to exist to signal that progress is enabled
        pass

    # Return None for display and coordinator since services handle their own
    return None, None, progress_callback


def get_cache_services_with_fallback(
    ctx: typer.Context,
) -> tuple[CacheManager, ZmkWorkspaceCacheService, CompilationBuildCacheService]:
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


def get_build_output_dir(output: Path | None, ctx: typer.Context) -> tuple[Path, bool]:
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
            temp_dir = tempfile.mkdtemp(prefix="glovebox_build_")
            build_output_dir = Path(temp_dir)
            logger.warning(
                "Using fallback temporary directory due to decorator issue: %s",
                build_output_dir,
            )
            return build_output_dir, True


def prepare_config_file(
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

    # Case 1: Need to create or augment config file with flags
    if effective_config_flags:
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

    # Case 2: Use provided config file as-is
    if config_file is not None:
        return config_file

    # Case 3: No config file provided and no flags - create empty config
    temp_config_file = build_output_dir / "empty_config.conf"
    temp_config_file.write_text("")
    logger.info("Created empty config file for keymap compilation")
    return temp_config_file


def cleanup_temp_directory(build_output_dir: Path, manual_cleanup_needed: bool) -> None:
    """Clean up temporary build directory if needed.

    Args:
        build_output_dir: Directory to clean up
        manual_cleanup_needed: Whether manual cleanup is required
    """
    if manual_cleanup_needed and build_output_dir.exists():
        try:
            shutil.rmtree(build_output_dir)
            logger.debug("Cleaned up temporary build directory: %s", build_output_dir)
        except Exception as cleanup_error:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.warning(
                "Failed to clean up temporary build directory: %s",
                cleanup_error,
                exc_info=exc_info,
            )


def compile_json_to_firmware(
    json_file: Path, keyboard_profile: "KeyboardProfile", ctx: typer.Context
) -> list[Path]:
    """Compile JSON file to firmware and return list of UF2 files.

    Args:
        json_file: Path to JSON layout file
        keyboard_profile: Keyboard profile for compilation
        ctx: Typer context

    Returns:
        List of compiled UF2 firmware file paths

    Raises:
        typer.Exit: If compilation fails
    """
    import shutil
    from pathlib import Path
    from tempfile import mkdtemp

    from glovebox.cli.helpers import (
        print_error_message,
        print_success_message,
    )
    from glovebox.cli.helpers.profile import get_user_config_from_context
    from glovebox.config import create_user_config

    print_success_message(f"Compiling JSON layout to firmware: {json_file.name}")

    try:
        # Get user config
        user_config = get_user_config_from_context(ctx) or create_user_config()

        # Create temporary directory for compilation output
        temp_dir = Path(mkdtemp(prefix="glovebox_compile_"))

        try:
            # Resolve compilation strategy and config
            compilation_strategy, compile_config = resolve_compilation_type(
                keyboard_profile, None, ctx
            )

            # Update config with profile settings
            update_config_from_profile(compile_config, keyboard_profile)

            # Get cache services
            cache_manager, workspace_cache_service, build_cache_service = (
                get_cache_services_with_fallback(ctx)
            )

            # Create compilation service directly
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
                session_metrics=ctx.obj.session_metrics,
            )

            # Compile the JSON file
            result = compilation_service.compile_from_json(
                json_file=json_file,
                output_dir=temp_dir,
                config=compile_config,
                keyboard_profile=keyboard_profile,
            )

            if not result.success:
                print_error_message(
                    f"Failed to compile {json_file.name}: {'; '.join(result.errors)}"
                )
                ctx.exit(1)

            # Find all UF2 files in the output
            uf2_files = []
            if result.output_files and result.output_files.uf2_files:
                # Copy UF2 files to persistent location (current directory)
                for uf2_file in result.output_files.uf2_files:
                    if uf2_file.exists():
                        # Create a name based on the original JSON file
                        base_name = json_file.stem
                        if (
                            "lh" in uf2_file.name.lower()
                            or "lf" in uf2_file.name.lower()
                        ):
                            target_name = f"{base_name}_lf.uf2"
                        elif "rh" in uf2_file.name.lower():
                            target_name = f"{base_name}_rh.uf2"
                        else:
                            target_name = f"{base_name}.uf2"

                        target_path = Path(target_name)
                        shutil.copy2(uf2_file, target_path)
                        uf2_files.append(target_path)
                        print_success_message(f"Created firmware file: {target_path}")

            if not uf2_files:
                print_error_message(
                    f"No firmware files were generated from {json_file.name}"
                )
                ctx.exit(1)

            return uf2_files

        finally:
            # Clean up temporary directory
            try:
                shutil.rmtree(temp_dir)
            except Exception as cleanup_error:
                logger.warning(
                    "Failed to clean up temporary directory: %s", cleanup_error
                )

    except Exception as e:
        print_error_message(f"Compilation failed for {json_file.name}: {str(e)}")
        ctx.exit(1)
