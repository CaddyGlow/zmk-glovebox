"""Tests for CLI parameter helper functions."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import typer

from glovebox.cli.helpers.parameter_helpers import (
    format_and_output_data,
    get_format_result_from_context,
    get_format_type_from_context,
    get_formatter_from_context,
    get_input_data_from_context,
    get_input_path_from_context,
    get_input_result_from_context,
    get_output_path_from_context,
    get_output_result_from_context,
    is_json_format_from_context,
    is_output_stdout_from_context,
    process_format_parameter,
    process_input_parameter,
    process_output_parameter,
    read_input_from_result,
    validate_input_file,
    validate_output_path,
    write_output_from_result,
)
from glovebox.cli.helpers.parameter_types import (
    FormatResult,
    InputResult,
    OutputResult,
    ValidationResult,
)


# =============================================================================
# Test Context Access Functions
# =============================================================================


class TestContextAccessFunctions:
    """Test context access helper functions."""

    def test_get_input_result_from_context(self):
        """Test getting input result from context."""
        # Create mock context with input result
        ctx = Mock(spec=typer.Context)
        ctx.obj = Mock()

        input_result = InputResult(raw_value="test.json")
        ctx.obj.param_input_result = input_result

        # Mock hasattr and getattr
        with (
            patch("builtins.hasattr", return_value=True),
            patch("builtins.getattr", return_value=input_result),
        ):
            result = get_input_result_from_context(ctx)
            assert result == input_result

    def test_get_input_result_from_context_none(self):
        """Test getting input result when not present."""
        ctx = Mock(spec=typer.Context)
        ctx.obj = Mock()

        with patch("builtins.hasattr", return_value=False):
            result = get_input_result_from_context(ctx)
            assert result is None

    def test_get_output_result_from_context(self):
        """Test getting output result from context."""
        ctx = Mock(spec=typer.Context)
        ctx.obj = Mock()

        output_result = OutputResult(raw_value="output.json")

        with (
            patch("builtins.hasattr", return_value=True),
            patch("builtins.getattr", return_value=output_result),
        ):
            result = get_output_result_from_context(ctx)
            assert result == output_result

    def test_get_format_result_from_context(self):
        """Test getting format result from context."""
        ctx = Mock(spec=typer.Context)
        ctx.obj = Mock()

        format_result = FormatResult(format_type="json")

        with (
            patch("builtins.hasattr", return_value=True),
            patch("builtins.getattr", return_value=format_result),
        ):
            result = get_format_result_from_context(ctx)
            assert result == format_result

    def test_get_input_data_from_context(self):
        """Test getting input data from context."""
        ctx = Mock(spec=typer.Context)
        input_result = InputResult(raw_value="test.json", data='{"test": "data"}')

        with patch(
            "glovebox.cli.helpers.parameter_helpers.get_input_result_from_context",
            return_value=input_result,
        ):
            data = get_input_data_from_context(ctx)
            assert data == '{"test": "data"}'

    def test_get_input_data_from_context_none(self):
        """Test getting input data when not present."""
        ctx = Mock(spec=typer.Context)

        with patch(
            "glovebox.cli.helpers.parameter_helpers.get_input_result_from_context",
            return_value=None,
        ):
            data = get_input_data_from_context(ctx)
            assert data is None

    def test_get_input_path_from_context(self):
        """Test getting input path from context."""
        ctx = Mock(spec=typer.Context)
        input_result = InputResult(
            raw_value="test.json", resolved_path=Path("test.json")
        )

        with patch(
            "glovebox.cli.helpers.parameter_helpers.get_input_result_from_context",
            return_value=input_result,
        ):
            path = get_input_path_from_context(ctx)
            assert path == Path("test.json")

    def test_get_output_path_from_context(self):
        """Test getting output path from context."""
        ctx = Mock(spec=typer.Context)
        output_result = OutputResult(
            raw_value="output.json", resolved_path=Path("output.json")
        )

        with patch(
            "glovebox.cli.helpers.parameter_helpers.get_output_result_from_context",
            return_value=output_result,
        ):
            path = get_output_path_from_context(ctx)
            assert path == Path("output.json")

    def test_get_output_path_from_context_stdout(self):
        """Test getting output path when output is stdout."""
        ctx = Mock(spec=typer.Context)
        output_result = OutputResult(raw_value="-", is_stdout=True)

        with patch(
            "glovebox.cli.helpers.parameter_helpers.get_output_result_from_context",
            return_value=output_result,
        ):
            path = get_output_path_from_context(ctx)
            assert path is None

    def test_is_output_stdout_from_context(self):
        """Test checking if output is stdout."""
        ctx = Mock(spec=typer.Context)
        output_result = OutputResult(raw_value="-", is_stdout=True)

        with patch(
            "glovebox.cli.helpers.parameter_helpers.get_output_result_from_context",
            return_value=output_result,
        ):
            is_stdout = is_output_stdout_from_context(ctx)
            assert is_stdout is True

    def test_get_format_type_from_context(self):
        """Test getting format type from context."""
        ctx = Mock(spec=typer.Context)
        format_result = FormatResult(format_type="json")

        with patch(
            "glovebox.cli.helpers.parameter_helpers.get_format_result_from_context",
            return_value=format_result,
        ):
            format_type = get_format_type_from_context(ctx)
            assert format_type == "json"

    def test_get_format_type_from_context_default(self):
        """Test getting format type with default when not present."""
        ctx = Mock(spec=typer.Context)

        with patch(
            "glovebox.cli.helpers.parameter_helpers.get_format_result_from_context",
            return_value=None,
        ):
            format_type = get_format_type_from_context(ctx)
            assert format_type == "table"

    def test_is_json_format_from_context(self):
        """Test checking if format is JSON."""
        ctx = Mock(spec=typer.Context)
        format_result = FormatResult(format_type="json", is_json=True)

        with patch(
            "glovebox.cli.helpers.parameter_helpers.get_format_result_from_context",
            return_value=format_result,
        ):
            is_json = is_json_format_from_context(ctx)
            assert is_json is True


# =============================================================================
# Test Input Parameter Processing
# =============================================================================


class TestInputParameterProcessing:
    """Test input parameter processing functions."""

    def test_process_input_parameter_file(self, tmp_path):
        """Test processing a file input parameter."""
        test_file = tmp_path / "test.json"
        test_file.write_text('{"test": "data"}')

        result = process_input_parameter(test_file)

        assert result.raw_value == test_file
        assert result.resolved_path == test_file
        assert result.is_stdin is False
        assert result.env_fallback_used is False

    def test_process_input_parameter_stdin(self):
        """Test processing stdin input parameter."""
        result = process_input_parameter("-", supports_stdin=True)

        assert result.raw_value == "-"
        assert result.resolved_path is None
        assert result.is_stdin is True
        assert result.env_fallback_used is False

    def test_process_input_parameter_env_fallback(self, tmp_path):
        """Test processing input with environment variable fallback."""
        test_file = tmp_path / "env_test.json"
        test_file.write_text('{"env": "data"}')

        with patch.dict(os.environ, {"TEST_ENV_VAR": str(test_file)}):
            result = process_input_parameter(
                None,
                env_fallback="TEST_ENV_VAR",
                required=True,
            )

            assert result.raw_value == str(test_file)
            assert result.resolved_path == test_file
            assert result.env_fallback_used is True

    def test_process_input_parameter_required_missing(self):
        """Test processing required input when missing."""
        with pytest.raises(typer.BadParameter, match="Input file is required"):
            process_input_parameter(None, required=True)

    def test_process_input_parameter_file_not_exists(self):
        """Test processing input when file doesn't exist."""
        with pytest.raises(typer.BadParameter, match="Input file does not exist"):
            process_input_parameter(Path("nonexistent.json"))

    def test_process_input_parameter_invalid_extension(self, tmp_path):
        """Test processing input with invalid extension."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        with pytest.raises(typer.BadParameter, match="Unsupported file extension"):
            process_input_parameter(
                test_file,
                allowed_extensions=[".json", ".yaml"],
            )

    @patch("glovebox.cli.helpers.parameter_helpers.read_json_input")
    def test_read_input_from_result_json(self, mock_read_json):
        """Test reading JSON input from result."""
        mock_read_json.return_value = {"test": "data"}
        result = InputResult(raw_value="test.json", resolved_path=Path("test.json"))

        data = read_input_from_result(result, as_json=True)

        mock_read_json.assert_called_once_with("test.json")
        assert data == {"test": "data"}

    @patch("glovebox.cli.helpers.parameter_helpers.read_input_data")
    def test_read_input_from_result_text(self, mock_read_data):
        """Test reading text input from result."""
        mock_read_data.return_value = "test data"
        result = InputResult(raw_value="test.txt", resolved_path=Path("test.txt"))

        data = read_input_from_result(result)

        mock_read_data.assert_called_once_with("test.txt")
        assert data == "test data"

    def test_read_input_from_result_cached_data(self):
        """Test reading input when data is already cached."""
        result = InputResult(
            raw_value="test.json",
            resolved_path=Path("test.json"),
            data='{"cached": "data"}',
        )

        data = read_input_from_result(result, as_json=True)
        assert data == '{"cached": "data"}'

    def test_read_input_from_result_stdin(self):
        """Test reading input from stdin result."""
        result = InputResult(raw_value="-", is_stdin=True)

        with patch(
            "glovebox.cli.helpers.parameter_helpers.read_input_data",
            return_value="stdin data",
        ) as mock_read:
            data = read_input_from_result(result)
            mock_read.assert_called_once_with("-")
            assert data == "stdin data"


# =============================================================================
# Test Output Parameter Processing
# =============================================================================


class TestOutputParameterProcessing:
    """Test output parameter processing functions."""

    def test_process_output_parameter_file(self):
        """Test processing file output parameter."""
        result = process_output_parameter("output.json")

        assert result.raw_value == "output.json"
        assert result.resolved_path == Path("output.json")
        assert result.is_stdout is False
        assert result.smart_default_used is False

    def test_process_output_parameter_stdout(self):
        """Test processing stdout output parameter."""
        result = process_output_parameter("-", supports_stdout=True)

        assert result.raw_value == "-"
        assert result.resolved_path is None
        assert result.is_stdout is True

    def test_process_output_parameter_smart_default(self):
        """Test processing output with smart default template."""
        template_vars = {"name": "test", "ext": "json"}
        result = process_output_parameter(
            None,
            smart_default_template="{name}.{ext}",
            template_vars=template_vars,
        )

        assert result.raw_value is None
        assert result.resolved_path == Path.cwd() / "test.json"
        assert result.smart_default_used is True

    def test_process_output_parameter_template_missing_var(self):
        """Test processing output with missing template variable."""
        with pytest.raises(typer.BadParameter, match="Missing template variable"):
            process_output_parameter(
                None,
                smart_default_template="{missing_var}.json",
                template_vars={},
            )

    @patch("glovebox.cli.helpers.parameter_helpers.typer.confirm")
    def test_process_output_parameter_existing_file_confirm(
        self, mock_confirm, tmp_path
    ):
        """Test processing output when file exists and user confirms."""
        existing_file = tmp_path / "existing.json"
        existing_file.write_text('{"existing": "data"}')
        mock_confirm.return_value = True

        with patch("glovebox.cli.helpers.parameter_helpers.get_themed_console"):
            result = process_output_parameter(existing_file)

            assert result.resolved_path == existing_file
            mock_confirm.assert_called_once()

    @patch("glovebox.cli.helpers.parameter_helpers.typer.confirm")
    def test_process_output_parameter_existing_file_abort(self, mock_confirm, tmp_path):
        """Test processing output when file exists and user aborts."""
        existing_file = tmp_path / "existing.json"
        existing_file.write_text('{"existing": "data"}')
        mock_confirm.return_value = False

        with (
            patch("glovebox.cli.helpers.parameter_helpers.get_themed_console"),
            pytest.raises(typer.Abort),
        ):
            process_output_parameter(existing_file)

    def test_write_output_from_result_file(self, tmp_path):
        """Test writing output to file."""
        output_file = tmp_path / "output.json"
        result = OutputResult(raw_value=str(output_file), resolved_path=output_file)

        with patch("glovebox.cli.helpers.parameter_helpers.get_themed_console"):
            write_output_from_result(result, '{"test": "data"}')

            assert output_file.exists()
            assert output_file.read_text() == '{"test": "data"}'

    @patch("builtins.print")
    def test_write_output_from_result_stdout(self, mock_print):
        """Test writing output to stdout."""
        result = OutputResult(raw_value="-", is_stdout=True)

        write_output_from_result(result, "test output")

        mock_print.assert_called_once_with("test output")

    def test_write_output_from_result_binary(self, tmp_path):
        """Test writing binary output to file."""
        output_file = tmp_path / "output.bin"
        result = OutputResult(raw_value=str(output_file), resolved_path=output_file)

        with patch("glovebox.cli.helpers.parameter_helpers.get_themed_console"):
            write_output_from_result(result, b"binary data")

            assert output_file.exists()
            assert output_file.read_bytes() == b"binary data"

    def test_write_output_from_result_no_destination(self):
        """Test writing output with no valid destination."""
        result = OutputResult(raw_value=None, resolved_path=None, is_stdout=False)

        with pytest.raises(ValueError, match="No valid output destination"):
            write_output_from_result(result, "test data")


# =============================================================================
# Test Format Parameter Processing
# =============================================================================


class TestFormatParameterProcessing:
    """Test format parameter processing functions."""

    def test_process_format_parameter_valid(self):
        """Test processing valid format parameter."""
        result = process_format_parameter("json")

        assert result.format_type == "json"
        assert result.is_json is True
        assert result.supports_rich is False
        assert result.legacy_format is False

    def test_process_format_parameter_json_flag(self):
        """Test processing format with JSON flag override."""
        result = process_format_parameter("table", json_flag=True)

        assert result.format_type == "json"
        assert result.is_json is True

    def test_process_format_parameter_invalid(self):
        """Test processing invalid format parameter."""
        with pytest.raises(typer.BadParameter, match="Unsupported format"):
            process_format_parameter("invalid_format")

    def test_process_format_parameter_custom_formats(self):
        """Test processing format with custom supported formats."""
        result = process_format_parameter(
            "yaml",
            supported_formats=["yaml", "xml", "csv"],
        )

        assert result.format_type == "yaml"
        assert result.is_json is False

    def test_process_format_parameter_rich_format(self):
        """Test processing Rich format."""
        result = process_format_parameter("rich-table")

        assert result.format_type == "rich-table"
        assert result.is_json is False
        assert result.supports_rich is True
        assert result.legacy_format is False

    def test_process_format_parameter_legacy_format(self):
        """Test processing legacy format."""
        result = process_format_parameter("table")

        assert result.format_type == "table"
        assert result.is_json is False
        assert result.supports_rich is True
        assert result.legacy_format is True

    @patch("glovebox.cli.helpers.parameter_helpers.create_output_formatter")
    def test_format_and_output_data(self, mock_create_formatter, tmp_path):
        """Test formatting and outputting data."""
        # Setup mocks
        mock_formatter = Mock()
        mock_formatter.format.return_value = '{"formatted": "data"}'
        mock_create_formatter.return_value = mock_formatter

        # Setup results
        output_file = tmp_path / "output.json"
        output_result = OutputResult(
            raw_value=str(output_file), resolved_path=output_file
        )
        format_result = FormatResult(format_type="json")

        test_data = {"test": "data"}

        with patch(
            "glovebox.cli.helpers.parameter_helpers.write_output_from_result"
        ) as mock_write:
            format_and_output_data(test_data, output_result, format_result)

            mock_formatter.format.assert_called_once_with(test_data, "json")
            mock_write.assert_called_once_with(output_result, '{"formatted": "data"}')


# =============================================================================
# Test Validation Functions
# =============================================================================


class TestValidationFunctions:
    """Test parameter validation functions."""

    def test_validate_input_file_valid(self, tmp_path):
        """Test validating a valid input file."""
        test_file = tmp_path / "test.json"
        test_file.write_text('{"test": "data"}')

        result = validate_input_file(test_file)

        assert result.is_valid is True
        assert result.error_message is None

    def test_validate_input_file_not_exists(self):
        """Test validating a non-existent input file."""
        result = validate_input_file(Path("nonexistent.json"))

        assert result.is_valid is False
        assert result.error_message is not None
        assert "does not exist" in result.error_message
        assert "Check the file path" in result.suggestions

    def test_validate_input_file_not_required_exists(self):
        """Test validating non-existent file when existence not required."""
        result = validate_input_file(Path("nonexistent.json"), must_exist=False)

        assert result.is_valid is True

    def test_validate_input_file_invalid_extension(self, tmp_path):
        """Test validating file with invalid extension."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        result = validate_input_file(test_file, allowed_extensions=[".json", ".yaml"])

        assert result.is_valid is False
        assert result.error_message is not None
        assert "Unsupported file extension" in result.error_message
        assert ".json, .yaml" in result.suggestions[0]

    def test_validate_input_file_large_size(self, tmp_path):
        """Test validating large file."""
        test_file = tmp_path / "large.json"
        # Create a file larger than 1MB
        test_file.write_text("x" * (2 * 1024 * 1024))  # 2MB

        result = validate_input_file(test_file, max_size_mb=1.0)

        assert result.is_valid is False
        assert result.error_message is not None
        assert "File too large" in result.error_message

    def test_validate_input_file_warning_size(self, tmp_path):
        """Test validating file with warning size."""
        test_file = tmp_path / "medium.json"
        # Create a file between warning and max size
        test_file.write_text("x" * (1024 * 1024))  # 1MB

        result = validate_input_file(test_file, max_size_mb=2.0)

        assert result.is_valid is True
        assert len(result.warnings) > 0
        assert "Large file detected" in result.warnings[0]

    def test_validate_input_file_directory(self, tmp_path):
        """Test validating directory instead of file."""
        result = validate_input_file(tmp_path)

        assert result.is_valid is False
        assert result.error_message is not None
        assert "not a file" in result.error_message

    def test_validate_output_path_valid(self, tmp_path):
        """Test validating valid output path."""
        output_file = tmp_path / "output.json"

        result = validate_output_path(output_file)

        assert result.is_valid is True

    def test_validate_output_path_existing_file(self, tmp_path):
        """Test validating existing output file."""
        existing_file = tmp_path / "existing.json"
        existing_file.write_text('{"existing": "data"}')

        result = validate_output_path(existing_file)

        assert result.is_valid is True
        assert len(result.warnings) > 0
        assert "already exists" in result.warnings[0]
        assert "--force" in result.suggestions[0]

    def test_validate_output_path_no_parent_dir(self, tmp_path):
        """Test validating output path with non-existent parent."""
        output_file = tmp_path / "nonexistent" / "output.json"

        result = validate_output_path(output_file, create_dirs=False)

        assert result.is_valid is False
        assert result.error_message is not None
        assert "Parent directory does not exist" in result.error_message

    @patch("pathlib.Path.mkdir")
    def test_validate_output_path_create_dirs_permission_error(
        self, mock_mkdir, tmp_path
    ):
        """Test validating output path when directory creation fails."""
        mock_mkdir.side_effect = PermissionError("Permission denied")
        output_file = tmp_path / "restricted" / "output.json"

        result = validate_output_path(output_file, create_dirs=True)

        assert result.is_valid is False
        assert result.error_message is not None
        assert "permission denied" in result.error_message

    @patch("pathlib.Path.touch")
    @patch("pathlib.Path.unlink")
    def test_validate_output_path_no_write_permission(
        self, mock_unlink, mock_touch, tmp_path
    ):
        """Test validating output path with no write permission."""
        mock_touch.side_effect = PermissionError("Permission denied")
        output_file = tmp_path / "output.json"

        result = validate_output_path(output_file)

        assert result.is_valid is False
        assert result.error_message is not None
        assert "No write permission" in result.error_message
