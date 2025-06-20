"""Tests for USB device flashing functionality."""

import platform
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from glovebox.core.errors import FlashError
from glovebox.firmware.flash.models import BlockDevice, BlockDeviceError, FlashResult
from glovebox.firmware.flash.usb import (
    FirmwareFlasherImpl,
    create_firmware_flasher,
    get_device_path,
)


@pytest.fixture
def mock_device_detector():
    """Create a mock device detector for testing."""
    detector = Mock()
    detector.parse_query.return_value = True
    detector.get_devices.return_value = []
    detector.list_matching_devices.return_value = []
    detector.register_callback = Mock()
    detector.unregister_callback = Mock()
    detector.start_monitoring = Mock()
    detector.stop_monitoring = Mock()
    return detector


@pytest.fixture
def mock_flash_operations():
    """Create a mock flash operations instance."""
    flash_ops = Mock()
    flash_ops.mount_and_flash.return_value = True
    return flash_ops


@pytest.fixture
def sample_block_device():
    """Create a sample BlockDevice for testing."""
    return BlockDevice(
        name="sda1",
        device_node="/dev/sda1",
        size=8192000,
        type="disk",
        removable=True,
        model="Glove80_Bootloader",
        vendor="Adafruit",
        serial="GLV80-12345",
        uuid="1234-5678",
        label="GLV80LDR",
        vendor_id="239a",
        product_id="0029",
        partitions=["sda1"],
        mountpoints={"/dev/sda1": "/media/GLV80LDR"},
        symlinks={"usb-Adafruit_Glove80_Bootloader_GLV80-12345"},
        raw={"ID_VENDOR": "Adafruit", "ID_MODEL": "Glove80_Bootloader"},
    )


@pytest.fixture
def firmware_file(tmp_path):
    """Create a temporary firmware file for testing."""
    firmware_path = tmp_path / "test_firmware.uf2"
    firmware_path.write_text("fake firmware content")
    return firmware_path


class TestGetDevicePath:
    """Test the get_device_path utility function."""

    @patch("platform.system")
    def test_get_device_path_linux(self, mock_system):
        """Test device path generation on Linux."""
        mock_system.return_value = "Linux"
        result = get_device_path("sda1")
        assert result == "/dev/sda1"

    @patch("platform.system")
    def test_get_device_path_darwin(self, mock_system):
        """Test device path generation on macOS."""
        mock_system.return_value = "Darwin"
        result = get_device_path("disk2")
        assert result == "/dev/disk2"

    @patch("platform.system")
    def test_get_device_path_windows_unsupported(self, mock_system):
        """Test device path generation fails on Windows."""
        mock_system.return_value = "Windows"
        with pytest.raises(FlashError, match="Unsupported operating system: windows"):
            get_device_path("C:")

    @patch("platform.system")
    def test_get_device_path_unknown_os(self, mock_system):
        """Test device path generation fails on unknown OS."""
        mock_system.return_value = "UnknownOS"
        with pytest.raises(FlashError, match="Unsupported operating system: unknownos"):
            get_device_path("dev1")


