"""User behavior models for keyboard layouts."""

from typing import Union

from pydantic import Field, field_validator

from glovebox.layout.behavior.models import ParamValue
from glovebox.models.base import GloveboxBaseModel

from .core import LayoutBinding
from .types import LayerIndex, TemplateNumeric


class HoldTapBehavior(GloveboxBaseModel):
    """Model for hold-tap behavior definitions."""

    name: str
    description: str | None = ""
    bindings: list[str] = Field(default_factory=list)
    tapping_term_ms: TemplateNumeric = Field(default=None, alias="tappingTermMs")
    quick_tap_ms: TemplateNumeric = Field(default=None, alias="quickTapMs")
    flavor: str | None = None
    hold_trigger_on_release: bool | None = Field(
        default=None, alias="holdTriggerOnRelease"
    )
    require_prior_idle_ms: TemplateNumeric = Field(
        default=None, alias="requirePriorIdleMs"
    )
    hold_trigger_key_positions: list[int] | None = Field(
        default=None, alias="holdTriggerKeyPositions"
    )
    retro_tap: bool | None = Field(default=None, alias="retroTap")
    tap_behavior: str | None = Field(default=None, alias="tapBehavior")
    hold_behavior: str | None = Field(default=None, alias="holdBehavior")

    @field_validator("flavor")
    @classmethod
    def validate_flavor(cls, v: str | None) -> str | None:
        """Validate hold-tap flavor."""
        if v is not None:
            valid_flavors = [
                "tap-preferred",
                "hold-preferred",
                "balanced",
                "tap-unless-interrupted",
            ]
            if v not in valid_flavors:
                raise ValueError(
                    f"Invalid flavor: {v}. Must be one of {valid_flavors}"
                ) from None
        return v

    @field_validator("bindings")
    @classmethod
    def validate_bindings_count(cls, v: list[str]) -> list[str]:
        """Validate that hold-tap has exactly 2 bindings."""
        if len(v) != 2:
            raise ValueError(
                f"Hold-tap behavior requires exactly 2 bindings, found {len(v)}"
            ) from None
        return v


class ComboBehavior(GloveboxBaseModel):
    """Model for combo definitions."""

    name: str
    description: str | None = ""
    timeout_ms: TemplateNumeric = Field(default=None, alias="timeoutMs")
    key_positions: list[int] = Field(alias="keyPositions")
    layers: list[LayerIndex] | None = None
    binding: LayoutBinding = Field()
    behavior: str | None = Field(default=None, alias="behavior")

    @field_validator("key_positions")
    @classmethod
    def validate_key_positions(cls, v: list[int]) -> list[int]:
        """Validate key positions are valid."""
        if not v:
            raise ValueError("Combo must have at least one key position") from None
        for pos in v:
            if not isinstance(pos, int) or pos < 0:
                raise ValueError(f"Invalid key position: {pos}") from None
        return v


class MacroBehavior(GloveboxBaseModel):
    """Model for macro definitions."""

    name: str
    description: str | None = ""
    wait_ms: TemplateNumeric = Field(default=None, alias="waitMs")
    tap_ms: TemplateNumeric = Field(default=None, alias="tapMs")
    bindings: list[LayoutBinding] = Field(default_factory=list)
    params: list[ParamValue] | None = None

    @field_validator("params")
    @classmethod
    def validate_params_count(
        cls, v: list[ParamValue] | None
    ) -> list[ParamValue] | None:
        """Validate macro parameter count."""
        if v is not None and len(v) > 2:
            raise ValueError(
                f"Macro cannot have more than 2 parameters, found {len(v)}"
            ) from None
        return v


class TapDanceBehavior(GloveboxBaseModel):
    """Model for tap-dance behavior definitions."""

    name: str
    description: str | None = ""
    tapping_term_ms: TemplateNumeric = Field(default=None, alias="tappingTermMs")
    bindings: list[LayoutBinding] = Field(default_factory=list)

    @field_validator("bindings")
    @classmethod
    def validate_bindings_count(cls, v: list[LayoutBinding]) -> list[LayoutBinding]:
        """Validate tap-dance bindings count."""
        if len(v) < 2:
            raise ValueError("Tap-dance must have at least 2 bindings") from None
        if len(v) > 5:
            raise ValueError("Tap-dance cannot have more than 5 bindings") from None
        return v


class StickyKeyBehavior(GloveboxBaseModel):
    """Model for sticky-key behavior definitions."""

    name: str
    description: str | None = ""
    release_after_ms: TemplateNumeric = Field(default=None, alias="releaseAfterMs")
    quick_release: bool = Field(default=False, alias="quickRelease")
    lazy: bool = Field(default=False)
    ignore_modifiers: bool = Field(default=False, alias="ignoreModifiers")
    bindings: list[LayoutBinding] = Field(default_factory=list)


class CapsWordBehavior(GloveboxBaseModel):
    """Model for caps-word behavior definitions."""

    name: str
    description: str | None = ""
    continue_list: list[str] = Field(default_factory=list, alias="continueList")
    mods: int | None = Field(default=None)


class ModMorphBehavior(GloveboxBaseModel):
    """Model for mod-morph behavior definitions."""

    name: str
    description: str | None = ""
    mods: int
    bindings: list[LayoutBinding] = Field(default_factory=list)
    keep_mods: int | None = Field(default=None, alias="keepMods")

    @field_validator("bindings")
    @classmethod
    def validate_bindings_count(cls, v: list[LayoutBinding]) -> list[LayoutBinding]:
        """Validate mod-morph bindings count."""
        if len(v) != 2:
            raise ValueError("Mod-morph must have exactly 2 bindings") from None
        return v


class InputProcessor(GloveboxBaseModel):
    """Model for input processors."""

    code: str
    params: list[ParamValue] = Field(default_factory=list)


class InputListenerNode(GloveboxBaseModel):
    """Model for input listener nodes."""

    code: str
    description: str | None = ""
    layers: list[LayerIndex] = Field(default_factory=list)
    input_processors: list[InputProcessor] = Field(
        default_factory=list, alias="inputProcessors"
    )


# TODO: investigate the issue with the parser
# exclude_unset in to_dict consider it's empty at
# the creation
class InputListener(GloveboxBaseModel):
    """Model for input listeners."""

    code: str
    input_processors: list[InputProcessor] = Field(
        default_factory=list, alias="inputProcessors"
    )
    nodes: list[InputListenerNode] = Field(default_factory=list)


# Type alias for collections of behaviors
BehaviorList = list[
    HoldTapBehavior
    | ComboBehavior
    | MacroBehavior
    | TapDanceBehavior
    | StickyKeyBehavior
    | CapsWordBehavior
    | ModMorphBehavior
    | InputListener
]
