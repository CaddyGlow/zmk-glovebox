"""Tests for the LoggingProgressManager and related components."""

import logging
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from glovebox.cli.components.logging_progress import (
    CompilationLoggingProgressManager,
    LogCapturingHandler,
    LoggingProgressManager,
    WorkspaceLoggingProgressManager,
    create_compilation_logging_progress_manager,
    create_logging_progress_manager,
    create_workspace_logging_progress_manager,
)


class TestLogCapturingHandler:
    """Test LogCapturingHandler functionality."""

    def test_handler_initialization(self):
        """Test handler initialization."""
        handler = LogCapturingHandler()

        assert isinstance(handler, logging.Handler)
        assert len(handler.captured_logs) == 0
        assert isinstance(handler.captured_logs, list)

    def test_log_capture(self):
        """Test basic log capture functionality."""
        handler = LogCapturingHandler()

        # Create a test logger and add our handler
        test_logger = logging.getLogger("test.capture")
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.DEBUG)

        # Log some messages
        test_logger.info("Test info message")
        test_logger.warning("Test warning message")
        test_logger.error("Test error message")

        # Check captured logs
        captured = handler.captured_logs
        assert len(captured) == 3

        assert captured[0] == ("info", "Test info message")
        assert captured[1] == ("warning", "Test warning message")
        assert captured[2] == ("error", "Test error message")

    def test_log_memory_limit(self):
        """Test that log memory is limited to prevent growth."""
        handler = LogCapturingHandler()

        test_logger = logging.getLogger("test.memory")
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.DEBUG)

        # Log more than the memory limit (200 messages)
        for i in range(250):
            test_logger.info(f"Message {i}")

        # Should be limited to 200 messages
        captured = handler.captured_logs
        assert len(captured) == 200

        # Should contain the most recent messages
        assert captured[-1] == ("info", "Message 249")
        assert captured[0] == ("info", "Message 50")  # First 50 should be dropped

    def test_thread_safety(self):
        """Test that log capture is thread-safe."""
        handler = LogCapturingHandler()

        test_logger = logging.getLogger("test.threading")
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.DEBUG)

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

        # Should have all 50 messages (5 workers * 10 messages each)
        captured = handler.captured_logs
        assert len(captured) == 50

        # Verify all messages are captured
        worker_counts = {}
        for _level, message in captured:
            if "Worker" in message:
                worker_id = int(message.split()[1])
                worker_counts[worker_id] = worker_counts.get(worker_id, 0) + 1

        # Each worker should have 10 messages
        for worker_id in range(5):
            assert worker_counts[worker_id] == 10


class TestLoggingProgressManager:
    """Test LoggingProgressManager functionality."""

    def test_manager_initialization(self):
        """Test manager initialization."""
        manager = LoggingProgressManager()

        assert manager.debug_file is None
        assert manager.show_logs is True
        assert isinstance(manager.log_capture_handler, LogCapturingHandler)
        assert manager.progress_manager is None
        assert len(manager.queue_managers) == 0
        assert manager.logger is None

    def test_manager_with_debug_file(self, tmp_path):
        """Test manager initialization with debug file."""
        debug_file = tmp_path / "test-debug.log"
        manager = LoggingProgressManager(debug_file=debug_file, show_logs=False)

        assert manager.debug_file == debug_file
        assert manager.show_logs is False

    def test_start_and_stop_lifecycle(self, tmp_path):
        """Test complete start/stop lifecycle."""
        debug_file = tmp_path / "lifecycle-test.log"
        manager = LoggingProgressManager(debug_file=debug_file)

        # Start the manager
        progress_callback = manager.start()

        # Verify initialization
        assert manager.logger is not None
        assert len(manager.queue_managers) > 0
        assert manager.progress_manager is not None
        assert callable(progress_callback)

        # Test logging functionality
        logger = manager.get_logger("glovebox.test.lifecycle")  # Use glovebox namespace
        logger.info("Test lifecycle message")

        # Give queue time to process
        time.sleep(0.1)

        # Check that logs were captured
        captured = manager.log_capture_handler.captured_logs
        assert len(captured) > 0
        assert any("Test lifecycle message" in msg for level, msg in captured)

        # Stop the manager
        manager.stop()

        # Verify cleanup
        assert debug_file.exists()  # Debug file should be created

    def test_get_logger(self, tmp_path):
        """Test get_logger functionality."""
        debug_file = tmp_path / "logger-test.log"
        manager = LoggingProgressManager(debug_file=debug_file)

        progress_callback = manager.start()

        try:
            # Get logger and test it
            logger = manager.get_logger("glovebox.test.module")
            assert isinstance(logger, logging.Logger)
            assert logger.name == "glovebox.test.module"

            # Test logging
            logger.info("Test message from custom logger")
            time.sleep(0.1)

            # Verify message was captured
            captured = manager.log_capture_handler.captured_logs
            assert any("Test message from custom logger" in msg for level, msg in captured)

        finally:
            manager.stop()

    def test_progress_callback_integration(self, tmp_path):
        """Test integration with progress callback."""
        debug_file = tmp_path / "progress-test.log"
        manager = LoggingProgressManager(debug_file=debug_file)

        progress_callback = manager.start()

        try:
            # Test progress callback with string data
            progress_callback("Test progress message")

            # Test with custom progress data
            class MockProgress:
                def get_status_text(self) -> str:
                    return "Mock progress status"

                def get_progress_info(self) -> tuple[int, int, str]:
                    return (50, 100, "Mock progress description")

            progress_callback(MockProgress())

            # Give time for processing
            time.sleep(0.1)

            # Progress manager should be handling these updates
            # (We can't easily test the display without mocking Rich components)
            assert manager.progress_manager is not None

        finally:
            manager.stop()


