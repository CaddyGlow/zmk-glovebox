# glovebox/protocols/progress_coordinator_protocol.py
"""Protocol for compilation progress coordinators."""

from typing import Protocol, runtime_checkable

from glovebox.core.file_operations import CompilationProgress


@runtime_checkable
class ProgressCoordinatorProtocol(Protocol):
    """Protocol defining the interface for compilation progress coordinators.

    This protocol ensures all progress coordinators (real implementations and NoOp)
    provide the same interface without requiring inheritance or union types.
    """

    @property
    def compilation_strategy(self) -> str:
        """Get the compilation strategy name."""
        ...

    # Common attributes that implementations may need
    current_phase: str
    docker_image_name: str

    def transition_to_phase(self, phase: str, description: str = "") -> None:
        """Transition to a new compilation phase."""
        ...

    def set_compilation_strategy(self, strategy: str, docker_image: str = "") -> None:
        """Set compilation strategy metadata."""
        ...

    def update_cache_progress(
        self,
        operation: str,
        current: int = 0,
        total: int = 100,
        description: str = "",
        status: str = "in_progress",
    ) -> None:
        """Update cache restoration progress."""
        ...

    def update_workspace_progress(
        self,
        files_copied: int = 0,
        total_files: int = 0,
        bytes_copied: int = 0,
        total_bytes: int = 0,
        current_file: str = "",
        component: str = "",
        transfer_speed_mb_s: float = 0.0,
        eta_seconds: float = 0.0,
    ) -> None:
        """Update workspace setup progress."""
        ...

    def update_export_progress(
        self,
        files_processed: int = 0,
        total_files: int = 0,
        current_file: str = "",
        archive_format: str = "",
        compression_level: int = 0,
        speed_mb_s: float = 0.0,
        eta_seconds: float = 0.0,
    ) -> None:
        """Update workspace export progress."""
        ...

    def update_repository_progress(self, repository_name: str) -> None:
        """Update repository download progress during west update."""
        ...

    def update_board_progress(
        self,
        board_name: str = "",
        current_step: int = 0,
        total_steps: int = 0,
        completed: bool = False,
    ) -> None:
        """Update board compilation progress."""
        ...

    def complete_all_builds(self) -> None:
        """Mark all builds as complete and transition to done phase."""
        ...

    def complete_build_success(
        self, reason: str = "Build completed successfully"
    ) -> None:
        """Mark build as complete regardless of current phase (for cached builds)."""
        ...

    def update_cache_saving(self, operation: str = "", progress_info: str = "") -> None:
        """Update cache saving progress."""
        ...

    def update_docker_verification(
        self, image_name: str, status: str = "verifying"
    ) -> None:
        """Update Docker image verification progress (MoErgo specific)."""
        ...

    def update_nix_build_progress(
        self, operation: str, status: str = "building"
    ) -> None:
        """Update Nix environment build progress (MoErgo specific)."""
        ...

    def get_current_progress(self) -> CompilationProgress:
        """Get the current unified progress state."""
        ...
