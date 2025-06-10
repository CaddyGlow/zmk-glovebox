"""Method-specific configuration models for flash methods."""

from abc import ABC
from pathlib import Path

from pydantic import BaseModel, Field


class FlashMethodConfig(BaseModel, ABC):
    """Base configuration for flash methods."""

    method_type: str
    fallback_methods: list[str] = Field(default_factory=list)


class USBFlashConfig(FlashMethodConfig):
    """USB mounting flash configuration."""

    method_type: str = "usb"
    device_query: str
    mount_timeout: int = 30
    copy_timeout: int = 60
    sync_after_copy: bool = True


class DFUFlashConfig(FlashMethodConfig):
    """DFU-util flash configuration."""

    method_type: str = "dfu"
    vid: str
    pid: str
    interface: int = 0
    alt_setting: int = 0
    timeout: int = 30


class BootloaderFlashConfig(FlashMethodConfig):
    """Direct bootloader flash configuration."""

    method_type: str = "bootloader"
    protocol: str  # "uart", "spi", "i2c"
    port: str | None = None  # "/dev/ttyUSB0" for UART
    baud_rate: int = 115200
    reset_sequence: list[str] = Field(default_factory=list)


class WiFiFlashConfig(FlashMethodConfig):
    """Wireless flash configuration."""

    method_type: str = "wifi"
    host: str
    port: int = 8080
    protocol: str = "http"  # "http", "mqtt", "websocket"
    auth_token: str | None = None
