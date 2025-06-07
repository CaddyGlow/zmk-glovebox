"""Protocol definition for Docker operations."""

from pathlib import Path
from typing import Any, Protocol, TypeAlias, runtime_checkable


# Type aliases for Docker operations
DockerVolume: TypeAlias = tuple[str, str]  # (host_path, container_path)
DockerEnv: TypeAlias = dict[str, str]  # Environment variables
DockerResult: TypeAlias = tuple[
    int, list[str], list[str]
]  # (return_code, stdout, stderr)


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
        middleware: Any | None = None,
    ) -> DockerResult:
        """Run a Docker container with specified configuration.

        Args:
            image: Docker image name/tag to run
            volumes: List of volume mounts (host_path, container_path)
            environment: Dictionary of environment variables
            command: Optional command to run in the container
            middleware: Optional middleware for processing output

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
    ) -> bool:
        """Build a Docker image from a Dockerfile.

        Args:
            dockerfile_dir: Directory containing the Dockerfile
            image_name: Name to tag the built image with
            image_tag: Tag to use for the image
            no_cache: Whether to use Docker's cache during build

        Returns:
            True if the image was built successfully

        Raises:
            DockerError: If the image fails to build
        """
        ...
