"""User context manager for Docker volume permission handling."""

import logging
import platform

from glovebox.core.errors import GloveboxError
from glovebox.models.docker import DockerUserContext


logger = logging.getLogger(__name__)


class UserContextManagerError(GloveboxError):
    """Error in user context management."""


class UserContextManager:
    """Manage user context detection for Docker operations.

    Provides platform-aware user context detection and configuration
    management for Docker volume permission handling.
    """

    def __init__(self) -> None:
        """Initialize user context manager."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def get_user_context(
        self, enable_user_mapping: bool = True, detect_automatically: bool = True
    ) -> DockerUserContext | None:
        """Get user context for Docker operations.

        Args:
            enable_user_mapping: Whether to enable user mapping
            detect_automatically: Whether to auto-detect user context

        Returns:
            DockerUserContext | None: User context if available and enabled

        Raises:
            UserContextManagerError: If detection fails when auto-detection enabled
        """
        if not enable_user_mapping:
            self.logger.debug("User mapping disabled, returning None")
            return None

        if not detect_automatically:
            self.logger.debug("Auto-detection disabled, returning None")
            return None

        try:
            user_context = DockerUserContext.detect_current_user()
            user_context.enable_user_mapping = enable_user_mapping

            self.logger.info(
                "Detected user context: %s (UID=%d, GID=%d)",
                user_context.username,
                user_context.uid,
                user_context.gid,
            )
            return user_context

        except RuntimeError as e:
            self.logger.warning("User context detection failed: %s", e)
            if platform.system() in DockerUserContext._supported_platforms:
                # Only raise error on supported platforms
                raise UserContextManagerError(f"User detection failed: {e}") from e
            else:
                # On unsupported platforms, just log and return None
                self.logger.info("User mapping not supported on %s", platform.system())
                return None

        except Exception as e:
            msg = f"Unexpected error during user detection: {e}"
            self.logger.error(msg)
            raise UserContextManagerError(msg) from e

    def create_user_context(
        self, uid: int, gid: int, username: str, enable_user_mapping: bool = True
    ) -> DockerUserContext:
        """Create user context manually.

        Args:
            uid: User ID
            gid: Group ID
            username: Username
            enable_user_mapping: Whether to enable user mapping

        Returns:
            DockerUserContext: Created user context

        Raises:
            UserContextManagerError: If user context creation fails
        """
        try:
            user_context = DockerUserContext(
                uid=uid,
                gid=gid,
                username=username,
                enable_user_mapping=enable_user_mapping,
            )

            self.logger.debug(
                "Created user context: %s (UID=%d, GID=%d)", username, uid, gid
            )
            return user_context

        except Exception as e:
            msg = f"Failed to create user context: {e}"
            self.logger.error(msg)
            raise UserContextManagerError(msg) from e

    def is_user_mapping_supported(self) -> bool:
        """Check if user mapping is supported on current platform.

        Returns:
            bool: True if user mapping is supported
        """
        current_platform = platform.system()
        supported = current_platform in DockerUserContext._supported_platforms

        self.logger.debug(
            "Platform %s user mapping support: %s", current_platform, supported
        )
        return supported

    def get_platform_info(self) -> dict[str, str]:
        """Get platform information for debugging.

        Returns:
            dict[str, str]: Platform information
        """
        return {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "user_mapping_supported": str(self.is_user_mapping_supported()),
        }


def create_user_context_manager() -> UserContextManager:
    """Create user context manager instance.

    Returns:
        UserContextManager: New user context manager
    """
    return UserContextManager()


__all__ = [
    "UserContextManager",
    "UserContextManagerError",
    "create_user_context_manager",
]
