"""Tests for the new SessionMetrics CLI commands."""

import json
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from glovebox.cli.commands.metrics import (
    _complete_session_uuid,
    _find_session_by_prefix,
    _format_duration,
    _format_timestamp,
    metrics_app,
)


pytestmark = [pytest.mark.docker, pytest.mark.integration]


@pytest.fixture
def mock_cache_manager():
    """Mock cache manager for testing."""
    cache_manager = Mock()
    cache_manager.keys.return_value = []
    cache_manager.get.return_value = None
    cache_manager.get_metadata.return_value = None
    cache_manager.delete.return_value = None
    return cache_manager


@pytest.fixture
def sample_session_data():
    """Create sample session data for testing."""
    session1_uuid = str(uuid.uuid4())
    session2_uuid = str(uuid.uuid4())

    session1_data = {
        "session_info": {
            "session_id": "session_1234",
            "start_time": "2024-01-01T10:00:00Z",
            "end_time": "2024-01-01T10:05:00Z",
            "duration_seconds": 300.0,
            "exit_code": 0,
            "success": True,
            "cli_args": ["glovebox", "layout", "compile", "test.json"],
        },
        "counters": {"operations_total": {"values": {"()": "1"}}},
        "gauges": {"memory_usage": {"values": {"()": "1024"}}},
        "histograms": {"compile_time": {"total_count": 1, "total_sum": 300.0}},
        "summaries": {"file_sizes": {"total_count": 3, "total_sum": 15000.0}},
        "activity_log": [
            {
                "timestamp": 1704103200.0,
                "metric_name": "operations_total",
                "operation": "inc",
                "value": 1,
            }
        ],
    }

    session2_data = {
        "session_info": {
            "session_id": "session_5678",
            "start_time": "2024-01-01T11:00:00Z",
            "end_time": "2024-01-01T11:02:00Z",
            "duration_seconds": 120.0,
            "exit_code": 1,
            "success": False,
            "cli_args": ["glovebox", "firmware", "flash", "test.uf2"],
        },
        "counters": {},
        "gauges": {},
        "histograms": {},
        "summaries": {},
    }

    return {session1_uuid: session1_data, session2_uuid: session2_data}


class TestUtilityFunctions:
    """Test utility functions used by metrics commands."""

    def test_format_duration_seconds(self):
        """Test duration formatting for seconds."""
        assert _format_duration(0.5) == "0.500s"
        assert _format_duration(1.0) == "1.0s"
        assert _format_duration(30.5) == "30.5s"

    def test_format_duration_minutes(self):
        """Test duration formatting for minutes."""
        assert _format_duration(60) == "1.0m"
        assert _format_duration(150) == "2.5m"
        assert _format_duration(3540) == "59.0m"

    def test_format_duration_hours(self):
        """Test duration formatting for hours."""
        assert _format_duration(3600) == "1.0h"
        assert _format_duration(7200) == "2.0h"
        assert _format_duration(10800) == "3.0h"

    def test_format_timestamp_recent(self):
        """Test timestamp formatting for recent times."""

        # Use UTC to avoid timezone issues
        now = datetime.now(UTC)
        recent = (now - timedelta(seconds=30)).isoformat()
        result = _format_timestamp(recent)
        assert result == "just now" or "ago" in result

        minutes_ago = (now - timedelta(minutes=15)).isoformat()
        result = _format_timestamp(minutes_ago)
        assert "ago" in result or result == "just now"

        hours_ago = (now - timedelta(hours=2)).isoformat()
        result = _format_timestamp(hours_ago)
        assert "ago" in result or result == "just now"

        days_ago = (now - timedelta(days=3)).isoformat()
        result = _format_timestamp(days_ago)
        assert "ago" in result

    def test_format_timestamp_invalid(self):
        """Test timestamp formatting with invalid input."""
        invalid_timestamp = "invalid-timestamp"
        assert _format_timestamp(invalid_timestamp) == invalid_timestamp


