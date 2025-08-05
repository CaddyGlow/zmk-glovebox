"""Refactored firmware flash command using IOCommand pattern."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

import typer

from glovebox.core.structlog_logger import get_struct_logger


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


logger = get_struct_logger(__name__)


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
        no_wait: bool,
        poll_interval: float | None,
        show_progress: bool | None,
        paired: bool,
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

            # Enforce max 2 firmware files for simplicity
            if len(all_firmware_files) > 2:
                raise ValueError(
                    "Maximum 2 firmware files supported. "
                    "Use 1 file for standard flashing or 2 files (left/right) for split keyboards."
                )

            # Auto-enable paired mode when exactly 2 files are provided
            if len(all_firmware_files) == 2:
                if not paired:
                    self.console.print_info(
                        "Detected 2 firmware files, enabling paired mode for split keyboard"
                    )
                paired = True

            # Check for paired mode validation
            from glovebox.firmware.flash.firmware_pairing import (
                create_firmware_pairing_service,
            )
            from glovebox.firmware.flash.models import is_split_firmware

            firmware_pairs = []
            if paired:
                if len(all_firmware_files) != 2:
                    raise ValueError(
                        "Paired mode requires exactly 2 firmware files (left and right)"
                    )

                # Validate that we have proper left/right firmware
                pairing_service = create_firmware_pairing_service()
                firmware_pairs = pairing_service.detect_firmware_pairs(
                    all_firmware_files
                )

                if not firmware_pairs:
                    # If no pairs detected, check if files are marked as left/right
                    if not is_split_firmware(all_firmware_files):
                        self.console.print_warning(
                            "Firmware files don't appear to be left/right pairs. "
                            "Files should have _lh/_rh or _left/_right suffixes."
                        )
                    # Create manual pair from the two files
                    from glovebox.firmware.flash.models import (
                        FirmwarePair,
                        detect_firmware_side,
                    )

                    file1_side = detect_firmware_side(all_firmware_files[0])
                    file2_side = detect_firmware_side(all_firmware_files[1])

                    # Determine which is left and which is right
                    if file1_side.value == "left" or (
                        file1_side.value == "unified" and file2_side.value == "right"
                    ):
                        left_file = all_firmware_files[0]
                        right_file = all_firmware_files[1]
                    else:
                        left_file = all_firmware_files[1]
                        right_file = all_firmware_files[0]

                    firmware_pairs = [
                        FirmwarePair(
                            left=left_file, right=right_file, base_name="firmware"
                        )
                    ]

                if firmware_pairs:
                    self.console.print_info(
                        f"Paired mode: {firmware_pairs[0].left.name} (left) + {firmware_pairs[0].right.name} (right)"
                    )

            # Check if this is a split keyboard from profile
            is_split_keyboard = bool(
                profile
                and hasattr(profile, "keyboard_config")
                and hasattr(profile.keyboard_config, "is_split")
                and profile.keyboard_config.is_split
            )

            # Get user config and apply defaults
            user_config = get_user_config_from_context(ctx)
            flash_params = self._get_effective_flash_params(
                user_config,
                timeout,
                count,
                track_flashed,
                skip_existing,
                no_wait,
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

            # If we have pairs, flash them with proper count distribution
            if firmware_pairs and paired:
                pair = firmware_pairs[0]  # We only have one pair now (max 2 files)

                # In paired mode with split keyboards, count represents number of KEYBOARDS
                # Each keyboard has 2 devices (left and right)
                # So count=1 means 1 keyboard (1 left + 1 right = 2 devices total)
                # count=2 means 2 keyboards (2 left + 2 right = 4 devices total)
                device_count_per_side = flash_params["count"]
                total_devices = device_count_per_side * 2

                if is_split_keyboard:
                    self.console.print_info(
                        f"Split keyboard mode: flashing {flash_params['count']} keyboard(s) "
                        f"({total_devices} devices total: {device_count_per_side} left, {device_count_per_side} right)"
                    )
                else:
                    self.console.print_info(
                        f"Paired mode: flashing {flash_params['count']} keyboard(s) "
                        f"({total_devices} devices total: {device_count_per_side} left, {device_count_per_side} right)"
                    )

                # Prepare modified params for each side
                left_params = flash_params.copy()
                left_params["count"] = device_count_per_side

                right_params = flash_params.copy()
                right_params["count"] = device_count_per_side

                # Flash left side first
                self.console.print_info(f"Flashing LEFT: {pair.left.name}")
                left_result = flash_service.flash(
                    firmware_file=pair.left,
                    profile=profile,
                    query=query,
                    paired_mode=True,
                    **left_params,
                )
                all_results.append(left_result)
                total_devices_flashed += left_result.devices_flashed
                total_devices_failed += left_result.devices_failed

                # Flash right side
                self.console.print_info(f"Flashing RIGHT: {pair.right.name}")
                right_result = flash_service.flash(
                    firmware_file=pair.right,
                    profile=profile,
                    query=query,
                    paired_mode=True,
                    **right_params,
                )
                all_results.append(right_result)
                total_devices_flashed += right_result.devices_flashed
                total_devices_failed += right_result.devices_failed

                # Show pair results
                if left_result.success and right_result.success:
                    self.console.print_success(
                        f"Successfully flashed {total_devices_flashed} devices "
                        f"({left_result.devices_flashed} left, {right_result.devices_flashed} right)"
                    )
                elif total_devices_flashed > 0:
                    self.console.print_warning(
                        f"Partially flashed {total_devices_flashed} devices "
                        f"({left_result.devices_flashed} left, {right_result.devices_flashed} right), "
                        f"{total_devices_failed} failed"
                    )
                else:
                    self.console.print_error(
                        f"Failed to flash devices (left: {'OK' if left_result.success else 'FAILED'}, "
                        f"right: {'OK' if right_result.success else 'FAILED'})"
                    )
            else:
                # Single firmware file - but might be for a split keyboard with unified firmware
                firmware_file = all_firmware_files[0]

                if is_split_keyboard:
                    # For split keyboards with unified firmware:
                    # count=1 means flash 1 keyboard (both halves with same firmware)
                    # We need to flash the firmware to 2 devices (left and right)
                    actual_device_count = flash_params["count"] * 2

                    self.console.print_info(
                        f"Split keyboard (unified firmware): flashing {flash_params['count']} keyboard(s) "
                        f"({actual_device_count} devices total with same firmware)"
                    )

                    # Update the count in flash_params for the actual flash operation
                    modified_params = flash_params.copy()
                    modified_params["count"] = actual_device_count
                else:
                    # Non-split keyboard, count is just number of devices
                    self.console.print_info(f"Flashing firmware: {firmware_file.name}")
                    modified_params = flash_params

                result = flash_service.flash(
                    firmware_file=firmware_file,
                    profile=profile,
                    query=query,
                    paired_mode=False,
                    **modified_params,
                )

                all_results.append(result)
                total_devices_flashed += result.devices_flashed
                total_devices_failed += result.devices_failed

            # Create combined result and handle output
            combined_result = self._create_combined_result(
                all_results, total_devices_flashed, total_devices_failed
            )

            self._handle_final_result(
                combined_result,
                len(all_firmware_files),
                output_format,
                ctx,
                is_split_keyboard,
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
        no_wait: bool,
        poll_interval: float | None,
        show_progress: bool | None,
    ) -> dict[str, Any]:
        """Get effective flash parameters with user config defaults."""
        # Convert no_wait to wait (invert the logic)
        wait = not no_wait

        # Handle unlimited timeout (0 means unlimited)
        effective_timeout = timeout if timeout > 0 else float("inf")

        if user_config:
            return {
                "timeout": effective_timeout,
                "count": count,
                "track_flashed": track_flashed,
                "skip_existing": skip_existing
                or user_config._config.firmware.flash.skip_existing,
                "wait": wait,  # Use the inverted no_wait value
                "poll_interval": poll_interval
                if poll_interval is not None
                else user_config._config.firmware.flash.poll_interval,
                "show_progress": show_progress
                if show_progress is not None
                else user_config._config.firmware.flash.show_progress,
            }
        else:
            return {
                "timeout": effective_timeout,
                "count": count,
                "track_flashed": track_flashed,
                "skip_existing": skip_existing,
                "wait": wait,  # Use the inverted no_wait value
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
        self,
        result: FlashResult,
        num_firmware_files: int,
        output_format: str,
        ctx: typer.Context,
        is_split_keyboard: bool,
    ) -> None:
        """Handle final result output."""

        if output_format.lower() == "json":
            result_data = {
                "success": result.success,
                "devices_flashed": result.devices_flashed,
                "devices_failed": result.devices_failed,
                "firmware_files_processed": num_firmware_files,
                "device_details": result.device_details,
            }
            self.format_and_print(result_data, "json")
        else:
            # Display appropriate message based on results
            if result.success:
                if is_split_keyboard:
                    keyboards_flashed = result.devices_flashed // 2
                    self.console.print_success(
                        f"Successfully flashed {keyboards_flashed} keyboard(s) ({result.devices_flashed} devices)"
                    )
                else:
                    self.console.print_success(
                        f"Successfully flashed {result.devices_flashed} device(s)"
                    )
            elif result.devices_flashed > 0:
                # Partial success
                if is_split_keyboard:
                    keyboards_flashed = result.devices_flashed // 2
                    self.console.print_warning(
                        f"Partially flashed {keyboards_flashed} keyboard(s) ({result.devices_flashed} devices), "
                        f"{result.devices_failed} device(s) failed"
                    )
                else:
                    self.console.print_warning(
                        f"Partially flashed {result.devices_flashed} device(s), "
                        f"{result.devices_failed} device(s) failed"
                    )
            else:
                # Complete failure
                self.console.print_error(
                    f"Failed to flash: {result.devices_failed} device(s) failed"
                )

            # Show device details
            if result.device_details:
                for device in result.device_details:
                    if device["status"] == "failed":
                        self.console.print_error(
                            f"✗ {device['name']}: FAILED - {device.get('error', 'Unknown error')}"
                        )

        # Only raise exception if complete failure, not partial success
        if not result.success and result.devices_flashed == 0:
            error_msg = "Failed to flash any devices"
            if result.errors:
                error_msg = result.errors[0]
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
    timeout: Annotated[
        int, typer.Option("--timeout", help="Timeout in seconds (0 for unlimited)")
    ] = 0,
    count: Annotated[
        int,
        typer.Option(
            "--count",
            "-n",
            help="Number of keyboards to flash. For split keyboards: 1 = one complete keyboard (2 devices)",
        ),
    ] = 1,
    no_track: Annotated[
        bool, typer.Option("--no-track", help="Disable device tracking")
    ] = False,
    skip_existing: Annotated[
        bool,
        typer.Option("--skip-existing", help="Skip devices already present at startup"),
    ] = False,
    no_wait: Annotated[
        bool,
        typer.Option(
            "--no-wait",
            help="Disable waiting for devices (flash immediately if devices are present)",
        ),
    ] = False,
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
    paired: Annotated[
        bool,
        typer.Option(
            "--paired",
            help="Enable paired flashing mode for split keyboards (auto-detected for left/right firmware files)",
        ),
    ] = False,
    output_format: ParameterFactory.output_format() = "text",  # type: ignore[valid-type]
) -> None:
    """Flash firmware file(s) or JSON layout file(s) to connected keyboard devices.

    By default, waits for a device to connect and flashes it (wait mode enabled).
    The command will wait indefinitely until a device is detected or interrupted.

    Supports 1 file for standard keyboards or 2 files for split keyboards.
    JSON layout files are automatically compiled to firmware before flashing.

    Default Behavior:
    - Wait mode: ENABLED (waits for devices to connect)
    - Timeout: UNLIMITED (waits indefinitely)
    - Count: 1 keyboard (for split keyboards, this means both halves)
    - Use --no-wait to flash only currently connected devices

    Split Keyboard Support:
    - Provide exactly 2 firmware files (left and right) to enable paired mode
    - Paired mode is auto-enabled when 2 files are provided
    - In paired mode, --count means number of KEYBOARDS (not devices)
      • count=1 flashes 1 keyboard (1 left + 1 right = 2 devices)
      • count=2 flashes 2 keyboards (2 left + 2 right = 4 devices)
    - Files should have _lh/_rh or _left/_right suffixes for proper detection

    Examples:
        # Flash single firmware when device connects (default wait mode)
        glovebox firmware flash firmware.uf2 --profile glove80/v25.05

        # Flash immediately without waiting (only if device already connected)
        glovebox firmware flash firmware.uf2 --profile glove80/v25.05 --no-wait

        # Flash JSON layout (waits for device by default)
        glovebox firmware flash my_layout.json

        # Flash split keyboard (auto-enables paired mode, waits for 1 complete keyboard)
        glovebox firmware flash glove80_lh.uf2 glove80_rh.uf2 --profile glove80/v25.05

        # Flash 2 split keyboards (count=2 means 2 keyboards = 4 devices total)
        glovebox firmware flash left.uf2 right.uf2 --count 2

        # Set a specific timeout instead of unlimited
        glovebox firmware flash firmware.uf2 --timeout 120

        # Flash multiple devices sequentially
        glovebox firmware flash firmware.uf2 --count 3

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
        no_wait=no_wait,
        poll_interval=poll_interval,
        show_progress=show_progress,
        paired=paired,
        output_format=output_format,
    )
