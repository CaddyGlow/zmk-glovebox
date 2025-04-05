#!/usr/bin/env python3

import os
import platform
import sys
import logging
from typing import Dict, List, Optional, Union
from dataclasses import dataclass, field

# Configure logger
logger = logging.getLogger(__name__)


class BlockDeviceError(Exception):
    """Base exception for block device operations."""

    pass


@dataclass
class BlockDevice:
    """Represents a block device with its properties."""

    name: str
    size: int = 0
    type: str = "unknown"
    removable: bool = False
    model: str = ""
    vendor: str = ""
    partitions: list[str] = field(default_factory=list)
    mount_points: dict[str, str] = field(default_factory=dict)


def format_size(bytes_count: int) -> str:
    """Format byte count to human-readable string.

    Args:
        bytes_count: Size in bytes

    Returns:
        Human-readable size string
    """
    count = float(bytes_count)
    for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if count < 1024.0 or unit == "PB":
            return f"{count:.2f} {unit}"
        count /= 1024.0
    raise Exception("Size too large to format")


# Linux implementation
def get_linux_mount_points() -> Dict[str, str]:
    """Get mount points from /proc/mounts.

    Returns:
        Dictionary mapping device names to mount points
    """
    mount_points = {}

    try:
        with open("/proc/mounts", "r") as f:
            for line in f:
                fields = line.split()
                if len(fields) < 2:
                    continue

                device = fields[0]
                mount_point = fields[1]

                # Extract device name from path
                if device.startswith("/dev/"):
                    device_name = device[5:]  # Remove /dev/ prefix
                    mount_points[device_name] = mount_point
    except IOError as e:
        logger.warning(f"Could not read mount points: {e}")

    return mount_points


def get_linux_block_devices() -> List[BlockDevice]:
    """Get block devices on Linux systems.

    Returns:
        List of BlockDevice objects

    Raises:
        BlockDeviceError: If /sys/block cannot be accessed
    """
    devices = []

    try:
        mount_points = get_linux_mount_points()

        if not os.path.isdir("/sys/block"):
            raise BlockDeviceError("Cannot access /sys/block directory")

        for device_path in os.listdir("/sys/block"):
            device_sys_path = os.path.join("/sys/block", device_path)

            # Skip if not a directory
            if not os.path.isdir(device_sys_path):
                continue

            # Create device
            device = BlockDevice(device_path)
            device.mount_points = mount_points

            # Get device size
            try:
                with open(os.path.join(device_sys_path, "size"), "r") as f:
                    size_sectors = int(f.read().strip())
                    # Size is in 512-byte sectors
                    device.size = size_sectors * 512
            except (IOError, ValueError) as e:
                logger.debug(f"Could not read size for {device_path}: {e}")

            # Get device type
            if device_path.startswith("sd"):
                device.type = "disk"
            elif device_path.startswith("nvme"):
                device.type = "disk"
            elif device_path.startswith("loop"):
                device.type = "loop"
            elif device_path.startswith("ram"):
                device.type = "ram"
            else:
                device.type = "unknown"

            # Check if removable
            try:
                with open(os.path.join(device_sys_path, "removable"), "r") as f:
                    removable = f.read().strip()
                    device.removable = removable == "1"
            except IOError as e:
                logger.debug(f"Could not read removable flag for {device_path}: {e}")

            # Get model information
            try:
                with open(os.path.join(device_sys_path, "device/model"), "r") as f:
                    device.model = f.read().strip()
            except IOError as e:
                logger.debug(f"Could not read model for {device_path}: {e}")

            # Get vendor information
            try:
                with open(os.path.join(device_sys_path, "device/vendor"), "r") as f:
                    device.vendor = f.read().strip()
            except IOError as e:
                logger.debug(f"Could not read vendor for {device_path}: {e}")

            # Get partitions
            for part_path in os.listdir(device_sys_path):
                if part_path.startswith(device_path) and part_path != device_path:
                    device.partitions.append(part_path)

            devices.append(device)

    except Exception as e:
        raise BlockDeviceError(f"Error getting Linux block devices: {e}")

    return devices


