"""Tests for the OutputHandler class."""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest
import yaml

from glovebox.core.io import OutputError, OutputHandler, create_output_handler
from glovebox.models.base import GloveboxBaseModel


class SampleModel(GloveboxBaseModel):
    """Sample model for testing."""

    name: str
    value: int
    optional: str | None = None


class TestOutputHandler:
    """Test OutputHandler functionality."""

    @pytest.fixture
    def handler(self) -> OutputHandler:
        """Create an OutputHandler instance."""
        return create_output_handler()

    @pytest.fixture
    def sample_data(self) -> dict[str, Any]:
        """Create sample data for testing."""
        return {
            "name": "test",
            "value": 42,
            "items": ["one", "two", "three"],
            "nested": {"key": "value"},
        }

    @pytest.fixture
    def sample_model(self) -> SampleModel:
        """Create a sample Pydantic model."""
        return SampleModel(name="test", value=42)

    def test_create_output_handler(self) -> None:
        """Test factory function creates OutputHandler."""
        handler = create_output_handler()
        assert isinstance(handler, OutputHandler)
        assert handler.service_name == "OutputHandler"
        assert handler.service_version == "1.0.0"

    def test_write_to_stdout_json(
        self, handler: OutputHandler, sample_data: dict[str, Any]
    ) -> None:
        """Test writing JSON to stdout."""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            handler.write_to_stdout(sample_data, format="json")
            output = mock_stdout.getvalue()

            # Verify valid JSON
            parsed = json.loads(output.strip())
            assert parsed == sample_data

    def test_write_to_stdout_yaml(
        self, handler: OutputHandler, sample_data: dict[str, Any]
    ) -> None:
        """Test writing YAML to stdout."""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            handler.write_to_stdout(sample_data, format="yaml")
            output = mock_stdout.getvalue()

            # Verify valid YAML
            parsed = yaml.safe_load(output)
            assert parsed == sample_data

    def test_write_to_stdout_text(self, handler: OutputHandler) -> None:
        """Test writing text to stdout."""
        text_data = "Hello, world!"
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            handler.write_to_stdout(text_data, format="text")
            output = mock_stdout.getvalue()
            assert output.strip() == text_data

    def test_write_to_stdout_pydantic_model(
        self, handler: OutputHandler, sample_model: SampleModel
    ) -> None:
        """Test writing Pydantic model to stdout."""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            handler.write_to_stdout(sample_model, format="json")
            output = mock_stdout.getvalue()

            parsed = json.loads(output.strip())
            assert parsed["name"] == "test"
            assert parsed["value"] == 42
            # Should exclude None values
            assert "optional" not in parsed

    def test_write_to_stdout_invalid_format(
        self, handler: OutputHandler, sample_data: dict[str, Any]
    ) -> None:
        """Test writing with invalid format raises error."""
        with pytest.raises(OutputError, match="Unsupported format: invalid"):
            handler.write_to_stdout(sample_data, format="invalid")

    def test_write_to_file_json(
        self, handler: OutputHandler, sample_data: dict[str, Any], tmp_path: Path
    ) -> None:
        """Test writing JSON to file."""
        output_file = tmp_path / "output.json"
        handler.write_to_file(sample_data, output_file, format="json")

        assert output_file.exists()
        with output_file.open() as f:
            loaded = json.load(f)
            assert loaded == sample_data

    def test_write_to_file_yaml(
        self, handler: OutputHandler, sample_data: dict[str, Any], tmp_path: Path
    ) -> None:
        """Test writing YAML to file."""
        output_file = tmp_path / "output.yaml"
        handler.write_to_file(sample_data, output_file, format="yaml")

        assert output_file.exists()
        with output_file.open() as f:
            loaded = yaml.safe_load(f)
            assert loaded == sample_data

    def test_write_to_file_text(self, handler: OutputHandler, tmp_path: Path) -> None:
        """Test writing text to file."""
        text_data = "Hello, world!\nMultiple lines\nof text"
        output_file = tmp_path / "output.txt"
        handler.write_to_file(text_data, output_file, format="text")

        assert output_file.exists()
        assert output_file.read_text() == text_data

    def test_write_to_file_creates_parent_dirs(
        self, handler: OutputHandler, sample_data: dict[str, Any], tmp_path: Path
    ) -> None:
        """Test writing to file creates parent directories."""
        output_file = tmp_path / "nested" / "dir" / "output.json"
        handler.write_to_file(sample_data, output_file, format="json")

        assert output_file.exists()
        assert output_file.parent.exists()

    def test_write_to_file_pydantic_model(
        self, handler: OutputHandler, sample_model: SampleModel, tmp_path: Path
    ) -> None:
        """Test writing Pydantic model to file."""
        output_file = tmp_path / "model.json"
        handler.write_to_file(sample_model, output_file, format="json")

        assert output_file.exists()
        with output_file.open() as f:
            loaded = json.load(f)
            assert loaded["name"] == "test"
            assert loaded["value"] == 42
            assert "optional" not in loaded

    def test_write_to_directory(self, handler: OutputHandler, tmp_path: Path) -> None:
        """Test writing multiple files to directory."""
        files = {
            "data.json": {"key": "value"},
            "config.yaml": {"setting": "enabled"},
            "readme.txt": "This is a readme",
            "nested/file.json": {"nested": True},
        }

        output_dir = tmp_path / "output"
        handler.write_to_directory(files, output_dir)

        # Verify all files exist with correct content
        json_file = output_dir / "data.json"
        assert json_file.exists()
        with json_file.open() as f:
            assert json.load(f) == {"key": "value"}

        yaml_file = output_dir / "config.yaml"
        assert yaml_file.exists()
        with yaml_file.open() as f:
            assert yaml.safe_load(f) == {"setting": "enabled"}

        txt_file = output_dir / "readme.txt"
        assert txt_file.exists()
        assert txt_file.read_text() == "This is a readme"

        nested_file = output_dir / "nested" / "file.json"
        assert nested_file.exists()
        with nested_file.open() as f:
            assert json.load(f) == {"nested": True}

    def test_write_to_directory_invalid_data(
        self, handler: OutputHandler, tmp_path: Path
    ) -> None:
        """Test writing non-dict to directory raises error."""
        output_dir = tmp_path / "output"
        with pytest.raises(OutputError, match="Expected dict for directory output"):
            # Type ignore is intentional - testing error handling for wrong type
            handler.write_to_directory("not a dict", output_dir)  # type: ignore[arg-type]

    def test_write_output_to_stdout(
        self, handler: OutputHandler, sample_data: dict[str, Any]
    ) -> None:
        """Test write_output with stdout destination."""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            handler.write_output(sample_data, "-", format="json")
            output = mock_stdout.getvalue()
            assert json.loads(output.strip()) == sample_data

    def test_write_output_to_file(
        self, handler: OutputHandler, sample_data: dict[str, Any], tmp_path: Path
    ) -> None:
        """Test write_output with file destination."""
        output_file = tmp_path / "output.json"
        handler.write_output(sample_data, str(output_file), format="json")

        assert output_file.exists()
        with output_file.open() as f:
            assert json.load(f) == sample_data

    def test_write_output_to_existing_directory(
        self, handler: OutputHandler, tmp_path: Path
    ) -> None:
        """Test write_output with existing directory destination."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        files = {"file1.txt": "content1", "file2.txt": "content2"}
        handler.write_output(files, str(output_dir))

        assert (output_dir / "file1.txt").read_text() == "content1"
        assert (output_dir / "file2.txt").read_text() == "content2"

    def test_write_output_to_new_file_path(
        self, handler: OutputHandler, sample_data: dict[str, Any], tmp_path: Path
    ) -> None:
        """Test write_output treats non-existent path as file."""
        output_file = tmp_path / "new" / "output.json"
        handler.write_output(sample_data, str(output_file), format="json")

        assert output_file.exists()
        with output_file.open() as f:
            assert json.load(f) == sample_data

    def test_write_output_directory_with_non_dict(
        self, handler: OutputHandler, tmp_path: Path
    ) -> None:
        """Test write_output to directory with non-dict data raises error."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with pytest.raises(OutputError, match="Directory output requires dict data"):
            handler.write_output("not a dict", str(output_dir))

    def test_format_json_with_bytes(self, handler: OutputHandler) -> None:
        """Test JSON formatting with bytes data."""
        # JSON doesn't support bytes directly
        with pytest.raises(OutputError, match="Failed to format as JSON"):
            handler._format_json(b"bytes data")

    def test_format_yaml_with_complex_types(self, handler: OutputHandler) -> None:
        """Test YAML formatting with complex types."""
        data = {
            "list": [1, 2, 3],
            "dict": {"nested": {"deep": "value"}},
            "string": "test",
            "number": 42.5,
            "bool": True,
            "none": None,
        }
        result = handler._format_yaml(data)
        parsed = yaml.safe_load(result)

        # YAML should preserve all types except None
        assert parsed["list"] == [1, 2, 3]
        assert parsed["dict"]["nested"]["deep"] == "value"
        assert parsed["string"] == "test"
        assert parsed["number"] == 42.5
        assert parsed["bool"] is True
        assert parsed["none"] is None

    def test_format_text_with_different_types(self, handler: OutputHandler) -> None:
        """Test text formatting with different data types."""
        # String
        assert handler._format_text("hello") == "hello"

        # Bytes
        assert handler._format_text(b"bytes") == "bytes"

        # Object with __str__
        obj = Mock(__str__=lambda self: "mock object")
        assert handler._format_text(obj) == "mock object"

        # Complex type falls back to JSON
        data = {"key": "value"}
        result = handler._format_text(data)
        # Dict has __str__ method, so it will use str() not JSON
        assert result == str(data)

    def test_error_handling_with_debug_logging(
        self, handler: OutputHandler, tmp_path: Path, caplog
    ) -> None:
        """Test error handling includes stack trace in debug mode."""
        # Set debug level
        import logging

        handler.logger.setLevel(logging.DEBUG)

        # Create a read-only directory to trigger permission error
        output_dir = tmp_path / "readonly"
        output_dir.mkdir()
        output_file = output_dir / "test.json"
        output_file.write_text("existing")
        output_file.chmod(0o444)  # Read-only
        output_dir.chmod(0o555)  # Read-only directory

        try:
            with pytest.raises(OutputError):
                handler.write_to_file({"data": "value"}, output_file)

            # Should have logged with exc_info
            assert "Failed to write to file" in caplog.text
        finally:
            # Restore permissions for cleanup
            output_dir.chmod(0o755)
            output_file.chmod(0o644)

    def test_write_to_stdout_adds_newline(self, handler: OutputHandler) -> None:
        """Test stdout write adds newline if missing."""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            handler.write_to_stdout("no newline", format="text")
            output = mock_stdout.getvalue()
            assert output == "no newline\n"

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            handler.write_to_stdout("has newline\n", format="text")
            output = mock_stdout.getvalue()
            assert output == "has newline\n"

    def test_write_output_invalid_destination(
        self, handler: OutputHandler, tmp_path: Path
    ) -> None:
        """Test write_output with invalid destination type."""
        # Create a non-file, non-directory path (e.g., device file)
        # Since we can't easily create device files, we'll mock the path checks
        invalid_path = tmp_path / "invalid"
        invalid_path.write_text("test")

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "is_dir", return_value=False),
            patch.object(Path, "suffix", ""),
            pytest.raises(OutputError, match="Invalid destination"),
        ):
            handler.write_output({"data": "value"}, str(invalid_path))

    def test_service_info(self, handler: OutputHandler) -> None:
        """Test service info method."""
        info = handler.get_service_info()
        assert info["name"] == "OutputHandler"
        assert info["version"] == "1.0.0"
        assert info["type"] == "OutputHandler"

    def test_write_to_directory_handles_write_errors(
        self, handler: OutputHandler, tmp_path: Path
    ) -> None:
        """Test directory write handles individual file errors gracefully."""
        files = {
            "good.txt": "This should work",
            "bad/file.txt": "This might fail",
        }

        output_dir = tmp_path / "output"

        # Mock write_to_file to fail on second file
        original_write = handler.write_to_file
        call_count = 0

        def mock_write(data, path, format):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise OutputError("Simulated write failure")
            return original_write(data, path, format)

        with (
            patch.object(handler, "write_to_file", side_effect=mock_write),
            pytest.raises(OutputError, match="Simulated write failure"),
        ):
            handler.write_to_directory(files, output_dir)

        # First file should have been written
        assert (output_dir / "good.txt").exists()
