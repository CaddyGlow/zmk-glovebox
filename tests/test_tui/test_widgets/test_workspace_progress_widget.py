"""Tests for the WorkspaceProgressWidget component."""

import time
from typing import Any
from unittest.mock import Mock

import pytest

from glovebox.tui.widgets.workspace_progress_widget import (
    WorkspaceProgressWidget,
    create_workspace_progress_widget,
)


class MockWorkspaceProgressData:
    """Mock workspace progress data for testing."""

    def __init__(
        self,
        current_file: str = "test_file.txt",
        component_name: str = "zmk",
        files_processed: int = 5,
        total_files: int = 10,
        bytes_copied: int = 1024,
        total_bytes: int = 2048,
    ) -> None:
        self.current_file = current_file
        self.component_name = component_name
        self.files_processed = files_processed
        self.total_files = total_files
        self.bytes_copied = bytes_copied
        self.total_bytes = total_bytes


class TestWorkspaceProgressWidget:
    """Test cases for WorkspaceProgressWidget."""

    def test_initialization(self) -> None:
        """Test WorkspaceProgressWidget initialization."""
        widget = WorkspaceProgressWidget()

        # Check base class initialization
        assert widget.progress_current == 0
        assert widget.progress_total == 100
        assert widget.status_text == "Initializing..."
        assert widget.description == "Starting..."

        # Check workspace-specific initialization
        assert widget.current_file == ""
        assert widget.component_name == ""
        assert widget.files_processed == 0
        assert widget.total_files == 0
        assert widget.bytes_copied == 0
        assert widget.total_bytes == 0
        assert widget.transfer_speed == 0.0
        assert widget.last_update_time == 0.0

    def test_workspace_progress_data_update(self) -> None:
        """Test updating widget with workspace progress data."""
        widget = WorkspaceProgressWidget()

        progress_data = MockWorkspaceProgressData(
            current_file="src/main.c",
            component_name="zmk",
            files_processed=3,
            total_files=10,
            bytes_copied=512,
            total_bytes=1024,
        )

        widget._update_from_progress_data(progress_data)

        assert widget.current_file == "src/main.c"
        assert widget.component_name == "zmk"
        assert widget.files_processed == 3
        assert widget.total_files == 10
        assert widget.bytes_copied == 512
        assert widget.total_bytes == 1024
        assert widget.progress_current == 512  # Uses bytes as primary metric
        assert widget.progress_total == 1024
        assert "Copying: main.c" in widget.status_text

    def test_file_based_progress_fallback(self) -> None:
        """Test fallback to file-based progress when bytes not available."""
        widget = WorkspaceProgressWidget()

        # Create progress data without bytes information
        progress_data = MockWorkspaceProgressData(
            current_file="test.txt",
            files_processed=5,
            total_files=20,
            bytes_copied=0,
            total_bytes=0,
        )

        widget._update_from_progress_data(progress_data)

        # Should fall back to file count
        assert widget.progress_current == 5
        assert widget.progress_total == 20
        assert widget.description == "Copying files"

    def test_transfer_speed_calculation(self) -> None:
        """Test transfer speed calculation."""
        widget = WorkspaceProgressWidget()

        # First update
        first_data = MockWorkspaceProgressData(
            current_file="file1.txt",
            bytes_copied=0,
            total_bytes=1024,
        )
        widget._update_from_progress_data(first_data)

        # Simulate time passing
        time.sleep(0.1)

        # Second update with more bytes
        second_data = MockWorkspaceProgressData(
            current_file="file2.txt",
            bytes_copied=512,
            total_bytes=1024,
        )
        widget._update_from_progress_data(second_data)

        # Transfer speed should be calculated
        assert widget.transfer_speed > 0

    def test_current_file_display_truncation(self) -> None:
        """Test that long file names are properly truncated."""
        widget = WorkspaceProgressWidget()

        # Mock the UI components
        widget.current_file_widget = Mock()

        # Test with a very long file name
        long_filename = "very_long_filename_that_exceeds_fifty_characters_total.txt"
        widget.current_file = long_filename
        widget._update_current_file_display()

        # Verify truncation occurred
        call_args = widget.current_file_widget.update.call_args[0][0]
        assert len(call_args) <= 50
        assert "..." in call_args

    def test_current_file_display_normal(self) -> None:
        """Test normal file name display."""
        widget = WorkspaceProgressWidget()

        # Mock the UI components
        widget.current_file_widget = Mock()

        # Test with normal file name
        widget.current_file = "src/main.c"
        widget._update_current_file_display()

        # Should display just the filename
        widget.current_file_widget.update.assert_called_with("main.c")

    def test_file_stats_update(self) -> None:
        """Test file statistics display update."""
        widget = WorkspaceProgressWidget()

        # Mock the UI components
        widget.file_stats_widget = Mock()

        widget.files_processed = 7
        widget.total_files = 15
        widget._update_file_stats()

        widget.file_stats_widget.update.assert_called_with("Files: 7/15")

    def test_speed_stats_update(self) -> None:
        """Test speed statistics display update."""
        widget = WorkspaceProgressWidget()

        # Mock the UI components
        widget.speed_stats_widget = Mock()

        widget.bytes_copied = 1536  # 1.5 KB
        widget.total_bytes = 2048  # 2 KB
        widget.transfer_speed = 5.0  # 5 MB/s
        widget._update_speed_stats()

        call_args = widget.speed_stats_widget.update.call_args[0][0]
        assert "1.5 KB" in call_args
        assert "2.0 KB" in call_args
        assert "5.0 MB/s" in call_args

    def test_format_bytes_helper(self) -> None:
        """Test the internal bytes formatting helper."""
        widget = WorkspaceProgressWidget()

        # Mock the UI components
        widget.speed_stats_widget = Mock()

        # Test various byte sizes
        test_cases = [
            (512, "512.0 B"),
            (1536, "1.5 KB"),
            (1048576, "1.0 MB"),
            (2147483648, "2.0 GB"),
        ]

        for bytes_val, expected in test_cases:
            widget.bytes_copied = bytes_val
            widget.total_bytes = bytes_val
            widget._update_speed_stats()

            call_args = widget.speed_stats_widget.update.call_args[0][0]
            assert expected in call_args

    def test_component_info_display(self) -> None:
        """Test component information display."""
        widget = WorkspaceProgressWidget()

        # Mock the UI components
        widget.component_info_widget = Mock()

        progress_data = MockWorkspaceProgressData(
            current_file="config.h",
            component_name="zephyr",
        )

        widget._update_from_progress_data(progress_data)

        # Component info should be displayed
        widget.component_info_widget.update.assert_called_with("(zephyr)")

    def test_component_info_empty(self) -> None:
        """Test component information display when empty."""
        widget = WorkspaceProgressWidget()

        # Mock the UI components
        widget.component_info_widget = Mock()

        progress_data = MockWorkspaceProgressData(
            current_file="config.h",
            component_name="",  # Empty component name
        )

        widget._update_from_progress_data(progress_data)

        # Component info should be empty
        widget.component_info_widget.update.assert_called_with("")

    def test_progress_info_update_bytes(self) -> None:
        """Test progress info update with byte-based progress."""
        widget = WorkspaceProgressWidget()

        # Mock the UI components
        widget.progress_info_widget = Mock()

        widget.bytes_copied = 750
        widget.total_bytes = 1000
        widget._update_progress_info()

        call_args = widget.progress_info_widget.update.call_args[0][0]
        assert "Progress: 75.0%" in call_args

    def test_progress_info_update_files(self) -> None:
        """Test progress info update with file-based progress."""
        widget = WorkspaceProgressWidget()

        # Mock the UI components
        widget.progress_info_widget = Mock()

        widget.files_processed = 6
        widget.total_files = 8
        widget.bytes_copied = 0
        widget.total_bytes = 0
        widget._update_progress_info()

        call_args = widget.progress_info_widget.update.call_args[0][0]
        assert "Progress: 75.0%" in call_args

    def test_complete_progress_workspace_specific(self) -> None:
        """Test workspace-specific completion display."""
        widget = WorkspaceProgressWidget()

        # Mock the UI components
        widget.file_stats_widget = Mock()
        widget.speed_stats_widget = Mock()
        widget.current_file_widget = Mock()
        widget.component_info_widget = Mock()

        # Set up some data
        widget.total_files = 10
        widget.total_bytes = 2048
        widget.start_time = time.time() - 1.0  # 1 second ago

        widget.complete_progress({"status": "success"})

        # Verify workspace-specific completion updates
        widget.file_stats_widget.update.assert_called_with("✅ Completed: 10 files")
        widget.current_file_widget.update.assert_called_with("Operation completed")
        widget.component_info_widget.update.assert_called_with("")

        # Speed stats should show completion with average speed
        call_args = widget.speed_stats_widget.update.call_args[0][0]
        assert "✅" in call_args
        assert "MB/s avg" in call_args

    def test_fallback_progress_data(self) -> None:
        """Test handling of non-workspace progress data."""
        widget = WorkspaceProgressWidget()

        # Test with simple string data (should fall back to base class)
        simple_data = "Simple progress update"
        widget._update_from_progress_data(simple_data)

        assert widget.status_text == "Simple progress update"

    def test_reactive_properties_trigger_updates(self) -> None:
        """Test that reactive properties trigger workspace-specific updates."""
        widget = WorkspaceProgressWidget()

        # Mock the UI components and parent methods
        widget.progress_info_widget = Mock()
        widget.status_widget = Mock()
        widget.progress_bar = Mock()

        # Test progress current update
        widget.watch_progress_current(50)

        # Should call parent watcher and progress info update
        widget.progress_bar.update.assert_called_with(progress=50)

    def test_no_current_file_handling(self) -> None:
        """Test handling when no current file is provided."""
        widget = WorkspaceProgressWidget()

        # Mock UI components
        widget.current_file_widget = Mock()

        # Test with empty current file
        widget.current_file = ""
        widget._update_current_file_display()

        widget.current_file_widget.update.assert_called_with("")

    def test_zero_total_files_handling(self) -> None:
        """Test handling when total files is zero."""
        widget = WorkspaceProgressWidget()

        # Mock UI components
        widget.file_stats_widget = Mock()

        widget.files_processed = 5
        widget.total_files = 0
        widget._update_file_stats()

        widget.file_stats_widget.update.assert_called_with("")

    def test_zero_total_bytes_handling(self) -> None:
        """Test handling when total bytes is zero."""
        widget = WorkspaceProgressWidget()

        # Mock UI components
        widget.speed_stats_widget = Mock()

        widget.bytes_copied = 100
        widget.total_bytes = 0
        widget._update_speed_stats()

        widget.speed_stats_widget.update.assert_called_with("")


