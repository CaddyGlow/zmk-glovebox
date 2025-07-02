"""Tests for base command classes."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
import typer
import yaml

from glovebox.cli.core.command_base import BaseCommand, IOCommand, ServiceCommand
from glovebox.cli.helpers.parameter_types import InputResult, OutputResult


class ConcreteCommand(BaseCommand):
    """Concrete implementation for testing BaseCommand."""

    def execute(self, message: str = "test") -> str:
        return f"Executed: {message}"


class ConcreteIOCommand(IOCommand):
    """Concrete implementation for testing IOCommand."""

    def execute(self, input_file: str | None = None) -> dict[str, Any]:
        if input_file:
            result = self.load_json_input(input_file)
            return {"loaded": result}
        return {"loaded": None}


class ConcreteServiceCommand(ServiceCommand):
    """Concrete implementation for testing ServiceCommand."""

    def execute(self, service_name: str = "test") -> Any:
        # Use a mock factory for testing
        mock_factory = Mock(return_value={"service": service_name})
        service = self.get_service(service_name, mock_factory)
        return service


class TestBaseCommand:
    """Test BaseCommand functionality."""

    def test_initialization(self):
        """Test command initialization."""
        cmd = ConcreteCommand()
        assert cmd.logger is not None
        assert cmd.logger.name == "ConcreteCommand"
        assert cmd._console is None  # Lazy loading

    def test_console_property(self):
        """Test themed console lazy loading."""
        cmd = ConcreteCommand()
        console = cmd.console
        assert console is not None
        assert cmd._console is console  # Cached
        assert cmd.console is console  # Same instance

    def test_handle_service_error(self):
        """Test service error handling."""
        cmd = ConcreteCommand()
        error = ValueError("Test error")

        with pytest.raises(typer.Exit) as exc_info:
            cmd.handle_service_error(error, "test operation")

        assert exc_info.value.exit_code == 1

    def test_print_operation_success(self):
        """Test success message printing."""
        cmd = ConcreteCommand()
        with (
            patch.object(cmd.console, "print_success") as mock_success,
            patch.object(cmd.console, "print_info") as mock_info,
        ):
            cmd.print_operation_success("Operation completed")
            mock_success.assert_called_once_with("Operation completed")
            mock_info.assert_not_called()

    def test_print_operation_success_with_details(self):
        """Test success message with details."""
        cmd = ConcreteCommand()
        details = {
            "files_processed": 10,
            "time_taken": "2.5s",
            "output_path": "/tmp/output",
            "none_value": None,  # Should be skipped
        }

        with (
            patch.object(cmd.console, "print_success") as mock_success,
            patch.object(cmd.console, "print_info") as mock_info,
        ):
            cmd.print_operation_success("Operation completed", details)
            mock_success.assert_called_once_with("Operation completed")
            assert mock_info.call_count == 3  # None value skipped

            # Check formatted keys
            calls = [call[0][0] for call in mock_info.call_args_list]
            assert "Files Processed: 10" in calls
            assert "Time Taken: 2.5s" in calls
            assert "Output Path: /tmp/output" in calls

    def test_execute_with_error_handling(self):
        """Test command execution with error handling decorator."""
        cmd = ConcreteCommand()
        result = cmd("custom message")
        assert result == "Executed: custom message"

    def test_abstract_execute_not_implemented(self):
        """Test that execute must be implemented."""
        with pytest.raises(TypeError):
            BaseCommand()  # Can't instantiate abstract class


class TestIOCommand:
    """Test IOCommand functionality."""

    def test_initialization(self):
        """Test IO command initialization."""
        cmd = ConcreteIOCommand()
        assert cmd.output_formatter is not None

    def test_load_input_from_file(self, tmp_path):
        """Test loading input from file."""
        cmd = ConcreteIOCommand()
        test_file = tmp_path / "test.json"
        test_data = {"key": "value", "number": 42}
        test_file.write_text(json.dumps(test_data))

        result = cmd.load_input(test_file)
        assert isinstance(result, InputResult)
        assert result.resolved_path == test_file
        assert not result.is_stdin
        assert result.data is not None

    def test_load_input_stdin(self):
        """Test loading input from stdin."""
        cmd = ConcreteIOCommand()

        # Mock the entire parameter processing chain for stdin
        mock_result = InputResult(
            raw_value="-", resolved_path=None, is_stdin=True, data='{"stdin": "data"}'
        )

        with patch(
            "glovebox.cli.core.command_base.process_input_parameter",
            return_value=mock_result,
        ):
            result = cmd.load_input("-")
            assert result.is_stdin
            assert result.data == '{"stdin": "data"}'

    def test_load_input_required_missing(self):
        """Test required input validation."""
        cmd = ConcreteIOCommand()

        with pytest.raises(typer.BadParameter, match="Input file is required"):
            cmd.load_input(None, required=True)

    def test_load_input_optional_missing(self):
        """Test optional input handling."""
        cmd = ConcreteIOCommand()
        result = cmd.load_input(None, required=False)
        assert result.raw_value is None

    def test_load_input_extension_validation(self, tmp_path):
        """Test file extension validation."""
        cmd = ConcreteIOCommand()
        test_file = tmp_path / "test.txt"
        test_file.write_text("not json")

        with pytest.raises(typer.BadParameter, match="Unsupported file extension"):
            cmd.load_input(test_file, allowed_extensions=[".json"])

    def test_load_json_input_valid(self, tmp_path):
        """Test loading valid JSON input."""
        cmd = ConcreteIOCommand()
        test_file = tmp_path / "test.json"
        test_data = {"key": "value", "nested": {"item": 1}}
        test_file.write_text(json.dumps(test_data))

        data = cmd.load_json_input(test_file)
        assert data == test_data

    def test_load_json_input_invalid(self, tmp_path):
        """Test loading invalid JSON input."""
        cmd = ConcreteIOCommand()
        test_file = tmp_path / "test.json"
        test_file.write_text("not valid json")

        with pytest.raises(ValueError, match="Invalid JSON"):
            cmd.load_json_input(test_file)

    def test_load_json_input_not_object(self, tmp_path):
        """Test JSON input that's not an object."""
        cmd = ConcreteIOCommand()
        test_file = tmp_path / "test.json"
        test_file.write_text('["array", "not", "object"]')

        with pytest.raises(ValueError, match="Expected JSON object"):
            cmd.load_json_input(test_file)

    def test_write_output_json_to_file(self, tmp_path):
        """Test writing JSON output to file."""
        cmd = ConcreteIOCommand()
        output_file = tmp_path / "output.json"
        test_data = {"result": "success", "count": 5}

        result = cmd.write_output(test_data, output_file, format="json")

        assert output_file.exists()
        assert json.loads(output_file.read_text()) == test_data
        assert result.resolved_path == output_file
        assert not result.is_stdout

    def test_write_output_yaml_to_file(self, tmp_path):
        """Test writing YAML output to file."""
        cmd = ConcreteIOCommand()
        output_file = tmp_path / "output.yaml"
        test_data = {"result": "success", "items": ["a", "b", "c"]}

        result = cmd.write_output(test_data, output_file, format="yaml")

        assert output_file.exists()
        assert yaml.safe_load(output_file.read_text()) == test_data

    def test_write_output_text_to_file(self, tmp_path):
        """Test writing text output to file."""
        cmd = ConcreteIOCommand()
        output_file = tmp_path / "output.txt"
        test_text = "Simple text output"

        result = cmd.write_output(test_text, output_file, format="text")

        assert output_file.exists()
        assert output_file.read_text() == test_text

    def test_write_output_to_stdout(self):
        """Test writing output to stdout."""
        cmd = ConcreteIOCommand()
        test_data = {"stdout": "output"}

        # We need to patch at the module level where it's imported
        with patch(
            "glovebox.cli.core.command_base.write_output_from_result"
        ) as mock_write:
            result = cmd.write_output(test_data, "-", format="json")
            assert result.is_stdout
            mock_write.assert_called_once()
            # Check that JSON was formatted
            call_args = mock_write.call_args[0]
            assert call_args[0] == result  # First arg is the result
            assert '"stdout": "output"' in call_args[1]  # Second arg is formatted JSON

    def test_write_output_create_dirs(self, tmp_path):
        """Test creating parent directories for output."""
        cmd = ConcreteIOCommand()
        output_file = tmp_path / "nested" / "dir" / "output.json"
        test_data = {"created": "dirs"}

        result = cmd.write_output(
            test_data, output_file, format="json", create_dirs=True
        )

        assert output_file.exists()
        assert output_file.parent.exists()

    def test_write_output_overwrite_prompt(self, tmp_path):
        """Test overwrite confirmation prompt."""
        cmd = ConcreteIOCommand()
        output_file = tmp_path / "existing.json"
        output_file.write_text('{"old": "data"}')

        with patch("typer.confirm", return_value=False), pytest.raises(typer.Abort):
            cmd.write_output({"new": "data"}, output_file, force_overwrite=False)

    def test_write_output_force_overwrite(self, tmp_path):
        """Test force overwrite option."""
        cmd = ConcreteIOCommand()
        output_file = tmp_path / "existing.json"
        output_file.write_text('{"old": "data"}')
        new_data = {"new": "data"}

        result = cmd.write_output(new_data, output_file, force_overwrite=True)

        assert json.loads(output_file.read_text()) == new_data

    def test_format_and_print(self):
        """Test formatting and printing data."""
        cmd = ConcreteIOCommand()
        test_data = {"key": "value"}

        with patch.object(cmd.output_formatter, "print_formatted") as mock_print:
            cmd.format_and_print(test_data, "json")
            mock_print.assert_called_once_with(test_data, "json")

    def test_validate_input_file_exists(self, tmp_path):
        """Test validating existing input file."""
        cmd = ConcreteIOCommand()
        test_file = tmp_path / "exists.json"
        test_file.write_text("{}")

        # Should not raise
        cmd.validate_input_file(test_file)

    def test_validate_input_file_not_found(self, tmp_path):
        """Test validating non-existent input file."""
        cmd = ConcreteIOCommand()
        test_file = tmp_path / "missing.json"

        with pytest.raises(typer.Exit):
            cmd.validate_input_file(test_file)

    def test_validate_input_file_is_directory(self, tmp_path):
        """Test validating directory as input file."""
        cmd = ConcreteIOCommand()

        with pytest.raises(typer.Exit):
            cmd.validate_input_file(tmp_path)

    def test_validate_output_path_new_file(self, tmp_path):
        """Test validating new output path."""
        cmd = ConcreteIOCommand()
        output_file = tmp_path / "new.json"

        # Should not raise
        cmd.validate_output_path(output_file)

    def test_validate_output_path_existing_with_confirm(self, tmp_path):
        """Test validating existing output path with confirmation."""
        cmd = ConcreteIOCommand()
        output_file = tmp_path / "existing.json"
        output_file.write_text("{}")

        with patch("typer.confirm", return_value=True):
            # Should not raise
            cmd.validate_output_path(output_file)


