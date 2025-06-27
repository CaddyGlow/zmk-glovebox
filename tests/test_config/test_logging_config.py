"""Tests for logging configuration models and functionality."""

import json
import logging
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from glovebox.config.models.logging import (
    LogFormat,
    LoggingConfig,
    LogHandlerConfig,
    LogHandlerType,
    create_default_logging_config,
    create_developer_logging_config,
)
from glovebox.core.logging import (
    JSONFormatter,
    _create_formatter,
    _create_handler,
    setup_logging_from_config,
)


class TestLogHandlerConfig:
    """Test LogHandlerConfig model validation and functionality."""

    def test_valid_console_handler(self):
        """Test creating a valid console handler."""
        handler = LogHandlerConfig(
            type=LogHandlerType.CONSOLE,
            level="INFO",
            format=LogFormat.SIMPLE,
            colored=True,
        )
        assert handler.type == LogHandlerType.CONSOLE
        assert handler.level == "INFO"
        assert handler.format == LogFormat.SIMPLE
        assert handler.colored is True
        assert handler.file_path is None

    def test_valid_file_handler(self, tmp_path):
        """Test creating a valid file handler."""
        log_file = tmp_path / "test.log"
        handler = LogHandlerConfig(
            type=LogHandlerType.FILE,
            level="DEBUG",
            format=LogFormat.JSON,
            colored=False,
            file_path=log_file,
        )
        assert handler.type == LogHandlerType.FILE
        assert handler.level == "DEBUG"
        assert handler.format == LogFormat.JSON
        assert handler.colored is False
        assert handler.file_path == log_file.resolve()

    def test_log_level_validation(self):
        """Test log level validation."""
        # Valid levels
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            handler = LogHandlerConfig(type=LogHandlerType.STDERR, level=level)
            assert handler.level == level

        # Case insensitive
        handler = LogHandlerConfig(type=LogHandlerType.STDERR, level="info")
        assert handler.level == "INFO"

        # Invalid level
        with pytest.raises(ValueError, match="Log level must be one of"):
            LogHandlerConfig(type=LogHandlerType.STDERR, level="INVALID")

    def test_file_handler_requires_path(self):
        """Test that file handlers require a file path."""
        with pytest.raises(ValueError, match="file_path is required for file handlers"):
            LogHandlerConfig(type=LogHandlerType.FILE, level="INFO")

    def test_file_path_expansion(self, tmp_path):
        """Test file path expansion and resolution."""
        # Test string path
        handler = LogHandlerConfig(
            type=LogHandlerType.FILE,
            level="INFO",
            file_path=str(tmp_path / "test.log"),
        )
        assert isinstance(handler.file_path, Path)
        assert handler.file_path.is_absolute()

        # Test Path object
        log_file = tmp_path / "test2.log"
        handler = LogHandlerConfig(
            type=LogHandlerType.FILE,
            level="INFO",
            file_path=log_file,
        )
        assert handler.file_path == log_file.resolve()

    def test_get_log_level_int(self):
        """Test conversion of string log level to integer."""
        handler = LogHandlerConfig(type=LogHandlerType.STDERR, level="DEBUG")
        assert handler.get_log_level_int() == logging.DEBUG

        handler = LogHandlerConfig(type=LogHandlerType.STDERR, level="INFO")
        assert handler.get_log_level_int() == logging.INFO

        handler = LogHandlerConfig(type=LogHandlerType.STDERR, level="WARNING")
        assert handler.get_log_level_int() == logging.WARNING

        handler = LogHandlerConfig(type=LogHandlerType.STDERR, level="ERROR")
        assert handler.get_log_level_int() == logging.ERROR

        handler = LogHandlerConfig(type=LogHandlerType.STDERR, level="CRITICAL")
        assert handler.get_log_level_int() == logging.CRITICAL


