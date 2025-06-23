"""Tests for session ID flow from CLI to compilation services."""

import uuid
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from glovebox.metrics.collector import firmware_metrics
from glovebox.metrics.context import (
    clear_metrics_context,
    get_current_session_id,
    set_current_session_id,
)
from glovebox.metrics.decorators import track_firmware_operation
from glovebox.metrics.models import OperationMetrics, OperationStatus, OperationType


class TestSessionFlowIntegration:
    """Test session ID flow from decorators to context managers."""

    def setup_method(self):
        """Clear context before each test."""
        clear_metrics_context()

    def teardown_method(self):
        """Clear context after each test."""
        clear_metrics_context()

    def test_thread_local_context_basic(self):
        """Test basic thread-local context functionality."""
        session_id = str(uuid.uuid4())

        # Initially no session ID
        assert get_current_session_id() is None

        # Set session ID
        set_current_session_id(session_id)
        assert get_current_session_id() == session_id

        # Clear context
        clear_metrics_context()
        assert get_current_session_id() is None

    def test_firmware_metrics_uses_thread_local_session_id(self):
        """Test that firmware_metrics() picks up session_id from thread-local context."""
        session_id = str(uuid.uuid4())

        # Set session_id in thread-local context
        set_current_session_id(session_id)

        # Create metrics collector - should pick up session_id automatically
        with firmware_metrics() as metrics:
            # Check that session_id was set in context
            assert metrics._context.get("session_id") == session_id

    def test_firmware_metrics_explicit_session_id_overrides_thread_local(self):
        """Test that explicit session_id parameter overrides thread-local."""
        thread_session_id = str(uuid.uuid4())
        explicit_session_id = str(uuid.uuid4())

        # Set one session_id in thread-local context
        set_current_session_id(thread_session_id)

        # Create metrics collector with explicit session_id - should override thread-local
        with firmware_metrics(session_id=explicit_session_id) as metrics:
            # Check that explicit session_id was used
            assert metrics._context.get("session_id") == explicit_session_id

    @patch("glovebox.metrics.collector.create_metrics_service")
    def test_decorator_sets_thread_local_context(self, mock_create_service):
        """Test that the track_firmware_operation decorator sets thread-local context."""
        mock_service = Mock()
        mock_service.record_operation_start = Mock()
        mock_service.record_operation_end = Mock()
        mock_create_service.return_value = mock_service

        session_id = str(uuid.uuid4())

        # Mock context extractor that returns session_id
        def mock_extract_context(func, args, kwargs):
            return {"session_id": session_id}

        # Decorated function that checks thread-local context
        @track_firmware_operation(extract_context=mock_extract_context)
        def test_function():
            # Verify that session_id is available in thread-local context
            current_session_id = get_current_session_id()
            assert current_session_id == session_id
            return "success"

        # Execute the decorated function
        result = test_function()
        assert result == "success"

        # Verify context was cleared after execution
        assert get_current_session_id() is None

    @patch("glovebox.metrics.collector.create_metrics_service")
    def test_compilation_service_session_flow(self, mock_create_service):
        """Test session flow in a compilation service pattern."""
        mock_service = Mock()
        mock_service.record_operation_start = Mock()
        mock_service.record_operation_end = Mock()
        mock_create_service.return_value = mock_service

        session_id = str(uuid.uuid4())

        # Mock CLI context extractor
        def mock_cli_extract_context(func, args, kwargs):
            return {"session_id": session_id, "profile_name": "glove80/v25.05"}

        # Mock compilation service that uses firmware_metrics()
        def mock_compilation_service():
            """Simulates how compilation service uses metrics."""
            with firmware_metrics() as metrics:
                metrics.set_context(compilation_strategy="zmk_config")
                # Check that session_id is available
                assert metrics._context.get("session_id") == session_id
                return "compilation_success"

        # CLI command that calls compilation service
        @track_firmware_operation(extract_context=mock_cli_extract_context)
        def mock_cli_command():
            # This simulates the CLI command calling the compilation service
            return mock_compilation_service()

        # Execute the flow
        result = mock_cli_command()
        assert result == "compilation_success"

        # Verify context was cleared after CLI execution
        assert get_current_session_id() is None

        # Verify metrics service was called with proper context
        mock_service.record_operation_start.assert_called()
        mock_service.record_operation_end.assert_called()

    def test_nested_context_managers(self):
        """Test that nested metrics context managers work correctly."""
        session_id = str(uuid.uuid4())
        set_current_session_id(session_id)

        collected_session_ids = []

        # Simulate nested metrics collection
        with firmware_metrics() as outer_metrics:
            collected_session_ids.append(outer_metrics._context.get("session_id"))

            with firmware_metrics() as inner_metrics:
                collected_session_ids.append(inner_metrics._context.get("session_id"))

        # Both should have the same session_id
        assert collected_session_ids == [session_id, session_id]

    @patch("glovebox.metrics.collector.create_metrics_service")
    def test_error_handling_clears_context(self, mock_create_service):
        """Test that thread-local context is cleared even if decorated function fails."""
        mock_service = Mock()
        mock_service.record_operation_start = Mock()
        mock_service.record_operation_end = Mock()
        mock_create_service.return_value = mock_service

        session_id = str(uuid.uuid4())

        # Mock context extractor
        def mock_extract_context(func, args, kwargs):
            return {"session_id": session_id}

        @track_firmware_operation(extract_context=mock_extract_context)
        def failing_function():
            # Verify session_id is set during execution
            assert get_current_session_id() == session_id
            raise ValueError("Test error")

        # Execute and expect exception
        with pytest.raises(ValueError, match="Test error"):
            failing_function()

        # Verify context was cleared even after exception
        assert get_current_session_id() is None
