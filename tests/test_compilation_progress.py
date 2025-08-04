#!/usr/bin/env python3
"""Unit tests for compilation progress functionality."""

from unittest.mock import Mock

import pytest

from glovebox.adapters.compilation_progress_middleware import (
    CompilationProgressMiddleware,
    create_compilation_progress_middleware,
)
from glovebox.core.file_operations import CompilationProgress


pytestmark = [pytest.mark.network, pytest.mark.integration, pytest.mark.docker]


class TestCompilationProgress:
    """Test CompilationProgress model."""

    def test_compilation_progress_creation(self) -> None:
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
            # Include new fields with appropriate values
            cache_operation_progress=0,
            cache_operation_total=100,
            cache_operation_status="pending",
            compilation_strategy="zmk_west",
            docker_image_name="",
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
        # Overall progress should be within west_update phase (15-40%)
        # 38.46% of repositories downloaded should put us around 30% overall
        expected_progress = 15 + (38.46 / 100) * (40 - 15)  # ~24.6%
        assert abs(progress.overall_progress_percent - expected_progress) < 1.0

    def test_compilation_progress_edge_cases(self) -> None:
        """Test CompilationProgress with edge cases."""
        # Test with zero totals
        progress = CompilationProgress(
            repositories_downloaded=0,
            total_repositories=0,
            current_repository="",
            compilation_phase="west_update",
            # Include required fields with defaults
            cache_operation_progress=0,
            cache_operation_total=100,
            cache_operation_status="pending",
            compilation_strategy="zmk_west",
            docker_image_name="",
        )

        assert progress.repository_progress_percent == 0.0
        assert progress.bytes_progress_percent == 0.0
        assert progress.repositories_remaining == 0


