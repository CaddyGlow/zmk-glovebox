"""Layout models for keyboard layouts."""

from datetime import datetime
from typing import Any, Literal, TypeAlias, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)


# Type aliases for common parameter types
ParamValue: TypeAlias = str | int
ConfigValue: TypeAlias = str | int | bool
LayerIndex: TypeAlias = int
#
# This type alias improves type safety and makes future changes easier
LayerBindings: TypeAlias = list["LayoutBinding"]
# Type alias for collections of behaviors
BehaviorList: TypeAlias = list[
    Union["HoldTapBehavior", "ComboBehavior", "MacroBehavior", "InputListener"]
]
# Type alias for configuration parameters
ConfigParamList: TypeAlias = list["ConfigParameter"]


class LayoutParam(BaseModel):
    """Model for parameter values in key bindings."""

    model_config = ConfigDict(extra="allow")

    value: ParamValue
    params: list["LayoutParam"] = Field(default_factory=list)


# Recursive type reference for LayoutParam
LayoutParam.model_rebuild()


class LayoutBinding(BaseModel):
    """Model for individual key bindings."""

    model_config = ConfigDict(extra="allow")

    value: str
    params: list[LayoutParam] = Field(default_factory=list)

    @property
    def behavior(self) -> str:
        """Get the behavior code."""
        return self.value


class LayoutLayer(BaseModel):
    """Model for keyboard layers."""

    model_config = ConfigDict(extra="allow")

    name: str
    bindings: list[LayoutBinding]

    @field_validator("bindings")
    @classmethod
    def validate_bindings_count(cls, v: list[LayoutBinding]) -> list[LayoutBinding]:
        """Validate that layer has expected number of bindings."""
        if len(v) != 80:  # Glove80 specific
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Layer has {len(v)} bindings, expected 80")
        return v


class HoldTapBehavior(BaseModel):
    """Model for hold-tap behavior definitions."""

    model_config = ConfigDict(extra="allow")

    name: str
    description: str | None = ""
    bindings: list[LayoutBinding] = Field(default_factory=list)
    tapping_term_ms: int | None = Field(default=None, alias="tappingTermMs")
    quick_tap_ms: int | None = Field(default=None, alias="quickTapMs")
    flavor: str | None = None
    hold_trigger_on_release: bool | None = Field(
        default=None, alias="holdTriggerOnRelease"
    )
    require_prior_idle_ms: int | None = Field(default=None, alias="requirePriorIdleMs")
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
    def validate_bindings_count(cls, v: list[LayoutBinding]) -> list[LayoutBinding]:
        """Validate that hold-tap has exactly 2 bindings."""
        if len(v) != 2:
            raise ValueError(
                f"Hold-tap behavior requires exactly 2 bindings, found {len(v)}"
            ) from None
        return v


class ComboBehavior(BaseModel):
    """Model for combo definitions."""

    model_config = ConfigDict(extra="allow")

    name: str
    description: str | None = ""
    timeout_ms: int | None = Field(default=None, alias="timeoutMs")
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


class MacroBehavior(BaseModel):
    """Model for macro definitions."""

    model_config = ConfigDict(extra="allow")

    name: str
    description: str | None = ""
    wait_ms: int | None = Field(default=None, alias="waitMs")
    tap_ms: int | None = Field(default=None, alias="tapMs")
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


class ConfigParameter(BaseModel):
    """Model for configuration parameters."""

    model_config = ConfigDict(extra="allow")

    param_name: str = Field(alias="paramName")
    value: ConfigValue
    description: str | None = None


class InputProcessor(BaseModel):
    """Model for input processors."""

    model_config = ConfigDict(extra="allow")

    code: str
    params: list[ParamValue] = Field(default_factory=list)


class InputListenerNode(BaseModel):
    """Model for input listener nodes."""

    model_config = ConfigDict(extra="allow")

    code: str
    description: str | None = ""
    layers: list[LayerIndex] = Field(default_factory=list)
    input_processors: list[InputProcessor] = Field(
        default_factory=list, alias="inputProcessors"
    )


class InputListener(BaseModel):
    """Model for input listeners."""

    model_config = ConfigDict(extra="allow")

    code: str
    input_processors: list[InputProcessor] = Field(
        default_factory=list, alias="inputProcessors"
    )
    nodes: list[InputListenerNode] = Field(default_factory=list)


class LayoutMetadata(BaseModel):
    """Pydantic model for layout metadata fields."""

    model_config = ConfigDict(extra="allow")

    # Required fields
    keyboard: str
    title: str

    # Optional metadata
    firmware_api_version: str = Field(default="1", alias="firmware_api_version")
    locale: str = Field(default="en-US")
    uuid: str = Field(default="")
    parent_uuid: str = Field(default="", alias="parent_uuid")
    date: datetime = Field(default_factory=datetime.now)
    creator: str = Field(default="")
    notes: str = Field(default="")
    tags: list[str] = Field(default_factory=list)


class LayoutData(LayoutMetadata):
    """Complete layout data model with Pydantic v2."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    # Essential structure fields
    layers: list[LayerBindings] = Field(default_factory=list)
    layer_names: list[str] = Field(default_factory=list, alias="layer_names")

    # Behavior definitions
    hold_taps: list[HoldTapBehavior] = Field(default_factory=list, alias="holdTaps")
    combos: list[ComboBehavior] = Field(default_factory=list)
    macros: list[MacroBehavior] = Field(default_factory=list)
    input_listeners: list[InputListener] = Field(
        default_factory=list, alias="inputListeners"
    )

    # Configuration
    config_parameters: ConfigParamList = Field(
        default_factory=list, alias="config_parameters"
    )

    # Custom code
    custom_defined_behaviors: str = Field(default="", alias="custom_defined_behaviors")
    custom_devicetree: str = Field(default="", alias="custom_devicetree")

    @field_validator("layers")
    @classmethod
    def validate_layers_structure(cls, v: list[LayerBindings]) -> list[LayerBindings]:
        """Validate layers structure."""
        if not v:
            raise ValueError("Layout must have at least one layer") from None

        for i, layer in enumerate(v):
            if not isinstance(layer, list):
                raise ValueError(f"Layer {i} must be a list of bindings") from None

            # Validate each binding in the layer
            for j, binding in enumerate(layer):
                if not isinstance(binding, LayoutBinding):
                    raise ValueError(
                        f"Layer {i}, binding {j} must be a LayoutBinding"
                    ) from None
                if not binding.value:
                    raise ValueError(
                        f"Layer {i}, binding {j} missing 'value' field"
                    ) from None

        return v

    @model_validator(mode="after")
    def validate_layer_consistency(self) -> "LayoutData":
        """Validate consistency between layer names and layer data."""
        if len(self.layers) != len(self.layer_names):
            raise ValueError(
                f"Number of layers ({len(self.layers)}) must match "
                f"number of layer names ({len(self.layer_names)})"
            ) from None
        return self

    def get_structured_layers(self) -> list[LayoutLayer]:
        """Create LayoutLayer objects from typed layer data."""
        structured_layers = []

        for layer_name, layer_bindings in zip(
            self.layer_names, self.layers, strict=False
        ):
            # Create LayoutLayer directly from properly typed bindings
            layer = LayoutLayer(name=layer_name, bindings=layer_bindings)
            structured_layers.append(layer)

        return structured_layers

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with proper field names."""
        return self.model_dump(by_alias=True, exclude_unset=True)
