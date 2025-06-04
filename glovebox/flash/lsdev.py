#!/usr/bin/env python3
import logging
import os
import threading
import time
from collections.abc import Callable  # UP035: Re-added Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path  # PTH123: Added Path import
from typing import Any, Optional

import pyudev


# Configure logger
logger = logging.getLogger(__name__)


class BlockDeviceError(Exception):
    """Base exception for block device operations."""

    pass


# DEVNAME: /dev/sda
# DEVPATH: /devices/pci0000:00/0000:00:14.0/usb1/1-6/1-6.4/1-6.4:1.2/host8/target8:0:0/8:0:0:0/block/sda
# DEVTYPE: disk
# DISKSEQ: 42
# ID_BUS: usb
# ID_FS_BLOCKSIZE: 512
# ID_FS_LABEL: GLV80RHBOOT
# ID_FS_LABEL_ENC: GLV80RHBOOT
# ID_FS_SIZE: 33690112
# ID_FS_TYPE: vfat
# ID_FS_USAGE: filesystem
# ID_FS_UUID: 0042-0042
# ID_FS_UUID_ENC: 0042-0042
# ID_FS_VERSION: FAT16
# ID_INSTANCE: 0:0
# ID_MODEL: nRF_UF2
# ID_MODEL_ENC: nRF\x20UF2\x20\x20\x20\x20\x20\x20\x20\x20\x20
# ID_MODEL_ID: 0029
# ID_PATH: pci-0000:00:14.0-usb-0:6.4:1.2-scsi-0:0:0:0
# ID_PATH_TAG: pci-0000_00_14_0-usb-0_6_4_1_2-scsi-0_0_0_0
# ID_PATH_WITH_USB_REVISION: pci-0000:00:14.0-usbv2-0:6.4:1.2-scsi-0:0:0:0
# ID_REVISION: 1.0
# ID_SERIAL: Adafruit_nRF_UF2_GLV80-735A88B1887FDE8B-0:0
# ID_SERIAL_SHORT: GLV80-735A88B1887FDE8B
# ID_TYPE: disk
# ID_USB_DRIVER: usb-storage
# ID_USB_INSTANCE: 0:0
# ID_USB_INTERFACES: :020200:0a0000:080650:
# ID_USB_INTERFACE_NUM: 02
# ID_USB_MODEL: nRF_UF2
# ID_USB_MODEL_ENC: nRF\x20UF2\x20\x20\x20\x20\x20\x20\x20\x20\x20
# ID_USB_MODEL_ID: 0029
# ID_USB_REVISION: 1.0
# ID_USB_SERIAL: Adafruit_nRF_UF2_GLV80-735A88B1887FDE8B-0:0
# ID_USB_SERIAL_SHORT: GLV80-735A88B1887FDE8B
# ID_USB_TYPE: disk
# ID_USB_VENDOR: Adafruit
# ID_USB_VENDOR_ENC: Adafruit
# ID_USB_VENDOR_ID: 239a
# ID_VENDOR: Adafruit
# ID_VENDOR_ENC: Adafruit
# ID_VENDOR_ID: 239a


