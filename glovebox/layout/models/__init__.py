"""Layout models for keyboard layouts."""

from datetime import datetime
from pathlib import Path
from typing import Any, TypeAlias, Union

from pydantic import (
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_serializer,
    model_validator,
)

# Import behavior models that are now part of the layout domain
from glovebox.layout.behavior.models import (
    BehaviorCommand,
    BehaviorParameter,
    KeymapBehavior,
    ParameterType,
    ParamValue,
    SystemBehavior,
    SystemBehaviorParam,
    SystemParamList,
)
from glovebox.models.base import GloveboxBaseModel

from .bookmarks import BookmarkCollection, BookmarkSource, LayoutBookmark


# Type aliases for common parameter types
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


# TODO: rename to maybe KeyPararm to avoid confusion with LayoutParam
class LayoutParam(GloveboxBaseModel):
    """Model for parameter values in key bindings."""

    value: ParamValue
    params: list["LayoutParam"] = Field(default_factory=list)


# Recursive type reference for LayoutParam
LayoutParam.model_rebuild()


class LayoutBinding(GloveboxBaseModel):
    """Model for individual key bindings."""

    value: str
    params: list[LayoutParam] = Field(default_factory=list)

    @property
    def behavior(self) -> str:
        """Get the behavior code."""
        return self.value


class LayoutLayer(GloveboxBaseModel):
    """Model for keyboard layers."""

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


class HoldTapBehavior(GloveboxBaseModel):
    """Model for hold-tap behavior definitions."""

    name: str
    description: str | None = ""
    bindings: list[str] = Field(default_factory=list)
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

    @field_validator("bindings", mode="before")
    @classmethod
    def convert_legacy_bindings(cls, v: Any) -> Any:
        """Convert legacy LayoutBinding objects to strings for backward compatibility.

        This handles JSON data that still uses the old format:
        bindings: [{"value": "&kp", "params": []}, {"value": "&lt", "params": []}]

        And converts it to the new format:
        bindings: ["&kp", "&lt"]
        """
        if isinstance(v, list):
            result = []
            for item in v:
                if isinstance(item, str):
                    # Already a string, keep as-is
                    result.append(item)
                elif isinstance(item, dict) and "value" in item:
                    # Legacy LayoutBinding dict format, extract value
                    result.append(item["value"])
                elif hasattr(item, "value"):
                    # Legacy LayoutBinding object, extract value
                    result.append(item.value)
                else:
                    # Unknown format, try to convert to string
                    result.append(str(item))
            return result
        return v

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


class MacroBehavior(GloveboxBaseModel):
    """Model for macro definitions."""

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


class ConfigParameter(GloveboxBaseModel):
    """Model for configuration parameters."""

    param_name: str = Field(alias="paramName")
    value: ConfigValue
    description: str | None = None


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


class InputListener(GloveboxBaseModel):
    """Model for input listeners."""

    code: str
    input_processors: list[InputProcessor] = Field(
        default_factory=list, alias="inputProcessors"
    )
    nodes: list[InputListenerNode] = Field(default_factory=list)


class LayoutMetadata(GloveboxBaseModel):
    """Pydantic model for layout metadata fields."""

    # Required fields
    keyboard: str
    title: str

    # Optional metadata
    firmware_api_version: str = Field(default="1", alias="firmware_api_version")
    locale: str = Field(default="en-US")
    uuid: str = Field(default="")
    parent_uuid: str = Field(default="", alias="parent_uuid")
    date: datetime = Field(default_factory=datetime.now)

    @field_serializer("date", when_used="json")
    def serialize_date(self, dt: datetime) -> int:
        """Serialize date to Unix timestamp for JSON."""
        return int(dt.timestamp())

    creator: str = Field(default="")
    notes: str = Field(default="")
    tags: list[str] = Field(default_factory=list)

    # layers order and name
    layer_names: list[str] = Field(default_factory=list, alias="layer_names")

    # User behavior definitions
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

    # Version tracking (new)
    version: str = Field(default="1.0.0")
    base_version: str = Field(default="")  # Master version this is based on
    base_layout: str = Field(default="")  # e.g., "glorious-engrammer"

    # Firmware tracking (new)
    last_firmware_build: dict[str, Any] = Field(default_factory=dict)
    # Structure: {
    #     "date": "2024-01-15T10:30:00Z",
    #     "profile": "glove80/v25.05",
    #     "firmware_path": "firmware/my-layout-v42.uf2",
    #     "firmware_hash": "sha256:abc123...",
    #     "build_id": "8984a4e0-v25.05-598b0350"
    # }


