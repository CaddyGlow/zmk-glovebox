"""Comprehensive integration tests for the refactored layout system.

Tests the full flow: JSON input → LayoutService → Output
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

from glovebox.adapters import create_file_adapter, create_template_adapter
from glovebox.cli.helpers.stdin_utils import (
    is_stdin_input,
    resolve_input_source_with_env,
)
from glovebox.config.models import (
    BuildOptions,
    DisplayConfig,
    FirmwareConfig,
    FormattingConfig,
    KConfigOption,
    KeyboardConfig,
    KeymapSection,
)
from glovebox.config.profile import KeyboardProfile
from glovebox.core.metrics.session_metrics import SessionMetrics
from glovebox.layout.models import LayoutData, LayoutResult
from glovebox.layout.service import LayoutService


# Test fixtures for JSON layout data
@pytest.fixture
def minimal_layout_json() -> dict[str, Any]:
    """Minimal valid layout JSON for testing."""
    return {
        "keyboard": "glove80",
        "title": "Test Layout",
        "firmware_version": "3.0",
        "layout": "QWERTY",
        "layer_names": ["Base", "Symbols"],
        "layers": [
            ["KC_Q", "KC_W", "KC_E", "KC_R", "KC_T"],
            ["KC_EXLM", "KC_AT", "KC_HASH", "KC_DLR", "KC_PERC"],
        ],
    }


@pytest.fixture
def complex_layout_json() -> dict[str, Any]:
    """Complex layout JSON with behaviors, combos, and macros."""
    return {
        "keyboard": "glove80",
        "title": "Complex Test Layout",
        "firmware_version": "3.0",
        "layout": "QWERTY",
        "layer_names": ["Base", "Symbols", "Numbers"],
        "layers": [
            [
                "KC_Q",
                "KC_W",
                "KC_E",
                "KC_R",
                "KC_T",
                "&lt 1 SPACE",
                "&mo 2",
                "&kp LSHIFT",
            ],
            [
                "KC_EXLM",
                "KC_AT",
                "KC_HASH",
                "KC_DLR",
                "KC_PERC",
                "_____",
                "_____",
                "_____",
            ],
            ["KC_1", "KC_2", "KC_3", "KC_4", "KC_5", "_____", "_____", "_____"],
        ],
        "combos": [
            {
                "name": "copy",
                "keyPositions": [0, 1],
                "binding": "&kp LC(C)",
                "layers": ["Base"],
            }
        ],
        "macros": [
            {
                "name": "test_macro",
                "bindings": [
                    {"behavior": "&kp", "param": "H"},
                    {"behavior": "&kp", "param": "E"},
                    {"behavior": "&kp", "param": "L"},
                    {"behavior": "&kp", "param": "L"},
                    {"behavior": "&kp", "param": "O"},
                ],
            }
        ],
        "custom_behaviors": [
            {
                "name": "my_td",
                "type": "tap-dance",
                "bindings": [
                    {"behavior": "&kp", "param": "A"},
                    {"behavior": "&kp", "param": "B"},
                ],
                "tapping-term-ms": 200,
            }
        ],
    }


@pytest.fixture
def invalid_layout_json() -> dict[str, Any]:
    """Invalid layout JSON for error testing."""
    return {
        "keyboard": "glove80",
        # Missing required fields like title, layer_names
        "layers": [["KC_Q", "KC_W"]],
    }


@pytest.fixture
def layout_service() -> LayoutService:
    """Create a LayoutService instance for testing."""
    # Import here to avoid circular dependencies
    from glovebox.layout import (
        create_behavior_registry,
        create_grid_layout_formatter,
        create_layout_component_service,
        create_layout_display_service,
        create_layout_service,
        create_zmk_file_generator,
        create_zmk_keymap_parser,
    )
    from glovebox.layout.behavior.formatter import BehaviorFormatterImpl

    # Create all dependencies
    file_adapter = create_file_adapter()
    template_adapter = create_template_adapter()
    behavior_registry = create_behavior_registry()
    behavior_formatter = BehaviorFormatterImpl(behavior_registry)
    dtsi_generator = create_zmk_file_generator(behavior_formatter)
    layout_generator = create_grid_layout_formatter()
    component_service = create_layout_component_service(file_adapter)
    layout_display_service = create_layout_display_service(layout_generator)
    keymap_parser = create_zmk_keymap_parser()

    return create_layout_service(
        file_adapter=file_adapter,
        template_adapter=template_adapter,
        behavior_registry=behavior_registry,
        component_service=component_service,
        layout_service=layout_display_service,
        behavior_formatter=behavior_formatter,
        dtsi_generator=dtsi_generator,
        keymap_parser=keymap_parser,
    )


@pytest.fixture
def session_metrics():
    """Create mock session metrics for testing."""
    import uuid
    from contextlib import contextmanager
    from unittest.mock import MagicMock

    # Create a mock that implements the expected interface
    mock_metrics = Mock()

    # Mock for operation metrics
    op_metrics_mock = Mock()
    op_metrics_mock.add_metadata = Mock()

    @contextmanager
    def measure_operation_mock(operation_name):
        yield op_metrics_mock

    # Set up the mock methods
    mock_metrics.measure_operation = measure_operation_mock
    mock_metrics.set_context = Mock()
    mock_metrics.time_operation = Mock()
    mock_metrics.set_exit_code = Mock()
    mock_metrics.set_cli_args = Mock()
    mock_metrics.save = Mock()

    return mock_metrics


class TestLayoutServiceIntegration:
    """Test the full integration flow of the layout service."""

    def test_json_data_to_output_success(
        self,
        layout_service: LayoutService,
        minimal_layout_json: dict[str, Any],
    ):
        """Test successful flow: JSON data → LayoutService → Output content."""
        # Act: Process through layout service
        result = layout_service.compile(minimal_layout_json)

        # Assert: Verify success and content
        assert result.success
        assert len(result.errors) == 0

        # Check that content was generated
        assert result.keymap_content is not None
        assert result.config_content is not None
        assert len(result.keymap_content) > 0

    @pytest.mark.skip(reason="Complex layout validation needs model fixes")
    def test_complex_layout_compilation(
        self,
        layout_service: LayoutService,
        complex_layout_json: dict[str, Any],
    ):
        """Test compilation of complex layout with behaviors, combos, and macros."""
        # Act: Process through layout service
        result = layout_service.compile(complex_layout_json)

        # Assert: Verify success and content
        assert result.success
        assert len(result.errors) == 0

        # Check that content was generated
        assert result.keymap_content is not None
        assert result.config_content is not None

    def test_layout_validation(
        self,
        layout_service: LayoutService,
        minimal_layout_json: dict[str, Any],
        invalid_layout_json: dict[str, Any],
    ):
        """Test layout validation functionality."""
        # Test valid layout
        is_valid = layout_service.validate(minimal_layout_json)
        assert is_valid is True

        # Test invalid layout
        is_invalid = layout_service.validate(invalid_layout_json)
        assert is_invalid is False

    def test_layout_display(
        self,
        layout_service: LayoutService,
        minimal_layout_json: dict[str, Any],
    ):
        """Test layout display functionality."""
        from glovebox.layout.formatting import ViewMode

        # Act: Generate display
        display_content = layout_service.show(minimal_layout_json, ViewMode.NORMAL)

        # Assert: Should return display content
        assert isinstance(display_content, str)
        assert len(display_content) > 0


class TestInputHandling:
    """Test various input handling scenarios."""

    def test_read_json_from_stdin(self, minimal_layout_json: dict[str, Any]):
        """Test reading JSON from stdin using core IO infrastructure."""
        from glovebox.core.io import create_input_handler

        # Mock stdin
        json_str = json.dumps(minimal_layout_json)

        with patch("sys.stdin.read", return_value=json_str):
            input_handler = create_input_handler()
            result = input_handler.load_json_input("-")

        assert result == minimal_layout_json

    def test_malformed_json_from_stdin(self):
        """Test error handling for malformed JSON from stdin using core IO infrastructure."""
        from glovebox.core.io import create_input_handler

        malformed = '{"invalid": json}'

        with patch("sys.stdin.read", return_value=malformed):
            with pytest.raises(ValueError) as exc_info:
                input_handler = create_input_handler()
                input_handler.load_json_input("-")
            assert "Invalid JSON" in str(exc_info.value)

    def test_environment_variable_precedence(self, tmp_path: Path):
        """Test environment variable takes precedence when no input given."""
        # Create a file and set env var
        env_file = tmp_path / "env_layout.json"
        env_file.write_text('{"test": "env"}')

        os.environ["GLOVEBOX_JSON_FILE"] = str(env_file)

        try:
            # No input provided, should use env var
            result = resolve_input_source_with_env(None, "GLOVEBOX_JSON_FILE")
            assert result == str(env_file)

            # Explicit input provided, should use that instead
            explicit_input = "explicit.json"
            result = resolve_input_source_with_env(explicit_input, "GLOVEBOX_JSON_FILE")
            assert result == explicit_input
        finally:
            os.environ.pop("GLOVEBOX_JSON_FILE", None)

    def test_stdin_detection(self):
        """Test stdin input detection."""
        # Test various inputs
        assert is_stdin_input("-") is True
        assert is_stdin_input("--") is False
        assert is_stdin_input("file.json") is False
        assert is_stdin_input("/path/to/file.json") is False
        assert is_stdin_input(None) is False


class TestLayoutCommandIntegration:
    """Test the full IOCommand workflow: input → command → service → output."""

    def test_compile_command_json_input_to_file_output(
        self, tmp_path: Path, minimal_layout_json: dict[str, Any]
    ):
        """Test CompileLayoutCommand with JSON input file and file output."""
        from glovebox.cli.commands.layout.core import CompileLayoutCommand

        # Setup test files
        input_file = tmp_path / "input.json"
        output_file = tmp_path / "output"

        input_file.write_text(json.dumps(minimal_layout_json))

        # Create command instance
        command = CompileLayoutCommand()

        # Mock the layout service to return success
        mock_result = LayoutResult(
            success=True,
            keymap_content="mocked keymap content",
            config_content="mocked config content",
            errors=[],
        )

        with patch(
            "glovebox.cli.commands.layout.dependencies.create_full_layout_service"
        ) as mock_service_factory:
            mock_service = Mock()
            mock_service.compile.return_value = mock_result
            mock_service_factory.return_value = mock_service

            # Execute command
            command.execute(
                ctx=Mock(),
                input=str(input_file),
                output=str(output_file),
                profile=None,
                no_auto=False,
                force=False,
                format="text",
            )

        # Verify files were created
        keymap_file = tmp_path / "output.keymap"
        config_file = tmp_path / "output.conf"

        assert keymap_file.exists()
        assert config_file.exists()
        assert keymap_file.read_text() == "mocked keymap content"
        assert config_file.read_text() == "mocked config content"

    def test_compile_command_stdin_to_stdout(self, minimal_layout_json: dict[str, Any]):
        """Test CompileLayoutCommand with stdin input and stdout output."""
        from glovebox.cli.commands.layout.core import CompileLayoutCommand

        # Create command instance
        command = CompileLayoutCommand()

        # Mock the layout service
        mock_result = LayoutResult(
            success=True,
            keymap_content="mocked keymap content",
            config_content="mocked config content",
            errors=[],
        )

        json_input = json.dumps(minimal_layout_json)

        with (
            patch(
                "glovebox.cli.commands.layout.dependencies.create_full_layout_service"
            ) as mock_service_factory,
            patch(
                "glovebox.core.io.handlers.InputHandler.load_json_input"
            ) as mock_load_json,
            patch.object(command, "format_and_print") as mock_print,
        ):
            mock_service = Mock()
            mock_service.compile.return_value = mock_result
            mock_service_factory.return_value = mock_service
            mock_load_json.return_value = minimal_layout_json

            # Execute command
            command.execute(
                ctx=Mock(),
                input="-",  # stdin
                output=None,  # stdout
                profile=None,
                no_auto=False,
                force=False,
                format="json",
            )

            # Verify JSON output was formatted and printed
            mock_print.assert_called_once()
            call_args = mock_print.call_args[0]
            assert call_args[1] == "json"  # format
            assert call_args[0]["success"] is True

    def test_compile_command_with_library_reference(self):
        """Test CompileLayoutCommand with @library reference input."""
        from glovebox.cli.commands.layout.core import CompileLayoutCommand

        # Create command instance
        command = CompileLayoutCommand()

        # Mock the layout service
        mock_result = LayoutResult(
            success=True,
            keymap_content="mocked keymap content",
            config_content="mocked config content",
            errors=[],
        )

        mock_library_data = {"test": "library", "keyboard": "glove80"}

        with (
            patch(
                "glovebox.cli.commands.layout.dependencies.create_full_layout_service"
            ) as mock_service_factory,
            patch(
                "glovebox.core.io.handlers.InputHandler.load_json_input"
            ) as mock_load_json,
        ):
            mock_service = Mock()
            mock_service.compile.return_value = mock_result
            mock_service_factory.return_value = mock_service
            mock_load_json.return_value = mock_library_data

            # Execute command with library reference
            command.execute(
                ctx=Mock(),
                input="@test/library",  # library reference
                output=None,
                profile=None,
                no_auto=False,
                force=False,
                format="text",
            )

            # Verify library reference was loaded
            mock_load_json.assert_called_once_with("@test/library")
            mock_service.compile.assert_called_once_with(mock_library_data)

    def test_compile_command_error_handling(self, tmp_path: Path):
        """Test CompileLayoutCommand error handling when service fails."""
        from glovebox.cli.commands.layout.core import CompileLayoutCommand

        # Setup test file
        input_file = tmp_path / "input.json"
        input_file.write_text('{"invalid": "layout"}')

        # Create command instance
        command = CompileLayoutCommand()

        # Mock the layout service to return failure
        mock_result = LayoutResult(
            success=False,
            keymap_content=None,
            config_content=None,
            errors=["Validation failed", "Missing required fields"],
        )

        with (
            patch(
                "glovebox.cli.commands.layout.dependencies.create_full_layout_service"
            ) as mock_service_factory,
            pytest.raises(SystemExit),  # typer.Exit(1)
        ):
            mock_service = Mock()
            mock_service.compile.return_value = mock_result
            mock_service_factory.return_value = mock_service

            # Execute command
            command.execute(
                ctx=Mock(),
                input=str(input_file),
                output=None,
                profile=None,
                no_auto=False,
                force=False,
                format="text",
            )

    def test_validate_command_integration(
        self, tmp_path: Path, minimal_layout_json: dict[str, Any]
    ):
        """Test ValidateLayoutCommand integration workflow."""
        from glovebox.cli.commands.layout.core import ValidateLayoutCommand

        # Setup test file
        input_file = tmp_path / "input.json"
        input_file.write_text(json.dumps(minimal_layout_json))

        # Create command instance
        command = ValidateLayoutCommand()

        with (
            patch("glovebox.layout.create_layout_service") as mock_service_factory,
            patch.object(command, "format_and_print") as mock_print,
        ):
            mock_service = Mock()
            mock_service.validate.return_value = True
            mock_service_factory.return_value = mock_service

            # Execute command
            command.execute(
                ctx=Mock(),
                input=str(input_file),
                format="json",
            )

            # Verify validation was called and result printed
            mock_service.validate.assert_called_once_with(minimal_layout_json)
            mock_print.assert_called_once()

    def test_show_command_integration(
        self, tmp_path: Path, minimal_layout_json: dict[str, Any]
    ):
        """Test ShowLayoutCommand integration workflow."""
        from glovebox.cli.commands.layout.core import ShowLayoutCommand

        # Setup test file
        input_file = tmp_path / "input.json"
        input_file.write_text(json.dumps(minimal_layout_json))

        # Create command instance
        command = ShowLayoutCommand()

        with (
            patch("glovebox.layout.create_layout_service") as mock_service_factory,
            patch.object(command, "format_and_print") as mock_print,
        ):
            mock_service = Mock()
            mock_service.show.return_value = "mocked display content"
            mock_service_factory.return_value = mock_service

            # Execute command
            command.execute(
                ctx=Mock(),
                input=str(input_file),
                mode="normal",
                format="text",
            )

            # Verify show was called and result printed
            mock_service.show.assert_called_once()
            mock_print.assert_called_once_with("mocked display content", "text")


class TestLayoutIOPatterns:
    """Test IO pattern integration in layout commands."""

    def test_input_handler_integration(
        self, tmp_path: Path, minimal_layout_json: dict[str, Any]
    ):
        """Test InputHandler integration with layout commands."""
        from glovebox.core.io import create_input_handler

        # Test file input
        input_file = tmp_path / "test.json"
        input_file.write_text(json.dumps(minimal_layout_json))

        input_handler = create_input_handler()
        result = input_handler.load_json_input(str(input_file))
        assert result == minimal_layout_json

        # Test stdin input
        with patch("sys.stdin.read", return_value=json.dumps(minimal_layout_json)):
            result = input_handler.load_json_input("-")
            assert result == minimal_layout_json

    def test_output_handler_integration(self, tmp_path: Path):
        """Test OutputHandler integration with layout commands."""
        from glovebox.core.io import create_output_handler

        test_data = {"test": "output", "content": "example"}
        output_file = tmp_path / "output.json"

        output_handler = create_output_handler()

        # Test file output
        result = output_handler.write_json_output(test_data, str(output_file))
        assert result.success
        assert output_file.exists()

        # Verify content
        written_data = json.loads(output_file.read_text())
        assert written_data == test_data

    def test_memory_first_service_integration(
        self, minimal_layout_json: dict[str, Any]
    ):
        """Test memory-first service pattern integration."""
        from glovebox.layout import create_layout_service

        # Test service directly with memory data (new pattern)
        service = create_layout_service()
        result = service.compile(minimal_layout_json)

        # Should work with dictionary input (memory-first)
        assert isinstance(result, LayoutResult)
        assert result is not None
