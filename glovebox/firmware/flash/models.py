"""Models and type definitions for flash operations."""

import contextlib
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import Field, field_validator

from glovebox.core.structlog_logger import get_struct_logger
from glovebox.models.results import BaseResult


if TYPE_CHECKING:
    pass


logger = get_struct_logger(__name__)


class FirmwareSide(str, Enum):
    """Firmware side for split keyboards."""

    LEFT = "left"
    RIGHT = "right"
    UNIFIED = "unified"  # For non-split keyboards or combined firmware


class BlockDeviceError(Exception):
    """Base exception for block device operations."""

    pass


# Type definitions for BlockDevice operations
BlockDeviceDict = dict[str, Any]
BlockDevicePathMap = dict[str, str]
BlockDeviceSymlinks = set[str]


@dataclass
class USBDeviceInfo:
    """USB device information from system profiler."""

    name: str = ""
    vendor: str = ""
    vendor_id: str = ""
    product_id: str = ""
    serial: str = ""


@dataclass
class USBDevice:
    """Represents any USB device detected by the system."""

    # Core identification
    name: str  # Required field - device name
    device_node: str = ""  # Device node path (may be empty for non-storage)
    sys_path: str = ""  # Device path in /sys/

    # Device classification
    subsystem: str = ""  # Device subsystem (block, input, usb, etc.)
    device_type: str = "unknown"  # Device type (usb, disk, keyboard, etc.)

    # Device metadata
    model: str = ""  # Device model name
    vendor: str = ""  # Device vendor name
    serial: str = ""  # Device serial number
    vendor_id: str = ""  # USB vendor ID
    product_id: str = ""  # USB product ID

    # Physical characteristics (optional for non-storage)
    size: int = 0  # Device size in bytes (0 for non-storage)
    removable: bool = False  # Whether device is removable

    # Storage-specific fields (optional)
    uuid: str = ""  # Filesystem UUID
    label: str = ""  # Filesystem label
    partitions: list[str] = field(default_factory=list)  # Child partitions
    mountpoints: dict[str, str] = field(default_factory=dict)  # Mount information

    # System information
    symlinks: set[str] = field(default_factory=set)  # Device symlinks
    raw: dict[str, str] = field(default_factory=dict)  # Raw udev properties

    @classmethod
    def from_pyudev_device(cls, device: Any) -> "USBDevice":
        """Create a USBDevice from a pyudev Device."""
        name = device.sys_name or "unknown"
        device_node = getattr(device, "device_node", "") or ""
        sys_path = getattr(device, "device_path", "") or ""

        raw_dict = (
            dict(device.properties.items()) if hasattr(device, "properties") else {}
        )

        # Basic device information
        subsystem = getattr(device, "subsystem", "unknown")

        # Size calculation (only for block devices)
        size = 0
        if (
            subsystem == "block"
            and hasattr(device, "attributes")
            and device.attributes.get("size")
        ):
            try:
                size = int(device.attributes.get("size", 0)) * 512
            except (ValueError, TypeError):
                size = 0

        # Removable status
        removable = False
        if hasattr(device, "attributes") and device.attributes.get("removable"):
            try:
                removable = bool(int(device.attributes.get("removable", 0)))
            except (ValueError, TypeError):
                removable = False

        # Device metadata from properties
        model = raw_dict.get("ID_MODEL", "")
        vendor = raw_dict.get("ID_VENDOR", "")
        serial = raw_dict.get("ID_SERIAL_SHORT", "")
        vendor_id = raw_dict.get("ID_VENDOR_ID", "")
        product_id = raw_dict.get("ID_MODEL_ID", "")

        # Device type determination
        device_type = "unknown"
        if raw_dict.get("ID_BUS") == "usb":
            # Determine USB device type based on subsystem
            if subsystem == "block":
                device_type = "usb_storage"
            elif subsystem == "input":
                device_type = "usb_input"
            elif subsystem == "usb":
                device_type = "usb_device"
            else:
                device_type = f"usb_{subsystem}"
        elif name.startswith("sd"):
            device_type = "disk"
        elif name.startswith("nvme"):
            device_type = "nvme"
        else:
            device_type = raw_dict.get("DEVTYPE", subsystem)

        # Storage-specific properties (only for block devices)
        label = raw_dict.get("ID_FS_LABEL", "") if subsystem == "block" else ""
        uuid = raw_dict.get("ID_FS_UUID", "") if subsystem == "block" else ""

        # Symlinks
        symlinks = set()
        if hasattr(device, "device_links"):
            symlinks = set(device.device_links)

        # Partitions (only for block devices)
        partitions = []
        if subsystem == "block" and hasattr(device, "children"):
            partitions = [child.sys_name for child in device.children]

        return cls(
            name=name,
            device_node=device_node,
            sys_path=sys_path,
            subsystem=subsystem,
            device_type=device_type,
            model=model,
            vendor=vendor,
            serial=serial,
            vendor_id=vendor_id,
            product_id=product_id,
            size=size,
            removable=removable,
            uuid=uuid,
            label=label,
            partitions=partitions,
            symlinks=symlinks,
            raw=raw_dict,
        )

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
            return f"{self.model} ({self.name})"
        else:
            return self.name

    def is_ready(self) -> bool:
        """Check if the device node exists and is ready for operations."""
        if not self.device_node:
            return False
        return Path(self.device_node).exists()

    def wait_for_ready(self, timeout: float = 5.0, poll_interval: float = 0.1) -> bool:
        """Wait for the device node to be ready.

        Args:
            timeout: Maximum time to wait in seconds
            poll_interval: Time between checks in seconds

        Returns:
            True if device becomes ready, False if timeout
        """
        import time

        start_time = time.time()

        while time.time() - start_time < timeout:
            if self.is_ready():
                return True
            time.sleep(poll_interval)

        return False

    @property
    def type(self) -> str:
        """Alias for device_type for BlockDevice compatibility."""
        return self.device_type

    @property
    def path(self) -> str:
        """Return device_node for BlockDevice compatibility.

        Note: This differs from the sys_path field which contains the /sys/ path.
        For BlockDevice compatibility, this property returns device_node.
        """
        return self.device_node


