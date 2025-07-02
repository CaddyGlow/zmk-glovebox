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

    # Track if callbacks were registered and devices were added
    callback_registered = False
    device_added = False

    # Keep reference to original register_callback
    original_register = mock_flash_service.usb_adapter.detector.register_callback

    def track_register_callback(callback):
        nonlocal callback_registered
        callback_registered = True
        # Simulate device add event after callback is registered
        original_register(callback)
        # Simulate a device event
        callback("add", test_device)

    mock_flash_service.usb_adapter.detector.register_callback = track_register_callback

    # Mock the necessary context and profile functions
    with (
        patch("glovebox.adapters.create_file_adapter") as mock_create_file,
        patch(
            "glovebox.firmware.flash.device_wait_service.create_device_wait_service"
        ) as mock_create_wait,
        patch("glovebox.firmware.flash.create_flash_service") as mock_create,
        patch(
            "glovebox.cli.commands.firmware.devices.get_keyboard_profile_from_context"
        ) as mock_get_profile,
        patch(
            "glovebox.cli.commands.firmware.devices.get_icon_mode_from_context"
        ) as mock_get_icon,
        patch("signal.signal") as mock_signal,
        patch("time.sleep") as mock_sleep,
    ):
        mock_create_file.return_value = Mock()
        mock_create_wait.return_value = Mock()
        mock_create.return_value = mock_flash_service
        mock_get_profile.return_value = None  # Profile is optional for devices command
        mock_get_icon.return_value = "text"  # Use text mode for testing

        # Mock sleep to allow quick test execution
        sleep_count = 0

        def mock_sleep_func(duration):
            nonlocal sleep_count
            sleep_count += 1
            if sleep_count > 3:
                # After a few loops, stop the monitoring
                raise KeyboardInterrupt()
            time.sleep(0.01)  # Very short sleep for testing

        mock_sleep.side_effect = mock_sleep_func

        # Run the command
        result = cli_runner.invoke(
            firmware_app, ["devices", "--wait"], catch_exceptions=True
        )

        # Verify that callbacks were registered
        assert callback_registered, "Callback should have been registered"

        # Check the output
        assert result.exit_code == 0
        assert "Starting continuous device monitoring" in result.output
        assert "Monitoring for device changes (real-time)" in result.output
        assert "Device connected:" in result.output  # From simulated device add
        assert "TEST123" in result.output  # Device serial

        # Verify no polling message (which would indicate old implementation)
        assert "Poll every second" not in result.output


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
        patch("glovebox.adapters.create_file_adapter") as mock_create_file,
        patch(
            "glovebox.firmware.flash.device_wait_service.create_device_wait_service"
        ) as mock_create_wait,
        patch("glovebox.firmware.flash.create_flash_service") as mock_create,
        patch(
            "glovebox.cli.commands.firmware.devices.get_keyboard_profile_from_context"
        ) as mock_get_profile,
        patch(
            "glovebox.cli.commands.firmware.devices.get_icon_mode_from_context"
        ) as mock_get_icon,
        patch("signal.signal") as mock_signal,
    ):
        mock_create_file.return_value = Mock()
        mock_create_wait.return_value = Mock()
        mock_create.return_value = mock_flash_service
        mock_get_profile.return_value = None
        mock_get_icon.return_value = "text"

        # Mock sleep to allow quick test execution
        sleep_count = 0

        def mock_sleep_func(duration):
            nonlocal sleep_count
            sleep_count += 1
            if sleep_count > 3:
                # After a few loops, stop the monitoring
                raise KeyboardInterrupt()
            time.sleep(0.01)  # Very short sleep for testing

        with patch("time.sleep") as mock_sleep:
            mock_sleep.side_effect = mock_sleep_func

            # Run command with query filter
            result = cli_runner.invoke(
                firmware_app,
                ["devices", "--wait", "--query", "vendor=TestVendor"],
                catch_exceptions=True,
            )

            # Check that query filter was applied
            assert result.exit_code == 0
            assert "Query filter: vendor=TestVendor" in result.output


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
        patch("glovebox.adapters.create_file_adapter") as mock_create_file,
        patch(
            "glovebox.firmware.flash.device_wait_service.create_device_wait_service"
        ) as mock_create_wait,
        patch("glovebox.firmware.flash.create_flash_service") as mock_create,
        patch(
            "glovebox.cli.commands.firmware.devices.get_keyboard_profile_from_context"
        ) as mock_get_profile,
        patch(
            "glovebox.cli.commands.firmware.devices.get_icon_mode_from_context"
        ) as mock_get_icon,
        patch("signal.signal") as mock_signal,
    ):
        mock_create_file.return_value = Mock()
        mock_create_wait.return_value = Mock()
        mock_create.return_value = mock_flash_service
        mock_get_profile.return_value = None
        mock_get_icon.return_value = "text"

        # Mock sleep to allow quick test execution
        sleep_count = 0

        def mock_sleep_func(duration):
            nonlocal sleep_count
            sleep_count += 1
            if sleep_count > 3:
                # After a few loops, stop the monitoring
                raise KeyboardInterrupt()
            time.sleep(0.01)  # Very short sleep for testing

        with patch("time.sleep") as mock_sleep:
            mock_sleep.side_effect = mock_sleep_func

            # Run command
            result = cli_runner.invoke(
                firmware_app, ["devices", "--wait"], catch_exceptions=True
            )

            # Check the output shows initial devices
            assert result.exit_code == 0
            assert "Currently connected devices: 1" in result.output
            assert "TEST123" in result.output
