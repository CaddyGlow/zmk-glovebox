"""Tests for metrics decorators and automatic operation tracking."""

import asyncio
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import typer

from glovebox.metrics.context_extractors import (
    extract_cli_context,
    extract_compilation_context,
    extract_service_context,
)
from glovebox.metrics.decorators import (
    create_operation_tracker,
    track_firmware_operation,
    track_flash_operation,
    track_layout_operation,
    track_operation,
)
from glovebox.metrics.models import OperationType
from glovebox.metrics.protocols import MetricsServiceProtocol


class TestMetricsDecorators:
    """Test metrics decorators functionality."""

    def test_track_operation_basic_sync_function(self):
        """Test basic decorator on synchronous function."""
        mock_service = Mock(spec=MetricsServiceProtocol)

        @track_operation(OperationType.LAYOUT_COMPILATION, metrics_service=mock_service)
        def test_function(arg1: str, arg2: int = 42) -> str:
            return f"result: {arg1}-{arg2}"

        result = test_function("test", arg2=100)

        assert result == "result: test-100"
        # Function should be wrapped but preserve functionality

    def test_track_operation_with_exception(self):
        """Test decorator behavior when wrapped function raises exception."""
        mock_service = Mock(spec=MetricsServiceProtocol)

        @track_operation(OperationType.LAYOUT_COMPILATION, metrics_service=mock_service)
        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            failing_function()

        # Exception should be re-raised

    # Async test disabled - requires pytest-asyncio
    # @pytest.mark.asyncio
    # async def test_track_operation_async_function(self):
    #     """Test decorator on asynchronous function."""
    #     mock_service = Mock(spec=MetricsServiceProtocol)
    #
    #     @track_operation(OperationType.FIRMWARE_COMPILATION, metrics_service=mock_service)
    #     async def async_function(delay: float = 0.01) -> str:
    #         await asyncio.sleep(delay)
    #         return "async result"
    #
    #     result = await async_function(0.001)
    #
    #     assert result == "async result"

    def test_track_operation_with_context_extraction(self):
        """Test decorator with context extraction."""
        mock_service = Mock(spec=MetricsServiceProtocol)

        def test_extractor(func, args, kwargs):
            return {"test_context": "extracted", "args_count": len(args)}

        @track_operation(
            OperationType.LAYOUT_COMPILATION,
            extract_context=test_extractor,
            metrics_service=mock_service,
        )
        def function_with_context(a, b, c=None):
            return f"{a}-{b}-{c}"

        result = function_with_context("x", "y", c="z")

        assert result == "x-y-z"

    def test_convenience_decorators(self):
        """Test convenience decorators for specific operation types."""
        mock_service = Mock(spec=MetricsServiceProtocol)

        @track_layout_operation(metrics_service=mock_service)
        def layout_func():
            return "layout"

        @track_firmware_operation(metrics_service=mock_service)
        def firmware_func():
            return "firmware"

        @track_flash_operation(metrics_service=mock_service)
        def flash_func():
            return "flash"

        assert layout_func() == "layout"
        assert firmware_func() == "firmware"
        assert flash_func() == "flash"

    def test_create_operation_tracker_factory(self):
        """Test factory function for creating operation trackers."""
        mock_service = Mock(spec=MetricsServiceProtocol)

        def test_extractor(func, args, kwargs):
            return {"factory_test": True}

        tracker = create_operation_tracker(
            OperationType.LAYOUT_COMPILATION,
            extract_context=test_extractor,
            metrics_service=mock_service,
        )

        @tracker
        def tracked_function():
            return "tracked"

        result = tracked_function()
        assert result == "tracked"

    def test_decorator_preserves_function_metadata(self):
        """Test that decorator preserves original function metadata."""

        @track_operation(OperationType.LAYOUT_COMPILATION)
        def documented_function(param: str) -> str:
            """A well-documented function.

            Args:
                param: A parameter

            Returns:
                A result
            """
            return f"result: {param}"

        assert documented_function.__name__ == "documented_function"
        assert (
            documented_function.__doc__ is not None
            and "well-documented function" in documented_function.__doc__
        )
        # Wrapped function should preserve metadata

    def test_decorator_with_missing_metrics_service(self):
        """Test decorator behavior when metrics service is not provided."""

        @track_operation(OperationType.LAYOUT_COMPILATION)
        def test_function():
            return "success"

        # Should work even without explicit metrics service
        result = test_function()
        assert result == "success"

    def test_decorator_with_context_extraction_failure(self):
        """Test decorator behavior when context extraction fails."""
        mock_service = Mock(spec=MetricsServiceProtocol)

        def failing_extractor(func, args, kwargs):
            raise RuntimeError("Context extraction failed")

        @track_operation(
            OperationType.LAYOUT_COMPILATION,
            extract_context=failing_extractor,
            metrics_service=mock_service,
        )
        def test_function():
            return "success"

        # Function should still work despite context extraction failure
        result = test_function()
        assert result == "success"


