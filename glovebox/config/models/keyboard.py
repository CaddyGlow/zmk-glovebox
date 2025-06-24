"""Keyboard configuration models."""

import logging
from typing import Any

from pydantic import ConfigDict, Field, field_validator, model_validator

from glovebox.compilation.models import (
    MoergoCompilationConfig,
    ZmkCompilationConfig,
)
from glovebox.layout.behavior.models import SystemBehavior
from glovebox.models.base import GloveboxBaseModel

from ..flash_methods import USBFlashConfig
from .behavior import BehaviorConfig
from .display import DisplayConfig
from .firmware import FirmwareConfig, KConfigOption
from .zmk import ZmkConfig


logger = logging.getLogger(__name__)


# Formatting configuration
class FormattingConfig(GloveboxBaseModel):
    """Formatting configuration for a keyboard."""

    # Override model config to preserve whitespace for formatting fields
    model_config = ConfigDict(
        extra="allow",
        str_strip_whitespace=False,  # Don't strip whitespace for formatting fields
        use_enum_values=True,
        validate_assignment=True,
    )

    key_gap: str = Field(default=" ")
    base_indent: str = ""
    rows: list[list[int]] | None = None
    vertical_split_threshold: float = Field(
        default=0.85,
        description="Console width threshold (0.0-1.0) for triggering vertical split display",
    )

    @field_validator("key_gap")
    @classmethod
    def validate_key_gap(cls, v: str) -> str:
        """Validate that key_gap is provided (can be spaces)."""
        if v is None:
            raise ValueError("Key gap cannot be None")
        return v


# Keymap section
class KeymapSection(GloveboxBaseModel):
    """Keymap section of a keyboard configuration."""

    header_includes: list[str]
    formatting: FormattingConfig
    system_behaviors: list[SystemBehavior]
    kconfig_options: dict[str, KConfigOption]
    keymap_dtsi: str | None = None
    keymap_dtsi_file: str | None = None
    system_behaviors_dts: str | None = None
    key_position_header: str | None = None

    @model_validator(mode="after")
    def validate_keymap_template_source(self) -> "KeymapSection":
        """Validate that only one keymap template source is specified."""
        has_inline = self.keymap_dtsi is not None
        has_file = self.keymap_dtsi_file is not None

        if has_inline and has_file:
            raise ValueError(
                "Cannot specify both keymap_dtsi and keymap_dtsi_file. "
                "Choose either inline template or template file."
            )

        return self


# Union types for method configurations
CompileMethodConfigUnion = ZmkCompilationConfig | MoergoCompilationConfig

FlashMethodConfigUnion = USBFlashConfig


# Complete keyboard configuration
class KeyboardConfig(GloveboxBaseModel):
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
            header_includes=[],
            formatting=FormattingConfig(key_gap=" "),
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

        # Handle top-level system_behaviors - move them to keymap section
        if "system_behaviors" in data:
            if "keymap" not in data or not isinstance(data["keymap"], dict):
                data["keymap"] = {}

            # Move top-level system_behaviors to keymap.system_behaviors
            data["keymap"]["system_behaviors"] = data.pop("system_behaviors")

        # Convert keymap section using layout domain utility (if present)
        if data.get("keymap") and isinstance(data["keymap"], dict):
            try:
                from glovebox.layout.utils import convert_keymap_section_from_dict

                data["keymap"] = convert_keymap_section_from_dict(data["keymap"])
            except ImportError:
                # Layout utils not available, keep as-is
                pass

        # Convert compile_methods: map 'strategy' field to 'type' field
        if "compile_methods" in data and isinstance(data["compile_methods"], list):
            for i, method in enumerate(data["compile_methods"]):
                if isinstance(method, dict) and "strategy" in method:
                    # Convert build_config to build_matrix format
                    if "build_config" in method:
                        build_config = method.pop("build_config")
                        if isinstance(build_config, dict):
                            from glovebox.compilation.models.build_matrix import (
                                BuildMatrix,
                            )

                            method["build_matrix"] = BuildMatrix.model_validate(
                                build_config
                            )

                    if method["strategy"] in "zmk_config":
                        data["compile_methods"][i] = (
                            ZmkCompilationConfig.model_validate(method)
                        )
                    elif method["strategy"] in "moergo":
                        data["compile_methods"][i] = (
                            MoergoCompilationConfig.model_validate(method)
                        )
                    else:
                        logger.warning(
                            "Unknown compilation strategy: %s", method["strategy"]
                        )
        #
        return data
