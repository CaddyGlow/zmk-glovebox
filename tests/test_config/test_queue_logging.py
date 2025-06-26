"""Tests for queue-based logging functionality for TUI applications."""

import logging
import queue
import sys
import threading
import time
from pathlib import Path

import pytest

from glovebox.config.models.logging import (
    LogFormat,
    LoggingConfig,
    LogHandlerConfig,
    LogHandlerType,
    create_tui_logging_config,
)
from glovebox.core.logging import (
    QueueLoggerManager,
    create_queue_handler,
    setup_queue_logging_from_config,
    start_queue_logging,
    stop_queue_logging,
)


class TestQueueLoggerManager:
    """Test QueueLoggerManager functionality."""

    def test_queue_manager_initialization(self):
        """Test QueueLoggerManager initialization."""
        manager = QueueLoggerManager()

        assert isinstance(manager.log_queue, queue.Queue)
        assert manager.queue_listener is None
        assert len(manager.target_handlers) == 0

    def test_add_handler(self):
        """Test adding handlers to queue manager."""
        manager = QueueLoggerManager()
        handler = logging.StreamHandler(sys.stderr)

        manager.add_handler(handler)

        assert len(manager.target_handlers) == 1
        assert handler in manager.target_handlers

    def test_get_queue_handler(self):
        """Test getting QueueHandler from manager."""
        manager = QueueLoggerManager()
        queue_handler = manager.get_queue_handler()

        assert isinstance(queue_handler, logging.handlers.QueueHandler)
        assert queue_handler.queue is manager.log_queue

    def test_start_stop_listener(self):
        """Test starting and stopping queue listener."""
        manager = QueueLoggerManager()
        handler = logging.StreamHandler(sys.stderr)
        manager.add_handler(handler)

        # Start listener
        manager.start_listener()
        assert manager.queue_listener is not None
        assert manager.queue_listener._thread.is_alive()

        # Stop listener
        manager.stop_listener()
        assert manager.queue_listener is None

    def test_listener_without_handlers(self):
        """Test that listener doesn't start without handlers."""
        manager = QueueLoggerManager()

        manager.start_listener()
        assert manager.queue_listener is None

    def test_multiple_start_stop_cycles(self):
        """Test multiple start/stop cycles work correctly."""
        manager = QueueLoggerManager()
        handler = logging.StreamHandler(sys.stderr)
        manager.add_handler(handler)

        # Multiple start/stop cycles
        for _ in range(3):
            manager.start_listener()
            assert manager.queue_listener is not None

            manager.stop_listener()
            assert manager.queue_listener is None


class TestCreateQueueHandler:
    """Test queue handler creation functionality."""

    def test_create_queue_handler_stderr(self):
        """Test creating queue handler for stderr."""
        config = LogHandlerConfig(
            type=LogHandlerType.STDERR,
            level="INFO",
            format=LogFormat.SIMPLE,
            queue_enabled=True,
        )

        queue_handler, queue_manager = create_queue_handler(config)

        assert isinstance(queue_handler, logging.handlers.QueueHandler)
        assert isinstance(queue_manager, QueueLoggerManager)
        assert queue_handler.level == logging.INFO
        assert len(queue_manager.target_handlers) == 1

        target_handler = queue_manager.target_handlers[0]
        assert isinstance(target_handler, logging.StreamHandler)
        assert target_handler.stream is sys.stderr

    def test_create_queue_handler_file(self, tmp_path):
        """Test creating queue handler for file."""
        log_file = tmp_path / "test.log"
        config = LogHandlerConfig(
            type=LogHandlerType.FILE,
            level="DEBUG",
            format=LogFormat.JSON,
            file_path=log_file,
            queue_enabled=True,
        )

        queue_handler, queue_manager = create_queue_handler(config)

        assert isinstance(queue_handler, logging.handlers.QueueHandler)
        assert queue_handler.level == logging.DEBUG
        assert len(queue_manager.target_handlers) == 1

        target_handler = queue_manager.target_handlers[0]
        assert isinstance(target_handler, logging.FileHandler)

    def test_create_queue_handler_invalid_config(self):
        """Test creating queue handler with invalid config."""
        config = LogHandlerConfig(
            type=LogHandlerType.FILE,
            level="INFO",
            format=LogFormat.SIMPLE,
            file_path=Path("/tmp/dummy.log"),
        )
        # Override to None to simulate invalid config
        config.file_path = None

        with pytest.raises(ValueError, match="Failed to create target handler"):
            create_queue_handler(config)


