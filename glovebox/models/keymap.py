"""Keymap models for Glove80 keyboard."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class KeymapBinding(BaseModel):
    """Model for individual key bindings."""

    model_config = ConfigDict(extra="allow")

    value: str
    params: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def behavior(self) -> str:
        """Get the behavior code."""
        return self.value


class KeymapLayer(BaseModel):
    """Model for keyboard layers."""

    model_config = ConfigDict(extra="allow")

    name: str
    bindings: list[KeymapBinding]

    @field_validator("bindings")
    @classmethod
    def validate_bindings_count(cls, v: list[KeymapBinding]) -> list[KeymapBinding]:
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
    bindings: list[KeymapBinding] = Field(default_factory=list)
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
    def validate_bindings_count(cls, v: list[KeymapBinding]) -> list[KeymapBinding]:
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
    layers: list[int] | None = None
    binding: list[KeymapBinding] = Field(default_factory=list)
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
    bindings: list[KeymapBinding] = Field(default_factory=list)
    params: list[Any] | None = None

    @field_validator("params")
    @classmethod
    def validate_params_count(cls, v: list[Any] | None) -> list[Any] | None:
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
    value: Any
    description: str | None = None


class InputProcessor(BaseModel):
    """Model for input processors."""

    model_config = ConfigDict(extra="allow")

    code: str
    params: list[Any] = Field(default_factory=list)


class InputListenerNode(BaseModel):
    """Model for input listener nodes."""

    model_config = ConfigDict(extra="allow")

    code: str
    description: str | None = ""
    layers: list[int] = Field(default_factory=list)
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


class KeymapData(BaseModel):
    """Complete keymap data model with Pydantic v2."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    # Required fields
    keyboard: str
    title: str
    layer_names: list[str] = Field(alias="layer_names")
    # TODO: Type it here to avoid to do it below
    layers: list[list[dict[str, Any]]]  # Raw layer data, will be processed

    # Optional metadata
    firmware_api_version: str = Field(default="1", alias="firmware_api_version")
    locale: str = Field(default="en-US")
    uuid: str = Field(default="")
    parent_uuid: str = Field(default="", alias="parent_uuid")
    date: datetime | int | str = Field(default_factory=datetime.now)
    creator: str = Field(default="")
    notes: str = Field(default="")
    tags: list[str] = Field(default_factory=list)

    # Behavior definitions
    hold_taps: list[HoldTapBehavior] = Field(default_factory=list, alias="holdTaps")
    combos: list[ComboBehavior] = Field(default_factory=list)
    macros: list[MacroBehavior] = Field(default_factory=list)
    input_listeners: list[InputListener] = Field(
        default_factory=list, alias="inputListeners"
    )

    # Configuration
    config_parameters: list[ConfigParameter] = Field(
        default_factory=list, alias="config_parameters"
    )
    kconfig: dict[str, Any] = Field(default_factory=dict)

    # Custom code
    custom_defined_behaviors: str = Field(default="", alias="custom_defined_behaviors")
    custom_devicetree: str = Field(default="", alias="custom_devicetree")

    @field_validator("date", mode="before")
    @classmethod
    def parse_date(cls, v: datetime | int | str) -> datetime:
        """Parse date from various formats."""
        import logging

        logger = logging.getLogger(__name__)

        if isinstance(v, datetime):
            return v
        elif isinstance(v, int):
            # Assume Unix timestamp
            return datetime.fromtimestamp(v)
        elif isinstance(v, str):
            try:
                # Try ISO format first
                return datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                try:
                    # Try Unix timestamp as string
                    return datetime.fromtimestamp(float(v))
                except (ValueError, TypeError):
                    logger.warning(f"Could not parse date '{v}', using current time")
                    return datetime.now()
        else:
            return datetime.now()

    @field_validator("layers")
    @classmethod
    def validate_layers_structure(
        cls, v: list[list[dict[str, Any]]]
    ) -> list[list[dict[str, Any]]]:
        """Validate layers structure."""
        if not v:
            raise ValueError("Keymap must have at least one layer") from None

        for i, layer in enumerate(v):
            if not isinstance(layer, list):
                raise ValueError(f"Layer {i} must be a list of bindings") from None

            # Validate each binding in the layer
            for j, binding in enumerate(layer):
                if not isinstance(binding, dict):
                    raise ValueError(
                        f"Layer {i}, binding {j} must be a dictionary"
                    ) from None
                if "value" not in binding:
                    raise ValueError(
                        f"Layer {i}, binding {j} missing 'value' field"
                    ) from None

        return v

    @model_validator(mode="after")
    def validate_layer_consistency(self) -> "KeymapData":
        """Validate consistency between layer names and layer data."""
        if len(self.layers) != len(self.layer_names):
            raise ValueError(
                f"Number of layers ({len(self.layers)}) must match "
                f"number of layer names ({len(self.layer_names)})"
            ) from None
        return self

    def get_structured_layers(self) -> list[KeymapLayer]:
        """Convert raw layer data to structured KeymapLayer objects."""
        import logging

        logger = logging.getLogger(__name__)

        structured_layers = []

        for i, (layer_name, layer_data) in enumerate(
            zip(self.layer_names, self.layers, strict=False)
        ):
            # Convert raw binding dicts to KeymapBinding objects
            bindings = []
            for binding_dict in layer_data:
                try:
                    binding = KeymapBinding.model_validate(binding_dict)
                    bindings.append(binding)
                except Exception as e:
                    logger.warning(
                        f"Invalid binding in layer {i}: {binding_dict}. Error: {e}"
                    )
                    # Create a fallback binding
                    bindings.append(KeymapBinding(value="&none", params=[]))

            layer = KeymapLayer(name=layer_name, bindings=bindings)
            structured_layers.append(layer)

        return structured_layers

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with proper field names."""
        return self.model_dump(by_alias=True, exclude_unset=True)