class TestContextExtractors:
    """Test context extraction functions."""

    def test_extract_cli_context_basic(self):
        """Test basic CLI context extraction."""

        def mock_cli_function(ctx, json_file, output_dir, profile=None, force=False):
            pass

        args = ()
        kwargs = {
            "ctx": Mock(spec=typer.Context),
            "json_file": "/path/to/layout.json",
            "output_dir": "/path/to/output",
            "profile": "glove80/v25.05",
            "force": True,
        }

        context = extract_cli_context(mock_cli_function, args, kwargs)

        assert context["profile_name"] == "glove80/v25.05"
        assert context["input_file"] == "/path/to/layout.json"
        assert context["output_directory"] == "/path/to/output"
        assert context["force"] is True

    def test_extract_cli_context_with_positional_args(self):
        """Test CLI context extraction with positional arguments."""

        def mock_cli_function(ctx, json_file, output_file_prefix):
            pass

        args = (Mock(spec=typer.Context), Path("/input/layout.json"), "/output/prefix")
        kwargs: dict[str, str] = {}

        context = extract_cli_context(mock_cli_function, args, kwargs)

        assert context["input_file"] == "/input/layout.json"
        assert context["output_directory"] == "/output/prefix"

    def test_extract_cli_context_with_typer_context_params(self):
        """Test CLI context extraction from typer context params."""

        def mock_cli_function(ctx):
            pass

        mock_ctx = Mock(spec=typer.Context)
        mock_ctx.params = {"profile": "keyboard/firmware"}

        args = ()
        kwargs = {"ctx": mock_ctx}

        context = extract_cli_context(mock_cli_function, args, kwargs)

        assert context["profile_name"] == "keyboard/firmware"

    def test_extract_service_context_with_profile(self):
        """Test service context extraction with profile."""

        def mock_service_method(self, profile, json_file_path, output_file_prefix):
            pass

        mock_profile = Mock()
        mock_profile.keyboard_name = "glove80"
        mock_profile.firmware_version = "v25.05"

        args = (Mock(), mock_profile)  # self, profile
        kwargs = {
            "json_file_path": Path("/path/to/layout.json"),
            "output_file_prefix": "/output/prefix",
            "force": True,
        }

        context = extract_service_context(mock_service_method, args, kwargs)

        assert context["keyboard_name"] == "glove80"
        assert context["firmware_version"] == "v25.05"
        assert context["profile_name"] == "glove80/v25.05"
        assert context["input_file"] == "/path/to/layout.json"
        assert context["output_directory"] == "/output/prefix"
        assert context["force"] is True

    def test_extract_service_context_with_profile_kwarg(self):
        """Test service context extraction with profile as keyword argument."""

        def mock_service_method(self, **kwargs):
            pass

        mock_profile = Mock()
        mock_profile.keyboard_name = "nice_nano"
        mock_profile.firmware_version = None

        args = (Mock(),)  # self only
        kwargs = {
            "profile": mock_profile,
            "json_file_path": Path("/path/to/layout.json"),
        }

        context = extract_service_context(mock_service_method, args, kwargs)

        assert context["keyboard_name"] == "nice_nano"
        assert context["profile_name"] == "nice_nano"
        assert "firmware_version" not in context or context["firmware_version"] is None

    def test_extract_compilation_context(self):
        """Test compilation context extraction."""

        def mock_compile_function(self, keymap_file, config_file, output_dir, config):
            pass

        mock_config = Mock()
        mock_config.type = "zmk_config"
        mock_config.build_matrix = Mock()
        mock_config.build_matrix.board = ["nice_nano_v2", "pro_micro"]
        mock_config.image = "zmkfirmware/zmk-build-arm:stable"
        mock_config.repository = "zmkfirmware/zmk"
        mock_config.branch = "main"

        args = (Mock(),)  # self
        kwargs = {
            "keymap_file": Path("/path/to/keymap.keymap"),
            "config_file": Path("/path/to/config.conf"),
            "output_dir": Path("/output"),
            "config": mock_config,
        }

        context = extract_compilation_context(mock_compile_function, args, kwargs)

        assert context["compilation_strategy"] == "zmk_config"
        assert context["board_targets"] == ["nice_nano_v2", "pro_micro"]
        assert context["docker_image"] == "zmkfirmware/zmk-build-arm:stable"
        assert context["repository"] == "zmkfirmware/zmk"
        assert context["branch"] == "main"
        assert context["keymap_file"] == "/path/to/keymap.keymap"
        assert context["config_file"] == "/path/to/config.conf"
        assert context["output_directory"] == "/output"

    def test_extract_compilation_context_inferred_strategy(self):
        """Test compilation context extraction with inferred strategy."""

        def mock_compile_function(self, config):
            pass

        # Mock config without explicit type
        mock_config = Mock()
        mock_config.__class__.__name__ = "ZmkCompilationConfig"
        del mock_config.type  # Remove type attribute

        args = (Mock(),)
        kwargs = {"config": mock_config}

        context = extract_compilation_context(mock_compile_function, args, kwargs)

        assert context["compilation_strategy"] == "zmk_config"

    def test_context_extractors_handle_exceptions(self):
        """Test that context extractors handle exceptions gracefully."""

        def mock_function():
            pass

        # Test with invalid arguments that would cause exceptions
        context = extract_cli_context(mock_function, (), {"invalid": object()})
        assert isinstance(context, dict)  # Should return empty dict, not crash

        context = extract_service_context(mock_function, (), {"invalid": object()})
        assert isinstance(context, dict)

        context = extract_compilation_context(mock_function, (), {"invalid": object()})
        assert isinstance(context, dict)


