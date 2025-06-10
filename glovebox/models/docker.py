"""Docker-specific models for cross-domain operations."""

import os
import platform
from typing import ClassVar

from pydantic import BaseModel, Field, field_validator


class DockerUserContext(BaseModel):
    """Docker user context for volume permission handling.

    Represents user information needed for Docker --user flag to
    solve volume permission issues when mounting host directories.
    """

    uid: int = Field(..., description="User ID for Docker --user flag")
    gid: int = Field(..., description="Group ID for Docker --user flag")
    username: str = Field(..., description="Username for reference")
    enable_user_mapping: bool = Field(
        default=True, description="Whether to enable --user flag in Docker commands"
    )

    # Platform compatibility
    _supported_platforms: ClassVar[set[str]] = {"Linux", "Darwin"}

    @field_validator("uid", "gid")
    @classmethod
    def validate_positive_ids(cls, v: int) -> int:
        """Validate that UID/GID are positive integers."""
        if v < 0:
            raise ValueError("UID and GID must be non-negative")
        return v

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username is not empty."""
        if not v or not v.strip():
            raise ValueError("Username cannot be empty")
        return v.strip()

    @classmethod
    def detect_current_user(cls) -> "DockerUserContext":
        """Detect current user context from system.

        Returns:
            DockerUserContext: Current user's context

        Raises:
            RuntimeError: If user detection fails or platform unsupported
        """
        current_platform = platform.system()

        if current_platform not in cls._supported_platforms:
            raise RuntimeError(
                f"User detection not supported on {current_platform}. "
                f"Supported platforms: {', '.join(cls._supported_platforms)}"
            )

        try:
            uid = os.getuid()
            gid = os.getgid()
            username = os.getenv("USER") or os.getenv("USERNAME") or "unknown"

            return cls(uid=uid, gid=gid, username=username, enable_user_mapping=True)

        except AttributeError as e:
            raise RuntimeError(
                f"Failed to detect user on {current_platform}: {e}"
            ) from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error detecting user: {e}") from e

    def get_docker_user_flag(self) -> str:
        """Get Docker --user flag value.

        Returns:
            str: Docker user flag in format "uid:gid"
        """
        return f"{self.uid}:{self.gid}"

    def is_supported_platform(self) -> bool:
        """Check if current platform supports user mapping.

        Returns:
            bool: True if platform supports user mapping
        """
        return platform.system() in self._supported_platforms

    def should_use_user_mapping(self) -> bool:
        """Check if user mapping should be used.

        Returns:
            bool: True if user mapping is enabled and platform is supported
        """
        return self.enable_user_mapping and self.is_supported_platform()


__all__ = ["DockerUserContext"]
