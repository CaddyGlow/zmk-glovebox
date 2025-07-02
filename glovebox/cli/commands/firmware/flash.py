"""Firmware flash command implementation."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile

from glovebox.cli.decorators import handle_errors, with_metrics, with_profile
from glovebox.cli.helpers import (
    print_error_message,
    print_list_item,
    print_success_message,
)
from glovebox.cli.helpers.parameter_factory import ParameterFactory
from glovebox.cli.helpers.parameters import ProfileOption
from glovebox.cli.helpers.profile import (
    get_keyboard_profile_from_context,
    get_user_config_from_context,
)
from glovebox.firmware.flash import create_flash_service
from glovebox.firmware.flash.models import FlashResult


logger = logging.getLogger(__name__)


@handle_errors
@with_profile(required=False, firmware_optional=True, support_auto_detection=True)
@with_metrics("flash")
def flash(
    ctx: typer.Context,
    firmware_files: ParameterFactory.input_multiple_files(  # type: ignore[valid-type]
        help_text="Path(s) to firmware (.uf2) file(s) or layout (.json) file(s)",
        file_extensions=[".uf2", ".json"],
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
            "--count",
            "-n",
            help="Total number of devices to flash sequentially (0 for infinite)",
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
    """Flash firmware file(s) or JSON layout file(s) to connected keyboard devices.

    Automatically detects USB keyboards in bootloader mode and flashes
    the firmware file(s) sequentially. Supports flashing multiple devices
    simultaneously and multiple firmware files one after the other.

    JSON layout files are automatically compiled to firmware before flashing.
    Profile auto-detection is supported for JSON files containing a 'keyboard' field.

    Wait mode uses real-time USB device monitoring for immediate detection
    when devices are connected. Devices are flashed sequentially as they become
    available until the specified count is reached. Configure defaults in user config file.

    Examples:
        # Flash UF2 firmware (requires profile)
        glovebox firmware flash firmware.uf2 --profile glove80/v25.05

        # Flash JSON layout (auto-detects profile from 'keyboard' field)
        glovebox firmware flash my_layout.json

        # Flash JSON layout with explicit profile (overrides auto-detection)
        glovebox firmware flash my_layout.json --profile glove80/v25.05

        # Flash multiple firmwares sequentially (e.g., left and right halves)
        glovebox firmware flash left.uf2 right.uf2 --profile glove80/v25.05

        # Mix JSON and UF2 files (JSON will be compiled first)
        glovebox firmware flash my_layout.json firmware.uf2 --profile glove80/v25.05

        # Enable wait mode with CLI flags
        glovebox firmware flash firmware.uf2 --wait --timeout 120

        # Flash 2 devices sequentially with custom polling
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
    try:
        keyboard_profile = get_keyboard_profile_from_context(ctx)

        # Check if any of the files are JSON files that need compilation
        json_files = [f for f in firmware_files if f.suffix.lower() == ".json"]
        uf2_files = [f for f in firmware_files if f.suffix.lower() == ".uf2"]

        # Handle JSON files - compile them to firmware first
        compiled_firmware_files = []
        if json_files:
            # If we have JSON files but no profile, try auto-detection
            if keyboard_profile is None and json_files:
                from glovebox.cli.helpers.auto_profile import extract_keyboard_from_json
                from glovebox.config import create_keyboard_profile

                # Try to auto-detect from the first JSON file
                first_json = json_files[0]
                keyboard_name = extract_keyboard_from_json(first_json)
                if keyboard_name:
                    keyboard_profile = create_keyboard_profile(keyboard_name)
                    from glovebox.cli.helpers.profile import (
                        set_keyboard_profile_in_context,
                    )

                    set_keyboard_profile_in_context(ctx, keyboard_profile)

            # If we still don't have a profile after auto-detection, that's an error
            if keyboard_profile is None:
                print_error_message(
                    "No keyboard profile available. Profile is required for JSON file compilation. "
                    "Use --profile flag or ensure JSON file contains 'keyboard' field for auto-detection."
                )
                raise typer.Exit(1)

            # Compile each JSON file to firmware
            for json_file in json_files:
                compiled_firmware = _compile_json_to_firmware(
                    json_file, keyboard_profile, ctx
                )
                compiled_firmware_files.extend(compiled_firmware)

        # Add original UF2 files to the list
        all_firmware_files = uf2_files + compiled_firmware_files

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

        for i, firmware_file in enumerate(all_firmware_files):
            print_success_message(
                f"Flashing firmware {i + 1}/{len(all_firmware_files)}: {firmware_file.name}"
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
                    f"Successfully flashed {len(all_firmware_files)} firmware file(s) to {result.devices_flashed} device(s) total"
                )
                if result.device_details:
                    for device in result.device_details:
                        if device["status"] == "success":
                            print_list_item(f"{device['name']}: SUCCESS")
        else:
            print_error_message(
                f"Flash completed with {result.devices_failed} failure(s) across {len(all_firmware_files)} firmware file(s)"
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


def _compile_json_to_firmware(
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

    from glovebox.cli.commands.firmware.helpers import (
        create_compilation_service_with_progress,
        get_cache_services_with_fallback,
        resolve_compilation_type,
        update_config_from_profile,
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
                keyboard_profile, None
            )

            # Update config with profile settings
            update_config_from_profile(compile_config, keyboard_profile)

            # Get cache services
            cache_manager, workspace_cache_service, build_cache_service = (
                get_cache_services_with_fallback(ctx)
            )

            # Create compilation service
            compilation_service = create_compilation_service_with_progress(
                compilation_strategy,
                user_config,
                ctx.obj.session_metrics,
                None,  # No progress coordinator for flash compilation
                cache_manager,
                workspace_cache_service,
                build_cache_service,
            )

            # Compile the JSON file
            result = compilation_service.compile_from_json(
                json_file_path=json_file,
                profile=keyboard_profile,
                output_dir=temp_dir,
            )

            if not result.success:
                print_error_message(
                    f"Failed to compile {json_file.name}: {'; '.join(result.errors)}"
                )
                raise typer.Exit(1)

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
                raise typer.Exit(1)

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
        raise typer.Exit(1) from None
