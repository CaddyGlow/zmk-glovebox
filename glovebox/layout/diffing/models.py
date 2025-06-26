"""Pydantic models for layout diff and patch operations."""

from datetime import datetime
from typing import Any

from pydantic import Field

from glovebox.models.base import GloveboxBaseModel


class BehaviorChanges(GloveboxBaseModel):
    """Changes for behavior lists (hold_taps, combos, macros, input_listeners, layers)."""

    added: list[dict[str, Any]] = Field(default_factory=list)
    removed: list[dict[str, Any]] = Field(default_factory=list)  # Only name, data=[]
    modified: list[dict[str, Any]] = Field(default_factory=list)  # {name: jsonpatch}


class LayoutDiff(GloveboxBaseModel):
    """Complete layout diff with all fields."""

    # Diff metadata (always present)
    base_version: str
    modified_version: str
    base_uuid: str
    modified_uuid: str
    timestamp: datetime
    diff_type: str = "layout_diff_v2"

    # Structured changes for lists
    layers: BehaviorChanges
    hold_taps: BehaviorChanges = Field(alias="holdTaps")
    combos: BehaviorChanges
    macros: BehaviorChanges
    input_listeners: BehaviorChanges = Field(alias="inputListeners")

    # Simple fields (JSON patch when changed, None when unchanged)
    keyboard: list[dict[str, Any]] | None = None
    title: list[dict[str, Any]] | None = None
    firmware_api_version: list[dict[str, Any]] | None = Field(
        None, alias="firmware_api_version"
    )
    locale: list[dict[str, Any]] | None = None
    uuid: list[dict[str, Any]] | None = None
    parent_uuid: list[dict[str, Any]] | None = Field(None, alias="parent_uuid")
    date: list[dict[str, Any]] | None = None
    creator: list[dict[str, Any]] | None = None
    notes: list[dict[str, Any]] | None = None
    tags: list[dict[str, Any]] | None = None
    variables: list[dict[str, Any]] | None = None
    config_parameters: list[dict[str, Any]] | None = Field(
        None, alias="config_parameters"
    )
    version: list[dict[str, Any]] | None = None
    base_version_patch: list[dict[str, Any]] | None = Field(
        None, alias="base_version_changes"
    )
    base_layout: list[dict[str, Any]] | None = Field(None, alias="base_layout")
    layer_names: list[dict[str, Any]] | None = Field(None, alias="layer_names")
    last_firmware_build: list[dict[str, Any]] | None = Field(
        None, alias="last_firmware_build"
    )

    # DTSI fields (unified diff strings, only included with flag)
    custom_defined_behaviors: str | None = Field(None, alias="custom_defined_behaviors")
    custom_devicetree: str | None = Field(None, alias="custom_devicetree")
