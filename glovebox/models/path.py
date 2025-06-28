"""
Custom path field types that preserve original notation while providing resolved paths.

This module provides Pydantic field types that:
1. Store the original path string with variables/tildes
2. Behave exactly like Path objects for all operations
3. Serialize back to the original notation to preserve user intent
"""

import os
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

from pydantic import BeforeValidator, Field, field_serializer, field_validator
from pydantic_core import core_schema

from glovebox.models.base import GloveboxBaseModel


class PreservingPath(Path):
    """
    A Path subclass that preserves original notation while providing full Path functionality.

    This class behaves exactly like a Path object for all operations but stores the
    original path string (with variables/tildes) for serialization back to config files.
    """

    _original: str
    _resolved_str: str

    def __new__(
        cls, original: str, _resolved_path: Path | None = None
    ) -> "PreservingPath":
        """
        Create a new PreservingPath instance.

        Args:
            original: The original path string (may contain variables/tildes)
            _resolved_path: Internal parameter for from_path method
        """
        if _resolved_path is None:
            # Normal case: resolve from original string
            expanded = cls._expand_with_fallbacks(original)
            resolved_path = Path(expanded).resolve()
        else:
            # Special case: use provided resolved path (from from_path method)
            resolved_path = _resolved_path

        # Create the Path instance with the resolved path
        instance = super().__new__(cls, str(resolved_path))

        # Store the original notation as an instance attribute
        instance._original = original
        instance._resolved_str = str(resolved_path)

        return instance

    @classmethod
    def _expand_with_fallbacks(cls, path_str: str) -> str:
        """
        Expand environment variables with intelligent fallbacks.

        Handles common XDG variables and provides sensible defaults when they're missing.
        """
        xdg_fallbacks = {
            "$XDG_CACHE_HOME": "~/.cache",
            "$XDG_CONFIG_HOME": "~/.config",
            "$XDG_DATA_HOME": "~/.local/share",
        }

        for xdg_var, fallback in xdg_fallbacks.items():
            if xdg_var in path_str:
                env_value = os.environ.get(xdg_var[1:])  # Remove the $ prefix
                path_str = path_str.replace(xdg_var, env_value or fallback)

        # Expand any remaining environment variables and user home
        return os.path.expandvars(str(Path(path_str).expanduser()))

    @property
    def original(self) -> str:
        """Get the original path string with variables/tildes."""
        return self._original

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return f"PreservingPath('{self.original}')"

    def __str__(self) -> str:
        """Return the string representation of the resolved path."""
        # Use the stored resolved string
        return self._resolved_str

    @classmethod
    def from_path(
        cls, path: Path | str, original: str | None = None
    ) -> "PreservingPath":
        """Create a PreservingPath from an existing Path with optional original notation."""
        if original is None:
            original = str(path)
        # Use the provided path as the resolved path
        resolved = Path(path).resolve()
        return cls(original, resolved)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: Callable[[Any], core_schema.CoreSchema]
    ) -> core_schema.CoreSchema:
        """Get Pydantic core schema for PreservingPath."""
        # Accept PreservingPath, str, or Path as input
        from_str_schema = core_schema.chain_schema(
            [
                core_schema.str_schema(),
                core_schema.no_info_plain_validator_function(lambda v: cls(v)),
            ]
        )
        from_path_schema = core_schema.chain_schema(
            [
                core_schema.is_instance_schema(Path),
                core_schema.no_info_plain_validator_function(lambda v: cls(str(v))),
            ]
        )
        from_self_schema = core_schema.is_instance_schema(cls)

        return core_schema.union_schema(
            [
                from_self_schema,
                from_str_schema,
                from_path_schema,
            ]
        )


class PathField:
    """
    Factory for creating path fields that preserve original notation.

    Usage:
        file_path: PreservingPath | None = PathField(default=None, description="Log file path")
    """

    def __new__(cls, default: Any = None, description: str = "", **kwargs: Any) -> Any:
        """Create a Pydantic field with path preservation validators and serializers."""

        # Create the field with the validators
        field_kwargs = {"default": default, "description": description, **kwargs}

        return Field(**field_kwargs)


# Convenience function for creating path fields
def path_field(default: Any = None, description: str = "", **kwargs: Any) -> Any:
    """
    Create a path field that preserves original notation.

    Args:
        default: Default value for the field
        description: Field description
        **kwargs: Additional field arguments

    Returns:
        A Pydantic field with path preservation
    """
    return PathField(default=default, description=description, **kwargs)


# Type alias for annotated PreservingPath fields
def _validate_preserving_path(value: Any) -> PreservingPath:
    """Validator function for PreservingPath fields."""
    if isinstance(value, PreservingPath):
        return value
    if isinstance(value, str | Path):
        return PreservingPath(str(value))
    raise ValueError(f"Invalid type for PreservingPath: {type(value)}")


# Annotated type that automatically handles validation
PreservingPathField = Annotated[
    PreservingPath, BeforeValidator(_validate_preserving_path)
]
