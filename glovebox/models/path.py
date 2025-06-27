"""
Custom path field types that preserve original notation while providing resolved paths.

This module provides Pydantic field types that:
1. Store the original path string with variables/tildes
2. Behave exactly like Path objects for all operations
3. Serialize back to the original notation to preserve user intent
"""

import os
from pathlib import Path
from typing import Any, Callable

from pydantic import Field, field_serializer, field_validator
from pydantic_core import core_schema

from glovebox.models.base import GloveboxBaseModel


class PreservingPath(Path):
    """
    A Path subclass that preserves original notation while providing full Path functionality.

    This class behaves exactly like a Path object for all operations but stores the
    original path string (with variables/tildes) for serialization back to config files.
    """
    
    _original: str

    def __new__(cls, original: str):
        """
        Create a new PreservingPath instance.

        Args:
            original: The original path string (may contain variables/tildes)
        """
        # Expand environment variables and user home directory for Path operations
        expanded = cls._expand_with_fallbacks(original)
        resolved_path = Path(expanded).resolve()
        
        # Create the Path instance with the resolved path
        instance = super().__new__(cls, str(resolved_path))
        
        # Store the original notation as an instance attribute
        instance._original = original
        
        return instance

    @classmethod
    def _expand_with_fallbacks(cls, path_str: str) -> str:
        """
        Expand environment variables with intelligent fallbacks.

        Handles common XDG variables and provides sensible defaults when they're missing.
        """
        # Handle XDG_CACHE_HOME specifically
        if "$XDG_CACHE_HOME" in path_str:
            xdg_cache = os.environ.get("XDG_CACHE_HOME")
            if xdg_cache:
                path_str = path_str.replace("$XDG_CACHE_HOME", xdg_cache)
            else:
                # Fallback to ~/.cache
                path_str = path_str.replace("$XDG_CACHE_HOME", "~/.cache")

        # Handle XDG_CONFIG_HOME specifically
        if "$XDG_CONFIG_HOME" in path_str:
            xdg_config = os.environ.get("XDG_CONFIG_HOME")
            if xdg_config:
                path_str = path_str.replace("$XDG_CONFIG_HOME", xdg_config)
            else:
                # Fallback to ~/.config
                path_str = path_str.replace("$XDG_CONFIG_HOME", "~/.config")

        # Handle XDG_DATA_HOME specifically
        if "$XDG_DATA_HOME" in path_str:
            xdg_data = os.environ.get("XDG_DATA_HOME")
            if xdg_data:
                path_str = path_str.replace("$XDG_DATA_HOME", xdg_data)
            else:
                # Fallback to ~/.local/share
                path_str = path_str.replace("$XDG_DATA_HOME", "~/.local/share")

        # Expand any remaining environment variables and user home
        return os.path.expandvars(str(Path(path_str).expanduser()))

    @property
    def original(self) -> str:
        """Get the original path string with variables/tildes."""
        return self._original

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return f"PreservingPath('{self.original}')"

    @classmethod
    def from_path(
        cls, path: Path | str, original: str | None = None
    ) -> "PreservingPath":
        """Create a PreservingPath from an existing Path with optional original notation."""
        if original is None:
            original = str(path)
        return cls(original)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: Callable[[Any], core_schema.CoreSchema]
    ) -> core_schema.CoreSchema:
        """Get Pydantic core schema for PreservingPath."""
        return core_schema.no_info_before_validator_function(
            cls._validate_preserving_path,
            handler(str),
        )

    @classmethod
    def _validate_preserving_path(cls, value: Any) -> "PreservingPath":
        """Validate and convert value to PreservingPath."""
        if isinstance(value, cls):
            return value
        if isinstance(value, str | Path):
            return cls(str(value))
        raise ValueError(f"Invalid type for PreservingPath: {type(value)}")


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


