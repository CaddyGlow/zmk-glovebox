"""Display configuration models."""

from pydantic import ConfigDict, Field, field_validator

from glovebox.models.base import GloveboxBaseModel


class LayoutStructure(GloveboxBaseModel):
    """Physical layout structure for display."""

    rows: dict[str, list[list[int]]] = Field(
        description="Row-wise key position mapping"
    )

    @field_validator("rows")
    @classmethod
    def validate_row_structure(
        cls, v: dict[str, list[list[int]]]
    ) -> dict[str, list[list[int]]]:
        """Validate row structure contains valid key positions."""
        if not v:
            raise ValueError("Row structure cannot be empty")

        # Validate that all values are lists of lists of integers
        for row_name, row_data in v.items():
            if not isinstance(row_data, list):
                raise ValueError(f"Row '{row_name}' must be a list")
            for i, segment in enumerate(row_data):
                if not isinstance(segment, list):
                    raise ValueError(f"Row '{row_name}' segment {i} must be a list")
                for j, key_pos in enumerate(segment):
                    if not isinstance(key_pos, int) or key_pos < 0:
                        raise ValueError(
                            f"Row '{row_name}' segment {i} position {j} must be a non-negative integer"
                        )

        return v


class DisplayFormatting(GloveboxBaseModel):
    """Display formatting configuration."""

    # Override model config to preserve whitespace for display formatting fields
    model_config = ConfigDict(
        extra="allow",
        str_strip_whitespace=False,  # Don't strip whitespace for display formatting fields
        use_enum_values=True,
        validate_assignment=True,
    )

    header_width: int = Field(default=80, gt=0)
    none_display: str = Field(default="&none")
    trans_display: str = Field(default="▽")
    key_width: int = Field(default=8, gt=0)
    center_small_rows: bool = Field(default=True)
    horizontal_spacer: str = Field(default=" | ")


class DisplayConfig(GloveboxBaseModel):
    """Complete display configuration."""

    layout_structure: LayoutStructure | None = None
    formatting: DisplayFormatting = Field(default_factory=DisplayFormatting)