class TestLoggingConfig:
    """Test LoggingConfig model validation and functionality."""

    def test_valid_logging_config(self):
        """Test creating a valid logging configuration."""
        config = LoggingConfig(
            handlers=[
                LogHandlerConfig(
                    type=LogHandlerType.STDERR,
                    level="WARNING",
                    format=LogFormat.SIMPLE,
                    colored=True,
                )
            ]
        )
        assert len(config.handlers) == 1
        assert config.handlers[0].type == LogHandlerType.STDERR

    def test_empty_handlers_validation(self):
        """Test that empty handlers list raises validation error."""
        with pytest.raises(
            ValueError, match="At least one log handler must be configured"
        ):
            LoggingConfig(handlers=[])

    def test_duplicate_file_paths_validation(self, tmp_path):
        """Test validation of duplicate file paths."""
        log_file = tmp_path / "test.log"

        with pytest.raises(ValueError, match="Duplicate file path in handlers"):
            LoggingConfig(
                handlers=[
                    LogHandlerConfig(
                        type=LogHandlerType.FILE,
                        level="INFO",
                        file_path=log_file,
                    ),
                    LogHandlerConfig(
                        type=LogHandlerType.FILE,
                        level="DEBUG",
                        file_path=log_file,
                    ),
                ]
            )

    def test_multiple_console_handlers_allowed(self):
        """Test that multiple console/stderr handlers are allowed."""
        config = LoggingConfig(
            handlers=[
                LogHandlerConfig(
                    type=LogHandlerType.STDERR,
                    level="WARNING",
                ),
                LogHandlerConfig(
                    type=LogHandlerType.CONSOLE,
                    level="INFO",
                ),
            ]
        )
        assert len(config.handlers) == 2


class TestFactoryFunctions:
    """Test factory functions for logging configurations."""

    def test_create_default_logging_config(self):
        """Test default logging configuration creation."""
        config = create_default_logging_config()

        assert isinstance(config, LoggingConfig)
        assert len(config.handlers) == 1

        handler = config.handlers[0]
        assert handler.type == LogHandlerType.STDERR
        assert handler.level == "WARNING"
        assert handler.format == LogFormat.SIMPLE
        assert handler.colored is True

    def test_create_developer_logging_config_without_file(self):
        """Test developer logging config without debug file."""
        config = create_developer_logging_config()

        assert isinstance(config, LoggingConfig)
        assert len(config.handlers) == 1

        handler = config.handlers[0]
        assert handler.type == LogHandlerType.STDERR
        assert handler.level == "INFO"
        assert handler.format == LogFormat.DETAILED
        assert handler.colored is True

    def test_create_developer_logging_config_with_file(self, tmp_path):
        """Test developer logging config with debug file."""
        debug_file = tmp_path / "debug.log"
        config = create_developer_logging_config(debug_file)

        assert isinstance(config, LoggingConfig)
        assert len(config.handlers) == 2

        # First handler should be stderr
        stderr_handler = config.handlers[0]
        assert stderr_handler.type == LogHandlerType.STDERR
        assert stderr_handler.level == "INFO"
        assert stderr_handler.format == LogFormat.DETAILED
        assert stderr_handler.colored is True

        # Second handler should be file
        file_handler = config.handlers[1]
        assert file_handler.type == LogHandlerType.FILE
        assert file_handler.level == "DEBUG"
        assert file_handler.format == LogFormat.JSON
        assert file_handler.colored is False
        assert file_handler.file_path == debug_file.resolve()


class TestJSONFormatter:
    """Test custom JSON formatter."""

    def test_json_formatter_basic(self):
        """Test basic JSON formatting."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert "timestamp" in data
        assert data["level"] == "INFO"
        assert data["logger"] == "test.logger"
        assert data["message"] == "Test message"

    def test_json_formatter_with_exception(self):
        """Test JSON formatting with exception info."""
        formatter = JSONFormatter()

        try:
            raise ValueError("Test exception")
        except ValueError:
            import sys

            exc_info = sys.exc_info()
            record = logging.LogRecord(
                name="test.logger",
                level=logging.ERROR,
                pathname="",
                lineno=0,
                msg="Error occurred",
                args=(),
                exc_info=exc_info,
            )

        output = formatter.format(record)
        data = json.loads(output)

        assert "exception" in data
        assert "ValueError: Test exception" in data["exception"]

    def test_json_formatter_with_extra_fields(self):
        """Test JSON formatting with extra fields."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.extra = {"user_id": "123", "request_id": "abc"}

        output = formatter.format(record)
        data = json.loads(output)

        assert data["user_id"] == "123"
        assert data["request_id"] == "abc"


