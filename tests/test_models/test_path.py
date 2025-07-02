"""Tests for path preservation functionality."""

import os
import tempfile
from pathlib import Path

import pytest
from pydantic import Field, field_serializer, field_validator

from glovebox.models.base import GloveboxBaseModel
from glovebox.models.path import PreservingPath, path_field


class ExamplePathModel(GloveboxBaseModel):
    """Example model demonstrating path preservation."""

    file_path: PreservingPath | None = path_field(
        default=None, description="Example file path with preservation"
    )
    cache_path: PreservingPath = Field(
        default_factory=lambda: PreservingPath("~/.cache/example"),
        description="Example cache path with preservation",
    )

    @field_validator("file_path", mode="before")
    @classmethod
    def validate_file_path(cls, v) -> PreservingPath | None:
        """Validate and create PreservingPath for file_path."""
        if v is None:
            return None

        if isinstance(v, PreservingPath):
            return v

        if isinstance(v, str | Path):
            return PreservingPath(str(v))

        raise ValueError(f"Invalid file path type: {type(v)}")

    @field_validator("cache_path", mode="before")
    @classmethod
    def validate_cache_path(cls, v) -> PreservingPath:
        """Validate and create PreservingPath for cache_path."""
        if isinstance(v, PreservingPath):
            return v

        if isinstance(v, str | Path):
            return PreservingPath(str(v))

        raise ValueError(f"Invalid cache path type: {type(v)}")

    @field_serializer("file_path", when_used="json")
    def serialize_file_path(self, value: PreservingPath | None) -> str | None:
        """Serialize file_path back to original notation."""
        if value is None:
            return None
        return value.original

    @field_serializer("cache_path", when_used="json")
    def serialize_cache_path(self, value: PreservingPath) -> str:
        """Serialize cache_path back to original notation."""
        return value.original


class TestPreservingPath:
    """Test cases for PreservingPath class."""

    def test_basic_path_operations(self):
        """Test that PreservingPath behaves like a normal Path for basic operations."""
        original = "~/test/path"
        preserving_path = PreservingPath(original)

        # Should resolve like a normal Path
        expected = Path(original).expanduser().resolve()
        assert str(preserving_path) == str(expected)

        # Should preserve original notation
        assert preserving_path.original == original

        # Should support Path operations
        assert preserving_path.name == "path"
        assert preserving_path.parent.name == "test"
        assert isinstance(preserving_path.parent, Path)

    def test_tilde_expansion(self):
        """Test that tilde expansion works correctly."""
        original = "~/Documents/test.txt"
        preserving_path = PreservingPath(original)

        # Original should be preserved
        assert preserving_path.original == original

        # Resolved path should expand tilde
        expected = Path.home() / "Documents" / "test.txt"
        assert preserving_path == expected

    def test_xdg_cache_home_fallback(self):
        """Test XDG_CACHE_HOME fallback behavior."""
        # Ensure XDG_CACHE_HOME is not set
        original_env = os.environ.get("XDG_CACHE_HOME")
        if "XDG_CACHE_HOME" in os.environ:
            del os.environ["XDG_CACHE_HOME"]

        try:
            original = "$XDG_CACHE_HOME/glovebox"
            preserving_path = PreservingPath(original)

            # Original should be preserved
            assert preserving_path.original == original

            # Should fallback to ~/.cache/glovebox
            expected = Path.home() / ".cache" / "glovebox"
            assert preserving_path == expected
        finally:
            # Restore original environment
            if original_env is not None:
                os.environ["XDG_CACHE_HOME"] = original_env

    def test_xdg_cache_home_expansion(self):
        """Test XDG_CACHE_HOME expansion when variable is set."""
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["XDG_CACHE_HOME"] = temp_dir
            try:
                original = "$XDG_CACHE_HOME/glovebox"
                preserving_path = PreservingPath(original)

                # Original should be preserved
                assert preserving_path.original == original

                # Should expand to temp directory
                expected = Path(temp_dir) / "glovebox"
                assert preserving_path == expected
            finally:
                # Clean up
                if "XDG_CACHE_HOME" in os.environ:
                    del os.environ["XDG_CACHE_HOME"]

    def test_xdg_config_home_fallback(self):
        """Test XDG_CONFIG_HOME fallback behavior."""
        original_env = os.environ.get("XDG_CONFIG_HOME")
        if "XDG_CONFIG_HOME" in os.environ:
            del os.environ["XDG_CONFIG_HOME"]

        try:
            original = "$XDG_CONFIG_HOME/glovebox"
            preserving_path = PreservingPath(original)

            # Original should be preserved
            assert preserving_path.original == original

            # Should fallback to ~/.config/glovebox
            expected = Path.home() / ".config" / "glovebox"
            assert preserving_path == expected
        finally:
            if original_env is not None:
                os.environ["XDG_CONFIG_HOME"] = original_env

    def test_xdg_data_home_fallback(self):
        """Test XDG_DATA_HOME fallback behavior."""
        original_env = os.environ.get("XDG_DATA_HOME")
        if "XDG_DATA_HOME" in os.environ:
            del os.environ["XDG_DATA_HOME"]

        try:
            original = "$XDG_DATA_HOME/glovebox"
            preserving_path = PreservingPath(original)

            # Original should be preserved
            assert preserving_path.original == original

            # Should fallback to ~/.local/share/glovebox
            expected = Path.home() / ".local" / "share" / "glovebox"
            assert preserving_path == expected
        finally:
            if original_env is not None:
                os.environ["XDG_DATA_HOME"] = original_env

    def test_regular_environment_variable(self):
        """Test expansion of regular environment variables."""
        test_var = "TEST_PATH_VAR"
        test_value = "/tmp/test"

        os.environ[test_var] = test_value
        try:
            original = f"${test_var}/subdir"
            preserving_path = PreservingPath(original)

            # Original should be preserved
            assert preserving_path.original == original

            # Should expand environment variable
            expected = Path(test_value) / "subdir"
            assert preserving_path == expected
        finally:
            if test_var in os.environ:
                del os.environ[test_var]

    def test_from_path_classmethod(self):
        """Test PreservingPath.from_path() class method."""
        # Test with existing Path
        existing_path = Path("/tmp/test")
        preserving_path = PreservingPath.from_path(existing_path)

        assert preserving_path.original == "/tmp/test"
        assert preserving_path == existing_path.resolve()

        # Test with custom original
        custom_original = "~/test"
        preserving_path = PreservingPath.from_path(existing_path, custom_original)

        assert preserving_path.original == custom_original
        assert preserving_path == existing_path.resolve()

    def test_equality_comparison(self):
        """Test that PreservingPath compares correctly with other paths."""
        preserving_path = PreservingPath("~/test")
        regular_path = Path("~/test").expanduser().resolve()

        # Should be equal to resolved regular Path
        assert preserving_path == regular_path

        # Should be equal to other PreservingPath with same resolved path
        other_preserving = PreservingPath.from_path(regular_path, "different/original")
        assert preserving_path == other_preserving

    def test_repr_and_str(self):
        """Test string representations."""
        original = "~/test"
        preserving_path = PreservingPath(original)

        # repr should show original
        assert repr(preserving_path) == f"PreservingPath('{original}')"

        # str should show resolved path
        expected_str = str(Path(original).expanduser().resolve())
        assert str(preserving_path) == expected_str


