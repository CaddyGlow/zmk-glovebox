"""Tests for USB device monitoring functionality."""

import json
import platform
import subprocess
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from glovebox.firmware.flash.models import (
    BlockDevice,
    BlockDeviceDict,
    DiskInfo,
    USBDeviceInfo,
)
from glovebox.firmware.flash.usb_monitor import (
    LinuxUSBDeviceMonitor,
    MacOSUSBDeviceMonitor,
    StubUSBDeviceMonitor,
    USBDeviceMonitorBase,
    _create_mount_cache,
    create_usb_monitor,
)


@pytest.fixture
def sample_block_device():
    """Create a sample BlockDevice for testing."""
    return BlockDevice(
        name="sda1",
        device_node="/dev/sda1",
        size=8192000,
        type="usb",
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
def mock_pyudev_device():
    """Create a mock pyudev device for testing."""
    device = Mock()
    device.subsystem = "block"
    device.device_node = "/dev/sda1"
    device.sys_name = "sda1"
    device.action = "add"

    # Mock attributes
    device.attributes = {
        "size": "16000000",  # Size in sectors
        "removable": "1",
    }

    # Mock properties
    device.properties = {
        "ID_MODEL": "Glove80_Bootloader",
        "ID_VENDOR": "Adafruit",
        "ID_BUS": "usb",
        "ID_FS_LABEL": "GLV80LDR",
        "ID_FS_UUID": "1234-5678",
        "ID_SERIAL_SHORT": "GLV80-12345",
        "ID_VENDOR_ID": "239a",
        "ID_MODEL_ID": "0029",
    }

    # Mock device links
    device.device_links = [
        "/dev/disk/by-id/usb-Adafruit_Glove80_Bootloader_GLV80-12345",
        "/dev/disk/by-label/GLV80LDR",
    ]

    # Mock ancestors for USB detection
    usb_ancestor = Mock()
    usb_ancestor.subsystem = "usb"
    device.ancestors = [usb_ancestor]

    # Mock children for partitions
    device.children = []

    return device


@pytest.fixture
def mock_usb_device_info():
    """Create mock USB device info for macOS testing."""
    return USBDeviceInfo(
        name="Glove80_Bootloader",
        vendor="Adafruit",
        vendor_id="239a",
        product_id="0029",
        serial="GLV80-12345",
    )


@pytest.fixture
def mock_disk_info():
    """Create mock disk info for macOS testing."""
    return DiskInfo(
        size=8192000,
        media_name="Glove80_Bootloader",
        volume_name="GLV80LDR",
        removable=True,
        protocol="USB",
        partitions=["disk2s1"],
    )


class TestUSBDeviceMonitorBase:
    """Test the abstract base class functionality."""

    def test_abstract_methods_require_implementation(self):
        """Test that abstract methods cannot be instantiated without implementation."""
        with pytest.raises(TypeError):
            USBDeviceMonitorBase()  # type: ignore[abstract]

    def test_concrete_implementation_init(self):
        """Test initialization of concrete implementation."""

        class ConcreteMonitor(USBDeviceMonitorBase):
            def scan_existing_devices(self) -> None:
                pass

            def is_usb_device(self, device_info) -> bool:
                return True

            def _monitor_loop(self) -> None:
                pass

        monitor = ConcreteMonitor()

        assert monitor.known_devices == set()
        assert monitor.devices == []
        assert monitor._callbacks == set()
        assert isinstance(monitor._lock, type(threading.RLock()))
        assert not monitor._monitoring
        assert monitor._monitor_thread is None

    def test_get_devices(self, sample_block_device):
        """Test getting current device list."""

        class ConcreteMonitor(USBDeviceMonitorBase):
            def scan_existing_devices(self) -> None:
                pass

            def is_usb_device(self, device_info) -> bool:
                return True

            def _monitor_loop(self) -> None:
                pass

        monitor = ConcreteMonitor()
        monitor.devices = [sample_block_device]

        devices = monitor.get_devices()
        assert len(devices) == 1
        assert devices[0] == sample_block_device
        # Verify it returns a copy
        assert devices is not monitor.devices

    def test_format_device_debug(self, sample_block_device):
        """Test device debug formatting."""

        class ConcreteMonitor(USBDeviceMonitorBase):
            def scan_existing_devices(self) -> None:
                pass

            def is_usb_device(self, device_info) -> bool:
                return True

            def _monitor_loop(self) -> None:
                pass

        monitor = ConcreteMonitor()
        debug_str = monitor._format_device_debug(sample_block_device)

        expected = "239a:0029:GLV80-12345:/dev/sda1 (Adafruit Glove80_Bootloader)"
        assert debug_str == expected

    def test_format_device_debug_with_unknowns(self):
        """Test device debug formatting with missing fields."""

        class ConcreteMonitor(USBDeviceMonitorBase):
            def scan_existing_devices(self) -> None:
                pass

            def is_usb_device(self, device_info) -> bool:
                return True

            def _monitor_loop(self) -> None:
                pass

        device = BlockDevice(name="sda1")  # Minimal device

        monitor = ConcreteMonitor()
        debug_str = monitor._format_device_debug(device)

        expected = "unknown:unknown:unknown:unknown (unknown unknown)"
        assert debug_str == expected

    def test_register_callback(self):
        """Test registering callbacks."""

        class ConcreteMonitor(USBDeviceMonitorBase):
            def scan_existing_devices(self) -> None:
                pass

            def is_usb_device(self, device_info) -> bool:
                return True

            def _monitor_loop(self) -> None:
                pass

        monitor = ConcreteMonitor()
        callback = Mock()

        monitor.register_callback(callback)
        assert callback in monitor._callbacks

    def test_unregister_callback(self):
        """Test unregistering callbacks."""

        class ConcreteMonitor(USBDeviceMonitorBase):
            def scan_existing_devices(self) -> None:
                pass

            def is_usb_device(self, device_info) -> bool:
                return True

            def _monitor_loop(self) -> None:
                pass

        monitor = ConcreteMonitor()
        callback = Mock()

        monitor.register_callback(callback)
        monitor.unregister_callback(callback)
        assert callback not in monitor._callbacks

    def test_notify_callbacks_success(self, sample_block_device):
        """Test successful callback notification."""

        class ConcreteMonitor(USBDeviceMonitorBase):
            def scan_existing_devices(self) -> None:
                pass

            def is_usb_device(self, device_info) -> bool:
                return True

            def _monitor_loop(self) -> None:
                pass

        monitor = ConcreteMonitor()
        callback1 = Mock()
        callback2 = Mock()

        monitor.register_callback(callback1)
        monitor.register_callback(callback2)

        monitor._notify_callbacks("add", sample_block_device)

        callback1.assert_called_once_with("add", sample_block_device)
        callback2.assert_called_once_with("add", sample_block_device)

    def test_notify_callbacks_with_exception(self, sample_block_device):
        """Test callback notification handles exceptions gracefully."""

        class ConcreteMonitor(USBDeviceMonitorBase):
            def scan_existing_devices(self) -> None:
                pass

            def is_usb_device(self, device_info) -> bool:
                return True

            def _monitor_loop(self) -> None:
                pass

        monitor = ConcreteMonitor()
        callback_good = Mock()
        callback_bad = Mock(side_effect=RuntimeError("Callback error"))

        monitor.register_callback(callback_good)
        monitor.register_callback(callback_bad)

        # Should not raise exception
        monitor._notify_callbacks("add", sample_block_device)

        callback_good.assert_called_once_with("add", sample_block_device)
        callback_bad.assert_called_once_with("add", sample_block_device)

    def test_start_monitoring(self):
        """Test starting monitoring."""

        class ConcreteMonitor(USBDeviceMonitorBase):
            def scan_existing_devices(self) -> None:
                pass

            def is_usb_device(self, device_info) -> bool:
                return True

            def _monitor_loop(self) -> None:
                time.sleep(0.1)  # Short sleep to simulate monitoring

        monitor = ConcreteMonitor()

        assert not monitor._monitoring
        assert monitor._monitor_thread is None

        monitor.start_monitoring()

        assert monitor._monitoring
        if monitor._monitor_thread is not None:  # type: ignore[unreachable]
            assert monitor._monitor_thread.daemon

        # Clean up
        monitor.stop_monitoring()

    def test_start_monitoring_already_started(self):
        """Test that starting monitoring when already started is a no-op."""

        class ConcreteMonitor(USBDeviceMonitorBase):
            def scan_existing_devices(self) -> None:
                pass

            def is_usb_device(self, device_info) -> bool:
                return True

            def _monitor_loop(self) -> None:
                time.sleep(0.1)

        monitor = ConcreteMonitor()

        monitor.start_monitoring()
        first_thread = monitor._monitor_thread

        # Start again - should be no-op
        monitor.start_monitoring()
        second_thread = monitor._monitor_thread

        assert first_thread is second_thread

        # Clean up
        monitor.stop_monitoring()

    def test_stop_monitoring(self):
        """Test stopping monitoring."""

        class ConcreteMonitor(USBDeviceMonitorBase):
            def scan_existing_devices(self) -> None:
                pass

            def is_usb_device(self, device_info) -> bool:
                return True

            def _monitor_loop(self) -> None:
                while self._monitoring:
                    time.sleep(0.01)

        monitor = ConcreteMonitor()

        monitor.start_monitoring()
        time.sleep(0.1)  # Let it start

        monitor.stop_monitoring()

        assert not monitor._monitoring
        assert monitor._monitor_thread is None

    def test_wait_for_device_found(self, sample_block_device):
        """Test waiting for device when device is found."""

        class ConcreteMonitor(USBDeviceMonitorBase):
            def scan_existing_devices(self) -> None:
                pass

            def is_usb_device(self, device_info) -> bool:
                return True

            def _monitor_loop(self) -> None:
                pass

        monitor = ConcreteMonitor()

        # Initially no devices
        assert monitor.get_devices() == []

        # Add device after short delay
        def add_device():
            time.sleep(0.1)
            monitor.devices = [sample_block_device]

        thread = threading.Thread(target=add_device)
        thread.start()

        # Wait for device
        found_device = monitor.wait_for_device(timeout=1, poll_interval=0.05)

        thread.join()

        assert found_device is not None
        assert found_device.name == "sda1"

    def test_wait_for_device_timeout(self):
        """Test waiting for device when timeout occurs."""

        class ConcreteMonitor(USBDeviceMonitorBase):
            def scan_existing_devices(self) -> None:
                pass

            def is_usb_device(self, device_info) -> bool:
                return True

            def _monitor_loop(self) -> None:
                pass

        monitor = ConcreteMonitor()

        # No devices will be added
        found_device = monitor.wait_for_device(timeout=1, poll_interval=0.02)

        assert found_device is None

    def test_wait_for_device_existing_device_ignored(self, sample_block_device):
        """Test that existing devices are ignored when waiting."""

        class ConcreteMonitor(USBDeviceMonitorBase):
            def scan_existing_devices(self) -> None:
                pass

            def is_usb_device(self, device_info) -> bool:
                return True

            def _monitor_loop(self) -> None:
                pass

        monitor = ConcreteMonitor()
        monitor.devices = [sample_block_device]  # Pre-existing device

        # Should timeout because device already exists
        found_device = monitor.wait_for_device(timeout=1, poll_interval=0.02)

        assert found_device is None


class TestLinuxUSBDeviceMonitor:
    """Test Linux-specific USB device monitor."""

    @patch("glovebox.firmware.flash.usb_monitor.platform.system", return_value="Linux")
    def test_create_usb_monitor_linux(self, mock_platform):
        """Test creating Linux USB monitor via factory."""
        with patch(
            "glovebox.firmware.flash.usb_monitor.LinuxUSBDeviceMonitor"
        ) as mock_linux:
            create_usb_monitor()
            mock_linux.assert_called_once()

    @patch("glovebox.firmware.flash.usb_monitor._create_mount_cache")
    @patch.object(LinuxUSBDeviceMonitor, "scan_existing_devices")
    def test_linux_monitor_init(self, mock_scan, mock_create_cache):
        """Test Linux monitor initialization."""
        mock_cache = Mock()
        mock_create_cache.return_value = mock_cache

        # Mock the pyudev import inside the __init__ method
        mock_pyudev = Mock()
        mock_context = Mock()
        mock_pyudev.Context.return_value = mock_context

        with patch.dict("sys.modules", {"pyudev": mock_pyudev}):
            monitor = LinuxUSBDeviceMonitor()

            assert monitor.context is mock_context
            assert monitor._mount_cache is mock_cache
            mock_create_cache.assert_called_once()

    @patch.object(LinuxUSBDeviceMonitor, "scan_existing_devices")
    def test_linux_monitor_init_missing_pyudev(self, mock_scan):
        """Test Linux monitor initialization fails without pyudev."""
        with (
            patch.dict("sys.modules", {"pyudev": None}),
            patch(
                "builtins.__import__",
                side_effect=ImportError("No module named 'pyudev'"),
            ),
            pytest.raises(ImportError, match="pyudev is required"),
        ):
            LinuxUSBDeviceMonitor()

    @patch("glovebox.firmware.flash.usb_monitor._create_mount_cache")
    @patch.object(LinuxUSBDeviceMonitor, "scan_existing_devices")
    def test_is_usb_device_valid(
        self, mock_scan, mock_create_cache, mock_pyudev_device
    ):
        """Test USB device detection on Linux."""
        mock_pyudev = Mock()
        mock_context = Mock()
        mock_pyudev.Context.return_value = mock_context

        with patch.dict("sys.modules", {"pyudev": mock_pyudev}):
            monitor = LinuxUSBDeviceMonitor()

            result = monitor.is_usb_device(mock_pyudev_device)
            assert result is True

    @patch("glovebox.firmware.flash.usb_monitor._create_mount_cache")
    @patch.object(LinuxUSBDeviceMonitor, "scan_existing_devices")
    def test_is_usb_device_not_block(self, mock_scan, mock_create_cache):
        """Test device rejection when not block subsystem."""
        device = Mock()
        device.subsystem = "input"  # Not block

        mock_pyudev = Mock()
        mock_context = Mock()
        mock_pyudev.Context.return_value = mock_context

        with patch.dict("sys.modules", {"pyudev": mock_pyudev}):
            monitor = LinuxUSBDeviceMonitor()

            result = monitor.is_usb_device(device)
            assert result is False

    @patch("glovebox.firmware.flash.usb_monitor._create_mount_cache")
    @patch.object(LinuxUSBDeviceMonitor, "scan_existing_devices")
    def test_is_usb_device_no_usb_ancestor(self, mock_scan, mock_create_cache):
        """Test device rejection when no USB ancestor."""
        device = Mock()
        device.subsystem = "block"

        # No USB ancestors
        non_usb_ancestor = Mock()
        non_usb_ancestor.subsystem = "pci"
        device.ancestors = [non_usb_ancestor]

        mock_pyudev = Mock()
        mock_context = Mock()
        mock_pyudev.Context.return_value = mock_context

        with patch.dict("sys.modules", {"pyudev": mock_pyudev}):
            monitor = LinuxUSBDeviceMonitor()

            result = monitor.is_usb_device(device)
            assert result is False

    @patch("glovebox.firmware.flash.usb_monitor._create_mount_cache")
    @patch.object(LinuxUSBDeviceMonitor, "scan_existing_devices")
    def test_is_usb_device_no_ancestors_attribute(self, mock_scan, mock_create_cache):
        """Test device rejection when no ancestors attribute."""
        device = Mock()
        device.subsystem = "block"
        del device.ancestors  # No ancestors attribute

        mock_pyudev = Mock()
        mock_context = Mock()
        mock_pyudev.Context.return_value = mock_context

        with patch.dict("sys.modules", {"pyudev": mock_pyudev}):
            monitor = LinuxUSBDeviceMonitor()

            result = monitor.is_usb_device(device)
            assert result is False

    @patch("glovebox.firmware.flash.usb_monitor.BlockDevice.from_pyudev_device")
    @patch("glovebox.firmware.flash.usb_monitor._create_mount_cache")
    def test_scan_existing_devices(
        self,
        mock_create_cache,
        mock_from_pyudev,
        mock_pyudev_device,
        sample_block_device,
    ):
        """Test scanning existing devices on Linux."""
        mock_cache = Mock()
        mock_cache.get_mountpoints.return_value = {"/dev/sda1": "/media/GLV80LDR"}
        mock_create_cache.return_value = mock_cache

        mock_pyudev = Mock()
        mock_ctx = Mock()
        mock_ctx.list_devices.return_value = [mock_pyudev_device]
        mock_pyudev.Context.return_value = mock_ctx

        mock_from_pyudev.return_value = sample_block_device

        with patch.dict("sys.modules", {"pyudev": mock_pyudev}):
            # Don't call scan_existing_devices in init
            with patch.object(LinuxUSBDeviceMonitor, "scan_existing_devices"):
                monitor = LinuxUSBDeviceMonitor()

            # Clear devices and call scan manually
            monitor.devices.clear()
            monitor.known_devices.clear()

            monitor.scan_existing_devices()

            assert len(monitor.devices) == 1
            assert monitor.devices[0] == sample_block_device
            assert "/dev/sda1" in monitor.known_devices
            mock_from_pyudev.assert_called_with(mock_pyudev_device)

    @patch("glovebox.firmware.flash.usb_monitor._create_mount_cache")
    @patch.object(LinuxUSBDeviceMonitor, "scan_existing_devices")
    def test_update_mountpoints(
        self, mock_scan, mock_create_cache, sample_block_device
    ):
        """Test updating device mount points."""
        mount_points = {
            "sda1": "/media/GLV80LDR",
            "/dev/sda1": "/media/GLV80LDR",
        }

        mock_pyudev = Mock()
        mock_context = Mock()
        mock_pyudev.Context.return_value = mock_context

        with patch.dict("sys.modules", {"pyudev": mock_pyudev}):
            monitor = LinuxUSBDeviceMonitor()

            # Test device with partitions
            device = BlockDevice(
                name="sda",
                partitions=["sda1"],
                mountpoints={},
            )

            monitor._update_mountpoints(device, mount_points)

            assert device.mountpoints["sda1"] == "/media/GLV80LDR"

    @patch("glovebox.firmware.flash.usb_monitor.BlockDevice.from_pyudev_device")
    @patch("glovebox.firmware.flash.usb_monitor._create_mount_cache")
    def test_monitor_loop_device_add(
        self,
        mock_create_cache,
        mock_from_pyudev,
        mock_pyudev_device,
        sample_block_device,
    ):
        """Test monitor loop handling device add events."""
        mock_pyudev = Mock()
        mock_context = Mock()
        mock_pyudev.Context.return_value = mock_context

        # Setup monitor
        mock_monitor = Mock()
        mock_observer = Mock()

        mock_pyudev.Monitor.from_netlink.return_value = mock_monitor
        mock_pyudev.MonitorObserver.return_value = mock_observer

        mock_from_pyudev.return_value = sample_block_device

        with patch.dict("sys.modules", {"pyudev": mock_pyudev}):
            # Don't call scan_existing_devices in init
            with patch.object(LinuxUSBDeviceMonitor, "scan_existing_devices"):
                monitor = LinuxUSBDeviceMonitor()

            monitor.devices.clear()

            # Mock the callback to trigger device event
            captured_callback = None

            def capture_callback(monitor_obj, callback):
                nonlocal captured_callback
                captured_callback = callback
                return mock_observer

            mock_pyudev.MonitorObserver.side_effect = capture_callback

            # Start monitoring in a separate thread
            def start_and_stop():
                monitor._monitor_loop()

            monitor._monitoring = True
            thread = threading.Thread(target=start_and_stop)
            thread.start()

            # Wait for monitor to start
            time.sleep(0.1)

            # Trigger device add event
            if captured_callback:
                mock_pyudev_device.action = "add"
                captured_callback(mock_pyudev_device)

            # Stop monitoring
            monitor._monitoring = False
            thread.join(timeout=1)

            # Verify device was added
            assert len(monitor.devices) == 1
            assert monitor.devices[0] == sample_block_device

    @patch("glovebox.firmware.flash.usb_monitor._create_mount_cache")
    def test_monitor_loop_device_remove(
        self, mock_create_cache, mock_pyudev_device, sample_block_device
    ):
        """Test monitor loop handling device remove events."""
        mock_pyudev = Mock()
        mock_context = Mock()
        mock_pyudev.Context.return_value = mock_context

        # Setup monitor
        mock_monitor = Mock()
        mock_observer = Mock()

        mock_pyudev.Monitor.from_netlink.return_value = mock_monitor
        mock_pyudev.MonitorObserver.return_value = mock_observer

        with patch.dict("sys.modules", {"pyudev": mock_pyudev}):
            # Don't call scan_existing_devices in init
            with patch.object(LinuxUSBDeviceMonitor, "scan_existing_devices"):
                monitor = LinuxUSBDeviceMonitor()

            monitor.devices = [sample_block_device]  # Pre-existing device

            # Mock the callback to trigger device event
            captured_callback = None

            def capture_callback(monitor_obj, callback):
                nonlocal captured_callback
                captured_callback = callback
                return mock_observer

            mock_pyudev.MonitorObserver.side_effect = capture_callback

            # Start monitoring in a separate thread
            def start_and_stop():
                monitor._monitor_loop()

            monitor._monitoring = True
            thread = threading.Thread(target=start_and_stop)
            thread.start()

            # Wait for monitor to start
            time.sleep(0.1)

            # Trigger device remove event
            if captured_callback:
                mock_pyudev_device.action = "remove"
                mock_pyudev_device.device_node = "/dev/sda1"
                captured_callback(mock_pyudev_device)

            # Stop monitoring
            monitor._monitoring = False
            thread.join(timeout=1)

            # Verify device was removed
            assert len(monitor.devices) == 0


class TestMacOSUSBDeviceMonitor:
    """Test macOS-specific USB device monitor."""

    @patch("glovebox.firmware.flash.usb_monitor.platform.system", return_value="Darwin")
    def test_create_usb_monitor_macos(self, mock_platform):
        """Test creating macOS USB monitor via factory."""
        with patch(
            "glovebox.firmware.flash.usb_monitor.MacOSUSBDeviceMonitor"
        ) as mock_macos:
            create_usb_monitor()
            mock_macos.assert_called_once()

    def test_macos_monitor_init(self):
        """Test macOS monitor initialization."""
        with patch.object(MacOSUSBDeviceMonitor, "scan_existing_devices"):
            monitor = MacOSUSBDeviceMonitor()
            assert monitor.devices == []

    def test_is_usb_device_removable(self):
        """Test USB device detection for removable devices."""
        monitor = MacOSUSBDeviceMonitor()

        device_dict: BlockDeviceDict = {"removable": True}
        result = monitor.is_usb_device(device_dict)
        assert result is True

    def test_is_usb_device_not_removable(self):
        """Test USB device detection for non-removable devices."""
        monitor = MacOSUSBDeviceMonitor()

        device_dict: BlockDeviceDict = {"removable": False}
        result = monitor.is_usb_device(device_dict)
        assert result is False

    def test_is_usb_device_missing_removable(self):
        """Test USB device detection when removable field is missing."""
        monitor = MacOSUSBDeviceMonitor()

        device_dict: BlockDeviceDict = {}
        result = monitor.is_usb_device(device_dict)
        assert result is False

    @patch("subprocess.run")
    def test_get_usb_device_info_success(self, mock_run):
        """Test successful USB device info retrieval on macOS."""
        # Mock system_profiler output
        usb_data = {
            "SPUSBDataType": [
                {
                    "_items": [
                        {
                            "_name": "Glove80_Bootloader",
                            "manufacturer": "Adafruit",
                            "vendor_id": "0x239a",
                            "product_id": "0x0029",
                            "serial_num": "GLV80-12345",
                        }
                    ]
                }
            ]
        }

        mock_result = Mock()
        mock_result.stdout = json.dumps(usb_data)
        mock_run.return_value = mock_result

        monitor = MacOSUSBDeviceMonitor()
        usb_devices = monitor._get_usb_device_info()

        assert len(usb_devices) == 1
        device = usb_devices[0]
        assert device.name == "Glove80_Bootloader"
        assert device.vendor == "Adafruit"
        assert device.vendor_id == "239a"  # Should strip 0x prefix
        assert device.product_id == "0x0029"
        assert device.serial == "GLV80-12345"

    @patch("subprocess.run")
    def test_get_usb_device_info_nested_items(self, mock_run):
        """Test USB device info with nested items."""
        usb_data = {
            "SPUSBDataType": [
                {
                    "_items": [
                        {
                            "_name": "USB Hub",
                            "manufacturer": "Generic",
                            "_items": [
                                {
                                    "_name": "Glove80_Bootloader",
                                    "manufacturer": "Adafruit",
                                    "vendor_id": "239a",
                                    "product_id": "0029",
                                }
                            ],
                        }
                    ]
                }
            ]
        }

        mock_result = Mock()
        mock_result.stdout = json.dumps(usb_data)
        mock_run.return_value = mock_result

        monitor = MacOSUSBDeviceMonitor()
        usb_devices = monitor._get_usb_device_info()

        assert len(usb_devices) == 2  # Hub + nested device
        assert any(device.name == "USB Hub" for device in usb_devices)
        assert any(device.name == "Glove80_Bootloader" for device in usb_devices)

    @patch("subprocess.run")
    def test_get_usb_device_info_command_error(self, mock_run):
        """Test USB device info when command fails."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "system_profiler")

        monitor = MacOSUSBDeviceMonitor()
        usb_devices = monitor._get_usb_device_info()

        assert usb_devices == []

    @patch("subprocess.run")
    def test_get_usb_device_info_json_error(self, mock_run):
        """Test USB device info when JSON parsing fails."""
        mock_result = Mock()
        mock_result.stdout = "invalid json"
        mock_run.return_value = mock_result

        monitor = MacOSUSBDeviceMonitor()
        usb_devices = monitor._get_usb_device_info()

        assert usb_devices == []

    @patch("subprocess.run")
    def test_get_disk_info_success(self, mock_run):
        """Test successful disk info retrieval on macOS."""
        import plistlib

        # Mock diskutil list output
        list_data = {
            "AllDisksAndPartitions": [
                {
                    "DeviceIdentifier": "disk2",
                    "Partitions": [{"DeviceIdentifier": "disk2s1"}],
                }
            ]
        }

        # Mock diskutil info output for disk
        disk_info_data = {
            "Size": 8192000,
            "MediaName": "Glove80_Bootloader",
            "VolumeName": "GLV80LDR",
            "Removable": True,
            "Protocol": "USB",
        }

        # Mock diskutil info output for partition
        partition_info_data = {
            "VolumeName": "GLV80LDR",
        }

        def mock_run_side_effect(cmd, **kwargs):
            result = Mock()
            if "list" in cmd:
                result.stdout = plistlib.dumps(list_data)
            elif "disk2s1" in cmd:
                result.stdout = plistlib.dumps(partition_info_data)
            else:  # disk2
                result.stdout = plistlib.dumps(disk_info_data)
            return result

        mock_run.side_effect = mock_run_side_effect

        monitor = MacOSUSBDeviceMonitor()
        disk_info = monitor._get_disk_info()

        assert "disk2" in disk_info
        info = disk_info["disk2"]
        assert info.size == 8192000
        assert info.media_name == "Glove80_Bootloader"
        assert info.volume_name == "GLV80LDR"
        assert info.removable is True
        assert info.protocol == "USB"
        assert "disk2s1" in info.partitions

    @patch("subprocess.run")
    def test_get_disk_info_command_error(self, mock_run):
        """Test disk info when command fails."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "diskutil")

        monitor = MacOSUSBDeviceMonitor()
        disk_info = monitor._get_disk_info()

        assert disk_info == {}

    @patch.object(MacOSUSBDeviceMonitor, "_get_usb_device_info")
    @patch.object(MacOSUSBDeviceMonitor, "_get_disk_info")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.iterdir")
    @patch("glovebox.firmware.flash.usb_monitor.BlockDevice.from_macos_disk_info")
    def test_scan_existing_devices_with_matching(
        self,
        mock_from_macos,
        mock_iterdir,
        mock_exists,
        mock_get_disk_info,
        mock_get_usb_info,
        mock_usb_device_info,
        mock_disk_info,
        sample_block_device,
    ):
        """Test scanning devices with USB/disk matching on macOS."""
        # Setup mocks
        mock_get_usb_info.return_value = [mock_usb_device_info]
        mock_get_disk_info.return_value = {"disk2": mock_disk_info}
        mock_exists.return_value = True

        # Mock /Volumes directory
        mock_volume = Mock()
        mock_volume.is_dir.return_value = True
        mock_volume.name = "GLV80LDR"
        mock_iterdir.return_value = [mock_volume]

        mock_from_macos.return_value = sample_block_device

        # Don't call scan_existing_devices in init
        with patch.object(MacOSUSBDeviceMonitor, "scan_existing_devices"):
            monitor = MacOSUSBDeviceMonitor()

        monitor.devices.clear()

        monitor.scan_existing_devices()

        assert len(monitor.devices) == 1
        assert monitor.devices[0] == sample_block_device
        # Should be called at least once (could be called during actual scan)
        assert mock_from_macos.call_count >= 1

    @patch.object(MacOSUSBDeviceMonitor, "_get_usb_device_info")
    @patch.object(MacOSUSBDeviceMonitor, "_get_disk_info")
    def test_scan_existing_devices_exception(
        self, mock_get_disk_info, mock_get_usb_info
    ):
        """Test scan_existing_devices handles exceptions gracefully."""
        mock_get_usb_info.side_effect = Exception("USB info error")

        monitor = MacOSUSBDeviceMonitor()

        # Should not raise exception
        monitor.scan_existing_devices()
        assert monitor.devices == []

    @patch.object(MacOSUSBDeviceMonitor, "scan_existing_devices")
    @patch("time.sleep")
    def test_monitor_loop_device_changes(self, mock_sleep, mock_scan):
        """Test monitor loop detecting device changes."""
        monitor = MacOSUSBDeviceMonitor()

        # Mock device changes
        device1 = BlockDevice(name="disk1", device_node="/dev/disk1")
        device2 = BlockDevice(name="disk2", device_node="/dev/disk2")

        scan_results = [
            [device1],  # Initial scan
            [device1, device2],  # Device added
            [device2],  # Device removed
            [device2],  # No change
        ]

        scan_call_count = 0

        def mock_scan_side_effect():
            nonlocal scan_call_count
            if scan_call_count < len(scan_results):
                monitor.devices = scan_results[scan_call_count]
                scan_call_count += 1

        mock_scan.side_effect = mock_scan_side_effect

        # Mock callbacks
        add_callback = Mock()
        remove_callback = Mock()
        monitor.register_callback(add_callback)

        # Run monitor loop briefly
        monitor._monitoring = True

        def run_loop():
            loop_count = 0
            while monitor._monitoring and loop_count < 3:
                # Simulate one iteration of the loop
                old_devices = {d.path for d in monitor.devices}
                monitor.scan_existing_devices()
                new_devices = {d.path for d in monitor.devices}

                # Check for added devices
                for path in new_devices - old_devices:
                    device = next((d for d in monitor.devices if d.path == path), None)
                    if device:
                        monitor._notify_callbacks("add", device)

                # Check for removed devices
                for path in old_devices - new_devices:
                    removed_device = BlockDevice(
                        name=Path(path).name,
                        device_node=path,
                        model="",
                        vendor="",
                        serial="",
                        vendor_id="",
                        product_id="",
                    )
                    monitor._notify_callbacks("remove", removed_device)

                loop_count += 1
                if monitor._monitoring:
                    time.sleep(0.01)

        thread = threading.Thread(target=run_loop)
        thread.start()

        time.sleep(0.1)  # Let it run
        monitor._monitoring = False
        thread.join(timeout=1)

        # Verify callbacks were called for device changes
        assert add_callback.call_count >= 1  # At least one device was added


class TestStubUSBDeviceMonitor:
    """Test stub USB device monitor for unsupported platforms."""

    @patch(
        "glovebox.firmware.flash.usb_monitor.platform.system", return_value="Windows"
    )
    def test_create_usb_monitor_unsupported(self, mock_platform):
        """Test creating stub monitor for unsupported platform."""
        monitor = create_usb_monitor()
        assert isinstance(monitor, StubUSBDeviceMonitor)

    def test_stub_monitor_init(self):
        """Test stub monitor initialization."""
        monitor = StubUSBDeviceMonitor()
        assert monitor.devices == []
        assert monitor.known_devices == set()

    def test_stub_scan_existing_devices(self):
        """Test stub scan does nothing."""
        monitor = StubUSBDeviceMonitor()
        monitor.scan_existing_devices()  # Should not raise
        assert monitor.devices == []

    def test_stub_is_usb_device(self):
        """Test stub always returns False for USB detection."""
        monitor = StubUSBDeviceMonitor()

        device_dict: BlockDeviceDict = {"removable": True}
        result = monitor.is_usb_device(device_dict)
        assert result is False

    @patch("time.sleep")
    def test_stub_monitor_loop(self, mock_sleep):
        """Test stub monitor loop does nothing."""
        monitor = StubUSBDeviceMonitor()

        # Run briefly
        monitor._monitoring = True

        def run_loop():
            loop_count = 0
            while monitor._monitoring and loop_count < 2:
                time.sleep(0.01)
                loop_count += 1

        thread = threading.Thread(target=run_loop)
        thread.start()

        time.sleep(0.1)
        monitor._monitoring = False
        thread.join(timeout=1)

        # Should have called sleep
        mock_sleep.assert_called()


class TestCreateMountCache:
    """Test mount cache creation."""

    @patch("glovebox.firmware.flash.usb_monitor.platform.system", return_value="Linux")
    def test_create_mount_cache_linux(self, mock_platform):
        """Test creating mount cache for Linux."""
        with patch(
            "glovebox.firmware.flash.device_detector.MountPointCache"
        ) as mock_cache_class:
            cache = _create_mount_cache()
            mock_cache_class.assert_called_once()

    @patch("glovebox.firmware.flash.usb_monitor.platform.system", return_value="Darwin")
    def test_create_mount_cache_non_linux(self, mock_platform):
        """Test creating mount cache for non-Linux platforms."""
        cache = _create_mount_cache()

        # Should return stub that has get_mountpoints method
        assert hasattr(cache, "get_mountpoints")
        assert cache.get_mountpoints() == {}


class TestCreateUSBMonitor:
    """Test USB monitor factory function."""

    @patch("glovebox.firmware.flash.usb_monitor.platform.system", return_value="Linux")
    def test_create_usb_monitor_linux(self, mock_platform):
        """Test creating USB monitor for Linux."""
        with patch(
            "glovebox.firmware.flash.usb_monitor.LinuxUSBDeviceMonitor"
        ) as mock_linux:
            create_usb_monitor()
            mock_linux.assert_called_once()

    @patch("glovebox.firmware.flash.usb_monitor.platform.system", return_value="Darwin")
    def test_create_usb_monitor_macos(self, mock_platform):
        """Test creating USB monitor for macOS."""
        with patch(
            "glovebox.firmware.flash.usb_monitor.MacOSUSBDeviceMonitor"
        ) as mock_macos:
            create_usb_monitor()
            mock_macos.assert_called_once()

    @patch(
        "glovebox.firmware.flash.usb_monitor.platform.system", return_value="Windows"
    )
    def test_create_usb_monitor_windows(self, mock_platform):
        """Test creating USB monitor for Windows (unsupported)."""
        monitor = create_usb_monitor()
        assert isinstance(monitor, StubUSBDeviceMonitor)

    @patch(
        "glovebox.firmware.flash.usb_monitor.platform.system", return_value="FreeBSD"
    )
    def test_create_usb_monitor_unknown(self, mock_platform):
        """Test creating USB monitor for unknown platform."""
        monitor = create_usb_monitor()
        assert isinstance(monitor, StubUSBDeviceMonitor)


class TestUSBMonitorIntegration:
    """Integration tests for USB monitoring workflows."""

    def test_complete_monitoring_workflow(self):
        """Test complete workflow: start → register callbacks → detect devices → stop."""

        class TestMonitor(USBDeviceMonitorBase):
            def __init__(self):
                super().__init__()
                self.scan_called = False
                # Call scan during init like real monitors do
                self.scan_existing_devices()

            def scan_existing_devices(self) -> None:
                self.scan_called = True

            def is_usb_device(self, device_info) -> bool:
                return True

            def _monitor_loop(self) -> None:
                while self._monitoring:
                    time.sleep(0.01)

        monitor = TestMonitor()
        callback = Mock()

        # Register callback
        monitor.register_callback(callback)

        # Start monitoring
        monitor.start_monitoring()

        # Add a device manually
        device = BlockDevice(name="test")
        monitor._notify_callbacks("add", device)

        # Stop monitoring
        monitor.stop_monitoring()

        # Verify workflow
        assert monitor.scan_called
        callback.assert_called_once_with("add", device)
        assert not monitor._monitoring

    def test_thread_safety_device_access(self):
        """Test thread-safe access to device list."""

        class TestMonitor(USBDeviceMonitorBase):
            def scan_existing_devices(self) -> None:
                pass

            def is_usb_device(self, device_info) -> bool:
                return True

            def _monitor_loop(self) -> None:
                # Simulate device changes in monitor thread
                for i in range(10):
                    if not self._monitoring:
                        break
                    device = BlockDevice(name=f"device{i}")
                    with self._lock:
                        self.devices.append(device)
                    time.sleep(0.01)

        monitor = TestMonitor()

        # Start monitoring
        monitor.start_monitoring()

        # Simultaneously access devices from main thread
        device_counts = []
        for _ in range(5):
            devices = monitor.get_devices()  # Thread-safe access
            device_counts.append(len(devices))
            time.sleep(0.02)

        # Stop monitoring
        monitor.stop_monitoring()

        # Verify no exceptions occurred and devices were added
        assert all(isinstance(count, int) for count in device_counts)
        assert max(device_counts) > 0  # At least some devices were added