@dataclass
class BlockDevice:
    """Represents a block device with its properties."""

    name: str
    device_node: str = ""  # Store the original pyudev device node for easier access
    size: int = 0
    type: str = "unknown"
    removable: bool = False
    model: str = ""
    vendor: str = ""
    serial: str = ""
    uuid: str = ""
    label: str = ""
    partitions: list[str] = field(default_factory=list)
    mountpoints: dict[str, str] = field(default_factory=dict)
    symlinks: set[str] = field(default_factory=set)  # UP035: set is already modern
    raw: dict[str, str] = field(default_factory=dict)

    @property
    def path(self) -> str:
        """Return the device path."""
        return self.device_node

    @property
    def description(self) -> str:
        """Return a human-readable description of the device."""
        if self.label:
            return f"{self.label} ({self.name})"
        elif self.vendor and self.model:
            return f"{self.vendor} {self.model} ({self.name})"
        elif self.vendor:
            return f"{self.vendor} {self.name}"
        elif self.model:
            return f"{self.model} {self.name}"
        else:
            return self.name

    @classmethod
    def from_pyudev_device(cls, device: pyudev.Device) -> "BlockDevice":
        """Create a BlockDevice from a pyudev Device."""
        name = device.sys_name
        device_node = device.device_node

        raw_dict = dict(device.properties.items())

        # Extract size using device attributes
        size = 0
        if device.attributes.get("size"):
            try:
                size = int(device.attributes.get("size", 0)) * 512
            except (ValueError, TypeError):
                logger.debug(f"Could not convert size attribute for {name}")

        # Get removable status from attributes
        removable = False
        if device.attributes.get("removable"):
            try:
                removable = bool(int(device.attributes.get("removable", 0)))
            except (ValueError, TypeError):
                logger.debug(f"Could not convert removable attribute for {name}")

        # Extract model and vendor from properties
        model = device.properties.get("ID_MODEL", "")
        vendor = device.properties.get("ID_VENDOR", "")

        # Determine device type
        device_type = "unknown"
        if device.properties.get("ID_BUS") == "usb":
            device_type = "usb"
        elif name.startswith("sd"):
            device_type = "disk"
        elif name.startswith("nvme"):
            device_type = "nvme"
        else:
            device_type = device.properties.get("DEVTYPE", "unknown")

        # Collect symlinks
        symlinks = set()
        for link in device.device_links:
            symlink = Path(link).name
            symlinks.add(symlink)

        # Get partitions
        partitions = []
        try:
            for child in device.children:
                if child.subsystem == "block" and child.device_node != device_node:
                    partitions.append(child.sys_name)
        except (AttributeError, KeyError) as e:
            logger.debug(f"Error getting partitions for {name}: {e}")

        # Create the block device object
        block_device = cls(
            name=name,
            device_node=device_node,
            size=size,
            type=device_type,
            removable=removable,
            model=model,
            vendor=vendor,
            partitions=partitions,
            symlinks=symlinks,
            label=device.properties.get("ID_FS_LABEL", ""),
            uuid=device.properties.get("ID_FS_UUID", ""),
            # serial_short=device.properties.get("ID_SERIAL_SHORT", ""),
            serial=device.properties.get("ID_SERIAL_SHORT", ""),
        )

        # Get mount points (done externally to avoid reading /proc/mounts for each device)
        return block_device


class MountPointCache:
    """Cache for system mount points to avoid repeated file access."""

    def __init__(self) -> None:
        self._mountpoints: dict[str, str] = {}
        self._last_updated: float = 0
        self._cache_ttl: int = 5  # Seconds before refreshing cache
        self._lock = threading.RLock()

    def get_mountpoints(self) -> dict[str, str]:
        """Get mapping of device names to mount points."""
        with self._lock:
            now = time.time()
            if now - self._last_updated > self._cache_ttl:
                self._update_cache()
            return self._mountpoints.copy()

    def _update_cache(self) -> None:
        """Update the mount point cache from /proc/mounts."""
        mountpoints = {}
        try:
            with Path("/proc/mounts").open(
                encoding="utf-8"
            ) as f:  # PTH123 & added encoding
                for line in f:
                    fields = line.split()
                    if len(fields) < 2 or not fields[0].startswith("/dev/"):
                        continue

                    device = fields[0][5:]  # Remove /dev/ prefix
                    mount_point = fields[1]
                    mountpoints[device] = mount_point

            self._mountpoints = mountpoints
            self._last_updated = time.time()
        except OSError as e:
            logger.warning(f"Failed to read mount points: {e}")


