"""Tests for metrics CLI commands with session ID functionality."""

import uuid
from datetime import datetime
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from glovebox.cli.commands.metrics import metrics_app
from glovebox.metrics.models import OperationMetrics, OperationStatus, OperationType


@pytest.fixture
def mock_metrics_service(monkeypatch):
    """Mock metrics service for testing."""
    mock_service = Mock()
    mock_storage = Mock()
    mock_service.storage = mock_storage

    # Mock the create_metrics_service function
    def mock_create_service():
        return mock_service

    monkeypatch.setattr(
        "glovebox.cli.commands.metrics.create_metrics_service", mock_create_service
    )
    return mock_service


@pytest.fixture
def sample_metrics_with_sessions():
    """Create sample metrics with different session IDs."""
    session1 = str(uuid.uuid4())
    session2 = str(uuid.uuid4())

    return [
        OperationMetrics(
            operation_id="op1",
            operation_type=OperationType.LAYOUT_COMPILATION,
            status=OperationStatus.SUCCESS,
            start_time=datetime.now(),
            session_id=session1,
            profile_name="glove80/v25.05",
            duration_seconds=1.5,
        ),
        OperationMetrics(
            operation_id="op2",
            operation_type=OperationType.FIRMWARE_COMPILATION,
            status=OperationStatus.SUCCESS,
            start_time=datetime.now(),
            session_id=session1,
            profile_name="glove80/v25.05",
            duration_seconds=5.2,
        ),
        OperationMetrics(
            operation_id="op3",
            operation_type=OperationType.LAYOUT_COMPILATION,
            status=OperationStatus.FAILURE,
            start_time=datetime.now(),
            session_id=session2,
            profile_name="planck/v23.08",
            duration_seconds=0.8,
        ),
        OperationMetrics(
            operation_id="op4",
            operation_type=OperationType.FIRMWARE_FLASH,
            status=OperationStatus.SUCCESS,
            start_time=datetime.now(),
            session_id=None,  # No session ID
            profile_name="planck/v23.08",
            duration_seconds=2.1,
        ),
    ]


class TestMetricsShowCommand:
    """Test metrics show command with session ID support."""

    def test_show_metrics_includes_session_column(
        self, mock_metrics_service, sample_metrics_with_sessions
    ):
        """Test that show command includes session ID column."""
        mock_metrics_service.get_operation_metrics.return_value = (
            sample_metrics_with_sessions
        )

        runner = CliRunner()
        result = runner.invoke(metrics_app, ["show"])

        assert result.exit_code == 0
        assert "Session" in result.stdout
        assert "Recent Operation Metrics" in result.stdout

    def test_show_metrics_filter_by_session(
        self, mock_metrics_service, sample_metrics_with_sessions
    ):
        """Test filtering metrics by session ID."""
        mock_metrics_service.get_operation_metrics.return_value = (
            sample_metrics_with_sessions
        )
        session_id = sample_metrics_with_sessions[0].session_id

        runner = CliRunner()
        result = runner.invoke(metrics_app, ["show", "--session", session_id])

        assert result.exit_code == 0
        # Should show filtered results
        mock_metrics_service.get_operation_metrics.assert_called_once()

    def test_show_metrics_json_includes_session_id(
        self, mock_metrics_service, sample_metrics_with_sessions
    ):
        """Test that JSON output includes session_id field."""
        mock_metrics_service.get_operation_metrics.return_value = (
            sample_metrics_with_sessions
        )

        runner = CliRunner()
        result = runner.invoke(metrics_app, ["show", "--json"])

        assert result.exit_code == 0
        # JSON output should contain session_id field
        assert "session_id" in result.stdout


