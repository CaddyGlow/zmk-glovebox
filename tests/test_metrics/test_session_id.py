"""Tests for session ID functionality in metrics system."""

import uuid
from datetime import datetime
from unittest.mock import Mock

import pytest
import typer

from glovebox.cli.app import AppContext
from glovebox.metrics.context_extractors import extract_cli_context
from glovebox.metrics.models import OperationMetrics, OperationStatus, OperationType


class TestSessionIdModel:
    """Test session_id field in OperationMetrics model."""

    def test_operation_metrics_with_session_id(self):
        """Test that OperationMetrics can store session_id."""
        session_id = str(uuid.uuid4())

        metrics = OperationMetrics(
            operation_id="test-op-123",
            operation_type=OperationType.LAYOUT_COMPILATION,
            status=OperationStatus.SUCCESS,
            start_time=datetime.now(),
            session_id=session_id,
        )

        assert metrics.session_id == session_id

    def test_operation_metrics_without_session_id(self):
        """Test that session_id is optional and defaults to None."""
        metrics = OperationMetrics(
            operation_id="test-op-123",
            operation_type=OperationType.LAYOUT_COMPILATION,
            status=OperationStatus.SUCCESS,
            start_time=datetime.now(),
        )

        assert metrics.session_id is None

    def test_operation_metrics_serialization_with_session_id(self):
        """Test that session_id is included in serialization."""
        session_id = str(uuid.uuid4())

        metrics = OperationMetrics(
            operation_id="test-op-123",
            operation_type=OperationType.LAYOUT_COMPILATION,
            status=OperationStatus.SUCCESS,
            start_time=datetime.now(),
            session_id=session_id,
        )

        data = metrics.model_dump(mode="json")
        assert data["session_id"] == session_id


class TestAppContextSessionId:
    """Test session ID generation in AppContext."""

    def test_app_context_generates_session_id(self):
        """Test that AppContext generates a unique session_id."""
        context = AppContext()

        assert context.session_id is not None
        assert isinstance(context.session_id, str)
        # Verify it's a valid UUID
        uuid.UUID(context.session_id)

    def test_app_context_different_sessions(self):
        """Test that different AppContext instances have different session IDs."""
        context1 = AppContext()
        context2 = AppContext()

        assert context1.session_id != context2.session_id


class TestCliContextExtraction:
    """Test session ID extraction from CLI context."""

    def test_extract_session_id_from_typer_context(self):
        """Test that session_id is extracted from typer context."""
        # Create mock AppContext with session_id
        app_context = AppContext()
        session_id = app_context.session_id

        # Create mock typer context
        typer_ctx = Mock(spec=typer.Context)
        typer_ctx.obj = app_context

        # Mock function and arguments
        mock_func = Mock()
        args = ()
        kwargs = {"ctx": typer_ctx}

        # Extract context
        context = extract_cli_context(mock_func, args, kwargs)

        assert context["session_id"] == session_id

    def test_extract_context_without_session_id(self):
        """Test context extraction when no session_id is available."""
        # Create mock typer context without session_id
        typer_ctx = Mock(spec=typer.Context)
        typer_ctx.obj = None

        # Mock function and arguments
        mock_func = Mock()
        args = ()
        kwargs = {"ctx": typer_ctx}

        # Extract context
        context = extract_cli_context(mock_func, args, kwargs)

        assert "session_id" not in context

    def test_extract_context_with_other_fields_and_session_id(self):
        """Test that session_id is extracted along with other context fields."""
        # Create mock AppContext with session_id
        app_context = AppContext()
        session_id = app_context.session_id

        # Create mock typer context
        typer_ctx = Mock(spec=typer.Context)
        typer_ctx.obj = app_context

        # Mock function and arguments with additional context
        mock_func = Mock()
        args = ()
        kwargs = {"ctx": typer_ctx, "profile": "glove80/v25.05", "force": True}

        # Extract context
        context = extract_cli_context(mock_func, args, kwargs)

        assert context["session_id"] == session_id
        assert context["profile_name"] == "glove80/v25.05"
        assert context["force"] is True


class TestSessionIdFiltering:
    """Test filtering metrics by session ID."""

    def test_filter_metrics_by_session_id(self):
        """Test filtering a list of metrics by session_id."""
        session1 = str(uuid.uuid4())
        session2 = str(uuid.uuid4())

        # Create metrics with different session IDs
        metrics = [
            OperationMetrics(
                operation_id="op1",
                operation_type=OperationType.LAYOUT_COMPILATION,
                status=OperationStatus.SUCCESS,
                start_time=datetime.now(),
                session_id=session1,
            ),
            OperationMetrics(
                operation_id="op2",
                operation_type=OperationType.FIRMWARE_COMPILATION,
                status=OperationStatus.SUCCESS,
                start_time=datetime.now(),
                session_id=session2,
            ),
            OperationMetrics(
                operation_id="op3",
                operation_type=OperationType.LAYOUT_COMPILATION,
                status=OperationStatus.SUCCESS,
                start_time=datetime.now(),
                session_id=session1,
            ),
            OperationMetrics(
                operation_id="op4",
                operation_type=OperationType.FIRMWARE_COMPILATION,
                status=OperationStatus.SUCCESS,
                start_time=datetime.now(),
                session_id=None,  # No session ID
            ),
        ]

        # Filter by session1
        session1_metrics = [m for m in metrics if m.session_id == session1]
        assert len(session1_metrics) == 2
        assert all(m.session_id == session1 for m in session1_metrics)

        # Filter by session2
        session2_metrics = [m for m in metrics if m.session_id == session2]
        assert len(session2_metrics) == 1
        assert session2_metrics[0].session_id == session2

        # Filter metrics without session ID
        no_session_metrics = [m for m in metrics if m.session_id is None]
        assert len(no_session_metrics) == 1
        assert no_session_metrics[0].session_id is None