class TestDecoratorIntegration:
    """Test decorator integration with existing codebase patterns."""

    def test_decorator_with_existing_cli_decorators(self):
        """Test decorator compatibility with existing CLI decorators."""

        def mock_handle_errors(func):
            return func

        def mock_with_profile():
            def decorator(func):
                return func

            return decorator

        @mock_handle_errors
        @mock_with_profile()
        @track_layout_operation(extract_context=extract_cli_context)
        def mock_cli_command(ctx, json_file, output_dir, profile=None):
            return "success"

        result = mock_cli_command(
            Mock(spec=typer.Context), "/input.json", "/output", profile="test"
        )
        assert result == "success"

    def test_decorator_preserves_dependency_injection(self):
        """Test that decorator preserves dependency injection patterns."""
        mock_service = Mock(spec=MetricsServiceProtocol)

        # Create decorator with injected service
        tracker = create_operation_tracker(
            OperationType.LAYOUT_COMPILATION, metrics_service=mock_service
        )

        @tracker
        def service_method():
            return "injected"

        result = service_method()
        assert result == "injected"

    def test_decorator_with_claude_md_patterns(self):
        """Test decorator compatibility with CLAUDE.md patterns."""

        # Mock factory function pattern
        def create_test_service(metrics_service=None):
            @track_operation(
                OperationType.LAYOUT_COMPILATION, metrics_service=metrics_service
            )
            def service_method():
                return "factory_created"

            return service_method

        # Create service with dependency injection
        service = create_test_service(Mock(spec=MetricsServiceProtocol))
        result = service()
        assert result == "factory_created"

    def test_multiple_decorators_on_same_function(self):
        """Test applying multiple metric decorators (should not happen in practice)."""
        mock_service = Mock(spec=MetricsServiceProtocol)

        # This is an edge case test - normally you wouldn't do this
        @track_operation(OperationType.LAYOUT_COMPILATION, metrics_service=mock_service)
        @track_operation(
            OperationType.FIRMWARE_COMPILATION, metrics_service=mock_service
        )
        def double_tracked_function():
            return "double_tracked"

        # Should still work (outer decorator wins)
        result = double_tracked_function()
        assert result == "double_tracked"
