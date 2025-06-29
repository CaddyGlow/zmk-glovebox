# glovebox/cli/components/progress_coordinator_base.py
"""Base classes for compilation progress coordination."""

import logging
from abc import ABC, abstractmethod
from typing import Any

from glovebox.core.file_operations import (
    CompilationProgress,
    CompilationProgressCallback,
)
from glovebox.protocols.progress_coordinator_protocol import ProgressCoordinatorProtocol


logger = logging.getLogger(__name__)


class BaseCompilationProgressCoordinator(ABC, ProgressCoordinatorProtocol):
    """Base class for compilation progress coordinators with strategy-specific behavior."""

    def __init__(
        self,
        tui_callback: CompilationProgressCallback,
        total_boards: int = 1,
        board_names: list[str] | None = None,
        total_repositories: int = 39,
    ) -> None:
        """Initialize the base progress coordinator."""
        self.tui_callback = tui_callback
        self.total_boards = total_boards
        self.board_names = board_names or []
        self.total_repositories = total_repositories

        # Phase tracking - subclasses define their own phase sequences
        self.current_phase = "initialization"
        self.phase_progress: dict[str, dict[str, Any]] = self._initialize_phases()

        # Common progress state
        self.repositories_downloaded = 0
        self.current_repository = ""
        self.boards_completed = 0
        self.current_board = ""
        self.current_board_step = 0
        self.total_board_steps = 0
        self.cache_operation_progress = 0
        self.cache_operation_total = 100
        self.cache_operation_status = "pending"
        self.docker_image_name = ""
        self.workspace_files_copied = 0
        self.workspace_total_files = 0
        self.workspace_bytes_copied = 0
        self.workspace_total_bytes = 0

    @property
    @abstractmethod
    def compilation_strategy(self) -> str:
        """Get the compilation strategy name."""
        pass

    @abstractmethod
    def _initialize_phases(self) -> dict[str, dict[str, Any]]:
        """Initialize strategy-specific phases."""
        pass

    @abstractmethod
    def _get_phase_sequence(self) -> list[str]:
        """Get the sequence of phases for this strategy."""
        pass

    def transition_to_phase(self, phase: str, description: str = "") -> None:
        """Transition to a new compilation phase."""
        try:
            logger.debug(
                "Phase transition: %s -> %s (%s)",
                self.current_phase,
                phase,
                description,
            )
            self.current_phase = phase
            self._send_progress_update(description or f"Starting {phase}")
        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error("Failed to transition phase: %s", e, exc_info=exc_info)

    def set_compilation_strategy(self, strategy: str, docker_image: str = "") -> None:
        """Set compilation strategy metadata."""
        try:
            # For base class, this is mainly for docker image tracking
            self.docker_image_name = docker_image
            logger.debug("Set docker image: %s", docker_image)
        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error("Failed to set compilation strategy: %s", e, exc_info=exc_info)

    # Common progress update methods
    def update_cache_progress(
        self,
        operation: str,
        current: int = 0,
        total: int = 100,
        description: str = "",
        status: str = "in_progress",
    ) -> None:
        """Update cache restoration progress."""
        try:
            if self.current_phase != "cache_restoration":
                self.transition_to_phase(
                    "cache_restoration", "Restoring cached workspace"
                )

            self.cache_operation_progress = current
            self.cache_operation_total = total
            self.cache_operation_status = status
            self.current_repository = (
                f"{operation}: {description}" if description else operation
            )

            logger.debug(
                "Cache progress: %s (%d/%d) [%s]", operation, current, total, status
            )
            self._send_progress_update()
        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error("Failed to update cache progress: %s", e, exc_info=exc_info)

    def update_workspace_progress(
        self,
        files_copied: int = 0,
        total_files: int = 0,
        bytes_copied: int = 0,
        total_bytes: int = 0,
        current_file: str = "",
        component: str = "",
    ) -> None:
        """Update workspace setup progress."""
        try:
            if self.current_phase not in ["workspace_setup", "cache_restoration"]:
                self.transition_to_phase("workspace_setup", "Setting up workspace")

            self.workspace_files_copied = files_copied
            self.workspace_total_files = total_files
            self.workspace_bytes_copied = bytes_copied
            self.workspace_total_bytes = total_bytes

            self.current_repository = self._get_workspace_progress_description(
                current_file, component
            )

            logger.debug(
                "Workspace progress: %d/%d files, %d/%d bytes (%s)",
                files_copied,
                total_files,
                bytes_copied,
                total_bytes,
                component,
            )
            self._send_progress_update()
        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error(
                "Failed to update workspace progress: %s", e, exc_info=exc_info
            )

    def update_board_progress(
        self,
        board_name: str = "",
        current_step: int = 0,
        total_steps: int = 0,
        completed: bool = False,
    ) -> None:
        """Update board compilation progress."""
        try:
            if self.current_phase != "building":
                self.transition_to_phase("building", "Compiling boards")

            self._handle_board_transition(board_name, completed)

            if current_step > 0:
                self._update_board_step_progress(current_step, total_steps)

            self._send_progress_update()
        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error("Failed to update board progress: %s", e, exc_info=exc_info)

    def complete_all_builds(self) -> None:
        """Mark all builds as complete and transition to done phase."""
        try:
            self.boards_completed = self.total_boards
            self.current_board = ""

            logger.debug(
                "All builds completed successfully (%d/%d). Marking as done.",
                self.boards_completed,
                self.total_boards,
            )
            self.transition_to_phase("done", "Build completed successfully")
            # Send additional progress update to ensure 100% completion is shown
            self._send_progress_update("Build completed successfully")
        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error("Failed to complete all builds: %s", e, exc_info=exc_info)

    def complete_build_success(
        self, reason: str = "Build completed successfully"
    ) -> None:
        """Mark build as complete regardless of current phase (for cached builds)."""
        try:
            self.boards_completed = self.total_boards
            self.current_board = ""

            logger.debug(
                "Build completed: %s (phase: %s)",
                reason,
                self.current_phase,
            )
            self.transition_to_phase("done", reason)
            # Send additional progress update to ensure 100% completion is shown
            self._send_progress_update(reason)
        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error("Failed to complete build: %s", e, exc_info=exc_info)

    def update_cache_saving(self, operation: str = "", progress_info: str = "") -> None:
        """Update cache saving progress."""
        try:
            if self.current_phase != "cache_saving":
                self.transition_to_phase("cache_saving", "Saving build cache")

            self.current_repository = self._get_cache_saving_description(
                operation, progress_info
            )
            logger.debug("Cache saving: %s", self.current_repository)
            self._send_progress_update()
        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error("Failed to update cache saving: %s", e, exc_info=exc_info)

    def update_docker_verification(
        self, image_name: str, status: str = "verifying"
    ) -> None:
        """Update Docker image verification progress (default implementation)."""
        # Default implementation - can be overridden by strategy-specific coordinators
        logger.debug("Docker verification: %s (%s)", image_name, status)

    def update_nix_build_progress(
        self, operation: str, status: str = "building"
    ) -> None:
        """Update Nix environment build progress (default implementation)."""
        # Default implementation - can be overridden by strategy-specific coordinators
        logger.debug("Nix build: %s (%s)", operation, status)

    def update_repository_progress(self, repository_name: str) -> None:
        """Update repository download progress (default implementation)."""
        # Default implementation - can be overridden by strategy-specific coordinators
        logger.debug("Repository progress: %s", repository_name)

    def get_current_progress(self) -> CompilationProgress:
        """Get the current unified progress state."""
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
            cache_operation_progress=self.cache_operation_progress,
            cache_operation_total=self.cache_operation_total,
            cache_operation_status=self.cache_operation_status,
            compilation_strategy=self.compilation_strategy,
            docker_image_name=self.docker_image_name,
        )

    # Helper methods
    def _get_workspace_progress_description(
        self, current_file: str, component: str
    ) -> str:
        """Get workspace progress description based on current state."""
        if current_file:
            return f"Copying: {current_file}"
        elif component:
            return f"Setting up: {component}"
        else:
            return "Setting up workspace"

    def _get_cache_saving_description(self, operation: str, progress_info: str) -> str:
        """Get cache saving description based on operation and progress info."""
        if operation and progress_info:
            return f"{operation}: {progress_info}"
        elif operation:
            return f"Cache {operation}"
        else:
            return "Saving build cache"

    def _handle_board_transition(self, board_name: str, completed: bool) -> None:
        """Handle board transition logic."""
        if board_name and board_name != self.current_board:
            if self.current_board:
                self.boards_completed += 1
                logger.debug(
                    "Completed build for board: %s (%d/%d)",
                    self.current_board,
                    self.boards_completed,
                    self.total_boards,
                )

            self.current_board = board_name
            self.current_board_step = 0
            self.total_board_steps = 0
            logger.debug(
                "Starting build for board: %s (%d/%d)",
                board_name,
                self.boards_completed + 1,
                self.total_boards,
            )

        if completed and self.current_board:
            logger.debug(
                "Board %s build completed (%d/%d)",
                self.current_board,
                self.boards_completed + 1,
                self.total_boards,
            )
            self.boards_completed += 1
            self.current_board = ""

    def _update_board_step_progress(self, current_step: int, total_steps: int) -> None:
        """Update board step progress."""
        self.current_board_step = current_step
        if total_steps > self.total_board_steps:
            self.total_board_steps = total_steps

        logger.debug(
            "Build progress for %s: %d/%d steps",
            self.current_board or "board",
            current_step,
            total_steps,
        )

    def _send_progress_update(self, custom_description: str = "") -> None:
        """Send unified progress update to TUI callback."""
        try:
            current_item = self._get_current_item_description(custom_description)

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
                cache_operation_progress=self.cache_operation_progress,
                cache_operation_total=self.cache_operation_total,
                cache_operation_status=self.cache_operation_status,
                compilation_strategy=self.compilation_strategy,
                docker_image_name=self.docker_image_name,
            )

            self.tui_callback(progress)
        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error("Failed to send progress update: %s", e, exc_info=exc_info)

    def _get_current_item_description(self, custom_description: str) -> str:
        """Get current item description based on phase and state."""
        if custom_description:
            return custom_description
        elif self.current_phase in [
            "cache_restoration",
            "workspace_setup",
            "west_update",
        ]:
            return self.current_repository
        elif self.current_phase == "building":
            return self._get_building_phase_description()
        elif self.current_phase == "collecting":
            return self.current_repository
        else:
            return "Initializing..."

    def _get_building_phase_description(self) -> str:
        """Get building phase description."""
        if self.current_board:
            if self.total_board_steps > 0:
                return f"{self.current_board} ({self.current_board_step}/{self.total_board_steps})"
            else:
                return f"{self.current_board} (starting)"
        else:
            return f"Completed {self.boards_completed}/{self.total_boards} boards"