class TestExamplePathModel:
    """Test cases for Pydantic model integration."""

    def test_model_serialization_preserves_original(self):
        """Test that model serialization preserves original path notation."""
        model = ExamplePathModel(
            file_path=PreservingPath("~/logs/app.log"),
            cache_path=PreservingPath("$XDG_CACHE_HOME/myapp"),
        )

        # Serialize to dict
        data = model.model_dump(mode="json")

        # Should preserve original notation
        assert data["file_path"] == "~/logs/app.log"
        assert data["cache_path"] == "$XDG_CACHE_HOME/myapp"

    def test_model_deserialization_from_strings(self):
        """Test that model can be created from string paths."""
        data = {"file_path": "~/logs/debug.log", "cache_path": "$XDG_CACHE_HOME/test"}

        model = ExamplePathModel.model_validate(data)

        # Should create PreservingPath objects
        assert isinstance(model.file_path, PreservingPath)
        assert isinstance(model.cache_path, PreservingPath)

        # Should preserve original notation
        assert model.file_path.original == "~/logs/debug.log"
        assert model.cache_path.original == "$XDG_CACHE_HOME/test"

        # Should resolve paths correctly
        expected_file = Path("~/logs/debug.log").expanduser().resolve()
        assert model.file_path == expected_file

    def test_model_roundtrip_serialization(self):
        """Test that serialization and deserialization preserves original notation."""
        original_data = {
            "file_path": "~/config/app.conf",
            "cache_path": "$XDG_CACHE_HOME/app",
        }

        # Create model from data
        model = ExamplePathModel.model_validate(original_data)

        # Serialize back to dict
        serialized = model.model_dump(mode="json")

        # Should preserve original notation
        assert serialized["file_path"] == original_data["file_path"]
        assert serialized["cache_path"] == original_data["cache_path"]

        # Create new model from serialized data
        model2 = ExamplePathModel.model_validate(serialized)

        # Should be equivalent
        assert model2.file_path == model.file_path
        assert model2.cache_path == model.cache_path
        assert model2.file_path is not None and model.file_path is not None
        assert model2.file_path.original == model.file_path.original
        assert model2.cache_path.original == model.cache_path.original

    def test_model_with_none_file_path(self):
        """Test model behavior with None file_path."""
        model = ExamplePathModel(
            file_path=None, cache_path=PreservingPath("~/.cache/test")
        )

        # Serialize to dict
        data = model.model_dump(mode="json")

        # Should handle None correctly - with exclude_none=True (default), None values are excluded
        assert "file_path" not in data
        assert data["cache_path"] == "~/.cache/test"

        # Test with exclude_none=False to include None values
        data_with_none = model.model_dump(mode="json", exclude_none=False)
        assert data_with_none["file_path"] is None
        assert data_with_none["cache_path"] == "~/.cache/test"

    def test_model_validation_errors(self):
        """Test that invalid path types raise validation errors."""
        with pytest.raises(ValueError, match="Invalid file path type"):
            ExamplePathModel(
                file_path=123,  # type: ignore[arg-type]  # Invalid type for testing
                cache_path=PreservingPath("~/.cache/test"),
            )

        with pytest.raises(ValueError, match="Invalid cache path type"):
            ExamplePathModel(
                file_path=None,
                cache_path=123,  # type: ignore[arg-type]  # Invalid type for testing
            )
