"""Refactored firmware flash command using IOCommand pattern."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

import typer


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile

from glovebox.cli.commands.firmware.base import FirmwareFileCommand
from glovebox.cli.decorators import handle_errors, with_metrics, with_profile
from glovebox.cli.helpers.parameter_factory import ParameterFactory
from glovebox.cli.helpers.parameters import ProfileOption
from glovebox.cli.helpers.profile import (
    get_keyboard_profile_from_context,
    get_user_config_from_context,
)
from glovebox.firmware.flash import create_flash_service
from glovebox.firmware.flash.models import FlashResult


logger = logging.getLogger(__name__)


class FlashFirmwareCommand(FirmwareFileCommand):
    """Command to flash firmware files to devices."""

    def execute(
        self,
        ctx: typer.Context,
        firmware_files: list[Path],
        profile: "KeyboardProfile | None",
        query: str,
        timeout: int,
        count: int,
        track_flashed: bool,
        skip_existing: bool,
        wait: bool | None,
        poll_interval: float | None,
        show_progress: bool | None,
        output_format: str,
    ) -> None:
        """Execute the flash firmware command."""
        try:
            # Validate all firmware files
            for firmware_file in firmware_files:
                self.validate_firmware_file(firmware_file)

            # Check if any of the files are JSON files that need compilation
            json_files = [f for f in firmware_files if f.suffix.lower() == ".json"]
            uf2_files = [f for f in firmware_files if f.suffix.lower() == ".uf2"]

            # Handle JSON files - compile them to firmware first
            compiled_firmware_files = []
            if json_files:
                compiled_firmware_files = self._compile_json_files(
                    json_files, profile, ctx
                )

            # Combine all firmware files
            all_firmware_files = uf2_files + compiled_firmware_files

            # Get user config and apply defaults
            user_config = get_user_config_from_context(ctx)
            flash_params = self._get_effective_flash_params(
                user_config,
                timeout,
                count,
                track_flashed,
                skip_existing,
                wait,
                poll_interval,
                show_progress,
            )

            # Create flash service
            from glovebox.adapters import create_file_adapter
            from glovebox.firmware.flash.device_wait_service import (
                create_device_wait_service,
            )

            file_adapter = create_file_adapter()
            device_wait_service = create_device_wait_service()
            flash_service = create_flash_service(file_adapter, device_wait_service)

            # Flash all firmware files
            all_results = []
            total_devices_flashed = 0
            total_devices_failed = 0

            for i, firmware_file in enumerate(all_firmware_files):
                self.console.print_info(
                    f"Flashing firmware {i + 1}/{len(all_firmware_files)}: {firmware_file.name}"
                )

                result = flash_service.flash(
                    firmware_file=firmware_file,
                    profile=profile,
                    query=query,
                    **flash_params,
                )

                all_results.append(result)
                total_devices_flashed += result.devices_flashed
                total_devices_failed += result.devices_failed

                # Show result for this firmware file
                if result.success:
                    self.console.print_success(
                        f"Firmware {firmware_file.name}: {result.devices_flashed} device(s) flashed"
                    )
                else:
                    self.console.print_error(
                        f"Firmware {firmware_file.name}: {result.devices_failed} device(s) failed"
                    )

            # Create combined result and handle output
            combined_result = self._create_combined_result(
                all_results, total_devices_flashed, total_devices_failed
            )

            self._handle_final_result(
                combined_result, len(all_firmware_files), output_format
            )

        except Exception as e:
            self.handle_service_error(e, "flash firmware")

    def _compile_json_files(
        self,
        json_files: list[Path],
        profile: "KeyboardProfile | None",
        ctx: typer.Context,
    ) -> list[Path]:
        """Compile JSON files to firmware."""
        # If we have JSON files but no profile, try auto-detection
        if profile is None and json_files:
            profile = self._try_auto_detect_profile(json_files[0], ctx)

        if profile is None:
            raise ValueError(
                "No keyboard profile available. Profile is required for JSON file compilation. "
                "Use --profile flag or ensure JSON file contains 'keyboard' field for auto-detection."
            )

        # Import the helper function from helpers
        from glovebox.cli.commands.firmware.helpers import compile_json_to_firmware

        compiled_firmware_files = []
        for json_file in json_files:
            compiled_firmware = compile_json_to_firmware(json_file, profile, ctx)
            compiled_firmware_files.extend(compiled_firmware)

        return compiled_firmware_files

    def _try_auto_detect_profile(
        self, json_file: Path, ctx: typer.Context
    ) -> "KeyboardProfile | None":
        """Try to auto-detect profile from JSON file."""
        try:
            from glovebox.cli.helpers.auto_profile import extract_keyboard_from_json
            from glovebox.cli.helpers.profile import set_keyboard_profile_in_context
            from glovebox.config import create_keyboard_profile

            keyboard_name = extract_keyboard_from_json(json_file)
            if keyboard_name:
                profile = create_keyboard_profile(keyboard_name)
                set_keyboard_profile_in_context(ctx, profile)
                return profile
        except Exception as e:
            logger.debug("Auto-detection failed: %s", e)
        return None

    def _get_effective_flash_params(
        self,
        user_config: Any,
        timeout: int,
        count: int,
        track_flashed: bool,
        skip_existing: bool,
        wait: bool | None,
        poll_interval: float | None,
        show_progress: bool | None,
    ) -> dict[str, Any]:
        """Get effective flash parameters with user config defaults."""
        if user_config:
            return {
                "timeout": timeout
                if timeout != 60
                else user_config._config.firmware.flash.timeout,
                "count": count
                if count != 2
                else user_config._config.firmware.flash.count,
                "track_flashed": track_flashed,
                "skip_existing": skip_existing
                or user_config._config.firmware.flash.skip_existing,
                "wait": wait
                if wait is not None
                else user_config._config.firmware.flash.wait,
                "poll_interval": poll_interval
                if poll_interval is not None
                else user_config._config.firmware.flash.poll_interval,
                "show_progress": show_progress
                if show_progress is not None
                else user_config._config.firmware.flash.show_progress,
            }
        else:
            return {
                "timeout": timeout,
                "count": count,
                "track_flashed": track_flashed,
                "skip_existing": skip_existing,
                "wait": wait if wait is not None else False,
                "poll_interval": poll_interval if poll_interval is not None else 0.5,
                "show_progress": show_progress if show_progress is not None else True,
            }

    def _create_combined_result(
        self,
        all_results: list[FlashResult],
        total_devices_flashed: int,
        total_devices_failed: int,
    ) -> FlashResult:
        """Create combined result from individual flash results."""
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

        return result

    def _handle_final_result(
        self, result: FlashResult, num_firmware_files: int, output_format: str
    ) -> None:
        """Handle final result output."""
        if result.success:
            if output_format.lower() == "json":
                result_data = {
                    "success": True,
                    "devices_flashed": result.devices_flashed,
                    "firmware_files_processed": num_firmware_files,
                    "device_details": result.device_details,
                }
                self.format_and_print(result_data, "json")
            else:
                self.print_operation_success(
                    f"Successfully flashed {num_firmware_files} firmware file(s) to {result.devices_flashed} device(s) total"
                )
                if result.device_details:
                    for device in result.device_details:
                        if device["status"] == "success":
                            self.console.print_info(f"{device['name']}: SUCCESS")
        else:
            error_msg = f"Flash completed with {result.devices_failed} failure(s) across {num_firmware_files} firmware file(s)"
            if result.device_details:
                for device in result.device_details:
                    if device["status"] == "failed":
                        error_msg = device.get("error", "Unknown error")
                        self.console.print_error(
                            f"{device['name']}: FAILED - {error_msg}"
                        )
            raise ValueError(error_msg)


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
    keyboard_profile = get_keyboard_profile_from_context(ctx)

    command = FlashFirmwareCommand()
    command.execute(
        ctx=ctx,
        firmware_files=firmware_files,
        profile=keyboard_profile,
        query=query,
        timeout=timeout,
        count=count,
        track_flashed=not no_track,
        skip_existing=skip_existing,
        wait=wait,
        poll_interval=poll_interval,
        show_progress=show_progress,
        output_format=output_format,
    )
