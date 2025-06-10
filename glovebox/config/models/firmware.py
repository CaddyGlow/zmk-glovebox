"""Firmware configuration models."""

from typing import Any

from pydantic import BaseModel, Field


class KConfigOption(BaseModel):
    """Definition of a KConfig option."""

    name: str
    type: str
    default: Any
    description: str


class BuildOptions(BaseModel):
    """Build options for a firmware."""

    repository: str
    branch: str


class FirmwareConfig(BaseModel):
    """Firmware configuration for a keyboard."""

    version: str
    description: str
    build_options: BuildOptions
    kconfig: dict[str, KConfigOption] | None = None


class FirmwareFlashConfig(BaseModel):
    """Firmware flash configuration settings."""

    # Device detection and flashing behavior
    timeout: int = Field(
        default=60, ge=1, description="Timeout in seconds for flash operations"
    )
    count: int = Field(
        default=2, ge=0, description="Number of devices to flash (0 for infinite)"
    )
    track_flashed: bool = Field(
        default=True, description="Enable device tracking during flash"
    )
    skip_existing: bool = Field(
        default=False, description="Skip devices already present at startup"
    )


class UserFirmwareConfig(BaseModel):
    """Firmware-related configuration settings."""

    flash: FirmwareFlashConfig = Field(default_factory=FirmwareFlashConfig)
