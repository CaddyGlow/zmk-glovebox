"""Tests for CLI parameter type definitions."""

from __future__ import annotations

from pathlib import Path

import pytest

from glovebox.cli.helpers.parameter_types import (
    FormatResult,
    InputResult,
    OutputResult,
    ValidationResult,
    # Parameter type annotations are tested via usage in decorators
)


class TestInputResult:
    """Test InputResult class."""

    def test_input_result_init(self):
        """Test InputResult initialization."""
        result = InputResult(
            raw_value="test.json",
            resolved_path=Path("test.json"),
            is_stdin=False,
            env_fallback_used=False,
            data=None,
        )

        assert result.raw_value == "test.json"
        assert result.resolved_path == Path("test.json")
        assert result.is_stdin is False
        assert result.env_fallback_used is False
        assert result.data is None

    def test_input_result_stdin(self):
        """Test InputResult for stdin input."""
        result = InputResult(
            raw_value="-",
            resolved_path=None,
            is_stdin=True,
            env_fallback_used=False,
            data='{"test": "data"}',
        )

        assert result.raw_value == "-"
        assert result.resolved_path is None
        assert result.is_stdin is True
        assert result.env_fallback_used is False
        assert result.data == '{"test": "data"}'

    def test_input_result_env_fallback(self):
        """Test InputResult with environment fallback."""
        result = InputResult(
            raw_value="from_env.json",
            resolved_path=Path("from_env.json"),
            is_stdin=False,
            env_fallback_used=True,
            data=None,
        )

        assert result.raw_value == "from_env.json"
        assert result.resolved_path == Path("from_env.json")
        assert result.is_stdin is False
        assert result.env_fallback_used is True
        assert result.data is None


class TestOutputResult:
    """Test OutputResult class."""

    def test_output_result_init(self):
        """Test OutputResult initialization."""
        template_vars = {"name": "test", "ext": "json"}
        result = OutputResult(
            raw_value="output.json",
            resolved_path=Path("output.json"),
            is_stdout=False,
            smart_default_used=False,
            template_vars=template_vars,
        )

        assert result.raw_value == "output.json"
        assert result.resolved_path == Path("output.json")
        assert result.is_stdout is False
        assert result.smart_default_used is False
        assert result.template_vars == template_vars

    def test_output_result_stdout(self):
        """Test OutputResult for stdout output."""
        result = OutputResult(
            raw_value="-",
            resolved_path=None,
            is_stdout=True,
            smart_default_used=False,
        )

        assert result.raw_value == "-"
        assert result.resolved_path is None
        assert result.is_stdout is True
        assert result.smart_default_used is False
        assert result.template_vars == {}

    def test_output_result_smart_default(self):
        """Test OutputResult with smart defaults."""
        result = OutputResult(
            raw_value=None,
            resolved_path=Path("smart_default.json"),
            is_stdout=False,
            smart_default_used=True,
            template_vars={"type": "layout"},
        )

        assert result.raw_value is None
        assert result.resolved_path == Path("smart_default.json")
        assert result.is_stdout is False
        assert result.smart_default_used is True
        assert result.template_vars == {"type": "layout"}


class TestFormatResult:
    """Test FormatResult class."""

    def test_format_result_json(self):
        """Test FormatResult for JSON format."""
        result = FormatResult(
            format_type="json",
            is_json=True,
            supports_rich=False,
            legacy_format=False,
        )

        assert result.format_type == "json"
        assert result.is_json is True
        assert result.supports_rich is False
        assert result.legacy_format is False

    def test_format_result_rich_table(self):
        """Test FormatResult for rich-table format."""
        result = FormatResult(
            format_type="rich-table",
            is_json=False,
            supports_rich=True,
            legacy_format=False,
        )

        assert result.format_type == "rich-table"
        assert result.is_json is False
        assert result.supports_rich is True
        assert result.legacy_format is False

    def test_format_result_legacy_table(self):
        """Test FormatResult for legacy table format."""
        result = FormatResult(
            format_type="table",
            is_json=False,
            supports_rich=True,
            legacy_format=True,
        )

        assert result.format_type == "table"
        assert result.is_json is False
        assert result.supports_rich is True
        assert result.legacy_format is True

    def test_format_result_defaults(self):
        """Test FormatResult with default values."""
        result = FormatResult(format_type="text")

        assert result.format_type == "text"
        assert result.is_json is False
        assert result.supports_rich is True
        assert result.legacy_format is False


