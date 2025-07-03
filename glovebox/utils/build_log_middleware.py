"""Build log capture middleware for compilation processes."""

import logging
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Any, TextIO

from glovebox.utils.stream_process import OutputMiddleware


if TYPE_CHECKING:
    from glovebox.protocols.progress_context_protocol import ProgressContextProtocol


logger = logging.getLogger(__name__)


class BuildLogCaptureMiddleware(OutputMiddleware[str]):
    """Middleware that captures all build output to a log file.

    This middleware captures both stdout and stderr output from compilation
    processes and writes them to a build log file in the artifacts directory.
    It preserves the original output for chaining with other middleware.

    The log file includes:
    - Timestamp for each log entry
    - Stream type indication (stdout/stderr)
    - Original command output

    Thread-safe for concurrent access to the log file.
    """

    def __init__(
        self,
        log_file_path: Path,
        progress_context: "ProgressContextProtocol",
        include_timestamps: bool = True,
        include_stream_type: bool = True,
    ) -> None:
        """Initialize build log capture middleware.

        Args:
            log_file_path: Path where the build log should be saved
            include_timestamps: Whether to include timestamps in log entries
            include_stream_type: Whether to indicate stream type (stdout/stderr)
            progress_context: Progress context for file writing progress updates
        """
        self.log_file_path = log_file_path
        self.include_timestamps = include_timestamps
        self.include_stream_type = include_stream_type
        self.progress_context = progress_context
        self._file_handle: TextIO | None = None
        self._lock = Lock()
        self._lines_written = 0
        self._initialize_log_file()

    def _initialize_log_file(self) -> None:
        """Initialize the log file and write header."""
        try:
            # Ensure parent directory exists
            self.log_file_path.parent.mkdir(parents=True, exist_ok=True)

            # Open log file for writing
            self._file_handle = self.log_file_path.open("w", encoding="utf-8")

            # Write log header
            timestamp = datetime.now().isoformat()
            self._file_handle.write(f"# Build Log - {timestamp}\n")
            self._file_handle.write(f"# Log file: {self.log_file_path}\n")
            self._file_handle.write("# Format: [timestamp] [stream] output\n")
            self._file_handle.write("# ==========================================\n\n")
            self._file_handle.flush()

            logger.debug("Initialized build log file: %s", self.log_file_path)

            # Update progress context
            self.progress_context.log(
                f"Initialized build log: {self.log_file_path.name}"
            )
            self.progress_context.set_status_info(
                {"current_file": str(self.log_file_path.name)}
            )

        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error(
                "Failed to initialize build log file %s: %s",
                self.log_file_path,
                e,
                exc_info=exc_info,
            )
            self.progress_context.log(f"ERROR: Failed to initialize build log: {e}")
            self._file_handle = None

    def process(self, line: str, stream_type: str) -> str:
        """Process a line of output and write it to the log file.

        Args:
            line: Output line from the process
            stream_type: Either "stdout" or "stderr"

        Returns:
            The original line (unmodified for chaining)
        """
        if self._file_handle is None:
            # Log file initialization failed, just pass through
            return line

        try:
            with self._lock:
                # Format log entry
                log_entry_parts = []

                if self.include_timestamps:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    log_entry_parts.append(f"[{timestamp}]")

                if self.include_stream_type:
                    stream_prefix = "STDOUT" if stream_type == "stdout" else "STDERR"
                    log_entry_parts.append(f"[{stream_prefix}]")

                log_entry_parts.append(line)
                log_entry = " ".join(log_entry_parts) + "\n"

                # Write to log file
                self._file_handle.write(log_entry)
                self._file_handle.flush()  # Ensure immediate write for real-time monitoring

                # Update line counter and progress
                self._lines_written += 1

                # Update progress context every 100 lines to avoid spam
                if self._lines_written % 100 == 0:
                    self.progress_context.set_status_info(
                        {
                            "current_file": str(self.log_file_path.name),
                            "files_copied": f"{self._lines_written} lines",
                        }
                    )

        except Exception as e:
            # Don't let logging errors break the compilation process
            logger.warning("Failed to write to build log file: %s", e)
            self.progress_context.log(f"WARNING: Failed to write to build log: {e}")

        # Return original line for chaining
        return line

    def close(self) -> None:
        """Close the log file handle."""
        try:
            with self._lock:
                if self._file_handle:
                    self._file_handle.write(
                        f"\n# Build log completed - {datetime.now().isoformat()}\n"
                    )
                    self._file_handle.close()
                    self._file_handle = None
                    logger.debug("Closed build log file: %s", self.log_file_path)

                    # Update progress context
                    self.progress_context.log(
                        f"Completed build log: {self._lines_written} lines written"
                    )
                    self.progress_context.set_status_info(
                        {
                            "current_file": str(self.log_file_path.name),
                            "files_copied": f"{self._lines_written} lines total",
                        }
                    )

        except Exception as e:
            logger.warning("Error closing build log file: %s", e)
            self.progress_context.log(f"WARNING: Error closing build log: {e}")

    def __enter__(self) -> "BuildLogCaptureMiddleware":
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Context manager exit - ensure log file is closed."""
        self.close()


def create_build_log_middleware(
    artifacts_dir: Path,
    progress_context: "ProgressContextProtocol",
    log_filename: str = "build.log",
    include_timestamps: bool = True,
    include_stream_type: bool = True,
) -> BuildLogCaptureMiddleware:
    """Factory function to create a build log capture middleware.

    Args:
        artifacts_dir: Directory where the build log should be saved
        log_filename: Name of the log file (default: "build.log")
        include_timestamps: Whether to include timestamps in log entries
        include_stream_type: Whether to indicate stream type (stdout/stderr)
        progress_context: Progress context for file writing progress updates

    Returns:
        BuildLogCaptureMiddleware instance

    Example:
        ```python
        from glovebox.utils.build_log_middleware import create_build_log_middleware
        from glovebox.utils.stream_process import create_chained_middleware

        # Create build log middleware
        log_middleware = create_build_log_middleware(artifacts_dir)

        # Chain with other middleware
        middlewares = [log_middleware, DefaultOutputMiddleware()]
        chained = create_chained_middleware(middlewares)

        # Use with Docker adapter
        result = docker_adapter.run_container("image", [], {}, middleware=chained)

        # Close log file when done
        log_middleware.close()
        ```
    """
    log_file_path = artifacts_dir / log_filename
    return BuildLogCaptureMiddleware(
        log_file_path=log_file_path,
        progress_context=progress_context,
        include_timestamps=include_timestamps,
        include_stream_type=include_stream_type,
    )
