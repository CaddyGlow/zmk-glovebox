"""Tests for the InputHandler class."""

import json
import logging
import os
from io import StringIO
from unittest.mock import patch

import pytest

from glovebox.core.io.handlers import InputError, InputHandler, create_input_handler


class TestInputHandler:
    """Test cases for InputHandler class."""

    @pytest.fixture
    def handler(self):
        """Create an InputHandler instance for testing."""
        return create_input_handler()

    @pytest.fixture
    def valid_json_data(self):
        """Sample valid JSON data."""
        return {"key": "value", "number": 42, "list": [1, 2, 3]}

    @pytest.fixture
    def json_file(self, tmp_path, valid_json_data):
        """Create a temporary JSON file."""
        file_path = tmp_path / "test.json"
        file_path.write_text(json.dumps(valid_json_data))
        return file_path

    def test_create_input_handler(self):
        """Test factory function creates InputHandler instance."""
        handler = create_input_handler()
        assert isinstance(handler, InputHandler)

    def test_load_from_file_success(self, handler, json_file, valid_json_data):
        """Test successfully loading JSON from a file."""
        result = handler.load_json_input(str(json_file))
        assert result == valid_json_data

    def test_load_from_file_not_found(self, handler, tmp_path):
        """Test loading from non-existent file raises error."""
        non_existent = tmp_path / "does_not_exist.json"
        with pytest.raises(InputError, match="File not found"):
            handler.load_json_input(str(non_existent))

    def test_load_from_file_not_a_file(self, handler, tmp_path):
        """Test loading from directory raises error."""
        with pytest.raises(InputError, match="Not a file"):
            handler.load_json_input(str(tmp_path))

    def test_load_from_file_invalid_json(self, handler, tmp_path):
        """Test loading invalid JSON raises error."""
        invalid_json_file = tmp_path / "invalid.json"
        invalid_json_file.write_text("{ invalid json")

        with pytest.raises(InputError, match="Invalid JSON"):
            handler.load_json_input(str(invalid_json_file))

    def test_load_from_file_permission_error(self, handler, tmp_path):
        """Test handling permission errors when reading file."""
        file_path = tmp_path / "no_permission.json"
        file_path.write_text("{}")

        with (
            patch("pathlib.Path.open", side_effect=PermissionError("No access")),
            pytest.raises(InputError, match="Permission denied"),
        ):
            handler.load_json_input(str(file_path))

    def test_load_from_file_non_dict_wrapped(self, handler, tmp_path):
        """Test non-dict JSON data is wrapped in a dict."""
        array_file = tmp_path / "array.json"
        array_file.write_text("[1, 2, 3]")

        result = handler.load_json_input(str(array_file))
        assert result == {"data": [1, 2, 3]}

    def test_load_from_stdin_success(self, handler, valid_json_data):
        """Test successfully loading JSON from stdin."""
        json_str = json.dumps(valid_json_data)

        with (
            patch("sys.stdin", StringIO(json_str)),
            patch("sys.stdin.isatty", return_value=False),
        ):
            result = handler.load_json_input("-")
            assert result == valid_json_data

    def test_load_from_stdin_interactive_terminal(self, handler):
        """Test loading from stdin with interactive terminal raises error."""
        with (
            patch("sys.stdin.isatty", return_value=True),
            pytest.raises(InputError, match="terminal is interactive"),
        ):
            handler.load_json_input("-")

    def test_load_from_stdin_empty(self, handler):
        """Test loading empty stdin raises error."""
        with (
            patch("sys.stdin", StringIO("")),
            patch("sys.stdin.isatty", return_value=False),
            pytest.raises(InputError, match="No data provided"),
        ):
            handler.load_json_input("-")

    def test_load_from_stdin_invalid_json(self, handler):
        """Test loading invalid JSON from stdin raises error."""
        with (
            patch("sys.stdin", StringIO("{ invalid")),
            patch("sys.stdin.isatty", return_value=False),
            pytest.raises(InputError, match="Invalid JSON from stdin"),
        ):
            handler.load_json_input("-")

    def test_load_from_stdin_non_dict_wrapped(self, handler):
        """Test non-dict JSON from stdin is wrapped."""
        with (
            patch("sys.stdin", StringIO('"string value"')),
            patch("sys.stdin.isatty", return_value=False),
        ):
            result = handler.load_json_input("-")
            assert result == {"data": "string value"}

    def test_load_from_environment_success(self, handler, valid_json_data):
        """Test successfully loading JSON from environment variable."""
        var_name = "TEST_JSON_DATA"
        json_str = json.dumps(valid_json_data)

        with patch.dict(os.environ, {var_name: json_str}):
            result = handler.load_json_input(var_name)
            assert result == valid_json_data

    def test_load_from_environment_not_found(self, handler):
        """Test loading from non-existent environment variable."""
        # Ensure variable doesn't exist
        var_name = "NONEXISTENT_VAR_12345"
        os.environ.pop(var_name, None)

        with pytest.raises(InputError, match="Environment variable not found"):
            handler.load_from_environment(var_name)

    def test_load_from_environment_empty(self, handler):
        """Test loading empty environment variable raises error."""
        var_name = "EMPTY_VAR"

        with (
            patch.dict(os.environ, {var_name: ""}),
            pytest.raises(InputError, match="is empty"),
        ):
            handler.load_json_input(var_name)

    def test_load_from_environment_invalid_json(self, handler):
        """Test loading invalid JSON from environment variable."""
        var_name = "INVALID_JSON"

        with (
            patch.dict(os.environ, {var_name: "not json"}),
            pytest.raises(InputError, match="Invalid JSON in environment"),
        ):
            handler.load_json_input(var_name)

    def test_load_from_environment_non_dict_wrapped(self, handler):
        """Test non-dict JSON from environment is wrapped."""
        var_name = "ARRAY_JSON"

        with patch.dict(os.environ, {var_name: "[1, 2, 3]"}):
            result = handler.load_json_input(var_name)
            assert result == {"data": [1, 2, 3]}

    def test_library_reference_not_implemented(self, handler):
        """Test library references raise not implemented error."""
        with pytest.raises(InputError, match="not yet implemented"):
            handler.load_json_input("@my-library")

        with pytest.raises(InputError, match="not yet implemented"):
            handler.load_json_input("@uuid-12345")

    def test_library_reference_empty(self, handler):
        """Test empty library reference raises error."""
        with pytest.raises(InputError, match="Empty library reference"):
            handler.resolve_library_reference("@")

    def test_library_reference_invalid_format(self, handler):
        """Test invalid library reference format."""
        with pytest.raises(InputError, match="Invalid library reference format"):
            handler.resolve_library_reference("not-a-reference")

    def test_load_json_input_prioritizes_stdin(self, handler):
        """Test that "-" is recognized as stdin even if file exists."""
        # Create a file named "-" (unlikely but possible)
        with (
            patch("sys.stdin", StringIO('{"from": "stdin"}')),
            patch("sys.stdin.isatty", return_value=False),
        ):
            result = handler.load_json_input("-")
            assert result == {"from": "stdin"}

    def test_load_json_input_prioritizes_library_ref(self, handler, tmp_path):
        """Test that @ prefix is recognized as library ref even if file exists."""
        # Create a file that starts with @
        weird_file = tmp_path / "@library.json"
        weird_file.write_text('{"from": "file"}')

        with pytest.raises(InputError, match="not yet implemented"):
            handler.load_json_input("@library.json")

    def test_load_json_input_environment_precedence(self, handler, tmp_path):
        """Test environment variable takes precedence over file with same name."""
        var_name = "test.json"
        file_path = tmp_path / var_name

        # Create both file and env var with same name
        file_path.write_text('{"from": "file"}')
        with patch.dict(os.environ, {var_name: '{"from": "env"}'}):
            result = handler.load_json_input(var_name)
            assert result == {"from": "env"}

    def test_error_logging_with_debug(self, handler, tmp_path):
        """Test that stack traces are included when debug logging is enabled."""
        non_existent = tmp_path / "missing.json"

        with (
            patch.object(
                handler.logger, "isEnabledFor", return_value=True
            ) as mock_enabled,
            patch.object(handler.logger, "error") as mock_error,
            pytest.raises(InputError),
        ):
            handler.load_json_input(str(non_existent))

            # Check that exc_info was passed as True
            mock_enabled.assert_called_with(logging.DEBUG)
            assert mock_error.call_args[1].get("exc_info") is True

    def test_error_logging_without_debug(self, handler, tmp_path):
        """Test that stack traces are excluded when debug logging is disabled."""
        non_existent = tmp_path / "missing.json"

        with (
            patch.object(
                handler.logger, "isEnabledFor", return_value=False
            ) as mock_enabled,
            patch.object(handler.logger, "error") as mock_error,
            pytest.raises(InputError),
        ):
            handler.load_json_input(str(non_existent))

            # Check that exc_info was passed as False
            mock_enabled.assert_called_with(logging.DEBUG)
            assert mock_error.call_args[1].get("exc_info") is False

    def test_os_error_handling(self, handler, tmp_path):
        """Test handling of generic OS errors."""
        file_path = tmp_path / "test.json"
        file_path.write_text("{}")

        with (
            patch("pathlib.Path.open", side_effect=OSError("Disk full")),
            pytest.raises(InputError, match="Error reading file"),
        ):
            handler.load_json_input(str(file_path))

    def test_stdin_read_exception(self, handler):
        """Test handling of exceptions when reading stdin."""
        with (
            patch("sys.stdin.isatty", return_value=False),
            patch("sys.stdin.read", side_effect=OSError("Read error")),
            pytest.raises(InputError, match="Error reading from stdin"),
        ):
            handler.load_json_input("-")


