"""Platform-specific USB device monitoring implementations."""

import abc
import platform
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from glovebox.core.structlog_logger import get_struct_logger
from glovebox.firmware.flash.models import (
    BlockDevice,
    BlockDeviceDict,
    BlockDevicePathMap,
    DiskInfo,
    USBDevice,
    USBDeviceInfo,
)
from glovebox.protocols.mount_cache_protocol import MountCacheProtocol


logger = get_struct_logger(__name__)

# Union type for USB devices to support both storage and non-storage devices
USBDeviceType = BlockDevice | USBDevice


class USBDeviceMonitorBase(abc.ABC):
    """Abstract base class for USB device monitoring."""

    def __init__(self) -> None:
        """Initialize the USB device monitor."""
        self.known_devices: set[str] = set()
        self.devices: list[USBDeviceType] = []
        self._callbacks: set[Callable[[str, USBDeviceType], None]] = set()
        self._lock = threading.RLock()
        self._monitoring = False
        self._monitor_thread: threading.Thread | None = None

    @abc.abstractmethod
    def scan_existing_devices(self) -> None:
        """Scan existing USB block devices and populate the device list."""
        pass

    @abc.abstractmethod
    def is_usb_device(self, device_info: Any) -> bool:
        """Check if a device is USB-connected storage.

        Args:
            device_info: Platform-specific device info (pyudev Device on Linux,
                        BlockDeviceDict on macOS, etc.)
        """
        pass

    def get_devices(self) -> list[USBDeviceType]:
        """Get the current list of USB devices."""
        with self._lock:
            return self.devices.copy()

    def start_monitoring(self) -> None:
        """Start monitoring for USB device events."""
        if self._monitoring:
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Started USB device monitoring")

    def stop_monitoring(self) -> None:
        """Stop monitoring for USB device events."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
            self._monitor_thread = None
        logger.info("Stopped USB device monitoring")

    def _format_device_debug(self, device: USBDeviceType) -> str:
        """Format device information for debug logging in vid:pid:serial:dev format."""
        vid = getattr(device, "vendor_id", None) or "unknown"
        pid = getattr(device, "product_id", None) or "unknown"
        serial = getattr(device, "serial", None) or "unknown"
        dev = (
            getattr(device, "device_node", None)
            or getattr(device, "sys_path", None)
            or "unknown"
        )
        vendor = getattr(device, "vendor", None) or "unknown"
        model = getattr(device, "model", None) or "unknown"

        return f"{vid}:{pid}:{serial}:{dev} ({vendor} {model})"

    @abc.abstractmethod
    def _monitor_loop(self) -> None:
        """Main monitoring loop (platform-specific)."""
        pass

    def register_callback(self, callback: Callable[[str, USBDeviceType], None]) -> None:
        """Register a callback for device events."""
        self._callbacks.add(callback)

    def unregister_callback(
        self, callback: Callable[[str, USBDeviceType], None]
    ) -> None:
        """Unregister a callback for device events."""
        self._callbacks.discard(callback)

    def wait_for_device(
        self, timeout: int = 60, poll_interval: float = 0.5
    ) -> USBDeviceType | None:
        """Wait for a new USB device to be connected."""
        start_time = time.time()
        initial_devices = {
            getattr(d, "device_node", None) or getattr(d, "sys_path", None)
            for d in self.get_devices()
        }

        while time.time() - start_time < timeout:
            current_devices = self.get_devices()
            for device in current_devices:
                device_path = getattr(device, "device_node", None) or getattr(
                    device, "sys_path", None
                )
                if device_path not in initial_devices:
                    return device
            time.sleep(poll_interval)

        return None

    def _notify_callbacks(self, action: str, device: USBDeviceType) -> None:
        """Notify all registered callbacks of a device event."""
        for callback in self._callbacks:
            try:
                callback(action, device)
            except Exception as e:
                logger.error(f"Error in callback: {e}")


class LinuxUSBDeviceMonitor(USBDeviceMonitorBase):
    """Linux-specific USB device monitor using udev."""

    def __init__(self) -> None:
        """Initialize the Linux USB device monitor."""
        super().__init__()

        # Import pyudev only on Linux
        try:
            import pyudev  # type: ignore
        except ImportError as e:
            raise ImportError("pyudev is required for Linux USB monitoring") from e

        self.pyudev = pyudev

        self.context = pyudev.Context()
        self._observer: Any | None = None
        self._mount_cache: MountCacheProtocol = _create_mount_cache()
        self.scan_existing_devices()

    def scan_existing_devices(self) -> None:
        """Scan existing USB devices and populate the device list."""
        with self._lock:
            self.devices = []
            mount_points = self._mount_cache.get_mountpoints()

            for device in self.context.list_devices():
                if self.is_usb_device(device):
                    device_node = getattr(device, "device_node", None)
                    if device_node:
                        self.known_devices.add(device_node)

                    # Check if this is a storage device to maintain compatibility
                    if hasattr(device, "subsystem") and device.subsystem == "block":
                        block_device = BlockDevice.from_pyudev_device(device)
                        self._update_mountpoints(block_device, mount_points)
                        self.devices.append(block_device)
                        logger.debug(
                            f"Found existing storage device: {self._format_device_debug(block_device)}"
                        )
                    else:
                        # Handle non-storage USB devices
                        usb_device = USBDevice.from_pyudev_device(device)
                        self.devices.append(usb_device)
                        logger.debug(
                            f"Found existing USB device: {usb_device.name} ({usb_device.device_type})"
                        )

    def is_usb_device(self, device: Any) -> bool:
        """Check if a device is USB-connected."""
        if hasattr(device, "ancestors"):
            return any(parent.subsystem == "usb" for parent in device.ancestors)
        return False

    def _update_mountpoints(
        self, device: BlockDevice, mount_points: BlockDevicePathMap
    ) -> None:
        """Update device mount points from the cache."""
        for part in device.partitions:
            if part in mount_points:
                device.mountpoints[part] = mount_points[part]

        if device.name in mount_points:
            device.mountpoints[device.name] = mount_points[device.name]

    def _monitor_loop(self) -> None:
        """Main monitoring loop using udev."""
        monitor = self.pyudev.Monitor.from_netlink(self.context)
        # monitor.filter_by(subsystem="block")  # Removed to allow all USB device types

        def device_event(device: Any) -> None:
            # The device object has an action attribute
            action = device.action
            if action in ("add", "remove") and self.is_usb_device(device):
                if action == "add":
                    device_node = getattr(device, "device_node", None)
                    if device_node:
                        self.known_devices.add(device_node)

                    # Handle storage vs non-storage devices
                    if hasattr(device, "subsystem") and device.subsystem == "block":
                        # Wait for device to be fully initialized
                        if not getattr(device, "is_initialized", True):
                            logger.debug(
                                f"Waiting for device {device.sys_name} to be initialized"
                            )
                            # Give udev time to finish processing
                            time.sleep(0.5)

                        # Verify device node exists before creating BlockDevice
                        device_node = getattr(device, "device_node", None)
                        if device_node:
                            # Wait for device node to actually appear in filesystem
                            max_retries = 10
                            for retry in range(max_retries):
                                if Path(device_node).exists():
                                    break
                                if retry < max_retries - 1:
                                    logger.debug(
                                        f"Waiting for device node {device_node} to appear (attempt {retry + 1}/{max_retries})"
                                    )
                                    time.sleep(0.2)
                            else:
                                logger.warning(
                                    f"Device node {device_node} did not appear after {max_retries} attempts"
                                )
                                return

                        block_device = BlockDevice.from_pyudev_device(device)
                        with self._lock:
                            self.devices.append(block_device)
                        logger.debug(
                            f"USB storage device added: {self._format_device_debug(block_device)}"
                        )
                        self._notify_callbacks("add", block_device)
                    else:
                        usb_device = USBDevice.from_pyudev_device(device)
                        with self._lock:
                            self.devices.append(usb_device)
                        logger.debug(
                            f"USB device added: {usb_device.name} ({usb_device.device_type})"
                        )
                        self._notify_callbacks("add", usb_device)

                elif action == "remove":
                    # Find the device being removed for logging
                    removed_device = None
                    device_node = getattr(device, "device_node", None)
                    with self._lock:
                        for d in self.devices:
                            # Handle both BlockDevice and USBDevice types
                            device_path = getattr(d, "device_node", None) or getattr(
                                d, "sys_path", None
                            )
                            if device_path == device_node:
                                removed_device = d
                                break
                        if device_node:
                            self.devices = [
                                d
                                for d in self.devices
                                if (
                                    getattr(d, "device_node", None)
                                    or getattr(d, "sys_path", None)
                                )
                                != device_node
                            ]
                    if removed_device:
                        if isinstance(removed_device, BlockDevice):
                            logger.debug(
                                f"USB storage device removed: {self._format_device_debug(removed_device)}"
                            )
                        else:  # USBDevice
                            logger.debug(
                                f"USB device removed: {removed_device.name} ({removed_device.device_type})"
                            )

        self._observer = self.pyudev.MonitorObserver(monitor, callback=device_event)
        self._observer.start()

        while self._monitoring:
            time.sleep(0.5)

        if self._observer:
            self._observer.stop()


class MacOSUSBDeviceMonitor(USBDeviceMonitorBase):
    """macOS-specific USB device monitor using diskutil."""

    def __init__(self) -> None:
        """Initialize the macOS USB device monitor."""
        super().__init__()
        self.scan_existing_devices()

    def scan_existing_devices(self) -> None:
        """Scan existing USB block devices using diskutil and system_profiler."""
        with self._lock:
            self.devices = []

            try:
                # First, get USB device info from system_profiler
                usb_info = self._get_usb_device_info()

                # Then get disk info from diskutil
                disk_info = self._get_disk_info()

                # Also check /Volumes for mounted devices
                volumes_path = Path("/Volumes")
                mounted_volumes = set()
                if volumes_path.exists():
                    for volume in volumes_path.iterdir():
                        if volume.is_dir() and not volume.name.startswith("."):
                            mounted_volumes.add(volume.name)

                # Match USB devices with disk info and volumes
                for disk_name, disk_data in disk_info.items():
                    # Try to find matching USB info
                    usb_data = None
                    volume_name = disk_data.volume_name
                    media_name = disk_data.media_name

                    # Look for USB device by matching volume name, media name, disk identifier, or vendor
                    for usb_device in usb_info:
                        usb_name = usb_device.name.lower().strip()
                        usb_vendor = usb_device.vendor.lower().strip()
                        vol_name_lower = volume_name.lower().strip()
                        media_name_lower = media_name.lower().strip()

                        # Check various matching criteria
                        if (
                            # Match by volume name
                            (
                                vol_name_lower
                                and (
                                    usb_name in vol_name_lower
                                    or vol_name_lower in usb_name
                                )
                            )
                            or
                            # Match by media name
                            (
                                media_name_lower
                                and (
                                    usb_name in media_name_lower
                                    or media_name_lower in usb_name
                                )
                            )
                            or
                            # Match by vendor in volume/media name
                            (
                                vol_name_lower
                                and usb_vendor
                                and usb_vendor in vol_name_lower
                            )
                            or (
                                media_name_lower
                                and usb_vendor
                                and usb_vendor in media_name_lower
                            )
                        ):
                            usb_data = usb_device
                            logger.debug(
                                f"Matched USB device: {usb_device} to disk {disk_name}"
                            )
                            break

                    # Create BlockDevice using factory method
                    device = BlockDevice.from_macos_disk_info(
                        disk_name=disk_name,
                        disk_info=disk_data,
                        usb_info=usb_data,
                        mounted_volumes=mounted_volumes,
                    )

                    # Only add if it's a removable device or has USB info
                    if disk_data.removable or usb_data:
                        self.devices.append(device)
                        logger.debug(
                            f"Found device: {self._format_device_debug(device)}"
                        )

            except Exception as e:
                logger.error(f"Error scanning devices: {e}")

    def _get_usb_device_info(self) -> list[USBDeviceInfo]:
        """Get USB device information from system_profiler."""
        try:
            import json

            result = subprocess.run(
                ["system_profiler", "SPUSBDataType", "-json"],
                capture_output=True,
                text=True,
                check=True,
            )

            data = json.loads(result.stdout)
            usb_devices = []

            def extract_devices(items: list[Any], parent_name: str = "") -> None:
                """Recursively extract USB device information."""
                for item in items:
                    vendor_id = item.get("vendor_id", "")
                    # Clean up vendor ID format (remove "0x" prefix if present)
                    if vendor_id.startswith("0x"):
                        vendor_id = vendor_id[2:]

                    device_info = USBDeviceInfo(
                        name=item.get("_name", "Unknown"),
                        vendor=item.get("manufacturer", ""),
                        vendor_id=vendor_id,
                        product_id=item.get("product_id", ""),
                        serial=item.get("serial_num", ""),
                    )

                    usb_devices.append(device_info)

                    # Recursively process nested devices
                    if "_items" in item:
                        extract_devices(item["_items"], item.get("_name", ""))

            # Extract devices from the SPUSBDataType
            for entry in data.get("SPUSBDataType", []):
                if "_items" in entry:
                    extract_devices(entry["_items"])

            return usb_devices

        except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error getting USB device info: {e}")
            return []

    def _get_disk_info(self) -> dict[str, DiskInfo]:
        """Get disk information from diskutil."""
        try:
            import plistlib

            # Get all disk info
            result = subprocess.run(
                ["diskutil", "list", "-plist"], capture_output=True, check=True
            )

            plist_data = plistlib.loads(result.stdout)
            disk_info = {}

            # Get detailed info for each disk
            for disk_dict in plist_data.get("AllDisksAndPartitions", []):
                disk_id = disk_dict.get("DeviceIdentifier", "")
                if not disk_id:
                    continue

                # Get detailed info for this disk
                detail_result = subprocess.run(
                    ["diskutil", "info", "-plist", disk_id],
                    capture_output=True,
                    check=True,
                )

                detail_data = plistlib.loads(detail_result.stdout)

                partitions_list: list[str] = []
                disk_info[disk_id] = DiskInfo(
                    size=detail_data.get("Size", 0),
                    media_name=detail_data.get("MediaName", ""),
                    volume_name=detail_data.get("VolumeName", ""),
                    removable=detail_data.get("Removable", False),
                    protocol=detail_data.get("Protocol", ""),
                    partitions=partitions_list,
                )

                # Add partition info
                for partition in disk_dict.get("Partitions", []):
                    part_id = partition.get("DeviceIdentifier", "")
                    if part_id:
                        partitions_list.append(part_id)

                        # Also get volume name for partitions
                        part_detail_result = subprocess.run(
                            ["diskutil", "info", "-plist", part_id],
                            capture_output=True,
                            check=True,
                        )
                        part_detail_data = plistlib.loads(part_detail_result.stdout)
                        part_volume_name = part_detail_data.get("VolumeName", "")
                        if part_volume_name and not disk_info[disk_id].volume_name:
                            # Use partition volume name if disk doesn't have one
                            disk_info[disk_id].volume_name = part_volume_name

            return disk_info

        except (subprocess.CalledProcessError, Exception) as e:
            logger.error(f"Error getting disk info: {e}")
            return {}

    def is_usb_device(self, device_info: BlockDeviceDict) -> bool:
        """Check if a device is USB-connected storage."""
        # On macOS, we'd need to check the device protocol
        # For now, assume removable devices are USB
        return bool(device_info.get("removable", False))

    def _monitor_loop(self) -> None:
        """Main monitoring loop for macOS."""
        # Simple polling approach for macOS
        while self._monitoring:
            old_devices = {d.path for d in self.devices}
            self.scan_existing_devices()
            new_devices = {d.path for d in self.devices}

            # Check for added devices
            for path in new_devices - old_devices:
                device = next((d for d in self.devices if d.path == path), None)
                if device:
                    logger.debug(
                        f"USB device added: {self._format_device_debug(device)}"
                    )
                    self._notify_callbacks("add", device)

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
                logger.debug(
                    f"USB device removed: {self._format_device_debug(removed_device)}"
                )
                self._notify_callbacks("remove", removed_device)

            time.sleep(1.0)  # Poll every second


class StubUSBDeviceMonitor(USBDeviceMonitorBase):
    """Stub implementation for testing or unsupported platforms."""

    def scan_existing_devices(self) -> None:
        """No-op scan for stub implementation."""
        logger.warning("Using stub USB device monitor - no devices will be detected")

    def is_usb_device(self, device_info: BlockDeviceDict) -> bool:
        """Always returns False for stub."""
        return False

    def _monitor_loop(self) -> None:
        """No-op monitoring loop."""
        while self._monitoring:
            time.sleep(1.0)


def _create_mount_cache() -> MountCacheProtocol:
    """Create appropriate mount cache for the current platform."""
    if platform.system() == "Linux":
        from glovebox.firmware.flash.device_detector import MountPointCache

        return MountPointCache()
    else:

        class MountPointCacheStub:
            """Stub MountPointCache for non-Linux platforms."""

            def get_mountpoints(self) -> BlockDevicePathMap:
                return {}

        return MountPointCacheStub()


def create_usb_monitor() -> USBDeviceMonitorBase:
    """Factory function to create the appropriate USB monitor for the platform."""
    system = platform.system()

    if system == "Linux":
        logger.info("Creating Linux USB device monitor")
        return LinuxUSBDeviceMonitor()
    elif system == "Darwin":
        logger.info("Creating macOS USB device monitor")
        return MacOSUSBDeviceMonitor()
    else:
        logger.warning(f"Unsupported platform: {system}, using stub monitor")
        return StubUSBDeviceMonitor()
