"""ZMK configuration models."""

from pydantic import BaseModel, Field


# ZMK Constants
MACRO_PLACEHOLDER = "MACRO_PLACEHOLDER"


class ZmkCompatibleStrings(BaseModel):
    """ZMK compatible string constants."""

    macro: str = Field(default="zmk,behavior-macro")
    macro_one_param: str = Field(default="zmk,behavior-macro-one-param")
    macro_two_param: str = Field(default="zmk,behavior-macro-two-param")
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
