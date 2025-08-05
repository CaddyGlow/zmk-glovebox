"""Startup services for application initialization."""

import logging
import threading
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from glovebox.config.user_config import UserConfig


logger = logging.getLogger(__name__)


class StartupService:
    """Service for handling application startup tasks."""

    def __init__(self, user_config: "UserConfig") -> None:
        """Initialize startup service.

        Args:
            user_config: User configuration instance
        """
        self.user_config = user_config
        self.logger = logging.getLogger(__name__)

    def run_startup_checks(self) -> None:
        """Run all startup checks and notifications in background threads."""
        # Run version checks in background threads to avoid blocking CLI startup
        zmk_thread = threading.Thread(
            target=self._check_zmk_updates, daemon=True, name="zmk-version-check"
        )
        glovebox_thread = threading.Thread(
            target=self._check_glovebox_updates,
            daemon=True,
            name="glovebox-version-check",
        )

        # Start both threads
        zmk_thread.start()
        glovebox_thread.start()

        # Don't wait for threads to complete - let them run in background
        self.logger.debug("Started background version check threads")

    def _check_zmk_updates(self) -> None:
        """Check for ZMK firmware updates and notify user if available."""
        try:
            from glovebox.core.version_check import create_zmk_version_checker

            version_checker = create_zmk_version_checker()
            result = version_checker.check_for_updates()

            if result.check_disabled:
                return

            if result.has_update and result.latest_version:
                print("\n[ZMK Firmware Update Available]")
                print(f"   Current: {result.current_version or 'unknown'}")
                print(f"   Latest:  {result.latest_version}")
                if result.latest_url:
                    print(f"   Details: {result.latest_url}")
                print(
                    "   To disable these checks: glovebox config set disable_version_checks true"
                )
                print()
            else:
                self.logger.debug("ZMK firmware is up to date")

        except Exception as e:
            # Silently fail for version checks - don't interrupt user workflow
            self.logger.debug("Failed to check for ZMK updates: %s", e)

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

                print("\n[Glovebox Update Available]")
                print(f"   Current: {result.current_version or 'unknown'}")
                print(f"   Latest:  {result.latest_version}")
                if result.latest_url:
                    print(f"   Details: {result.latest_url}")
                print(f"   Update:  {update_command}")
                print(
                    "   To disable these checks: glovebox config set disable_version_checks true"
                )
                print()
            else:
                self.logger.debug("Glovebox is up to date")

        except Exception as e:
            # Silently fail for version checks - don't interrupt user workflow
            self.logger.debug("Failed to check for Glovebox updates: %s", e)


def create_startup_service(user_config: "UserConfig") -> StartupService:
    """Factory function to create startup service.

    Args:
        user_config: User configuration instance

    Returns:
        Configured StartupService instance
    """
    return StartupService(user_config)
