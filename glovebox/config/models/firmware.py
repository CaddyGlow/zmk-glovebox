"""Firmware configuration models."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


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

    # Device waiting behavior
    wait: bool = Field(
        default=False, description="Wait for devices to connect before flashing"
    )
    poll_interval: float = Field(
        default=0.5,
        ge=0.1,
        le=5.0,
        description="Polling interval in seconds when waiting",
    )
    show_progress: bool = Field(
        default=True, description="Show real-time device detection progress"
    )


class FirmwareDockerConfig(BaseModel):
    """Docker user context configuration for firmware compilation."""

    # Auto-detection settings
    enable_user_mapping: bool = Field(
        default=True,
        description="Enable Docker --user flag for volume permission handling",
    )
    detect_automatically: bool = Field(
        default=True,
        description="Automatically detect current user UID/GID from system",
    )

    # Manual override settings (optional)
    manual_uid: int | None = Field(
        default=None,
        ge=0,
        description="Manual UID override (takes precedence over auto-detection)",
    )
    manual_gid: int | None = Field(
        default=None,
        ge=0,
        description="Manual GID override (takes precedence over auto-detection)",
    )
    manual_username: str | None = Field(
        default=None,
        description="Manual username override (takes precedence over auto-detection)",
    )

    # Home directory settings
    host_home_dir: Path | None = Field(
        default=None, description="Host home directory to map into container"
    )
    container_home_dir: str = Field(
        default="/tmp", description="Home directory path inside container"
    )

    # Advanced options
    force_manual: bool = Field(
        default=False,
        description="Force manual user context even when auto-detection works",
    )
    debug_user_mapping: bool = Field(
        default=False,
        description="Enable debug logging for Docker user mapping operations",
    )

    @field_validator("manual_username")
    @classmethod
    def validate_manual_username(cls, v: str | None) -> str | None:
        """Validate manual username is not empty if provided."""
        if v is not None and not v.strip():
            raise ValueError("Manual username cannot be empty")
        return v.strip() if v else None

    @field_validator("host_home_dir", mode="before")
    @classmethod
    def expand_host_home_dir(cls, v: str | Path | None) -> Path | None:
        """Expand user home and environment variables in host home directory."""
        if v is None:
            return None
        path = Path(v).expanduser()
        return path.resolve() if path.exists() else path

    @field_validator("container_home_dir")
    @classmethod
    def validate_container_home_dir(cls, v: str) -> str:
        """Validate container home directory is absolute path."""
        if not v.startswith("/"):
            raise ValueError("Container home directory must be an absolute path")
        return v


class UserFirmwareConfig(BaseModel):
    """Firmware-related configuration settings."""

    flash: FirmwareFlashConfig = Field(default_factory=FirmwareFlashConfig)
    docker: FirmwareDockerConfig = Field(default_factory=FirmwareDockerConfig)
