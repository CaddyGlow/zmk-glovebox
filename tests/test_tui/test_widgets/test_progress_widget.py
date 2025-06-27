"""Tests for the base ProgressWidget component."""

import asyncio
import time
from typing import Any
from unittest.mock import Mock, patch

import pytest
from textual.app import App
from textual.widgets import ProgressBar, Static

from glovebox.tui.widgets.progress_widget import (
    ProgressWidget,
    StandaloneProgressApp,
)


class MockProgressData:
    """Mock progress data for testing."""

    def __init__(
        self,
        status: str = "Test status",
        current: int = 50,
        total: int = 100,
        description: str = "Test description",
    ) -> None:
        self.status = status
        self.current = current
        self.total = total
        self.description = description

    def get_status_text(self) -> str:
        """Get the current status text to display."""
        return self.status

    def get_progress_info(self) -> tuple[int, int, str]:
        """Get progress information as (current, total, description)."""
        return self.current, self.total, self.description


class TestProgressWidget:
    """Test cases for ProgressWidget."""

    def test_initialization(self) -> None:
        """Test ProgressWidget initialization."""
        widget = ProgressWidget[Any]()

        assert widget.progress_current == 0
        assert widget.progress_total == 100
        assert widget.status_text == "Initializing..."
        assert widget.description == "Starting..."
        assert not widget.is_paused
        assert not widget.is_cancelled
        assert not widget.is_completed

    def test_progress_callback_creation(self) -> None:
        """Test creating a progress callback."""
        widget = ProgressWidget[MockProgressData]()
        callback = widget.start_progress()

        assert callable(callback)
        assert not widget.is_completed
        assert not widget.is_cancelled

    def test_progress_data_update(self) -> None:
        """Test updating progress with mock data."""
        widget = ProgressWidget[MockProgressData]()

        # Create mock progress data
        progress_data = MockProgressData(
            status="Processing...",
            current=25,
            total=100,
            description="Processing files",
        )

        # Update widget with progress data
        widget._update_from_progress_data(progress_data)

        assert widget.status_text == "Processing..."
        assert widget.progress_current == 25
        assert widget.progress_total == 100
        assert widget.description == "Processing files"

    def test_complete_progress(self) -> None:
        """Test completing progress operation."""
        widget = ProgressWidget[Any]()
        result = {"status": "success", "files": 10}

        widget.complete_progress(result)

        assert widget.is_completed
        assert widget.get_result() == result
        assert widget.progress_current == widget.progress_total
        assert "Completed" in widget.status_text

    def test_cancel_progress(self) -> None:
        """Test cancelling progress operation."""
        widget = ProgressWidget[Any]()
        error = Exception("Operation failed")

        widget.cancel_progress(error)

        assert widget.is_cancelled
        assert widget.get_error() == error
        assert "Cancelled" in widget.status_text

    def test_cancel_progress_without_error(self) -> None:
        """Test cancelling progress without specific error."""
        widget = ProgressWidget[Any]()

        widget.cancel_progress()

        assert widget.is_cancelled
        assert widget.get_error() is None
        assert "Cancelled by user" in widget.status_text

    def test_progress_callback_with_cancelled_state(self) -> None:
        """Test that progress callback respects cancelled state."""
        widget = ProgressWidget[MockProgressData]()
        callback = widget.start_progress()

        # Cancel the widget
        widget.cancel_progress()

        # Try to update progress (should be ignored)
        progress_data = MockProgressData(status="Should be ignored")
        callback(progress_data)

        # Status should still show cancelled
        assert widget.is_cancelled
        assert "Cancelled" in widget.status_text

    def test_progress_callback_error_handling(self) -> None:
        """Test error handling in progress callback."""
        widget = ProgressWidget[Any]()
        callback = widget.start_progress()

        # Create invalid progress data that will cause an error
        invalid_data = "not an object with methods"

        # This should not raise an exception
        callback(invalid_data)

        # Widget should handle the error gracefully
        assert (
            "Error" in widget.status_text
            or widget.status_text == "not an object with methods"
        )

    def test_reactive_properties_update_ui(self) -> None:
        """Test that reactive properties trigger UI updates."""
        widget = ProgressWidget[Any]()

        # Mock the UI components
        widget.status_widget = Mock()
        widget.description_widget = Mock()
        widget.progress_bar = Mock()

        # Update reactive properties
        widget.status_text = "New status"
        widget.description = "New description"
        widget.progress_current = 75
        widget.progress_total = 150

        # Verify watchers are called (simulated by manual calls)
        widget.watch_status_text("New status")
        widget.watch_description("New description")
        widget.watch_progress_current(75)
        widget.watch_progress_total(150)

        # Verify UI components are updated
        widget.status_widget.update.assert_called_with("New status")
        widget.description_widget.update.assert_called_with("New description")
        widget.progress_bar.update.assert_called_with(progress=75)
        widget.progress_bar.update.assert_called_with(total=150)

    def test_keyboard_actions(self) -> None:
        """Test keyboard action handlers."""
        widget = ProgressWidget[Any]()

        # Test cancel action
        widget.action_cancel()
        assert widget.is_cancelled

        # Reset widget
        widget = ProgressWidget[Any]()

        # Test pause action
        widget.action_toggle_pause()
        assert widget.is_paused
        assert "Paused" in widget.status_text

        # Test resume action
        widget.action_toggle_pause()
        assert not widget.is_paused
        assert "Resumed" in widget.status_text

    def test_action_quit_with_app(self) -> None:
        """Test quit action when widget has an app."""
        widget = ProgressWidget[Any]()

        # Mock app with exit method
        mock_app = Mock()
        widget.app = mock_app

        widget.action_quit()

        assert widget.is_cancelled
        mock_app.exit.assert_called_once()

    def test_compose_creates_required_widgets(self) -> None:
        """Test that compose creates the required child widgets."""
        widget = ProgressWidget[Any]()

        # Get the composed widgets
        composed = list(widget.compose())

        # Should have status, progress bar, and description
        assert len(composed) == 3
        assert isinstance(composed[0], Static)  # status
        assert isinstance(composed[1], ProgressBar)  # progress bar
        assert isinstance(composed[2], Static)  # description

    def test_timing_calculation(self) -> None:
        """Test timing calculations in widget lifecycle."""
        widget = ProgressWidget[Any]()

        start_time = time.time()
        widget.start_progress()

        # Simulate some time passing
        time.sleep(0.1)

        widget.complete_progress()

        # Check that timing was calculated
        assert "Completed in" in widget.status_text

        # Time should be reasonable (less than 1 second for this test)
        completion_time = time.time() - start_time
        assert completion_time < 1.0


