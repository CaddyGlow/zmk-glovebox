"""Tests for the CompilationProgressWidget component."""

import time
from typing import Any
from unittest.mock import Mock

import pytest

from glovebox.tui.widgets.compilation_progress_widget import (
    CompilationProgressWidget,
    create_compilation_progress_widget,
)


class MockCompilationProgressData:
    """Mock compilation progress data for testing."""

    def __init__(
        self,
        compilation_phase: str = "initialization",
        current_repository: str = "zmkfirmware/zmk",
        current_board: str = "nice_nano_v2",
        repositories_downloaded: int = 1,
        total_repositories: int = 5,
        boards_completed: int = 0,
        total_boards: int = 2,
        bytes_downloaded: int = 1024,
        total_bytes: int = 2048,
        overall_progress_percent: int = 50,
    ) -> None:
        self.compilation_phase = compilation_phase
        self.current_repository = current_repository
        self.current_board = current_board
        self.repositories_downloaded = repositories_downloaded
        self.total_repositories = total_repositories
        self.boards_completed = boards_completed
        self.total_boards = total_boards
        self.bytes_downloaded = bytes_downloaded
        self.total_bytes = total_bytes
        self.overall_progress_percent = overall_progress_percent


class TestCompilationProgressWidget:
    """Test cases for CompilationProgressWidget."""

    def test_initialization(self) -> None:
        """Test CompilationProgressWidget initialization."""
        widget = CompilationProgressWidget()

        # Check base class initialization
        assert widget.progress_current == 0
        assert widget.progress_total == 100
        assert widget.status_text == "Initializing..."
        assert widget.description == "Starting..."

        # Check compilation-specific initialization
        assert widget.compilation_phase == "initialization"
        assert widget.current_repository == ""
        assert widget.current_board == ""
        assert widget.repositories_downloaded == 0
        assert widget.total_repositories == 0
        assert widget.boards_completed == 0
        assert widget.total_boards == 0
        assert widget.bytes_downloaded == 0
        assert widget.total_bytes == 0
        assert widget.overall_progress_percent == 0

    def test_initialization_phase_handling(self) -> None:
        """Test handling of initialization phase."""
        widget = CompilationProgressWidget()

        # Mock UI components
        widget.phase_icon = Mock()
        widget.phase_info_widget = Mock()

        progress_data = MockCompilationProgressData(
            compilation_phase="initialization",
            current_repository="zmkfirmware/zmk",
            repositories_downloaded=2,
            total_repositories=5,
        )

        widget._update_from_progress_data(progress_data)

        assert widget.compilation_phase == "initialization"
        assert widget.current_repository == "zmkfirmware/zmk"
        assert widget.repositories_downloaded == 2
        assert widget.total_repositories == 5
        assert widget.progress_current == 2
        assert widget.progress_total == 5
        assert "Setup: zmkfirmware/zmk" in widget.status_text
        widget.phase_icon.update.assert_called_with("⚙️")
        widget.phase_info_widget.update.assert_called_with("(initialization)")

    def test_cache_restoration_phase_handling(self) -> None:
        """Test handling of cache restoration phase."""
        widget = CompilationProgressWidget()

        # Mock UI components
        widget.phase_icon = Mock()
        widget.phase_info_widget = Mock()

        progress_data = MockCompilationProgressData(
            compilation_phase="cache_restoration",
            current_repository="zmkfirmware/zmk",
            bytes_downloaded=1024,
            total_bytes=2048,
        )

        widget._update_from_progress_data(progress_data)

        assert widget.compilation_phase == "cache_restoration"
        assert widget.bytes_downloaded == 1024
        assert widget.total_bytes == 2048
        assert widget.progress_current == 1024
        assert widget.progress_total == 2048
        assert "Cache: zmkfirmware/zmk" in widget.status_text
        widget.phase_icon.update.assert_called_with("💾")
        widget.phase_info_widget.update.assert_called_with("(cache restoration)")

    def test_cache_restoration_fallback_to_repos(self) -> None:
        """Test cache restoration falls back to repo count when bytes unavailable."""
        widget = CompilationProgressWidget()

        # Mock UI components
        widget.phase_icon = Mock()
        widget.phase_info_widget = Mock()

        progress_data = MockCompilationProgressData(
            compilation_phase="cache_restoration",
            current_repository="zmkfirmware/zmk",
            repositories_downloaded=3,
            total_repositories=5,
            bytes_downloaded=0,
            total_bytes=0,  # No bytes data
        )

        widget._update_from_progress_data(progress_data)

        # Should fall back to repository progress
        assert widget.progress_current == 3
        assert widget.progress_total == 5

    def test_workspace_setup_phase_handling(self) -> None:
        """Test handling of workspace setup phase."""
        widget = CompilationProgressWidget()

        # Mock UI components
        widget.phase_icon = Mock()
        widget.phase_info_widget = Mock()

        progress_data = MockCompilationProgressData(
            compilation_phase="workspace_setup",
            current_repository="zmkfirmware/zmk",
            bytes_downloaded=512,
            total_bytes=1024,
        )

        widget._update_from_progress_data(progress_data)

        assert widget.compilation_phase == "workspace_setup"
        assert "Workspace: zmkfirmware/zmk" in widget.status_text
        widget.phase_icon.update.assert_called_with("🗂️")
        widget.phase_info_widget.update.assert_called_with("(workspace setup)")

    def test_workspace_setup_fallback_progress(self) -> None:
        """Test workspace setup with fallback progress when no bytes."""
        widget = CompilationProgressWidget()

        # Mock UI components
        widget.phase_icon = Mock()
        widget.phase_info_widget = Mock()

        progress_data = MockCompilationProgressData(
            compilation_phase="workspace_setup",
            current_repository="zmkfirmware/zmk",
            bytes_downloaded=0,
            total_bytes=0,  # No bytes data
        )

        widget._update_from_progress_data(progress_data)

        # Should use arbitrary progress
        assert widget.progress_current == 50
        assert widget.progress_total == 100

    def test_west_update_phase_handling(self) -> None:
        """Test handling of west update phase."""
        widget = CompilationProgressWidget()

        # Mock UI components
        widget.phase_icon = Mock()
        widget.phase_info_widget = Mock()

        progress_data = MockCompilationProgressData(
            compilation_phase="west_update",
            current_repository="zmkfirmware/zmk",
            repositories_downloaded=4,
            total_repositories=7,
        )

        widget._update_from_progress_data(progress_data)

        assert widget.compilation_phase == "west_update"
        assert "Downloading: zmkfirmware/zmk" in widget.status_text
        widget.phase_icon.update.assert_called_with("📦")
        widget.phase_info_widget.update.assert_called_with("(west update)")

    def test_building_phase_single_board(self) -> None:
        """Test handling of building phase with single board."""
        widget = CompilationProgressWidget()

        # Mock UI components
        widget.phase_icon = Mock()
        widget.phase_info_widget = Mock()
        widget.current_board_widget = Mock()

        progress_data = MockCompilationProgressData(
            compilation_phase="building",
            current_repository="zmkfirmware/zmk",
            overall_progress_percent=75,
            total_boards=1,  # Single board
        )

        widget._update_from_progress_data(progress_data)

        assert widget.compilation_phase == "building"
        assert widget.overall_progress_percent == 75
        assert widget.progress_current == 75
        assert widget.progress_total == 100
        assert "Building: zmkfirmware/zmk" in widget.status_text
        widget.phase_icon.update.assert_called_with("🔨")
        widget.phase_info_widget.update.assert_called_with("(building)")
        widget.current_board_widget.update.assert_called_with("")

    def test_building_phase_multi_board(self) -> None:
        """Test handling of building phase with multiple boards."""
        widget = CompilationProgressWidget()

        # Mock UI components
        widget.phase_icon = Mock()
        widget.phase_info_widget = Mock()
        widget.current_board_widget = Mock()

        progress_data = MockCompilationProgressData(
            compilation_phase="building",
            current_repository="zmkfirmware/zmk",
            current_board="nice_nano_v2",
            boards_completed=1,
            total_boards=3,
            overall_progress_percent=60,
        )

        widget._update_from_progress_data(progress_data)

        assert widget.compilation_phase == "building"
        assert widget.current_board == "nice_nano_v2"
        assert widget.boards_completed == 1
        assert widget.total_boards == 3
        assert "Building: nice_nano_v2 (2/3)" in widget.status_text
        widget.current_board_widget.update.assert_called_with("nice_nano_v2")

    def test_cache_saving_phase_handling(self) -> None:
        """Test handling of cache saving phase."""
        widget = CompilationProgressWidget()

        # Mock UI components
        widget.phase_icon = Mock()
        widget.phase_info_widget = Mock()

        progress_data = MockCompilationProgressData(
            compilation_phase="cache_saving",
            current_repository="zmkfirmware/zmk",
            overall_progress_percent=90,
        )

        widget._update_from_progress_data(progress_data)

        assert widget.compilation_phase == "cache_saving"
        assert "Cache: zmkfirmware/zmk" in widget.status_text
        widget.phase_icon.update.assert_called_with("💾")
        widget.phase_info_widget.update.assert_called_with("(cache saving)")

    def test_unknown_phase_handling(self) -> None:
        """Test handling of unknown compilation phases."""
        widget = CompilationProgressWidget()

        # Mock UI components
        widget.phase_icon = Mock()
        widget.phase_info_widget = Mock()

        progress_data = MockCompilationProgressData(
            compilation_phase="unknown_phase",
            current_repository="zmkfirmware/zmk",
        )

        widget._update_from_progress_data(progress_data)

        assert widget.compilation_phase == "unknown_phase"
        assert "zmkfirmware/zmk" in widget.status_text
        widget.phase_icon.update.assert_called_with("⚙️")
        widget.phase_info_widget.update.assert_called_with("(unknown_phase)")

    def test_repo_display_truncation(self) -> None:
        """Test that long repository names are properly truncated."""
        widget = CompilationProgressWidget()

        # Mock UI components
        widget.current_repo_widget = Mock()

        # Test with very long repository name
        long_repo = (
            "very_long_organization_name/very_long_repository_name_that_exceeds_limit"
        )
        widget.current_repository = long_repo
        widget._update_repo_display()

        # Verify truncation occurred
        call_args = widget.current_repo_widget.update.call_args[0][0]
        assert len(call_args) <= 40
        assert "..." in call_args

    def test_repo_display_normal(self) -> None:
        """Test normal repository name display."""
        widget = CompilationProgressWidget()

        # Mock UI components
        widget.current_repo_widget = Mock()

        widget.current_repository = "zmkfirmware/zmk"
        widget._update_repo_display()

        widget.current_repo_widget.update.assert_called_with("zmkfirmware/zmk")

    def test_repo_stats_update(self) -> None:
        """Test repository statistics display update."""
        widget = CompilationProgressWidget()

        # Mock UI components
        widget.repo_stats_widget = Mock()

        widget.repositories_downloaded = 3
        widget.total_repositories = 8
        widget._update_repo_stats()

        widget.repo_stats_widget.update.assert_called_with("Repos: 3/8")

    def test_download_stats_update(self) -> None:
        """Test download statistics display update."""
        widget = CompilationProgressWidget()

        # Mock UI components
        widget.download_stats_widget = Mock()

        widget.bytes_downloaded = 1536  # 1.5 KB
        widget.total_bytes = 2048  # 2 KB
        widget._update_download_stats()

        call_args = widget.download_stats_widget.update.call_args[0][0]
        assert "Downloaded: 1.5 KB/2.0 KB" in call_args

    def test_board_progress_update_multi_board(self) -> None:
        """Test board progress display with multiple boards."""
        widget = CompilationProgressWidget()

        # Mock UI components
        widget.board_progress_widget = Mock()

        widget.boards_completed = 2
        widget.total_boards = 5
        widget._update_board_progress()

        widget.board_progress_widget.update.assert_called_with("Board 3/5")

    def test_board_progress_update_single_board(self) -> None:
        """Test board progress display with single board."""
        widget = CompilationProgressWidget()

        # Mock UI components
        widget.board_progress_widget = Mock()

        widget.boards_completed = 0
        widget.total_boards = 1
        widget._update_board_progress()

        widget.board_progress_widget.update.assert_called_with("")

    def test_progress_info_update_multi_board(self) -> None:
        """Test progress info update with multi-board compilation."""
        widget = CompilationProgressWidget()

        # Mock UI components
        widget.progress_info_widget = Mock()

        widget.compilation_phase = "building"
        widget.boards_completed = 1
        widget.total_boards = 4
        widget.overall_progress_percent = 60
        widget._update_progress_info()

        call_args = widget.progress_info_widget.update.call_args[0][0]
        # Calculate expected: (1 + 0.6) / 4 * 100 = 40%
        assert "Overall: 40.0%" in call_args

    def test_progress_info_update_single_progress(self) -> None:
        """Test progress info update with single progress percentage."""
        widget = CompilationProgressWidget()

        # Mock UI components
        widget.progress_info_widget = Mock()

        widget.overall_progress_percent = 75
        widget.total_boards = 0
        widget._update_progress_info()

        call_args = widget.progress_info_widget.update.call_args[0][0]
        assert "Progress: 75.0%" in call_args

    def test_progress_info_update_repo_based(self) -> None:
        """Test progress info update with repository-based progress."""
        widget = CompilationProgressWidget()

        # Mock UI components
        widget.progress_info_widget = Mock()

        widget.repositories_downloaded = 6
        widget.total_repositories = 10
        widget.overall_progress_percent = 0
        widget.total_boards = 0
        widget._update_progress_info()

        call_args = widget.progress_info_widget.update.call_args[0][0]
        assert "Progress: 60.0%" in call_args

    def test_complete_progress_compilation_specific(self) -> None:
        """Test compilation-specific completion display."""
        widget = CompilationProgressWidget()

        # Mock UI components
        widget.phase_icon = Mock()
        widget.current_repo_widget = Mock()
        widget.phase_info_widget = Mock()
        widget.board_progress_widget = Mock()
        widget.repo_stats_widget = Mock()
        widget.current_board_widget = Mock()

        # Set up some data
        widget.total_boards = 3
        widget.total_repositories = 5

        widget.complete_progress({"status": "success"})

        # Verify compilation-specific completion updates
        widget.phase_icon.update.assert_called_with("✅")
        widget.current_repo_widget.update.assert_called_with("Build completed")
        widget.phase_info_widget.update.assert_called_with("(finished)")
        widget.board_progress_widget.update.assert_called_with("✅ All 3 boards")
        widget.repo_stats_widget.update.assert_called_with("✅ Processed: 5 repos")
        widget.current_board_widget.update.assert_called_with("")

    def test_complete_progress_single_board(self) -> None:
        """Test completion display for single board builds."""
        widget = CompilationProgressWidget()

        # Mock UI components
        widget.phase_icon = Mock()
        widget.current_repo_widget = Mock()
        widget.phase_info_widget = Mock()
        widget.board_progress_widget = Mock()
        widget.repo_stats_widget = Mock()
        widget.current_board_widget = Mock()

        # Set up single board data
        widget.total_boards = 1
        widget.total_repositories = 0

        widget.complete_progress()

        widget.board_progress_widget.update.assert_called_with("✅ Build complete")

    def test_fallback_progress_data(self) -> None:
        """Test handling of non-compilation progress data."""
        widget = CompilationProgressWidget()

        # Test with simple string data (should fall back to base class)
        simple_data = "Simple compilation update"
        widget._update_from_progress_data(simple_data)

        assert widget.status_text == "Simple compilation update"

    def test_reactive_properties_trigger_updates(self) -> None:
        """Test that reactive properties trigger compilation-specific updates."""
        widget = CompilationProgressWidget()

        # Mock UI components and parent methods
        widget.progress_info_widget = Mock()
        widget.progress_bar = Mock()

        # Test progress current update
        widget.watch_progress_current(75)

        # Should call parent watcher and progress info update
        widget.progress_bar.update.assert_called_with(progress=75)

    def test_empty_repository_handling(self) -> None:
        """Test handling when repository name is empty."""
        widget = CompilationProgressWidget()

        # Mock UI components
        widget.current_repo_widget = Mock()

        widget.current_repository = ""
        widget._update_repo_display()

        widget.current_repo_widget.update.assert_called_with("")

    def test_zero_totals_handling(self) -> None:
        """Test handling when totals are zero."""
        widget = CompilationProgressWidget()

        # Mock UI components
        widget.repo_stats_widget = Mock()
        widget.download_stats_widget = Mock()

        # Test zero repositories
        widget.repositories_downloaded = 2
        widget.total_repositories = 0
        widget._update_repo_stats()
        widget.repo_stats_widget.update.assert_called_with("")

        # Test zero bytes
        widget.bytes_downloaded = 500
        widget.total_bytes = 0
        widget._update_download_stats()
        widget.download_stats_widget.update.assert_called_with("")


