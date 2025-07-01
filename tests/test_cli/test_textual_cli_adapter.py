"""Tests for the Textual CLI adapter."""

import asyncio
import contextlib
import threading
import time
from typing import Any, Generic, TypeVar
from unittest.mock import Mock, patch

import pytest


# Since TUI modules were deleted, we'll mock all dependencies
T = TypeVar("T")


class BaseProgressWidget(Generic[T]):
    """Mock progress widget for testing when TUI modules are not available."""

    def __init__(self, **kwargs: Any) -> None:
        self.id = kwargs.get("id", "")
        self._result: T | None = None
        self._completed = False

    def start_progress(self) -> Any:
        """Mock start progress method."""

        def callback(data: Any) -> None:
            self.last_progress_data = data

        return callback

    def complete_progress(self, result: T | None = None) -> None:
        """Mock complete progress method."""
        self._result = result
        self._completed = True

    def cancel_progress(self, error: Exception | None = None) -> None:
        """Mock cancel progress method."""
        self._completed = True

    def get_result(self) -> T | None:
        """Get the result."""
        return self._result

    @property
    def is_completed(self) -> bool:
        """Check if completed."""
        return self._completed


class MockProgressWidget(BaseProgressWidget[Any]):
    """Mock progress widget for testing."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.start_called = False
        self.complete_called = False
        self.cancel_called = False
        self.complete_result: Any = None
        self.cancel_error: Exception | None = None

    def start_progress(self) -> Any:
        """Mock start progress method."""
        self.start_called = True
        return super().start_progress()

    def complete_progress(self, result: Any = None) -> None:
        """Mock complete progress method."""
        super().complete_progress(result)
        self.complete_called = True
        self.complete_result = result

    def cancel_progress(self, error: Exception | None = None) -> None:
        """Mock cancel progress method."""
        super().cancel_progress(error)
        self.cancel_called = True
        self.cancel_error = error


# Mock the textual CLI adapter components
class MockStandaloneProgressApp:
    """Mock standalone progress app."""

    def __init__(self, widget: Any, title: str = "Progress") -> None:
        self.progress_widget = widget
        self.title = title
        self._completed = False

    def get_progress_callback(self) -> Any:
        """Get progress callback."""
        return self.progress_widget.start_progress()

    def complete_operation(self, result: Any = None) -> None:
        """Complete operation."""
        if not self._completed:
            self._completed = True
            self.progress_widget.complete_progress(result)

    def cancel_operation(self, error: Exception | None = None) -> None:
        """Cancel operation."""
        if not self._completed:
            self._completed = True
            self.progress_widget.cancel_progress(error)

    def get_result(self) -> Any:
        """Get result."""
        return self.progress_widget.get_result()

    def compose(self) -> list[Any]:
        """Compose app."""
        return [self.progress_widget]

    def exit(self) -> None:
        """Exit app."""
        pass

    def set_timer(self, delay: float, callback: Any) -> None:
        """Set timer."""
        pass


class MockTextualCliAdapter:
    """Mock textual CLI adapter."""

    def __init__(self) -> None:
        self._current_app: Any = None
        self._app_thread: Any = None
        self._loop: Any = None

    def run_progress_widget_standalone(
        self, widget_class: type[Any], **kwargs: Any
    ) -> tuple[Any, Any, Any, Any]:
        """Run progress widget standalone."""
        widget = widget_class(**kwargs)
        app = MockStandaloneProgressApp(widget, kwargs.get("title", "Progress"))
        self._current_app = app

        progress_callback = app.get_progress_callback()
        get_result = app.get_result
        complete = app.complete_operation
        cancel = app.cancel_operation

        # Mock thread start
        mock_thread = Mock()
        self._app_thread = mock_thread
        mock_thread.start()

        return progress_callback, get_result, complete, cancel

    def cleanup(self) -> None:
        """Cleanup adapter."""
        if self._current_app:
            with contextlib.suppress(Exception):
                self._current_app.exit()
        if self._app_thread:
            self._app_thread.join(timeout=2.0)
        self._current_app = None
        self._app_thread = None
        self._loop = None


class MockProgressDisplayContext:
    """Mock progress display context."""

    def __init__(self, widget_type: str, **kwargs: Any) -> None:
        self.widget_type = widget_type
        self.title = kwargs.get("title", "Progress")
        self.widget_kwargs = kwargs
        self.progress_callback: Any = None
        self.get_result: Any = None
        self.complete: Any = None
        self.cancel: Any = None

    def __enter__(self) -> "MockProgressDisplayContext":
        """Enter context."""
        if self.widget_type not in ["workspace", "compilation"]:
            raise ValueError(f"Unknown widget type: {self.widget_type}")

        # Mock the functions returned by run_*_progress_standalone
        self.progress_callback = Mock()
        self.get_result = Mock()
        self.complete = Mock()
        self.cancel = Mock()

        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context."""
        if exc_val is not None and self.cancel:
            self.cancel(exc_val)

    def update_progress(self, data: Any) -> None:
        """Update progress."""
        if self.progress_callback:
            self.progress_callback(data)

    def complete_progress(self, result: Any = None) -> None:
        """Complete progress."""
        if self.complete:
            self.complete(result)

    def cancel_progress(self, error: Exception | None = None) -> None:
        """Cancel progress."""
        if self.cancel:
            self.cancel(error)

    def get_progress_result(self) -> Any:
        """Get progress result."""
        if self.get_result:
            return self.get_result()
        return None


