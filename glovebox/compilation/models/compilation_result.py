"""Compilation result models for build outcomes."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from glovebox.firmware.models import BuildResult, FirmwareOutputFiles


class CompilationResult(BaseModel):
    """Enhanced compilation result with strategy-specific information.

    Extends BuildResult with compilation-specific metadata and
    strategy information for detailed build tracking.
    """

    build_result: BuildResult
    strategy_used: str
    workspace_path: Path | None = None
    build_targets: list[str] = Field(default_factory=list)
    cache_used: bool = False
    build_time_seconds: float = 0.0

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def success(self) -> bool:
        """Check if compilation was successful."""
        return self.build_result.success

    @property
    def output_files(self) -> FirmwareOutputFiles | None:
        """Get output files from build result."""
        return self.build_result.output_files

    @property
    def messages(self) -> list[str]:
        """Get messages from build result."""
        return self.build_result.messages

    @property
    def errors(self) -> list[str]:
        """Get errors from build result."""
        return self.build_result.errors


class StrategyResult(BaseModel):
    """Result from a specific compilation strategy.

    Contains strategy-specific information and performance metrics.
    """

    strategy_name: str
    success: bool
    execution_time_seconds: float = 0.0
    memory_usage_mb: float = 0.0
    artifacts_generated: int = 0
    error_message: str | None = None
    warnings: list[str] = Field(default_factory=list)


class BuildMatrixResult(BaseModel):
    """Result from build matrix execution.

    Tracks results across multiple build targets in a matrix build.
    """

    total_targets: int
    successful_targets: int
    failed_targets: int
    target_results: dict[str, StrategyResult] = Field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_targets == 0:
            return 0.0
        return (self.successful_targets / self.total_targets) * 100.0

    @property
    def overall_success(self) -> bool:
        """Check if all targets built successfully."""
        return self.failed_targets == 0 and self.total_targets > 0
