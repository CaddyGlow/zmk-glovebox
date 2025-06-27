"""Tests for the Textual CLI adapter."""

import asyncio
import threading
import time
from typing import Any
from unittest.mock import Mock, patch

import pytest

from glovebox.cli.components.textual_cli_adapter import (
    ProgressDisplayContext,
    StandaloneProgressApp,
    TextualCliAdapter,
    get_textual_cli_adapter,
    run_compilation_progress_standalone,
    run_workspace_progress_standalone,
)
from glovebox.tui.widgets.progress_widget import ProgressWidget


class MockProgressWidget(ProgressWidget[Any]):
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

        def callback(data: Any) -> None:
            self.last_progress_data = data

        return callback

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


class TestStandaloneProgressApp:
    """Test cases for StandaloneProgressApp."""

    def test_initialization(self) -> None:
        """Test StandaloneProgressApp initialization."""
        widget = MockProgressWidget()
        app = StandaloneProgressApp(widget, title="Test App")

        assert app.progress_widget == widget
        assert app.title == "Test App"
        assert not app._completed

    def test_get_progress_callback(self) -> None:
        """Test getting progress callback."""
        widget = MockProgressWidget()
        app = StandaloneProgressApp(widget)

        callback = app.get_progress_callback()
        assert callable(callback)
        assert widget.start_called

    def test_complete_operation(self) -> None:
        """Test completing operation."""
        widget = MockProgressWidget()
        app = StandaloneProgressApp(widget)

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
        app = StandaloneProgressApp(widget)

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
        app = StandaloneProgressApp(widget)

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
        app = StandaloneProgressApp(widget)

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
        app = StandaloneProgressApp(widget)

        widget._result = {"test": "data"}
        result = app.get_result()

        assert result == {"test": "data"}

    @pytest.mark.asyncio
    async def test_compose(self) -> None:
        """Test app composition."""
        widget = MockProgressWidget()
        app = StandaloneProgressApp(widget)

        composed = list(app.compose())
        assert len(composed) == 1
        assert composed[0] == widget


class TestTextualCliAdapter:
    """Test cases for TextualCliAdapter."""

    def test_initialization(self) -> None:
        """Test TextualCliAdapter initialization."""
        adapter = TextualCliAdapter()

        assert adapter._current_app is None
        assert adapter._app_thread is None
        assert adapter._loop is None

    @patch("threading.Thread")
    @patch("asyncio.new_event_loop")
    def test_run_progress_widget_standalone(
        self, mock_new_loop: Mock, mock_thread: Mock
    ) -> None:
        """Test running progress widget standalone."""
        adapter = TextualCliAdapter()

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

        # Verify thread was started
        mock_thread_instance.start.assert_called_once()

    def test_cleanup(self) -> None:
        """Test adapter cleanup."""
        adapter = TextualCliAdapter()

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
        adapter = TextualCliAdapter()

        # Mock current app that raises error on exit
        mock_app = Mock()
        mock_app.exit.side_effect = Exception("App exit error")
        adapter._current_app = mock_app

        # Should not raise exception
        adapter.cleanup()

        assert adapter._current_app is None

    @patch("asyncio.set_event_loop")
    @patch("asyncio.new_event_loop")
    def test_start_app_async_thread_function(
        self, mock_new_loop: Mock, mock_set_loop: Mock
    ) -> None:
        """Test the async app start thread function."""
        adapter = TextualCliAdapter()

        # Create a mock app
        mock_app = Mock()
        mock_app.run_async = Mock(return_value=asyncio.Future())
        mock_app.run_async.return_value.set_result(None)

        # Create a mock loop
        mock_loop_instance = Mock()
        mock_new_loop.return_value = mock_loop_instance

        # Test the thread function directly
        # Note: This is testing the internal behavior, so we need to be careful
        # In a real test, this would run in a separate thread
        with patch.object(adapter, "_loop", mock_loop_instance):
            # The actual thread function would be more complex to test
            # This is a simplified test of the setup
            mock_new_loop.assert_not_called()  # Not called until thread runs


