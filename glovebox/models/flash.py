"""Models and type definitions for flash operations."""

from typing import Any


# Type definitions for BlockDevice
BlockDeviceDict = dict[str, Any]
BlockDevicePathMap = dict[str, str]
BlockDeviceSymlinks = set[str]
USBDeviceInfo = dict[str, str]
DiskInfo = dict[str, Any]
