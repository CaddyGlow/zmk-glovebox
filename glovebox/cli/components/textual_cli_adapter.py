"""Textual CLI adapter for running Textual widgets standalone in CLI commands."""

import asyncio
import sys
from collections.abc import Callable
from typing import Any, Generic, TypeVar

from textual.app import App, ComposeResult

# Import the progress widgets
from glovebox.tui.widgets.progress_widget import ProgressWidget


# Type variable for progress data
T = TypeVar("T")


class StandaloneProgressApp(App[Any], Generic[T]):
    """Standalone Textual app for running progress widgets in CLI mode.

    This app provides a minimal container for running progress widgets
    as standalone CLI components with proper keyboard handling and
    graceful exit functionality.
    """

    def __init__(
        self,
        progress_widget: ProgressWidget[T],
        title: str = "Progress",
        **kwargs: Any,
    ) -> None:
        """Initialize the standalone progress app.

        Args:
            progress_widget: The progress widget to display
            title: The title for the app window (stored but not passed to App)
            **kwargs: Additional arguments for the App
        """
        super().__init__(**kwargs)
        self.progress_widget = progress_widget
        self.app_title = title  # Store title for potential future use
        self._result: Any = None
        self._completed = False

    def compose(self) -> ComposeResult:
        """Compose the app with the progress widget."""
        yield self.progress_widget

    def on_mount(self) -> None:
        """Initialize the app when mounted."""
        # Widget will handle its own initialization
        pass

    def get_result(self) -> Any:
        """Get the result of the progress operation.

        Returns:
            The result from the progress widget
        """
        return self.progress_widget.get_result()

    def get_progress_callback(self) -> Callable[[T], None]:
        """Get the progress callback from the widget.

        Returns:
            The progress callback function
        """
        return self.progress_widget.start_progress()

    def complete_operation(self, result: Any = None) -> None:
        """Complete the progress operation and exit.

        Args:
            result: Optional result data
        """
        if not self._completed:
            self._completed = True
            self.progress_widget.complete_progress(result)
            # Schedule app exit after a brief delay to show completion
            self.set_timer(1.5, self.exit)

    def cancel_operation(self, error: Exception | None = None) -> None:
        """Cancel the progress operation.

        Args:
            error: Optional error that caused cancellation
        """
        if not self._completed:
            self._completed = True
            self.progress_widget.cancel_progress(error)
            # Schedule app exit after a brief delay to show cancellation
            self.set_timer(1.0, self.exit)


class TextualCliAdapter:
    """Adapter for running Textual widgets as standalone CLI components.

    This adapter provides a bridge between Textual widgets and CLI commands,
    allowing widgets to be used both in standalone CLI mode and integrated
    within the full TUI application.
    """

    def __init__(self) -> None:
        """Initialize the CLI adapter."""
        self._current_app: StandaloneProgressApp[Any] | None = None

    def run_progress_widget_standalone(
        self,
        widget_class: type[ProgressWidget[T]],
        title: str = "Progress",
        **widget_kwargs: Any,
    ) -> tuple[
        Callable[[T], None],
        Callable[[], Any],
        Callable[[Any], None],
        Callable[[Exception | None], None],
    ]:
        """Run a progress widget standalone in CLI mode.

        Args:
            widget_class: The progress widget class to run
            title: The title for the progress display
            **widget_kwargs: Keyword arguments for the widget

        Returns:
            Tuple of (progress_callback, get_result, complete, cancel) functions
        """
        # Create the widget and app
        widget = widget_class(**widget_kwargs)
        app = StandaloneProgressApp(widget, title=title)
        self._current_app = app

        # Get the progress callback
        progress_callback = app.get_progress_callback()

        # Define control functions
        def get_result() -> Any:
            """Get the result of the operation."""
            return app.get_result()

        def complete(result: Any = None) -> None:
            """Complete the operation."""
            app.complete_operation(result)

        def cancel(error: Exception | None = None) -> None:
            """Cancel the operation."""
            app.cancel_operation(error)

        # Start the app in a separate thread
        self._start_app_async(app)

        return progress_callback, get_result, complete, cancel

    def _start_app_async(self, app: StandaloneProgressApp[Any]) -> None:
        """Start the Textual app asynchronously in the main thread.

        Args:
            app: The app to start
        """
        try:
            # Check if we're already in an event loop
            try:
                loop = asyncio.get_running_loop()
                # We're in an existing event loop, schedule the app to run
                asyncio.create_task(self._run_app_in_existing_loop(app))
            except RuntimeError:
                # No event loop running, we can run directly
                asyncio.run(app.run_async())
        except Exception as e:
            # Handle any errors in app execution
            print(f"Error running Textual app: {e}", file=sys.stderr)

    async def _run_app_in_existing_loop(self, app: StandaloneProgressApp[Any]) -> None:
        """Run the app within an existing event loop.

        Args:
            app: The app to start
        """
        try:
            await app.run_async()
        except Exception as e:
            print(f"Error running Textual app in existing loop: {e}", file=sys.stderr)

    def cleanup(self) -> None:
        """Clean up the adapter and any running apps."""
        if self._current_app:
            # Try to exit the app gracefully
            try:
                if hasattr(self._current_app, "exit"):
                    self._current_app.exit()
            except Exception:
                pass  # Ignore cleanup errors

        self._current_app = None