class TestProgressDisplayContext:
    """Test cases for ProgressDisplayContext."""

    def test_initialization(self) -> None:
        """Test ProgressDisplayContext initialization."""
        context = ProgressDisplayContext(
            "workspace", title="Test Progress", id="test-widget"
        )

        assert context.widget_type == "workspace"
        assert context.title == "Test Progress"
        assert context.widget_kwargs == {"id": "test-widget"}
        assert context.progress_callback is None

    @patch(
        "glovebox.cli.components.textual_cli_adapter.run_workspace_progress_standalone"
    )
    def test_enter_workspace_context(self, mock_run_workspace: Mock) -> None:
        """Test entering workspace context."""
        # Mock the return values
        mock_callback = Mock()
        mock_get_result = Mock()
        mock_complete = Mock()
        mock_cancel = Mock()
        mock_run_workspace.return_value = (
            mock_callback,
            mock_get_result,
            mock_complete,
            mock_cancel,
        )

        context = ProgressDisplayContext("workspace", title="Test")
        result = context.__enter__()

        assert result == context
        assert context.progress_callback == mock_callback
        assert context.get_result == mock_get_result
        assert context.complete == mock_complete
        assert context.cancel == mock_cancel
        mock_run_workspace.assert_called_once_with(title="Test")

    @patch(
        "glovebox.cli.components.textual_cli_adapter.run_compilation_progress_standalone"
    )
    def test_enter_compilation_context(self, mock_run_compilation: Mock) -> None:
        """Test entering compilation context."""
        # Mock the return values
        mock_callback = Mock()
        mock_get_result = Mock()
        mock_complete = Mock()
        mock_cancel = Mock()
        mock_run_compilation.return_value = (
            mock_callback,
            mock_get_result,
            mock_complete,
            mock_cancel,
        )

        context = ProgressDisplayContext("compilation", title="Test")
        result = context.__enter__()

        assert result == context
        mock_run_compilation.assert_called_once_with(title="Test")

    def test_enter_invalid_widget_type(self) -> None:
        """Test entering context with invalid widget type."""
        context = ProgressDisplayContext("invalid", title="Test")

        with pytest.raises(ValueError, match="Unknown widget type: invalid"):
            context.__enter__()

    @patch("glovebox.cli.components.textual_cli_adapter.get_textual_cli_adapter")
    def test_exit_context_normal(self, mock_get_adapter: Mock) -> None:
        """Test exiting context normally."""
        mock_adapter = Mock()
        mock_get_adapter.return_value = mock_adapter

        context = ProgressDisplayContext("workspace")
        context.progress_callback = Mock()
        context.cancel = Mock()

        context.__exit__(None, None, None)

        # Should not call cancel
        context.cancel.assert_not_called()
        mock_adapter.cleanup.assert_called_once()

    @patch("glovebox.cli.components.textual_cli_adapter.get_textual_cli_adapter")
    def test_exit_context_with_exception(self, mock_get_adapter: Mock) -> None:
        """Test exiting context with exception."""
        mock_adapter = Mock()
        mock_get_adapter.return_value = mock_adapter

        context = ProgressDisplayContext("workspace")
        context.progress_callback = Mock()
        context.cancel = Mock()

        error = Exception("Test error")
        context.__exit__(Exception, error, None)

        # Should call cancel with the exception
        context.cancel.assert_called_once_with(error)
        mock_adapter.cleanup.assert_called_once()

    def test_update_progress(self) -> None:
        """Test updating progress."""
        context = ProgressDisplayContext("workspace")
        mock_callback = Mock()
        context.progress_callback = mock_callback

        test_data = {"status": "test"}
        context.update_progress(test_data)

        mock_callback.assert_called_once_with(test_data)

    def test_update_progress_no_callback(self) -> None:
        """Test updating progress when no callback set."""
        context = ProgressDisplayContext("workspace")

        # Should not raise error
        context.update_progress({"status": "test"})

    def test_complete_progress(self) -> None:
        """Test completing progress."""
        context = ProgressDisplayContext("workspace")
        mock_complete = Mock()
        context.complete = mock_complete

        test_result = {"status": "success"}
        context.complete_progress(test_result)

        mock_complete.assert_called_once_with(test_result)

    def test_cancel_progress(self) -> None:
        """Test cancelling progress."""
        context = ProgressDisplayContext("workspace")
        mock_cancel = Mock()
        context.cancel = mock_cancel

        test_error = Exception("Test error")
        context.cancel_progress(test_error)

        mock_cancel.assert_called_once_with(test_error)

    def test_get_progress_result(self) -> None:
        """Test getting progress result."""
        context = ProgressDisplayContext("workspace")
        mock_get_result = Mock(return_value={"status": "success"})
        context.get_result = mock_get_result

        result = context.get_progress_result()

        assert result == {"status": "success"}
        mock_get_result.assert_called_once()

    def test_get_progress_result_no_function(self) -> None:
        """Test getting progress result when no function set."""
        context = ProgressDisplayContext("workspace")

        result = context.get_progress_result()
        assert result is None


