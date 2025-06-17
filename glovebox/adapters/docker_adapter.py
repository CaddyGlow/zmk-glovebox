"""Docker adapter for container operations."""

import datetime
import hashlib
import logging
import shlex
import subprocess
from pathlib import Path
from typing import cast

from glovebox.models.docker import DockerUserContext
from glovebox.protocols.docker_adapter_protocol import (
    DockerAdapterProtocol,
    DockerEnv,
    DockerVolume,
)
from glovebox.utils.error_utils import create_docker_error
from glovebox.utils.stream_process import (
    OutputMiddleware,
    ProcessResult,
    T,
)


logger = logging.getLogger(__name__)


class LoggerOutputMiddleware(OutputMiddleware[str]):
    """Simple middleware that prints output with optional prefixes.

    This middleware prints each line to the console with configurable
    prefixes for stdout and stderr streams.
    """

    def __init__(
        self, logger: logging.Logger, stdout_prefix: str = "", stderr_prefix: str = ""
    ):
        """Initialize middleware with custom prefixes.

        Args:
            stdout_prefix: Prefix for stdout lines (default: "")
            stderr_prefix: Prefix for stderr lines (default: "")
        """
        self.logger = logger
        self.stderr_prefix = stderr_prefix
        self.stdout_prefix = stdout_prefix

    def process(self, line: str, stream_type: str) -> str:
        """Process and print a line with the appropriate prefix.

        Args:
            line: Output line to process
            stream_type: Either "stdout" or "stderr"

        Returns:
            The original line (unmodified)
        """
        if stream_type == "stdout":
            logger.debug(f"{self.stdout_prefix}{line}")
        else:
            logger.warning(f"{self.stderr_prefix}{line}")
        return line