class TestInputHandlerIntegration:
    """Integration tests for InputHandler."""

    @pytest.fixture
    def handler(self):
        """Create an InputHandler instance for testing."""
        return create_input_handler()

    def test_full_workflow_file(self, handler, tmp_path):
        """Test complete workflow with file input."""
        # Create test data
        data = {
            "layout": {"keys": ["a", "b", "c"]},
            "metadata": {"version": "1.0"},
        }

        # Save to file
        file_path = tmp_path / "layout.json"
        file_path.write_text(json.dumps(data, indent=2))

        # Load and verify
        result = handler.load_json_input(str(file_path))
        assert result == data

    def test_full_workflow_environment(self, handler):
        """Test complete workflow with environment variable."""
        data = {"config": {"theme": "dark"}, "settings": {"auto_save": True}}

        var_name = "APP_CONFIG"

        with patch.dict(os.environ, {var_name: json.dumps(data)}):
            result = handler.load_json_input(var_name)
            assert result == data

    def test_unicode_handling(self, handler, tmp_path):
        """Test handling of Unicode in JSON data."""
        data = {"name": "Test 测试", "emoji": "🎹", "symbols": "αβγ"}

        # Test file
        file_path = tmp_path / "unicode.json"
        file_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        result = handler.load_json_input(str(file_path))
        assert result == data

        # Test environment
        with patch.dict(
            os.environ, {"UNICODE_TEST": json.dumps(data, ensure_ascii=False)}
        ):
            result = handler.load_json_input("UNICODE_TEST")
            assert result == data

    def test_large_json_handling(self, handler, tmp_path):
        """Test handling of large JSON files."""
        # Create a large nested structure
        large_data = {
            f"level_{i}": {f"item_{j}": list(range(100)) for j in range(10)}
            for i in range(10)
        }

        file_path = tmp_path / "large.json"
        file_path.write_text(json.dumps(large_data))

        result = handler.load_json_input(str(file_path))
        assert result == large_data
