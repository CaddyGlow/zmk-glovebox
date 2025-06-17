"""Unified flash configuration for USB firmware flashing."""

from pydantic import BaseModel


class USBFlashConfig(BaseModel):
    """USB mounting flash configuration.

    Simplified unified configuration for USB-based firmware flashing,
    which is the primary method used by ZMK keyboards.
    """

    method_type: str = "usb"
    device_query: str
    mount_timeout: int = 30
    copy_timeout: int = 60
    sync_after_copy: bool = True


__all__ = ["USBFlashConfig"]
