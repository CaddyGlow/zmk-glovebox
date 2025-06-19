"""Base model for all Glovebox Pydantic models.

This module provides a base model class that enforces consistent serialization
behavior across all Glovebox models.
"""

from typing import Any

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
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary with consistent serialization parameters.

        Returns:
            Dictionary representation using JSON-compatible serialization
        """
        return self.model_dump(by_alias=True, exclude_unset=True, mode="json")

    def to_dict_full(self) -> dict[str, Any]:
        """Convert model to dictionary including all fields (even unset ones).

        Returns:
            Dictionary representation including all fields
        """
        return self.model_dump(by_alias=True, exclude_unset=False, mode="json")

    def to_dict_python(self) -> dict[str, Any]:
        """Convert model to dictionary using Python serialization.

        Returns:
            Dictionary representation using Python types (e.g., datetime objects)
        """
        return self.model_dump(by_alias=True, exclude_unset=True, mode="python")
