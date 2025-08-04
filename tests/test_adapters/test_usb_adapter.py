"""Tests for USBAdapter implementation."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.adapters.usb_adapter import USBAdapter, create_usb_adapter
from glovebox.core.errors import USBError
from glovebox.firmware.flash.models import BlockDevice, DiskInfo, USBDeviceInfo
from glovebox.protocols.usb_adapter_protocol import USBAdapterProtocol


@pytest.fixture
def mock_flash_operations():
    """Create a mock flash operations."""
    return Mock()


@pytest.fixture
def mock_detector():
    """Create a mock detector."""
    return Mock()


@pytest.fixture
def usb_adapter(mock_flash_operations, mock_detector):
    """Create a USB adapter with mocked dependencies."""
    return USBAdapter(
        flash_operations=mock_flash_operations,
        detector=mock_detector,
    )


class TestUSBAdapter:
    """Test USBAdapter class."""

    def test_usb_adapter_initialization(self, usb_adapter):
        """Test USBAdapter can be initialized."""
        assert usb_adapter is not None
        assert hasattr(usb_adapter, "detector")

    def test_detect_device_success(self, usb_adapter):
        """Test successful device detection."""
        adapter = usb_adapter

        mock_device = BlockDevice(
            name="sda", model="Test Device", vendor="Test Vendor", serial="12345"
        )

        with patch.object(
            adapter.detector, "detect_device", return_value=mock_device
        ) as mock_detect:
            result = adapter.detect_device("vendor=Test", timeout=30)

        assert result == mock_device
        mock_detect.assert_called_once_with("vendor=Test", 30, None)

    def test_detect_device_with_initial_devices(self, usb_adapter):
        """Test device detection with initial devices list."""
        adapter = usb_adapter

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

    def test_detect_device_exception(self, usb_adapter):
        """Test device detection handles exceptions."""
        adapter = usb_adapter

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

    def test_list_matching_devices_success(self, usb_adapter):
        """Test successful device listing."""
        adapter = usb_adapter

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

    def test_list_matching_devices_exception(self, usb_adapter):
        """Test device listing handles exceptions."""
        adapter = usb_adapter

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

    def test_flash_device_success(self, usb_adapter):
        """Test successful device flashing."""
        adapter = usb_adapter

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

    def test_flash_device_firmware_not_found(self, usb_adapter):
        """Test flash_device raises error when firmware file doesn't exist."""
        adapter = usb_adapter

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

    def test_flash_device_custom_retries(self, usb_adapter):
        """Test flash_device with custom retry parameters."""
        adapter = usb_adapter

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

    def test_flash_device_exception(self, usb_adapter):
        """Test flash_device handles exceptions."""
        adapter = usb_adapter

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

    def test_get_all_devices_success(self, usb_adapter):
        """Test successful retrieval of all devices."""
        adapter = usb_adapter

        mock_devices = [BlockDevice(name="sda"), BlockDevice(name="sdb")]

        with patch.object(
            adapter.detector, "get_devices", return_value=mock_devices
        ) as mock_get:
            result = adapter.get_all_devices()

        assert result == mock_devices
        mock_get.assert_called_once()

    def test_get_all_devices_exception(self, usb_adapter):
        """Test get_all_devices handles exceptions."""
        adapter = usb_adapter

        with (
            patch.object(
                adapter.detector,
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

    def test_create_usb_adapter(self, mock_flash_operations, mock_detector):
        """Test factory function creates USBAdapter instance."""
        adapter = create_usb_adapter(
            flash_operations=mock_flash_operations,
            detector=mock_detector,
        )
        assert isinstance(adapter, USBAdapter)
        assert isinstance(adapter, USBAdapterProtocol)


class TestUSBAdapterProtocol:
    """Test USBAdapter protocol implementation."""

    def test_usb_adapter_implements_protocol(self, usb_adapter):
        """Test that USBAdapter correctly implements USBAdapter protocol."""
        assert isinstance(usb_adapter, USBAdapterProtocol), (
            "USBAdapter must implement USBAdapterProtocol"
        )

    def test_runtime_protocol_check(self, usb_adapter):
        """Test that USBAdapter passes runtime protocol check."""
        assert isinstance(usb_adapter, USBAdapterProtocol), (
            "USBAdapter should be instance of USBAdapterProtocol"
        )


class TestBlockDeviceUSBPIDs:
    """Test BlockDevice USB PID fields."""

    def test_block_device_default_pids(self):
        """Test BlockDevice initializes with empty USB PIDs by default."""
        device = BlockDevice(name="sda")
        assert device.vendor_id == ""
        assert device.product_id == ""

    def test_block_device_with_pids(self):
        """Test BlockDevice can be created with USB PIDs."""
        device = BlockDevice(
            name="sda",
            vendor_id="1234",
            product_id="5678",
            vendor="Test Vendor",
            model="Test Device",
        )
        assert device.vendor_id == "1234"
        assert device.product_id == "5678"
        assert device.vendor == "Test Vendor"
        assert device.model == "Test Device"

    def test_from_pyudev_device_with_pids(self):
        """Test BlockDevice.from_pyudev_device extracts USB PIDs."""
        # Mock pyudev device
        mock_device = Mock()
        mock_device.sys_name = "sda"
        mock_device.device_node = "/dev/sda"
        mock_device.properties = {
            "ID_VENDOR": "Test Vendor",
            "ID_MODEL": "Test Device",
            "ID_VENDOR_ID": "1234",
            "ID_MODEL_ID": "5678",
            "ID_SERIAL_SHORT": "ABC123",
            "ID_FS_LABEL": "TESTDRIVE",
            "ID_FS_UUID": "1234-5678",
            "ID_BUS": "usb",
        }
        mock_device.attributes = {"size": "1024", "removable": "1"}
        mock_device.children = []
        mock_device.device_links = []

        device = BlockDevice.from_pyudev_device(mock_device)

        assert device.vendor_id == "1234"
        assert device.product_id == "5678"
        assert device.vendor == "Test Vendor"
        assert device.model == "Test Device"
        assert device.type == "usb"

    def test_from_pyudev_device_without_pids(self):
        """Test BlockDevice.from_pyudev_device handles missing USB PIDs."""
        # Mock pyudev device without USB IDs
        mock_device = Mock()
        mock_device.sys_name = "sda"
        mock_device.device_node = "/dev/sda"
        mock_device.properties = {
            "ID_VENDOR": "Test Vendor",
            "ID_MODEL": "Test Device",
        }
        mock_device.attributes = {"size": "1024", "removable": "0"}
        mock_device.children = []
        mock_device.device_links = []

        device = BlockDevice.from_pyudev_device(mock_device)

        assert device.vendor_id == ""
        assert device.product_id == ""
        assert device.vendor == "Test Vendor"
        assert device.model == "Test Device"

    def test_from_macos_disk_info_with_usb_pids(self):
        """Test BlockDevice.from_macos_disk_info extracts USB PIDs."""
        disk_info = DiskInfo(
            size=1024 * 1024 * 1024,
            media_name="Test Media",
            volume_name="TESTDRIVE",
            removable=True,
            protocol="USB",
            partitions=["disk1s1"],
        )

        usb_info = USBDeviceInfo(
            name="Test USB Device",
            vendor="Test Vendor",
            vendor_id="1234",
            product_id="5678",
            serial="ABC123",
        )

        mounted_volumes = {"TESTDRIVE"}

        device = BlockDevice.from_macos_disk_info(
            disk_name="disk1",
            disk_info=disk_info,
            usb_info=usb_info,
            mounted_volumes=mounted_volumes,
        )

        assert device.vendor_id == "1234"
        assert device.product_id == "5678"
        assert device.vendor == "Test Vendor"
        assert device.model == "Test USB Device"
        assert device.type == "usb"

    def test_from_macos_disk_info_without_usb_info(self):
        """Test BlockDevice.from_macos_disk_info handles missing USB info."""
        disk_info = DiskInfo(
            size=1024 * 1024 * 1024,
            media_name="Test Media",
            volume_name="TESTDRIVE",
            removable=False,
            protocol="SATA",
            partitions=["disk1s1"],
        )

        device = BlockDevice.from_macos_disk_info(
            disk_name="disk1", disk_info=disk_info, usb_info=None, mounted_volumes=set()
        )

        assert device.vendor_id == ""
        assert device.product_id == ""
        assert device.vendor == "Unknown"
        assert device.model == "Test Media"
        assert device.type == "disk"

    def test_from_macos_disk_info_with_empty_usb_pids(self):
        """Test BlockDevice.from_macos_disk_info handles empty USB PIDs."""
        disk_info = DiskInfo(
            size=1024 * 1024 * 1024,
            media_name="Test Media",
            volume_name="TESTDRIVE",
            removable=True,
            protocol="USB",
        )

        usb_info = USBDeviceInfo(
            name="Test USB Device",
            vendor="Test Vendor",
            vendor_id="",  # Empty vendor_id
            product_id="",  # Empty product_id
            serial="ABC123",
        )

        device = BlockDevice.from_macos_disk_info(
            disk_name="disk1", disk_info=disk_info, usb_info=usb_info
        )

        assert device.vendor_id == ""
        assert device.product_id == ""
        assert device.vendor == "Test Vendor"
        assert device.model == "Test USB Device"