class TestServiceCommand:
    """Test ServiceCommand functionality."""

    def test_initialization(self):
        """Test service command initialization."""
        cmd = ConcreteServiceCommand()
        assert cmd._services == {}

    def test_get_service_creates_new(self):
        """Test creating new service instance."""
        cmd = ConcreteServiceCommand()
        mock_factory = Mock(return_value={"service": "instance"})

        service = cmd.get_service("test_service", mock_factory, "arg1", key="value")

        assert service == {"service": "instance"}
        mock_factory.assert_called_once_with("arg1", key="value")
        assert "test_service" in cmd._services

    def test_get_service_returns_cached(self):
        """Test returning cached service instance."""
        cmd = ConcreteServiceCommand()
        mock_factory = Mock(return_value={"service": "instance"})

        # Get service twice
        service1 = cmd.get_service("test_service", mock_factory)
        service2 = cmd.get_service("test_service", mock_factory)

        assert service1 is service2
        mock_factory.assert_called_once()  # Only called once

    def test_clear_services(self):
        """Test clearing cached services."""
        cmd = ConcreteServiceCommand()
        mock_factory = Mock(return_value={"service": "instance"})

        cmd.get_service("service1", mock_factory)
        cmd.get_service("service2", mock_factory)
        assert len(cmd._services) == 2

        cmd.clear_services()
        assert len(cmd._services) == 0

    def test_with_progress(self):
        """Test progress context creation."""
        cmd = ConcreteServiceCommand()

        # We need to patch where the functions are imported in the method
        with patch(
            "glovebox.cli.components.progress_config.ProgressConfig"
        ) as mock_config_class:
            mock_config = MagicMock()
            mock_config_class.return_value = mock_config

            result = cmd.with_progress("Processing", total=100)

            # Check that ProgressConfig was created with correct parameters
            mock_config_class.assert_called_once_with(
                operation_name="Processing",
                icon_mode=cmd.console.icon_mode,
            )

            # Result should be a progress context
            assert result is not None

    def test_handle_cache_error(self):
        """Test cache error handling."""
        cmd = ConcreteServiceCommand()
        error = RuntimeError("Cache unavailable")

        with patch.object(cmd.console, "print_warning") as mock_warning:
            # Should not raise
            cmd.handle_cache_error(error, "loading data")
            mock_warning.assert_called_once()

    def test_get_context_value_exists(self):
        """Test getting existing context value."""
        cmd = ConcreteServiceCommand()
        ctx = Mock(spec=typer.Context)
        ctx.obj = Mock(test_value="found")

        value = cmd.get_context_value(ctx, "test_value")
        assert value == "found"

    def test_get_context_value_missing(self):
        """Test getting missing context value."""
        cmd = ConcreteServiceCommand()
        ctx = Mock(spec=typer.Context)
        ctx.obj = Mock(spec=[])  # No attributes

        value = cmd.get_context_value(ctx, "missing_value", default="default")
        assert value == "default"

    def test_get_context_value_no_context(self):
        """Test getting value with no context."""
        cmd = ConcreteServiceCommand()

        value = cmd.get_context_value(None, "any_value", default="fallback")
        assert value == "fallback"

    def test_require_context_value_exists(self):
        """Test requiring existing context value."""
        cmd = ConcreteServiceCommand()
        ctx = Mock(spec=typer.Context)
        ctx.obj = Mock(required_value="present")

        value = cmd.require_context_value(ctx, "required_value", "Error message")
        assert value == "present"

    def test_require_context_value_missing(self):
        """Test requiring missing context value."""
        cmd = ConcreteServiceCommand()
        ctx = Mock(spec=typer.Context)
        ctx.obj = Mock(spec=[])  # No attributes

        with pytest.raises(typer.Exit) as exc_info:
            cmd.require_context_value(ctx, "missing_value", "Value not found")

        assert exc_info.value.exit_code == 1


