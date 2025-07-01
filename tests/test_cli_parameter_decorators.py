"""Tests for CLI parameter decorators."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import typer

from glovebox.cli.decorators.parameters import (
    with_input_file,
    with_multiple_input_files,
    with_output_file,
    with_output_directory,
    with_format,
    with_input_output,
    with_input_output_format,
    _get_context_from_args,
    _process_input_parameter,
    _process_output_parameter,
    _process_format_parameter,
    PARAM_INPUT_RESULT_KEY,
    PARAM_OUTPUT_RESULT_KEY,
    PARAM_FORMAT_RESULT_KEY,
    PARAM_FORMATTER_KEY,
)
from glovebox.cli.helpers.parameter_types import (
    InputResult,
    OutputResult,
    FormatResult,
)


# =============================================================================
# Test Helper Functions
# =============================================================================

class TestHelperFunctions:
    """Test internal helper functions."""

    def test_get_context_from_args_in_args(self):
        """Test extracting context from args tuple."""
        ctx = Mock(spec=typer.Context)
        args = (ctx, "other_arg")
        kwargs = {}
        
        result = _get_context_from_args(args, kwargs)
        assert result == ctx

    def test_get_context_from_args_in_kwargs(self):
        """Test extracting context from kwargs."""
        ctx = Mock(spec=typer.Context)
        args = ("other_arg",)
        kwargs = {"ctx": ctx, "other_param": "value"}
        
        result = _get_context_from_args(args, kwargs)
        assert result == ctx

    def test_get_context_from_args_not_found(self):
        """Test extracting context when not present."""
        args = ("arg1", "arg2")
        kwargs = {"param": "value"}
        
        result = _get_context_from_args(args, kwargs)
        assert result is None

    def test_get_context_from_args_wrong_type(self):
        """Test extracting context with wrong type."""
        args = ("not_context",)
        kwargs = {"ctx": "also_not_context"}
        
        result = _get_context_from_args(args, kwargs)
        assert result is None

    def test_process_input_parameter_basic(self, tmp_path):
        """Test basic input parameter processing."""
        test_file = tmp_path / "test.json"
        test_file.write_text('{"test": "data"}')
        
        result = _process_input_parameter(raw_value=test_file)
        
        assert result.raw_value == test_file
        assert result.resolved_path == test_file
        assert result.is_stdin is False
        assert result.env_fallback_used is False

    def test_process_input_parameter_stdin(self):
        """Test stdin input parameter processing."""
        result = _process_input_parameter(
            raw_value="-",
            supports_stdin=True,
        )
        
        assert result.raw_value == "-"
        assert result.resolved_path is None
        assert result.is_stdin is True

    def test_process_input_parameter_env_fallback(self, tmp_path):
        """Test input parameter with environment fallback."""
        test_file = tmp_path / "env_test.json"
        test_file.write_text('{"env": "data"}')
        
        with patch.dict(os.environ, {"TEST_VAR": str(test_file)}):
            result = _process_input_parameter(
                raw_value=None,
                env_fallback="TEST_VAR",
                required=True,
            )
            
            assert result.raw_value == str(test_file)
            assert result.env_fallback_used is True

    @patch('glovebox.cli.decorators.parameters.read_json_input')
    def test_process_input_parameter_auto_read_json(self, mock_read_json, tmp_path):
        """Test input parameter with auto-read JSON."""
        test_file = tmp_path / "test.json"
        test_file.write_text('{"test": "data"}')
        mock_read_json.return_value = {"test": "data"}
        
        result = _process_input_parameter(
            raw_value=test_file,
            auto_read=True,
            read_as_json=True,
        )
        
        assert result.data == {"test": "data"}
        mock_read_json.assert_called_once_with(str(test_file))

    def test_process_output_parameter_basic(self):
        """Test basic output parameter processing."""
        result = _process_output_parameter(raw_value="output.json")
        
        assert result.raw_value == "output.json"
        assert result.resolved_path == Path("output.json")
        assert result.is_stdout is False

    def test_process_output_parameter_stdout(self):
        """Test stdout output parameter processing."""
        result = _process_output_parameter(
            raw_value="-",
            supports_stdout=True,
        )
        
        assert result.raw_value == "-"
        assert result.is_stdout is True

    def test_process_output_parameter_smart_default(self):
        """Test output parameter with smart defaults."""
        result = _process_output_parameter(
            raw_value=None,
            smart_defaults=True,
        )
        
        assert result.raw_value is None
        assert result.smart_default_used is True
        assert result.resolved_path == Path.cwd() / "output.txt"

    def test_process_format_parameter_basic(self):
        """Test basic format parameter processing."""
        result = _process_format_parameter(format_value="json")
        
        assert result.format_type == "json"
        assert result.is_json is True
        assert result.supports_rich is False

    def test_process_format_parameter_json_flag(self):
        """Test format parameter with JSON flag."""
        result = _process_format_parameter(
            format_value="table",
            json_flag=True,
        )
        
        assert result.format_type == "json"
        assert result.is_json is True

    def test_process_format_parameter_rich(self):
        """Test Rich format parameter processing."""
        result = _process_format_parameter(format_value="rich-table")
        
        assert result.format_type == "rich-table"
        assert result.supports_rich is True
        assert result.legacy_format is False


# =============================================================================
# Test Input Decorators
# =============================================================================

class TestInputDecorators:
    """Test input parameter decorators."""

    def test_with_input_file_decorator(self, tmp_path):
        """Test with_input_file decorator."""
        test_file = tmp_path / "test.json"
        test_file.write_text('{"test": "data"}')
        
        # Create mock context
        ctx = Mock(spec=typer.Context)
        ctx.obj = Mock()
        
        @with_input_file(param_name="input_file")
        def test_command(ctx: typer.Context, input_file: str):
            return "success"
        
        # Mock the context storage
        stored_result = None
        def mock_setattr(key, value):
            nonlocal stored_result
            if key == PARAM_INPUT_RESULT_KEY:
                stored_result = value
        
        ctx.obj.setattr = mock_setattr
        
        # Call the decorated function
        result = test_command(ctx, input_file=str(test_file))
        
        assert result == "success"
        assert stored_result is not None
        assert stored_result.raw_value == str(test_file)
        assert stored_result.resolved_path == test_file

    def test_with_input_file_decorator_no_context(self):
        """Test with_input_file decorator without context."""
        @with_input_file(param_name="input_file")
        def test_command(input_file: str):
            return "no_context"
        
        # Call without context - should pass through
        result = test_command(input_file="test.json")
        assert result == "no_context"

    def test_with_input_file_decorator_error_handling(self):
        """Test with_input_file decorator error handling."""
        ctx = Mock(spec=typer.Context)
        ctx.obj = Mock()
        
        @with_input_file(param_name="input_file", required=True)
        def test_command(ctx: typer.Context, input_file: str):
            return "success"
        
        # Should raise typer.Exit on error
        with pytest.raises(typer.Exit):
            test_command(ctx, input_file="nonexistent.json")

    def test_with_multiple_input_files_decorator(self, tmp_path):
        """Test with_multiple_input_files decorator."""
        test_file1 = tmp_path / "test1.json"
        test_file2 = tmp_path / "test2.json"
        test_file1.write_text('{"test1": "data"}')
        test_file2.write_text('{"test2": "data"}')
        
        ctx = Mock(spec=typer.Context)
        ctx.obj = Mock()
        
        @with_multiple_input_files(param_name="input_files")
        def test_command(ctx: typer.Context, input_files: list[str]):
            return "success"
        
        stored_results = None
        def mock_setattr(key, value):
            nonlocal stored_results
            if key == f"{PARAM_INPUT_RESULT_KEY}_multiple":
                stored_results = value
        
        ctx.obj.setattr = mock_setattr
        
        result = test_command(ctx, input_files=[test_file1, test_file2])
        
        assert result == "success"
        assert stored_results is not None
        assert len(stored_results) == 2
        assert stored_results[0].resolved_path == test_file1
        assert stored_results[1].resolved_path == test_file2


# =============================================================================
# Test Output Decorators
# =============================================================================

class TestOutputDecorators:
    """Test output parameter decorators."""

    def test_with_output_file_decorator(self):
        """Test with_output_file decorator."""
        ctx = Mock(spec=typer.Context)
        ctx.obj = Mock()
        
        @with_output_file(param_name="output")
        def test_command(ctx: typer.Context, output: str):
            return "success"
        
        stored_result = None
        def mock_setattr(key, value):
            nonlocal stored_result
            if key == PARAM_OUTPUT_RESULT_KEY:
                stored_result = value
        
        ctx.obj.setattr = mock_setattr
        
        result = test_command(ctx, output="output.json")
        
        assert result == "success"
        assert stored_result is not None
        assert stored_result.raw_value == "output.json"
        assert stored_result.resolved_path == Path("output.json")

    def test_with_output_file_decorator_stdout(self):
        """Test with_output_file decorator with stdout."""
        ctx = Mock(spec=typer.Context)
        ctx.obj = Mock()
        
        @with_output_file(param_name="output", supports_stdout=True)
        def test_command(ctx: typer.Context, output: str):
            return "success"
        
        stored_result = None
        def mock_setattr(key, value):
            nonlocal stored_result
            if key == PARAM_OUTPUT_RESULT_KEY:
                stored_result = value
        
        ctx.obj.setattr = mock_setattr
        
        result = test_command(ctx, output="-")
        
        assert result == "success"
        assert stored_result is not None
        assert stored_result.raw_value == "-"
        assert stored_result.is_stdout is True

    def test_with_output_directory_decorator(self, tmp_path):
        """Test with_output_directory decorator."""
        ctx = Mock(spec=typer.Context)
        ctx.obj = Mock()
        
        @with_output_directory(param_name="output_dir")
        def test_command(ctx: typer.Context, output_dir: str):
            return "success"
        
        stored_result = None
        def mock_setattr(key, value):
            nonlocal stored_result
            if key == PARAM_OUTPUT_RESULT_KEY:
                stored_result = value
        
        ctx.obj.setattr = mock_setattr
        
        result = test_command(ctx, output_dir=str(tmp_path))
        
        assert result == "success"
        assert stored_result is not None
        assert stored_result.resolved_path == tmp_path

    def test_with_output_directory_decorator_create_dirs(self, tmp_path):
        """Test with_output_directory decorator creating directories."""
        ctx = Mock(spec=typer.Context)
        ctx.obj = Mock()
        
        @with_output_directory(param_name="output_dir", create_dirs=True)
        def test_command(ctx: typer.Context, output_dir: str):
            return "success"
        
        stored_result = None
        def mock_setattr(key, value):
            nonlocal stored_result
            if key == PARAM_OUTPUT_RESULT_KEY:
                stored_result = value
        
        ctx.obj.setattr = mock_setattr
        
        new_dir = tmp_path / "new_directory"
        result = test_command(ctx, output_dir=str(new_dir))
        
        assert result == "success"
        assert new_dir.exists()
        assert stored_result.resolved_path == new_dir


# =============================================================================
# Test Format Decorators
# =============================================================================

class TestFormatDecorators:
    """Test format parameter decorators."""

    def test_with_format_decorator(self):
        """Test with_format decorator."""
        ctx = Mock(spec=typer.Context)
        ctx.obj = Mock()
        
        @with_format(format_param="output_format")
        def test_command(ctx: typer.Context, output_format: str):
            return "success"
        
        stored_format_result = None
        stored_formatter = None
        
        def mock_setattr(key, value):
            nonlocal stored_format_result, stored_formatter
            if key == PARAM_FORMAT_RESULT_KEY:
                stored_format_result = value
            elif key == PARAM_FORMATTER_KEY:
                stored_formatter = value
        
        ctx.obj.setattr = mock_setattr
        
        with patch('glovebox.cli.decorators.parameters.create_output_formatter') as mock_create:
            mock_formatter = Mock()
            mock_create.return_value = mock_formatter
            
            result = test_command(ctx, output_format="json")
            
            assert result == "success"
            assert stored_format_result is not None
            assert stored_format_result.format_type == "json"
            assert stored_format_result.is_json is True
            assert stored_formatter == mock_formatter

    def test_with_format_decorator_json_param(self):
        """Test with_format decorator with JSON parameter."""
        ctx = Mock(spec=typer.Context)
        ctx.obj = Mock()
        
        @with_format(format_param="output_format", json_param="json_flag")
        def test_command(ctx: typer.Context, output_format: str, json_flag: bool):
            return "success"
        
        stored_result = None
        def mock_setattr(key, value):
            nonlocal stored_result
            if key == PARAM_FORMAT_RESULT_KEY:
                stored_result = value
        
        ctx.obj.setattr = mock_setattr
        
        with patch('glovebox.cli.decorators.parameters.create_output_formatter'):
            result = test_command(ctx, output_format="table", json_flag=True)
            
            assert result == "success"
            assert stored_result.format_type == "json"
            assert stored_result.is_json is True

    def test_with_format_decorator_no_formatter(self):
        """Test with_format decorator without creating formatter."""
        ctx = Mock(spec=typer.Context)
        ctx.obj = Mock()
        
        @with_format(format_param="output_format", create_formatter=False)
        def test_command(ctx: typer.Context, output_format: str):
            return "success"
        
        stored_formatter = None
        def mock_setattr(key, value):
            nonlocal stored_formatter
            if key == PARAM_FORMATTER_KEY:
                stored_formatter = value
        
        ctx.obj.setattr = mock_setattr
        
        result = test_command(ctx, output_format="json")
        
        assert result == "success"
        assert stored_formatter is None


# =============================================================================
# Test Combined Decorators
# =============================================================================

class TestCombinedDecorators:
    """Test combined parameter decorators."""

    def test_with_input_output_decorator(self, tmp_path):
        """Test with_input_output combined decorator."""
        test_file = tmp_path / "input.json"
        test_file.write_text('{"test": "data"}')
        
        ctx = Mock(spec=typer.Context)
        ctx.obj = Mock()
        
        @with_input_output(input_param="input_file", output_param="output")
        def test_command(ctx: typer.Context, input_file: str, output: str):
            return "success"
        
        stored_input = None
        stored_output = None
        
        def mock_setattr(key, value):
            nonlocal stored_input, stored_output
            if key == PARAM_INPUT_RESULT_KEY:
                stored_input = value
            elif key == PARAM_OUTPUT_RESULT_KEY:
                stored_output = value
        
        ctx.obj.setattr = mock_setattr
        
        result = test_command(ctx, input_file=str(test_file), output="output.json")
        
        assert result == "success"
        assert stored_input is not None
        assert stored_input.resolved_path == test_file
        assert stored_output is not None
        assert stored_output.resolved_path == Path("output.json")

    def test_with_input_output_format_decorator(self, tmp_path):
        """Test with_input_output_format combined decorator."""
        test_file = tmp_path / "input.json"
        test_file.write_text('{"test": "data"}')
        
        ctx = Mock(spec=typer.Context)
        ctx.obj = Mock()
        
        @with_input_output_format(
            input_param="input_file",
            output_param="output",
            format_param="output_format",
        )
        def test_command(ctx: typer.Context, input_file: str, output: str, output_format: str):
            return "success"
        
        stored_input = None
        stored_output = None
        stored_format = None
        
        def mock_setattr(key, value):
            nonlocal stored_input, stored_output, stored_format
            if key == PARAM_INPUT_RESULT_KEY:
                stored_input = value
            elif key == PARAM_OUTPUT_RESULT_KEY:
                stored_output = value
            elif key == PARAM_FORMAT_RESULT_KEY:
                stored_format = value
        
        ctx.obj.setattr = mock_setattr
        
        with patch('glovebox.cli.decorators.parameters.create_output_formatter'):
            result = test_command(
                ctx,
                input_file=str(test_file),
                output="output.json",
                output_format="json",
            )
            
            assert result == "success"
            assert stored_input is not None
            assert stored_output is not None
            assert stored_format is not None
            assert stored_format.format_type == "json"


# =============================================================================
# Test Error Handling
# =============================================================================

class TestErrorHandling:
    """Test decorator error handling."""

    def test_input_decorator_file_not_found_error(self):
        """Test input decorator with file not found error."""
        ctx = Mock(spec=typer.Context)
        ctx.obj = Mock()
        
        @with_input_file(param_name="input_file")
        def test_command(ctx: typer.Context, input_file: str):
            return "success"
        
        with pytest.raises(typer.Exit):
            test_command(ctx, input_file="nonexistent.json")

    def test_output_decorator_permission_error(self, tmp_path):
        """Test output decorator with permission error."""
        ctx = Mock(spec=typer.Context)
        ctx.obj = Mock()
        
        @with_output_directory(param_name="output_dir", create_dirs=False)
        def test_command(ctx: typer.Context, output_dir: str):
            return "success"
        
        nonexistent_dir = tmp_path / "nonexistent" / "deep"
        
        with pytest.raises(typer.Exit):
            test_command(ctx, output_dir=str(nonexistent_dir))

    def test_format_decorator_invalid_format_error(self):
        """Test format decorator with invalid format error."""
        ctx = Mock(spec=typer.Context)
        ctx.obj = Mock()
        
        @with_format(format_param="output_format")
        def test_command(ctx: typer.Context, output_format: str):
            return "success"
        
        with pytest.raises(typer.Exit):
            test_command(ctx, output_format="invalid_format")

    @patch('glovebox.cli.decorators.parameters.logger')
    def test_decorator_logging_on_error(self, mock_logger):
        """Test that decorators log errors appropriately."""
        ctx = Mock(spec=typer.Context)
        ctx.obj = Mock()
        
        @with_input_file(param_name="input_file")
        def test_command(ctx: typer.Context, input_file: str):
            return "success"
        
        with pytest.raises(typer.Exit):
            test_command(ctx, input_file="nonexistent.json")
        
        # Verify error was logged
        mock_logger.error.assert_called()
        error_call = mock_logger.error.call_args
        assert "Input parameter processing failed" in error_call[0][0]


# =============================================================================
# Test Integration Scenarios
# =============================================================================

class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_file_transformation_workflow(self, tmp_path):
        """Test a complete file transformation workflow."""
        input_file = tmp_path / "input.json"
        output_file = tmp_path / "output.json"
        input_file.write_text('{"input": "data"}')
        
        ctx = Mock(spec=typer.Context)
        ctx.obj = Mock()
        
        @with_input_output_format(
            input_param="input_file",
            output_param="output",
            format_param="output_format",
        )
        def transform_command(ctx: typer.Context, input_file: str, output: str, output_format: str):
            # This would contain actual transformation logic
            return "transformed"
        
        results = {}
        def mock_setattr(key, value):
            results[key] = value
        
        ctx.obj.setattr = mock_setattr
        
        with patch('glovebox.cli.decorators.parameters.create_output_formatter'):
            result = transform_command(
                ctx,
                input_file=str(input_file),
                output=str(output_file),
                output_format="json",
            )
            
            assert result == "transformed"
            assert PARAM_INPUT_RESULT_KEY in results
            assert PARAM_OUTPUT_RESULT_KEY in results
            assert PARAM_FORMAT_RESULT_KEY in results
            
            input_result = results[PARAM_INPUT_RESULT_KEY]
            output_result = results[PARAM_OUTPUT_RESULT_KEY]
            format_result = results[PARAM_FORMAT_RESULT_KEY]
            
            assert input_result.resolved_path == input_file
            assert output_result.resolved_path == output_file
            assert format_result.format_type == "json"

    def test_stdin_stdout_workflow(self):
        """Test stdin to stdout workflow."""
        ctx = Mock(spec=typer.Context)
        ctx.obj = Mock()
        
        @with_input_output(
            input_param="input_file",
            output_param="output",
            supports_stdin=True,
            supports_stdout=True,
        )
        def pipe_command(ctx: typer.Context, input_file: str, output: str):
            return "piped"
        
        results = {}
        def mock_setattr(key, value):
            results[key] = value
        
        ctx.obj.setattr = mock_setattr
        
        result = pipe_command(ctx, input_file="-", output="-")
        
        assert result == "piped"
        
        input_result = results[PARAM_INPUT_RESULT_KEY]
        output_result = results[PARAM_OUTPUT_RESULT_KEY]
        
        assert input_result.is_stdin is True
        assert output_result.is_stdout is True

    def test_environment_variable_workflow(self, tmp_path):
        """Test workflow with environment variable fallback."""
        input_file = tmp_path / "env_input.json"
        input_file.write_text('{"env": "data"}')
        
        ctx = Mock(spec=typer.Context)
        ctx.obj = Mock()
        
        @with_input_file(
            param_name="input_file",
            env_fallback="GLOVEBOX_JSON_FILE",
        )
        def env_command(ctx: typer.Context, input_file: str):
            return "env_success"
        
        stored_result = None
        def mock_setattr(key, value):
            nonlocal stored_result
            if key == PARAM_INPUT_RESULT_KEY:
                stored_result = value
        
        ctx.obj.setattr = mock_setattr
        
        with patch.dict(os.environ, {"GLOVEBOX_JSON_FILE": str(input_file)}):
            result = env_command(ctx, input_file=None)
            
            assert result == "env_success"
            assert stored_result is not None
            assert stored_result.env_fallback_used is True
            assert stored_result.resolved_path == input_file