class LayoutData(LayoutMetadata):
    """Complete layout data model with Pydantic v2."""

    # LayoutData doesn't need to override model_config since it inherits from GloveboxBaseModel

    # Essential structure fields
    layers: list[LayerBindings] = Field(default_factory=list)

    # Custom code
    custom_defined_behaviors: str = Field(default="", alias="custom_defined_behaviors")
    custom_devicetree: str = Field(default="", alias="custom_devicetree")

    @model_serializer(mode="wrap")
    def serialize_with_sorted_fields(
        self, serializer: Any, info: Any
    ) -> dict[str, Any]:
        """Serialize with fields in a specific order."""
        data = serializer(self)

        # Define the desired field order
        field_order = [
            "keyboard",
            "firmware_api_version",
            "locale",
            "uuid",
            "parent_uuid",
            "date",
            "creator",
            "title",
            "notes",
            "tags",
            # Added fields for the layout master feature
            "version",
            "base_version",
            "base_layout",
            "last_firmware_build",
            # Normal layout structure
            "layer_names",
            "config_parameters",
            "holdTaps",
            "combos",
            "macros",
            "inputListeners",
            "layers",
            "custom_defined_behaviors",
            "custom_devicetree",
        ]

        # Create ordered dict with known fields first
        ordered_data = {}
        for field in field_order:
            if field in data:
                ordered_data[field] = data[field]

        # Add any remaining fields not in the order list
        for key, value in data.items():
            if key not in ordered_data:
                ordered_data[key] = value

        return ordered_data

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

    # We should check that layer_name have a matching layer in the folder=
    # @model_validator(mode="after")
    # def validate_layer_consistency(self) -> "LayoutData":
    #     """Validate consistency between layer names and layer data."""
    #     if len(self.layers) != len(self.layer_names):
    #         raise ValueError(
    #             f"Number of layers ({len(self.layers)}) must match "
    #             f"number of layer names ({len(self.layer_names)})"
    #         ) from None
    #     return self

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
        """Convert to dictionary with proper field names and JSON serialization."""
        return self.model_dump(mode="json", by_alias=True, exclude_unset=True)


# Layout result models
class KeymapResult(GloveboxBaseModel):
    """Result of keymap operations."""

    success: bool
    timestamp: datetime = Field(default_factory=datetime.now)
    messages: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    @field_serializer("timestamp", when_used="json")
    def serialize_timestamp(self, dt: datetime) -> int:
        """Serialize timestamp to Unix timestamp for JSON."""
        return int(dt.timestamp())

    keymap_path: Path | None = None
    conf_path: Path | None = None
    json_path: Path | None = None
    profile_name: str | None = None
    layer_count: int | None = None

    def add_message(self, message: str) -> None:
        """Add an informational message."""
        if not isinstance(message, str):
            raise ValueError("Message must be a string") from None
        self.messages.append(message)

    def add_error(self, error: str) -> None:
        """Add an error message."""
        if not isinstance(error, str):
            raise ValueError("Error must be a string") from None
        self.errors.append(error)
        self.success = False


class LayoutResult(GloveboxBaseModel):
    """Result of layout operations."""

    success: bool
    timestamp: datetime = Field(default_factory=datetime.now)
    messages: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    @field_serializer("timestamp", when_used="json")
    def serialize_timestamp(self, dt: datetime) -> int:
        """Serialize timestamp to Unix timestamp for JSON."""
        return int(dt.timestamp())

    keymap_path: Path | None = None
    conf_path: Path | None = None
    json_path: Path | None = None
    profile_name: str | None = None
    layer_count: int | None = None

    @field_validator("keymap_path", "conf_path", "json_path")
    @classmethod
    def validate_paths(cls, v: Any) -> Path | None:
        """Validate that paths are Path objects if provided."""
        if v is None:
            return None
        if isinstance(v, Path):
            return v
        if isinstance(v, str):
            return Path(v)
        # If we get here, v is neither None, Path, nor str
        raise ValueError("Paths must be Path objects or strings") from None

    @field_validator("layer_count")
    @classmethod
    def validate_layer_count(cls, v: int | None) -> int | None:
        """Validate layer count is positive if provided."""
        if v is not None and (not isinstance(v, int) or v < 0):
            raise ValueError("Layer count must be a non-negative integer") from None
        return v

    def add_message(self, message: str) -> None:
        """Add an informational message."""
        if not isinstance(message, str):
            raise ValueError("Message must be a string") from None
        self.messages.append(message)

    def add_error(self, error: str) -> None:
        """Add an error message."""
        if not isinstance(error, str):
            raise ValueError("Error must be a string") from None
        self.errors.append(error)
        self.success = False

    def get_output_files(self) -> dict[str, Path]:
        """Get dictionary of output file types to paths."""
        files = {}
        if self.keymap_path:
            files["keymap"] = self.keymap_path
        if self.conf_path:
            files["conf"] = self.conf_path
        if self.json_path:
            files["json"] = self.json_path
        return files

    def validate_output_files_exist(self) -> bool:
        """Check if all output files actually exist on disk."""
        files = self.get_output_files()
        missing_files = []

        for file_type, file_path in files.items():
            if not file_path.exists():
                missing_files.append(f"{file_type}: {file_path}")

        if missing_files:
            self.add_error(f"Output files missing: {', '.join(missing_files)}")
            return False

        return True


# Re-export all models for external use
__all__ = [
    # Type aliases
    "ConfigValue",
    "LayerIndex",
    "LayerBindings",
    "BehaviorList",
    "ConfigParamList",
    # Layout models
    "LayoutParam",
    "LayoutBinding",
    "LayoutLayer",
    "LayoutData",
    "LayoutMetadata",
    # Behavior models
    "HoldTapBehavior",
    "ComboBehavior",
    "MacroBehavior",
    "InputProcessor",
    "InputListenerNode",
    "InputListener",
    "ConfigParameter",
    # Re-exported behavior models from behavior_models
    "BehaviorCommand",
    "BehaviorParameter",
    "KeymapBehavior",
    "ParameterType",
    "ParamValue",
    "SystemBehavior",
    "SystemBehaviorParam",
    "SystemParamList",
    # Result models
    "KeymapResult",
    "LayoutResult",
    # Bookmark models
    "LayoutBookmark",
    "BookmarkCollection",
    "BookmarkSource",
]
