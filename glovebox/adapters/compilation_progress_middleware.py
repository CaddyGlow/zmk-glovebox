"""Compilation progress middleware for Docker output parsing."""

import logging
import re
from typing import Optional

from glovebox.core.file_operations import (
    CompilationProgress,
    CompilationProgressCallback,
)
from glovebox.utils.stream_process import OutputMiddleware


logger = logging.getLogger(__name__)


class CompilationProgressMiddleware(OutputMiddleware[str]):
    """Middleware for tracking firmware compilation progress through Docker output.

    This middleware parses Docker output during firmware compilation to track:
    - Repository downloads during 'west update' (e.g., "From https://github.com/...")
    - Build progress during compilation
    - Artifact collection
    """

    def __init__(
        self,
        progress_callback: CompilationProgressCallback,
        total_repositories: int = 39,  # Default based on user's example
        initial_phase: str = "west_update",
        skip_west_update: bool = False,  # Set to True if compilation starts directly with building
        total_boards: int = 1,  # Total boards to build (e.g., 2 for split keyboards)
        board_names: list[str] | None = None,  # Board names for identification
    ) -> None:
        """Initialize the compilation progress middleware.

        Args:
            progress_callback: Callback function to call with progress updates
            total_repositories: Total number of repositories expected to be downloaded
            initial_phase: Initial compilation phase
            skip_west_update: Whether to skip west update phase and start with building
            total_boards: Total number of boards to build
            board_names: List of board names (e.g., ["glove80_lh", "glove80_rh"])
        """
        self.progress_callback = progress_callback
        self.total_repositories = total_repositories
        self.repositories_downloaded = 0
        self.current_phase = "building" if skip_west_update else initial_phase
        self.current_repository = ""

        # Multi-board support
        self.total_boards = total_boards
        self.board_names = board_names or []
        self.boards_completed = 0
        self.current_board = ""
        self.current_board_step = 0
        self.total_board_steps = 0

        # Log capture for Rich display
        self.captured_logs: list[tuple[str, str]] = []  # (level, message) pairs
        self.max_log_lines = 100  # Keep last 100 log lines

        # Patterns for parsing different types of output
        self.repo_download_pattern = re.compile(
            r"^From https://github\.com/([^/]+/[^/\s]+)"
        )
        self.build_start_pattern = re.compile(r"west build.*-b\s+(\w+)")
        self.build_progress_pattern = re.compile(r"\[\s*(\d+)/(\d+)\s*\].*Building")
        self.build_complete_pattern = re.compile(
            r"Memory region\s+Used Size|FLASH.*region.*overlaps"
        )
        # Board-specific patterns
        self.board_detection_pattern = re.compile(r"west build.*-b\s+([a-zA-Z0-9_]+)")
        self.board_complete_pattern = re.compile(r"TOTAL_FLASH|\.uf2.*generated")

    def process(self, line: str, stream_type: str) -> str:
        """Process Docker output line and update compilation progress.

        Args:
            line: Output line from Docker
            stream_type: Either "stdout" or "stderr"

        Returns:
            The original line (unmodified)
        """
        line_stripped = line.strip()

        # Log all Docker output for debugging and capture for Rich display
        if stream_type == "stdout":
            logger.debug("Docker stdout: %s", line_stripped)
            if line_stripped:  # Don't capture empty lines
                self._capture_log("info", line_stripped)
        else:
            # Log stderr at warning level since it might contain important errors
            if line_stripped:  # Don't log empty stderr lines
                logger.warning("Docker stderr: %s", line_stripped)
                self._capture_log("warning", line_stripped)

        if not line_stripped:
            return line

        try:
            # Check for build start patterns regardless of current phase
            # This handles cases where compilation starts directly with building
            build_match = self.build_start_pattern.search(line_stripped)
            build_progress_match = self.build_progress_pattern.search(line_stripped)

            if (
                build_match or build_progress_match
            ) and self.current_phase == "west_update":
                # Transition to building phase if we detect build activity
                logger.info(
                    "Detected build activity, transitioning from west_update to building phase"
                )
                self.current_phase = "building"
                self._update_phase_progress("building", "Starting compilation")

            # Parse repository downloads during west update
            if self.current_phase == "west_update":
                repo_match = self.repo_download_pattern.match(line_stripped)
                if repo_match:
                    repository_name = repo_match.group(1)
                    self.repositories_downloaded += 1
                    self.current_repository = repository_name

                    # Create progress update
                    progress = CompilationProgress(
                        repositories_downloaded=self.repositories_downloaded,
                        total_repositories=self.total_repositories,
                        current_repository=repository_name,
                        compilation_phase=self.current_phase,
                        current_board=self.current_board,
                        boards_completed=self.boards_completed,
                        total_boards=self.total_boards,
                        current_board_step=self.current_board_step,
                        total_board_steps=self.total_board_steps,
                    )

                    # Log repository download progress
                    logger.info(
                        "Downloaded repository %d/%d: %s",
                        self.repositories_downloaded,
                        self.total_repositories,
                        repository_name,
                    )

                    # Call progress callback
                    self.progress_callback(progress)

                    # Check if west update is complete
                    if self.repositories_downloaded >= self.total_repositories:
                        logger.info(
                            "West update completed: %d repositories downloaded. Starting build phase.",
                            self.total_repositories,
                        )
                        self.current_phase = "building"
                        self._update_phase_progress("building", "Starting compilation")

            # Parse build progress
            elif self.current_phase == "building":
                # Detect board start
                board_match = self.board_detection_pattern.search(line_stripped)
                if board_match:
                    board_name = board_match.group(1)
                    if board_name != self.current_board:
                        # Starting new board
                        if self.current_board:
                            # Previous board completed
                            self.boards_completed += 1
                            logger.info(
                                "Completed build for board: %s (%d/%d)",
                                self.current_board,
                                self.boards_completed,
                                self.total_boards,
                            )

                        self.current_board = board_name
                        self.current_board_step = 0
                        self.total_board_steps = 0
                        logger.info(
                            "Starting build for board: %s (%d/%d)",
                            board_name,
                            self.boards_completed + 1,
                            self.total_boards,
                        )
                        self._update_board_progress()

                # Check for build progress indicators [xx/xx] Building...
                build_progress_match = self.build_progress_pattern.search(line_stripped)
                if build_progress_match:
                    current_step = int(build_progress_match.group(1))
                    total_steps = int(build_progress_match.group(2))

                    # Update current board progress
                    self.current_board_step = current_step
                    if total_steps > self.total_board_steps:
                        self.total_board_steps = total_steps

                    logger.info(
                        "Build progress for %s: %d/%d steps",
                        self.current_board or "board",
                        current_step,
                        total_steps,
                    )
                    self._update_board_progress()

                # Check for individual board completion
                if (
                    self.board_complete_pattern.search(line_stripped)
                    and self.current_board
                ):
                    logger.info("Board %s build completed", self.current_board)
                    self.boards_completed += 1
                    self.current_board = ""
                    self._update_board_progress()

                # Check for overall build completion indicators
                if self.build_complete_pattern.search(line_stripped):
                    # Ensure all boards are marked complete
                    if self.boards_completed < self.total_boards:
                        self.boards_completed = self.total_boards

                    logger.info(
                        "All builds completed successfully (%d/%d). Starting artifact collection.",
                        self.boards_completed,
                        self.total_boards,
                    )
                    self.current_phase = "collecting"
                    self._update_phase_progress("collecting", "Collecting artifacts")

        except Exception as e:
            # Don't let progress tracking break the compilation
            logger.warning("Error processing compilation progress: %s", e)

        return line

    def _update_phase_progress(self, phase: str, current_item: str) -> None:
        """Update progress for phase transitions.

        Args:
            phase: New compilation phase
            current_item: Description of current operation
        """
        progress = CompilationProgress(
            repositories_downloaded=self.repositories_downloaded,
            total_repositories=self.total_repositories,
            current_repository=current_item,
            compilation_phase=phase,
            current_board=self.current_board,
            boards_completed=self.boards_completed,
            total_boards=self.total_boards,
            current_board_step=self.current_board_step,
            total_board_steps=self.total_board_steps,
        )

        logger.info("Phase transition: %s - %s", phase, current_item)
        self.progress_callback(progress)

    def _update_board_progress(self) -> None:
        """Update progress for board-specific changes."""
        # Format current repository/item description
        if self.current_board:
            if self.total_board_steps > 0:
                current_item = f"{self.current_board} ({self.current_board_step}/{self.total_board_steps})"
            else:
                current_item = f"{self.current_board} (starting)"
        else:
            current_item = (
                f"Completed {self.boards_completed}/{self.total_boards} boards"
            )

        progress = CompilationProgress(
            repositories_downloaded=self.repositories_downloaded,
            total_repositories=self.total_repositories,
            current_repository=current_item,
            compilation_phase=self.current_phase,
            current_board=self.current_board,
            boards_completed=self.boards_completed,
            total_boards=self.total_boards,
            current_board_step=self.current_board_step,
            total_board_steps=self.total_board_steps,
        )

        self.progress_callback(progress)

    def _capture_log(self, level: str, message: str) -> None:
        """Capture log line for Rich display.

        Args:
            level: Log level (info, warning, error)
            message: Log message
        """
        self.captured_logs.append((level, message))

        # Keep only the last max_log_lines entries
        if len(self.captured_logs) > self.max_log_lines:
            self.captured_logs = self.captured_logs[-self.max_log_lines :]

    def get_current_progress(self) -> CompilationProgress:
        """Get the current progress state.

        Returns:
            Current CompilationProgress object
        """
        return CompilationProgress(
            repositories_downloaded=self.repositories_downloaded,
            total_repositories=self.total_repositories,
            current_repository=self.current_repository,
            compilation_phase=self.current_phase,
            current_board=self.current_board,
            boards_completed=self.boards_completed,
            total_boards=self.total_boards,
            current_board_step=self.current_board_step,
            total_board_steps=self.total_board_steps,
        )


def create_compilation_progress_middleware(
    progress_callback: CompilationProgressCallback,
    total_repositories: int = 39,
    skip_west_update: bool = False,
    total_boards: int = 1,
    board_names: list[str] | None = None,
) -> CompilationProgressMiddleware:
    """Factory function to create compilation progress middleware.

    Args:
        progress_callback: Callback function for progress updates
        total_repositories: Total number of repositories expected
        skip_west_update: Whether to skip west update phase and start with building
        total_boards: Total number of boards to build
        board_names: List of board names for identification

    Returns:
        Configured CompilationProgressMiddleware instance
    """
    return CompilationProgressMiddleware(
        progress_callback=progress_callback,
        total_repositories=total_repositories,
        skip_west_update=skip_west_update,
        total_boards=total_boards,
        board_names=board_names,
    )
