"""Unit tests for GloveboxLogger."""

import logging
from unittest.mock import MagicMock, Mock

import pytest

from glovebox.adapters.zmk_layout.logger import GloveboxLogger


class TestGloveboxLogger:
    """Test suite for GloveboxLogger."""

    @pytest.fixture
    def mock_logging_service(self):
        """Mock logging service."""
        service = Mock()
        mock_logger = MagicMock()
        service.get_logger.return_value = mock_logger
        return service

    @pytest.fixture
    def mock_logger_instance(self, mock_logging_service):
        """Get the mock logger instance."""
        return mock_logging_service.get_logger.return_value

    @pytest.fixture
    def provider(self, mock_logging_service):
        """Create logger provider instance for testing."""
        return GloveboxLogger(
            logging_service=mock_logging_service, component="test_component"
        )

    def test_initialization(self, provider, mock_logging_service, mock_logger_instance):
        """Test logger provider initialization."""
        assert provider.component == "test_component"
        assert provider.logger is mock_logger_instance
        mock_logging_service.get_logger.assert_called_once_with("test_component")

    def test_initialization_default_component(self, mock_logging_service):
        """Test logger provider initialization with default component."""
        provider = GloveboxLogger(logging_service=mock_logging_service)

        assert provider.component == "zmk_layout"
        mock_logging_service.get_logger.assert_called_once_with("zmk_layout")

    def test_debug_logging(self, provider, mock_logger_instance):
        """Test debug logging."""
        provider.debug("Debug message", key1="value1", key2="value2")

        mock_logger_instance.debug.assert_called_once_with(
            "Debug message",
            extra={"component": "test_component", "key1": "value1", "key2": "value2"},
        )

    def test_info_logging(self, provider, mock_logger_instance):
        """Test info logging."""
        provider.info("Info message", operation="test", keyboard="crkbd")

        mock_logger_instance.info.assert_called_once_with(
            "Info message",
            extra={
                "component": "test_component",
                "operation": "test",
                "keyboard": "crkbd",
            },
        )

    def test_warning_logging(self, provider, mock_logger_instance):
        """Test warning logging."""
        provider.warning("Warning message", issue="performance")

        mock_logger_instance.warning.assert_called_once_with(
            "Warning message",
            extra={"component": "test_component", "issue": "performance"},
        )

    def test_error_logging(self, provider, mock_logger_instance):
        """Test error logging without exception info."""
        provider.error("Error message", error_code=500)

        mock_logger_instance.error.assert_called_once_with(
            "Error message",
            exc_info=False,
            extra={"component": "test_component", "error_code": 500},
        )

    def test_error_logging_with_exc_info(self, provider, mock_logger_instance):
        """Test error logging with exception info."""
        provider.error("Error message", exc_info=True, error_code=500)

        mock_logger_instance.error.assert_called_once_with(
            "Error message",
            exc_info=True,
            extra={"component": "test_component", "error_code": 500},
        )

    def test_exception_logging(self, provider, mock_logger_instance):
        """Test exception logging."""
        provider.exception("Exception occurred", context="validation")

        mock_logger_instance.exception.assert_called_once_with(
            "Exception occurred",
            extra={"component": "test_component", "context": "validation"},
        )

    def test_log_layout_operation(self, provider, mock_logger_instance):
        """Test layout-specific operation logging."""
        provider.log_layout_operation(
            operation="compile", keyboard="crkbd", layers=3, behaviors=42
        )

        mock_logger_instance.info.assert_called_once_with(
            "Layout operation: compile",
            extra={
                "component": "test_component",
                "operation": "compile",
                "keyboard": "crkbd",
                "layers": 3,
                "behaviors": 42,
            },
        )

    def test_log_performance_metric_default_unit(self, provider, mock_logger_instance):
        """Test performance metric logging with default unit."""
        provider.log_performance_metric(metric_name="compilation_time", value=150.5)

        mock_logger_instance.info.assert_called_once_with(
            "Performance metric: compilation_time",
            extra={
                "component": "test_component",
                "metric": "compilation_time",
                "value": 150.5,
                "unit": "ms",
                "category": "performance",
            },
        )

    def test_log_performance_metric_custom_unit(self, provider, mock_logger_instance):
        """Test performance metric logging with custom unit."""
        provider.log_performance_metric(
            metric_name="memory_usage", value=256.0, unit="MB"
        )

        mock_logger_instance.info.assert_called_once_with(
            "Performance metric: memory_usage",
            extra={
                "component": "test_component",
                "metric": "memory_usage",
                "value": 256.0,
                "unit": "MB",
                "category": "performance",
            },
        )

    def test_logging_without_kwargs(self, provider, mock_logger_instance):
        """Test logging without additional keyword arguments."""
        provider.debug("Simple debug message")

        mock_logger_instance.debug.assert_called_once_with(
            "Simple debug message", extra={"component": "test_component"}
        )

    def test_logging_with_empty_kwargs(self, provider, mock_logger_instance):
        """Test logging with empty keyword arguments."""
        provider.info("Simple info message", **{})

        mock_logger_instance.info.assert_called_once_with(
            "Simple info message", extra={"component": "test_component"}
        )

    def test_multiple_logging_calls(self, provider, mock_logger_instance):
        """Test multiple logging calls maintain correct component."""
        provider.debug("First message", context="initialization")
        provider.info("Second message", context="processing")
        provider.error("Third message", context="cleanup")

        # Check all calls included the component
        assert mock_logger_instance.debug.call_count == 1
        assert mock_logger_instance.info.call_count == 1
        assert mock_logger_instance.error.call_count == 1

        # Check component was included in all calls
        debug_call = mock_logger_instance.debug.call_args
        info_call = mock_logger_instance.info.call_args
        error_call = mock_logger_instance.error.call_args

        assert debug_call[1]["extra"]["component"] == "test_component"
        assert info_call[1]["extra"]["component"] == "test_component"
        assert error_call[1]["extra"]["component"] == "test_component"

    def test_complex_layout_operation_logging(self, provider, mock_logger_instance):
        """Test complex layout operation with many details."""
        provider.log_layout_operation(
            operation="parse_and_validate",
            keyboard="glove80",
            source_file="/path/to/layout.json",
            layers=5,
            behaviors=78,
            combos=12,
            hold_taps=8,
            parsing_time_ms=45.2,
            validation_time_ms=23.8,
            errors=0,
            warnings=2,
        )

        expected_extra = {
            "component": "test_component",
            "operation": "parse_and_validate",
            "keyboard": "glove80",
            "source_file": "/path/to/layout.json",
            "layers": 5,
            "behaviors": 78,
            "combos": 12,
            "hold_taps": 8,
            "parsing_time_ms": 45.2,
            "validation_time_ms": 23.8,
            "errors": 0,
            "warnings": 2,
        }

        mock_logger_instance.info.assert_called_once_with(
            "Layout operation: parse_and_validate", extra=expected_extra
        )

    def test_performance_metrics_different_types(self, provider, mock_logger_instance):
        """Test performance metrics with different value types."""
        # Integer value
        provider.log_performance_metric("count", 42)

        # Float value
        provider.log_performance_metric("ratio", 0.85)

        # Zero value
        provider.log_performance_metric("errors", 0)

        # Large value
        provider.log_performance_metric("memory", 1024 * 1024 * 512, "bytes")

        assert mock_logger_instance.info.call_count == 4

        # Check the calls contain correct values
        calls = mock_logger_instance.info.call_args_list

        assert calls[0][1]["extra"]["value"] == 42
        assert calls[1][1]["extra"]["value"] == 0.85
        assert calls[2][1]["extra"]["value"] == 0
        assert calls[3][1]["extra"]["value"] == 1024 * 1024 * 512
        assert calls[3][1]["extra"]["unit"] == "bytes"
