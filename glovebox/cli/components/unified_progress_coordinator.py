"""Unified progress coordinator for all compilation phases."""

import logging
from collections.abc import Callable
from typing import Any

from glovebox.core.file_operations import (
    CompilationProgress,
    CompilationProgressCallback,
)


logger = logging.getLogger(__name__)


class UnifiedCompilationProgressCoordinator:
    """Coordinates progress updates from multiple compilation phases into a single TUI display.

    This coordinator aggregates progress from:
    - Cache restoration operations
    - Workspace setup operations
    - Repository downloads (west update)
    - Board compilation (building)
    - Artifact collection

    All progress is unified and sent to a single TUI display manager.
    """

    def __init__(
        self,
        tui_callback: CompilationProgressCallback,
        total_boards: int = 1,
        board_names: list[str] | None = None,
        total_repositories: int = 39,
    ) -> None:
        """Initialize the unified progress coordinator.

        Args:
            tui_callback: Callback function for TUI progress updates
            total_boards: Total number of boards to compile
            board_names: List of board names for identification
            total_repositories: Total repositories expected during west update
        """
        self.tui_callback = tui_callback
        self.total_boards = total_boards
        self.board_names = board_names or []
        self.total_repositories = total_repositories

        # Phase tracking
        self.current_phase = "initialization"
        self.phase_progress: dict[str, dict[str, Any]] = {
            "initialization": {},
            "cache_restoration": {},
            "workspace_setup": {},
            "west_update": {},
            "building": {},
            "collecting": {},
        }

        # Overall progress state
        self.repositories_downloaded = 0
        self.current_repository = ""
        self.boards_completed = 0
        self.current_board = ""
        self.current_board_step = 0
        self.total_board_steps = 0

        # Cache/workspace progress
        self.cache_operation_progress = 0
        self.cache_operation_total = 100
        self.workspace_files_copied = 0
        self.workspace_total_files = 0
        self.workspace_bytes_copied = 0
        self.workspace_total_bytes = 0

    def transition_to_phase(self, phase: str, description: str = "") -> None:
        """Transition to a new compilation phase.

        Args:
            phase: New phase name
            description: Optional description of the phase
        """
        logger.info("Phase transition: %s -> %s (%s)", self.current_phase, phase, description)
        self.current_phase = phase
        self._send_progress_update(description or f"Starting {phase}")

    def update_cache_progress(
        self,
        operation: str,
        current: int = 0,
        total: int = 100,
        description: str = "",
    ) -> None:
        """Update cache restoration progress.

        Args:
            operation: Cache operation (e.g., "downloading", "extracting", "restoring")
            current: Current progress value
            total: Total progress value
            description: Description of current operation
        """
        if self.current_phase != "cache_restoration":
            self.transition_to_phase("cache_restoration", "Restoring cached workspace")

        self.cache_operation_progress = current
        self.cache_operation_total = total
        self.current_repository = f"{operation}: {description}" if description else operation

        logger.info("Cache progress: %s (%d/%d)", operation, current, total)
        self._send_progress_update()

    def update_workspace_progress(
        self,
        files_copied: int = 0,
        total_files: int = 0,
        bytes_copied: int = 0,
        total_bytes: int = 0,
        current_file: str = "",
        component: str = "",
    ) -> None:
        """Update workspace setup progress.

        Args:
            files_copied: Number of files copied so far
            total_files: Total files to copy
            bytes_copied: Bytes copied so far
            total_bytes: Total bytes to copy
            current_file: Currently copying file
            component: Component being copied (e.g., "zmk", "zephyr")
        """
        if self.current_phase not in ["workspace_setup", "cache_restoration"]:
            self.transition_to_phase("workspace_setup", "Setting up workspace")

        self.workspace_files_copied = files_copied
        self.workspace_total_files = total_files
        self.workspace_bytes_copied = bytes_copied
        self.workspace_total_bytes = total_bytes

        if current_file:
            self.current_repository = f"Copying: {current_file}"
        elif component:
            self.current_repository = f"Setting up: {component}"
        else:
            self.current_repository = "Setting up workspace"

        logger.info(
            "Workspace progress: %d/%d files, %d/%d bytes (%s)",
            files_copied, total_files, bytes_copied, total_bytes, component
        )
        self._send_progress_update()

    def update_repository_progress(self, repository_name: str) -> None:
        """Update repository download progress during west update.

        Args:
            repository_name: Name of repository being downloaded
        """
        if self.current_phase != "west_update":
            self.transition_to_phase("west_update", "Downloading repositories")

        self.repositories_downloaded += 1
        self.current_repository = repository_name

        logger.info(
            "Downloaded repository %d/%d: %s",
            self.repositories_downloaded, self.total_repositories, repository_name
        )
        self._send_progress_update()

        # Check if west update is complete
        if self.repositories_downloaded >= self.total_repositories:
            logger.info(
                "West update completed: %d repositories downloaded. Starting build phase.",
                self.total_repositories,
            )
            self.transition_to_phase("building", "Starting compilation")

    def update_board_progress(
        self,
        board_name: str = "",
        current_step: int = 0,
        total_steps: int = 0,
        completed: bool = False,
    ) -> None:
        """Update board compilation progress.

        Args:
            board_name: Name of board being compiled
            current_step: Current build step
            total_steps: Total build steps
            completed: Whether this board is completed
        """
        if self.current_phase != "building":
            self.transition_to_phase("building", "Compiling boards")

        # Handle board transitions
        if board_name and board_name != self.current_board:
            if self.current_board:
                # Previous board completed
                self.boards_completed += 1
                logger.info(
                    "Completed build for board: %s (%d/%d)",
                    self.current_board, self.boards_completed, self.total_boards
                )

            self.current_board = board_name
            self.current_board_step = 0
            self.total_board_steps = 0
            logger.info(
                "Starting build for board: %s (%d/%d)",
                board_name, self.boards_completed + 1, self.total_boards
            )

        # Update step progress
        if current_step > 0:
            self.current_board_step = current_step
            if total_steps > self.total_board_steps:
                self.total_board_steps = total_steps

            logger.info(
                "Build progress for %s: %d/%d steps",
                self.current_board or "board", current_step, total_steps
            )

        # Handle completion
        if completed and self.current_board:
            logger.info("Board %s build completed", self.current_board)
            self.boards_completed += 1
            self.current_board = ""

        self._send_progress_update()

        # Check if all boards are complete
        if self.boards_completed >= self.total_boards:
            logger.info(
                "All builds completed successfully (%d/%d). Starting artifact collection.",
                self.boards_completed, self.total_boards,
            )
            self.transition_to_phase("collecting", "Collecting artifacts")

    def update_artifact_collection(self, artifact: str = "") -> None:
        """Update artifact collection progress.

        Args:
            artifact: Name of artifact being collected
        """
        if self.current_phase != "collecting":
            self.transition_to_phase("collecting", "Collecting artifacts")

        self.current_repository = f"Collecting: {artifact}" if artifact else "Collecting artifacts"
        logger.info("Artifact collection: %s", artifact)
        self._send_progress_update()

    def _send_progress_update(self, custom_description: str = "") -> None:
        """Send unified progress update to TUI callback.

        Args:
            custom_description: Custom description override
        """
        # Calculate current item description based on phase
        if custom_description:
            current_item = custom_description
        elif self.current_phase == "cache_restoration" or self.current_phase == "workspace_setup" or self.current_phase == "west_update":
            current_item = self.current_repository
        elif self.current_phase == "building":
            if self.current_board:
                if self.total_board_steps > 0:
                    current_item = f"{self.current_board} ({self.current_board_step}/{self.total_board_steps})"
                else:
                    current_item = f"{self.current_board} (starting)"
            else:
                current_item = f"Completed {self.boards_completed}/{self.total_boards} boards"
        elif self.current_phase == "collecting":
            current_item = self.current_repository
        else:
            current_item = "Initializing..."

        # Create progress object
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

        # Send to TUI callback
        self.tui_callback(progress)

    def get_current_progress(self) -> CompilationProgress:
        """Get the current unified progress state.

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


def create_unified_progress_coordinator(
    tui_callback: CompilationProgressCallback,
    total_boards: int = 1,
    board_names: list[str] | None = None,
    total_repositories: int = 39,
) -> UnifiedCompilationProgressCoordinator:
    """Factory function to create a unified progress coordinator.

    Args:
        tui_callback: Callback function for TUI progress updates
        total_boards: Total number of boards to compile
        board_names: List of board names for identification
        total_repositories: Total repositories expected during west update

    Returns:
        Configured UnifiedCompilationProgressCoordinator instance
    """
    return UnifiedCompilationProgressCoordinator(
        tui_callback=tui_callback,
        total_boards=total_boards,
        board_names=board_names,
        total_repositories=total_repositories,
    )