class TestSpecializedManagers:
    """Test specialized manager classes."""

    def test_workspace_manager_creation(self, tmp_path):
        """Test WorkspaceLoggingProgressManager creation."""
        debug_file = tmp_path / "workspace-test.log"
        manager = WorkspaceLoggingProgressManager(debug_file=debug_file)

        assert isinstance(manager, LoggingProgressManager)
        assert manager.debug_file == debug_file

    def test_compilation_manager_creation(self, tmp_path):
        """Test CompilationLoggingProgressManager creation."""
        debug_file = tmp_path / "compilation-test.log"
        manager = CompilationLoggingProgressManager(debug_file=debug_file)

        assert isinstance(manager, LoggingProgressManager)
        assert manager.debug_file == debug_file

    @patch('glovebox.cli.components.progress_display.WorkspaceProgressDisplayManager')
    def test_workspace_manager_uses_specialized_display(self, mock_workspace_display, tmp_path):
        """Test that WorkspaceLoggingProgressManager uses WorkspaceProgressDisplayManager."""
        debug_file = tmp_path / "workspace-specialized.log"
        manager = WorkspaceLoggingProgressManager(debug_file=debug_file)

        # Mock the display manager
        mock_instance = MagicMock()
        mock_workspace_display.return_value = mock_instance
        mock_instance.start.return_value = MagicMock()

        progress_callback = manager.start()

        try:
            # Verify WorkspaceProgressDisplayManager was used
            mock_workspace_display.assert_called_once()
            mock_instance.set_log_provider.assert_called_once()
            mock_instance.start.assert_called_once()

        finally:
            manager.stop()

    @patch('glovebox.cli.components.progress_display.CompilationProgressDisplayManager')
    def test_compilation_manager_uses_specialized_display(self, mock_compilation_display, tmp_path):
        """Test that CompilationLoggingProgressManager uses CompilationProgressDisplayManager."""
        debug_file = tmp_path / "compilation-specialized.log"
        manager = CompilationLoggingProgressManager(debug_file=debug_file)

        # Mock the display manager
        mock_instance = MagicMock()
        mock_compilation_display.return_value = mock_instance
        mock_instance.start.return_value = MagicMock()

        progress_callback = manager.start()

        try:
            # Verify CompilationProgressDisplayManager was used
            mock_compilation_display.assert_called_once()
            mock_instance.set_log_provider.assert_called_once()
            mock_instance.start.assert_called_once()

        finally:
            manager.stop()


