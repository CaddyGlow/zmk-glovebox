"""
Type definitions for keyboard and user configuration.

This module provides dataclasses and models for representing configuration data
loaded from YAML files. These provide type safety, validation,
and help with IDE autocompletion.
"""

import os
from pathlib import Path
from typing import Annotated, Any, Optional, Union

from pydantic import (
    BaseModel,
    BeforeValidator,
    Field,
    PlainValidator,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def parse_keyboard_paths(value: Any) -> list[Path]:
    """Parse keyboard_paths from various input formats."""
    if isinstance(value, list):
        # Already a list, convert items to Path objects
        return [Path(item) if not isinstance(item, Path) else item for item in value]
    elif isinstance(value, str):
        # Comma-separated string from environment variable or file
        if not value.strip():
            return []
        return [Path(path.strip()) for path in value.split(",") if path.strip()]
    elif value is None:
        return []
    else:
        raise ValueError(f"Invalid keyboard_paths format: {type(value)}")


# KConfig type definitions
class KConfigOption(BaseModel):
    """Definition of a KConfig option."""

    name: str
    type: str
    default: Any
    description: str


# Flash configuration
class FlashConfig(BaseModel):
    """Flash configuration for a keyboard."""

    method: str
    query: str
    usb_vid: str
    usb_pid: str

    @field_validator("method", "query", "usb_vid", "usb_pid")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        """Validate that string fields are not empty."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()


# Build configuration
class BuildConfig(BaseModel):
    """Build configuration for a keyboard."""

    method: str
    docker_image: str
    repository: str
    branch: str

    @field_validator("method", "docker_image", "repository", "branch")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        """Validate that string fields are not empty."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()


# Visual layout configuration
class VisualLayout(BaseModel):
    """Visual layout for a keyboard."""

    rows: list[list[int]]


# Formatting configuration
class FormattingConfig(BaseModel):
    """Formatting configuration for a keyboard."""

    default_key_width: int = Field(
        gt=0, description="Default key width must be positive"
    )
    key_gap: str
    base_indent: str = ""
    rows: list[list[int]] | None = None

    @field_validator("key_gap")
    @classmethod
    def validate_key_gap(cls, v: str) -> str:
        """Validate that key_gap is provided (can be spaces)."""
        if v is None:
            raise ValueError("Key gap cannot be None")
        return v


# Firmware build options
class BuildOptions(BaseModel):
    """Build options for a firmware."""

    repository: str
    branch: str


# Firmware configuration
class FirmwareConfig(BaseModel):
    """Firmware configuration for a keyboard."""

    version: str
    description: str
    build_options: BuildOptions
    kconfig: dict[str, KConfigOption] | None = None


# Keymap section
class KeymapSection(BaseModel):
    """Keymap section of a keyboard configuration."""

    includes: list[str]
    formatting: FormattingConfig
    system_behaviors: list[Any]
    kconfig_options: dict[str, KConfigOption]
    keymap_dtsi: str | None = None
    system_behaviors_dts: str | None = None
    key_position_header: str | None = None


# Complete keyboard configuration
class KeyboardConfig(BaseModel):
    """Complete keyboard configuration."""

    keyboard: str
    description: str
    vendor: str
    key_count: int = Field(gt=0, description="Number of keys must be positive")
    flash: FlashConfig
    build: BuildConfig
    firmwares: dict[str, FirmwareConfig] = Field(default_factory=dict)
    keymap: KeymapSection = Field(
        default_factory=lambda: KeymapSection(
            includes=[],
            formatting=FormattingConfig(default_key_width=4, key_gap=" "),
            system_behaviors=[],
            kconfig_options={},
        )
    )

    @field_validator("keyboard", "description", "vendor")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        """Validate that string fields are not empty."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()

    @model_validator(mode="before")
    @classmethod
    def validate_and_convert_data(cls, data: Any) -> Any:
        """Convert nested dictionaries to proper models."""
        if not isinstance(data, dict):
            return data

        # Convert keymap section using layout domain utility (if present)
        if data.get("keymap") and isinstance(data["keymap"], dict):
            try:
                from glovebox.layout.utils import convert_keymap_section_from_dict

                data["keymap"] = convert_keymap_section_from_dict(data["keymap"])
            except ImportError:
                # Layout utils not available, keep as-is
                pass

        return data


# Firmware flash configuration
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


# Firmware configuration subsection
class UserFirmwareConfig(BaseModel):
    """Firmware-related configuration settings."""

    flash: FirmwareFlashConfig = Field(default_factory=FirmwareFlashConfig)


# User configuration model using Pydantic Settings
class UserConfigData(BaseSettings):
    """User configuration data model with automatic environment variable support.

    This model represents user-specific configuration settings with validation
    and automatic environment variable parsing.

    Precedence order (highest to lowest):
    1. Environment variables (highest)
    2. Constructor arguments (file data)
    3. .env file
    4. Default values (lowest)
    """

    model_config = SettingsConfigDict(
        env_prefix="GLOVEBOX_",
        env_nested_delimiter="__",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        json_schema_extra={
            "env_ignore_empty": True,
        },
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: Any,
        env_settings: Any,
        dotenv_settings: Any,
        file_secret_settings: Any,
    ) -> tuple[Any, ...]:
        """
        Customize the sources and their precedence order.

        Returns sources in priority order: env > init > dotenv > file_secret
        This ensures environment variables override file configuration.
        """
        return (
            env_settings,  # Highest precedence: environment variables
            init_settings,  # Second: constructor arguments (file data)
            dotenv_settings,  # Third: .env file
            file_secret_settings,  # Lowest: file secrets
        )

    keyboard_paths: Annotated[list[Path], NoDecode] = []

    # Paths for user-defined keyboards and layouts (stored as string, accessed as list[Path])
    @field_validator("keyboard_paths", mode="before")
    @classmethod
    def decode_keyboard_paths(cls, v: Any) -> list[Path]:
        if isinstance(v, str):
            return [Path(path.strip()) for path in v.split(",") if path.strip()]
        elif isinstance(v, list):
            return [
                Path(path.strip() if isinstance(path, str) else path)
                for path in v
                if str(path).strip()
            ]
        return []

    # Default profile (keyboard/firmware combination)
    profile: str = Field(
        default="glove80/v25.05",
        description="Default keyboard/firmware profile (e.g., 'glove80/v25.05')",
    )

    # Logging
    log_level: str = "INFO"

    # Firmware settings
    firmware: UserFirmwareConfig = Field(default_factory=UserFirmwareConfig)

    # Backward compatibility - deprecated, use firmware.flash.skip_existing instead
    flash_skip_existing: bool = Field(
        default=False, description="Deprecated: use firmware.flash.skip_existing"
    )

    @field_validator("profile")
    @classmethod
    def validate_profile(cls, v: str) -> str:
        """Validate profile follows keyboard/firmware or keyboard-only format."""
        if not v or not v.strip():
            raise ValueError(
                "Profile must be in format 'keyboard/firmware' (e.g., 'glove80/v25.05') or 'keyboard' (e.g., 'glove80')"
            )

        # Handle keyboard-only format (no slash)
        if "/" not in v:
            if not v.strip():
                raise ValueError("Keyboard name cannot be empty")
            return v.strip()

        # Handle keyboard/firmware format
        parts = v.split("/")
        if len(parts) != 2 or not all(part.strip() for part in parts):
            raise ValueError(
                "Profile must be in format 'keyboard/firmware' (e.g., 'glove80/v25.05') or 'keyboard' (e.g., 'glove80')"
            )

        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is a recognized value."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        # Strip whitespace and convert to uppercase
        upper_v = v.strip().upper()
        if upper_v not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return upper_v  # Always normalize to uppercase
