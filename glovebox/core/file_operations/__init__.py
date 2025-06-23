"""File operations module with strategy-based copy optimizations."""

from .benchmarks import (
    BenchmarkResult,
    FileOperationsBenchmark,
    create_benchmark_runner,
)
from .enums import CopyStrategy
from .models import CopyResult
from .protocols import CopyStrategyProtocol
from .service import FileCopyService, create_copy_service


__all__ = [
    "BenchmarkResult",
    "CopyResult",
    "CopyStrategy",
    "CopyStrategyProtocol",
    "create_benchmark_runner",
    "create_copy_service",
    "FileOperationsBenchmark",
    "FileCopyService",
]
