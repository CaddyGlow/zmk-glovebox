"""Keyboard configuration models."""

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from ..compile_methods import (
    CompilationConfig,
    CompileMethodConfig,
    CrossCompileConfig,
    DockerCompileConfig,
    LocalCompileConfig,
    QemuCompileConfig,
)
from ..flash_methods import (
    BootloaderFlashConfig,
    DFUFlashConfig,
    FlashMethodConfig,
    USBFlashConfig,
    WiFiFlashConfig,
)
from .behavior import BehaviorConfig
from .display import DisplayConfig
from .firmware import FirmwareConfig, KConfigOption
from .zmk import ZmkConfig


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
    DockerCompileConfig
    | CompilationConfig
    | LocalCompileConfig
    | CrossCompileConfig
    | QemuCompileConfig
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
