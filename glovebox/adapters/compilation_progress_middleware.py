"""Compilation progress middleware for Docker output parsing."""

import logging
import re
from typing import TYPE_CHECKING

from glovebox.utils.stream_process import OutputMiddleware


if TYPE_CHECKING:
    from glovebox.compilation.models.compilation_config import ProgressPhasePatterns
    from glovebox.protocols.progress_context_protocol import ProgressContextProtocol


logger = logging.getLogger(__name__)


class CompilationProgressMiddleware(OutputMiddleware[str]):
    """Middleware for tracking firmware compilation progress through Docker output.

    This middleware parses Docker output during firmware compilation and delegates
    progress updates to a ProgressCoordinatorProtocol implementation.

    Tracks:
    - Repository downloads during 'west update' (e.g., "From https://github.com/...")
    - Build progress during compilation
    - Artifact collection
    """

    def __init__(
        self,
        progress_context: "ProgressContextProtocol",
        progress_patterns: "ProgressPhasePatterns | None" = None,
        skip_west_update: bool = False,  # Set to True if compilation starts directly with building
    ) -> None:
        """Initialize the compilation progress middleware.

        Args:
            progress_coordinator: Progress coordinator to delegate updates to
            progress_patterns: Regex patterns for phase detection (defaults to standard patterns)
            skip_west_update: Whether to skip west update phase and start with building
            progress_context: Progress context for UI updates
        """
        self.progress_context = progress_context
        self.skip_west_update = skip_west_update

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

        # Enhanced git clone progress patterns
        self.git_objects_pattern = re.compile(
            r"Receiving objects:\s+(\d+)%\s+\((\d+)/(\d+)\),?\s*(?:(\d+(?:\.\d+)?)\s*(KiB|MiB|GiB)/s)?"
        )
        self.git_deltas_pattern = re.compile(
            r"Resolving deltas:\s+(\d+)%\s+\((\d+)/(\d+)\)"
        )

        # Current repository being processed (for detailed progress)
        self._current_repository = ""

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
            # Initialization detection for cache vs west init
            init_type = self._detect_initialization_type(line_stripped)
            package_count = self._extract_package_count(line_stripped)

            if init_type == "cache_restore":
                self.progress_context.log("Restoring cached workspace")
                self.progress_context.set_status_info(
                    {"docker_status": "cache_restore"}
                )
            elif init_type == "west_init":
                if package_count:
                    msg = f"Downloading dependencies ({package_count} packages)"
                    self.progress_context.set_status_info(
                        {"docker_status": "west_init", "total_packages": package_count}
                    )
                else:
                    msg = "Downloading dependencies (west update)"
                    self.progress_context.set_status_info(
                        {"docker_status": "west_init"}
                    )

                self.progress_context.log(msg)

            # Check for build start patterns to detect phase transitions
            build_match = self.build_start_pattern.search(line_stripped)
            build_progress_match = self.build_progress_pattern.search(line_stripped)

            # If we detect build activity, update progress context
            if build_match or build_progress_match:
                self.progress_context.log("Starting compilation")
                self.progress_context.set_status_info({"docker_status": "building"})

            # Parse repository downloads during west update
            repo_match = self.repo_download_pattern.match(line_stripped)
            if repo_match:
                repository_name = repo_match.group(1)
                self._current_repository = repository_name
                self.progress_context.log(f"Downloading {repository_name}")
                self.progress_context.set_status_info({"current_file": repository_name})

            # Enhanced git clone progress tracking
            objects_match = self.git_objects_pattern.search(line_stripped)
            if objects_match and self._current_repository:
                try:
                    percent = int(objects_match.group(1))
                    current_objects = int(objects_match.group(2))
                    total_objects = int(objects_match.group(3))

                    # Extract transfer speed if available
                    speed = 0.0
                    if objects_match.group(4) and objects_match.group(5):
                        speed_value = float(objects_match.group(4))
                        speed_unit = objects_match.group(5)
                        # Convert to MB/s for display
                        if speed_unit == "GiB":
                            speed = speed_value * 1024
                        elif speed_unit == "MiB":
                            speed = speed_value
                        else:  # KiB
                            speed = speed_value / 1024

                    self.progress_context.update_progress(
                        current_objects, total_objects
                    )
                    if speed > 0:
                        self.progress_context.set_status_info(
                            {
                                "current_file": self._current_repository,
                                "speed": f"{speed:.1f} MB/s",
                            }
                        )
                except (ValueError, IndexError) as e:
                    logger.debug("Error parsing git objects progress: %s", e)

            # Parse "Resolving deltas" progress
            deltas_match = self.git_deltas_pattern.search(line_stripped)
            if deltas_match and self._current_repository:
                try:
                    percent = int(deltas_match.group(1))
                    current_deltas = int(deltas_match.group(2))
                    total_deltas = int(deltas_match.group(3))

                    self.progress_context.update_progress(current_deltas, total_deltas)
                    self.progress_context.set_status_info(
                        {
                            "current_file": self._current_repository,
                            "component": "resolving deltas",
                        }
                    )
                except (ValueError, IndexError) as e:
                    logger.debug("Error parsing git deltas progress: %s", e)

            # Parse build progress during building phase
            # Detect board start
            board_match = self.board_detection_pattern.search(line_stripped)
            if board_match:
                board_name = board_match.group(1)
                self.progress_context.log(f"Building {board_name}")
                self.progress_context.set_status_info({"component": board_name})

            # Check for build progress indicators [xx/xx] Building...
            if build_progress_match:
                current_step = int(build_progress_match.group(1))
                total_steps = int(build_progress_match.group(2))
                self.progress_context.update_progress(current_step, total_steps)

            # Check for individual board completion using multiple patterns
            board_completion_indicators = [
                self.board_complete_pattern.search(line_stripped),
                # Additional patterns for different ZMK output formats
                re.search(r"Memory region.*Used Size", line_stripped),
                re.search(r"Generating zephyr/merged\.hex", line_stripped),
                re.search(r"west build.*completed", line_stripped, re.IGNORECASE),
                re.search(r"Build complete", line_stripped, re.IGNORECASE),
            ]

            if any(board_completion_indicators):
                logger.debug("Board completion detected: %s", line_stripped)
                self.progress_context.log("Board build completed")

            # Check for overall build completion with improved patterns
            build_completion_indicators = [
                self.build_complete_pattern.search(line_stripped),
                # Additional completion patterns
                re.search(r"Memory region\s+Used Size", line_stripped),
                re.search(r"FLASH.*region.*overlaps", line_stripped),
                re.search(
                    r"west build.*completed.*successfully",
                    line_stripped,
                    re.IGNORECASE,
                ),
            ]

            if any(build_completion_indicators):
                logger.info("All builds completed")
                self.progress_context.log("Compilation completed successfully")

            # Cache saving phase is handled by the service layer, not Docker output
            # No need to track it in the middleware

        except Exception as e:
            # Don't let progress tracking break the compilation
            logger.warning("Error processing compilation progress: %s", e)

        # Forward interesting Docker output to the progress display
        # This captures build tool output (west, cmake, gcc) that doesn't go through glovebox loggers
        try:
            if self._should_forward_docker_output(line_stripped):
                # Determine log level based on content
                log_level = self._determine_log_level(line_stripped)
                if log_level == "error":
                    self.progress_context.log(f"ERROR: {line_stripped}")
                elif log_level == "warning":
                    self.progress_context.log(f"WARNING: {line_stripped}")
                else:
                    self.progress_context.log(line_stripped)
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

    def _determine_log_level(self, line: str) -> str:
        """Determine the appropriate log level for a Docker output line.

        Args:
            line: The Docker output line

        Returns:
            Log level string (error, warning, info, debug)
        """
        line_lower = line.lower()

        # Error indicators
        if any(keyword in line_lower for keyword in ["error", "failed", "✗", "fatal"]):
            return "error"

        # Warning indicators
        if any(keyword in line_lower for keyword in ["warning", "warn", "deprecated"]):
            return "warning"

        # Debug indicators (very verbose output)
        if any(keyword in line_lower for keyword in ["debug", "verbose", "trace"]):
            return "debug"

        # Default to info level
        return "info"

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


def create_compilation_progress_middleware(
    progress_context: "ProgressContextProtocol",
    progress_patterns: "ProgressPhasePatterns | None" = None,
    skip_west_update: bool = False,
) -> CompilationProgressMiddleware:
    """Factory function to create compilation progress middleware.

    Args:
        progress_coordinator: Progress coordinator to delegate updates to
        progress_patterns: Regex patterns for phase detection (defaults to standard patterns)
        skip_west_update: Whether to skip west update phase and start with building
        progress_context: Progress context for UI updates

    Returns:
        Configured CompilationProgressMiddleware instance
    """
    return CompilationProgressMiddleware(
        progress_context=progress_context,
        progress_patterns=progress_patterns,
        skip_west_update=skip_west_update,
    )
