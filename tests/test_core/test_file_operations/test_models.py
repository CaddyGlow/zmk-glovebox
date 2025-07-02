"""Tests for file operations models."""

import pytest


pytestmark = pytest.mark.unit

from glovebox.core.file_operations.models import CopyResult


class TestCopyResult:
    """Test CopyResult model functionality."""

    def test_successful_result(self):
        """Test successful copy result calculation."""
        result = CopyResult(
            success=True,
            bytes_copied=1024 * 1024 * 100,  # 100MB
            elapsed_time=10.0,  # 10 seconds
            strategy_used="buffered",
        )

        assert result.success is True
        assert result.bytes_copied == 100 * 1024 * 1024
        assert result.elapsed_time == 10.0
        assert result.strategy_used == "buffered"
        assert result.error is None

        # Test speed calculations
        assert abs(result.speed_mbps - 10.0) < 0.1  # ~10 MB/s
        assert abs(result.speed_gbps - (10.0 / 1024)) < 0.001  # ~0.0098 GB/s

    def test_failed_result(self):
        """Test failed copy result."""
        result = CopyResult(
            success=False,
            bytes_copied=0,
            elapsed_time=5.0,
            error="Permission denied",
            strategy_used="baseline",
        )

        assert result.success is False
        assert result.bytes_copied == 0
        assert result.error == "Permission denied"
        assert result.speed_mbps == 0.0
        assert result.speed_gbps == 0.0

    def test_zero_time_result(self):
        """Test result with zero elapsed time."""
        result = CopyResult(success=True, bytes_copied=1000, elapsed_time=0.0)

        assert result.speed_mbps == 0.0
        assert result.speed_gbps == 0.0

    def test_partial_failure(self):
        """Test partial copy with some bytes copied but error."""
        result = CopyResult(
            success=False,
            bytes_copied=50 * 1024 * 1024,  # 50MB copied before failure
            elapsed_time=5.0,
            error="Disk full",
        )

        assert result.success is False
        assert result.bytes_copied == 50 * 1024 * 1024
        assert result.error == "Disk full"
        # Speed should still be 0 for failed operations
        assert result.speed_mbps == 0.0
