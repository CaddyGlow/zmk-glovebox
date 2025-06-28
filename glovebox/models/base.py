"""Base model for all Glovebox Pydantic models.

This module provides a base model class that enforces consistent serialization
behavior across all Glovebox models.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class GloveboxBaseModel(BaseModel):
    """Base model class for all Glovebox Pydantic models.

    This class enforces consistent serialization behavior:
    - by_alias=True: Use field aliases for serialization
    - exclude_unset=True: Exclude fields that weren't explicitly set
    - mode="json": Use JSON-compatible serialization (e.g., datetime -> timestamp)
    """

    model_config = ConfigDict(
        # Allow extra fields for flexibility
        extra="allow",
        # Strip whitespace from string fields
        str_strip_whitespace=True,
        # Use enum values in serialization
        use_enum_values=True,
        # Validate assignment after model creation
        validate_assignment=True,
        # allow to load with alias and name
        validate_by_alias=True,
        validate_by_name=True,
    )

    def model_dump(
        self,
        *,
        mode: Literal["json", "python"] | str = "json",
        by_alias: bool | None = True,
        exclude_unset: bool = True,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Override model_dump to default to using aliases.
        """
        # We explicitly set by_alias=True as the default for this method's signature.
        return super().model_dump(
            mode=mode, by_alias=by_alias, exclude_unset=exclude_unset, **kwargs
        )

    def model_dump_json(
        self, *, by_alias: bool | None = True, exclude_unset: bool = True, **kwargs
    ) -> str:
        """
        Override model_dump_json to default to using aliases.
        """
        return super().model_dump_json(
            by_alias=by_alias, exclude_unset=exclude_unset, **kwargs
        )

    def to_dict(self, exclude_unset: bool = True) -> dict[str, Any]:
        """Convert model to dictionary with consistent serialization parameters.

        Returns:
            Dictionary representation using JSON-compatible serialization
        """
        return self.model_dump(by_alias=True, exclude_unset=exclude_unset, mode="json")

    def to_dict_python(self) -> dict[str, Any]:
        """Convert model to dictionary using Python serialization.

        Returns:
            Dictionary representation using Python types (e.g., datetime objects)
        """
        return self.model_dump(by_alias=True, exclude_unset=True, mode="python")
