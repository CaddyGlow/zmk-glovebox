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
        if self.compilation_phase == "initialization":
            # Initialization is 10% of total progress
            return 5.0  # Show some progress during initialization
        elif self.compilation_phase == "west_update":
            # West update is 30% of total progress (10% to 40%)
            return 10.0 + (self.repository_progress_percent * 0.3)
        elif self.compilation_phase == "building":
            # Building is 50% of total progress (40% to 90%)
            base_progress = 40.0  # Initialization + west update completed
            board_weight = 50.0 / self.total_boards if self.total_boards > 0 else 50.0
            completed_boards_progress = self.boards_completed * board_weight
            current_board_progress = self.current_board_progress_percent * (
                board_weight / 100.0
            )
            return base_progress + completed_boards_progress + current_board_progress
        elif self.compilation_phase == "cache_saving":
            # Cache saving is 10% of total progress (90% to 100%)
            return 90.0 + min(10.0, 10.0)  # Show progress from 90% to 100%
        return 0.0

    def get_staged_progress_display(self) -> str:
        """Get a staged progress display with emojis and status indicators."""
        stages = [
            ("🔧 Setting up build environment", "initialization"),
            ("📦 Resolving dependencies", "west_update"),
            ("⚙️ Compiling firmware", "building"),
            ("🔗 Linking binaries", "building"),
            ("📱 Generating .uf2 files", "cache_saving"),
        ]

        lines = []
        for stage_name, stage_phase in stages:
            if self.compilation_phase == stage_phase:
                if stage_phase == "initialization":
                    status = "⚙️"  # Show as in progress during initialization
                elif stage_phase == "west_update":
                    progress = int(self.repository_progress_percent)
                    if progress == 100:
                        status = "✓"
                    else:
                        status = f"{'█' * (progress // 10)}{'░' * (10 - progress // 10)} {progress}%"
                elif stage_phase == "building":
                    if self.boards_completed == self.total_boards:
                        status = "✓"
                    else:
                        progress = int(self.current_board_progress_percent)
                        status = f"{'█' * (progress // 10)}{'░' * (10 - progress // 10)} {progress}%"
                elif stage_phase == "cache_saving":
                    status = "✓"
                else:
                    status = "(pending)"
            elif self._is_stage_completed(stage_phase):
                status = "✓"
            else:
                status = "(pending)"

            lines.append(f"{stage_name}... {status}")

        return "\n".join(lines)

    def _is_stage_completed(self, stage_phase: str) -> bool:
        """Check if a stage has been completed."""
        phase_order = ["initialization", "west_update", "building", "cache_saving"]
        if stage_phase not in phase_order:
            return False

        # Handle case where current phase is not in the list
        if self.compilation_phase not in phase_order:
            return False

        current_index = phase_order.index(self.compilation_phase)
        stage_index = phase_order.index(stage_phase)

        return stage_index < current_index

    def get_status_text(self) -> str:
        """Get status text for progress display compatibility."""
        if self.compilation_phase == "initialization":
            return "🔧 Initializing build environment"
        elif self.compilation_phase == "west_update":
            return f"📦 Downloading repositories ({self.repositories_downloaded}/{self.total_repositories})"
        elif self.compilation_phase == "building":
            if self.current_board:
                return f"⚙️ Building {self.current_board} ({self.boards_completed + 1}/{self.total_boards})"
            else:
                return f"⚙️ Compiling firmware ({self.boards_completed}/{self.total_boards})"
        elif self.compilation_phase == "cache_saving":
            return "💾 Saving build cache"
        else:
            return f"🔧 {self.compilation_phase.replace('_', ' ').title()}"

    def get_progress_info(self) -> tuple[int, int, str]:
        """Get progress info for progress display compatibility."""
        current = int(self.overall_progress_percent)
        total = 100
        description = self.get_status_text()
        return current, total, description


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
