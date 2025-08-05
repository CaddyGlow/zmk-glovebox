"""Build output filter middleware for cleaning verbose compiler warnings."""

import logging
import re
from typing import TYPE_CHECKING

from glovebox.core.structlog_logger import get_struct_logger
from glovebox.utils.stream_process import OutputMiddleware


if TYPE_CHECKING:
    from glovebox.protocols.progress_context_protocol import ProgressContextProtocol


logger = get_struct_logger(__name__)


class BuildOutputFilterMiddleware(OutputMiddleware[str]):
    """Middleware that filters out verbose compiler warnings from build output.

    This middleware removes repetitive and verbose warning messages that don't
    provide actionable information, while preserving important warnings and errors.
    It also manages blank lines to prevent gaps in the output where content was filtered.

    The filtered patterns include:
    - Macro expansion notes from devicetree headers
    - Long macro definition chains
    - Repetitive "note: in expansion of macro" messages
    - Overflow warnings with excessive detail

    Important warnings like redefinitions, deprecated properties, and actual
    errors are preserved.
    """

    def __init__(
        self,
        progress_context: "ProgressContextProtocol",
        filter_verbose_warnings: bool = True,
        preserve_important_warnings: bool = True,
    ) -> None:
        """Initialize build output filter middleware.

        Args:
            progress_context: Progress context for status updates
            filter_verbose_warnings: Whether to filter verbose compiler warnings
            preserve_important_warnings: Whether to preserve important warnings
        """
        self.progress_context = progress_context
        self.filter_verbose_warnings = filter_verbose_warnings
        self.preserve_important_warnings = preserve_important_warnings
        self._filtered_count = 0
        self._preserved_count = 0
        self._in_verbose_block = False
        self._verbose_block_lines: list[str] = []
        self._blank_line_buffer: list[str] = []
        self._last_was_filtered = False
        self._preserve_next_context_lines = (
            0  # Counter for preserving context after important warnings
        )

        # Patterns that indicate verbose warning blocks to filter
        self.verbose_patterns = [
            # Only filter specific verbose note messages about macro expansion
            re.compile(r".*note: in expansion of macro.*"),
            re.compile(r".*note: in definition of macro.*"),
            # Filter verbose macro definitions
            re.compile(r".*#define DT_FOREACH_OKAY_INST.*fn\(\d+\).*"),
            re.compile(r".*#define UTIL_PRIMITIVE_CAT.*"),
            re.compile(r".*#define UTIL_CAT.*"),
            re.compile(r".*#define DT_INST\(.*"),
            re.compile(r".*#define DT_DRV_INST.*"),
            re.compile(r".*#define DT_INST_PROP.*"),
            re.compile(r".*#define __DEBRACKET.*"),
            re.compile(r".*#define __GET_ARG2_DEBRACKET.*"),
            re.compile(r".*#define __COND_CODE.*"),
            re.compile(r".*#define Z_COND_CODE_.*"),
            re.compile(r".*#define COND_CODE_.*"),
            re.compile(r".*#define DT_CAT3.*"),
            re.compile(r".*#define DT_PROP\(.*"),
            re.compile(r".*#define DT_N_S_macros.*"),  # Macro definitions
            re.compile(r".*#define DT_N_INST_\d+_.*"),  # Instance definitions
            # DO NOT filter lines with line numbers and pipes - these show the actual code!
            # DO NOT filter pointer lines with ^ - these show where the issue is!
            # DO NOT filter "note: this is the location" - these explain the issue!
        ]

        # Patterns for important warnings to always preserve
        self.important_patterns = [
            re.compile(r".*warning:.*redefined.*"),
            re.compile(r".*warning:.*deprecated.*"),
            re.compile(r".*warning:.*defined but not used.*"),
            re.compile(r".*error:.*"),
            re.compile(r".*Error:.*"),
            re.compile(r".*ERROR:.*"),
            re.compile(r".*failed.*"),
            re.compile(r".*Failed.*"),
            re.compile(r".*FAILED.*"),
        ]

        # Pattern to detect start of overflow warning blocks
        self.overflow_warning_start = re.compile(
            r".*warning: unsigned conversion from.*changes value from.*"
        )

    def _is_verbose_line(self, line: str) -> bool:
        """Check if a line is part of verbose compiler output."""
        if not self.filter_verbose_warnings:
            return False

        # Check if line matches any verbose pattern
        return any(pattern.match(line) for pattern in self.verbose_patterns)

    def _is_important_line(self, line: str) -> bool:
        """Check if a line contains important information to preserve."""
        if not self.preserve_important_warnings:
            return False

        # Check if line matches any important pattern
        return any(pattern.match(line) for pattern in self.important_patterns)

    def _flush_blank_buffer(self) -> list[str]:
        """Flush the blank line buffer and return its contents."""
        result = self._blank_line_buffer.copy()
        self._blank_line_buffer = []
        return result

    def process(self, line: str, stream_type: str) -> str:
        """Process a line of output and filter if needed.

        Args:
            line: Output line from the process
            stream_type: Either "stdout" or "stderr"

        Returns:
            The original line, empty string if filtered, or multiple lines if buffered blanks need output
        """
        # Check if this is a blank line
        is_blank = not line.strip()

        if is_blank:
            # If we just filtered content, buffer this blank line
            if self._last_was_filtered:
                self._blank_line_buffer.append(line)
                return ""  # Don't output yet
            else:
                # Normal blank line, output any buffered blanks first then this one
                buffered = self._flush_blank_buffer()
                if buffered:
                    return "\n".join(buffered) + "\n" + line
                return line

        # Check if we're preserving context lines after an important warning
        if self._preserve_next_context_lines > 0:
            self._preserve_next_context_lines -= 1
            self._preserved_count += 1
            self._last_was_filtered = False
            # Output any buffered blank lines before this context line
            buffered = self._flush_blank_buffer()
            if buffered:
                return "\n".join(buffered) + "\n" + line
            return line

        # Check for important lines that should always be preserved
        if self._is_important_line(line):
            self._preserved_count += 1
            # Reset verbose block tracking
            self._in_verbose_block = False
            self._verbose_block_lines = []
            self._last_was_filtered = False

            # Set counter to preserve next few lines for context (pointer lines, etc.)
            # Important warnings usually have 1-5 lines of context including notes
            self._preserve_next_context_lines = 5

            # Output any buffered blank lines before this important line
            buffered = self._flush_blank_buffer()
            if buffered:
                return "\n".join(buffered) + "\n" + line
            return line

        # Check if this starts an overflow warning block (but not if we're preserving context)
        if (
            self.overflow_warning_start.match(line)
            and self._preserve_next_context_lines == 0
        ):
            # Start tracking verbose block
            self._in_verbose_block = True
            self._verbose_block_lines = [line]
            self._filtered_count += 1
            self._last_was_filtered = True

            # Clear any buffered blank lines since we're filtering
            self._blank_line_buffer = []

            # Log summary periodically
            if self._filtered_count % 100 == 0:
                self.progress_context.log(
                    f"Filtered {self._filtered_count} verbose warning lines"
                )

            return ""  # Filter the line

        # If we're in a verbose block, check if it continues
        if self._in_verbose_block:
            # Check if this line is part of the verbose block
            # Include lines that are:
            # - More verbose patterns
            # - Code snippet lines (contain | and line numbers)
            # - Pointer/caret lines (contain ^ to point at code)
            # - Continuation of the warning context
            line_stripped = line.strip()

            # Check various patterns that indicate continuation of verbose block
            is_code_snippet = "|" in line and (
                line_stripped[0].isdigit() if line_stripped else False
            )
            is_pointer_line = "^" in line_stripped and (
                "~" in line_stripped or len(line_stripped) < 100
            )
            is_continuation = (
                self._is_verbose_line(line)
                or is_code_snippet
                or is_pointer_line
                or line_stripped.startswith("|")
                or (line.startswith(" ") and "|" in line)
                or (line.startswith(" ") and "^" in line)
            )

            if is_continuation:
                self._verbose_block_lines.append(line)
                self._filtered_count += 1
                self._last_was_filtered = True
                # Clear any buffered blank lines since we're still filtering
                self._blank_line_buffer = []
                return ""  # Filter the line
            else:
                # End of verbose block
                self._in_verbose_block = False
                self._verbose_block_lines = []
                # This line might be important, check it recursively
                return self.process(line, stream_type)

        # Check if this is a standalone verbose line (but not if we're preserving context)
        if self._is_verbose_line(line) and self._preserve_next_context_lines == 0:
            self._filtered_count += 1
            self._last_was_filtered = True

            # Clear any buffered blank lines since we're filtering
            self._blank_line_buffer = []

            # Log summary periodically
            if self._filtered_count % 100 == 0:
                self.progress_context.log(
                    f"Filtered {self._filtered_count} verbose warning lines"
                )

            return ""  # Filter the line

        # Default: preserve the line
        self._preserved_count += 1
        self._last_was_filtered = False

        # Output any buffered blank lines before this normal line
        buffered = self._flush_blank_buffer()
        if buffered:
            return "\n".join(buffered) + "\n" + line
        return line

    def get_statistics(self) -> dict[str, int]:
        """Get filtering statistics.

        Returns:
            Dictionary with filtered and preserved line counts
        """
        return {
            "filtered_lines": self._filtered_count,
            "preserved_lines": self._preserved_count,
            "total_lines": self._filtered_count + self._preserved_count,
        }

    def close(self) -> None:
        """Log final statistics when closing."""
        stats = self.get_statistics()
        if stats["total_lines"] > 0:
            filter_percentage = (stats["filtered_lines"] / stats["total_lines"]) * 100
            logger.debug(
                "Build output filter statistics: Filtered %d lines (%.1f%%), Preserved %d lines",
                stats["filtered_lines"],
                filter_percentage,
                stats["preserved_lines"],
            )

            # Update progress context with final stats
            if self._filtered_count > 0:
                self.progress_context.log(
                    f"Filtered {self._filtered_count} verbose warning lines from build output"
                )