class USBDeviceMonitor:
    """Monitor for USB block devices with event handling."""

    def __init__(self) -> None:
        """Initialize the USB device monitor."""
        self.context = pyudev.Context()
        self.known_devices: set[str] = set()
        self.devices: list[BlockDevice] = []
        self._observer: pyudev.MonitorObserver | None = None
        self._mount_cache = MountPointCache()
        self._callbacks: set[Callable[[str, BlockDevice], None]] = set()
        self._lock = threading.RLock()
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

    def _update_mountpoints(
        self, device: BlockDevice, mount_points: dict[str, str]
    ) -> None:
        """Update device mount points from the cache."""
        for part in device.partitions:
            if part in mount_points:
                device.mountpoints[part] = mount_points[part]

        # Check if the device itself is mounted
        if device.name in mount_points:
            device.mountpoints[device.name] = mount_points[device.name]

    def is_usb_device(self, device: pyudev.Device) -> bool:
        """Check if a device is USB-connected storage."""
        if device.subsystem != "block":
            return False

        return any(parent.subsystem == "usb" for parent in device.ancestors)

    def start_monitoring(self) -> None:
        """Start monitoring for USB device events."""
        if self._observer is not None:
            logger.warning("Monitor already started")
            return

        monitor = pyudev.Monitor.from_netlink(self.context)
        monitor.filter_by(subsystem="block")
        self._observer = pyudev.MonitorObserver(monitor, self._device_event)
        self._observer.start()
        logger.info("USB device monitoring started")

    def stop_monitoring(self) -> None:
        """Stop the USB device monitor."""
        if self._observer is not None:
            self._observer.stop()
            self._observer = None
            logger.info("USB device monitoring stopped")

    @contextmanager
    def monitor(self) -> Any:
        """Context manager for temporary monitoring."""
        try:
            self.start_monitoring()
            yield self
        finally:
            self.stop_monitoring()

    def register_callback(
        self, callback: Callable[[str, BlockDevice], None]
    ) -> None:  # UP035
        """Register a callback function for device events.

        Args:
            callback: Function taking action ("add"/"remove") and device as arguments
        """
        self._callbacks.add(callback)

    def unregister_callback(
        self, callback: Callable[[str, BlockDevice], None]
    ) -> None:  # UP035
        """Unregister a previously registered callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _device_event(self, action: str, device: pyudev.Device) -> None:
        """Handle device events."""
        if device.subsystem != "block":
            return

        device_node = device.device_node

        with self._lock:
            if action == "add" and self.is_usb_device(device):
                if device_node not in self.known_devices:
                    self.known_devices.add(device_node)
                    block_device = BlockDevice.from_pyudev_device(device)

                    # Update mount points
                    mount_points = self._mount_cache.get_mountpoints()
                    self._update_mountpoints(block_device, mount_points)

                    self.devices.append(block_device)
                    logger.info(f"New device detected: {device_node}")

                    # Notify callbacks
                    for callback in self._callbacks:
                        try:
                            callback("add", block_device)
                        except Exception as e:
                            logger.error(f"Error in device callback: {e}")

            elif action == "remove" and device_node in self.known_devices:
                self.known_devices.remove(device_node)

                # Find and remove the device
                for i, dev in enumerate(self.devices):
                    if dev.device_node == device_node:
                        removed_device = self.devices.pop(i)
                        logger.info(f"Device removed: {device_node}")

                        # Notify callbacks
                        for callback in self._callbacks:
                            try:
                                callback("remove", removed_device)
                            except Exception as e:
                                logger.error(f"Error in device callback: {e}")
                        break

    def get_devices(self) -> list[BlockDevice]:
        """Get the current list of USB block devices."""
        with self._lock:
            # Refresh mount points for all devices
            mount_points = self._mount_cache.get_mountpoints()
            for device in self.devices:
                self._update_mountpoints(device, mount_points)
            return self.devices.copy()

    def wait_for_device(
        self, timeout: int = 60, poll_interval: float = 0.5
    ) -> BlockDevice | None:
        """Wait for any new USB storage device to be connected.

        Args:
            timeout: Maximum time to wait in seconds
            poll_interval: Time between device checks in seconds

        Returns:
            BlockDevice or None if timeout occurs
        """
        initial_devices = {d.device_node for d in self.get_devices()}
        new_device: BlockDevice | None = None
        event = threading.Event()

        def device_callback(action: str, device: BlockDevice) -> None:
            nonlocal new_device
            if action == "add" and device.device_node not in initial_devices:
                new_device = device
                event.set()

        # Register callback
        self.register_callback(device_callback)

        try:
            with self.monitor():
                # Wait for event or timeout
                if not event.wait(timeout):
                    logger.debug("Timeout waiting for new device")
                    return None
                return new_device
        finally:
            # Unregister callback
            self.unregister_callback(device_callback)


class Lsdev:
    """Class for USB block device operations."""

    _instance: Optional["Lsdev"] = None
    _lock = threading.RLock()

    def __new__(cls) -> "Lsdev":
        """Singleton pattern to ensure only one monitor exists."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        """Initialize the Lsdev class if not already initialized."""
        with self._lock:
            if getattr(self, "_initialized", False):
                return
            self._monitor = USBDeviceMonitor()
            self._initialized = True

    def get_devices(self) -> list[BlockDevice]:
        """Get USB block devices."""
        return self._monitor.get_devices()

    def get_device_by_name(self, name: str) -> BlockDevice | None:
        """Get a block device by name."""
        devices = self.get_devices()
        for device in devices:
            if device.name == name:
                return device
        return None

    def get_devices_by_query(self, **kwargs: Any) -> list[BlockDevice]:
        """Get devices matching the specified criteria."""
        devices = self.get_devices()
        result = []

        for device in devices:
            match = True
            for key, value in kwargs.items():
                if not hasattr(device, key) or getattr(device, key) != value:
                    match = False
                    break
            if match:
                result.append(device)

        return result

    def start_monitoring(self) -> None:
        """Start USB device monitoring."""
        self._monitor.start_monitoring()

    def stop_monitoring(self) -> None:
        """Stop USB device monitoring."""
        self._monitor.stop_monitoring()

    def register_callback(self, callback: Callable[[str, BlockDevice], None]) -> None:
        """Register a callback for device events."""
        self._monitor.register_callback(callback)

    def unregister_callback(self, callback: Callable[[str, BlockDevice], None]) -> None:
        """Unregister a callback."""
        self._monitor.unregister_callback(callback)

    def wait_for_device(
        self, timeout: int = 60, poll_interval: float = 0.5
    ) -> BlockDevice | None:
        """Wait for a new USB device to appear."""
        return self._monitor.wait_for_device(timeout, poll_interval)


def get_block_devices() -> list[BlockDevice]:
    """Get USB block devices.

    This is a compatibility function for use with existing code.
    """
    lsdev = Lsdev()
    return lsdev.get_devices()


def format_size(bytes_count: int) -> str:
    """Format byte count to human-readable string."""
    if bytes_count < 0:
        return "0 B"

    count = float(bytes_count)
    for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if count < 1024.0 or unit == "PB":
            return f"{count:.2f} {unit}"
        count /= 1024.0
    return f"{count:.2f} PB"


def print_device_info(devices: list[BlockDevice]) -> None:
    """Print information about block devices."""
    # Print header
    logger.info(
        f"{'NAME':<10} {'SIZE':<15} {'TYPE':<10} {'REMOVABLE':<10} {'MODEL':<20} {'VENDOR':<20} {'SERIAL':<20}"
    )
    logger.info("-" * 105)

    # Print devices
    for device in devices:
        size_str = format_size(device.size)
        removable_str = "yes" if device.removable else "no"

        logger.info(
            f"{device.name:<10} {size_str:<15} {device.type:<10} {removable_str:<10} {device.model:<20} {device.vendor:<20} {device.serial:<20}"
        )

        # Print partitions
        for part in device.partitions:
            mount_point = device.mountpoints.get(part, "-")
            logger.info(f"└─{part:<8} {mount_point}")

        # Print symlinks if any
        if device.symlinks:
            logger.info("  Symlinks:")
            for symlink in sorted(device.symlinks):
                logger.info(f"  └─{symlink}")


def main() -> None:
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info("USB Block Device Information")
    logger.info("=" * 105)

    try:
        lsdev = Lsdev()
        devices = lsdev.get_devices()
        print_device_info(devices)

        # Start monitoring mode
        def device_callback(action: str, device: BlockDevice) -> None:
            if action == "add":
                logger.info(f"\n[NEW DEVICE DETECTED] {device.device_node}")
                logger.info(f"Device: {device.name}")
                logger.info(f"Model: {device.model}")
                logger.info(f"Vendor: {device.vendor}")
                logger.info(f"Serial: {device.serial}")
                logger.info(f"Size: {format_size(device.size)}")
                logger.info(f"Type: {device}")
                logger.info("-" * 50)
            elif action == "remove":
                logger.info(f"\n[DEVICE REMOVED] {device.device_node}")

        lsdev.register_callback(device_callback)

        logger.info(
            "Starting USB device monitor. Plug in a device to see information..."
        )
        logger.info("Press Ctrl+C to exit.")

        # Start monitoring
        lsdev.start_monitoring()

        try:
            # Keep the script running
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        finally:
            lsdev.stop_monitoring()
    except Exception as e:
        logger.error(f"Error: {e}")
        import sys

        sys.exit(1)


if __name__ == "__main__":
    main()
