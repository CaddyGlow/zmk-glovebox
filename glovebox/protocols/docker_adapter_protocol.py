"""Protocol definition for Docker operations."""

from pathlib import Path
from typing import Any, Protocol, TypeAlias, TypeVar, runtime_checkable

from glovebox.models.docker import DockerUserContext
from glovebox.utils.stream_process import OutputMiddleware, ProcessResult, T


# Type aliases for Docker operations
DockerVolume: TypeAlias = tuple[str, str]  # (host_path, container_path)
DockerEnv: TypeAlias = dict[str, str]  # Environment variables
DockerResult: TypeAlias = tuple[
    int, list[str], list[str]
]  # (return_code, stdout, stderr)


# TODO: add get_version, image_info,
@runtime_checkable
class DockerAdapterProtocol(Protocol):
    """Protocol for Docker operations."""

    def is_available(self) -> bool:
        """Check if Docker is available on the system.

        Returns:
            True if Docker is available, False otherwise
        """
        ...

    def run_container(
        self,
        image: str,
        volumes: list[DockerVolume],
        environment: DockerEnv,
        command: list[str] | None = None,
        middleware: OutputMiddleware[T] | None = None,
        user_context: DockerUserContext | None = None,
        entrypoint: str | None = None,
    ) -> ProcessResult[T]:
        """Run a Docker container with specified configuration.

        Args:
            image: Docker image name/tag to run
            volumes: List of volume mounts (host_path, container_path)
            environment: Dictionary of environment variables
            command: Optional command to run in the container
            middleware: Optional middleware for processing output
            user_context: Optional user context for Docker --user flag
            entrypoint: Optional custom entrypoint to override the image's default

        Returns:
            Tuple containing (return_code, stdout_lines, stderr_lines)

        Raises:
            DockerError: If the container fails to run
        """
        ...

    def build_image(
        self,
        dockerfile_dir: Path,
        image_name: str,
        image_tag: str = "latest",
        no_cache: bool = False,
        middleware: OutputMiddleware[T] | None = None,
    ) -> ProcessResult[T]:
        """Build a Docker image from a Dockerfile.

        Args:
            dockerfile_dir: Directory containing the Dockerfile
            image_name: Name to tag the built image with
            image_tag: Tag to use for the image
            no_cache: Whether to use Docker's cache during build
            middleware: Optional middleware for processing output

        Returns:
            ProcessResult containing (return_code, stdout_lines, stderr_lines)

        Raises:
            DockerError: If the image fails to build
        """
        ...

    def image_exists(self, image_name: str, image_tag: str = "latest") -> bool:
        """Check if a Docker image exists locally.

        Args:
            image_name: Name of the image to check
            image_tag: Tag of the image to check

        Returns:
            True if the image exists locally, False otherwise
        """
        ...

    def pull_image(
        self,
        image_name: str,
        image_tag: str = "latest",
        middleware: OutputMiddleware[T] | None = None,
    ) -> ProcessResult[T]:
        """Pull a Docker image from registry.

        Args:
            image_name: Name of the image to pull
            image_tag: Tag of the image to pull
            middleware: Optional middleware for processing output

        Returns:
            ProcessResult containing (return_code, stdout_lines, stderr_lines)

        Raises:
            DockerError: If the image fails to pull
        """
        ...