class TestFirmwareFlasherImpl:
    """Test the FirmwareFlasherImpl class."""

    def test_init_with_detector(self, mock_device_detector):
        """Test initialization with provided detector."""
        flasher = FirmwareFlasherImpl(detector=mock_device_detector)
        assert flasher._detector is mock_device_detector
        assert isinstance(flasher._lock, type(threading.RLock()))
        assert isinstance(flasher._device_event, type(threading.Event()))
        assert flasher._current_device is None
        assert flasher._flashed_devices == set()

    @patch("glovebox.firmware.flash.usb.create_device_detector")
    def test_init_without_detector(self, mock_create_detector):
        """Test initialization creates detector when none provided."""
        mock_detector = Mock()
        mock_create_detector.return_value = mock_detector

        flasher = FirmwareFlasherImpl()

        mock_create_detector.assert_called_once()
        assert flasher._detector is mock_detector

    def test_extract_device_id_usb_symlink(
        self, mock_device_detector, sample_block_device
    ):
        """Test device ID extraction from USB symlinks."""
        flasher = FirmwareFlasherImpl(detector=mock_device_detector)
        device_id = flasher._extract_device_id(sample_block_device)
        assert device_id == "usb-Adafruit_Glove80_Bootloader_GLV80-12345"

    def test_extract_device_id_serial_fallback(self, mock_device_detector):
        """Test device ID extraction falls back to serial."""
        device = BlockDevice(
            name="sda1",
            serial="GLV80-67890",
            symlinks=set(),  # No USB symlinks
        )
        flasher = FirmwareFlasherImpl(detector=mock_device_detector)
        device_id = flasher._extract_device_id(device)
        assert device_id == "GLV80-67890"

    def test_extract_device_id_name_fallback(self, mock_device_detector):
        """Test device ID extraction falls back to name."""
        device = BlockDevice(
            name="sda1",
            serial="",  # No serial
            symlinks=set(),  # No USB symlinks
        )
        flasher = FirmwareFlasherImpl(detector=mock_device_detector)
        device_id = flasher._extract_device_id(device)
        assert device_id == "sda1"

    def test_device_callback_add_action(
        self, mock_device_detector, sample_block_device
    ):
        """Test device callback handles 'add' action."""
        flasher = FirmwareFlasherImpl(detector=mock_device_detector)
        flasher._device_callback("add", sample_block_device)

        assert flasher._current_device is sample_block_device
        assert flasher._device_event.is_set()

    def test_device_callback_ignore_non_add(
        self, mock_device_detector, sample_block_device
    ):
        """Test device callback ignores non-'add' actions."""
        flasher = FirmwareFlasherImpl(detector=mock_device_detector)
        flasher._device_callback("remove", sample_block_device)

        assert flasher._current_device is None
        assert not flasher._device_event.is_set()

    def test_device_callback_skip_flashed_device(
        self, mock_device_detector, sample_block_device
    ):
        """Test device callback skips already flashed devices."""
        flasher = FirmwareFlasherImpl(detector=mock_device_detector)
        device_id = flasher._extract_device_id(sample_block_device)
        flasher._flashed_devices.add(device_id)

        flasher._device_callback("add", sample_block_device)

        assert flasher._current_device is None
        assert not flasher._device_event.is_set()

    def test_flash_firmware_file_not_found(self, mock_device_detector):
        """Test flash_firmware raises FileNotFoundError for missing files."""
        flasher = FirmwareFlasherImpl(detector=mock_device_detector)

        with pytest.raises(FileNotFoundError, match="Firmware file not found"):
            flasher.flash_firmware("/nonexistent/firmware.uf2")

    def test_flash_firmware_invalid_query(self, mock_device_detector, firmware_file):
        """Test flash_firmware raises ValueError for invalid query."""
        flasher = FirmwareFlasherImpl(detector=mock_device_detector)
        mock_device_detector.parse_query.side_effect = ValueError("Invalid query")

        with pytest.raises(ValueError, match="Invalid query string"):
            flasher.flash_firmware(firmware_file, query="invalid query")

    def test_flash_firmware_non_uf2_warning(self, mock_device_detector, tmp_path):
        """Test flash_firmware shows warning for non-.uf2 files."""
        # Create a non-UF2 file
        firmware_path = tmp_path / "firmware.bin"
        firmware_path.write_text("fake firmware")

        flasher = FirmwareFlasherImpl(detector=mock_device_detector)

        # Mock device detection to timeout quickly
        mock_device_detector.list_matching_devices.return_value = []

        result = flasher.flash_firmware(firmware_path, timeout=1)

        assert "does not have .uf2 extension" in str(result.messages)
        assert not result.success

    @patch("glovebox.firmware.flash.usb.create_flash_operations")
    def test_flash_firmware_successful_single_device(
        self,
        mock_create_flash_ops,
        mock_device_detector,
        sample_block_device,
        firmware_file,
    ):
        """Test successful flashing of a single device."""
        # Setup mocks
        mock_flash_ops = Mock()
        mock_flash_ops.mount_and_flash.return_value = True
        mock_create_flash_ops.return_value = mock_flash_ops

        # Setup device detection to return our sample device immediately
        mock_device_detector.list_matching_devices.return_value = [sample_block_device]

        flasher = FirmwareFlasherImpl(detector=mock_device_detector)

        result = flasher.flash_firmware(firmware_file, count=1, timeout=1)

        assert result.success
        assert result.devices_flashed == 1
        assert result.devices_failed == 0
        assert result.firmware_path == firmware_file.resolve()

        # Verify flash operations were called
        mock_flash_ops.mount_and_flash.assert_called_once_with(
            sample_block_device, firmware_file.resolve()
        )

        # Verify device monitoring lifecycle
        mock_device_detector.register_callback.assert_called_once()
        mock_device_detector.start_monitoring.assert_called_once()
        mock_device_detector.stop_monitoring.assert_called_once()
        mock_device_detector.unregister_callback.assert_called_once()

    @patch("glovebox.firmware.flash.usb.create_flash_operations")
    def test_flash_firmware_flash_failure(
        self,
        mock_create_flash_ops,
        mock_device_detector,
        sample_block_device,
        firmware_file,
    ):
        """Test handling of flash operation failure."""
        # Setup mocks
        mock_flash_ops = Mock()
        mock_flash_ops.mount_and_flash.return_value = False  # Flash fails
        mock_create_flash_ops.return_value = mock_flash_ops

        # Setup device detection
        mock_device_detector.list_matching_devices.return_value = [sample_block_device]

        flasher = FirmwareFlasherImpl(detector=mock_device_detector)

        result = flasher.flash_firmware(firmware_file, count=1, timeout=1)

        assert not result.success
        assert result.devices_flashed == 0
        assert result.devices_failed == 1

        # Check device failure was recorded
        assert len(result.device_details) == 1
        device_detail = result.device_details[0]
        assert device_detail["name"] == "sda1"
        assert device_detail["status"] == "failed"
        assert "Failed to flash device" in device_detail["error"]

    @patch("glovebox.firmware.flash.usb.create_flash_operations")
    def test_flash_firmware_timeout_finite(
        self, mock_create_flash_ops, mock_device_detector, firmware_file
    ):
        """Test timeout behavior with finite device count."""
        # No devices found, should timeout
        mock_device_detector.list_matching_devices.return_value = []

        flasher = FirmwareFlasherImpl(detector=mock_device_detector)

        result = flasher.flash_firmware(firmware_file, count=1, timeout=1)

        assert not result.success
        assert result.devices_flashed == 0
        assert result.devices_failed == 0
        assert "Device detection timed out" in str(result.errors)

    @patch("glovebox.firmware.flash.usb.create_flash_operations")
    @patch("time.sleep")  # Mock sleep to speed up test
    def test_flash_firmware_timeout_infinite(
        self, mock_sleep, mock_create_flash_ops, mock_device_detector, firmware_file
    ):
        """Test timeout behavior with infinite device count continues after timeouts."""
        # Mock that no devices are found, infinite loop should continue with timeouts
        mock_device_detector.list_matching_devices.return_value = []

        flasher = FirmwareFlasherImpl(detector=mock_device_detector)

        # Use a very short timeout and manually break the infinite loop by simulating KeyboardInterrupt
        def interrupt_after_delay(*args, **kwargs):
            # Simulate user interruption after a few timeout cycles
            raise KeyboardInterrupt("Test interruption")

        # Mock the wait method to trigger interruption after first timeout
        original_wait = flasher._device_event.wait
        call_count = 0

        def mock_wait(timeout):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:  # After a couple of timeouts, interrupt
                interrupt_after_delay()
            return False  # Timeout

        flasher._device_event.wait = mock_wait  # type: ignore[assignment]

        result = flasher.flash_firmware(
            firmware_file, count=0, timeout=1
        )  # Infinite count

        # Should handle interrupt gracefully - with infinite count, success is True if no failures
        assert result.success  # Infinite count with no failures = success
        assert result.devices_flashed == 0  # No devices were actually flashed
        assert result.devices_failed == 0  # No devices failed
        assert "Operation interrupted by user" in str(result.messages)

    def test_flash_firmware_track_flashed_devices(
        self, mock_device_detector, sample_block_device, firmware_file
    ):
        """Test that flashed devices are tracked and skipped."""
        flasher = FirmwareFlasherImpl(detector=mock_device_detector)

        # Pre-add device to flashed list
        device_id = flasher._extract_device_id(sample_block_device)
        flasher._flashed_devices.add(device_id)

        # Setup device detection to return the already-flashed device
        mock_device_detector.list_matching_devices.return_value = [sample_block_device]

        result = flasher.flash_firmware(
            firmware_file, count=1, timeout=1, track_flashed=True
        )

        # Should timeout because device is skipped
        assert not result.success
        assert result.devices_flashed == 0

    def test_flash_firmware_no_tracking(
        self, mock_device_detector, sample_block_device, firmware_file
    ):
        """Test disabling flashed device tracking."""
        flasher = FirmwareFlasherImpl(detector=mock_device_detector)

        # Pre-add device to flashed list
        device_id = flasher._extract_device_id(sample_block_device)
        flasher._flashed_devices.add(device_id)

        # Verify flashed devices list is cleared when track_flashed=False
        flasher.flash_firmware(firmware_file, count=1, timeout=1, track_flashed=False)

        assert len(flasher._flashed_devices) == 0

    @patch("glovebox.firmware.flash.usb.create_flash_operations")
    def test_flash_firmware_critical_error_handling(
        self,
        mock_create_flash_ops,
        mock_device_detector,
        sample_block_device,
        firmware_file,
    ):
        """Test handling of critical errors during flashing."""
        # Setup flash operations to raise a critical error
        mock_flash_ops = Mock()
        mock_flash_ops.mount_and_flash.side_effect = BlockDeviceError(
            "Critical device error"
        )
        mock_create_flash_ops.return_value = mock_flash_ops

        mock_device_detector.list_matching_devices.return_value = [sample_block_device]

        flasher = FirmwareFlasherImpl(detector=mock_device_detector)

        result = flasher.flash_firmware(firmware_file, count=1, timeout=1)

        assert not result.success
        assert "Critical error during flash attempt" in str(result.errors)

    @patch("glovebox.firmware.flash.usb.create_flash_operations")
    def test_flash_firmware_keyboard_interrupt(
        self,
        mock_create_flash_ops,
        mock_device_detector,
        sample_block_device,
        firmware_file,
    ):
        """Test handling of keyboard interrupt during flashing."""
        # Setup flash operations to raise KeyboardInterrupt
        mock_flash_ops = Mock()
        mock_flash_ops.mount_and_flash.side_effect = KeyboardInterrupt()
        mock_create_flash_ops.return_value = mock_flash_ops

        mock_device_detector.list_matching_devices.return_value = [sample_block_device]

        flasher = FirmwareFlasherImpl(detector=mock_device_detector)

        result = flasher.flash_firmware(firmware_file, count=1, timeout=1)

        assert not result.success
        assert "Operation interrupted by user" in str(result.messages)

    @patch("glovebox.firmware.flash.usb.create_flash_operations")
    def test_flash_firmware_unexpected_error(
        self,
        mock_create_flash_ops,
        mock_device_detector,
        sample_block_device,
        firmware_file,
    ):
        """Test handling of unexpected errors during flashing."""
        # Setup flash operations to raise an unexpected error
        mock_flash_ops = Mock()
        mock_flash_ops.mount_and_flash.side_effect = RuntimeError("Unexpected error")
        mock_create_flash_ops.return_value = mock_flash_ops

        mock_device_detector.list_matching_devices.return_value = [sample_block_device]

        flasher = FirmwareFlasherImpl(detector=mock_device_detector)

        result = flasher.flash_firmware(firmware_file, count=1, timeout=1)

        assert not result.success
        assert "Unexpected error during flash attempt" in str(result.errors)

    def test_flash_firmware_device_event_without_device(
        self, mock_device_detector, firmware_file
    ):
        """Test handling of device event trigger without actual device."""
        flasher = FirmwareFlasherImpl(detector=mock_device_detector)

        # Setup a scenario where device event is set but no device is available
        def mock_callback_trigger(*args):
            flasher._device_event.set()  # Trigger event without setting device

        mock_device_detector.list_matching_devices.return_value = []
        mock_device_detector.register_callback.side_effect = mock_callback_trigger

        result = flasher.flash_firmware(firmware_file, count=1, timeout=1)

        # Should handle gracefully and continue waiting
        assert not result.success

    @patch("glovebox.firmware.flash.usb.create_flash_operations")
    @patch("time.sleep")
    def test_flash_firmware_multiple_devices(
        self, mock_sleep, mock_create_flash_ops, mock_device_detector, firmware_file
    ):
        """Test flashing multiple devices sequentially."""
        # Create multiple devices
        device1 = BlockDevice(name="sda1", serial="GLV80-001", symlinks={"usb-device1"})
        device2 = BlockDevice(name="sdb1", serial="GLV80-002", symlinks={"usb-device2"})

        # Setup device detection to return devices in sequence
        call_count = 0

        def side_effect_devices(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [device1]
            elif call_count == 2:
                return [device2]
            return []

        mock_device_detector.list_matching_devices.side_effect = side_effect_devices

        # Setup flash operations
        mock_flash_ops = Mock()
        mock_flash_ops.mount_and_flash.return_value = True
        mock_create_flash_ops.return_value = mock_flash_ops

        flasher = FirmwareFlasherImpl(detector=mock_device_detector)

        result = flasher.flash_firmware(firmware_file, count=2, timeout=1)

        assert result.success
        assert result.devices_flashed == 2
        assert result.devices_failed == 0

        # Verify both devices were flashed
        assert mock_flash_ops.mount_and_flash.call_count == 2


class TestCreateFirmwareFlasher:
    """Test the create_firmware_flasher factory function."""

    def test_create_firmware_flasher_default(self):
        """Test creating firmware flasher with default parameters."""
        flasher = create_firmware_flasher()

        assert isinstance(flasher, FirmwareFlasherImpl)
        assert flasher._detector is not None

    def test_create_firmware_flasher_with_detector(self, mock_device_detector):
        """Test creating firmware flasher with provided detector."""
        flasher = create_firmware_flasher(detector=mock_device_detector)

        assert isinstance(flasher, FirmwareFlasherImpl)
        assert flasher._detector is mock_device_detector


class TestIntegrationScenarios:
    """Integration test scenarios for complex flashing workflows."""

    @patch("glovebox.firmware.flash.usb.create_flash_operations")
    def test_real_world_flashing_workflow(
        self, mock_create_flash_ops, mock_device_detector, firmware_file
    ):
        """Test a realistic flashing workflow with device detection and successful flashing."""
        # Setup a device that appears after initial detection
        device = BlockDevice(name="sda1", serial="GLV80-TEST", symlinks={"usb-test"})

        # Return the device immediately when queried
        mock_device_detector.list_matching_devices.return_value = [device]

        # Flash operation succeeds
        mock_flash_ops = Mock()
        mock_flash_ops.mount_and_flash.return_value = True
        mock_create_flash_ops.return_value = mock_flash_ops

        flasher = FirmwareFlasherImpl(detector=mock_device_detector)

        result = flasher.flash_firmware(firmware_file, count=1, timeout=1)

        # Should succeed with the device
        assert result.success
        assert result.devices_flashed == 1
        assert result.devices_failed == 0
        assert result.firmware_path == firmware_file.resolve()