class TestIntegration:
    """Test integration scenarios."""

    def test_io_command_full_workflow(self, tmp_path):
        """Test full IO command workflow."""

        class TestWorkflowCommand(IOCommand):
            def execute(self, input_file: Path, output_file: Path) -> None:
                # Load input
                data = self.load_json_input(input_file)

                # Process data
                data["processed"] = True
                data["item_count"] = len(data.get("items", []))

                # Write output
                self.write_output(data, output_file, format="json")

                # Print success
                self.print_operation_success(
                    "Processing completed",
                    {
                        "input": input_file,
                        "output": output_file,
                        "items": data["item_count"],
                    },
                )

        # Setup
        input_file = tmp_path / "input.json"
        output_file = tmp_path / "output.json"
        input_data = {"items": ["a", "b", "c"], "version": 1}
        input_file.write_text(json.dumps(input_data))

        # Execute
        cmd = TestWorkflowCommand()
        cmd.execute(input_file, output_file)

        # Verify
        assert output_file.exists()
        output_data = json.loads(output_file.read_text())
        assert output_data["processed"] is True
        assert output_data["item_count"] == 3
        assert output_data["items"] == ["a", "b", "c"]

    def test_service_command_with_factory_pattern(self):
        """Test service command using factory pattern."""

        class TestServiceCommand(ServiceCommand):
            def execute(self) -> dict[str, Any]:
                # Simulate getting multiple services
                layout_service = self.get_service(
                    "layout", lambda: {"type": "layout", "version": "1.0"}
                )

                firmware_service = self.get_service(
                    "firmware",
                    lambda profile: {"type": "firmware", "profile": profile},
                    "glove80",
                )

                return {
                    "layout": layout_service,
                    "firmware": firmware_service,
                    "service_count": len(self._services),
                }

        cmd = TestServiceCommand()
        result = cmd.execute()

        assert result["layout"]["type"] == "layout"
        assert result["firmware"]["profile"] == "glove80"
        assert result["service_count"] == 2

    def test_error_handling_propagation(self):
        """Test error handling through command hierarchy."""

        class ErrorCommand(BaseCommand):
            def execute(self) -> None:
                try:
                    raise ValueError("Service error")
                except Exception as e:
                    self.handle_service_error(e, "perform operation")

        cmd = ErrorCommand()

        with pytest.raises(typer.Exit) as exc_info:
            cmd()  # Call through __call__ with error handling

        assert exc_info.value.exit_code == 1
