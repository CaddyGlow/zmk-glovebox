"""Startup services for application initialization."""

import logging
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
        """Run all startup checks and notifications."""
        self._check_zmk_updates()

    def _check_zmk_updates(self) -> None:
        """Check for ZMK firmware updates and notify user if available."""
        try:
            from glovebox.core.version_check import create_zmk_version_checker

            version_checker = create_zmk_version_checker()
            result = version_checker.check_for_updates()

            if result.check_disabled:
                self.logger.debug("ZMK version checks are disabled")
                return

            if result.has_update and result.latest_version:
                print("\n🔄 ZMK Firmware Update Available!")
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


def create_startup_service(user_config: "UserConfig") -> StartupService:
    """Factory function to create startup service.

    Args:
        user_config: User configuration instance

    Returns:
        Configured StartupService instance
    """
    return StartupService(user_config)