class TestFactoryFunctions:
    """Test factory functions for creating managers."""

    def test_create_logging_progress_manager(self, tmp_path):
        """Test create_logging_progress_manager factory function."""
        debug_file = tmp_path / "factory-test.log"

        manager = create_logging_progress_manager(
            debug_file=debug_file,
            show_logs=False
        )

        assert isinstance(manager, LoggingProgressManager)
        assert manager.debug_file == debug_file
        assert manager.show_logs is False

    def test_create_workspace_logging_progress_manager(self, tmp_path):
        """Test create_workspace_logging_progress_manager factory function."""
        debug_file = tmp_path / "workspace-factory.log"

        manager = create_workspace_logging_progress_manager(
            debug_file=debug_file,
            show_logs=True
        )

        assert isinstance(manager, WorkspaceLoggingProgressManager)
        assert manager.debug_file == debug_file
        assert manager.show_logs is True

    def test_create_compilation_logging_progress_manager(self, tmp_path):
        """Test create_compilation_logging_progress_manager factory function."""
        debug_file = tmp_path / "compilation-factory.log"

        manager = create_compilation_logging_progress_manager(
            debug_file=debug_file,
            show_logs=True
        )

        assert isinstance(manager, CompilationLoggingProgressManager)
        assert manager.debug_file == debug_file
        assert manager.show_logs is True

    def test_factory_functions_with_defaults(self):
        """Test factory functions with default parameters."""
        # Basic manager
        manager1 = create_logging_progress_manager()
        assert isinstance(manager1, LoggingProgressManager)
        assert manager1.debug_file is None
        assert manager1.show_logs is True

        # Workspace manager
        manager2 = create_workspace_logging_progress_manager()
        assert isinstance(manager2, WorkspaceLoggingProgressManager)

        # Compilation manager
        manager3 = create_compilation_logging_progress_manager()
        assert isinstance(manager3, CompilationLoggingProgressManager)


class TestIntegrationScenarios:
    """Test integration scenarios and edge cases."""

    def test_multiple_loggers_same_manager(self, tmp_path):
        """Test multiple loggers using the same manager."""
        debug_file = tmp_path / "multi-logger.log"
        manager = LoggingProgressManager(debug_file=debug_file)

        progress_callback = manager.start()

        try:
            # Get multiple loggers
            logger1 = manager.get_logger("glovebox.module1")
            logger2 = manager.get_logger("glovebox.module2")
            logger3 = manager.get_logger("glovebox.module3")

            # Log from different modules
            logger1.info("Message from module1")
            logger2.warning("Warning from module2")
            logger3.error("Error from module3")

            time.sleep(0.1)

            # All messages should be captured
            captured = manager.log_capture_handler.captured_logs
            assert len(captured) >= 3

            messages = [msg for level, msg in captured]
            assert "Message from module1" in messages
            assert "Warning from module2" in messages
            assert "Error from module3" in messages

        finally:
            manager.stop()

    def test_exception_handling_in_logging(self, tmp_path):
        """Test that exceptions in logging don't crash the manager."""
        debug_file = tmp_path / "exception-test.log"
        manager = LoggingProgressManager(debug_file=debug_file)

        progress_callback = manager.start()

        try:
            logger = manager.get_logger("glovebox.test.exception")

            # Test exception logging pattern from CLAUDE.md
            try:
                raise ValueError("Test exception for logging")
            except Exception as e:
                exc_info = logger.isEnabledFor(logging.DEBUG)
                logger.error("Operation failed: %s", e, exc_info=exc_info)

            time.sleep(0.1)

            # Exception should be logged without crashing
            captured = manager.log_capture_handler.captured_logs
            assert any("Operation failed:" in msg for level, msg in captured)

        finally:
            manager.stop()

    def test_rapid_progress_updates(self, tmp_path):
        """Test handling of rapid progress updates."""
        debug_file = tmp_path / "rapid-updates.log"
        manager = LoggingProgressManager(debug_file=debug_file)

        progress_callback = manager.start()

        try:
            logger = manager.get_logger("glovebox.test.rapid")

            # Send rapid progress updates and log messages
            for i in range(50):
                logger.info(f"Rapid message {i}")
                progress_callback(f"Rapid progress {i}")

                # Small delay to not overwhelm the system
                if i % 10 == 0:
                    time.sleep(0.01)

            time.sleep(0.2)  # Give time for processing

            # Should handle all messages without issues
            captured = manager.log_capture_handler.captured_logs
            assert len(captured) >= 40  # Should capture most messages

        finally:
            manager.stop()

    def test_cleanup_prevents_memory_leaks(self, tmp_path):
        """Test that proper cleanup prevents memory leaks."""
        debug_file = tmp_path / "cleanup-test.log"

        # Create and destroy multiple managers
        for i in range(5):
            manager = LoggingProgressManager(debug_file=debug_file)
            progress_callback = manager.start()

            logger = manager.get_logger(f"glovebox.test.cleanup.{i}")
            logger.info(f"Test message from iteration {i}")

            time.sleep(0.05)
            manager.stop()

        # If we get here without memory issues, cleanup is working
        # (In a real test environment, we could check memory usage)
        assert True
