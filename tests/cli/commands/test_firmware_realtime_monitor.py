"""Test firmware devices --wait command with real-time monitoring."""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
from typer.testing import CliRunner

from glovebox.cli.commands.firmware import firmware_app
from glovebox.firmware.flash.models import BlockDevice, FlashResult


class MockDetector:
    """Mock device detector with callback support."""

    def __init__(self) -> None:
        self.callbacks: set[Any] = set()
        self.monitoring = False
        self._monitor_thread: threading.Thread | None = None

    def register_callback(self, callback: Any) -> None:
        """Register a callback."""
        self.callbacks.add(callback)

    def unregister_callback(self, callback: Any) -> None:
        """Unregister a callback."""
        self.callbacks.discard(callback)

    def start_monitoring(self) -> None:
        """Start monitoring."""
        self.monitoring = True

    def stop_monitoring(self) -> None:
        """Stop monitoring."""
        self.monitoring = False

    def parse_query(self, query: str) -> list[tuple[str, str, str]]:
        """Mock query parsing."""
        if not query:
            return []
        return [("vendor", "=", "TestVendor")]

    def evaluate_condition(
        self, device: Any, field: str, operator: str, value: str
    ) -> bool:
        """Mock condition evaluation."""
        if field == "vendor":
            return getattr(device, "vendor", "") == value
        return True

    def simulate_device_event(self, action: str, device: BlockDevice) -> None:
        """Simulate a device event to trigger callbacks."""
        for callback in self.callbacks:
            callback(action, device)


