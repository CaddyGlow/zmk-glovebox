"""Workspace-specific progress integration for cache operations."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from glovebox.cli.progress import (
    create_progress_context,
    create_progress_display,
)
from glovebox.cli.progress.models import ProgressDisplayType


def create_workspace_cache_progress(
    operation_type: str = "workspace_cache",
    show_logs: bool = True,
    log_panel_height: int = 12,
    repository: str | None = None,
) -> tuple[Any, Callable[[Any], None]]:
    """Create progress display and callback for workspace cache operations.

    Args:
        operation_type: Type of workspace operation
        show_logs: Whether to show scrollable logs
        log_panel_height: Height of log panel
        repository: Repository being processed (for logging context)

    Returns:
        Tuple of (display, progress_callback)
    """
    logger = logging.getLogger("glovebox.workspace.cache")

    # Create context with scrollable logs for workspace operations
    context = create_progress_context(
        strategy="workspace_cache",
        display_enabled=True,
        show_logs=show_logs,
        log_panel_height=log_panel_height,
        max_log_lines=100,
        operation_type=operation_type,
        total_stages=4,  # Typical: check, extract, copy, verify
    )

    # Use staged display with logs for maximum visibility
    context.display_config.display_type = ProgressDisplayType.STAGED_WITH_LOGS

    # Create display
    display = create_progress_display(context)

    def workspace_progress_callback(copy_progress: Any) -> None:
        """Convert workspace copy progress to scrollable logs.

        This callback bridges the existing CopyProgress objects from
        workspace cache service to the new scrollable logs display.
        """
        try:
            # Extract progress information
            current_file = getattr(copy_progress, "current_file", "")
            component_name = getattr(copy_progress, "component_name", "")
            files_processed = getattr(copy_progress, "files_processed", 0)
            total_files = getattr(copy_progress, "total_files", 0)
            bytes_copied = getattr(copy_progress, "bytes_copied", 0)
            total_bytes = getattr(copy_progress, "total_bytes", 0)

            # Log current file being copied
            if current_file:
                # Extract just the filename for cleaner display
                filename = (
                    current_file.split("/")[-1] if "/" in current_file else current_file
                )

                if component_name:
                    logger.info(f"📁 {component_name}: {filename}")
                else:
                    logger.info(f"📄 Copying: {filename}")

            # Log component progress
            if component_name and files_processed > 0:
                logger.debug(
                    f"🔄 {component_name}: {files_processed}/{total_files} files"
                )

            # Log overall progress periodically
            if total_files > 0 and files_processed % 10 == 0:  # Every 10 files
                percentage = (files_processed / total_files) * 100
                if total_bytes > 0:
                    mb_copied = bytes_copied / (1024 * 1024)
                    mb_total = total_bytes / (1024 * 1024)
                    logger.info(
                        f"📊 Progress: {percentage:.1f}% ({mb_copied:.1f}/{mb_total:.1f} MB)"
                    )
                else:
                    logger.info(
                        f"📊 Progress: {files_processed}/{total_files} files ({percentage:.1f}%)"
                    )

        except Exception as e:
            # Don't let progress callback errors break the operation
            logger.debug(f"Progress callback error: {e}")

    return display, workspace_progress_callback


def create_early_workspace_display(
    operation_name: str = "Workspace Setup", repository: str | None = None
) -> Any:
    """Create early workspace display for application startup.

    This creates a minimal progress display that can be shown early
    in the application lifecycle to give immediate feedback.

    Args:
        operation_name: Name of the operation being performed
        repository: Repository context if available

    Returns:
        Progress display that can be used with context manager
    """
    logger = logging.getLogger("glovebox.startup")

    # Create simple context for early display
    context = create_progress_context(
        strategy="startup",
        display_enabled=True,
        show_logs=True,
        log_panel_height=10,
        max_log_lines=50,
        operation_type="startup",
        total_stages=3,  # Typical: init, cache check, ready
    )

    context.display_config.display_type = ProgressDisplayType.STAGED_WITH_LOGS
    display = create_progress_display(context)

    # Log startup context
    logger.info(f"🚀 Starting {operation_name}")
    if repository:
        logger.info(f"📦 Repository: {repository}")

    return display


__all__ = [
    "create_workspace_cache_progress",
    "create_early_workspace_display",
]
