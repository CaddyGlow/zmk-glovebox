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

from glovebox.config.compile_methods import (
    CompileMethodConfig,
    CrossCompileConfig,
    DockerCompileConfig,
    LocalCompileConfig,
    QemuCompileConfig,
)
from glovebox.config.flash_methods import (
    BootloaderFlashConfig,
    DFUFlashConfig,
    FlashMethodConfig,
    USBFlashConfig,
    WiFiFlashConfig,
)


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


# Behavior configuration models
class BehaviorMapping(BaseModel):
    """Individual behavior class mapping."""

    behavior_name: str = Field(description="ZMK behavior name (e.g., '&kp')")
    behavior_class: str = Field(description="Python class name (e.g., 'KPBehavior')")


class ModifierMapping(BaseModel):
    """Modifier key mapping configuration."""

    long_form: str = Field(description="Long modifier name (e.g., 'LALT')")
    short_form: str = Field(description="Short modifier name (e.g., 'LA')")


class BehaviorConfig(BaseModel):
    """Behavior system configuration."""

    behavior_mappings: list[BehaviorMapping] = Field(default_factory=list)
    modifier_mappings: list[ModifierMapping] = Field(default_factory=list)
    magic_layer_command: str = Field(default="&magic LAYER_Magic 0")
    reset_behavior_alias: str = Field(default="&sys_reset")


# Display configuration models
class LayoutStructure(BaseModel):
    """Physical layout structure for display."""

    rows: dict[str, list[list[int]]] = Field(
        description="Row-wise key position mapping"
    )

    @field_validator("rows")
    @classmethod
    def validate_row_structure(
        cls, v: dict[str, list[list[int]]]
    ) -> dict[str, list[list[int]]]:
        """Validate row structure contains valid key positions."""
        if not v:
            raise ValueError("Row structure cannot be empty")

        # Validate that all values are lists of lists of integers
        for row_name, row_data in v.items():
            if not isinstance(row_data, list):
                raise ValueError(f"Row '{row_name}' must be a list")
            for i, segment in enumerate(row_data):
                if not isinstance(segment, list):
                    raise ValueError(f"Row '{row_name}' segment {i} must be a list")
                for j, key_pos in enumerate(segment):
                    if not isinstance(key_pos, int) or key_pos < 0:
                        raise ValueError(
                            f"Row '{row_name}' segment {i} position {j} must be a non-negative integer"
                        )

        return v


class DisplayFormatting(BaseModel):
    """Display formatting configuration."""

    header_width: int = Field(default=80, gt=0)
    none_display: str = Field(default="&none")
    trans_display: str = Field(default="▽")
    key_width: int = Field(default=8, gt=0)
    center_small_rows: bool = Field(default=True)
    horizontal_spacer: str = Field(default=" | ")


class DisplayConfig(BaseModel):
    """Complete display configuration."""

    layout_structure: LayoutStructure | None = None
    formatting: DisplayFormatting = Field(default_factory=DisplayFormatting)


# ZMK configuration models
class ZmkCompatibleStrings(BaseModel):
    """ZMK compatible string constants."""

    macro: str = Field(default="zmk,behavior-macro")
    hold_tap: str = Field(default="zmk,behavior-hold-tap")
    combos: str = Field(default="zmk,combos")
    keymap: str = Field(default="zmk,keymap")


class ZmkPatterns(BaseModel):
    """ZMK naming and pattern configuration."""

    layer_define: str = Field(default="LAYER_{}")
    node_name_sanitize: str = Field(default="[^A-Z0-9_]")
    kconfig_prefix: str = Field(default="CONFIG_")


class FileExtensions(BaseModel):
    """File extension configuration."""

    keymap: str = Field(default=".keymap")
    conf: str = Field(default=".conf")
    dtsi: str = Field(default=".dtsi")
    metadata: str = Field(default=".json")


class ValidationLimits(BaseModel):
    """Validation limits and thresholds."""

    max_layers: int = Field(default=10, gt=0)
    max_macro_params: int = Field(default=2, gt=0)
    required_holdtap_bindings: int = Field(default=2, gt=0)
    warn_many_layers_threshold: int = Field(default=10, gt=0)


class ZmkConfig(BaseModel):
    """ZMK-specific configuration and constants."""

    compatible_strings: ZmkCompatibleStrings = Field(
        default_factory=ZmkCompatibleStrings
    )
    hold_tap_flavors: list[str] = Field(
        default=[
            "tap-preferred",
            "hold-preferred",
            "balanced",
            "tap-unless-interrupted",
        ]
    )
    patterns: ZmkPatterns = Field(default_factory=ZmkPatterns)
    file_extensions: FileExtensions = Field(default_factory=FileExtensions)
    validation_limits: ValidationLimits = Field(default_factory=ValidationLimits)


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


# Union types for method configurations
CompileMethodConfigUnion = (
    DockerCompileConfig | LocalCompileConfig | CrossCompileConfig | QemuCompileConfig
)

FlashMethodConfigUnion = (
    USBFlashConfig | DFUFlashConfig | BootloaderFlashConfig | WiFiFlashConfig
)


# Complete keyboard configuration
class KeyboardConfig(BaseModel):
    """Complete keyboard configuration with method-specific configs."""

    keyboard: str
    description: str
    vendor: str
    key_count: int = Field(gt=0, description="Number of keys must be positive")

    # Method-specific configurations (required for all keyboards)
    compile_methods: list[CompileMethodConfigUnion] = Field(default_factory=list)
    flash_methods: list[FlashMethodConfigUnion] = Field(default_factory=list)

    # Optional sections
    firmwares: dict[str, FirmwareConfig] = Field(default_factory=dict)
    keymap: KeymapSection = Field(
        default_factory=lambda: KeymapSection(
            includes=[],
            formatting=FormattingConfig(default_key_width=4, key_gap=" "),
            system_behaviors=[],
            kconfig_options={},
        )
    )

    # New configuration sections (Phase 2 additions)
    behavior: BehaviorConfig = Field(default_factory=BehaviorConfig)
    display: DisplayConfig = Field(default_factory=DisplayConfig)
    zmk: ZmkConfig = Field(default_factory=ZmkConfig)

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