class TestFormatterCreation:
    """Test formatter creation functions."""

    def test_create_simple_formatter(self):
        """Test creating simple formatter."""
        formatter = _create_formatter("simple", colored=False)
        assert isinstance(formatter, logging.Formatter)

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        assert output == "INFO: Test"

    def test_create_detailed_formatter(self):
        """Test creating detailed formatter."""
        formatter = _create_formatter("detailed", colored=False)
        assert isinstance(formatter, logging.Formatter)

        record = logging.LogRecord(
            name="test.logger",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="Warning message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        assert "WARNING" in output
        assert "test.logger" in output
        assert "Warning message" in output

    def test_create_json_formatter(self):
        """Test creating JSON formatter."""
        formatter = _create_formatter("json", colored=False)
        assert isinstance(formatter, JSONFormatter)

    @patch("glovebox.core.logging.HAS_COLORLOG", True)
    @patch("glovebox.core.logging.colorlog")
    def test_create_colored_formatter(self, mock_colorlog):
        """Test creating colored formatter when colorlog is available."""
        mock_colorlog.ColoredFormatter.return_value = "colored_formatter"

        formatter = _create_formatter("simple", colored=True)

        mock_colorlog.ColoredFormatter.assert_called_once()
        assert formatter == "colored_formatter"

    @patch("glovebox.core.logging.HAS_COLORLOG", False)
    def test_create_formatter_no_colorlog(self):
        """Test creating formatter when colorlog is not available."""
        formatter = _create_formatter("simple", colored=True)
        assert isinstance(formatter, logging.Formatter)


class TestHandlerCreation:
    """Test handler creation functions."""

    def test_create_console_handler(self):
        """Test creating console handler."""
        config = LogHandlerConfig(
            type=LogHandlerType.CONSOLE,
            level="INFO",
            format=LogFormat.SIMPLE,
        )

        handler = _create_handler(config)

        assert isinstance(handler, logging.StreamHandler)
        assert handler.level == logging.INFO
        assert handler.stream is sys.stdout

    def test_create_stderr_handler(self):
        """Test creating stderr handler."""
        config = LogHandlerConfig(
            type=LogHandlerType.STDERR,
            level="WARNING",
            format=LogFormat.DETAILED,
        )

        handler = _create_handler(config)

        assert isinstance(handler, logging.StreamHandler)
        assert handler.level == logging.WARNING
        assert handler.stream is sys.stderr

    def test_create_file_handler(self, tmp_path):
        """Test creating file handler."""
        log_file = tmp_path / "test.log"
        config = LogHandlerConfig(
            type=LogHandlerType.FILE,
            level="DEBUG",
            format=LogFormat.JSON,
            file_path=log_file,
        )

        handler = _create_handler(config)

        assert isinstance(handler, logging.FileHandler)
        assert handler.level == logging.DEBUG
        assert Path(handler.baseFilename) == log_file

    def test_create_file_handler_creates_directory(self, tmp_path):
        """Test that file handler creation creates parent directories."""
        log_file = tmp_path / "logs" / "app" / "test.log"
        config = LogHandlerConfig(
            type=LogHandlerType.FILE,
            level="INFO",
            format=LogFormat.SIMPLE,
            file_path=log_file,
        )

        handler = _create_handler(config)

        assert isinstance(handler, logging.FileHandler)
        assert log_file.parent.exists()

    def test_create_file_handler_without_path(self):
        """Test creating file handler without path returns None."""
        # Create a valid config first, then modify it to bypass validation
        config = LogHandlerConfig(
            type=LogHandlerType.FILE,
            level="INFO",
            format=LogFormat.SIMPLE,
            file_path=Path("/tmp/dummy.log"),
        )
        # Override file_path to None after validation
        config.file_path = None

        handler = _create_handler(config)

        assert handler is None

    def test_create_handler_exception_handling(self):
        """Test handler creation with invalid configuration."""
        config = LogHandlerConfig(
            type=LogHandlerType.FILE,
            level="INFO",
            format=LogFormat.SIMPLE,
            file_path=Path("/invalid/readonly/path/test.log"),
        )

        # This should not raise an exception, but return None
        handler = _create_handler(config)

        # Depending on system permissions, this might succeed or fail
        # We mainly want to ensure no exception is raised
        assert handler is None or isinstance(handler, logging.FileHandler)


class TestLoggingSetup:
    """Test logging setup from configuration."""

    def test_setup_logging_from_config_basic(self):
        """Test basic logging setup from configuration."""
        config = LoggingConfig(
            handlers=[
                LogHandlerConfig(
                    type=LogHandlerType.STDERR,
                    level="WARNING",
                    format=LogFormat.SIMPLE,
                )
            ]
        )

        logger = setup_logging_from_config(config)

        assert logger.name == "glovebox"
        assert logger.level == logging.WARNING
        assert len(logger.handlers) == 1

        handler = logger.handlers[0]
        assert isinstance(handler, logging.StreamHandler)
        assert handler.level == logging.WARNING

    def test_setup_logging_multiple_handlers(self, tmp_path):
        """Test logging setup with multiple handlers."""
        log_file = tmp_path / "test.log"
        config = LoggingConfig(
            handlers=[
                LogHandlerConfig(
                    type=LogHandlerType.STDERR,
                    level="INFO",
                    format=LogFormat.SIMPLE,
                ),
                LogHandlerConfig(
                    type=LogHandlerType.FILE,
                    level="DEBUG",
                    format=LogFormat.JSON,
                    file_path=log_file,
                ),
            ]
        )

        logger = setup_logging_from_config(config)

        assert logger.name == "glovebox"
        assert logger.level == logging.DEBUG  # Most restrictive level
        assert len(logger.handlers) == 2

    def test_setup_logging_clears_existing_handlers(self):
        """Test that setup clears existing handlers."""
        # Add a handler to the logger
        logger = logging.getLogger("glovebox")
        existing_handler = logging.StreamHandler()
        logger.addHandler(existing_handler)

        config = create_default_logging_config()

        new_logger = setup_logging_from_config(config)

        assert new_logger is logger
        assert len(logger.handlers) == 1
        assert existing_handler not in logger.handlers

    def test_setup_logging_propagation_disabled(self):
        """Test that logger propagation is disabled."""
        config = create_default_logging_config()
        logger = setup_logging_from_config(config)

        assert logger.propagate is False

    def test_setup_logging_with_failed_handler(self):
        """Test logging setup when handler creation fails."""
        config = LoggingConfig(
            handlers=[
                LogHandlerConfig(
                    type=LogHandlerType.STDERR,
                    level="INFO",
                    format=LogFormat.SIMPLE,
                ),
                LogHandlerConfig(
                    type=LogHandlerType.FILE,
                    level="DEBUG",
                    format=LogFormat.JSON,
                    file_path=Path("/invalid/readonly/path/test.log"),
                ),
            ]
        )

        logger = setup_logging_from_config(config)

        # Should still set up successfully with just the stderr handler
        assert logger.name == "glovebox"
        # Handlers count might be 1 or 2 depending on system permissions
        assert len(logger.handlers) >= 1


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_development_logging_scenario(self, tmp_path):
        """Test typical development logging scenario."""
        debug_file = tmp_path / "debug.log"
        config = create_developer_logging_config(debug_file)

        logger = setup_logging_from_config(config)

        # Test logging at different levels
        test_logger = logging.getLogger("glovebox.test")

        test_logger.debug("Debug message")
        test_logger.info("Info message")
        test_logger.warning("Warning message")
        test_logger.error("Error message")

        # Verify debug file was created and contains content
        assert debug_file.exists()
        content = debug_file.read_text()
        assert "Debug message" in content
        assert "Info message" in content
        assert "Warning message" in content
        assert "Error message" in content

        # Verify JSON format in file
        lines = content.strip().split("\n")
        for line in lines:
            data = json.loads(line)
            assert "timestamp" in data
            assert "level" in data
            assert "logger" in data
            assert "message" in data

    def test_production_logging_scenario(self):
        """Test typical production logging scenario."""
        config = LoggingConfig(
            handlers=[
                LogHandlerConfig(
                    type=LogHandlerType.STDERR,
                    level="ERROR",
                    format=LogFormat.JSON,
                    colored=False,
                )
            ]
        )

        logger = setup_logging_from_config(config)
        test_logger = logging.getLogger("glovebox.app")

        # Only errors should be logged
        test_logger.debug("Debug message")  # Should not appear
        test_logger.info("Info message")  # Should not appear
        test_logger.warning("Warning message")  # Should not appear
        test_logger.error("Error message")  # Should appear

        # Verify logger configuration
        assert logger.level == logging.ERROR
        assert len(logger.handlers) == 1

        handler = logger.handlers[0]
        assert handler.level == logging.ERROR
        assert isinstance(handler.formatter, JSONFormatter)

    def test_mixed_format_scenario(self, tmp_path):
        """Test scenario with mixed formats."""
        log_file = tmp_path / "structured.log"
        config = LoggingConfig(
            handlers=[
                LogHandlerConfig(
                    type=LogHandlerType.STDERR,
                    level="WARNING",
                    format=LogFormat.SIMPLE,
                    colored=True,
                ),
                LogHandlerConfig(
                    type=LogHandlerType.FILE,
                    level="INFO",
                    format=LogFormat.JSON,
                    file_path=log_file,
                ),
            ]
        )

        logger = setup_logging_from_config(config)
        test_logger = logging.getLogger("glovebox.mixed")

        test_logger.info("Info message")
        test_logger.warning("Warning message")
        test_logger.error("Error message")

        # Verify file contains JSON
        assert log_file.exists()
        content = log_file.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 3  # All three messages should be in file

        for line in lines:
            data = json.loads(line)
            assert data["logger"] == "glovebox.mixed"
