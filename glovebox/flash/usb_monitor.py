"""Platform-specific USB device monitoring implementations."""

import abc
import logging
import platform
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Optional

from glovebox.flash.lsdev import BlockDevice


logger = logging.getLogger(__name__)


class USBDeviceMonitorBase(abc.ABC):
    """Abstract base class for USB device monitoring."""

    def __init__(self) -> None:
        """Initialize the USB device monitor."""
        self.known_devices: set[str] = set()
        self.devices: list[BlockDevice] = []
        self._callbacks: set[Callable[[str, BlockDevice], None]] = set()
        self._lock = threading.RLock()
        self._monitoring = False
        self._monitor_thread: threading.Thread | None = None

    @abc.abstractmethod
    def scan_existing_devices(self) -> None:
        """Scan existing USB block devices and populate the device list."""
        pass

    @abc.abstractmethod
    def is_usb_device(self, device_info: dict) -> bool:
        """Check if a device is USB-connected storage."""
        pass

    def get_devices(self) -> list[BlockDevice]:
        """Get the current list of USB block devices."""
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

    @abc.abstractmethod
    def _monitor_loop(self) -> None:
        """Main monitoring loop (platform-specific)."""
        pass

    def register_callback(self, callback: Callable[[str, BlockDevice], None]) -> None:
        """Register a callback for device events."""
        self._callbacks.add(callback)

    def unregister_callback(self, callback: Callable[[str, BlockDevice], None]) -> None:
        """Unregister a callback for device events."""
        self._callbacks.discard(callback)

    def wait_for_device(
        self, timeout: int = 60, poll_interval: float = 0.5
    ) -> BlockDevice | None:
        """Wait for a new USB device to be connected."""
        start_time = time.time()
        initial_devices = {d.path for d in self.get_devices()}

        while time.time() - start_time < timeout:
            current_devices = self.get_devices()
            for device in current_devices:
                if device.path not in initial_devices:
                    return device
            time.sleep(poll_interval)

        return None

    def _notify_callbacks(self, action: str, device: BlockDevice) -> None:
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
        import pyudev

        self.pyudev = pyudev

        self.context = pyudev.Context()
        self._observer: pyudev.MonitorObserver | None = None
        self._mount_cache = MountPointCache()
        self.scan_existing_devices()

    def scan_existing_devices(self) -> None:
        """Scan existing USB block devices and populate the device list."""
        with self._lock:
            self.devices = []
            mount_points = self._mount_cache.get_mountpoints()

            for device in self.context.list_devices(subsystem="block"):
                if self.is_usb_device(device):
                    self.known_devices.add(device.device_node)
                    block_device = BlockDevice.from_pyudev_device(device)
                    self._update_mountpoints(block_device, mount_points)
                    self.devices.append(block_device)
                    logger.debug(f"Found existing device: {device.device_node}")

    def is_usb_device(self, device) -> bool:
        """Check if a device is USB-connected storage."""
        if hasattr(device, "subsystem") and device.subsystem != "block":
            return False

        if hasattr(device, "ancestors"):
            return any(parent.subsystem == "usb" for parent in device.ancestors)
        return False

    def _update_mountpoints(
        self, device: BlockDevice, mount_points: dict[str, str]
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
        monitor.filter_by(subsystem="block")

        def device_event(action, device):
            if action in ("add", "remove") and self.is_usb_device(device):
                if action == "add":
                    block_device = BlockDevice.from_pyudev_device(device)
                    with self._lock:
                        self.devices.append(block_device)
                    self._notify_callbacks("add", block_device)
                elif action == "remove":
                    with self._lock:
                        self.devices = [
                            d for d in self.devices if d.path != device.device_node
                        ]

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
                    volume_name = disk_data.get("VolumeName", "")
                    media_name = disk_data.get("MediaName", "")

                    # Look for USB device by matching volume name, media name, disk identifier, or vendor
                    for usb_device in usb_info:
                        usb_name = usb_device.get("name", "").lower().strip()
                        usb_vendor = usb_device.get("vendor", "").lower().strip()
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

                    # Create BlockDevice with real information
                    device = BlockDevice(
                        name=disk_name,
                        device_node=f"/dev/{disk_name}",
                        model=usb_data.get(
                            "name", disk_data.get("MediaName", "Unknown")
                        )
                        if usb_data
                        else disk_data.get("MediaName", "Unknown"),
                        vendor=usb_data.get("vendor", "Unknown")
                        if usb_data
                        else "Unknown",
                        serial=usb_data.get("serial", "") if usb_data else "",
                        size=disk_data.get("Size", 0),
                        removable=disk_data.get("Removable", False),
                        type="usb" if usb_data else "disk",
                        partitions=disk_data.get("Partitions", []),
                        mountpoints={volume_name: f"/Volumes/{volume_name}"}
                        if volume_name in mounted_volumes
                        else {},
                    )

                    # Only add if it's a removable device or has USB info
                    if device.removable or usb_data:
                        self.devices.append(device)
                        logger.debug(
                            f"Found device: {disk_name} - {device.model} (Vendor: {device.vendor}, Serial: {device.serial})"
                        )

            except Exception as e:
                logger.error(f"Error scanning devices: {e}")

    def _get_usb_device_info(self) -> list[dict]:
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

            def extract_devices(items, parent_name=""):
                """Recursively extract USB device information."""
                for item in items:
                    device_info = {
                        "name": item.get("_name", "Unknown"),
                        "vendor": item.get("manufacturer", ""),
                        "vendor_id": item.get("vendor_id", ""),
                        "product_id": item.get("product_id", ""),
                        "serial": item.get("serial_num", ""),
                    }

                    # Clean up vendor ID format (remove "0x" prefix if present)
                    if device_info["vendor_id"].startswith("0x"):
                        device_info["vendor_id"] = device_info["vendor_id"][2:]

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

    def _get_disk_info(self) -> dict:
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

                disk_info[disk_id] = {
                    "Size": detail_data.get("Size", 0),
                    "MediaName": detail_data.get("MediaName", ""),
                    "VolumeName": detail_data.get("VolumeName", ""),
                    "Removable": detail_data.get("Removable", False),
                    "Protocol": detail_data.get("Protocol", ""),
                    "Partitions": [],
                }

                # Add partition info
                for partition in disk_dict.get("Partitions", []):
                    part_id = partition.get("DeviceIdentifier", "")
                    if part_id:
                        disk_info[disk_id]["Partitions"].append(part_id)

                        # Also get volume name for partitions
                        part_detail_result = subprocess.run(
                            ["diskutil", "info", "-plist", part_id],
                            capture_output=True,
                            check=True,
                        )
                        part_detail_data = plistlib.loads(part_detail_result.stdout)
                        part_volume_name = part_detail_data.get("VolumeName", "")
                        if part_volume_name and not disk_info[disk_id]["VolumeName"]:
                            # Use partition volume name if disk doesn't have one
                            disk_info[disk_id]["VolumeName"] = part_volume_name

            return disk_info

        except (subprocess.CalledProcessError, Exception) as e:
            logger.error(f"Error getting disk info: {e}")
            return {}

    def is_usb_device(self, device_info: dict) -> bool:
        """Check if a device is USB-connected storage."""
        # On macOS, we'd need to check the device protocol
        # For now, assume removable devices are USB
        return device_info.get("removable", False)

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
                    self._notify_callbacks("add", device)

            # Check for removed devices
            for path in old_devices - new_devices:
                self._notify_callbacks(
                    "remove",
                    BlockDevice(
                        name=Path(path).name,
                        device_node=path,
                        model="",
                        vendor="",
                        serial="",
                    ),
                )

            time.sleep(1.0)  # Poll every second


class StubUSBDeviceMonitor(USBDeviceMonitorBase):
    """Stub implementation for testing or unsupported platforms."""

    def scan_existing_devices(self) -> None:
        """No-op scan for stub implementation."""
        logger.warning("Using stub USB device monitor - no devices will be detected")

    def is_usb_device(self, device_info: dict) -> bool:
        """Always returns False for stub."""
        return False

    def _monitor_loop(self) -> None:
        """No-op monitoring loop."""
        while self._monitoring:
            time.sleep(1.0)


# Import MountPointCache only if we're on Linux
if platform.system() == "Linux":
    from glovebox.flash.lsdev import MountPointCache
else:

    class MountPointCache:
        """Stub MountPointCache for non-Linux platforms."""

        def get_mountpoints(self) -> dict[str, str]:
            return {}


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
