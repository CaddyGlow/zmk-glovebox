"""Tests for USBAdapter implementation."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.adapters.usb_adapter import USBAdapterImpl, create_usb_adapter
from glovebox.core.errors import FlashError, USBError
from glovebox.flash.lsdev import BlockDevice
from glovebox.protocols.usb_adapter_protocol import USBAdapterProtocol


class TestUSBAdapterImpl:
    """Test USBAdapterImpl class."""

    def test_usb_adapter_initialization(self):
        """Test USBAdapter can be initialized."""
        adapter = USBAdapterImpl()
        assert adapter is not None
        assert hasattr(adapter, "detector")
        assert hasattr(adapter, "lsdev")

    def test_detect_device_success(self):
        """Test successful device detection."""
        adapter = USBAdapterImpl()

        mock_device = BlockDevice(
            name="sda", model="Test Device", vendor="Test Vendor", serial="12345"
        )

        with patch.object(
            adapter.detector, "detect_device", return_value=mock_device
        ) as mock_detect:
            result = adapter.detect_device("vendor=Test", timeout=30)

        assert result == mock_device
        mock_detect.assert_called_once_with("vendor=Test", 30, None)

    def test_detect_device_with_initial_devices(self):
        """Test device detection with initial devices list."""
        adapter = USBAdapterImpl()

        mock_device = BlockDevice(name="sda")
        initial_devices = [BlockDevice(name="sdb")]

        with patch.object(
            adapter.detector, "detect_device", return_value=mock_device
        ) as mock_detect:
            result = adapter.detect_device(
                "vendor=Test", timeout=60, initial_devices=initial_devices
            )

        assert result == mock_device
        mock_detect.assert_called_once_with("vendor=Test", 60, initial_devices)

    def test_detect_device_exception(self):
        """Test device detection handles exceptions."""
        adapter = USBAdapterImpl()

        with (
            patch.object(
                adapter.detector,
                "detect_device",
                side_effect=Exception("Detection failed"),
            ),
            pytest.raises(
                USBError,
                match="USB device operation 'detect_device' failed on 'vendor=Test': Detection failed",
            ),
        ):
            adapter.detect_device("vendor=Test")

    def test_list_matching_devices_success(self):
        """Test successful device listing."""
        adapter = USBAdapterImpl()

        mock_devices = [
            BlockDevice(name="sda", vendor="Test"),
            BlockDevice(name="sdb", vendor="Test"),
        ]

        with patch.object(
            adapter.detector, "list_matching_devices", return_value=mock_devices
        ) as mock_list:
            result = adapter.list_matching_devices("vendor=Test")

        assert result == mock_devices
        mock_list.assert_called_once_with("vendor=Test")

    def test_list_matching_devices_exception(self):
        """Test device listing handles exceptions."""
        adapter = USBAdapterImpl()

        with (
            patch.object(
                adapter.detector,
                "list_matching_devices",
                side_effect=Exception("List failed"),
            ),
            pytest.raises(
                USBError,
                match="USB device operation 'list_matching_devices' failed on 'vendor=Test': List failed",
            ),
        ):
            adapter.list_matching_devices("vendor=Test")

    def test_flash_device_success(self):
        """Test successful device flashing."""
        adapter = USBAdapterImpl()

        mock_device = BlockDevice(name="sda")
        firmware_path = Path("/test/firmware.uf2")

        with (
            patch.object(
                adapter._flash_ops, "mount_and_flash", return_value=True
            ) as mock_flash,
            patch("pathlib.Path.exists", return_value=True),
        ):
            result = adapter.flash_device(mock_device, firmware_path)

        assert result is True
        mock_flash.assert_called_once_with(mock_device, firmware_path, 3, 2.0)

    def test_flash_device_firmware_not_found(self):
        """Test flash_device raises error when firmware file doesn't exist."""
        adapter = USBAdapterImpl()

        mock_device = BlockDevice(name="sda")
        firmware_path = Path("/nonexistent/firmware.uf2")

        with (
            patch("pathlib.Path.exists", return_value=False),
            pytest.raises(
                USBError,
                match="USB device operation 'flash_device' failed on 'sda': Firmware file not found",
            ),
        ):
            adapter.flash_device(mock_device, firmware_path)

    def test_flash_device_custom_retries(self):
        """Test flash_device with custom retry parameters."""
        adapter = USBAdapterImpl()

        mock_device = BlockDevice(name="sda")
        firmware_path = Path("/test/firmware.uf2")

        with (
            patch.object(
                adapter._flash_ops, "mount_and_flash", return_value=True
            ) as mock_flash,
            patch("pathlib.Path.exists", return_value=True),
        ):
            adapter.flash_device(
                mock_device, firmware_path, max_retries=5, retry_delay=1.0
            )

        mock_flash.assert_called_once_with(mock_device, firmware_path, 5, 1.0)

    def test_flash_device_exception(self):
        """Test flash_device handles exceptions."""
        adapter = USBAdapterImpl()

        mock_device = BlockDevice(name="sda")
        firmware_path = Path("/test/firmware.uf2")

        with (
            patch.object(
                adapter._flash_ops,
                "mount_and_flash",
                side_effect=Exception("Flash failed"),
            ),
            patch("pathlib.Path.exists", return_value=True),
            pytest.raises(
                USBError,
                match="USB device operation 'flash_device' failed on 'sda': Flash failed",
            ),
        ):
            adapter.flash_device(mock_device, firmware_path)

    def test_get_all_devices_success(self):
        """Test successful retrieval of all devices."""
        adapter = USBAdapterImpl()

        mock_devices = [BlockDevice(name="sda"), BlockDevice(name="sdb")]

        with patch.object(
            adapter.lsdev, "get_devices", return_value=mock_devices
        ) as mock_get:
            result = adapter.get_all_devices()

        assert result == mock_devices
        mock_get.assert_called_once()

    def test_get_all_devices_exception(self):
        """Test get_all_devices handles exceptions."""
        adapter = USBAdapterImpl()

        with (
            patch.object(
                adapter.lsdev,
                "get_devices",
                side_effect=Exception("Get devices failed"),
            ),
            pytest.raises(
                USBError,
                match="USB device operation 'get_all_devices' failed on 'all': Get devices failed",
            ),
        ):
            adapter.get_all_devices()


class TestCreateUSBAdapter:
    """Test create_usb_adapter factory function."""

    def test_create_usb_adapter(self):
        """Test factory function creates USBAdapter instance."""
        adapter = create_usb_adapter()
        assert isinstance(adapter, USBAdapterImpl)
        assert isinstance(adapter, USBAdapterProtocol)


class TestUSBAdapterProtocol:
    """Test USBAdapter protocol implementation."""

    def test_usb_adapter_implements_protocol(self):
        """Test that USBAdapterImpl correctly implements USBAdapter protocol."""
        adapter = USBAdapterImpl()
        assert isinstance(adapter, USBAdapterProtocol), (
            "USBAdapterImpl must implement USBAdapterProtocol"
        )

    def test_runtime_protocol_check(self):
        """Test that USBAdapterImpl passes runtime protocol check."""
        adapter = USBAdapterImpl()
        assert isinstance(adapter, USBAdapterProtocol), (
            "USBAdapterImpl should be instance of USBAdapterProtocol"
        )
