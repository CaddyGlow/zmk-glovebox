"""Tests for metrics CLI commands."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from glovebox.cli.app import app
from glovebox.cli.commands import register_all_commands
from glovebox.metrics.models import (
    ErrorCategory,
    FirmwareMetrics,
    LayoutMetrics,
    MetricsSnapshot,
    MetricsSummary,
    OperationStatus,
    OperationType,
)


# Register commands with the app before running tests
register_all_commands(app)


@pytest.fixture
def cli_runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def sample_metrics():
    """Create sample metrics for testing."""
    now = datetime.now()
    return [
        LayoutMetrics(
            operation_id="layout-1",
            operation_type=OperationType.LAYOUT_COMPILATION,
            status=OperationStatus.SUCCESS,
            start_time=now - timedelta(minutes=30),
            end_time=now - timedelta(minutes=29, seconds=58),
            duration_seconds=2.0,
            profile_name="glove80/v25.05",
            keyboard_name="glove80",
            firmware_version="v25.05",
            layer_count=5,
            binding_count=80,
        ),
        FirmwareMetrics(
            operation_id="firmware-1",
            operation_type=OperationType.FIRMWARE_COMPILATION,
            status=OperationStatus.SUCCESS,
            start_time=now - timedelta(minutes=20),
            end_time=now - timedelta(minutes=19, seconds=30),
            duration_seconds=30.0,
            profile_name="glove80/v25.05",
            keyboard_name="glove80",
            firmware_version="v25.05",
            compilation_strategy="zmk_config",
        ),
        LayoutMetrics(
            operation_id="layout-2",
            operation_type=OperationType.LAYOUT_COMPILATION,
            status=OperationStatus.FAILURE,
            start_time=now - timedelta(minutes=10),
            end_time=now - timedelta(minutes=9, seconds=59),
            duration_seconds=1.0,
            profile_name="glove80/v25.05",
            keyboard_name="glove80",
            firmware_version="v25.05",
            error_message="Validation failed",
            error_category=ErrorCategory.VALIDATION_ERROR,
        ),
    ]


@pytest.fixture
def sample_summary():
    """Create sample summary for testing."""
    return MetricsSummary(
        start_time=datetime.now() - timedelta(days=7),
        end_time=datetime.now(),
        total_operations=10,
        successful_operations=8,
        failed_operations=2,
        layout_success_rate=0.75,
        firmware_success_rate=1.0,
        average_duration_seconds=15.5,
        median_duration_seconds=12.0,
        fastest_operation_seconds=0.5,
        slowest_operation_seconds=60.0,
        cache_hit_rate=0.3,
        cache_enabled_operations=5,
        error_breakdown={ErrorCategory.VALIDATION_ERROR: 2},
        most_common_error=ErrorCategory.VALIDATION_ERROR,
    )


class TestMetricsShowCommand:
    """Test the metrics show command."""

    @patch("glovebox.cli.commands.metrics.create_metrics_service")
    def test_show_metrics_basic(self, mock_create_service, cli_runner, sample_metrics):
        """Test basic metrics show command."""
        mock_service = Mock()
        mock_service.get_operation_metrics.return_value = sample_metrics
        mock_create_service.return_value = mock_service

        result = cli_runner.invoke(app, ["metrics", "show"])

        assert result.exit_code == 0
        # Verify service was called correctly
        mock_service.get_operation_metrics.assert_called_once_with(
            operation_type=None, start_time=None, limit=10
        )
        # Check output contains operation data
        assert "layout-1..." in result.stdout or "layout-1" in result.stdout
        assert "firmware..." in result.stdout  # Operation ID is truncated in display
        assert "layout_comp" in result.stdout  # Truncated type name
        assert "firmware_co" in result.stdout  # Truncated type name

    @patch("glovebox.cli.commands.metrics.create_metrics_service")
    def test_show_metrics_with_filters(
        self, mock_create_service, cli_runner, sample_metrics
    ):
        """Test metrics show with filters."""
        mock_service = Mock()
        mock_service.get_operation_metrics.return_value = sample_metrics[
            :1
        ]  # Only layout metrics
        mock_create_service.return_value = mock_service

        result = cli_runner.invoke(
            app,
            [
                "metrics",
                "show",
                "--type",
                "layout_compilation",
                "--limit",
                "5",
                "--days",
                "7",
            ],
        )

        assert result.exit_code == 0
        # Verify service was called with filters
        call_args = mock_service.get_operation_metrics.call_args
        assert call_args[1]["operation_type"] == OperationType.LAYOUT_COMPILATION
        assert call_args[1]["limit"] == 5
        assert (
            call_args[1]["start_time"] is not None
        )  # Should have calculated time filter

    @patch("glovebox.cli.commands.metrics.create_metrics_service")
    def test_show_metrics_json_output(
        self, mock_create_service, cli_runner, sample_metrics
    ):
        """Test metrics show with JSON output."""
        mock_service = Mock()
        mock_service.get_operation_metrics.return_value = sample_metrics
        mock_create_service.return_value = mock_service

        result = cli_runner.invoke(app, ["metrics", "show", "--json"])

        assert result.exit_code == 0
        # Verify output is valid JSON
        output_data = json.loads(result.stdout)
        assert len(output_data) == 3
        assert output_data[0]["operation_id"] == "layout-1"

    @patch("glovebox.cli.commands.metrics.create_metrics_service")
    def test_show_metrics_empty_results(self, mock_create_service, cli_runner):
        """Test metrics show with no results."""
        mock_service = Mock()
        mock_service.get_operation_metrics.return_value = []
        mock_create_service.return_value = mock_service

        result = cli_runner.invoke(app, ["metrics", "show"])

        assert result.exit_code == 0
        assert "No metrics found" in result.stdout

    @patch("glovebox.cli.commands.metrics.create_metrics_service")
    def test_show_metrics_service_error(self, mock_create_service, cli_runner):
        """Test metrics show with service error."""
        mock_service = Mock()
        mock_service.get_operation_metrics.side_effect = Exception("Service error")
        mock_create_service.return_value = mock_service

        result = cli_runner.invoke(app, ["metrics", "show"])

        assert result.exit_code == 1
        assert "Error:" in result.stdout


class TestMetricsSummaryCommand:
    """Test the metrics summary command."""

    @patch("glovebox.cli.commands.metrics.create_metrics_service")
    def test_summary_basic(self, mock_create_service, cli_runner, sample_summary):
        """Test basic summary command."""
        mock_service = Mock()
        mock_service.generate_summary.return_value = sample_summary
        mock_create_service.return_value = mock_service

        result = cli_runner.invoke(app, ["metrics", "summary"])

        assert result.exit_code == 0
        # Verify service was called
        mock_service.generate_summary.assert_called_once()

        # Check summary content
        assert "Total Operations" in result.stdout
        assert "10" in result.stdout  # Total operations
        assert "75.0%" in result.stdout  # Layout success rate
        assert "100.0%" in result.stdout  # Firmware success rate

    @patch("glovebox.cli.commands.metrics.create_metrics_service")
    def test_summary_with_days_filter(
        self, mock_create_service, cli_runner, sample_summary
    ):
        """Test summary with days filter."""
        mock_service = Mock()
        mock_service.generate_summary.return_value = sample_summary
        mock_create_service.return_value = mock_service

        result = cli_runner.invoke(app, ["metrics", "summary", "--days", "30"])

        assert result.exit_code == 0
        # Verify service was called with time range
        call_args = mock_service.generate_summary.call_args
        assert call_args[1]["start_time"] is not None
        assert call_args[1]["end_time"] is not None

    @patch("glovebox.cli.commands.metrics.create_metrics_service")
    def test_summary_json_output(self, mock_create_service, cli_runner, sample_summary):
        """Test summary with JSON output."""
        mock_service = Mock()
        mock_service.generate_summary.return_value = sample_summary
        mock_create_service.return_value = mock_service

        result = cli_runner.invoke(app, ["metrics", "summary", "--json"])

        assert result.exit_code == 0
        # Verify output is valid JSON
        output_data = json.loads(result.stdout)
        assert output_data["total_operations"] == 10
        assert output_data["successful_operations"] == 8

    @patch("glovebox.cli.commands.metrics.create_metrics_service")
    def test_summary_with_error_breakdown(
        self, mock_create_service, cli_runner, sample_summary
    ):
        """Test summary displays error breakdown."""
        mock_service = Mock()
        mock_service.generate_summary.return_value = sample_summary
        mock_create_service.return_value = mock_service

        result = cli_runner.invoke(app, ["metrics", "summary"])

        assert result.exit_code == 0
        # Check error breakdown table is shown
        assert "Error Breakdown" in result.stdout
        assert "validation_error" in result.stdout


class TestMetricsExportCommand:
    """Test the metrics export command."""

    @patch("glovebox.cli.commands.metrics.create_metrics_service")
    def test_export_basic(
        self, mock_create_service, cli_runner, sample_metrics, tmp_path
    ):
        """Test basic export command."""
        mock_service = Mock()
        snapshot = MetricsSnapshot(
            glovebox_version="1.0.0",
            operations=sample_metrics,
            total_operations=len(sample_metrics),
        )
        mock_service.export_metrics.return_value = snapshot
        mock_create_service.return_value = mock_service

        output_file = tmp_path / "export.json"
        result = cli_runner.invoke(app, ["metrics", "export", str(output_file)])

        assert result.exit_code == 0
        # Verify service was called
        mock_service.export_metrics.assert_called_once()
        call_args = mock_service.export_metrics.call_args
        assert call_args[1]["output_file"] == output_file

        # Check success message
        assert "Exported 3 metrics" in result.stdout

    @patch("glovebox.cli.commands.metrics.create_metrics_service")
    def test_export_with_filters(
        self, mock_create_service, cli_runner, sample_metrics, tmp_path
    ):
        """Test export with time and type filters."""
        mock_service = Mock()
        snapshot = MetricsSnapshot(
            operations=sample_metrics[:1],
            total_operations=1,
        )
        mock_service.export_metrics.return_value = snapshot
        mock_create_service.return_value = mock_service

        output_file = tmp_path / "filtered_export.json"
        result = cli_runner.invoke(
            app,
            [
                "metrics",
                "export",
                str(output_file),
                "--days",
                "7",
                "--type",
                "layout_compilation",
            ],
        )

        assert result.exit_code == 0
        # Verify filters were applied
        call_args = mock_service.export_metrics.call_args
        assert call_args[1]["start_time"] is not None
        assert call_args[1]["end_time"] is not None

    @patch("glovebox.cli.commands.metrics.create_metrics_service")
    def test_export_service_error(self, mock_create_service, cli_runner, tmp_path):
        """Test export with service error."""
        mock_service = Mock()
        mock_service.export_metrics.side_effect = Exception("Export failed")
        mock_create_service.return_value = mock_service

        output_file = tmp_path / "export.json"
        result = cli_runner.invoke(app, ["metrics", "export", str(output_file)])

        assert result.exit_code == 1
        assert "Error:" in result.stdout


class TestMetricsClearCommand:
    """Test the metrics clear command."""

    @patch("glovebox.cli.commands.metrics.create_metrics_service")
    def test_clear_all_with_force(self, mock_create_service, cli_runner):
        """Test clearing all metrics with force flag."""
        mock_service = Mock()
        mock_service.get_metrics_count.return_value = 10
        mock_service.clear_metrics.return_value = 10
        mock_create_service.return_value = mock_service

        result = cli_runner.invoke(app, ["metrics", "clear", "--force"])

        assert result.exit_code == 0
        mock_service.clear_metrics.assert_called_once_with(
            before_time=None, operation_type=None
        )
        assert "Cleared 10 metrics" in result.stdout

    @patch("glovebox.cli.commands.metrics.create_metrics_service")
    def test_clear_by_type(self, mock_create_service, cli_runner):
        """Test clearing metrics by type."""
        mock_service = Mock()
        mock_service.get_metrics_count.return_value = 5
        mock_service.clear_metrics.return_value = 3
        mock_create_service.return_value = mock_service

        result = cli_runner.invoke(
            app, ["metrics", "clear", "--type", "layout_compilation", "--force"]
        )

        assert result.exit_code == 0
        mock_service.clear_metrics.assert_called_once_with(
            before_time=None, operation_type=OperationType.LAYOUT_COMPILATION
        )

    @patch("glovebox.cli.commands.metrics.create_metrics_service")
    def test_clear_older_than(self, mock_create_service, cli_runner):
        """Test clearing metrics older than specified days."""
        mock_service = Mock()
        mock_service.get_metrics_count.return_value = 8
        mock_service.clear_metrics.return_value = 5
        mock_create_service.return_value = mock_service

        result = cli_runner.invoke(
            app, ["metrics", "clear", "--older-than", "30", "--force"]
        )

        assert result.exit_code == 0
        call_args = mock_service.clear_metrics.call_args
        assert call_args[1]["before_time"] is not None
        assert call_args[1]["operation_type"] is None

    @patch("glovebox.cli.commands.metrics.create_metrics_service")
    def test_clear_no_metrics(self, mock_create_service, cli_runner):
        """Test clearing when no metrics exist."""
        mock_service = Mock()
        mock_service.get_metrics_count.return_value = 0
        mock_create_service.return_value = mock_service

        result = cli_runner.invoke(app, ["metrics", "clear", "--force"])

        assert result.exit_code == 0
        assert "No metrics to clear" in result.stdout
        # Should not call clear_metrics
        mock_service.clear_metrics.assert_not_called()

    @patch("glovebox.cli.commands.metrics.create_metrics_service")
    def test_clear_cancelled_by_user(self, mock_create_service, cli_runner):
        """Test clearing cancelled by user confirmation."""
        mock_service = Mock()
        mock_service.get_metrics_count.return_value = 10
        mock_create_service.return_value = mock_service

        # Simulate user saying 'no' to confirmation
        result = cli_runner.invoke(app, ["metrics", "clear"], input="n\n")

        assert result.exit_code == 0
        assert "Cancelled" in result.stdout
        # Should not call clear_metrics
        mock_service.clear_metrics.assert_not_called()


class TestMetricsCountCommand:
    """Test the metrics count command."""

    @patch("glovebox.cli.commands.metrics.create_metrics_service")
    def test_count_basic(self, mock_create_service, cli_runner):
        """Test basic count command."""
        mock_service = Mock()
        mock_service.get_metrics_count.return_value = 42
        mock_create_service.return_value = mock_service

        result = cli_runner.invoke(app, ["metrics", "count"])

        assert result.exit_code == 0
        assert "Total metrics stored: 42" in result.stdout

    @patch("glovebox.cli.commands.metrics.create_metrics_service")
    def test_count_zero(self, mock_create_service, cli_runner):
        """Test count command with zero metrics."""
        mock_service = Mock()
        mock_service.get_metrics_count.return_value = 0
        mock_create_service.return_value = mock_service

        result = cli_runner.invoke(app, ["metrics", "count"])

        assert result.exit_code == 0
        assert "Total metrics stored: 0" in result.stdout

    @patch("glovebox.cli.commands.metrics.create_metrics_service")
    def test_count_service_error(self, mock_create_service, cli_runner):
        """Test count command with service error."""
        mock_service = Mock()
        mock_service.get_metrics_count.side_effect = Exception("Count failed")
        mock_create_service.return_value = mock_service

        result = cli_runner.invoke(app, ["metrics", "count"])

        assert result.exit_code == 1
        assert "Error:" in result.stdout


class TestUtilityFunctions:
    """Test utility functions used by CLI commands."""

    def test_format_duration_milliseconds(self):
        """Test duration formatting for milliseconds."""
        from glovebox.cli.commands.metrics import format_duration

        assert format_duration(0.001) == "1ms"
        assert format_duration(0.123) == "123ms"
        assert format_duration(0.999) == "999ms"

    def test_format_duration_seconds(self):
        """Test duration formatting for seconds."""
        from glovebox.cli.commands.metrics import format_duration

        assert format_duration(1.0) == "1.0s"
        assert format_duration(1.5) == "1.5s"
        assert format_duration(59.9) == "59.9s"

    def test_format_duration_minutes(self):
        """Test duration formatting for minutes."""
        from glovebox.cli.commands.metrics import format_duration

        assert format_duration(60.0) == "1.0m"
        assert format_duration(90.0) == "1.5m"
        assert format_duration(3599.0) == "60.0m"

    def test_format_duration_hours(self):
        """Test duration formatting for hours."""
        from glovebox.cli.commands.metrics import format_duration

        assert format_duration(3600.0) == "1.0h"
        assert format_duration(5400.0) == "1.5h"

    def test_format_duration_none(self):
        """Test duration formatting for None."""
        from glovebox.cli.commands.metrics import format_duration

        assert format_duration(None) == "N/A"

    def test_format_success_rate(self):
        """Test success rate formatting."""
        from glovebox.cli.commands.metrics import format_success_rate

        assert format_success_rate(0.0) == "0.0%"
        assert format_success_rate(0.5) == "50.0%"
        assert format_success_rate(0.756) == "75.6%"
        assert format_success_rate(1.0) == "100.0%"
        assert format_success_rate(None) == "N/A"

    def test_format_datetime(self):
        """Test datetime formatting."""
        from glovebox.cli.commands.metrics import format_datetime

        dt = datetime(2025, 6, 21, 14, 30, 45)
        assert format_datetime(dt) == "2025-06-21 14:30:45"
        assert format_datetime(None) == "N/A"