# macOS implementation
def get_macos_mount_points() -> Dict[str, str]:
    """Get mount points on macOS.

    Returns:
        Dictionary mapping device names to mount points
    """
    mount_points = {}

    try:
        import subprocess

        result = subprocess.run(["mount"], capture_output=True, text=True)

        for line in result.stdout.splitlines():
            fields = line.split()
            if len(fields) >= 3 and fields[0].startswith("/dev/"):
                device = fields[0][5:]  # Remove /dev/ prefix
                mount_point = fields[2]
                mount_points[device] = mount_point
    except Exception as e:
        logger.warning(f"Could not read mount points: {e}")

    return mount_points


def get_macos_block_devices() -> List[BlockDevice]:
    """Get block devices on macOS systems.

    Returns:
        List of BlockDevice objects

    Raises:
        BlockDeviceError: If required libraries are missing or if IOKit operations fail
    """
    try:
        import Foundation
        import IOKit.IOKitLib as IOKit
        import objc
    except ImportError:
        raise BlockDeviceError(
            "pyobjc library not found. Install with: pip install pyobjc"
        )

    devices = []

    try:
        mount_points = get_macos_mount_points()

        # Get an iterator for block storage devices
        matching_dict = IOKit.IOServiceMatching("IOBlockStorageDevice")
        iterator = IOKit.io_iterator_t()
        kr = IOKit.IOServiceGetMatchingServices(
            IOKit.kIOMasterPortDefault, matching_dict, byref(iterator)
        )

        if kr != IOKit.KERN_SUCCESS:
            raise BlockDeviceError(f"IOServiceGetMatchingServices returned {kr}")

        # Iterate through all block storage devices
        service = IOKit.IOIteratorNext(iterator)
        while service:
            try:
                # Get device properties
                props = IOKit.IORegistryEntryCreateCFProperties(
                    service, None, Foundation.kCFAllocatorDefault, IOKit.kNilOptions
                )
                if props:
                    props = props.value()

                    # Extract relevant information
                    device_characteristics = props.get("Device Characteristics", {})

                    # Get model and vendor names
                    model = props.get("Product Name", "")
                    vendor = props.get("Vendor Name", "")

                    # Get size and removable state from device characteristics
                    size = device_characteristics.get("Size", 0)
                    removable = device_characteristics.get("Removable Media", False)

                    # Get parent to find BSD name
                    parent = IOKit.io_object_t()
                    kr = IOKit.IORegistryEntryGetParentEntry(
                        service, "IOService", byref(parent)
                    )

                    if kr == IOKit.KERN_SUCCESS:
                        try:
                            parent_props = IOKit.IORegistryEntryCreateCFProperties(
                                parent,
                                None,
                                Foundation.kCFAllocatorDefault,
                                IOKit.kNilOptions,
                            )
                            if parent_props:
                                parent_props = parent_props.value()
                                bsd_name = parent_props.get("BSD Name", "")

                                if bsd_name:
                                    # Create device
                                    device = BlockDevice(bsd_name)
                                    device.size = size
                                    device.model = model
                                    device.vendor = vendor
                                    device.removable = removable
                                    device.mount_points = mount_points
                                    device.type = "disk"

                                    # Find partitions
                                    for mount_device in mount_points.keys():
                                        if (
                                            mount_device.startswith(bsd_name)
                                            and mount_device != bsd_name
                                        ):
                                            device.partitions.append(mount_device)

                                    devices.append(device)
                        finally:
                            IOKit.IOObjectRelease(parent)
            finally:
                IOKit.IOObjectRelease(service)
                service = IOKit.IOIteratorNext(iterator)

        IOKit.IOObjectRelease(iterator)

    except Exception as e:
        raise BlockDeviceError(f"Error getting macOS block devices: {e}")

    return devices