class TestPrefixMatching:
    """Test Docker-style prefix matching functionality."""

    @patch("glovebox.cli.commands.metrics._get_metrics_cache_manager")
    def test_find_session_by_prefix_exact_match(self, mock_get_cache):
        """Test finding session by exact prefix match."""
        test_uuid = "12345678-1234-5678-9abc-123456789abc"
        mock_cache = Mock()
        mock_cache.keys.return_value = [test_uuid, "other-key"]
        mock_get_cache.return_value = mock_cache

        result = _find_session_by_prefix("12345")
        assert result == test_uuid

    @patch("glovebox.cli.commands.metrics._get_metrics_cache_manager")
    def test_find_session_by_prefix_no_match(self, mock_get_cache):
        """Test finding session with no matching prefix."""
        mock_cache = Mock()
        mock_cache.keys.return_value = ["12345678-1234-5678-9abc-123456789abc"]
        mock_get_cache.return_value = mock_cache

        result = _find_session_by_prefix("99999")
        assert result is None

    @patch("glovebox.cli.commands.metrics._get_metrics_cache_manager")
    def test_find_session_by_prefix_ambiguous(self, mock_get_cache):
        """Test finding session with ambiguous prefix."""
        uuid1 = "12345678-1234-5678-9abc-123456789abc"
        uuid2 = "12345678-1234-5678-9def-987654321def"
        mock_cache = Mock()
        mock_cache.keys.return_value = [uuid1, uuid2]
        mock_get_cache.return_value = mock_cache

        with pytest.raises(ValueError, match="Ambiguous session ID"):
            _find_session_by_prefix("12345")

    @patch("glovebox.cli.commands.metrics._get_metrics_cache_manager")
    def test_find_session_filters_non_uuid_keys(self, mock_get_cache):
        """Test that non-UUID keys are filtered out."""
        test_uuid = "12345678-1234-5678-9abc-123456789abc"
        mock_cache = Mock()
        mock_cache.keys.return_value = [
            test_uuid,
            "metrics:old_key",  # Should be filtered out
            "short-key",  # Should be filtered out
            "not-a-uuid-key",  # Should be filtered out
        ]
        mock_get_cache.return_value = mock_cache

        result = _find_session_by_prefix("12345")
        assert result == test_uuid


class TestTabCompletion:
    """Test tab completion functionality."""

    @patch("glovebox.cli.commands.metrics._get_metrics_cache_manager")
    def test_complete_session_uuid_returns_matches(self, mock_get_cache):
        """Test tab completion returns matching UUIDs."""
        uuid1 = "12345678-1234-5678-9abc-123456789abc"
        uuid2 = "12345678-1234-5678-9def-987654321def"
        uuid3 = "87654321-4321-8765-cba9-fedcba987654"

        mock_cache = Mock()
        mock_cache.keys.return_value = [uuid1, uuid2, uuid3]
        mock_get_cache.return_value = mock_cache

        result = _complete_session_uuid("12345")
        assert sorted(result) == sorted([uuid1, uuid2])

    @patch("glovebox.cli.commands.metrics._get_metrics_cache_manager")
    def test_complete_session_uuid_no_matches(self, mock_get_cache):
        """Test tab completion with no matches."""
        mock_cache = Mock()
        mock_cache.keys.return_value = ["12345678-1234-5678-9abc-123456789abc"]
        mock_get_cache.return_value = mock_cache

        result = _complete_session_uuid("99999")
        assert result == []

    @patch("glovebox.cli.commands.metrics._get_metrics_cache_manager")
    def test_complete_session_uuid_handles_errors(self, mock_get_cache):
        """Test tab completion handles errors gracefully."""
        mock_cache = Mock()
        mock_cache.keys.side_effect = Exception("Cache error")
        mock_get_cache.return_value = mock_cache

        result = _complete_session_uuid("12345")
        assert result == []


