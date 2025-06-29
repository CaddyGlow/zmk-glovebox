# glovebox/cli/components/progress_coordinators.py
"""Specialized compilation progress coordinators for different strategies."""

import logging
from typing import Any

from glovebox.cli.components.progress_coordinator_base import (
    BaseCompilationProgressCoordinator,
)
from glovebox.core.file_operations import (
    CompilationProgress,
    CompilationProgressCallback,
)
from glovebox.protocols.progress_coordinator_protocol import ProgressCoordinatorProtocol


logger = logging.getLogger(__name__)


class ZmkWestProgressCoordinator(BaseCompilationProgressCoordinator):
    """Progress coordinator specialized for ZMK West compilation strategy."""

    @property
    def compilation_strategy(self) -> str:
        """Get the compilation strategy name."""
        return "zmk_west"

    def _initialize_phases(self) -> dict[str, dict[str, Any]]:
        """Initialize ZMK West specific phases."""
        return {
            "initialization": {},
            "cache_restoration": {},
            "workspace_setup": {},
            "west_update": {},
            "building": {},
            "cache_saving": {},
        }

    def _get_phase_sequence(self) -> list[str]:
        """Get the sequence of phases for ZMK West strategy."""
        return [
            "initialization",
            "cache_restoration",
            "west_update",
            "building",
            "cache_saving",
        ]

    def update_repository_progress(self, repository_name: str) -> None:
        """Update repository download progress during west update."""
        try:
            if self.current_phase != "west_update":
                self.transition_to_phase("west_update", "Downloading repositories")

            self.repositories_downloaded += 1
            self.current_repository = repository_name

            logger.debug(
                "Downloaded repository %d/%d: %s",
                self.repositories_downloaded,
                self.total_repositories,
                repository_name,
            )
            self._send_progress_update()

            # Check completion and transition
            if self.repositories_downloaded >= self.total_repositories:
                logger.debug(
                    "West update completed: %d repositories downloaded.",
                    self.total_repositories,
                )
                self.transition_to_phase("building", "Starting compilation")
        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error(
                "Failed to update repository progress: %s", e, exc_info=exc_info
            )


class MoergoNixProgressCoordinator(BaseCompilationProgressCoordinator):
    """Progress coordinator specialized for MoErgo Nix compilation strategy."""

    @property
    def compilation_strategy(self) -> str:
        """Get the compilation strategy name."""
        return "moergo_nix"

    def _initialize_phases(self) -> dict[str, dict[str, Any]]:
        """Initialize MoErgo Nix specific phases."""
        return {
            "initialization": {},
            "cache_restoration": {},
            "docker_verification": {},
            "nix_build": {},
            "building": {},
            "cache_saving": {},
        }

    def _get_phase_sequence(self) -> list[str]:
        """Get the sequence of phases for MoErgo Nix strategy."""
        return [
            "initialization",
            "cache_restoration",
            "docker_verification",
            "nix_build",
            "building",
            "cache_saving",
        ]

    def update_docker_verification(
        self, image_name: str, status: str = "verifying"
    ) -> None:
        """Update Docker image verification progress."""
        try:
            if self.current_phase != "docker_verification":
                self.transition_to_phase(
                    "docker_verification", "Verifying Docker image"
                )

            self.docker_image_name = image_name
            self.current_repository = f"Verifying {image_name}: {status}"

            logger.debug("Docker verification: %s (%s)", image_name, status)
            self._send_progress_update()
        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error(
                "Failed to update docker verification: %s", e, exc_info=exc_info
            )

    def update_nix_build_progress(
        self, operation: str, status: str = "building"
    ) -> None:
        """Update Nix environment build progress."""
        try:
            if self.current_phase != "nix_build":
                self.transition_to_phase("nix_build", "Building Nix environment")

            self.current_repository = f"Nix {operation}: {status}"

            logger.debug("Nix build: %s (%s)", operation, status)
            self._send_progress_update()
        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error(
                "Failed to update nix build progress: %s", e, exc_info=exc_info
            )

    def update_repository_progress(self, repository_name: str) -> None:
        """MoErgo doesn't use west repositories, so this is a no-op."""
        logger.debug(
            "MoErgo strategy doesn't use repository downloads: %s", repository_name
        )


