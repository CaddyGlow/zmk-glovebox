"""Flash module for firmware flashing functionality."""

from .detect import detect_device
from .usb import flash_firmware


__all__ = ["flash_firmware", "detect_device"]
