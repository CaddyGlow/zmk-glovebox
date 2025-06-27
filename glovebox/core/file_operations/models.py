"""Models for file operation results and configuration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional


@dataclass
class CopyProgress:
    """Progress information for copy operations."""

    files_processed: int
    total_files: int
    bytes_copied: int
    total_bytes: int
    current_file: str
    component_name: str = ""  # For component-level operations

    @property
    def file_progress_percent(self) -> float:
        """Calculate file progress percentage."""
        if self.total_files > 0:
            return (self.files_processed / self.total_files) * 100
        return 0.0

    @property
    def bytes_progress_percent(self) -> float:
        """Calculate bytes progress percentage."""
        if self.total_bytes > 0:
            return (self.bytes_copied / self.total_bytes) * 100
        return 0.0

    @property
    def speed_mbps(self) -> float:
        """Calculate copy speed in MB/s."""
        # Speed calculation would be handled externally with timing
        return 0.0


# Type alias for progress callback
CopyProgressCallback = Callable[[CopyProgress], None]


@dataclass
class CompilationProgress:
    """Progress information for firmware compilation operations."""

    repositories_downloaded: int
    total_repositories: int
    current_repository: str
    compilation_phase: str = "west_update"  # west_update, building, collecting
    bytes_downloaded: int = 0
    total_bytes: int = 0
    # Multi-board support
    current_board: str = ""  # Current board being built (e.g., "glove80_lh")
    boards_completed: int = 0  # Number of boards completed
    total_boards: int = 1  # Total boards to build (default 1 for non-split)
    current_board_step: int = 0  # Current build step within board
    total_board_steps: int = 0  # Total build steps for current board

    @property
    def repository_progress_percent(self) -> float:
        """Calculate repository download progress percentage."""
        if self.total_repositories > 0:
            return (self.repositories_downloaded / self.total_repositories) * 100
        return 0.0

    @property
    def bytes_progress_percent(self) -> float:
        """Calculate bytes download progress percentage."""
        if self.total_bytes > 0:
            return (self.bytes_downloaded / self.total_bytes) * 100
        return 0.0

    @property
    def repositories_remaining(self) -> int:
        """Calculate number of repositories remaining."""
        return max(0, self.total_repositories - self.repositories_downloaded)

    @property
    def board_progress_percent(self) -> float:
        """Calculate board completion progress percentage."""
        if self.total_boards > 0:
            return (self.boards_completed / self.total_boards) * 100
        return 0.0

    @property
    def current_board_progress_percent(self) -> float:
        """Calculate current board build step progress percentage."""
        if self.total_board_steps > 0:
            return (self.current_board_step / self.total_board_steps) * 100
        return 0.0

    @property
    def boards_remaining(self) -> int:
        """Calculate number of boards remaining to build."""
        return max(0, self.total_boards - self.boards_completed)

    @property
    def overall_progress_percent(self) -> float:
        """Calculate overall progress across all phases and boards."""
        if self.compilation_phase == "west_update":
            # West update is 30% of total progress
            return self.repository_progress_percent * 0.3
        elif self.compilation_phase == "building":
            # Building is 60% of total progress
            base_progress = 30.0  # West update completed
            board_weight = 60.0 / self.total_boards if self.total_boards > 0 else 60.0
            completed_boards_progress = self.boards_completed * board_weight
            current_board_progress = self.current_board_progress_percent * (
                board_weight / 100.0
            )
            return base_progress + completed_boards_progress + current_board_progress
        elif self.compilation_phase == "cache_saving":
            # Cache saving is 10% of total progress (90% to 100%)
            return 90.0 + min(10.0, 10.0)  # Show progress from 90% to 100%
        return 0.0


# Type alias for compilation progress callback
CompilationProgressCallback = Callable[[CompilationProgress], None]


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