class TestMetricsListCommand:
    """Test metrics list command."""

    @patch("glovebox.cli.commands.metrics._get_metrics_cache_manager")
    def test_list_no_sessions(self, mock_get_cache):
        """Test list command with no sessions."""
        mock_cache = Mock()
        mock_cache.keys.return_value = []
        mock_get_cache.return_value = mock_cache

        runner = CliRunner()
        result = runner.invoke(metrics_app, ["list"])

        assert result.exit_code == 0
        assert "No metrics sessions found" in result.output

    @patch("glovebox.cli.commands.metrics._get_metrics_cache_manager")
    def test_list_with_sessions(self, mock_get_cache, sample_session_data):
        """Test list command with sessions."""
        session_uuids = list(sample_session_data.keys())
        mock_cache = Mock()
        mock_cache.keys.return_value = session_uuids
        mock_cache.get.side_effect = lambda key: sample_session_data.get(key)
        mock_cache.get_metadata.return_value = None
        mock_get_cache.return_value = mock_cache

        runner = CliRunner()
        result = runner.invoke(metrics_app, ["list"])

        assert result.exit_code == 0
        assert "Recent Metrics Sessions" in result.output
        assert "UUID" in result.output
        assert "Started" in result.output
        assert "Duration" in result.output
        assert "Status" in result.output

    @patch("glovebox.cli.commands.metrics._get_metrics_cache_manager")
    def test_list_json_output(self, mock_get_cache, sample_session_data):
        """Test list command with JSON output."""
        session_uuids = list(sample_session_data.keys())
        mock_cache = Mock()
        mock_cache.keys.return_value = session_uuids
        mock_cache.get.side_effect = lambda key: sample_session_data.get(key)
        mock_cache.get_metadata.return_value = None
        mock_get_cache.return_value = mock_cache

        runner = CliRunner()
        result = runner.invoke(metrics_app, ["list", "--json"])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert "sessions" in output_data
        assert "total" in output_data
        assert len(output_data["sessions"]) == 2

    @patch("glovebox.cli.commands.metrics._get_metrics_cache_manager")
    def test_list_with_limit(self, mock_get_cache, sample_session_data):
        """Test list command with limit parameter."""
        session_uuids = list(sample_session_data.keys())
        mock_cache = Mock()
        mock_cache.keys.return_value = session_uuids
        mock_cache.get.side_effect = lambda key: sample_session_data.get(key)
        mock_cache.get_metadata.return_value = None
        mock_get_cache.return_value = mock_cache

        runner = CliRunner()
        result = runner.invoke(metrics_app, ["list", "--limit", "1"])

        assert result.exit_code == 0
        assert "Showing 1 of 2 total sessions" in result.output