class TestMetricsSummaryCommand:
    """Test metrics summary command with session ID support."""

    def test_summary_with_session_filter(
        self, mock_metrics_service, sample_metrics_with_sessions
    ):
        """Test summary command with session filter."""
        from glovebox.metrics.models import MetricsSummary

        mock_metrics_service.get_operation_metrics.return_value = (
            sample_metrics_with_sessions
        )
        mock_metrics_service.generate_summary.return_value = MetricsSummary(
            start_time=datetime.now(),
            end_time=datetime.now(),
            total_operations=2,
            successful_operations=2,
            failed_operations=0,
            average_duration_seconds=3.35,
            median_duration_seconds=3.35,
            fastest_operation_seconds=1.5,
            slowest_operation_seconds=5.2,
        )

        session_id = sample_metrics_with_sessions[0].session_id
        runner = CliRunner()
        result = runner.invoke(metrics_app, ["summary", "--session", session_id])

        assert result.exit_code == 0
        assert "Session Metrics Summary" in result.stdout
        assert session_id[:8] in result.stdout

    def test_summary_shows_sessions_breakdown(
        self, mock_metrics_service, sample_metrics_with_sessions
    ):
        """Test that summary shows sessions breakdown when not filtering."""
        from glovebox.metrics.models import MetricsSummary

        mock_metrics_service.get_operation_metrics.return_value = (
            sample_metrics_with_sessions
        )
        mock_metrics_service.generate_summary.return_value = MetricsSummary(
            start_time=datetime.now(),
            end_time=datetime.now(),
            total_operations=4,
            successful_operations=3,
            failed_operations=1,
            average_duration_seconds=2.4,
            median_duration_seconds=1.8,
            fastest_operation_seconds=0.8,
            slowest_operation_seconds=5.2,
        )

        runner = CliRunner()
        result = runner.invoke(metrics_app, ["summary"])

        assert result.exit_code == 0
        assert "Sessions Breakdown" in result.stdout


class TestMetricsSessionsCommand:
    """Test the new sessions command."""

    def test_sessions_command_shows_session_list(
        self, mock_metrics_service, sample_metrics_with_sessions
    ):
        """Test that sessions command shows list of sessions."""
        mock_metrics_service.get_operation_metrics.return_value = (
            sample_metrics_with_sessions
        )

        runner = CliRunner()
        result = runner.invoke(metrics_app, ["sessions"])

        assert result.exit_code == 0
        assert "Recent Sessions" in result.stdout
        assert "Session" in result.stdout and "ID" in result.stdout
        assert "Success" in result.stdout
        assert "Rate" in result.stdout

    def test_sessions_command_json_output(
        self, mock_metrics_service, sample_metrics_with_sessions
    ):
        """Test sessions command JSON output."""
        mock_metrics_service.get_operation_metrics.return_value = (
            sample_metrics_with_sessions
        )

        runner = CliRunner()
        result = runner.invoke(metrics_app, ["sessions", "--json"])

        assert result.exit_code == 0
        assert "session_id" in result.stdout
        assert "total_operations" in result.stdout
        assert "success_rate" in result.stdout

    def test_sessions_command_with_no_metrics(self, mock_metrics_service):
        """Test sessions command when no metrics exist."""
        mock_metrics_service.get_operation_metrics.return_value = []

        runner = CliRunner()
        result = runner.invoke(metrics_app, ["sessions"])

        assert result.exit_code == 0
        assert "No metrics found" in result.stdout


class TestSessionIdFiltering:
    """Test session ID filtering functionality."""

    def test_session_id_partial_match_display(self, sample_metrics_with_sessions):
        """Test that session IDs are displayed with partial match (first 8 chars)."""
        session_id = sample_metrics_with_sessions[0].session_id

        # Test the display format
        session_display = session_id[:8] + "..." if session_id else "N/A"
        assert len(session_display) == 11  # 8 chars + "..."
        assert session_display.startswith(session_id[:8])

    def test_no_session_id_handling(self, sample_metrics_with_sessions):
        """Test handling of metrics without session ID."""
        no_session_metric = sample_metrics_with_sessions[3]  # Has session_id=None

        assert no_session_metric.session_id is None
        session_display = (
            no_session_metric.session_id[:8] + "..."
            if no_session_metric.session_id
            else "N/A"
        )
        assert session_display == "N/A"
