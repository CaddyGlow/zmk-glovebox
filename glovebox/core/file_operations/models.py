"""Models for file operation results and configuration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional

from glovebox.cli.helpers.theme import Icons


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
    total_board_steps: int = 0

    # Cache operation progress tracking
    cache_operation_progress: int = 0
    cache_operation_total: int = 100
    cache_operation_status: str = (
        "pending"  # "pending", "in_progress", "success", "failed"
    )
    compilation_strategy: str = "zmk_west"  # "zmk_west", "moergo_nix"
    docker_image_name: str = ""  # For MoErgo: shows docker image being verified

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
        # Handle completion phases first
        if self.compilation_phase in ["done", "completed", "finished", "success"]:
            return 100.0

        # Define phase weights (percentages of total progress)
        phase_weights = {
            "initialization": (0, 5),  # 0-5%
            "cache_restoration": (5, 15),  # 5-15%
            "docker_verification": (15, 25),  # 15-25% (MoErgo only)
            "nix_build": (25, 40),  # 25-40% (MoErgo only)
            "west_update": (15, 40),  # 15-40% (ZMK only)
            "building": (40, 90),  # 40-90%
            "cache_saving": (90, 100),  # 90-100%
        }

        if self.compilation_phase not in phase_weights:
            return 0.0

        start_percent, end_percent = phase_weights[self.compilation_phase]
        phase_range = end_percent - start_percent

        if self.compilation_phase == "initialization":
            return float(start_percent)
        elif self.compilation_phase == "cache_restoration":
            if self.cache_operation_total > 0:
                phase_progress = (
                    self.cache_operation_progress / self.cache_operation_total
                )
                return start_percent + (phase_progress * phase_range)
            return float(start_percent)
        elif (
            self.compilation_phase == "docker_verification"
            or self.compilation_phase == "nix_build"
        ):
            return float(start_percent + phase_range * 0.5)  # Assume halfway through
        elif self.compilation_phase == "west_update":
            if self.total_repositories > 0:
                phase_progress = self.repositories_downloaded / self.total_repositories
                return start_percent + (phase_progress * phase_range)
            return float(start_percent)
        elif self.compilation_phase == "building":
            if self.total_boards > 0:
                phase_progress = self.boards_completed / self.total_boards
                return start_percent + (phase_progress * phase_range)
            return float(start_percent)
        elif self.compilation_phase == "cache_saving":
            return float(end_percent)
        else:
            return 0.0

    def get_staged_progress_display(self) -> str:
        """Get a staged progress display with icons and status indicators."""
        # Different stages based on compilation strategy
        if self.compilation_strategy == "moergo_nix":
            # MoErgo Nix compilation stages
            stages = [
                (
                    f"{Icons.get_icon('BUILD', 'text')} Setting up build environment",
                    "initialization",
                ),
                (
                    f"{Icons.get_icon('SAVE', 'text')} Restoring workspace cache",
                    "cache_restoration",
                ),
                (
                    f"{Icons.get_icon('DOCKER', 'text')} Verifying Docker image{f' ({self.docker_image_name})' if self.docker_image_name else ''}",
                    "docker_verification",
                ),
                (
                    f"{Icons.get_icon('BUILD', 'text')} Building Nix environment",
                    "nix_build",
                ),
                (f"{Icons.get_icon('CONFIG', 'text')} Compiling firmware", "building"),
                (
                    f"{Icons.get_icon('DEVICE', 'text')} Generating .uf2 files",
                    "cache_saving",
                ),
            ]
        else:
            # ZMK West compilation stages (default)
            stages = [
                (
                    f"{Icons.get_icon('BUILD', 'text')} Setting up build environment",
                    "initialization",
                ),
                (
                    f"{Icons.get_icon('SAVE', 'text')} Restoring workspace cache",
                    "cache_restoration",
                ),
                (
                    f"{Icons.get_icon('DOWNLOAD', 'text')} Downloading dependencies (west update)",
                    "west_update",
                ),
                (f"{Icons.get_icon('CONFIG', 'text')} Compiling firmware", "building"),
                (f"{Icons.get_icon('LINK', 'text')} Linking binaries", "building"),
                (
                    f"{Icons.get_icon('DEVICE', 'text')} Generating .uf2 files",
                    "cache_saving",
                ),
            ]

        lines = []
        for stage_name, stage_phase in stages:
            if self.compilation_phase == stage_phase:
                if stage_phase == "initialization":
                    status = Icons.get_icon(
                        "CONFIG", "text"
                    )  # Show as in progress during initialization
                elif stage_phase == "cache_restoration":
                    if (
                        hasattr(self, "cache_operation_status")
                        and self.cache_operation_status == "failed"
                    ):
                        status = Icons.get_icon("ERROR", "text")  # Show failure icon
                    elif hasattr(self, "cache_operation_progress") and hasattr(
                        self, "cache_operation_total"
                    ):
                        if self.cache_operation_total > 0:
                            progress = int(
                                (
                                    self.cache_operation_progress
                                    / self.cache_operation_total
                                )
                                * 100
                            )
                            if (
                                hasattr(self, "cache_operation_status")
                                and self.cache_operation_status == "success"
                            ):
                                status = Icons.get_icon(
                                    "SUCCESS", "text"
                                )  # Show success when completed
                            else:
                                status = f"{'█' * (progress // 10)}{'░' * (10 - progress // 10)} {progress}%"
                        else:
                            status = Icons.get_icon("CONFIG", "text")
                    else:
                        status = Icons.get_icon("CONFIG", "text")
                elif stage_phase == "docker_verification":
                    # For MoErgo docker verification phase
                    status = Icons.get_icon("CONFIG", "text")
                elif stage_phase == "nix_build":
                    # For MoErgo nix build phase
                    status = Icons.get_icon("CONFIG", "text")
                elif stage_phase == "west_update":
                    progress = int(self.repository_progress_percent)
                    if progress == 100:
                        status = Icons.get_icon("SUCCESS", "text")
                    else:
                        status = f"{'█' * (progress // 10)}{'░' * (10 - progress // 10)} {progress}%"
                elif stage_phase == "building":
                    if self.boards_completed == self.total_boards:
                        status = Icons.get_icon("SUCCESS", "text")
                    else:
                        progress = int(self.current_board_progress_percent)
                        # Show board count for multi-board builds
                        if self.total_boards > 1:
                            current_board_num = self.boards_completed + 1
                            board_info = f" ({current_board_num}/{self.total_boards})"
                        else:
                            board_info = ""
                        status = f"{'█' * (progress // 10)}{'░' * (10 - progress // 10)} {progress}%{board_info}"
                elif stage_phase == "cache_saving":
                    status = Icons.get_icon("SUCCESS", "text")
                else:
                    status = "(pending)"
            elif self._is_stage_completed(stage_phase):
                # Check for specific failure states
                if (
                    stage_phase == "cache_restoration"
                    and hasattr(self, "cache_operation_status")
                    and self.cache_operation_status == "failed"
                ):
                    status = Icons.get_icon("ERROR", "text")
                else:
                    status = Icons.get_icon("SUCCESS", "text")
            else:
                status = "(pending)"

            lines.append(f"{stage_name}... {status}")

        return "\n".join(lines)

    def _is_stage_completed(self, stage_phase: str) -> bool:
        """Check if a stage has been completed."""
        # If we're in a completion phase, all stages are completed
        if self.compilation_phase in ["done", "completed", "finished", "success"]:
            return True

        # Different phase orders based on compilation strategy
        if self.compilation_strategy == "moergo_nix":
            phase_order = [
                "initialization",
                "cache_restoration",
                "docker_verification",
                "nix_build",
                "building",
                "cache_saving",
            ]
        else:
            phase_order = [
                "initialization",
                "cache_restoration",
                "west_update",
                "building",
                "cache_saving",
            ]

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
            return f"{Icons.get_icon('BUILD', 'text')} Initializing build environment"
        elif self.compilation_phase == "cache_restoration":
            return f"{Icons.get_icon('SAVE', 'text')} Restoring workspace from cache"
        elif self.compilation_phase == "docker_verification":
            if self.docker_image_name:
                return f"{Icons.get_icon('DOCKER', 'text')} Verifying Docker image ({self.docker_image_name})"
            else:
                return f"{Icons.get_icon('DOCKER', 'text')} Verifying Docker image"
        elif self.compilation_phase == "nix_build":
            return f"{Icons.get_icon('BUILD', 'text')} Building Nix environment"
        elif self.compilation_phase == "west_update":
            return f"{Icons.get_icon('DOWNLOAD', 'text')} Downloading dependencies ({self.repositories_downloaded}/{self.total_repositories})"
        elif self.compilation_phase == "building":
            if self.current_board:
                return f"{Icons.get_icon('CONFIG', 'text')} Building {self.current_board} ({self.boards_completed + 1}/{self.total_boards})"
            else:
                return f"{Icons.get_icon('CONFIG', 'text')} Compiling firmware ({self.boards_completed}/{self.total_boards})"
        elif self.compilation_phase == "cache_saving":
            return f"{Icons.get_icon('SAVE', 'text')} Saving build cache"
        else:
            return f"{Icons.get_icon('BUILD', 'text')} {self.compilation_phase.replace('_', ' ').title()}"

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