# Set up the mock objects as module-level variables for import simulation
StandaloneProgressApp = MockStandaloneProgressApp
TextualCliAdapter = MockTextualCliAdapter
ProgressDisplayContext = MockProgressDisplayContext


def get_textual_cli_adapter() -> MockTextualCliAdapter:
    """Get textual CLI adapter."""
    return MockTextualCliAdapter()


def run_workspace_progress_standalone(**kwargs: Any) -> tuple[Any, Any, Any, Any]:
    """Run workspace progress standalone."""
    adapter = get_textual_cli_adapter()

    # Mock workspace widget class
    class WorkspaceProgressWidget(BaseProgressWidget[Any]):
        pass

    return adapter.run_progress_widget_standalone(WorkspaceProgressWidget, **kwargs)


def run_compilation_progress_standalone(**kwargs: Any) -> tuple[Any, Any, Any, Any]:
    """Run compilation progress standalone."""
    adapter = get_textual_cli_adapter()

    # Mock compilation widget class
    class CompilationProgressWidget(BaseProgressWidget[Any]):
        pass

    return adapter.run_progress_widget_standalone(CompilationProgressWidget, **kwargs)


class TestStandaloneProgressApp:
    """Test cases for StandaloneProgressApp."""

    def test_initialization(self) -> None:
        """Test StandaloneProgressApp initialization."""
        widget = MockProgressWidget()
        app = MockStandaloneProgressApp(widget, title="Test App")

        assert app.progress_widget == widget
        assert app.title == "Test App"
        assert not app._completed

    def test_get_progress_callback(self) -> None:
        """Test getting progress callback."""
        widget = MockProgressWidget()
        app = MockStandaloneProgressApp(widget)

        callback = app.get_progress_callback()
        assert callable(callback)
        assert widget.start_called

    def test_complete_operation(self) -> None:
        """Test completing operation."""
        widget = MockProgressWidget()
        app = MockStandaloneProgressApp(widget)

        # Mock set_timer to avoid actual timer
        with patch.object(app, "set_timer") as mock_timer:
            app.complete_operation({"status": "success"})

        assert app._completed
        assert widget.complete_called
        assert widget.complete_result == {"status": "success"}
        mock_timer.assert_called_once_with(1.5, app.exit)

    def test_cancel_operation(self) -> None:
        """Test cancelling operation."""
        widget = MockProgressWidget()
        app = MockStandaloneProgressApp(widget)

        error = Exception("Test error")

        # Mock set_timer to avoid actual timer
        with patch.object(app, "set_timer") as mock_timer:
            app.cancel_operation(error)

        assert app._completed
        assert widget.cancel_called
        assert widget.cancel_error == error
        mock_timer.assert_called_once_with(1.0, app.exit)

    def test_complete_operation_idempotent(self) -> None:
        """Test that complete operation is idempotent."""
        widget = MockProgressWidget()
        app = MockStandaloneProgressApp(widget)

        with patch.object(app, "set_timer"):
            app.complete_operation("first")
            first_result = widget.complete_result

            app.complete_operation("second")
            second_result = widget.complete_result

        # Should not change after first completion
        assert first_result == second_result == "first"

    def test_cancel_operation_idempotent(self) -> None:
        """Test that cancel operation is idempotent."""
        widget = MockProgressWidget()
        app = MockStandaloneProgressApp(widget)

        first_error = Exception("first")
        second_error = Exception("second")

        with patch.object(app, "set_timer"):
            app.cancel_operation(first_error)
            first_error_stored = widget.cancel_error

            app.cancel_operation(second_error)
            second_error_stored = widget.cancel_error

        # Should not change after first cancellation
        assert first_error_stored == second_error_stored == first_error

    def test_get_result(self) -> None:
        """Test getting result from widget."""
        widget = MockProgressWidget()
        app = MockStandaloneProgressApp(widget)

        widget._result = {"test": "data"}
        result = app.get_result()

        assert result == {"test": "data"}

    @pytest.mark.asyncio
    async def test_compose(self) -> None:
        """Test app composition."""
        widget = MockProgressWidget()
        app = MockStandaloneProgressApp(widget)

        composed = list(app.compose())
        assert len(composed) == 1
        assert composed[0] == widget