class TestValidationResult:
    """Test ValidationResult class."""

    def test_validation_result_valid(self):
        """Test ValidationResult for valid input."""
        result = ValidationResult(
            is_valid=True,
            error_message=None,
            warnings=["Warning message"],
            suggestions=["Suggestion"],
        )

        assert result.is_valid is True
        assert result.error_message is None
        assert result.warnings == ["Warning message"]
        assert result.suggestions == ["Suggestion"]

    def test_validation_result_invalid(self):
        """Test ValidationResult for invalid input."""
        result = ValidationResult(
            is_valid=False,
            error_message="File not found",
            warnings=None,
            suggestions=["Check file path"],
        )

        assert result.is_valid is False
        assert result.error_message == "File not found"
        assert result.warnings == []
        assert result.suggestions == ["Check file path"]

    def test_validation_result_defaults(self):
        """Test ValidationResult with default values."""
        result = ValidationResult(is_valid=True)

        assert result.is_valid is True
        assert result.error_message is None
        assert result.warnings == []
        assert result.suggestions == []

    def test_validation_result_none_lists_to_empty(self):
        """Test that None lists are converted to empty lists."""
        result = ValidationResult(
            is_valid=False,
            error_message="Error",
            warnings=None,
            suggestions=None,
        )

        assert result.warnings == []
        assert result.suggestions == []


# =============================================================================
# Integration Tests for Parameter Type Usage
# =============================================================================


class TestParameterTypeIntegration:
    """Test parameter types in realistic usage scenarios."""

    def test_input_result_file_processing_flow(self):
        """Test complete input file processing flow."""
        # Simulate processing a file input
        result = InputResult(
            raw_value="layout.json",
            resolved_path=Path("layout.json"),
            is_stdin=False,
            env_fallback_used=False,
            data='{"name": "test layout"}',
        )

        # Verify file processing workflow
        assert not result.is_stdin
        assert result.resolved_path is not None
        assert result.data is not None
        assert isinstance(result.data, str)

    def test_input_result_stdin_processing_flow(self):
        """Test complete stdin processing flow."""
        # Simulate processing stdin input
        result = InputResult(
            raw_value="-",
            resolved_path=None,
            is_stdin=True,
            env_fallback_used=False,
            data='{"piped": "data"}',
        )

        # Verify stdin processing workflow
        assert result.is_stdin
        assert result.resolved_path is None
        assert result.data is not None

    def test_output_result_file_writing_flow(self):
        """Test complete output file writing flow."""
        # Simulate output file processing
        result = OutputResult(
            raw_value="output.json",
            resolved_path=Path("output.json"),
            is_stdout=False,
            smart_default_used=False,
        )

        # Verify file writing workflow
        assert not result.is_stdout
        assert result.resolved_path is not None
        assert result.resolved_path.name == "output.json"

    def test_output_result_stdout_flow(self):
        """Test complete stdout output flow."""
        # Simulate stdout output processing
        result = OutputResult(
            raw_value="-",
            resolved_path=None,
            is_stdout=True,
            smart_default_used=False,
        )

        # Verify stdout workflow
        assert result.is_stdout
        assert result.resolved_path is None

    def test_format_result_json_flow(self):
        """Test complete JSON formatting flow."""
        # Simulate JSON format processing
        result = FormatResult(
            format_type="json",
            is_json=True,
            supports_rich=False,
            legacy_format=False,
        )

        # Verify JSON formatting workflow
        assert result.is_json
        assert not result.supports_rich
        assert result.format_type == "json"

    def test_format_result_rich_flow(self):
        """Test complete Rich formatting flow."""
        # Simulate Rich format processing
        result = FormatResult(
            format_type="rich-table",
            is_json=False,
            supports_rich=True,
            legacy_format=False,
        )

        # Verify Rich formatting workflow
        assert not result.is_json
        assert result.supports_rich
        assert result.format_type.startswith("rich-")

    def test_validation_result_error_flow(self):
        """Test complete validation error flow."""
        # Simulate validation error
        result = ValidationResult(
            is_valid=False,
            error_message="Invalid file format",
            warnings=["File size is large"],
            suggestions=["Use a smaller file", "Check file format"],
        )

        # Verify error handling workflow
        assert not result.is_valid
        assert result.error_message is not None
        assert len(result.warnings) > 0
        assert len(result.suggestions) > 0

    def test_validation_result_success_with_warnings_flow(self):
        """Test validation success with warnings."""
        # Simulate successful validation with warnings
        result = ValidationResult(
            is_valid=True,
            error_message=None,
            warnings=["File is very large", "Consider using compression"],
            suggestions=[],
        )

        # Verify success with warnings workflow
        assert result.is_valid
        assert result.error_message is None
        assert len(result.warnings) > 0
        assert len(result.suggestions) == 0