class TestCompilationProgressMiddleware:
    """Test CompilationProgressMiddleware functionality."""

    def test_middleware_creation(self) -> None:
        """Test middleware creation with factory function."""
        mock_coordinator = Mock()
        middleware = create_compilation_progress_middleware(mock_coordinator)

        assert isinstance(middleware, CompilationProgressMiddleware)
        assert middleware.progress_context == mock_coordinator

    def test_repository_download_parsing(self) -> None:
        """Test parsing of repository download lines."""
        mock_coordinator = Mock()
        middleware = CompilationProgressMiddleware(mock_coordinator)

        # Simulate repository download lines
        test_lines = [
            "From https://github.com/zmkfirmware/zephyr",
            "From https://github.com/zephyrproject-rtos/zcbor",
            "From https://github.com/moergo-sc/zmk",
        ]

        for line in test_lines:
            result = middleware.process(line, "stdout")
            assert result == line  # Should return original line

        # Verify coordinator was called for each repository
        assert mock_coordinator.update_repository_progress.call_count == 3

    def test_phase_transitions(self) -> None:
        """Test compilation phase transitions."""
        mock_coordinator = Mock()
        middleware = CompilationProgressMiddleware(mock_coordinator)

        # Test build phase detection
        middleware.process("west build -s zmk/app -b nice_nano_v2", "stdout")

        # Should have called transition_to_phase for building
        mock_coordinator.transition_to_phase.assert_called()

        # Test build completion
        middleware.process(
            "Memory region         Used Size  Region Size  %age Used", "stdout"
        )

        # Should have called transition_to_phase for collecting
        assert mock_coordinator.transition_to_phase.call_count >= 2

    def test_non_matching_lines(self) -> None:
        """Test that non-matching lines don't trigger callbacks."""
        mock_coordinator = Mock()
        middleware = CompilationProgressMiddleware(mock_coordinator)

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

        # No progress updates should have been triggered
        mock_coordinator.update_repository_progress.assert_not_called()
        mock_coordinator.update_build_progress.assert_not_called()

    def test_error_handling(self) -> None:
        """Test that errors in coordinator don't break processing."""
        failing_coordinator = Mock()
        failing_coordinator.update_repository_progress.side_effect = ValueError(
            "Test exception"
        )

        middleware = CompilationProgressMiddleware(failing_coordinator)

        # Process should continue even if coordinator fails
        line = "From https://github.com/zmkfirmware/zephyr"
        result = middleware.process(line, "stdout")

        assert result == line
        # Should have attempted to call coordinator despite error
        failing_coordinator.update_repository_progress.assert_called_once()

    def test_coordinator_delegation(self) -> None:
        """Test that middleware properly delegates to coordinator."""
        mock_coordinator = Mock()
        middleware = CompilationProgressMiddleware(mock_coordinator)

        # Process some repositories
        middleware.process("From https://github.com/zmkfirmware/zephyr", "stdout")
        middleware.process("From https://github.com/zephyrproject-rtos/zcbor", "stdout")

        # Should have called coordinator for each repository
        assert mock_coordinator.update_repository_progress.call_count == 2

    def test_repository_name_extraction(self) -> None:
        """Test correct extraction of repository names from URLs."""
        mock_coordinator = Mock()
        middleware = CompilationProgressMiddleware(mock_coordinator)

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

            # Check that coordinator was called with correct repository name
            last_call = mock_coordinator.update_repository_progress.call_args_list[-1]
            assert expected_repo in str(last_call)

    def test_stderr_processing(self) -> None:
        """Test processing stderr lines."""
        mock_coordinator = Mock()
        middleware = CompilationProgressMiddleware(mock_coordinator)

        # Repository downloads might appear in stderr
        line = "From https://github.com/zmkfirmware/zephyr"
        result = middleware.process(line, "stderr")

        assert result == line
        mock_coordinator.update_repository_progress.assert_called_once()

    def test_build_progress_pattern(self) -> None:
        """Test parsing of build progress [xx/xx] patterns."""
        mock_coordinator = Mock()
        middleware = CompilationProgressMiddleware(
            mock_coordinator, skip_west_update=True
        )

        # Test build progress patterns
        test_lines = [
            "[ 1/42] Building app/CMakeFiles/app.dir/src/main.c.obj",
            "[15/42] Building app/CMakeFiles/app.dir/src/behaviors/behavior_key_press.c.obj",
            "[42/42] Building firmware binary",
        ]

        for line in test_lines:
            result = middleware.process(line, "stdout")
            assert result == line

        # Should have called coordinator for each build step
        assert mock_coordinator.update_build_progress.call_count == 3

    def test_skip_west_update_parameter(self) -> None:
        """Test middleware creation with skip_west_update parameter."""
        mock_coordinator = Mock()
        middleware = create_compilation_progress_middleware(
            mock_coordinator, skip_west_update=True
        )

        # Should have called transition_to_phase for building
        mock_coordinator.transition_to_phase.assert_called_with(
            "building", "Starting compilation"
        )

        # Process a build step directly
        result = middleware.process("[ 5/42] Building something", "stdout")
        assert result == "[ 5/42] Building something"
        mock_coordinator.update_build_progress.assert_called()

    def test_automatic_phase_transition(self) -> None:
        """Test automatic transition from west_update to building when build detected."""
        mock_coordinator = Mock()
        middleware = CompilationProgressMiddleware(mock_coordinator)

        # Process a build line - should trigger transition to building
        result = middleware.process("west build -s zmk/app -b nice_nano_v2", "stdout")
        assert result == "west build -s zmk/app -b nice_nano_v2"

        # Should have called transition to building phase
        mock_coordinator.transition_to_phase.assert_called()

    def test_multi_board_progress_tracking(self) -> None:
        """Test progress tracking for multi-board builds (split keyboards)."""
        mock_coordinator = Mock()
        middleware = CompilationProgressMiddleware(
            mock_coordinator, skip_west_update=True
        )

        # Process first board build start
        result = middleware.process("west build -s zmk/app -b glove80_lh", "stdout")
        assert result == "west build -s zmk/app -b glove80_lh"

        # Process build steps for first board
        middleware.process("[ 5/42] Building something", "stdout")

        # Process first board completion
        middleware.process("TOTAL_FLASH usage: 123456 bytes", "stdout")

        # Process second board build start
        result = middleware.process("west build -s zmk/app -b glove80_rh", "stdout")
        assert result == "west build -s zmk/app -b glove80_rh"

        # Process build steps for second board
        middleware.process("[20/42] Building something else", "stdout")

        # Process final completion
        middleware.process(
            "Memory region         Used Size  Region Size  %age Used", "stdout"
        )

        # Should have called coordinator multiple times for all progress updates
        assert mock_coordinator.update_build_progress.call_count >= 2
        assert mock_coordinator.transition_to_phase.call_count >= 2

    def test_coordinator_integration(self) -> None:
        """Test factory function with coordinator integration."""
        mock_coordinator = Mock()
        middleware = create_compilation_progress_middleware(mock_coordinator)

        assert middleware.progress_context == mock_coordinator
