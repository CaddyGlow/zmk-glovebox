"""Layout metadata and data models."""

from datetime import datetime
from typing import Any

from pydantic import (
    Field,
    field_serializer,
    field_validator,
    model_serializer,
    model_validator,
)

from glovebox.models.base import GloveboxBaseModel

from .behaviors import (
    ComboBehavior,
    HoldTapBehavior,
    InputListener,
    MacroBehavior,
)
from .config import ConfigParameter
from .core import LayoutBinding, LayoutLayer
from .keymap import KeymapMetadata
from .types import ConfigParamList, LayerBindings


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

    # Variables for substitution
    variables: dict[str, Any] = Field(
        default_factory=dict,
        description="Global variables for substitution using ${variable_name} syntax",
    )

    # Configuration
    config_parameters: ConfigParamList = Field(
        default_factory=list, alias="config_parameters"
    )

    # Version tracking (new)
    version: str = Field(default="1.0.0")
    base_version: str = Field(default="")  # Master version this is based on
    base_layout: str = Field(default="")  # e.g., "glorious-engrammer"

    layer_names: list[str] = Field(default_factory=list, alias="layer_names")

    # Enhanced metadata for ZMK keymap reconstruction (Phase 4.1)
    keymap_metadata: KeymapMetadata = Field(
        default_factory=KeymapMetadata,
        alias="keymapMetadata",
        description="Enhanced metadata for ZMK keymap round-trip preservation",
    )


class LayoutData(LayoutMetadata):
    """Complete layout data model following Moergo API field names with aliases."""

    # User behavior definitions
    hold_taps: list[HoldTapBehavior] = Field(default_factory=list, alias="holdTaps")
    combos: list[ComboBehavior] = Field(default_factory=list)
    macros: list[MacroBehavior] = Field(default_factory=list)
    input_listeners: list[InputListener] = Field(
        default_factory=list, alias="inputListeners"
    )

    # Essential structure fields
    layers: list[LayerBindings] = Field(default_factory=list)

    # Custom code
    custom_defined_behaviors: str = Field(default="", alias="custom_defined_behaviors")
    custom_devicetree: str = Field(default="", alias="custom_devicetree")

    @model_validator(mode="before")
    @classmethod
    def validate_data_structure(cls, data: Any, info: Any = None) -> Any:
        """Basic validation without template processing.

        This only handles basic data structure validation like date conversion.
        Template processing is handled separately by process_templates().
        """
        if not isinstance(data, dict):
            return data

        # Convert integer timestamps to datetime objects for date fields
        if "date" in data and isinstance(data["date"], int):
            from datetime import datetime

            data["date"] = datetime.fromtimestamp(data["date"])

        return data

    def process_templates(self) -> "LayoutData":
        """Process all Jinja2 templates in the layout data.

        This is a separate method that can be called explicitly when needed,
        instead of being part of model validation.

        Returns:
            New LayoutData instance with resolved templates
        """
        # Skip processing if no variables or templates present
        if not self.variables and not self._has_template_syntax(self.model_dump()):
            return self

        from glovebox.layout.template_service import create_jinja2_template_service

        try:
            # Create template service and process the data
            template_service = create_jinja2_template_service()

            # Process templates and return new instance
            resolved_layout = template_service.process_layout_data(self)
            return resolved_layout

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.warning("Template resolution failed: %s", e, exc_info=exc_info)
            return self

    @classmethod
    def load_with_templates(cls, data: dict[str, Any]) -> "LayoutData":
        """Load layout data and process templates.

        This is the method to use when you want templates processed.
        """
        # First create the model without template processing
        layout = cls.model_validate(data)

        # Then process templates if not in skip context
        from glovebox.layout.utils.json_operations import (
            should_skip_variable_resolution,
        )

        if not should_skip_variable_resolution():
            layout = layout.process_templates()

        return layout

    @classmethod
    def _has_template_syntax(cls, data: dict[str, Any]) -> bool:
        """Check if data contains any Jinja2 template syntax."""
        import re

        def scan_for_templates(obj: Any) -> bool:
            if isinstance(obj, str):
                return bool(re.search(r"\{\{|\{%|\{#", obj))
            elif isinstance(obj, dict):
                return any(scan_for_templates(v) for v in obj.values())
            elif isinstance(obj, list):
                return any(scan_for_templates(item) for item in obj)
            return False

        return scan_for_templates(data)

    @model_serializer(mode="wrap")
    def serialize_with_sorted_fields(
        self, serializer: Any, info: Any
    ) -> dict[str, Any]:
        """Serialize with fields in a specific order."""
        data = serializer(self)

        # Define the desired field order
        # IMPORTANT: variables must be first for proper template resolution
        field_order = [
            "variables",
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
            # Enhanced metadata for full keymap reconstruction in layout parser
            "keymapMetadata",
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
        # Allow empty layers list during construction/processing
        if not v:
            return v

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

    def to_dict(self, exclude_unset: bool = True) -> dict[str, Any]:
        """Convert to dictionary with proper field names and JSON serialization."""
        return self.model_dump(mode="json", by_alias=True, exclude_unset=exclude_unset)

    def to_flattened_dict(self) -> dict[str, Any]:
        """Export layout with templates resolved and variables section removed.

        Returns:
            Dictionary representation with all templates resolved and variables section removed
        """
        # Get the original dict representation
        data = self.model_dump(mode="json", by_alias=True, exclude_unset=True)

        # If we have variables or templates, resolve and remove variables section
        if data.get("variables") or self._has_template_syntax(data):
            try:
                # Process templates on a copy
                resolved_layout = self.process_templates()
                resolved_data = resolved_layout.model_dump(
                    mode="json", by_alias=True, exclude_unset=True
                )

                # Remove variables section from output
                return {k: v for k, v in resolved_data.items() if k != "variables"}

            except Exception as e:
                # Fall back to removing variables section only
                import logging

                logger = logging.getLogger(__name__)
                exc_info = logger.isEnabledFor(logging.DEBUG)
                logger.warning(
                    "Template resolution failed in to_flattened_dict: %s",
                    e,
                    exc_info=exc_info,
                )
                return {k: v for k, v in data.items() if k != "variables"}

        # No variables or templates to resolve, just return without variables section
        return {k: v for k, v in data.items() if k != "variables"}