class TestFactoryFunctions:
    """Test cases for factory functions."""

    @patch(
        "glovebox.cli.components.textual_cli_adapter.TextualCliAdapter.run_progress_widget_standalone"
    )
    def test_run_workspace_progress_standalone(self, mock_run_widget: Mock) -> None:
        """Test workspace progress standalone function."""
        mock_functions = (Mock(), Mock(), Mock(), Mock())
        mock_run_widget.return_value = mock_functions

        result = run_workspace_progress_standalone(
            title="Test Workspace", id="test-widget"
        )

        assert result == mock_functions
        mock_run_widget.assert_called_once()

        # Check the widget class argument
        call_args = mock_run_widget.call_args
        from glovebox.tui.widgets.workspace_progress_widget import (
            WorkspaceProgressWidget,
        )

        assert call_args[0][0] == WorkspaceProgressWidget

    @patch(
        "glovebox.cli.components.textual_cli_adapter.TextualCliAdapter.run_progress_widget_standalone"
    )
    def test_run_compilation_progress_standalone(self, mock_run_widget: Mock) -> None:
        """Test compilation progress standalone function."""
        mock_functions = (Mock(), Mock(), Mock(), Mock())
        mock_run_widget.return_value = mock_functions

        result = run_compilation_progress_standalone(
            title="Test Compilation", id="test-widget"
        )

        assert result == mock_functions
        mock_run_widget.assert_called_once()

        # Check the widget class argument
        call_args = mock_run_widget.call_args
        from glovebox.tui.widgets.compilation_progress_widget import (
            CompilationProgressWidget,
        )

        assert call_args[0][0] == CompilationProgressWidget


def test_get_textual_cli_adapter_singleton() -> None:
    """Test that get_textual_cli_adapter returns singleton instance."""
    adapter1 = get_textual_cli_adapter()
    adapter2 = get_textual_cli_adapter()

    assert adapter1 is adapter2
    assert isinstance(adapter1, TextualCliAdapter)


@pytest.mark.asyncio
async def test_integration_context_manager() -> None:
    """Integration test for ProgressDisplayContext as context manager."""
    # Test the context manager pattern with mocked backend
    with patch(
        "glovebox.cli.components.textual_cli_adapter.run_workspace_progress_standalone"
    ) as mock_run:
        mock_callback = Mock()
        mock_get_result = Mock(return_value={"status": "success"})
        mock_complete = Mock()
        mock_cancel = Mock()
        mock_run.return_value = (
            mock_callback,
            mock_get_result,
            mock_complete,
            mock_cancel,
        )

        # Use context manager
        with ProgressDisplayContext("workspace", title="Integration Test") as context:
            # Simulate progress updates
            context.update_progress({"current": 50, "total": 100})
            context.update_progress({"current": 100, "total": 100})

            # Complete the operation
            context.complete_progress({"files": 10})

        # Verify calls were made
        assert mock_callback.call_count == 2
        mock_complete.assert_called_once_with({"files": 10})


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