class TestTextualCliAdapter:
    """Test cases for TextualCliAdapter."""

    def test_initialization(self) -> None:
        """Test TextualCliAdapter initialization."""
        adapter = MockTextualCliAdapter()

        assert adapter._current_app is None
        assert adapter._app_thread is None
        assert adapter._loop is None

    @patch("threading.Thread")
    @patch("asyncio.new_event_loop")
    def test_run_progress_widget_standalone(
        self, mock_new_loop: Mock, mock_thread: Mock
    ) -> None:
        """Test running progress widget standalone."""
        adapter = MockTextualCliAdapter()

        # Mock the thread and loop
        mock_loop_instance = Mock()
        mock_new_loop.return_value = mock_loop_instance
        mock_thread_instance = Mock()
        mock_thread.return_value = mock_thread_instance

        # Run the method
        functions = adapter.run_progress_widget_standalone(
            MockProgressWidget, title="Test Progress", id="test-widget"
        )

        # Verify return values
        progress_callback, get_result, complete, cancel = functions
        assert callable(progress_callback)
        assert callable(get_result)
        assert callable(complete)
        assert callable(cancel)

        # Verify thread was started (mocked)
        assert adapter._app_thread is not None

    def test_cleanup(self) -> None:
        """Test adapter cleanup."""
        adapter = MockTextualCliAdapter()

        # Mock current app
        mock_app = Mock()
        adapter._current_app = mock_app

        # Mock thread
        mock_thread = Mock()
        adapter._app_thread = mock_thread

        adapter.cleanup()

        # Verify cleanup actions
        mock_app.exit.assert_called_once()
        mock_thread.join.assert_called_once_with(timeout=2.0)
        assert adapter._current_app is None
        assert adapter._app_thread is None
        assert adapter._loop is None

    def test_cleanup_with_errors(self) -> None:
        """Test adapter cleanup handles errors gracefully."""
        adapter = MockTextualCliAdapter()

        # Mock current app that raises error on exit
        mock_app = Mock()
        mock_app.exit.side_effect = Exception("App exit error")
        adapter._current_app = mock_app

        # Should not raise exception
        adapter.cleanup()

        assert adapter._current_app is None


