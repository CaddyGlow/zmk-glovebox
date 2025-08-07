"""Refactored firmware compile command using IOCommand pattern."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from glovebox.core.structlog_logger import get_struct_logger


if TYPE_CHECKING:
    from glovebox.compilation.cache.compilation_build_cache_service import (
        CompilationBuildCacheService,
    )
    from glovebox.compilation.cache.workspace_cache_service import (
        ZmkWorkspaceCacheService,
    )
    from glovebox.compilation.models import CompilationConfigUnion
    from glovebox.config.profile import KeyboardProfile
    from glovebox.config.user_config import UserConfig
    from glovebox.core.cache.cache_manager import CacheManager
    from glovebox.core.file_operations.models import CompilationProgressCallback
    from glovebox.firmware.models import BuildResult
    from glovebox.protocols.progress_coordinator_protocol import (
        ProgressCoordinatorProtocol,
    )

from glovebox.cli.commands.firmware.base import FirmwareOutputCommand
from glovebox.cli.decorators import (
    handle_errors,
    with_cache,
    with_metrics,
    with_profile,
    with_tmpdir,
)
from glovebox.cli.helpers.parameter_factory import ParameterFactory
from glovebox.cli.helpers.parameter_helpers import resolve_firmware_input_file
from glovebox.cli.helpers.parameters import ProfileOption
from glovebox.cli.helpers.profile import (
    get_keyboard_profile_from_context,
    get_user_config_from_context,
)


logger = get_struct_logger(__name__)


class CompileFirmwareCommand(FirmwareOutputCommand):
    """Command to compile firmware from keymap/config files or JSON layout."""

    def __init__(self) -> None:
        super().__init__()
        self._temp_stdin_file: Path | None = None

    def execute(
        self,
        ctx: typer.Context,
        input_file: str | None,
        config_file: Path | None,
        profile: "KeyboardProfile | None",
        strategy: str | None,
        output_format: str,
        progress: bool | None,
        show_logs: bool,
        debug: bool,
        output: Path | None,
        config_flags: list[str] | None,
    ) -> None:
        """Execute the compile firmware command."""
        try:
            # Resolve input file
            resolved_input_file = self._resolve_input_file(input_file)

            # Validate profile
            if profile is None:
                raise ValueError(
                    "No keyboard profile available. Profile is required for firmware compilation."
                )

            # Detect input type and setup parameters
            is_json_input = resolved_input_file.suffix.lower() == ".json"

            # Get build directory and compilation parameters
            from glovebox.cli.commands.firmware.helpers import (
                cleanup_temp_directory,
                get_build_output_dir,
                get_cache_services_with_fallback,
                prepare_config_file,
                resolve_compilation_type,
                setup_progress_display,
                update_config_from_profile,
            )

            build_output_dir, manual_cleanup_needed = get_build_output_dir(output, ctx)
            compilation_type, compile_config = resolve_compilation_type(
                profile, strategy, ctx
            )

            # TODO: we don't need to update the config from the profile here TBC
            update_config_from_profile(compile_config, profile)

            # Setup progress display
            show_progress = progress if progress is not None else True
            progress_display, progress_coordinator, progress_callback = (
                setup_progress_display(ctx, show_progress)
            )

            # Get cache services
            cache_manager, workspace_service, build_service = (
                get_cache_services_with_fallback(ctx)
            )

            try:
                # Prepare config file
                # TODO: we should create it later if json we will need to merge
                # it with the config flag set in the file
                effective_config_file = prepare_config_file(
                    is_json_input, config_file, config_flags, build_output_dir
                )

                # Execute compilation
                from glovebox.config import create_user_config

                user_config = get_user_config_from_context(ctx) or create_user_config()

                if is_json_input:
                    result = self._execute_json_compilation(
                        compilation_type,
                        resolved_input_file,
                        build_output_dir,
                        compile_config,
                        profile,
                        ctx,
                        user_config,
                        progress_coordinator,
                        progress_callback,
                        cache_manager,
                        workspace_service,
                        build_service,
                    )
                else:
                    if effective_config_file is None:
                        raise ValueError(
                            "Config file is required for keymap compilation"
                        )
                    result = self._execute_keymap_compilation(
                        compilation_type,
                        resolved_input_file,
                        effective_config_file,
                        build_output_dir,
                        compile_config,
                        profile,
                        ctx,
                        user_config,
                        progress_coordinator,
                        progress_callback,
                        cache_manager,
                        workspace_service,
                        build_service,
                    )

                # Process results
                if result.success:
                    from glovebox.cli.commands.firmware.helpers import (
                        format_compilation_output,
                        process_compilation_output,
                    )

                    process_compilation_output(result, resolved_input_file, output)
                    format_compilation_output(
                        result, output_format, build_output_dir, ctx
                    )
                else:
                    raise ValueError(f"Compilation failed: {'; '.join(result.errors)}")

            finally:
                cleanup_temp_directory(build_output_dir, manual_cleanup_needed)
                self._cleanup_temp_stdin_file()

        except Exception as e:
            self.handle_service_error(e, "compile firmware")

    def _resolve_input_file(self, input_file: str | None) -> Path:
        """Resolve input file path, including stdin support."""
        from glovebox.cli.helpers.parameter_helpers import (
            process_input_parameter,
            read_input_from_result,
        )

        try:
            # Process input parameter with stdin support
            result = process_input_parameter(
                input_file,
                supports_stdin=True,
                env_fallback="GLOVEBOX_JSON_FILE",
                required=True,
                validate_existence=False,  # Don't validate stdin
                allowed_extensions=[".json", ".keymap"],
            )

            # Handle stdin input
            if result.is_stdin:
                # Read data from stdin
                content = read_input_from_result(result, as_json=False, as_binary=False)
                if not content or not content.strip():
                    raise ValueError("No data provided on stdin")

                # Determine file type from content
                import json
                import tempfile

                # Try to parse as JSON to determine type
                try:
                    json.loads(content)
                    file_suffix = ".json"
                except json.JSONDecodeError:
                    # Assume it's a keymap file if not JSON
                    file_suffix = ".keymap"

                # Create temporary file
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=file_suffix, delete=False, encoding="utf-8"
                ) as tmp_file:
                    tmp_file.write(content)
                    temp_path = Path(tmp_file.name)
                    self._temp_stdin_file = temp_path
                    logger.debug(
                        "Created temporary file for stdin input: %s", temp_path
                    )
                    return temp_path

            # Handle file path input
            elif result.resolved_path:
                # For library references, pass the raw value; for regular files, pass the resolved path
                input_to_resolve = (
                    result.raw_value
                    if str(result.raw_value).startswith("@")
                    else result.resolved_path
                )
                resolved_input_file = resolve_firmware_input_file(
                    input_to_resolve,
                    env_var="GLOVEBOX_JSON_FILE",
                    allowed_extensions=[".json", ".keymap"],
                )
                if resolved_input_file is None:
                    raise ValueError("Could not resolve input file")
                return resolved_input_file

            else:
                raise ValueError(
                    "Input file is required. Provide as argument or set GLOVEBOX_JSON_FILE environment variable."
                )

        except (FileNotFoundError, ValueError) as e:
            raise ValueError(str(e)) from e

    def _cleanup_temp_stdin_file(self) -> None:
        """Clean up temporary file created from stdin input."""
        if self._temp_stdin_file and self._temp_stdin_file.exists():
            try:
                self._temp_stdin_file.unlink()
                logger.debug(
                    "Cleaned up temporary stdin file: %s", self._temp_stdin_file
                )
            except Exception as cleanup_error:
                exc_info = logger.isEnabledFor(logging.DEBUG)
                logger.warning(
                    "Failed to clean up temporary stdin file: %s",
                    cleanup_error,
                    exc_info=exc_info,
                )
            finally:
                self._temp_stdin_file = None

    def _execute_json_compilation(
        self,
        compilation_type: str,
        json_file: Path,
        build_output_dir: Path,
        compile_config: "CompilationConfigUnion",
        profile: "KeyboardProfile",
        ctx: typer.Context,
        user_config: "UserConfig",
        progress_coordinator: "ProgressCoordinatorProtocol | None",
        progress_callback: "CompilationProgressCallback | None",
        cache_manager: "CacheManager",
        workspace_service: "ZmkWorkspaceCacheService",
        build_service: "CompilationBuildCacheService",
    ) -> "BuildResult":
        """Execute JSON file compilation."""
        from glovebox.adapters import create_docker_adapter, create_file_adapter
        from glovebox.compilation import create_compilation_service

        # Create adapters directly
        docker_adapter = create_docker_adapter()
        file_adapter = create_file_adapter()

        # Create compilation service directly
        compilation_service = create_compilation_service(
            compilation_type,
            user_config=user_config,
            docker_adapter=docker_adapter,
            file_adapter=file_adapter,
            cache_manager=cache_manager,
            workspace_cache_service=workspace_service,
            build_cache_service=build_service,
            session_metrics=ctx.obj.session_metrics,
        )

        # Call service method directly
        return compilation_service.compile_from_json(
            json_file=json_file,
            output_dir=build_output_dir,
            config=compile_config,
            keyboard_profile=profile,
            progress_callback=progress_callback,
        )

    def _execute_keymap_compilation(
        self,
        compilation_type: str,
        keymap_file: Path,
        config_file: Path,
        build_output_dir: Path,
        compile_config: "CompilationConfigUnion",
        profile: "KeyboardProfile",
        ctx: typer.Context,
        user_config: "UserConfig",
        progress_coordinator: "ProgressCoordinatorProtocol | None",
        progress_callback: "CompilationProgressCallback | None",
        cache_manager: "CacheManager",
        workspace_service: "ZmkWorkspaceCacheService",
        build_service: "CompilationBuildCacheService",
    ) -> "BuildResult":
        """Execute keymap file compilation."""
        from glovebox.adapters import create_docker_adapter, create_file_adapter
        from glovebox.compilation import create_compilation_service

        # Create adapters directly
        docker_adapter = create_docker_adapter()
        file_adapter = create_file_adapter()

        # Create compilation service directly
        compilation_service = create_compilation_service(
            compilation_type,
            user_config=user_config,
            docker_adapter=docker_adapter,
            file_adapter=file_adapter,
            cache_manager=cache_manager,
            workspace_cache_service=workspace_service,
            build_cache_service=build_service,
            session_metrics=ctx.obj.session_metrics,
        )

        # Call service method directly
        return compilation_service.compile(
            keymap_file=keymap_file,
            config_file=config_file,
            output_dir=build_output_dir,
            config=compile_config,
            keyboard_profile=profile,
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
        ),
    ] = None,
) -> None:
    """Build ZMK firmware from keymap/config files or JSON layout.

    Compiles .keymap and .conf files, or a .json layout file, into a flashable
    .uf2 firmware file using Docker and the ZMK build system. Requires Docker to be running.

    For JSON input, the layout is automatically converted to .keymap and .conf files
    before compilation. The config_file argument is optional for both JSON and keymap input.
    Config flags can be added using -D options (e.g., -D ZMK_SLEEP=y).

    Output behavior:
    - With --output: Creates build files in specified directory (traditional behavior)
    - Without --output: Creates {filename}.uf2 and {filename}_artefacts.zip in current directory
    - Split keyboards: Creates {filename}_lh.uf2 and {filename}_rh.uf2 for left/right hands
    - Unified firmware: Creates {filename}.uf2 file (when available)
    - Both unified and split files can be created simultaneously

    Profile precedence (highest to lowest):
    1. CLI --profile flag (overrides all)
    2. Auto-detection from JSON keyboard field (unless --no-auto)
    3. User config default profile
    4. Hardcoded fallback profile

    Supports multiple compilation strategies:
    - zmk_config: ZMK config repository builds (default, recommended)
    - moergo: Moergo-specific compilation strategy

    Configuration options like Docker settings, workspace management, and build
    parameters are managed through profile configurations and user config files.

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
    keyboard_profile = get_keyboard_profile_from_context(ctx)

    command = CompileFirmwareCommand()
    command.execute(
        ctx=ctx,
        input_file=input_file,
        config_file=config_file,
        profile=keyboard_profile,
        strategy=strategy,
        output_format=output_format,
        progress=progress,
        show_logs=show_logs,
        debug=debug,
        output=output,
        config_flags=config_flags,
    )