# Global adapter instance for reuse
_adapter_instance: TextualCliAdapter | None = None


def get_textual_cli_adapter() -> TextualCliAdapter:
    """Get the global TextualCliAdapter instance.

    Returns:
        The global adapter instance
    """
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = TextualCliAdapter()
    return _adapter_instance


def run_workspace_progress_standalone(
    title: str = "Workspace Progress",
    **widget_kwargs: Any,
) -> tuple[
    Callable[[Any], None],
    Callable[[], Any],
    Callable[[Any], None],
    Callable[[Exception | None], None],
]:
    """Run a workspace progress widget standalone.

    Args:
        title: The title for the progress display
        **widget_kwargs: Keyword arguments for the widget

    Returns:
        Tuple of (progress_callback, get_result, complete, cancel) functions
    """
    from glovebox.tui.widgets.workspace_progress_widget import WorkspaceProgressWidget

    adapter = get_textual_cli_adapter()
    return adapter.run_progress_widget_standalone(
        WorkspaceProgressWidget,
        title=title,
        **widget_kwargs,
    )


def run_compilation_progress_standalone(
    title: str = "Compilation Progress",
    **widget_kwargs: Any,
) -> tuple[
    Callable[[Any], None],
    Callable[[], Any],
    Callable[[Any], None],
    Callable[[Exception | None], None],
]:
    """Run a compilation progress widget standalone.

    Args:
        title: The title for the progress display
        **widget_kwargs: Keyword arguments for the widget

    Returns:
        Tuple of (progress_callback, get_result, complete, cancel) functions
    """
    from glovebox.tui.widgets.compilation_progress_widget import (
        CompilationProgressWidget,
    )

    adapter = get_textual_cli_adapter()
    return adapter.run_progress_widget_standalone(
        CompilationProgressWidget,
        title=title,
        **widget_kwargs,
    )


class ProgressDisplayContext:
    """Context manager for standalone progress displays.

    This context manager provides a clean interface for using progress
    widgets in CLI commands with proper setup and cleanup.
    """

    def __init__(
        self,
        widget_type: str,
        title: str | None = None,
        **widget_kwargs: Any,
    ) -> None:
        """Initialize the progress display context.

        Args:
            widget_type: Type of widget ("workspace" or "compilation")
            title: Optional title for the display
            **widget_kwargs: Keyword arguments for the widget
        """
        self.widget_type = widget_type
        self.title = title or f"{widget_type.title()} Progress"
        self.widget_kwargs = widget_kwargs

        self.progress_callback: Callable[[Any], None] | None = None
        self.get_result: Callable[[], Any] | None = None
        self.complete: Callable[[Any], None] | None = None
        self.cancel: Callable[[Exception | None], None] | None = None

    def __enter__(self) -> "ProgressDisplayContext":
        """Enter the context and set up the progress display."""
        if self.widget_type == "workspace":
            functions = run_workspace_progress_standalone(
                title=self.title,
                **self.widget_kwargs,
            )
        elif self.widget_type == "compilation":
            functions = run_compilation_progress_standalone(
                title=self.title,
                **self.widget_kwargs,
            )
        else:
            raise ValueError(f"Unknown widget type: {self.widget_type}")

        self.progress_callback, self.get_result, self.complete, self.cancel = functions
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit the context and clean up."""
        if exc_type is not None and self.cancel:
            # Cancel on exception - convert BaseException to Exception if needed
            error = (
                exc_val if isinstance(exc_val, Exception) else Exception(str(exc_val))
            )
            self.cancel(error)

        # Clean up the adapter
        adapter = get_textual_cli_adapter()
        adapter.cleanup()

    def update_progress(self, progress_data: Any) -> None:
        """Update the progress display.

        Args:
            progress_data: Progress data to display
        """
        if self.progress_callback:
            self.progress_callback(progress_data)

    def complete_progress(self, result: Any = None) -> None:
        """Complete the progress operation.

        Args:
            result: Optional result data
        """
        if self.complete:
            self.complete(result)

    def cancel_progress(self, error: Exception | None = None) -> None:
        """Cancel the progress operation.

        Args:
            error: Optional error that caused cancellation
        """
        if self.cancel:
            self.cancel(error)

    def get_progress_result(self) -> Any:
        """Get the result of the progress operation.

        Returns:
            The result data
        """
        if self.get_result:
            return self.get_result()
        return None
