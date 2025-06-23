"""Models for file operation results and configuration."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class CopyResult:
    """Result of a copy operation with performance metrics."""

    success: bool
    bytes_copied: int
    elapsed_time: float
    error: str | None = None
    strategy_used: str | None = None

    @property
    def speed_mbps(self) -> float:
        """Calculate copy speed in MB/s."""
        if self.elapsed_time > 0 and self.success:
            return (self.bytes_copied / (1024 * 1024)) / self.elapsed_time
        return 0.0

    @property
    def speed_gbps(self) -> float:
        """Calculate copy speed in GB/s."""
        return self.speed_mbps / 1024
