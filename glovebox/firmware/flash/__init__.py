"""Flash domain for firmware flashing functionality.

This package contains all flash-related functionality including:
- Flash service for high-level flash operations
- Flash models and result types
- Device detection and USB operations
- OS-specific flash adapters
"""

from .detect import create_device_detector
from .models import FlashResult
from .service import FlashService, create_flash_service
from .usb import create_firmware_flasher


__all__ = [
    # Service classes and factories
    "FlashService",
    "create_flash_service",
    # Models and results
    "FlashResult",
    # Low-level operations
    "create_device_detector",
    "create_firmware_flasher",
]
