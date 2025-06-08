"""
Type definitions for keyboard and user configuration.

This module provides dataclasses and models for representing configuration data
loaded from YAML files. These provide type safety, validation,
and help with IDE autocompletion.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeAlias

from pydantic import BaseModel, Field, field_validator


# KConfig type definitions
@dataclass
class KConfigOption:
    """Definition of a KConfig option."""

    name: str
    type: str
    default: Any
    description: str


# Flash configuration
@dataclass
class FlashConfig:
    """Flash configuration for a keyboard."""

    method: str
    query: str
    usb_vid: str
    usb_pid: str


# Build configuration
@dataclass
class BuildConfig:
    """Build configuration for a keyboard."""

    method: str
    docker_image: str
    repository: str
    branch: str


# Visual layout configuration
@dataclass
class VisualLayout:
    """Visual layout for a keyboard."""

    rows: list[list[int]]


# Formatting configuration
@dataclass
class FormattingConfig:
    """Formatting configuration for a keyboard."""

    default_key_width: int
    key_gap: str
    base_indent: str = ""
    rows: list[list[int]] | None = None


# Firmware build options
@dataclass
class BuildOptions:
    """Build options for a firmware."""

    repository: str
    branch: str


# Firmware configuration
@dataclass
class FirmwareConfig:
    """Firmware configuration for a keyboard."""

    version: str
    description: str
    build_options: BuildOptions
    kconfig: dict[str, KConfigOption] | None = None


# Keymap section
@dataclass
class KeymapSection:
    """Keymap section of a keyboard configuration."""

    includes: list[str]
    formatting: FormattingConfig
    system_behaviors: list[Any]
    kconfig_options: dict[str, KConfigOption]
    keymap_dtsi: str | None = None
    system_behaviors_dts: str | None = None
    key_position_header: str | None = None


# Complete keyboard configuration
@dataclass
class KeyboardConfig:
    """Complete keyboard configuration."""

    keyboard: str
    description: str
    vendor: str
    key_count: int
    flash: FlashConfig
    build: BuildConfig
    firmwares: dict[str, FirmwareConfig]
    keymap: KeymapSection

    def __post_init__(self) -> None:
        """Convert nested dictionaries to proper dataclasses."""
        # Convert flash config
        if isinstance(self.flash, dict):
            self.flash = FlashConfig(**self.flash)

        # Convert build config
        if isinstance(self.build, dict):
            self.build = BuildConfig(**self.build)

        # Convert firmwares
        if isinstance(self.firmwares, dict):
            converted_firmwares = {}
            for firmware_name, firmware_data in self.firmwares.items():
                # Cast to dict for type safety
                firmware_dict = firmware_data if isinstance(firmware_data, dict) else {}

                # Convert build options
                build_options_dict = firmware_dict.get("build_options", {})
                if isinstance(build_options_dict, dict):
                    build_options = BuildOptions(**build_options_dict)
                else:
                    build_options = BuildOptions(repository="", branch="")

                # Convert kconfig options
                kconfig_dict = firmware_dict.get("kconfig", {})
                if isinstance(kconfig_dict, dict):
                    converted_kconfig = {}
                    for k_name, k_data in kconfig_dict.items():
                        if isinstance(k_data, dict):
                            converted_kconfig[k_name] = KConfigOption(**k_data)
                    kconfig = converted_kconfig
                else:
                    kconfig = None

                # Create firmware config
                converted_firmwares[firmware_name] = FirmwareConfig(
                    version=firmware_dict.get("version", ""),
                    description=firmware_dict.get("description", ""),
                    build_options=build_options,
                    kconfig=kconfig,
                )
            self.firmwares = converted_firmwares

        # Convert keymap section
        if isinstance(self.keymap, dict):
            # Use layout domain utility to convert keymap section
            from glovebox.layout.utils import convert_keymap_section_from_dict

            self.keymap = convert_keymap_section_from_dict(self.keymap)


# User configuration model
class UserConfigData(BaseModel):
    """User configuration data model.

    This model represents user-specific configuration settings with validation.
    """

    # Paths for user-defined keyboards and layouts
    keyboard_paths: list[str] = Field(default_factory=list)

    # Default preferences
    default_keyboard: str = "glove80"
    default_firmware: str = "v25.05"

    # Logging
    log_level: str = "INFO"

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is a recognized value."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        upper_v = v.upper()
        if upper_v not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return upper_v  # Always normalize to uppercase

    @field_validator("keyboard_paths")
    @classmethod
    def validate_keyboard_paths(cls, v: list[str]) -> list[str]:
        """Validate keyboard paths are strings."""
        if not isinstance(v, list):
            raise ValueError("keyboard_paths must be a list")

        # Ensure all paths are strings
        return [str(path) for path in v]

    def get_expanded_keyboard_paths(self) -> list[Path]:
        """Get a list of expanded Path objects for keyboard_paths."""
        expanded_paths = []
        for path_str in self.keyboard_paths:
            # Expand environment variables and user directory
            expanded_path = os.path.expandvars(str(Path(path_str).expanduser()))
            expanded_paths.append(Path(expanded_path))

        return expanded_paths
