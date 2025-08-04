"""No-operation progress context implementation."""

from typing import TYPE_CHECKING, Any, Literal

from glovebox.protocols.progress_context_protocol import (
    ProgressContextProtocol,
    ProgressManagerProtocol,
)


if TYPE_CHECKING:
    from types import TracebackType


class NoOpProgressContext:
    """No-operation progress context that does nothing but satisfies the protocol.

    This implementation provides a null object pattern for progress tracking,
    allowing services to call progress methods unconditionally without None checks.
    All methods are no-ops with minimal overhead.
    """

    def set_total_checkpoints(self, checkpoints: list[str]) -> None:
        """No-op implementation of set_total_checkpoints."""
        pass

    def start_checkpoint(self, name: str) -> None:
        """No-op implementation of start_checkpoint."""
        pass

    def complete_checkpoint(self, name: str) -> None:
        """No-op implementation of complete_checkpoint."""
        pass

    def fail_checkpoint(self, name: str) -> None:
        """No-op implementation of fail_checkpoint."""
        pass

    def update_progress(self, current: int, total: int, status: str = "") -> None:
        """No-op implementation of update_progress."""
        pass

    def log(self, message: str, level: str = "info") -> None:
        """No-op implementation of log."""
        pass

    def set_status_info(self, info: dict[str, Any]) -> None:
        """No-op implementation of set_status_info."""
        pass

    def __enter__(self) -> ProgressContextProtocol:
        """Enter context manager, returning self.

        Returns:
            Self as ProgressContextProtocol for progress updates
        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: "TracebackType | None",
    ) -> Literal[False]:
        """Exit context manager.

        Args:
            exc_type: Exception type if an exception was raised
            exc_val: Exception value if an exception was raised
            exc_tb: Exception traceback if an exception was raised

        Returns:
            False to propagate any exception
        """
        # Don't suppress exceptions
        return False


# Singleton instance to avoid creating multiple NoOp objects
_NOOP_PROGRESS_CONTEXT = NoOpProgressContext()


def get_noop_progress_context() -> ProgressContextProtocol:
    """Get the singleton NoOp progress context.

    Returns:
        The singleton NoOpProgressContext instance that satisfies ProgressContextProtocol
    """
    return _NOOP_PROGRESS_CONTEXT


def get_noop_progress_manager() -> ProgressManagerProtocol:
    """Get the singleton NoOp progress context as a progress manager.

    Returns:
        The singleton NoOpProgressContext instance that satisfies ProgressManagerProtocol
    """
    return _NOOP_PROGRESS_CONTEXT