def test_create_workspace_progress_widget_factory() -> None:
    """Test the factory function for creating workspace progress widgets."""
    widget = create_workspace_progress_widget(id="test-widget")

    assert isinstance(widget, WorkspaceProgressWidget)
    assert widget.id == "test-widget"


def test_workspace_widget_inheritance() -> None:
    """Test that WorkspaceProgressWidget properly inherits from ProgressWidget."""
    widget = WorkspaceProgressWidget()

    # Should have base ProgressWidget functionality
    assert hasattr(widget, "start_progress")
    assert hasattr(widget, "complete_progress")
    assert hasattr(widget, "cancel_progress")
    assert hasattr(widget, "get_result")
    assert hasattr(widget, "get_error")

    # Should have workspace-specific functionality
    assert hasattr(widget, "_update_current_file_display")
    assert hasattr(widget, "_update_file_stats")
    assert hasattr(widget, "_update_speed_stats")


@pytest.mark.asyncio
async def test_workspace_widget_compose() -> None:
    """Test that WorkspaceProgressWidget composes with proper layout."""
    widget = WorkspaceProgressWidget()

    composed = list(widget.compose())

    # Should have multiple components for workspace display
    assert len(composed) > 3  # More than base ProgressWidget

    # Verify we have the expected structure (Vertical container with children)
    from textual.containers import Vertical

    assert len([w for w in composed if isinstance(w, Vertical)]) == 1
