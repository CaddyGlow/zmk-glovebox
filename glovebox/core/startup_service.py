"""Startup services for application initialization."""

import atexit
import contextlib
import logging
import sys
import threading
from typing import TYPE_CHECKING

from rich.console import Console
from rich.text import Text

from glovebox.core.structlog_logger import get_struct_logger


if TYPE_CHECKING:
    from glovebox.config.user_config import UserConfig


logger = get_struct_logger(__name__)

# Keep track of background threads
_background_threads: list[threading.Thread] = []

# Console for thread-safe output
_console = Console(stderr=False)


class StartupService:
    """Service for handling application startup tasks."""

    def __init__(self, user_config: "UserConfig") -> None:
        """Initialize startup service.

        Args:
            user_config: User configuration instance
        """
        self.user_config = user_config
        self.logger = get_struct_logger(__name__)

    def run_startup_checks(self) -> None:
        """Run all startup checks and notifications in background threads."""
        # Run version checks in background threads to avoid blocking CLI startup
        zmk_thread = threading.Thread(
            target=self._safe_check_zmk_updates, daemon=True, name="zmk-version-check"
        )
        glovebox_thread = threading.Thread(
            target=self._safe_check_glovebox_updates,
            daemon=True,
            name="glovebox-version-check",
        )

        # Keep track of threads
        global _background_threads
        _background_threads.extend([zmk_thread, glovebox_thread])

        # Start both threads
        zmk_thread.start()
        glovebox_thread.start()

        # Don't wait for threads to complete - let them run in background
        self.logger.debug("background_threads_started", thread_count=2)

    def _safe_check_zmk_updates(self) -> None:
        """Safely check for ZMK updates, handling stdout issues during shutdown."""
        with contextlib.suppress(Exception):
            # Silently ignore errors during shutdown
            self._check_zmk_updates()

    def _safe_check_glovebox_updates(self) -> None:
        """Safely check for Glovebox updates, handling stdout issues during shutdown."""
        with contextlib.suppress(Exception):
            # Silently ignore errors during shutdown
            self._check_glovebox_updates()

    def _check_zmk_updates(self) -> None:
        """Check for ZMK firmware updates and notify user if available."""
        try:
            from glovebox.core.version_check import create_zmk_version_checker

            version_checker = create_zmk_version_checker()
            result = version_checker.check_for_updates()

            if result.check_disabled:
                return

            if result.has_update and result.latest_version:
                try:
                    # Build single-line notification
                    message = Text()
                    message.append("[ZMK Update] ", style="bold cyan")
                    message.append(
                        f"{result.current_version or 'unknown'}", style="dim"
                    )
                    message.append(" → ", style="dim")
                    message.append(f"{result.latest_version}", style="green")
                    if result.latest_url:
                        message.append(" • ", style="dim")
                        message.append(f"{result.latest_url}", style="blue underline")

                    _console.print()
                    _console.print(message)
                except Exception:
                    # Ignore errors writing to stdout during shutdown
                    pass
            else:
                self.logger.debug(
                    "zmk_firmware_up_to_date", current_version=result.current_version
                )

        except Exception as e:
            # Silently fail for version checks - don't interrupt user workflow
            self.logger.debug("zmk_update_check_failed", error=str(e))

    def _check_glovebox_updates(self) -> None:
        """Check for Glovebox application updates and notify user if available."""
        try:
            from glovebox.core.version_check import create_glovebox_version_checker
            from glovebox.utils.installation import (
                detect_installation_method,
                get_update_command,
            )

            version_checker = create_glovebox_version_checker(self.user_config)
            result = version_checker.check_for_updates()

            if result.check_disabled:
                return

            if result.has_update and result.latest_version:
                # Detect installation method and get appropriate update command
                install_method = detect_installation_method()
                update_command = get_update_command(install_method)

                try:
                    # Build single-line notification
                    message = Text()
                    message.append("[Glovebox Update] ", style="bold green")
                    message.append(
                        f"{result.current_version or 'unknown'}", style="dim"
                    )
                    message.append(" → ", style="dim")
                    message.append(f"{result.latest_version}", style="green")
                    message.append(" • ", style="dim")
                    message.append(f"{update_command}", style="bold yellow")

                    _console.print()
                    _console.print(message)
                except Exception:
                    # Ignore errors writing to stdout during shutdown
                    pass
            else:
                self.logger.debug(
                    "glovebox_up_to_date", current_version=result.current_version
                )

        except Exception as e:
            # Silently fail for version checks - don't interrupt user workflow
            self.logger.debug("glovebox_update_check_failed", error=str(e))


def _cleanup_threads() -> None:
    """Cleanup function to ensure background threads complete before exit."""
    global _background_threads
    # Give threads a brief moment to complete
    for thread in _background_threads:
        if thread.is_alive():
            thread.join(timeout=0.1)  # Very short timeout
    _background_threads.clear()


# Register cleanup function
atexit.register(_cleanup_threads)


def create_startup_service(user_config: "UserConfig") -> StartupService:
    """Factory function to create startup service.

    Args:
        user_config: User configuration instance

    Returns:
        Configured StartupService instance
    """
    return StartupService(user_config)
