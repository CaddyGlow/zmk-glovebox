#!/usr/bin/env python3
"""Unit tests for compilation progress functionality."""

import re
from unittest.mock import Mock

import pytest

from glovebox.adapters.compilation_progress_middleware import (
    CompilationProgressMiddleware,
    create_compilation_progress_middleware,
)
from glovebox.core.file_operations import CompilationProgress


class TestCompilationProgress:
    """Test CompilationProgress model."""

    def test_compilation_progress_creation(self):
        """Test CompilationProgress model creation and properties."""
        progress = CompilationProgress(
            repositories_downloaded=15,
            total_repositories=39,
            current_repository="zmkfirmware/zephyr",
            compilation_phase="west_update",
            bytes_downloaded=1024 * 1024,
            total_bytes=10 * 1024 * 1024,
            current_board="glove80_lh",
            boards_completed=0,
            total_boards=2,
            current_board_step=5,
            total_board_steps=42,
        )

        assert progress.repositories_downloaded == 15
        assert progress.total_repositories == 39
        assert progress.current_repository == "zmkfirmware/zephyr"
        assert progress.compilation_phase == "west_update"
        assert progress.bytes_downloaded == 1024 * 1024
        assert progress.total_bytes == 10 * 1024 * 1024
        assert progress.current_board == "glove80_lh"
        assert progress.boards_completed == 0
        assert progress.total_boards == 2
        assert progress.current_board_step == 5
        assert progress.total_board_steps == 42

        # Test calculated properties
        assert abs(progress.repository_progress_percent - 38.46) < 0.1
        assert progress.bytes_progress_percent == 10.0
        assert progress.repositories_remaining == 24
        assert progress.board_progress_percent == 0.0  # 0/2 boards completed
        assert abs(progress.current_board_progress_percent - 11.9) < 0.1  # 5/42 steps
        assert progress.boards_remaining == 2
        # Overall progress should be ~11.5% (38.46% of west_update * 0.3)
        assert abs(progress.overall_progress_percent - 11.5) < 0.5

    def test_compilation_progress_edge_cases(self):
        """Test CompilationProgress with edge cases."""
        # Test with zero totals
        progress = CompilationProgress(
            repositories_downloaded=0,
            total_repositories=0,
            current_repository="",
            compilation_phase="west_update",
        )

        assert progress.repository_progress_percent == 0.0
        assert progress.bytes_progress_percent == 0.0
        assert progress.repositories_remaining == 0


