"""Progress manager with context manager pattern and logging capture."""

import logging
from typing import TYPE_CHECKING, Literal

from glovebox.cli.components.progress_config import ProgressConfig
from glovebox.cli.components.progress_context import ProgressContext
from glovebox.cli.components.progress_display import ProgressDisplay
from glovebox.protocols.progress_context_protocol import ProgressContextProtocol


if TYPE_CHECKING:
    from types import TracebackType


class ProgressManager:
    """Manages progress display lifecycle with integrated logging.

    This class provides a context manager interface for progress tracking,
    automatically handling display startup/shutdown and logging capture.

    Example:
        ```python
        config = ProgressConfig(
            operation_name="Build",
            checkpoints=["Setup", "Compile", "Package"]
        )

        with ProgressManager(config) as progress:
            progress.start_checkpoint("Setup")
            # ... do setup work
            progress.complete_checkpoint("Setup")
        ```
    """

    def __init__(self, config: ProgressConfig):
        """Initialize progress manager.

        Args:
            config: Progress display configuration
        """
        self.config = config
        self.display = ProgressDisplay(config)
        self.context = ProgressContext(self.display)


    def __enter__(self) -> ProgressContextProtocol:
        """Enter context manager, starting display.

        Returns:
            ProgressContextProtocol implementation for progress updates
        """
        # Start the display
        self.display.start()

        return self.context

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: "TracebackType | None",
    ) -> Literal[False]:
        """Exit context manager, stopping display.

        Args:
            exc_type: Exception type if an exception was raised
            exc_val: Exception value if an exception was raised
            exc_tb: Exception traceback if an exception was raised

        Returns:
            False to propagate any exception
        """
        # If an exception occurred, mark operation as failed
        if exc_type is not None:
            self.display.state.is_failed = True

            # Log the exception
            if exc_val is not None:
                self.context.log(f"Operation failed: {exc_val}", "error")

        # Stop the display
        self.display.stop()

        # Don't suppress exceptions
        return False