@dataclass
class DiskInfo:
    """Disk information from diskutil."""

    size: int = 0
    media_name: str = ""
    volume_name: str = ""
    removable: bool = False
    protocol: str = ""
    partitions: list[str] = field(default_factory=list)


@dataclass
class FirmwarePair:
    """Represents a pair of firmware files for split keyboards."""

    left: Path
    right: Path
    base_name: str = ""

    def __post_init__(self) -> None:
        """Validate firmware pair."""
        if not self.left.exists():
            raise ValueError(f"Left firmware file not found: {self.left}")
        if not self.right.exists():
            raise ValueError(f"Right firmware file not found: {self.right}")
        if not self.base_name:
            # Extract base name from left firmware
            name = self.left.stem
            for suffix in ["_lh", "_left", "-left", "_l"]:
                if name.endswith(suffix):
                    self.base_name = name[: -len(suffix)]
                    break
            if not self.base_name:
                self.base_name = name


class FlashResult(BaseResult):
    """Result of firmware flash operations."""

    devices_flashed: int = 0
    devices_failed: int = 0
    firmware_path: Path | None = None
    device_details: list[dict[str, Any]] = Field(default_factory=list)
    paired_mode: bool = False  # Track if this was a paired flash operation
    firmware_pairs: list[FirmwarePair] = Field(default_factory=list)

    @field_validator("devices_flashed", "devices_failed")
    @classmethod
    def validate_device_counts(cls, v: int) -> int:
        """Validate device counts are non-negative."""
        if not isinstance(v, int) or v < 0:
            raise ValueError("Device counts must be non-negative integers") from None
        return v

    @field_validator("firmware_path")
    @classmethod
    def validate_firmware_path(cls, v: Any) -> Path | None:
        """Validate firmware path if provided."""
        if v is None:
            return None
        if isinstance(v, Path):
            return v
        if isinstance(v, str):
            return Path(v)
        # If we get here, v is neither None, Path, nor str
        raise ValueError("Firmware path must be a Path object or string") from None

    @field_validator("device_details")
    @classmethod
    def validate_device_details(cls, v: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate device details structure."""
        if not isinstance(v, list):
            raise ValueError("Device details must be a list") from None

        for detail in v:
            if not isinstance(detail, dict):
                raise ValueError("Each device detail must be a dictionary") from None
            if "name" not in detail or "status" not in detail:
                raise ValueError(
                    "Device details must have 'name' and 'status' fields"
                ) from None
            if detail["status"] not in ["success", "failed"]:
                raise ValueError(
                    "Device status must be 'success' or 'failed'"
                ) from None

        return v

    def add_device_success(
        self,
        device_name: str,
        device_info: dict[str, Any] | None = None,
        firmware_side: FirmwareSide | None = None,
    ) -> None:
        """Record a successful device flash."""
        if not isinstance(device_name, str) or not device_name.strip():
            raise ValueError("Device name must be a non-empty string") from None

        self.devices_flashed += 1
        device_detail = {"name": device_name, "status": "success"}
        if firmware_side:
            device_detail["firmware_side"] = firmware_side.value
        if device_info:
            if not isinstance(device_info, dict):
                raise ValueError("Device info must be a dictionary") from None
            device_detail.update(device_info)
        self.device_details.append(device_detail)
        side_msg = f" ({firmware_side.value} side)" if firmware_side else ""
        self.add_message(f"Successfully flashed device{side_msg}: {device_name}")

    def add_device_failure(
        self,
        device_name: str,
        error: str,
        device_info: dict[str, Any] | None = None,
        firmware_side: FirmwareSide | None = None,
    ) -> None:
        """Record a failed device flash."""
        if not isinstance(device_name, str) or not device_name.strip():
            raise ValueError("Device name must be a non-empty string") from None
        if not isinstance(error, str) or not error.strip():
            raise ValueError("Error must be a non-empty string") from None

        self.devices_failed += 1
        device_detail = {"name": device_name, "status": "failed", "error": error}
        if firmware_side:
            device_detail["firmware_side"] = firmware_side.value
        if device_info:
            if not isinstance(device_info, dict):
                raise ValueError("Device info must be a dictionary") from None
            device_detail.update(device_info)
        self.device_details.append(device_detail)
        side_msg = f" ({firmware_side.value} side)" if firmware_side else ""
        self.add_error(f"Failed to flash device{side_msg} {device_name}: {error}")

    def get_flash_summary(self) -> dict[str, Any]:
        """Get flash operation summary."""
        total_devices = self.devices_flashed + self.devices_failed
        return {
            "total_devices": total_devices,
            "devices_flashed": self.devices_flashed,
            "devices_failed": self.devices_failed,
            "success_rate": (
                self.devices_flashed / total_devices if total_devices > 0 else 0.0
            ),
            "firmware_path": str(self.firmware_path) if self.firmware_path else None,
        }

    def validate_flash_consistency(self) -> bool:
        """Validate that device counts match device details."""
        expected_total = len(self.device_details)
        actual_total = self.devices_flashed + self.devices_failed

        if expected_total != actual_total:
            self.add_error(
                f"Device count mismatch: {expected_total} details vs {actual_total} counted"
            )
            return False

        success_count = sum(1 for d in self.device_details if d["status"] == "success")
        failed_count = sum(1 for d in self.device_details if d["status"] == "failed")

        if success_count != self.devices_flashed:
            self.add_error(
                f"Success count mismatch: {success_count} in details vs {self.devices_flashed} counted"
            )
            return False

        if failed_count != self.devices_failed:
            self.add_error(
                f"Failed count mismatch: {failed_count} in details vs {self.devices_failed} counted"
            )
            return False

        return True


@dataclass
class BlockDevice:
    """Represents a block device with its properties.

    This model represents USB block devices detected by the system,
    including their metadata, mount points, and device characteristics.
    """

    name: str
    device_node: str = ""  # Store the original device node for easier access
    size: int = 0
    type: str = "unknown"
    removable: bool = False
    model: str = ""
    vendor: str = ""
    serial: str = ""
    uuid: str = ""
    label: str = ""
    vendor_id: str = ""  # USB vendor ID (PID)
    product_id: str = ""  # USB product ID (PID)
    partitions: list[str] = field(default_factory=list)
    mountpoints: dict[str, str] = field(default_factory=dict)
    symlinks: set[str] = field(default_factory=set)
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

    def is_ready(self) -> bool:
        """Check if the device node exists and is ready for operations."""
        if not self.device_node:
            return False
        return Path(self.device_node).exists()

    def wait_for_ready(self, timeout: float = 5.0, poll_interval: float = 0.1) -> bool:
        """Wait for the device node to be ready.

        Args:
            timeout: Maximum time to wait in seconds
            poll_interval: Time between checks in seconds

        Returns:
            True if device becomes ready, False if timeout
        """
        import time

        start_time = time.time()

        while time.time() - start_time < timeout:
            if self.is_ready():
                return True
            time.sleep(poll_interval)

        return False

    @classmethod
    def from_pyudev_device(cls, device: Any) -> "BlockDevice":
        """Create a BlockDevice from a pyudev Device."""
        name = device.sys_name
        device_node = device.device_node

        raw_dict = dict(device.properties.items())

        # Extract size using device attributes
        size = 0
        if device.attributes.get("size"):
            with contextlib.suppress(ValueError, TypeError):
                size = int(device.attributes.get("size", 0)) * 512

        # Get removable status from attributes
        removable = False
        if device.attributes.get("removable"):
            with contextlib.suppress(ValueError, TypeError):
                removable = bool(int(device.attributes.get("removable", 0)))

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
        except (AttributeError, KeyError):
            pass  # Keep partitions as empty list

        # Create the block device object
        return cls(
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
            serial=device.properties.get("ID_SERIAL_SHORT", ""),
            vendor_id=device.properties.get("ID_VENDOR_ID", ""),
            product_id=device.properties.get("ID_MODEL_ID", ""),
            raw=raw_dict,
        )

    @classmethod
    def from_macos_disk_info(
        cls,
        disk_name: str,
        disk_info: "DiskInfo",
        usb_info: "USBDeviceInfo | None" = None,
        mounted_volumes: set[str] | None = None,
    ) -> "BlockDevice":
        """Create a BlockDevice from macOS disk and USB info."""
        if mounted_volumes is None:
            mounted_volumes = set()

        volume_name = disk_info.volume_name

        return cls(
            name=disk_name,
            device_node=f"/dev/{disk_name}",
            model=(
                usb_info.name if usb_info and usb_info.name else disk_info.media_name
            )
            or "Unknown",
            vendor=usb_info.vendor if usb_info and usb_info.vendor else "Unknown",
            serial=usb_info.serial if usb_info else "",
            size=disk_info.size,
            removable=disk_info.removable,
            type="usb" if usb_info else "disk",
            partitions=disk_info.partitions,
            vendor_id=usb_info.vendor_id if usb_info else "",
            product_id=usb_info.product_id if usb_info else "",
            mountpoints={volume_name: f"/Volumes/{volume_name}"}
            if volume_name in mounted_volumes
            else {},
        )


# Type alias for USB device types
USBDeviceType = BlockDevice | USBDevice


def detect_firmware_side(firmware_path: Path) -> FirmwareSide:
    """Detect the side of a firmware file based on its name.

    Args:
        firmware_path: Path to the firmware file

    Returns:
        FirmwareSide enum value (LEFT, RIGHT, or UNIFIED)
    """
    name = firmware_path.stem.lower()

    # Check for left side patterns
    left_patterns = ["_lh", "_left", "-left", "_l", "left_", "lh_"]
    for pattern in left_patterns:
        if pattern in name:
            return FirmwareSide.LEFT

    # Check for right side patterns
    right_patterns = ["_rh", "_right", "-right", "_r", "right_", "rh_"]
    for pattern in right_patterns:
        if pattern in name:
            return FirmwareSide.RIGHT

    # Default to unified for non-split firmware
    return FirmwareSide.UNIFIED


def is_split_firmware(firmware_files: list[Path]) -> bool:
    """Check if the firmware files are for a split keyboard.

    Args:
        firmware_files: List of firmware file paths

    Returns:
        True if files are for split keyboard (left/right pair)
    """
    if len(firmware_files) != 2:
        return False

    sides = [detect_firmware_side(f) for f in firmware_files]
    return FirmwareSide.LEFT in sides and FirmwareSide.RIGHT in sides