class TestStandaloneProgressApp:
    """Test cases for StandaloneProgressApp."""

    def test_initialization(self) -> None:
        """Test StandaloneProgressApp initialization."""
        widget = ProgressWidget[Any]()
        app = StandaloneProgressApp(widget, title="Test Progress")

        assert app.progress_widget == widget
        assert app.title == "Test Progress"
        assert not app._completed

    def test_get_progress_callback(self) -> None:
        """Test getting progress callback from app."""
        widget = ProgressWidget[MockProgressData]()
        app = StandaloneProgressApp(widget)

        callback = app.get_progress_callback()
        assert callable(callback)

        # Test callback updates widget
        progress_data = MockProgressData(status="Test update")
        callback(progress_data)

        assert widget.status_text == "Test update"

    def test_complete_operation(self) -> None:
        """Test completing operation."""
        widget = ProgressWidget[Any]()
        app = StandaloneProgressApp(widget)

        result = {"test": "data"}
        app.complete_operation(result)

        assert app._completed
        assert widget.is_completed
        assert widget.get_result() == result

    def test_cancel_operation(self) -> None:
        """Test cancelling operation."""
        widget = ProgressWidget[Any]()
        app = StandaloneProgressApp(widget)

        error = Exception("Test error")
        app.cancel_operation(error)

        assert app._completed
        assert widget.is_cancelled
        assert widget.get_error() == error

    def test_complete_operation_idempotent(self) -> None:
        """Test that completing operation multiple times is safe."""
        widget = ProgressWidget[Any]()
        app = StandaloneProgressApp(widget)

        app.complete_operation("first")
        first_status = widget.status_text

        app.complete_operation("second")
        second_status = widget.status_text

        # Should not change after first completion
        assert first_status == second_status
        assert widget.get_result() == "first"

    def test_cancel_operation_idempotent(self) -> None:
        """Test that cancelling operation multiple times is safe."""
        widget = ProgressWidget[Any]()
        app = StandaloneProgressApp(widget)

        first_error = Exception("first")
        second_error = Exception("second")

        app.cancel_operation(first_error)
        first_status = widget.status_text

        app.cancel_operation(second_error)
        second_status = widget.status_text

        # Should not change after first cancellation
        assert first_status == second_status
        assert widget.get_error() == first_error

    @pytest.mark.asyncio
    async def test_app_compose(self) -> None:
        """Test app composition includes the widget."""
        widget = ProgressWidget[Any]()
        app = StandaloneProgressApp(widget)

        composed = list(app.compose())
        assert len(composed) == 1
        assert composed[0] == widget

    @pytest.mark.asyncio
    async def test_app_timer_functionality(self) -> None:
        """Test that app sets timers for completion and cancellation."""
        widget = ProgressWidget[Any]()
        app = StandaloneProgressApp(widget)

        # Mock the set_timer method
        with patch.object(app, "set_timer") as mock_set_timer:
            app.complete_operation("test")
            mock_set_timer.assert_called_once_with(1.5, app.exit)

        # Reset mock
        mock_set_timer.reset_mock()

        # Test cancellation timer
        app._completed = False  # Reset completion state
        with patch.object(app, "set_timer") as mock_set_timer:
            app.cancel_operation()
            mock_set_timer.assert_called_once_with(1.0, app.exit)


@pytest.mark.asyncio
async def test_integration_with_real_textual_app() -> None:
    """Integration test with actual Textual app (if available)."""
    # This test verifies that our widgets work with the real Textual framework
    widget = ProgressWidget[MockProgressData]()
    app = StandaloneProgressApp(widget, title="Integration Test")

    # Start the widget
    callback = widget.start_progress()

    # Simulate progress updates
    progress_data = MockProgressData(
        status="Integration test running",
        current=33,
        total=100,
        description="Testing integration",
    )
    callback(progress_data)

    # Verify widget state
    assert widget.status_text == "Integration test running"
    assert widget.progress_current == 33
    assert widget.progress_total == 100
    assert widget.description == "Testing integration"

    # Complete the operation
    app.complete_operation({"status": "success"})

    assert widget.is_completed
    assert widget.get_result() == {"status": "success"}