class TestMetricsShowCommand:
    """Test metrics show command."""

    @patch("glovebox.cli.commands.metrics._get_metrics_cache_manager")
    def test_show_full_uuid(self, mock_get_cache, sample_session_data):
        """Test show command with full UUID."""
        session_uuid = list(sample_session_data.keys())[0]
        mock_cache = Mock()
        mock_cache.get.return_value = sample_session_data[session_uuid]
        mock_get_cache.return_value = mock_cache

        runner = CliRunner()
        result = runner.invoke(metrics_app, ["show", session_uuid])

        assert result.exit_code == 0
        assert "Session: session_1234" in result.output
        assert "Started:" in result.output
        assert "Duration:" in result.output
        assert "Status:" in result.output

    @patch("glovebox.cli.commands.metrics._get_metrics_cache_manager")
    def test_show_with_prefix(self, mock_get_cache, sample_session_data):
        """Test show command with UUID prefix."""
        session_uuid = list(sample_session_data.keys())[0]
        prefix = session_uuid[:8]

        mock_cache = Mock()
        mock_cache.keys.return_value = [session_uuid]
        mock_cache.get.return_value = sample_session_data[session_uuid]
        mock_get_cache.return_value = mock_cache

        runner = CliRunner()
        result = runner.invoke(metrics_app, ["show", prefix])

        assert result.exit_code == 0
        assert "Session: session_1234" in result.output

    @patch("glovebox.cli.commands.metrics._get_metrics_cache_manager")
    def test_show_not_found(self, mock_get_cache):
        """Test show command with non-existent session."""
        mock_cache = Mock()
        mock_cache.keys.return_value = []
        mock_get_cache.return_value = mock_cache

        runner = CliRunner()
        result = runner.invoke(metrics_app, ["show", "nonexistent"])

        assert result.exit_code == 1
        assert "No session found matching prefix" in result.output

    @patch("glovebox.cli.commands.metrics._get_metrics_cache_manager")
    def test_show_json_output(self, mock_get_cache, sample_session_data):
        """Test show command with JSON output."""
        session_uuid = list(sample_session_data.keys())[0]
        mock_cache = Mock()
        mock_cache.get.return_value = sample_session_data[session_uuid]
        mock_get_cache.return_value = mock_cache

        runner = CliRunner()
        result = runner.invoke(metrics_app, ["show", session_uuid, "--json"])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert "session_info" in output_data
        assert "counters" in output_data

    @patch("glovebox.cli.commands.metrics._get_metrics_cache_manager")
    def test_show_with_activity(self, mock_get_cache, sample_session_data):
        """Test show command with activity log."""
        session_uuid = list(sample_session_data.keys())[0]
        mock_cache = Mock()
        mock_cache.get.return_value = sample_session_data[session_uuid]
        mock_get_cache.return_value = mock_cache

        runner = CliRunner()
        result = runner.invoke(metrics_app, ["show", session_uuid, "--activity"])

        assert result.exit_code == 0
        assert "Recent Activity" in result.output


class TestMetricsDumpCommand:
    """Test metrics dump command."""

    @patch("glovebox.cli.commands.metrics._get_metrics_cache_manager")
    def test_dump_session(self, mock_get_cache, sample_session_data, tmp_path):
        """Test dump command."""
        session_uuid = list(sample_session_data.keys())[0]
        mock_cache = Mock()
        mock_cache.get.return_value = sample_session_data[session_uuid]
        mock_get_cache.return_value = mock_cache

        output_file = tmp_path / "test_dump.json"

        runner = CliRunner()
        result = runner.invoke(
            metrics_app, ["dump", session_uuid, "--output", str(output_file)]
        )

        assert result.exit_code == 0
        assert "Session metrics dumped to:" in result.output
        assert output_file.exists()

        # Verify file content
        with output_file.open() as f:
            data = json.load(f)
        assert data == sample_session_data[session_uuid]

    @patch("glovebox.cli.commands.metrics._get_metrics_cache_manager")
    def test_dump_auto_filename(
        self, mock_get_cache, sample_session_data, isolated_cli_environment
    ):
        """Test dump command with auto-generated filename."""
        session_uuid = list(sample_session_data.keys())[0]
        mock_cache = Mock()
        mock_cache.get.return_value = sample_session_data[session_uuid]
        mock_get_cache.return_value = mock_cache

        runner = CliRunner()
        # Use isolated environment to prevent file pollution
        import os

        env = os.environ.copy()
        result = runner.invoke(metrics_app, ["dump", session_uuid], env=env)

        assert result.exit_code == 0
        assert "Session metrics dumped to:" in result.output
        assert "metrics_session_1234_" in result.output