def test_create_compilation_progress_widget_factory() -> None:
    """Test the factory function for creating compilation progress widgets."""
    widget = create_compilation_progress_widget(id="test-widget")

    assert isinstance(widget, CompilationProgressWidget)
    assert widget.id == "test-widget"


def test_compilation_widget_inheritance() -> None:
    """Test that CompilationProgressWidget properly inherits from ProgressWidget."""
    widget = CompilationProgressWidget()

    # Should have base ProgressWidget functionality
    assert hasattr(widget, "start_progress")
    assert hasattr(widget, "complete_progress")
    assert hasattr(widget, "cancel_progress")
    assert hasattr(widget, "get_result")
    assert hasattr(widget, "get_error")

    # Should have compilation-specific functionality
    assert hasattr(widget, "_handle_initialization_phase")
    assert hasattr(widget, "_handle_building_phase")
    assert hasattr(widget, "_update_repo_display")
    assert hasattr(widget, "_update_download_stats")


@pytest.mark.asyncio
async def test_compilation_widget_compose() -> None:
    """Test that CompilationProgressWidget composes with proper layout."""
    widget = CompilationProgressWidget()

    composed = list(widget.compose())

    # Should have multiple components for compilation display
    assert len(composed) > 3  # More than base ProgressWidget

    # Verify we have the expected structure (Vertical container with children)
    from textual.containers import Vertical

    assert len([w for w in composed if isinstance(w, Vertical)]) == 1