class TestCompilationProgressMiddleware:
    """Test CompilationProgressMiddleware functionality."""

    def test_middleware_creation(self):
        """Test middleware creation with factory function."""
        mock_callback = Mock()
        middleware = create_compilation_progress_middleware(
            mock_callback, total_repositories=42
        )

        assert isinstance(middleware, CompilationProgressMiddleware)
        assert middleware.total_repositories == 42
        assert middleware.repositories_downloaded == 0
        assert middleware.current_phase == "west_update"

    def test_repository_download_parsing(self):
        """Test parsing of repository download lines."""
        mock_callback = Mock()
        middleware = CompilationProgressMiddleware(mock_callback, total_repositories=39)

        # Simulate repository download lines
        test_lines = [
            "From https://github.com/zmkfirmware/zephyr",
            "From https://github.com/zephyrproject-rtos/zcbor",
            "From https://github.com/moergo-sc/zmk",
        ]

        for line in test_lines:
            result = middleware.process(line, "stdout")
            assert result == line  # Should return original line

        # Verify callback was called for each repository
        assert mock_callback.call_count == 3
        assert middleware.repositories_downloaded == 3

        # Check the last progress update
        last_call = mock_callback.call_args_list[-1]
        progress = last_call[0][0]
        assert isinstance(progress, CompilationProgress)
        assert progress.repositories_downloaded == 3
        assert progress.total_repositories == 39
        assert progress.current_repository == "moergo-sc/zmk"
        assert progress.compilation_phase == "west_update"

    def test_phase_transitions(self):
        """Test compilation phase transitions."""
        mock_callback = Mock()
        middleware = CompilationProgressMiddleware(mock_callback, total_repositories=39)

        # Download all repositories to trigger phase change
        for i in range(39):
            line = f"From https://github.com/test-org/repo-{i}"
            middleware.process(line, "stdout")

        # Should have transitioned to building phase
        assert middleware.current_phase == "building"

        # Test build phase detection
        middleware.process("west build -s zmk/app -b nice_nano_v2", "stdout")

        # Test build completion
        middleware.process(
            "Memory region         Used Size  Region Size  %age Used", "stdout"
        )

        # Should have transitioned to collecting phase
        assert middleware.current_phase == "collecting"

    def test_non_matching_lines(self):
        """Test that non-matching lines don't trigger callbacks."""
        mock_callback = Mock()
        middleware = CompilationProgressMiddleware(mock_callback, total_repositories=39)

        # Test lines that shouldn't match
        test_lines = [
            "Some random output",
            "https://github.com/someuser/repo",  # Missing "From "
            "From https://gitlab.com/user/repo",  # Not github.com
            "",  # Empty line
            "   ",  # Whitespace only
        ]

        for line in test_lines:
            result = middleware.process(line, "stdout")
            assert result == line

        # No callbacks should have been triggered
        assert mock_callback.call_count == 0
        assert middleware.repositories_downloaded == 0

    def test_error_handling(self):
        """Test that errors in callback don't break processing."""

        def failing_callback(progress):
            raise ValueError("Test exception")

        middleware = CompilationProgressMiddleware(
            failing_callback, total_repositories=39
        )

        # Process should continue even if callback fails
        line = "From https://github.com/zmkfirmware/zephyr"
        result = middleware.process(line, "stdout")

        assert result == line
        assert middleware.repositories_downloaded == 1

    def test_get_current_progress(self):
        """Test getting current progress state."""
        mock_callback = Mock()
        middleware = CompilationProgressMiddleware(mock_callback, total_repositories=39)

        # Process some repositories
        middleware.process("From https://github.com/zmkfirmware/zephyr", "stdout")
        middleware.process("From https://github.com/zephyrproject-rtos/zcbor", "stdout")

        current_progress = middleware.get_current_progress()
        assert isinstance(current_progress, CompilationProgress)
        assert current_progress.repositories_downloaded == 2
        assert current_progress.total_repositories == 39
        assert current_progress.compilation_phase == "west_update"

    def test_repository_name_extraction(self):
        """Test correct extraction of repository names from URLs."""
        mock_callback = Mock()
        middleware = CompilationProgressMiddleware(mock_callback, total_repositories=39)

        test_cases = [
            ("From https://github.com/zmkfirmware/zephyr", "zmkfirmware/zephyr"),
            (
                "From https://github.com/zephyrproject-rtos/zcbor",
                "zephyrproject-rtos/zcbor",
            ),
            ("From https://github.com/moergo-sc/zmk", "moergo-sc/zmk"),
        ]

        for line, expected_repo in test_cases:
            middleware.process(line, "stdout")

            # Check that the last callback received the correct repository name
            last_call = mock_callback.call_args_list[-1]
            progress = last_call[0][0]
            assert progress.current_repository == expected_repo

    def test_stderr_processing(self):
        """Test processing stderr lines."""
        mock_callback = Mock()
        middleware = CompilationProgressMiddleware(mock_callback, total_repositories=39)

        # Repository downloads might appear in stderr
        line = "From https://github.com/zmkfirmware/zephyr"
        result = middleware.process(line, "stderr")

        assert result == line
        assert mock_callback.call_count == 1
        assert middleware.repositories_downloaded == 1

    def test_build_progress_pattern(self):
        """Test parsing of build progress [xx/xx] patterns."""
        mock_callback = Mock()
        middleware = CompilationProgressMiddleware(mock_callback, total_repositories=39)

        # Switch to building phase first
        middleware.current_phase = "building"

        # Test build progress patterns
        test_lines = [
            "[ 1/42] Building app/CMakeFiles/app.dir/src/main.c.obj",
            "[15/42] Building app/CMakeFiles/app.dir/src/behaviors/behavior_key_press.c.obj",
            "[42/42] Building firmware binary",
        ]

        for line in test_lines:
            result = middleware.process(line, "stdout")
            assert result == line

        # Should have called callback for each build step
        assert mock_callback.call_count == 3

        # Check the last progress update shows build step
        last_call = mock_callback.call_args_list[-1]
        progress = last_call[0][0]
        assert isinstance(progress, CompilationProgress)
        assert progress.compilation_phase == "building"
        assert progress.current_board_step == 42
        assert progress.total_board_steps == 42

    def test_skip_west_update_parameter(self):
        """Test middleware creation with skip_west_update parameter."""
        mock_callback = Mock()
        middleware = create_compilation_progress_middleware(
            mock_callback, total_repositories=39, skip_west_update=True
        )

        # Should start in building phase instead of west_update
        assert middleware.current_phase == "building"

        # Process a build step directly
        result = middleware.process("[ 5/42] Building something", "stdout")
        assert result == "[ 5/42] Building something"
        assert mock_callback.call_count == 1

    def test_automatic_phase_transition(self):
        """Test automatic transition from west_update to building when build detected."""
        mock_callback = Mock()
        middleware = CompilationProgressMiddleware(mock_callback, total_repositories=39)

        # Should start in west_update phase
        assert middleware.current_phase == "west_update"

        # Process a build line - should trigger transition to building
        result = middleware.process("west build -s zmk/app -b nice_nano_v2", "stdout")
        assert result == "west build -s zmk/app -b nice_nano_v2"

        # Should have transitioned to building phase
        assert middleware.current_phase == "building"
        assert mock_callback.call_count == 2  # Two callbacks: transition + build start detection

    def test_multi_board_progress_tracking(self):
        """Test progress tracking for multi-board builds (split keyboards)."""
        mock_callback = Mock()
        middleware = CompilationProgressMiddleware(
            mock_callback,
            total_repositories=39,
            total_boards=2,
            board_names=["glove80_lh", "glove80_rh"]
        )

        # Start in building phase for this test
        middleware.current_phase = "building"

        # Process first board build start
        result = middleware.process("west build -s zmk/app -b glove80_lh", "stdout")
        assert result == "west build -s zmk/app -b glove80_lh"
        assert middleware.current_board == "glove80_lh"
        assert middleware.boards_completed == 0

        # Process build steps for first board
        middleware.process("[ 5/42] Building something", "stdout")
        assert middleware.current_board_step == 5
        assert middleware.total_board_steps == 42

        # Process first board completion
        middleware.process("TOTAL_FLASH usage: 123456 bytes", "stdout")
        assert middleware.boards_completed == 1
        assert middleware.current_board == ""  # Reset after completion

        # Process second board build start
        result = middleware.process("west build -s zmk/app -b glove80_rh", "stdout")
        assert result == "west build -s zmk/app -b glove80_rh"
        assert middleware.current_board == "glove80_rh"
        assert middleware.boards_completed == 1

        # Process build steps for second board
        middleware.process("[20/42] Building something else", "stdout")
        assert middleware.current_board_step == 20

        # Process final completion
        middleware.process("Memory region         Used Size  Region Size  %age Used", "stdout")
        assert middleware.boards_completed == 2
        assert middleware.current_phase == "collecting"

        # Should have called callback multiple times for all progress updates
        assert mock_callback.call_count >= 6

    def test_multi_board_factory_creation(self):
        """Test factory function with multi-board parameters."""
        mock_callback = Mock()
        middleware = create_compilation_progress_middleware(
            mock_callback,
            total_repositories=39,
            total_boards=2,
            board_names=["glove80_lh", "glove80_rh"]
        )

        assert middleware.total_boards == 2
        assert middleware.board_names == ["glove80_lh", "glove80_rh"]
        assert middleware.boards_completed == 0
        assert middleware.current_board == ""