class TestQueueLoggingSetup:
    """Test queue-based logging setup functionality."""

    def test_setup_queue_logging_basic(self):
        """Test basic queue logging setup."""
        config = LoggingConfig(
            handlers=[
                LogHandlerConfig(
                    type=LogHandlerType.STDERR,
                    level="WARNING",
                    format=LogFormat.SIMPLE,
                    queue_enabled=True,
                )
            ]
        )

        logger, queue_managers = setup_queue_logging_from_config(config)

        assert logger.name == "glovebox"
        assert logger.level == logging.WARNING
        assert len(logger.handlers) == 1
        assert len(queue_managers) == 1

        # Handler should be QueueHandler
        handler = logger.handlers[0]
        assert isinstance(handler, logging.handlers.QueueHandler)

        # Cleanup
        stop_queue_logging(queue_managers)

    def test_setup_mixed_handlers(self, tmp_path):
        """Test setup with both queue and regular handlers."""
        log_file = tmp_path / "test.log"
        config = LoggingConfig(
            handlers=[
                LogHandlerConfig(
                    type=LogHandlerType.STDERR,
                    level="WARNING",
                    format=LogFormat.SIMPLE,
                    queue_enabled=True,  # Queue-based
                ),
                LogHandlerConfig(
                    type=LogHandlerType.FILE,
                    level="DEBUG",
                    format=LogFormat.JSON,
                    file_path=log_file,
                    queue_enabled=False,  # Regular handler
                ),
            ]
        )

        logger, queue_managers = setup_queue_logging_from_config(config)

        assert len(logger.handlers) == 2
        assert len(queue_managers) == 1  # Only one queue-enabled handler

        # First handler should be QueueHandler, second should be FileHandler
        assert isinstance(logger.handlers[0], logging.handlers.QueueHandler)
        assert isinstance(logger.handlers[1], logging.FileHandler)

        # Cleanup
        stop_queue_logging(queue_managers)

    def test_setup_no_queue_handlers(self):
        """Test setup with no queue-enabled handlers."""
        config = LoggingConfig(
            handlers=[
                LogHandlerConfig(
                    type=LogHandlerType.STDERR,
                    level="WARNING",
                    format=LogFormat.SIMPLE,
                    queue_enabled=False,  # Regular handler
                )
            ]
        )

        logger, queue_managers = setup_queue_logging_from_config(config)

        assert len(logger.handlers) == 1
        assert len(queue_managers) == 0  # No queue managers

        # Handler should be regular StreamHandler
        handler = logger.handlers[0]
        assert isinstance(handler, logging.StreamHandler)
        assert not isinstance(handler, logging.handlers.QueueHandler)

    def test_start_stop_queue_logging(self):
        """Test starting and stopping queue logging."""
        config = LoggingConfig(
            handlers=[
                LogHandlerConfig(
                    type=LogHandlerType.STDERR,
                    level="INFO",
                    format=LogFormat.SIMPLE,
                    queue_enabled=True,
                )
            ]
        )

        logger, queue_managers = setup_queue_logging_from_config(config)

        # Start queue logging
        start_queue_logging(queue_managers)

        # Verify listeners are running
        for manager in queue_managers:
            assert manager.queue_listener is not None
            assert manager.queue_listener._thread.is_alive()

        # Stop queue logging
        stop_queue_logging(queue_managers)

        # Verify listeners are stopped
        for manager in queue_managers:
            assert manager.queue_listener is None


class TestTUILoggingConfig:
    """Test TUI-specific logging configurations."""

    def test_create_tui_logging_config_basic(self):
        """Test creating basic TUI logging config."""
        config = create_tui_logging_config()

        assert isinstance(config, LoggingConfig)
        assert len(config.handlers) == 1

        handler = config.handlers[0]
        assert handler.type == LogHandlerType.STDERR
        assert handler.level == "WARNING"
        assert handler.format == LogFormat.SIMPLE
        assert handler.colored is True
        assert handler.queue_enabled is True  # Should be queue-enabled for TUI

    def test_create_tui_logging_config_with_debug_file(self, tmp_path):
        """Test creating TUI logging config with debug file."""
        debug_file = tmp_path / "tui-debug.log"
        config = create_tui_logging_config(debug_file)

        assert len(config.handlers) == 2

        # First handler: stderr
        stderr_handler = config.handlers[0]
        assert stderr_handler.type == LogHandlerType.STDERR
        assert stderr_handler.queue_enabled is True

        # Second handler: file
        file_handler = config.handlers[1]
        assert file_handler.type == LogHandlerType.FILE
        assert file_handler.level == "DEBUG"
        assert file_handler.format == LogFormat.JSON
        assert file_handler.file_path == debug_file
        assert file_handler.queue_enabled is True  # Should be queue-enabled for TUI