class NoOpProgressCoordinator(ProgressCoordinatorProtocol):
    """No-operation progress coordinator that implements the same interface but does nothing.

    This eliminates the need for conditional checks throughout the codebase by providing
    a do-nothing implementation of all progress coordinator methods.
    """

    def __init__(self) -> None:
        """Initialize no-op coordinator with minimal state."""
        self.current_phase = "initialization"
        self.total_boards = 0
        self.board_names: list[str] = []
        self.total_repositories = 0
        self.repositories_downloaded = 0
        self.boards_completed = 0
        self.current_board = ""
        self.current_repository = ""
        self.current_board_step = 0
        self.total_board_steps = 0
        self._compilation_strategy = "zmk_west"
        self.docker_image_name = ""

    @property
    def compilation_strategy(self) -> str:
        """Get the compilation strategy name."""
        return self._compilation_strategy

    def transition_to_phase(self, phase: str, description: str = "") -> None:
        """No-op phase transition."""
        self.current_phase = phase

    def set_compilation_strategy(self, strategy: str, docker_image: str = "") -> None:
        """No-op compilation strategy setting."""
        self._compilation_strategy = strategy
        self.docker_image_name = docker_image

    def update_cache_progress(
        self,
        operation: str,
        current: int = 0,
        total: int = 100,
        description: str = "",
        status: str = "in_progress",
    ) -> None:
        """No-op cache progress update."""
        pass

    def update_workspace_progress(
        self,
        files_copied: int = 0,
        total_files: int = 0,
        bytes_copied: int = 0,
        total_bytes: int = 0,
        current_file: str = "",
        component: str = "",
    ) -> None:
        """No-op workspace progress update."""
        pass

    def update_repository_progress(self, repository_name: str) -> None:
        """No-op repository progress update."""
        pass

    def update_board_progress(
        self,
        board_name: str = "",
        current_step: int = 0,
        total_steps: int = 0,
        completed: bool = False,
    ) -> None:
        """No-op board progress update."""
        pass

    def complete_all_builds(self) -> None:
        """No-op build completion."""
        pass

    def complete_build_success(
        self, reason: str = "Build completed successfully"
    ) -> None:
        """No-op build success completion."""
        pass

    def update_cache_saving(self, operation: str = "", progress_info: str = "") -> None:
        """No-op cache saving update."""
        pass

    def update_docker_verification(
        self, image_name: str, status: str = "verifying"
    ) -> None:
        """No-op docker verification update."""
        pass

    def update_nix_build_progress(
        self, operation: str, status: str = "building"
    ) -> None:
        """No-op nix build progress update."""
        pass

    def get_current_progress(self) -> CompilationProgress:
        """Return minimal progress object."""
        return CompilationProgress(
            repositories_downloaded=0,
            total_repositories=0,
            current_repository="",
            compilation_phase=self.current_phase,
            current_board="",
            boards_completed=0,
            total_boards=0,
            current_board_step=0,
            total_board_steps=0,
            cache_operation_progress=0,
            cache_operation_total=100,
            cache_operation_status="pending",
            compilation_strategy=self._compilation_strategy,
            docker_image_name=self.docker_image_name,
        )


def create_progress_coordinator(
    strategy: str,
    tui_callback: CompilationProgressCallback | None,
    total_boards: int = 1,
    board_names: list[str] | None = None,
    total_repositories: int = 39,
) -> ProgressCoordinatorProtocol:
    """Factory function to create appropriate progress coordinator based on strategy.

    Args:
        strategy: Compilation strategy ('zmk_west', 'moergo_nix', etc.)
        tui_callback: TUI callback function, or None for no-op coordinator
        total_boards: Total number of boards to compile
        board_names: List of board names for progress tracking
        total_repositories: Total number of repositories to download

    Returns:
        Strategy-specific progress coordinator implementing ProgressCoordinatorProtocol
    """
    if tui_callback is None:
        return NoOpProgressCoordinator()

    if strategy == "moergo_nix":
        return MoergoNixProgressCoordinator(
            tui_callback=tui_callback,
            total_boards=total_boards,
            board_names=board_names,
            total_repositories=total_repositories,
        )
    else:  # Default to ZMK West for 'zmk_west' and unknown strategies
        return ZmkWestProgressCoordinator(
            tui_callback=tui_callback,
            total_boards=total_boards,
            board_names=board_names,
            total_repositories=total_repositories,
        )