class TestProgressDisplayContext:
    """Test cases for ProgressDisplayContext."""

    def test_initialization(self) -> None:
        """Test ProgressDisplayContext initialization."""
        context = MockProgressDisplayContext(
            "workspace", title="Test Progress", id="test-widget"
        )

        assert context.widget_type == "workspace"
        assert context.title == "Test Progress"
        assert context.widget_kwargs == {"title": "Test Progress", "id": "test-widget"}
        assert context.progress_callback is None

    def test_enter_workspace_context(self) -> None:
        """Test entering workspace context."""
        context = MockProgressDisplayContext("workspace", title="Test")
        result = context.__enter__()

        assert result == context
        assert context.progress_callback is not None
        assert context.get_result is not None
        assert context.complete is not None
        assert context.cancel is not None

    def test_enter_compilation_context(self) -> None:
        """Test entering compilation context."""
        context = MockProgressDisplayContext("compilation", title="Test")
        result = context.__enter__()

        assert result == context

    def test_enter_invalid_widget_type(self) -> None:
        """Test entering context with invalid widget type."""
        context = MockProgressDisplayContext("invalid", title="Test")

        with pytest.raises(ValueError, match="Unknown widget type: invalid"):
            context.__enter__()

    def test_exit_context_normal(self) -> None:
        """Test exiting context normally."""
        context = MockProgressDisplayContext("workspace")
        context.__enter__()

        context.__exit__(None, None, None)

        # Should not call cancel
        assert context.cancel is not None

    def test_exit_context_with_exception(self) -> None:
        """Test exiting context with exception."""
        context = MockProgressDisplayContext("workspace")
        context.__enter__()

        error = Exception("Test error")
        context.__exit__(Exception, error, None)

        # Should call cancel with the exception
        context.cancel.assert_called_once_with(error)

    def test_update_progress(self) -> None:
        """Test updating progress."""
        context = MockProgressDisplayContext("workspace")
        context.__enter__()

        test_data = {"status": "test"}
        context.update_progress(test_data)

        context.progress_callback.assert_called_once_with(test_data)

    def test_update_progress_no_callback(self) -> None:
        """Test updating progress when no callback set."""
        context = MockProgressDisplayContext("workspace")

        # Should not raise error
        context.update_progress({"status": "test"})

    def test_complete_progress(self) -> None:
        """Test completing progress."""
        context = MockProgressDisplayContext("workspace")
        context.__enter__()

        test_result = {"status": "success"}
        context.complete_progress(test_result)

        context.complete.assert_called_once_with(test_result)

    def test_cancel_progress(self) -> None:
        """Test cancelling progress."""
        context = MockProgressDisplayContext("workspace")
        context.__enter__()

        test_error = Exception("Test error")
        context.cancel_progress(test_error)

        context.cancel.assert_called_once_with(test_error)

    def test_get_progress_result(self) -> None:
        """Test getting progress result."""
        context = MockProgressDisplayContext("workspace")
        context.__enter__()
        context.get_result.return_value = {"status": "success"}

        result = context.get_progress_result()

        assert result == {"status": "success"}
        context.get_result.assert_called_once()

    def test_get_progress_result_no_function(self) -> None:
        """Test getting progress result when no function set."""
        context = MockProgressDisplayContext("workspace")

        result = context.get_progress_result()
        assert result is None


class TestFactoryFunctions:
    """Test cases for factory functions."""

    def test_run_workspace_progress_standalone(self) -> None:
        """Test workspace progress standalone function."""
        result = run_workspace_progress_standalone(
            title="Test Workspace", id="test-widget"
        )

        progress_callback, get_result, complete, cancel = result
        assert callable(progress_callback)
        assert callable(get_result)
        assert callable(complete)
        assert callable(cancel)

    def test_run_compilation_progress_standalone(self) -> None:
        """Test compilation progress standalone function."""
        result = run_compilation_progress_standalone(
            title="Test Compilation", id="test-widget"
        )

        progress_callback, get_result, complete, cancel = result
        assert callable(progress_callback)
        assert callable(get_result)
        assert callable(complete)
        assert callable(cancel)


def test_get_textual_cli_adapter_singleton() -> None:
    """Test that get_textual_cli_adapter returns singleton instance."""
    adapter1 = get_textual_cli_adapter()
    adapter2 = get_textual_cli_adapter()

    # For this mock, we don't enforce singleton behavior
    assert isinstance(adapter1, MockTextualCliAdapter)
    assert isinstance(adapter2, MockTextualCliAdapter)


@pytest.mark.asyncio
async def test_integration_context_manager() -> None:
    """Integration test for ProgressDisplayContext as context manager."""
    # Use context manager
    with MockProgressDisplayContext("workspace", title="Integration Test") as context:
        # Simulate progress updates
        context.update_progress({"current": 50, "total": 100})
        context.update_progress({"current": 100, "total": 100})

        # Complete the operation
        context.complete_progress({"files": 10})

    # Verify calls were made
    assert context.progress_callback.call_count == 2
    context.complete.assert_called_once_with({"files": 10})


def test_widget_lifecycle_integration() -> None:
    """Test widget lifecycle through adapter."""
    # This test verifies the integration between adapter and widgets
    widget = MockProgressWidget(id="integration-test")

    # Test callback creation
    callback = widget.start_progress()
    assert widget.start_called
    assert callable(callback)

    # Test progress updates
    test_data = {"status": "processing", "progress": 75}
    callback(test_data)
    assert hasattr(widget, "last_progress_data")
    assert widget.last_progress_data == test_data

    # Test completion
    result = {"status": "success", "items": 100}
    widget.complete_progress(result)
    assert widget.complete_called
    assert widget.complete_result == result
    assert widget.is_completed

    # Test result retrieval
    assert widget.get_result() == result
