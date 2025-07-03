"""Firmware devices command implementation."""

import logging
import signal
import sys
import threading
import time
from collections import deque
from typing import Annotated, Any

import typer

from glovebox.cli.decorators import handle_errors, with_profile
from glovebox.cli.helpers.parameter_factory import ParameterFactory
from glovebox.cli.helpers.parameters import ProfileOption
from glovebox.cli.helpers.profile import get_keyboard_profile_from_context
from glovebox.cli.helpers.theme import (
    Icons,
    get_icon_mode_from_context,
    get_themed_console,
)
from glovebox.firmware.flash.models import BlockDevice


logger = logging.getLogger(__name__)


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
    from glovebox.firmware.flash import create_flash_service
    from glovebox.firmware.flash.device_wait_service import create_device_wait_service

    file_adapter = create_file_adapter()
    device_wait_service = create_device_wait_service()
    flash_service = create_flash_service(file_adapter, device_wait_service)

    # Get themed console and icon mode from context for consistent theming
    console = get_themed_console()
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
            console.print_success(
                "Starting continuous device monitoring (Ctrl+C to stop)..."
            )
            console.print_list_item(
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
                console.print_success("Stopping device monitoring...")
                monitoring = False
                sys.exit(0)

            signal.signal(signal.SIGINT, signal_handler)

            try:
                # Access the device detector through the USB adapter
                usb_adapter = getattr(flash_service, "usb_adapter", None)
                if not usb_adapter:
                    console.print_error("USB adapter not available")
                    raise typer.Exit(1)

                detector = getattr(usb_adapter, "detector", None)
                if not detector:
                    console.print_error(
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
                    console.print_success(
                        f"Currently connected devices: {len(initial_result.device_details)}"
                    )
                    for device_info in initial_result.device_details:
                        known_devices[device_info["path"]] = device_info
                        console.print_list_item(format_device_display(device_info))
                    print()
                else:
                    console.print_list_item("No devices currently connected")
                    print()

                console.print_list_item("Monitoring for device changes (real-time)...")

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
                    console.print_success(
                        f"Found {len(result.device_details)} device(s)"
                    )
                    for device in result.device_details:
                        vendor_id = device.get("vendor_id", "N/A")
                        product_id = device.get("product_id", "N/A")
                        console.print_list_item(
                            f"{device['name']} - Serial: {device['serial']} - VID: {vendor_id} - PID: {product_id} - Path: {device['path']}"
                        )
            else:
                console.print_error("No devices found matching criteria")
                for message in result.messages:
                    console.print_list_item(message)
    except Exception as e:
        console.print_error(f"Error listing devices: {str(e)}")
        raise typer.Exit(1) from None