def create_build_output_filter_middleware(
    progress_context: "ProgressContextProtocol",
    filter_verbose_warnings: bool = True,
    preserve_important_warnings: bool = True,
) -> BuildOutputFilterMiddleware:
    """Factory function to create a build output filter middleware.

    Args:
        progress_context: Progress context for status updates
        filter_verbose_warnings: Whether to filter verbose compiler warnings
        preserve_important_warnings: Whether to preserve important warnings

    Returns:
        BuildOutputFilterMiddleware instance

    Example:
        ```python
        from glovebox.utils.build_output_filter_middleware import create_build_output_filter_middleware
        from glovebox.utils.stream_process import create_chained_middleware

        # Create filter middleware
        filter_middleware = create_build_output_filter_middleware(progress_context)

        # Chain with other middleware
        middlewares = [filter_middleware, log_middleware]
        chained = create_chained_middleware(middlewares)

        # Use with Docker adapter
        result = docker_adapter.run_container("image", [], {}, middleware=chained)

        # Get statistics
        stats = filter_middleware.get_statistics()
        print(f"Filtered {stats['filtered_lines']} verbose warnings")
        ```
    """
    return BuildOutputFilterMiddleware(
        progress_context=progress_context,
        filter_verbose_warnings=filter_verbose_warnings,
        preserve_important_warnings=preserve_important_warnings,
    )
