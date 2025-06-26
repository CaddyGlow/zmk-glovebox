"""Shared utilities for cache CLI commands."""

import logging
from pathlib import Path
from typing import Any

from rich.console import Console

from glovebox.cli.helpers.theme import Icons
from glovebox.cli.workspace_display_utils import format_size, get_directory_size
from glovebox.compilation.cache import (
    ZmkWorkspaceCacheService,
    create_compilation_cache_service,
)
from glovebox.config.user_config import UserConfig, create_user_config
from glovebox.core.cache.cache_manager import CacheManager


logger = logging.getLogger(__name__)


def get_cache_manager_and_service(
    session_metrics: Any = None,
) -> tuple[CacheManager, ZmkWorkspaceCacheService, UserConfig]:
    """Get cache manager and workspace cache service using factory functions."""
    user_config = create_user_config()
    cache_manager, workspace_cache_service, _ = create_compilation_cache_service(
        user_config, session_metrics=session_metrics
    )
    return cache_manager, workspace_cache_service, user_config


def get_cache_manager() -> CacheManager:
    """Get cache manager using user config (backward compatibility)."""
    cache_manager, _, _ = get_cache_manager_and_service()
    return cache_manager


def format_size_display(size_bytes: float) -> str:
    """Format size in human readable format (backward compatibility alias)."""
    return format_size(size_bytes)


def get_directory_size_bytes(path: Path) -> int:
    """Get total size of directory in bytes (backward compatibility alias)."""
    return get_directory_size(path)


def get_console() -> Console:
    """Get a Rich console instance."""
    return Console()


def format_icon_with_message(icon_name: str, message: str, icon_mode: str = "emoji") -> str:
    """Format message with icon using the theme system."""
    return Icons.format_with_icon(icon_name, message, icon_mode)


def get_icon(icon_name: str, icon_mode: str = "emoji") -> str:
    """Get icon from the theme system."""
    return Icons.get_icon(icon_name, icon_mode)


def log_error_with_debug_stack(logger_instance: logging.Logger, message: str, exception: Exception) -> None:
    """Log error with debug-aware stack trace following CLAUDE.md pattern."""
    exc_info = logger_instance.isEnabledFor(logging.DEBUG)
    logger_instance.error(message, exception, exc_info=exc_info)