# Windows implementation
def get_windows_block_devices() -> List[BlockDevice]:
    """Get block devices on Windows systems.

    Returns:
        List of BlockDevice objects

    Raises:
        BlockDeviceError: If required libraries are missing or if WMI operations fail
    """
    try:
        import wmi
    except ImportError:
        raise BlockDeviceError("wmi library not found. Install with: pip install wmi")

    devices = []

    try:
        c = wmi.WMI()

        # Get all physical disks
        physical_disks = c.Win32_DiskDrive()

        # Get all logical disks (volumes) for mapping
        logical_disks = {d.DeviceID: d for d in c.Win32_LogicalDisk()}

        # Get partition to disk mappings
        partition_mappings = {}
        for partition in c.Win32_DiskPartition():
            partition_mappings[partition.DeviceID] = partition.DiskIndex

        # Get volume to partition mappings
        volume_mappings = {}
        for mapping in c.Win32_LogicalDiskToPartition():
            volume_mappings[mapping.Dependent.DeviceID] = mapping.Antecedent.DeviceID

        # Process each physical disk
        for disk in physical_disks:
            device = BlockDevice(f"disk{disk.Index}")
            device.size = int(disk.Size or 0)
            device.model = disk.Model or ""
            device.vendor = disk.Manufacturer or ""
            device.removable = bool(disk.MediaType and "Removable" in disk.MediaType)

            # Determine disk type
            if device.removable:
                device.type = "removable"
            elif disk.MediaType:
                if "Fixed" in disk.MediaType:
                    device.type = "disk"
                elif "SSD" in disk.MediaType:
                    device.type = "ssd"
                else:
                    device.type = disk.MediaType
            else:
                device.type = "disk"

            # Find partitions and mount points
            for volume_id, partition_id in volume_mappings.items():
                disk_index = partition_mappings.get(partition_id)

                if disk_index == disk.Index:
                    # This is a partition of the current disk
                    partition_name = f"part{partition_id.split('#')[1].split(',')[0]}"
                    device.partitions.append(partition_name)

                    # Get mount point if available
                    if volume_id in logical_disks:
                        logical_disk = logical_disks[volume_id]
                        if logical_disk.DeviceID:
                            device.mount_points[partition_name] = logical_disk.DeviceID

            devices.append(device)

    except Exception as e:
        raise BlockDeviceError(f"Error getting Windows block devices: {e}")

    return devices


def get_block_devices() -> List[BlockDevice]:
    """Get block devices for the current operating system.

    Returns:
        List of BlockDevice objects

    Raises:
        BlockDeviceError: If the operating system is unsupported or if device detection fails
    """
    system = platform.system().lower()

    if system == "linux":
        return get_linux_block_devices()
    elif system == "darwin":  # macOS
        return get_macos_block_devices()
    elif system == "windows":
        return get_windows_block_devices()
    else:
        raise BlockDeviceError(f"Unsupported operating system: {system}")


def print_device_info(devices: List[BlockDevice]) -> None:
    """Print information about block devices.

    Args:
        devices: List of BlockDevice objects
    """
    # Print header
    print(
        f"{'NAME':<10} {'SIZE':<15} {'TYPE':<10} {'REMOVABLE':<10} {'MODEL':<20} {'VENDOR':<20}"
    )
    print("-" * 85)

    # Print devices
    for device in devices:
        size_str = format_size(device.size)
        removable_str = "yes" if device.removable else "no"

        print(
            f"{device.name:<10} {size_str:<15} {device.type:<10} {removable_str:<10} {device.model:<20} {device.vendor:<20}"
        )

        # Print partitions
        for part in device.partitions:
            mount_point = device.mount_points.get(part, "-")
            print(f"└─{part:<8} {mount_point}")


def main() -> None:
    """Main function to run when the script is executed directly."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print(f"Block Device Information - {platform.system()}")
    print("=" * 85)

    try:
        devices = get_block_devices()
        print_device_info(devices)
    except BlockDeviceError as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
