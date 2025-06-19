"""Behavior configuration models."""

from pydantic import Field

from glovebox.models.base import GloveboxBaseModel


class BehaviorMapping(GloveboxBaseModel):
    """Individual behavior class mapping."""

    behavior_name: str = Field(description="ZMK behavior name (e.g., '&kp')")
    behavior_class: str = Field(description="Python class name (e.g., 'KPBehavior')")


class ModifierMapping(GloveboxBaseModel):
    """Modifier key mapping configuration."""

    long_form: str = Field(description="Long modifier name (e.g., 'LALT')")
    short_form: str = Field(description="Short modifier name (e.g., 'LA')")


class BehaviorConfig(GloveboxBaseModel):
    """Behavior system configuration."""

    behavior_mappings: list[BehaviorMapping] = Field(default_factory=list)
    modifier_mappings: list[ModifierMapping] = Field(default_factory=list)
    magic_layer_command: str = Field(default="&magic LAYER_Magic 0")
    reset_behavior_alias: str = Field(default="&sys_reset")