class DockerAdapter:
    """Implementation of Docker adapter."""

    def is_available(self) -> bool:
        """Check if Docker is available on the system."""
        docker_cmd = ["docker", "--version"]
        cmd_str = " ".join(docker_cmd)

        try:
            result = subprocess.run(
                docker_cmd, check=True, capture_output=True, text=True
            )
            docker_version = result.stdout.strip()
            logger.debug("Docker is available: %s", docker_version)
            return True

        except FileNotFoundError:
            logger.warning("Docker executable not found in PATH")
            return False

        except subprocess.CalledProcessError as e:
            stderr = e.stderr if hasattr(e, "stderr") and e.stderr else "unknown error"
            logger.warning("Docker command failed: %s - error: %s", cmd_str, stderr)
            return False

        except Exception as e:
            logger.warning("Unexpected error checking Docker availability: %s", e)
            return False

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
        """Run a Docker container with specified configuration."""
        from glovebox.utils import stream_process

        docker_cmd = ["docker", "run", "--rm"]

        # Add user context if provided and should be used
        if user_context and user_context.should_use_user_mapping():
            docker_user_flag = user_context.get_docker_user_flag()
            docker_cmd.extend(["--user", docker_user_flag])
            logger.debug("Using Docker user mapping: %s", docker_user_flag)

        # Add custom entrypoint if specified
        if entrypoint:
            docker_cmd.extend(["--entrypoint", entrypoint])
            logger.debug("Using custom entrypoint: %s", entrypoint)

        # Add volume mounts
        for host_path, container_path in volumes:
            docker_cmd.extend(["-v", f"{host_path}:{container_path}"])

        # Add environment variables
        for key, value in environment.items():
            docker_cmd.extend(["-e", f"{key}={value}"])

        # Add image
        docker_cmd.append(image)

        # Add command if specified
        if command:
            docker_cmd.extend(command)

        cmd_str = " ".join(shlex.quote(arg) for arg in docker_cmd)
        logger.debug("Docker command: %s", cmd_str)

        try:
            if middleware is None:
                # Cast is needed because T is unbound at this point
                middleware = cast(OutputMiddleware[T], LoggerOutputMiddleware(logger))
            result = stream_process.run_command(docker_cmd, middleware)
            # return_code: int = result[0]
            # stdout_lines_raw: list[str] = result[1]
            # stderr_lines_raw: list[str] = result[2]
            # stdout_lines: list[str] = stdout_lines_raw
            # stderr_lines: list[str] = stderr_lines_raw
            #
            # if return_code != 0 and stderr_lines:
            #     error_msg = "\n".join(stderr_lines)
            #     logger.warning(
            #         "Docker container exited with non-zero code %d: %s",
            #         return_code,
            #         error_msg[:200] + ("..." if len(error_msg) > 200 else ""),
            #     )

            return result  # return_code, stdout_lines, stderr_lines

        except FileNotFoundError as e:
            error = create_docker_error(f"Docker executable not found: {e}", cmd_str, e)
            logger.error("Docker executable not found: %s", e)
            raise error from e

        except subprocess.SubprocessError as e:
            error = create_docker_error(f"Docker subprocess error: {e}", cmd_str, e)
            logger.error("Docker subprocess error: %s", e)
            raise error from e

        except Exception as e:
            error = create_docker_error(
                f"Failed to run Docker container: {e}",
                cmd_str,
                e,
                {
                    "image": image,
                    "volumes_count": len(volumes),
                    "env_vars_count": len(environment),
                },
            )
            logger.error("Unexpected error running Docker container: %s", e)
            raise error from e

    def build_image(
        self,
        dockerfile_dir: Path,
        image_name: str,
        image_tag: str = "latest",
        no_cache: bool = False,
        middleware: OutputMiddleware[T] | None = None,
    ) -> ProcessResult[T]:
        """Build a Docker image from a Dockerfile."""
        from glovebox.utils import stream_process

        image_full_name = f"{image_name}:{image_tag}"

        # Check Docker availability
        if not self.is_available():
            error = create_docker_error(
                "Docker is not available or not properly installed",
                None,
                None,
                {"image": image_full_name},
            )
            logger.error("Docker not available for image build: %s", image_full_name)
            raise error

        # Validate dockerfile directory
        dockerfile_dir = Path(dockerfile_dir).resolve()
        if not dockerfile_dir.exists() or not dockerfile_dir.is_dir():
            error = create_docker_error(
                f"Dockerfile directory not found: {dockerfile_dir}",
                None,
                None,
                {"dockerfile_dir": str(dockerfile_dir), "image": image_full_name},
            )
            logger.error(
                "Invalid Dockerfile directory for image build: %s", dockerfile_dir
            )
            raise error

        # Check for Dockerfile
        dockerfile_path = dockerfile_dir / "Dockerfile"
        if not dockerfile_path.exists():
            error = create_docker_error(
                f"Dockerfile not found: {dockerfile_path}",
                None,
                None,
                {"dockerfile_path": str(dockerfile_path), "image": image_full_name},
            )
            logger.error("Dockerfile not found at %s for image build", dockerfile_path)
            raise error

        # Build the Docker command
        docker_cmd = [
            "docker",
            "build",
            "-t",
            image_full_name,
        ]

        if no_cache:
            docker_cmd.append("--no-cache")

        docker_cmd.append(str(dockerfile_dir))

        # Format command for logging
        cmd_str = " ".join(shlex.quote(arg) for arg in docker_cmd)
        logger.info("Building Docker image: %s", image_full_name)
        logger.debug("Docker command: %s", cmd_str)

        try:
            if middleware is None:
                # Cast is needed because T is unbound at this point
                middleware = cast(OutputMiddleware[T], LoggerOutputMiddleware(logger))

            result = stream_process.run_command(docker_cmd, middleware)
            return result

        except FileNotFoundError as e:
            error = create_docker_error(f"Docker executable not found: {e}", cmd_str, e)
            logger.error("Docker executable not found during image build: %s", e)
            raise error from e

        except subprocess.SubprocessError as e:
            error = create_docker_error(f"Docker subprocess error: {e}", cmd_str, e)
            logger.error("Docker subprocess error: %s", e)
            raise error from e

        except Exception as e:
            error = create_docker_error(
                f"Unexpected error building Docker image: {e}",
                cmd_str,
                e,
                {"image": image_full_name, "dockerfile_dir": str(dockerfile_dir)},
            )

            logger.error("Unexpected Docker build error for %s: %s", image_full_name, e)
            raise error from e

    def image_exists(self, image_name: str, image_tag: str = "latest") -> bool:
        """Check if a Docker image exists locally."""
        image_full_name = f"{image_name}:{image_tag}"

        # Check Docker availability
        if not self.is_available():
            logger.warning(
                "Docker not available, cannot check image existence: %s",
                image_full_name,
            )
            return False

        # Build the Docker command to check image existence
        docker_cmd = ["docker", "inspect", image_full_name]
        cmd_str = " ".join(shlex.quote(arg) for arg in docker_cmd)

        try:
            # Run Docker inspect command
            result = subprocess.run(
                docker_cmd, check=True, capture_output=True, text=True
            )

            logger.debug("Docker image exists: %s", image_full_name)
            return True

        except subprocess.CalledProcessError:
            # Image doesn't exist (inspect returns non-zero exit code)
            logger.debug("Docker image does not exist: %s", image_full_name)
            return False

        except FileNotFoundError:
            logger.warning("Docker executable not found during image check")
            return False

        except Exception as e:
            logger.warning("Unexpected error checking Docker image existence: %s", e)
            return False

    def pull_image(
        self,
        image_name: str,
        image_tag: str = "latest",
        middleware: OutputMiddleware[T] | None = None,
    ) -> ProcessResult[T]:
        """Pull a Docker image from registry."""
        from glovebox.utils import stream_process

        image_full_name = f"{image_name}:{image_tag}"

        # Check Docker availability
        if not self.is_available():
            error = create_docker_error(
                "Docker is not available or not properly installed",
                None,
                None,
                {"image": image_full_name},
            )
            logger.error("Docker not available for image pull: %s", image_full_name)
            raise error

        # Build the Docker command
        docker_cmd = ["docker", "pull", image_full_name]

        # Format command for logging
        cmd_str = " ".join(shlex.quote(arg) for arg in docker_cmd)
        logger.info("Pulling Docker image: %s", image_full_name)
        logger.debug("Docker command: %s", cmd_str)

        try:
            if middleware is None:
                # Cast is needed because T is unbound at this point
                middleware = cast(OutputMiddleware[T], LoggerOutputMiddleware(logger))

            result = stream_process.run_command(docker_cmd, middleware)
            return result

        except FileNotFoundError as e:
            error = create_docker_error(f"Docker executable not found: {e}", cmd_str, e)
            logger.error("Docker executable not found during image pull: %s", e)
            raise error from e

        except subprocess.SubprocessError as e:
            error = create_docker_error(f"Docker subprocess error: {e}", cmd_str, e)
            logger.error("Docker subprocess error: %s", e)
            raise error from e

        except Exception as e:
            error = create_docker_error(
                f"Unexpected error pulling Docker image: {e}",
                cmd_str,
                e,
                {"image": image_full_name},
            )

            logger.error("Unexpected Docker pull error for %s: %s", image_full_name, e)
            raise error from e


def create_docker_adapter() -> DockerAdapterProtocol:
    """
    Factory function to create a DockerAdapter instance.

    Returns:
        Configured DockerAdapter instance

    Example:
        >>> adapter = create_docker_adapter()
        >>> if adapter.is_available():
        ...     adapter.run_container("ubuntu:latest", [], {})
    """
    logger.debug("Creating DockerAdapter")
    return DockerAdapter()