@pytest.fixture
def mock_flash_service() -> Mock:
    """Create a mock flash service with USB adapter and detector."""
    service = Mock()

    # Create USB adapter with detector
    usb_adapter = Mock()
    detector = MockDetector()
    usb_adapter.detector = detector
    service.usb_adapter = usb_adapter

    # Mock list_devices method
    initial_result = FlashResult(success=True)
    initial_result.device_details = []
    service.list_devices.return_value = initial_result

    return service


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a CLI runner."""
    return CliRunner()


def test_firmware_devices_wait_realtime_callback(
    mock_flash_service: Mock, cli_runner: CliRunner
) -> None:
    """Test that firmware devices --wait uses real-time callbacks instead of polling."""
    # Create a test device
    test_device = BlockDevice(
        name="test-device",
        device_node="/dev/sdb",
        vendor="TestVendor",
        model="TestModel",
        serial="TEST123",
        vendor_id="1234",
        product_id="5678",
        removable=True,
        mountpoints={},
        partitions=[],
    )

    # Mock the necessary context and profile functions
    with (
        patch("glovebox.cli.commands.firmware.create_flash_service") as mock_create,
        patch(
            "glovebox.cli.commands.firmware.get_keyboard_profile_from_context"
        ) as mock_get_profile,
        patch(
            "glovebox.cli.commands.firmware.get_icon_mode_from_context"
        ) as mock_get_icon,
    ):
        mock_create.return_value = mock_flash_service
        mock_get_profile.return_value = None  # Profile is optional for devices command
        mock_get_icon.return_value = "text"  # Use text mode for testing

        # Run the command in a separate thread to simulate real-time monitoring
        result_container = {"result": None, "output": ""}

        def run_command() -> None:
            """Run the CLI command."""
            result = cli_runner.invoke(firmware_app, ["devices", "--wait"])
            result_container["result"] = result
            result_container["output"] = result.output

        command_thread = threading.Thread(target=run_command)
        command_thread.start()

        # Give the command time to start monitoring
        time.sleep(0.5)

        # Verify that callbacks were registered
        detector = mock_flash_service.usb_adapter.detector
        assert len(detector.callbacks) == 1, "Callback should be registered"
        assert detector.monitoring is True, "Monitoring should be started"

        # Simulate a device connection event
        detector.simulate_device_event("add", test_device)

        # Give time for the event to be processed
        time.sleep(0.2)

        # Stop the command with Ctrl+C simulation
        # Since we can't send actual signals in tests, we'll check the output instead
        command_thread.join(timeout=1.0)

        # Check the output
        output = result_container["output"]
        assert "Starting continuous device monitoring" in output
        assert "Monitoring for device changes (real-time)" in output

        # Verify no polling message (which would indicate old implementation)
        assert "Poll every second" not in output


def test_firmware_devices_wait_query_filtering(
    mock_flash_service: Mock, cli_runner: CliRunner
) -> None:
    """Test that query filtering works with real-time callbacks."""
    # Create test devices
    matching_device = BlockDevice(
        name="matching-device",
        device_node="/dev/sdb",
        vendor="TestVendor",
        model="TestModel",
        serial="MATCH123",
        removable=True,
    )

    non_matching_device = BlockDevice(
        name="non-matching-device",
        device_node="/dev/sdc",
        vendor="OtherVendor",
        model="OtherModel",
        serial="OTHER123",
        removable=True,
    )

    with (
        patch("glovebox.cli.commands.firmware.create_flash_service") as mock_create,
        patch(
            "glovebox.cli.commands.firmware.get_keyboard_profile_from_context"
        ) as mock_get_profile,
        patch(
            "glovebox.cli.commands.firmware.get_icon_mode_from_context"
        ) as mock_get_icon,
    ):
        mock_create.return_value = mock_flash_service
        mock_get_profile.return_value = None
        mock_get_icon.return_value = "text"

        # Track which devices were displayed
        displayed_devices = []

        # Patch the print functions to capture output
        with patch("glovebox.cli.commands.firmware.print_list_item") as mock_print:

            def capture_device_display(msg: str) -> None:
                if "Device connected:" in msg:
                    displayed_devices.append(msg)

            mock_print.side_effect = capture_device_display

            # Run command with query filter
            result_container = {"complete": False}

            def run_command() -> None:
                result = cli_runner.invoke(
                    firmware_app, ["devices", "--wait", "--query", "vendor=TestVendor"]
                )
                result_container["complete"] = True

            command_thread = threading.Thread(target=run_command)
            command_thread.start()

            # Give time to start
            time.sleep(0.3)

            # Get the detector
            detector = mock_flash_service.usb_adapter.detector

            # Simulate device events
            detector.simulate_device_event("add", matching_device)
            detector.simulate_device_event("add", non_matching_device)

            # Give time for processing
            time.sleep(0.2)

            # Stop the thread
            command_thread.join(timeout=1.0)

            # Verify only matching device was displayed
            assert len(displayed_devices) == 1
            assert "MATCH123" in displayed_devices[0]
            assert "OTHER123" not in displayed_devices[0]


def test_firmware_devices_wait_remove_events(
    mock_flash_service: Mock, cli_runner: CliRunner
) -> None:
    """Test that device removal events are handled correctly."""
    # Create a test device
    test_device = BlockDevice(
        name="test-device",
        device_node="/dev/sdb",
        vendor="TestVendor",
        model="TestModel",
        serial="TEST123",
        removable=True,
    )

    # Set up initial devices
    initial_result = FlashResult(success=True)
    initial_result.device_details = [
        {
            "name": test_device.name,
            "serial": test_device.serial,
            "vendor": test_device.vendor,
            "model": test_device.model,
            "path": test_device.device_node,
            "vendor_id": "1234",
            "product_id": "5678",
            "status": "success",
        }
    ]
    mock_flash_service.list_devices.return_value = initial_result

    with (
        patch("glovebox.cli.commands.firmware.create_flash_service") as mock_create,
        patch(
            "glovebox.cli.commands.firmware.get_keyboard_profile_from_context"
        ) as mock_get_profile,
        patch(
            "glovebox.cli.commands.firmware.get_icon_mode_from_context"
        ) as mock_get_icon,
    ):
        mock_create.return_value = mock_flash_service
        mock_get_profile.return_value = None
        mock_get_icon.return_value = "text"

        # Track displayed messages
        displayed_messages = []

        with patch("glovebox.cli.commands.firmware.print") as mock_print:

            def capture_output(msg: str) -> None:
                displayed_messages.append(msg)

            mock_print.side_effect = capture_output

            # Run command
            def run_command() -> None:
                cli_runner.invoke(firmware_app, ["devices", "--wait"])

            command_thread = threading.Thread(target=run_command)
            command_thread.start()

            # Give time to start and show initial devices
            time.sleep(0.3)

            # Get the detector and simulate removal
            detector = mock_flash_service.usb_adapter.detector
            detector.simulate_device_event("remove", test_device)

            # Give time for processing
            time.sleep(0.2)

            # Stop the thread
            command_thread.join(timeout=1.0)

            # Verify removal was detected
            removal_messages = [
                m for m in displayed_messages if "Device disconnected:" in m
            ]
            assert len(removal_messages) > 0
            assert "TEST123" in removal_messages[0]