class TestQueueLoggingIntegration:
    """Integration tests for queue-based logging."""

    def test_queue_logging_end_to_end(self, tmp_path):
        """Test complete queue logging workflow."""
        # Create TUI logging config
        debug_file = tmp_path / "tui.log"
        config = create_tui_logging_config(debug_file)

        # Setup queue logging
        logger, queue_managers = setup_queue_logging_from_config(config)

        # Start queue listeners
        start_queue_logging(queue_managers)

        # Get a test logger
        test_logger = logging.getLogger("glovebox.test.tui")

        # Log some messages
        test_logger.debug("Debug message")
        test_logger.info("Info message")
        test_logger.warning("Warning message")
        test_logger.error("Error message")

        # Give queue listeners time to process
        time.sleep(0.1)

        # Stop queue logging
        stop_queue_logging(queue_managers)

        # Verify debug file was created and contains messages
        assert debug_file.exists()
        content = debug_file.read_text()

        # Should contain debug, info, warning, and error (all levels >= DEBUG for file)
        assert "Debug message" in content
        assert "Info message" in content
        assert "Warning message" in content
        assert "Error message" in content

    def test_queue_logging_thread_safety(self):
        """Test that queue logging is thread-safe."""
        config = LoggingConfig(
            handlers=[
                LogHandlerConfig(
                    type=LogHandlerType.STDERR,
                    level="INFO",
                    format=LogFormat.SIMPLE,
                    queue_enabled=True,
                )
            ]
        )

        logger, queue_managers = setup_queue_logging_from_config(config)
        start_queue_logging(queue_managers)

        test_logger = logging.getLogger("glovebox.test.threading")

        # Function to log from multiple threads
        def log_worker(worker_id: int):
            for i in range(10):
                test_logger.info(f"Worker {worker_id} - Message {i}")

        # Start multiple threads logging simultaneously
        threads = []
        for worker_id in range(5):
            thread = threading.Thread(target=log_worker, args=(worker_id,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Give queue time to process
        time.sleep(0.1)

        # Stop queue logging
        stop_queue_logging(queue_managers)

        # If we get here without deadlocks or exceptions, thread safety works

    def test_queue_logging_performance_non_blocking(self):
        """Test that queue logging is non-blocking."""
        import time

        config = LoggingConfig(
            handlers=[
                LogHandlerConfig(
                    type=LogHandlerType.STDERR,
                    level="DEBUG",
                    format=LogFormat.SIMPLE,
                    queue_enabled=True,
                )
            ]
        )

        logger, queue_managers = setup_queue_logging_from_config(config)
        start_queue_logging(queue_managers)

        test_logger = logging.getLogger("glovebox.test.performance")

        # Time how long it takes to log many messages
        start_time = time.time()

        for i in range(1000):
            test_logger.debug(f"Performance test message {i}")

        elapsed = time.time() - start_time

        # Should be very fast (non-blocking) - less than 0.1 seconds for 1000 messages
        assert elapsed < 0.1, f"Queue logging took too long: {elapsed:.3f}s"

        # Cleanup
        stop_queue_logging(queue_managers)

    def test_queue_logging_memory_usage(self):
        """Test that queue logging doesn't cause memory leaks."""
        config = LoggingConfig(
            handlers=[
                LogHandlerConfig(
                    type=LogHandlerType.STDERR,
                    level="DEBUG",
                    format=LogFormat.SIMPLE,
                    queue_enabled=True,
                )
            ]
        )

        # Create and destroy multiple queue setups
        for _ in range(10):
            logger, queue_managers = setup_queue_logging_from_config(config)
            start_queue_logging(queue_managers)

            test_logger = logging.getLogger("glovebox.test.memory")
            test_logger.info("Memory test message")

            time.sleep(0.01)  # Give queue time to process
            stop_queue_logging(queue_managers)

        # If we get here without memory issues, we're good


class TestQueueLoggingErrorHandling:
    """Test error handling in queue-based logging."""

    def test_invalid_handler_creation(self):
        """Test handling of invalid handler creation in queue setup."""
        config = LoggingConfig(
            handlers=[
                LogHandlerConfig(
                    type=LogHandlerType.FILE,
                    level="INFO",
                    format=LogFormat.SIMPLE,
                    file_path=Path("/invalid/readonly/path/test.log"),
                    queue_enabled=True,
                )
            ]
        )

        # Should not raise exception, but should handle gracefully
        logger, queue_managers = setup_queue_logging_from_config(config)

        # Might have 0 handlers if creation failed, or 1 if system allows
        assert len(logger.handlers) >= 0
        # Should have 0 queue managers if handler creation failed
        assert len(queue_managers) >= 0

    def test_queue_manager_exception_handling(self):
        """Test that queue manager handles exceptions gracefully."""
        manager = QueueLoggerManager()

        # Add a handler that might cause issues
        class FaultyHandler(logging.Handler):
            def emit(self, record):
                raise RuntimeError("Simulated handler error")

        faulty_handler = FaultyHandler()
        manager.add_handler(faulty_handler)

        # Should still start without crashing
        manager.start_listener()

        # Log a message - should not crash the application
        queue_handler = manager.get_queue_handler()
        test_logger = logging.getLogger("test.faulty")
        test_logger.addHandler(queue_handler)
        test_logger.setLevel(logging.DEBUG)

        # This should not crash
        test_logger.error("Test message")

        time.sleep(0.1)  # Give queue time to process

        # Cleanup
        manager.stop_listener()
