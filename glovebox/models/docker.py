"""Docker-specific models for cross-domain operations."""

import os
import platform
from pathlib import Path
from typing import ClassVar

from pydantic import Field, field_validator

from glovebox.models.base import GloveboxBaseModel


class DockerUserContext(GloveboxBaseModel):
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

    # Home directory settings
    host_home_dir: Path | None = Field(
        default=None, description="Host home directory to map into container"
    )
    container_home_dir: str = Field(
        default="/tmp", description="Home directory path inside container"
    )

    # Source tracking for debugging
    manual_override: bool = Field(
        default=False,
        description="Whether this context was manually specified vs auto-detected",
    )
    detection_source: str = Field(
        default="auto",
        description="Source of user context: 'auto', 'manual', 'config', 'env'",
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

    @field_validator("host_home_dir", mode="before")
    @classmethod
    def expand_host_home_dir(cls, v: str | Path | None) -> Path | None:
        """Expand user home and environment variables in host home directory."""
        if v is None:
            return None
        path = Path(v).expanduser()
        return path.resolve() if path.exists() else path

    @field_validator("container_home_dir")
    @classmethod
    def validate_container_home_dir(cls, v: str) -> str:
        """Validate container home directory is absolute path."""
        if not v.startswith("/"):
            raise ValueError("Container home directory must be an absolute path")
        return v

    @field_validator("detection_source")
    @classmethod
    def validate_detection_source(cls, v: str) -> str:
        """Validate detection source is a known value."""
        valid_sources = {"auto", "manual", "config", "env", "cli"}
        if v not in valid_sources:
            raise ValueError(f"Detection source must be one of {valid_sources}")
        return v

    @classmethod
    def detect_current_user(
        cls, host_home_dir: Path | str | None = None, container_home_dir: str = "/tmp"
    ) -> "DockerUserContext":
        """Detect current user context from system.

        Args:
            host_home_dir: Optional host home directory override
            container_home_dir: Container home directory path

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

            # Use provided host home directory or detect from environment
            if host_home_dir is None:
                host_home_env = os.getenv("HOME")
                host_home_dir = Path(host_home_env) if host_home_env else None

            return cls(
                uid=uid,
                gid=gid,
                username=username,
                enable_user_mapping=True,
                host_home_dir=Path(host_home_dir)
                if isinstance(host_home_dir, str)
                else host_home_dir,
                container_home_dir=container_home_dir,
                manual_override=False,
                detection_source="auto",
            )

        except AttributeError as e:
            raise RuntimeError(
                f"Failed to detect user on {current_platform}: {e}"
            ) from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error detecting user: {e}") from e

    @classmethod
    def create_manual(
        cls,
        uid: int,
        gid: int,
        username: str,
        host_home_dir: Path | str | None = None,
        container_home_dir: str = "/tmp",
        enable_user_mapping: bool = True,
        detection_source: str = "manual",
    ) -> "DockerUserContext":
        """Create manual user context with custom values.

        Args:
            uid: User ID for Docker --user flag
            gid: Group ID for Docker --user flag
            username: Username for reference
            host_home_dir: Host home directory to map into container
            container_home_dir: Home directory path inside container
            enable_user_mapping: Whether to enable --user flag in Docker commands
            detection_source: Source of user context for debugging

        Returns:
            DockerUserContext: Manual user context

        Raises:
            ValueError: If validation fails for any parameter
        """
        return cls(
            uid=uid,
            gid=gid,
            username=username,
            enable_user_mapping=enable_user_mapping,
            host_home_dir=Path(host_home_dir)
            if isinstance(host_home_dir, str)
            else host_home_dir,
            container_home_dir=container_home_dir,
            manual_override=True,
            detection_source=detection_source,
        )

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

    def get_home_environment(self) -> dict[str, str]:
        """Get environment variables for home directory configuration.

        Returns:
            dict[str, str]: Environment variables to set in container
        """
        env = {}
        if self.container_home_dir:
            env["HOME"] = self.container_home_dir
        return env

    def get_home_volumes(self) -> list[tuple[str, str]]:
        """Get Docker volume mappings for home directory.

        Returns:
            list[tuple[str, str]]: List of (host_path, container_path) tuples
        """
        volumes = []
        if self.host_home_dir and self.container_home_dir:
            volumes.append((str(self.host_home_dir), self.container_home_dir))
        return volumes

    def describe_context(self) -> str:
        """Get human-readable description of user context.

        Returns:
            str: Description of user context for debugging
        """
        parts = [
            f"uid={self.uid}",
            f"gid={self.gid}",
            f"username={self.username}",
            f"source={self.detection_source}",
        ]

        if self.manual_override:
            parts.append("manual")

        if self.host_home_dir:
            parts.append(f"host_home={self.host_home_dir}")

        if self.container_home_dir != "/tmp":
            parts.append(f"container_home={self.container_home_dir}")

        return f"DockerUserContext({', '.join(parts)})"


__all__ = ["DockerUserContext"]
