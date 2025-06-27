"""Base progress widget for reusable progress display components."""

import asyncio
import time
from collections.abc import Callable
from typing import Any, Generic, Protocol, TypeVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import ProgressBar, Static


# Type variables for generic progress data
T = TypeVar("T")


class ProgressDataProtocol(Protocol):
    """Protocol for progress data objects."""

    def get_status_text(self) -> str:
        """Get the current status text to display."""
        ...

    def get_progress_info(self) -> tuple[int, int, str]:
        """Get progress information as (current, total, description)."""
        ...


ProgressCallback = Callable[[T], None]


class ProgressWidget(Widget, Generic[T]):
    """Base reusable progress widget using Textual.

    This widget provides a foundation for progress display components that can work
    both standalone in CLI commands and integrated within the full TUI application.

    Features:
    - Reactive progress tracking with automatic UI updates
    - Customizable status display and progress bar
    - Keyboard controls (ESC to cancel, space to pause/resume)
    - Extensible for specialized progress types (workspace, compilation, etc.)
    - Proper lifecycle management with start/stop methods
    """

    # Reactive properties for real-time updates
    progress_current: reactive[int] = reactive(0)
    progress_total: reactive[int] = reactive(100)
    status_text: reactive[str] = reactive("Initializing...")
    description: reactive[str] = reactive("Starting...")
    is_paused: reactive[bool] = reactive(False)
    is_cancelled: reactive[bool] = reactive(False)
    is_completed: reactive[bool] = reactive(False)

    # Keyboard bindings
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("space", "toggle_pause", "Pause/Resume"),
        Binding("q", "quit", "Quit", show=False),
    ]

    def __init__(
        self,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        """Initialize the progress widget.

        Args:
            name: The name of the widget
            id: The ID of the widget
            classes: CSS classes for styling
            disabled: Whether the widget is disabled
        """
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)

        # Progress tracking
        self.start_time = time.time()
        self._progress_callback: ProgressCallback[T] | None = None

        # Internal state
        self._result: Any = None
        self._error: Exception | None = None

    def compose(self) -> ComposeResult:
        """Compose the progress widget layout."""
        yield Static(self.status_text, id="status-text", classes="status")
        yield ProgressBar(
            total=self.progress_total,
            show_eta=True,
            show_percentage=True,
            id="progress-bar",
        )
        yield Static(self.description, id="description", classes="description")

    def on_mount(self) -> None:
        """Initialize the progress widget when mounted."""
        # Get references to child widgets
        self.status_widget = self.query_one("#status-text", Static)
        self.progress_bar = self.query_one("#progress-bar", ProgressBar)
        self.description_widget = self.query_one("#description", Static)

        # Set initial progress
        self.progress_bar.update(progress=self.progress_current)

    def start_progress(self) -> ProgressCallback[T]:
        """Start the progress tracking and return a callback for updates.

        Returns:
            Callback function to call with progress updates
        """
        self.start_time = time.time()
        self.is_completed = False
        self.is_cancelled = False
        self._error = None

        def progress_callback(progress_data: T) -> None:
            """Progress callback that updates the widget state."""
            if self.is_cancelled:
                return

            try:
                self._update_from_progress_data(progress_data)
            except Exception as e:
                self._error = e
                self.status_text = f"Error: {e}"

        self._progress_callback = progress_callback
        return progress_callback

    def complete_progress(self, result: Any = None) -> None:
        """Mark the progress as completed.

        Args:
            result: Optional result data to store
        """
        self.is_completed = True
        self._result = result
        total_time = time.time() - self.start_time
        self.status_text = f"✅ Completed in {total_time:.1f}s"
        self.progress_current = self.progress_total

    def cancel_progress(self, error: Exception | None = None) -> None:
        """Cancel the progress operation.

        Args:
            error: Optional error that caused cancellation
        """
        self.is_cancelled = True
        self._error = error
        if error:
            self.status_text = f"❌ Cancelled: {error}"
        else:
            self.status_text = "❌ Cancelled by user"

    def get_result(self) -> Any:
        """Get the result of the progress operation.

        Returns:
            The result data, or None if not completed
        """
        return self._result

    def get_error(self) -> Exception | None:
        """Get any error that occurred during progress.

        Returns:
            The error exception, or None if no error
        """
        return self._error

    def _update_from_progress_data(self, progress_data: T) -> None:
        """Update widget state from progress data.

        This method should be overridden by subclasses to handle
        specific progress data types.

        Args:
            progress_data: The progress data to process
        """
        # Default implementation assumes progress_data has protocol methods
        if hasattr(progress_data, "get_status_text"):
            self.status_text = progress_data.get_status_text()
        else:
            self.status_text = str(progress_data)

        if hasattr(progress_data, "get_progress_info"):
            current, total, description = progress_data.get_progress_info()
            self.progress_current = current
            self.progress_total = total
            self.description = description

    # Reactive watchers for UI updates
    def watch_status_text(self, status_text: str) -> None:
        """React to status text changes."""
        if hasattr(self, "status_widget"):
            self.status_widget.update(status_text)

    def watch_description(self, description: str) -> None:
        """React to description changes."""
        if hasattr(self, "description_widget"):
            self.description_widget.update(description)

    def watch_progress_current(self, progress_current: int) -> None:
        """React to progress current changes."""
        if hasattr(self, "progress_bar"):
            self.progress_bar.update(progress=progress_current)

    def watch_progress_total(self, progress_total: int) -> None:
        """React to progress total changes."""
        if hasattr(self, "progress_bar"):
            self.progress_bar.update(total=progress_total)

    # Action handlers for keyboard bindings
    def action_cancel(self) -> None:
        """Cancel the progress operation."""
        self.cancel_progress()

    def action_toggle_pause(self) -> None:
        """Toggle pause/resume state."""
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.status_text = "⏸️ Paused - Press space to resume"
        else:
            self.status_text = "▶️ Resumed"

    def action_quit(self) -> None:
        """Quit the progress display."""
        self.cancel_progress()
        # If running standalone, exit the app
        if hasattr(self.app, "exit"):
            self.app.exit()


class StandaloneProgressApp(Generic[T]):
    """Standalone app for running progress widgets in CLI mode."""

    def __init__(
        self, widget_class: type[ProgressWidget[T]], **widget_kwargs: Any
    ) -> None:
        """Initialize the standalone progress app.

        Args:
            widget_class: The progress widget class to run
            **widget_kwargs: Keyword arguments for the widget
        """
        self.widget_class = widget_class
        self.widget_kwargs = widget_kwargs
        self.widget: ProgressWidget[T] | None = None

    async def run_async(self) -> Any:
        """Run the progress widget asynchronously.

        Returns:
            The result of the progress operation
        """
        from textual.app import App

        class ProgressApp(App[Any]):
            """Minimal Textual app for standalone progress display."""

            def __init__(self, widget: ProgressWidget[T]) -> None:
                super().__init__()
                self.progress_widget = widget

            def compose(self) -> ComposeResult:
                yield self.progress_widget

            def on_mount(self) -> None:
                """Start progress tracking when app mounts."""
                self.progress_widget.start_progress()

        # Create widget and app
        self.widget = self.widget_class(**self.widget_kwargs)
        app = ProgressApp(self.widget)

        # Run the app and return result
        await app.run_async()
        return self.widget.get_result() if self.widget else None

    def get_progress_callback(self) -> ProgressCallback[T] | None:
        """Get the progress callback for external use.

        Returns:
            The progress callback function, or None if not started
        """
        return self.widget.start_progress() if self.widget else None