class TestMetricsCleanCommand:
    """Test metrics clean command."""

    @patch("glovebox.cli.commands.metrics._get_metrics_cache_manager")
    def test_clean_no_sessions(self, mock_get_cache):
        """Test clean command with no sessions."""
        mock_cache = Mock()
        mock_cache.keys.return_value = []
        mock_get_cache.return_value = mock_cache

        runner = CliRunner()
        result = runner.invoke(metrics_app, ["clean"])

        assert result.exit_code == 0
        assert "No metrics sessions found to clean" in result.output

    @patch("glovebox.cli.commands.metrics._get_metrics_cache_manager")
    def test_clean_no_old_sessions(self, mock_get_cache):
        """Test clean command with no old sessions."""
        # Create session data with recent timestamps (should not be cleaned)

        recent_session_uuid = str(uuid.uuid4())
        recent_date = datetime.now(UTC).isoformat()
        recent_session_data = {
            recent_session_uuid: {
                "session_info": {
                    "session_id": "recent_session",
                    "start_time": recent_date,
                    "end_time": recent_date,
                    "duration_seconds": 60.0,
                    "exit_code": 0,
                    "success": True,
                    "cli_args": ["glovebox", "test"],
                }
            }
        }

        mock_cache = Mock()
        mock_cache.keys.return_value = [recent_session_uuid]
        mock_cache.get.side_effect = lambda key: recent_session_data.get(key)
        mock_get_cache.return_value = mock_cache

        runner = CliRunner()
        # Use a larger older-than value so recent sessions won't be considered old
        result = runner.invoke(metrics_app, ["clean", "--older-than", "7"])

        assert result.exit_code == 0
        assert "No sessions older than 7 days found" in result.output

    @patch("glovebox.cli.commands.metrics._get_metrics_cache_manager")
    def test_clean_dry_run(self, mock_get_cache):
        """Test clean command with dry run."""

        # Create old session data (older than the threshold)
        old_session_uuid = str(uuid.uuid4())
        # Use timezone-aware datetime to match the clean function logic
        old_date = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        old_session_data = {
            "session_info": {
                "session_id": "old_session",
                "start_time": old_date,
                "end_time": old_date,
                "duration_seconds": 60.0,
                "exit_code": 0,
                "success": True,
                "cli_args": ["glovebox", "test"],
            }
        }

        mock_cache = Mock()
        mock_cache.keys.return_value = [old_session_uuid]
        mock_cache.get.return_value = old_session_data
        mock_get_cache.return_value = mock_cache

        runner = CliRunner()
        result = runner.invoke(
            metrics_app, ["clean", "--older-than", "5", "--dry-run"]
        )  # Use 5 days so 10-day old session is found

        assert result.exit_code == 0
        assert "Dry run complete" in result.output
        assert "would remove 1 sessions" in result.output
        mock_cache.delete.assert_not_called()


class TestErrorHandling:
    """Test error handling in metrics commands."""

    @patch("glovebox.cli.commands.metrics._get_metrics_cache_manager")
    def test_list_cache_error(self, mock_get_cache):
        """Test list command handles cache errors."""
        mock_cache = Mock()
        mock_cache.keys.side_effect = Exception("Cache error")
        mock_get_cache.return_value = mock_cache

        runner = CliRunner()
        result = runner.invoke(metrics_app, ["list"])

        assert result.exit_code == 1
        assert "Failed to list" in result.output

    @patch("glovebox.cli.commands.metrics._get_metrics_cache_manager")
    def test_show_ambiguous_prefix(self, mock_get_cache):
        """Test show command with ambiguous prefix."""
        uuid1 = "12345678-1234-5678-9abc-123456789abc"
        uuid2 = "12345678-1234-5678-9def-987654321def"
        mock_cache = Mock()
        mock_cache.keys.return_value = [uuid1, uuid2]
        mock_get_cache.return_value = mock_cache

        runner = CliRunner()
        result = runner.invoke(metrics_app, ["show", "12345"])

        assert result.exit_code == 1
        assert "Ambiguous session ID" in result.output

    @patch("glovebox.cli.commands.metrics._get_metrics_cache_manager")
    def test_dump_session_not_found(self, mock_get_cache):
        """Test dump command with non-existent session."""
        mock_cache = Mock()
        mock_cache.keys.return_value = []
        mock_get_cache.return_value = mock_cache

        runner = CliRunner()
        result = runner.invoke(metrics_app, ["dump", "nonexistent"])

        assert result.exit_code == 1
        assert "No session found" in result.output
