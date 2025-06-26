"""Simplified file operations module with embedded strategies."""

from .models import (
    CompilationProgress,
    CompilationProgressCallback,
    CopyProgress,
    CopyProgressCallback,
    CopyResult,
)
from .protocols import CopyStrategyProtocol
from .service import (
    BASELINE,
    PIPELINE,
    BaselineStrategy,
    FileCopyService,
    PipelineStrategy,
    create_copy_service,
)


__all__ = [
    "BASELINE",
    "PIPELINE",
    "BaselineStrategy",
    "CompilationProgress",
    "CompilationProgressCallback",
    "CopyProgress",
    "CopyProgressCallback",
    "CopyResult",
    "CopyStrategyProtocol",
    "FileCopyService",
    "PipelineStrategy",
    "create_copy_service",
]
