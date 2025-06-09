"""Docker adapter for container operations."""

import logging
import shlex
import subprocess
from pathlib import Path
from typing import Any

from glovebox.core.errors import BuildError, DockerError
from glovebox.protocols.docker_adapter_protocol import (
    DockerAdapterProtocol,
    DockerEnv,
    DockerResult,
    DockerVolume,
)
from glovebox.utils.error_utils import create_docker_error


logger = logging.getLogger(__name__)


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
        middleware: Any | None = None,
    ) -> DockerResult:
        """Run a Docker container with specified configuration."""
        from glovebox.utils import stream_process

        docker_cmd = ["docker", "run", "--rm"]

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
            result: tuple[int, list[str], list[str]] = stream_process.run_command(
                docker_cmd, middleware
            )
            return_code: int = result[0]
            stdout_lines_raw: list[str] = result[1]
            stderr_lines_raw: list[str] = result[2]
            stdout_lines: list[str] = stdout_lines_raw
            stderr_lines: list[str] = stderr_lines_raw

            if return_code != 0 and stderr_lines:
                error_msg = "\n".join(stderr_lines)
                logger.warning(
                    "Docker container exited with non-zero code %d: %s",
                    return_code,
                    error_msg[:200] + ("..." if len(error_msg) > 200 else ""),
                )

            return return_code, stdout_lines, stderr_lines

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
    ) -> bool:
        """Build a Docker image from a Dockerfile."""
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
            # Run Docker build command
            result = subprocess.run(
                docker_cmd, check=True, capture_output=True, text=True
            )

            # Log stdout on debug level if available
            if hasattr(result, "stdout") and result.stdout:
                stdout_preview = result.stdout[:500] + (
                    "..." if len(result.stdout) > 500 else ""
                )
                logger.debug("Docker build output: %s", stdout_preview)

            logger.info("Docker image built successfully: %s", image_full_name)
            return True

        except FileNotFoundError as e:
            error = create_docker_error(f"Docker executable not found: {e}", cmd_str, e)
            logger.error("Docker executable not found during image build: %s", e)
            raise error from e

        except subprocess.CalledProcessError as e:
            # Get detailed error message from stderr if available
            stderr = e.stderr if hasattr(e, "stderr") and e.stderr else str(e)
            error_preview = stderr[:500] + ("..." if len(stderr) > 500 else "")

            error = create_docker_error(
                f"Docker image build failed: {error_preview}",
                cmd_str,
                e,
                {
                    "image": image_full_name,
                    "exit_code": e.returncode
                    if hasattr(e, "returncode")
                    else "unknown",
                    "dockerfile_dir": str(dockerfile_dir),
                },
            )

            logger.error(
                "Docker image build failed for %s: %s", image_full_name, error_preview
            )
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
