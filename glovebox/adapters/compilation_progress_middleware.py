"""Compilation progress middleware for Docker output parsing."""

import logging
import re
from typing import TYPE_CHECKING, Optional

from glovebox.core.file_operations import (
    CompilationProgress,
    CompilationProgressCallback,
)
from glovebox.utils.stream_process import OutputMiddleware


if TYPE_CHECKING:
    from glovebox.cli.components.unified_progress_coordinator import (
        UnifiedCompilationProgressCoordinator,
    )
    from glovebox.compilation.models.compilation_config import ProgressPhasePatterns


logger = logging.getLogger(__name__)


class CompilationProgressMiddleware(OutputMiddleware[str]):
    """Middleware for tracking firmware compilation progress through Docker output.

    This middleware parses Docker output during firmware compilation and delegates
    progress updates to a UnifiedCompilationProgressCoordinator for unified TUI display.

    Tracks:
    - Repository downloads during 'west update' (e.g., "From https://github.com/...")
    - Build progress during compilation
    - Artifact collection
    """

    def __init__(
        self,
        progress_coordinator: "UnifiedCompilationProgressCoordinator",
        progress_patterns: "ProgressPhasePatterns | None" = None,
        skip_west_update: bool = False,  # Set to True if compilation starts directly with building
    ) -> None:
        """Initialize the compilation progress middleware.

        Args:
            progress_coordinator: Unified progress coordinator to delegate updates to
            progress_patterns: Regex patterns for phase detection (defaults to standard patterns)
            skip_west_update: Whether to skip west update phase and start with building
        """
        self.progress_coordinator = progress_coordinator
        self.skip_west_update = skip_west_update

        # Initialize coordinator to correct phase
        if skip_west_update:
            self.progress_coordinator.transition_to_phase(
                "building", "Starting compilation"
            )

        # Use provided patterns or create default ones
        if progress_patterns is None:
            from glovebox.compilation.models.compilation_config import (
                ProgressPhasePatterns,
            )

            progress_patterns = ProgressPhasePatterns()

        # Compile patterns for parsing different types of output
        self.repo_download_pattern = re.compile(progress_patterns.repo_download_pattern)
        self.build_start_pattern = re.compile(progress_patterns.build_start_pattern)
        self.build_progress_pattern = re.compile(
            progress_patterns.build_progress_pattern
        )
        self.build_complete_pattern = re.compile(
            progress_patterns.build_complete_pattern
        )
        # Board-specific patterns
        self.board_detection_pattern = re.compile(
            progress_patterns.board_detection_pattern
        )
        self.board_complete_pattern = re.compile(
            progress_patterns.board_complete_pattern
        )

    def process(self, line: str, stream_type: str) -> str:
        """Process Docker output line and update compilation progress.

        Args:
            line: Output line from Docker
            stream_type: Either "stdout" or "stderr"

        Returns:
            The original line (unmodified)
        """
        line_stripped = line.strip()

        if not line_stripped:
            return line

        try:
            # Enhanced initialization detection for cache vs west init
            if self.progress_coordinator.current_phase == "initialization":
                init_type = self._detect_initialization_type(line_stripped)
                package_count = self._extract_package_count(line_stripped)

                if init_type == "cache_restore":
                    self.progress_coordinator.transition_to_phase(
                        "cache_restoration", "Restoring cached workspace"
                    )
                    self.progress_coordinator.update_cache_progress(
                        "restoring", 25, 100, "Loading cached workspace"
                    )
                elif init_type == "west_init":
                    # Show warning about long duration for west init
                    if package_count:
                        desc = f"Downloading dependencies ({package_count} packages - this may take 15+ minutes)"
                    else:
                        desc = "Downloading dependencies (west update - this may take 15+ minutes)"

                    self.progress_coordinator.transition_to_phase(
                        "west_update", desc
                    )
                    if package_count:
                        # Update total repositories count with actual package count
                        self.progress_coordinator.total_repositories = package_count

            # Check for build start patterns to detect phase transitions
            build_match = self.build_start_pattern.search(line_stripped)
            build_progress_match = self.build_progress_pattern.search(line_stripped)

            # If we detect build activity and not already in building phase, transition to building
            if (
                build_match or build_progress_match
            ) and self.progress_coordinator.current_phase != "building":
                logger.info(
                    "Detected build activity, transitioning from %s to building phase",
                    self.progress_coordinator.current_phase,
                )
                self.progress_coordinator.transition_to_phase(
                    "building", "Starting compilation"
                )

            # Parse repository downloads during west update
            if self.progress_coordinator.current_phase == "west_update":
                repo_match = self.repo_download_pattern.match(line_stripped)
                if repo_match:
                    repository_name = repo_match.group(1)
                    self.progress_coordinator.update_repository_progress(
                        repository_name
                    )

            # Parse build progress during building phase
            elif self.progress_coordinator.current_phase == "building":
                # Detect board start
                board_match = self.board_detection_pattern.search(line_stripped)
                if board_match:
                    board_name = board_match.group(1)
                    self.progress_coordinator.update_board_progress(
                        board_name=board_name
                    )

                # Check for build progress indicators [xx/xx] Building...
                build_progress_match = self.build_progress_pattern.search(line_stripped)
                if build_progress_match:
                    current_step = int(build_progress_match.group(1))
                    total_steps = int(build_progress_match.group(2))
                    self.progress_coordinator.update_board_progress(
                        current_step=current_step, total_steps=total_steps
                    )

                # Check for individual board completion
                if self.board_complete_pattern.search(line_stripped):
                    self.progress_coordinator.update_board_progress(completed=True)

                # Check for individual board completion (Memory region appears per board)
                # Only transition when all boards are actually done
                if (
                    self.build_complete_pattern.search(line_stripped)
                    and self.progress_coordinator.boards_completed
                    >= self.progress_coordinator.total_boards
                ):
                    # All boards have completed - now we can transition to collecting
                    self.progress_coordinator.complete_all_builds()

            # Cache saving phase is handled by the service layer, not Docker output
            # No need to track it in the middleware

        except Exception as e:
            # Don't let progress tracking break the compilation
            logger.warning("Error processing compilation progress: %s", e)

        # Forward interesting Docker output to the TUI display
        # This captures build tool output (west, cmake, gcc) that doesn't go through glovebox loggers
        try:
            if (
                hasattr(self.progress_coordinator, "tui_callback")
                and hasattr(self.progress_coordinator.tui_callback, "add_log_line")
                and self._should_forward_docker_output(line_stripped)
            ):
                self.progress_coordinator.tui_callback.add_log_line(line_stripped)
        except Exception as e:
            # Don't let log forwarding break the compilation
            logger.debug("Error forwarding Docker output to display: %s", e)

        return line

    def _should_forward_docker_output(self, line: str) -> bool:
        """Check if a Docker output line should be forwarded to the log display."""
        if not line.strip():
            return False

        # Filter out common Docker/infrastructure noise
        noise_filters = [
            # Docker noise
            "WARNING: The requested image's platform",
            "Unable to find image",
            "Pulling from",
            "Pull complete",
            "Digest: sha256:",
            "Status: Downloaded",
            # Git noise that's not useful
            "remote: Enumerating objects:",
            "remote: Counting objects:",
            "remote: Compressing objects:",
            "Receiving objects:",
            "Resolving deltas:",
            # Very verbose build system output
            "-- Cache files will be written to:",
            "-- Configuring done",
            "-- Generating done",
        ]

        for noise in noise_filters:
            if noise in line:
                return False

        # Filter very short lines (probably not useful)
        if len(line.strip()) < 8:
            return False

        # Forward lines that look like interesting build output
        interesting_patterns = [
            # Build progress indicators
            "[",  # Like [150/200] Building...
            "Building",
            "Compiling",
            "Linking",
            # Build tools
            "west ",
            "cmake",
            "ninja",
            "make",
            "gcc",
            "clang",
            # Status messages
            "✓",
            "✗",
            "Error",
            "Warning",
            "Failed",
            "Success",
            # Memory/size info
            "Memory region",
            "FLASH:",
            "SRAM:",
            # west specific
            "Updating",
            "From https://",
            # West init patterns for package counting
            "west init",
            "Initialized",
            "Importing projects",
            "projects:",
            "revision",
            "manifest:",
            "Cloning",
            "repository",
            # Cache operations
            "Restoring",
            "cached",
            "cache",
        ]

        return any(pattern in line for pattern in interesting_patterns)

    def _detect_initialization_type(self, line: str) -> str | None:
        """Detect whether the initialization is cache restore or west init.

        Returns:
            "cache_restore" if cache is being restored
            "west_init" if west init is being performed
            None if neither is detected
        """
        line_lower = line.lower()

        # Cache restore patterns
        cache_patterns = [
            "restoring cached",
            "copying cached",
            "cache restoration",
            "cached workspace",
            "loading cached",
        ]

        # West init patterns
        west_init_patterns = [
            "west init",
            "initialized empty",
            "importing projects",
            "manifest repository",
            "cloning into",
            "--- zmk (path: zmk, revision:",
            "updating zmk",
        ]

        if any(pattern in line_lower for pattern in cache_patterns):
            return "cache_restore"
        elif any(pattern in line_lower for pattern in west_init_patterns):
            return "west_init"

        return None

    def _extract_package_count(self, line: str) -> int | None:
        """Extract package/project count from west init output.

        Returns:
            Number of packages/projects if detected, None otherwise
        """
        # Look for patterns like "=== (X projects) ===" or "X projects:"
        import re

        patterns = [
            r"=== \((\d+) projects?\) ===",
            r"(\d+) projects?:",
            r"importing (\d+) projects?",
            r"processing (\d+) projects?",
        ]

        for pattern in patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    continue

        return None

    def get_current_progress(self) -> CompilationProgress:
        """Get the current progress state from the coordinator.

        Returns:
            Current CompilationProgress object
        """
        return self.progress_coordinator.get_current_progress()


def create_compilation_progress_middleware(
    progress_coordinator: "UnifiedCompilationProgressCoordinator",
    progress_patterns: "ProgressPhasePatterns | None" = None,
    skip_west_update: bool = False,
) -> CompilationProgressMiddleware:
    """Factory function to create compilation progress middleware.

    Args:
        progress_coordinator: Unified progress coordinator to delegate updates to
        progress_patterns: Regex patterns for phase detection (defaults to standard patterns)
        skip_west_update: Whether to skip west update phase and start with building

    Returns:
        Configured CompilationProgressMiddleware instance
    """
    return CompilationProgressMiddleware(
        progress_coordinator=progress_coordinator,
        progress_patterns=progress_patterns,
        skip_west_update=skip_west_update,
    )
