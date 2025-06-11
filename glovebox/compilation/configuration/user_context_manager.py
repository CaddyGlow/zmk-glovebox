"""User context manager for Docker volume permission handling."""

import logging
import platform
from pathlib import Path
from typing import TYPE_CHECKING, Any

from glovebox.core.errors import GloveboxError
from glovebox.models.docker import DockerUserContext


if TYPE_CHECKING:
    from glovebox.config.models.firmware import FirmwareDockerConfig


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
        self,
        enable_user_mapping: bool = True,
        detect_automatically: bool = True,
        docker_config: "FirmwareDockerConfig | None" = None,
        manual_uid: int | None = None,
        manual_gid: int | None = None,
        manual_username: str | None = None,
        host_home_dir: Path | str | None = None,
        container_home_dir: str | None = None,
        detection_source: str = "auto",
    ) -> DockerUserContext | None:
        """Get user context for Docker operations with flexible override support.

        Args:
            enable_user_mapping: Whether to enable user mapping
            detect_automatically: Whether to auto-detect user context
            docker_config: Docker configuration with manual overrides
            manual_uid: Manual UID override (takes precedence over config)
            manual_gid: Manual GID override (takes precedence over config)
            manual_username: Manual username override (takes precedence over config)
            host_home_dir: Host home directory override (takes precedence over config)
            container_home_dir: Container home directory override (takes precedence over config)
            detection_source: Source identifier for debugging

        Returns:
            DockerUserContext | None: User context if available and enabled

        Raises:
            UserContextManagerError: If detection fails when auto-detection enabled
        """
        # Check if user mapping is enabled (config overrides parameter)
        effective_enable_mapping = enable_user_mapping
        effective_detect_auto = detect_automatically

        if docker_config:
            effective_enable_mapping = docker_config.enable_user_mapping
            effective_detect_auto = docker_config.detect_automatically
            # Update detection source if using config
            if detection_source == "auto":
                detection_source = "config"

        if not effective_enable_mapping:
            self.logger.debug("User mapping disabled, returning None")
            return None

        # Resolve manual overrides with precedence: CLI params > config > None
        resolved_uid = self._resolve_manual_override(
            manual_uid, docker_config.manual_uid if docker_config else None, "UID"
        )
        resolved_gid = self._resolve_manual_override(
            manual_gid, docker_config.manual_gid if docker_config else None, "GID"
        )
        resolved_username = self._resolve_manual_override(
            manual_username,
            docker_config.manual_username if docker_config else None,
            "username",
        )
        resolved_host_home = self._resolve_manual_override(
            host_home_dir,
            docker_config.host_home_dir if docker_config else None,
            "host_home_dir",
        )
        resolved_container_home = self._resolve_manual_override(
            container_home_dir,
            docker_config.container_home_dir if docker_config else None,
            "container_home_dir",
            default="/tmp",
        )

        # Check if we have enough manual overrides to skip auto-detection
        has_manual_overrides = (
            resolved_uid is not None
            and resolved_gid is not None
            and resolved_username is not None
        )

        force_manual = docker_config.force_manual if docker_config else False

        if has_manual_overrides and (force_manual or not effective_detect_auto):
            # Create manual user context - we know these are not None due to has_manual_overrides check
            assert resolved_uid is not None
            assert resolved_gid is not None
            assert resolved_username is not None

            self.logger.info(
                "Using manual user context: UID=%d, GID=%d, username=%s",
                resolved_uid,
                resolved_gid,
                resolved_username,
            )
            return DockerUserContext.create_manual(
                uid=resolved_uid,
                gid=resolved_gid,
                username=resolved_username,
                host_home_dir=resolved_host_home,
                container_home_dir=resolved_container_home,
                enable_user_mapping=effective_enable_mapping,
                detection_source="manual" if force_manual else detection_source,
            )

        # Auto-detection with optional overrides
        if not effective_detect_auto:
            self.logger.debug(
                "Auto-detection disabled and no manual overrides, returning None"
            )
            return None

        try:
            # Auto-detect with home directory overrides
            user_context = DockerUserContext.detect_current_user(
                host_home_dir=resolved_host_home,
                container_home_dir=resolved_container_home,
            )
            user_context.enable_user_mapping = effective_enable_mapping

            # Apply any manual overrides to auto-detected context
            if resolved_uid is not None:
                user_context.uid = resolved_uid
                user_context.manual_override = True
                user_context.detection_source = "mixed"
            if resolved_gid is not None:
                user_context.gid = resolved_gid
                user_context.manual_override = True
                user_context.detection_source = "mixed"
            if resolved_username is not None:
                user_context.username = resolved_username
                user_context.manual_override = True
                user_context.detection_source = "mixed"

            self.logger.info(
                "User context resolved: %s", user_context.describe_context()
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

    def _resolve_manual_override(
        self, cli_value: Any, config_value: Any, param_name: str, default: Any = None
    ) -> Any:
        """Resolve manual override with precedence: CLI > config > default.

        Args:
            cli_value: Value from CLI parameters (highest precedence)
            config_value: Value from configuration file
            param_name: Parameter name for logging
            default: Default value if no overrides provided

        Returns:
            Resolved value with proper precedence
        """
        if cli_value is not None:
            self.logger.debug("Using CLI override for %s: %s", param_name, cli_value)
            return cli_value
        elif config_value is not None:
            self.logger.debug(
                "Using config override for %s: %s", param_name, config_value
            )
            return config_value
        else:
            if default is not None:
                self.logger.debug("Using default for %s: %s", param_name, default)
            return default

    def create_user_context_from_config(
        self, docker_config: "FirmwareDockerConfig", **cli_overrides: Any
    ) -> DockerUserContext | None:
        """Create user context from configuration with CLI overrides.

        Args:
            docker_config: Docker configuration
            **cli_overrides: CLI parameter overrides

        Returns:
            DockerUserContext | None: Created user context or None if disabled
        """
        return self.get_user_context(
            docker_config=docker_config, detection_source="config", **cli_overrides
        )

    def create_user_context(
        self,
        uid: int,
        gid: int,
        username: str,
        enable_user_mapping: bool = True,
        host_home_dir: Path | str | None = None,
        container_home_dir: str = "/tmp",
    ) -> DockerUserContext:
        """Create user context manually.

        Args:
            uid: User ID
            gid: Group ID
            username: Username
            enable_user_mapping: Whether to enable user mapping
            host_home_dir: Host home directory to map into container
            container_home_dir: Container home directory path

        Returns:
            DockerUserContext: Created user context

        Raises:
            UserContextManagerError: If user context creation fails
        """
        try:
            user_context = DockerUserContext.create_manual(
                uid=uid,
                gid=gid,
                username=username,
                host_home_dir=host_home_dir,
                container_home_dir=container_home_dir,
                enable_user_mapping=enable_user_mapping,
                detection_source="manual",
            )

            self.logger.debug(
                "Created manual user context: %s", user_context.describe_context()
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
