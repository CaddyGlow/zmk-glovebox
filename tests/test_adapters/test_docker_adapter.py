"""Tests for DockerAdapter implementation."""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.adapters.docker_adapter import (
    DockerAdapter,
    LoggerOutputMiddleware,
    create_docker_adapter,
)
from glovebox.core.errors import DockerError
from glovebox.models.docker import DockerUserContext
from glovebox.protocols.docker_adapter_protocol import DockerAdapterProtocol


def _assert_docker_command_called(mock_run_command, expected_cmd):
    """Helper to assert Docker command was called with expected arguments and default middleware."""
    mock_run_command.assert_called_once()
    call_args = mock_run_command.call_args
    assert call_args[0][0] == expected_cmd  # First argument should be the command
    assert isinstance(
        call_args[0][1], LoggerOutputMiddleware
    )  # Second should be middleware


def _assert_docker_command_called_with_middleware(
    mock_run_command, expected_cmd, expected_middleware
):
    """Helper to assert Docker command was called with expected arguments and custom middleware."""
    mock_run_command.assert_called_once_with(expected_cmd, expected_middleware)


class TestDockerAdapter:
    """Test DockerAdapter class."""

    def test_docker_adapter_initialization(self):
        """Test DockerAdapter can be initialized."""
        adapter = DockerAdapter()
        assert adapter is not None

    def test_is_available_success(self):
        """Test is_available returns True when Docker is available."""
        adapter = DockerAdapter()

        mock_result = Mock()
        mock_result.stdout = "Docker version 20.10.0, build 1234567"

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = adapter.is_available()

        assert result is True
        mock_run.assert_called_once_with(
            ["docker", "--version"], check=True, capture_output=True, text=True
        )

    def test_is_available_docker_not_found(self):
        """Test is_available returns False when Docker is not found."""
        adapter = DockerAdapter()

        with patch("subprocess.run", side_effect=FileNotFoundError("docker not found")):
            result = adapter.is_available()

        assert result is False

    def test_is_available_docker_error(self):
        """Test is_available returns False when Docker command fails."""
        adapter = DockerAdapter()

        with patch(
            "subprocess.run", side_effect=subprocess.CalledProcessError(1, "docker")
        ):
            result = adapter.is_available()

        assert result is False

    def test_run_container_success(self):
        """Test successful container execution."""
        adapter = DockerAdapter()

        mock_run_command = Mock(
            return_value=(0, ["output line 1", "output line 2"], [])
        )

        with patch("glovebox.utils.stream_process.run_command", mock_run_command):
            return_code, stdout, stderr = adapter.run_container(
                image="ubuntu:latest",
                volumes=[("/host/path", "/container/path")],
                environment={"ENV_VAR": "value"},
                command=["echo", "hello"],
            )

        assert return_code == 0
        assert stdout == ["output line 1", "output line 2"]
        assert stderr == []

        expected_cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            "/host/path:/container/path",
            "-e",
            "ENV_VAR=value",
            "ubuntu:latest",
            "echo",
            "hello",
        ]
        _assert_docker_command_called(mock_run_command, expected_cmd)

    def test_run_container_no_command(self):
        """Test container execution without explicit command."""
        adapter = DockerAdapter()

        mock_run_command = Mock(return_value=(0, [], []))

        with patch("glovebox.utils.stream_process.run_command", mock_run_command):
            adapter.run_container(image="ubuntu:latest", volumes=[], environment={})

        expected_cmd = ["docker", "run", "--rm", "ubuntu:latest"]
        _assert_docker_command_called(mock_run_command, expected_cmd)

    def test_run_container_multiple_volumes_and_env(self):
        """Test container execution with multiple volumes and environment variables."""
        adapter = DockerAdapter()

        mock_run_command = Mock(return_value=(0, [], []))

        with patch("glovebox.utils.stream_process.run_command", mock_run_command):
            adapter.run_container(
                image="ubuntu:latest",
                volumes=[("/host1", "/container1"), ("/host2", "/container2")],
                environment={"VAR1": "value1", "VAR2": "value2"},
            )

        expected_cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            "/host1:/container1",
            "-v",
            "/host2:/container2",
            "-e",
            "VAR1=value1",
            "-e",
            "VAR2=value2",
            "ubuntu:latest",
        ]
        _assert_docker_command_called(mock_run_command, expected_cmd)

    def test_run_container_with_middleware(self):
        """Test container execution with middleware."""
        adapter = DockerAdapter()

        mock_middleware = Mock()
        mock_run_command = Mock(return_value=(0, ["output"], []))

        with patch("glovebox.utils.stream_process.run_command", mock_run_command):
            adapter.run_container(
                image="ubuntu:latest",
                volumes=[],
                environment={},
                middleware=mock_middleware,
            )

        expected_cmd = ["docker", "run", "--rm", "ubuntu:latest"]
        _assert_docker_command_called_with_middleware(
            mock_run_command, expected_cmd, mock_middleware
        )

    def test_run_container_with_entrypoint(self):
        """Test container execution with custom entrypoint."""
        adapter = DockerAdapter()

        mock_run_command = Mock(return_value=(0, ["output"], []))

        with patch("glovebox.utils.stream_process.run_command", mock_run_command):
            adapter.run_container(
                image="ubuntu:latest",
                volumes=[],
                environment={},
                entrypoint="/bin/bash",
            )

        expected_cmd = [
            "docker",
            "run",
            "--rm",
            "--entrypoint",
            "/bin/bash",
            "ubuntu:latest",
        ]
        _assert_docker_command_called(mock_run_command, expected_cmd)

    def test_run_container_with_entrypoint_and_command(self):
        """Test container execution with custom entrypoint and command."""
        adapter = DockerAdapter()

        mock_run_command = Mock(return_value=(0, ["output"], []))

        with patch("glovebox.utils.stream_process.run_command", mock_run_command):
            adapter.run_container(
                image="ubuntu:latest",
                volumes=[("/host", "/container")],
                environment={"TEST": "value"},
                command=["-c", "echo hello"],
                entrypoint="/bin/bash",
            )

        expected_cmd = [
            "docker",
            "run",
            "--rm",
            "--entrypoint",
            "/bin/bash",
            "-v",
            "/host:/container",
            "-e",
            "TEST=value",
            "ubuntu:latest",
            "-c",
            "echo hello",
        ]
        _assert_docker_command_called(mock_run_command, expected_cmd)

    def test_run_container_no_entrypoint(self):
        """Test container execution without entrypoint uses default behavior."""
        adapter = DockerAdapter()

        mock_run_command = Mock(return_value=(0, ["output"], []))

        with patch("glovebox.utils.stream_process.run_command", mock_run_command):
            adapter.run_container(
                image="ubuntu:latest",
                volumes=[],
                environment={},
                entrypoint=None,
            )

        expected_cmd = ["docker", "run", "--rm", "ubuntu:latest"]
        _assert_docker_command_called(mock_run_command, expected_cmd)

    def test_run_container_with_user_context(self):
        """Test container execution with user context."""
        adapter = DockerAdapter()

        user_context = DockerUserContext.create_manual(
            uid=1000, gid=1000, username="testuser", enable_user_mapping=True
        )
        mock_run_command = Mock(return_value=(0, ["output"], []))

        with patch("glovebox.utils.stream_process.run_command", mock_run_command):
            adapter.run_container(
                image="ubuntu:latest",
                volumes=[],
                environment={},
                user_context=user_context,
            )

        expected_cmd = [
            "docker",
            "run",
            "--rm",
            "--user",
            "1000:1000",
            "ubuntu:latest",
        ]
        _assert_docker_command_called(mock_run_command, expected_cmd)

    def test_run_container_with_user_context_disabled(self):
        """Test container execution with user context but mapping disabled."""
        adapter = DockerAdapter()

        user_context = DockerUserContext.create_manual(
            uid=1000, gid=1000, username="testuser", enable_user_mapping=False
        )
        mock_run_command = Mock(return_value=(0, ["output"], []))

        with patch("glovebox.utils.stream_process.run_command", mock_run_command):
            adapter.run_container(
                image="ubuntu:latest",
                volumes=[],
                environment={},
                user_context=user_context,
            )

        expected_cmd = ["docker", "run", "--rm", "ubuntu:latest"]
        _assert_docker_command_called(mock_run_command, expected_cmd)

    def test_run_container_with_user_context_unsupported_platform(self):
        """Test container execution with user context on unsupported platform."""
        adapter = DockerAdapter()

        user_context = DockerUserContext.create_manual(
            uid=1000, gid=1000, username="testuser", enable_user_mapping=True
        )
        mock_run_command = Mock(return_value=(0, ["output"], []))

        with (
            patch("glovebox.utils.stream_process.run_command", mock_run_command),
            patch.object(
                DockerUserContext, "is_supported_platform", return_value=False
            ),
        ):
            adapter.run_container(
                image="ubuntu:latest",
                volumes=[],
                environment={},
                user_context=user_context,
            )

        # Should not include --user flag when platform is unsupported
        expected_cmd = ["docker", "run", "--rm", "ubuntu:latest"]
        _assert_docker_command_called(mock_run_command, expected_cmd)

    def test_run_container_with_all_parameters(self):
        """Test container execution with all parameters including user context and entrypoint."""
        adapter = DockerAdapter()

        user_context = DockerUserContext.create_manual(
            uid=1000, gid=1000, username="testuser", enable_user_mapping=True
        )
        mock_middleware = Mock()
        mock_run_command = Mock(return_value=(0, ["output"], []))

        with patch("glovebox.utils.stream_process.run_command", mock_run_command):
            adapter.run_container(
                image="ubuntu:latest",
                volumes=[("/host1", "/container1"), ("/host2", "/container2")],
                environment={"VAR1": "value1", "VAR2": "value2"},
                command=["echo", "hello"],
                middleware=mock_middleware,
                user_context=user_context,
                entrypoint="/bin/bash",
            )

        expected_cmd = [
            "docker",
            "run",
            "--rm",
            "--user",
            "1000:1000",
            "--entrypoint",
            "/bin/bash",
            "-v",
            "/host1:/container1",
            "-v",
            "/host2:/container2",
            "-e",
            "VAR1=value1",
            "-e",
            "VAR2=value2",
            "ubuntu:latest",
            "echo",
            "hello",
        ]
        _assert_docker_command_called_with_middleware(
            mock_run_command, expected_cmd, mock_middleware
        )

    def test_run_container_no_user_context(self):
        """Test container execution without user context."""
        adapter = DockerAdapter()

        mock_run_command = Mock(return_value=(0, ["output"], []))

        with patch("glovebox.utils.stream_process.run_command", mock_run_command):
            adapter.run_container(
                image="ubuntu:latest",
                volumes=[],
                environment={},
                user_context=None,
            )

        expected_cmd = ["docker", "run", "--rm", "ubuntu:latest"]
        _assert_docker_command_called(mock_run_command, expected_cmd)

    def test_run_container_exception(self):
        """Test container execution handles exceptions."""
        adapter = DockerAdapter()

        with (
            patch(
                "glovebox.utils.stream_process.run_command",
                side_effect=Exception("Test error"),
            ),
            pytest.raises(
                DockerError, match="Failed to run Docker container: Test error"
            ),
        ):
            adapter.run_container("ubuntu:latest", [], {})

    def test_build_image_success(self):
        """Test successful image building."""
        adapter = DockerAdapter()

        dockerfile_dir = Path("/test/dockerfile")
        with (
            patch.object(adapter, "is_available", return_value=True),
            patch("subprocess.run") as mock_run,
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=True),
        ):
            result = adapter.build_image(
                dockerfile_dir=dockerfile_dir,
                image_name="test-image",
                image_tag="v1.0",
                no_cache=True,
            )

        assert result is True
        expected_cmd = [
            "docker",
            "build",
            "-t",
            "test-image:v1.0",
            "--no-cache",
            str(dockerfile_dir),
        ]
        mock_run.assert_called_once_with(
            expected_cmd, check=True, capture_output=True, text=True
        )

    def test_build_image_no_cache_false(self):
        """Test image building without no-cache flag."""
        adapter = DockerAdapter()

        dockerfile_dir = Path("/test/dockerfile")
        with (
            patch.object(adapter, "is_available", return_value=True),
            patch("subprocess.run") as mock_run,
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=True),
        ):
            adapter.build_image(dockerfile_dir=dockerfile_dir, image_name="test-image")

        expected_cmd = [
            "docker",
            "build",
            "-t",
            "test-image:latest",
            str(dockerfile_dir),
        ]
        mock_run.assert_called_once_with(
            expected_cmd, check=True, capture_output=True, text=True
        )

    def test_build_image_docker_not_available(self):
        """Test build_image raises error when Docker is not available."""
        adapter = DockerAdapter()

        with (
            patch.object(adapter, "is_available", return_value=False),
            pytest.raises(DockerError, match="Docker is not available"),
        ):
            adapter.build_image(Path("/test"), "test-image")

    def test_build_image_directory_not_found(self):
        """Test build_image raises error when directory doesn't exist."""
        adapter = DockerAdapter()

        with (
            patch.object(adapter, "is_available", return_value=True),
            patch("pathlib.Path.exists", return_value=False),
            pytest.raises(DockerError, match="Dockerfile directory not found"),
        ):
            adapter.build_image(Path("/nonexistent"), "test-image")

    def test_build_image_not_directory(self):
        """Test build_image raises error when path is not a directory."""
        adapter = DockerAdapter()

        with (
            patch.object(adapter, "is_available", return_value=True),
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=False),
            pytest.raises(DockerError, match="Dockerfile directory not found"),
        ):
            adapter.build_image(Path("/test/file"), "test-image")

    def test_build_image_dockerfile_not_found(self):
        """Test build_image raises error when Dockerfile doesn't exist."""
        adapter = DockerAdapter()

        with patch.object(adapter, "is_available", return_value=True):
            dockerfile_dir = Path("/test/dockerfile")

            # Mock directory exists but Dockerfile doesn't exist
            def mock_exists(self):
                return self.name != "Dockerfile"

            def mock_is_dir(self):
                return self.name == "dockerfile"

            with (
                patch("pathlib.Path.exists", mock_exists),
                patch("pathlib.Path.is_dir", mock_is_dir),
                pytest.raises(DockerError, match="Dockerfile not found"),
            ):
                adapter.build_image(dockerfile_dir, "test-image")

    def test_build_image_subprocess_error(self):
        """Test build_image handles subprocess errors."""
        adapter = DockerAdapter()

        error = subprocess.CalledProcessError(1, "docker")
        error.stderr = "Build failed: syntax error"

        dockerfile_dir = Path("/test/dockerfile")
        with (
            patch.object(adapter, "is_available", return_value=True),
            patch("subprocess.run", side_effect=error),
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=True),
            pytest.raises(
                DockerError,
                match="Docker image build failed: Build failed: syntax error",
            ),
        ):
            adapter.build_image(dockerfile_dir, "test-image")


class TestCreateDockerAdapter:
    """Test create_docker_adapter factory function."""

    def test_create_docker_adapter(self):
        """Test factory function creates DockerAdapter instance."""
        adapter = create_docker_adapter()
        assert isinstance(adapter, DockerAdapter)
        assert isinstance(adapter, DockerAdapterProtocol)


class TestDockerAdapterProtocol:
    """Test DockerAdapter protocol implementation."""

    def test_docker_adapter_implements_protocol(self):
        """Test that DockerAdapter correctly implements DockerAdapter protocol."""
        adapter = DockerAdapter()
        assert isinstance(adapter, DockerAdapterProtocol), (
            "DockerAdapter must implement DockerAdapterProtocol"
        )

    def test_runtime_protocol_check(self):
        """Test that DockerAdapter passes runtime protocol check."""
        adapter = DockerAdapter()
        assert isinstance(adapter, DockerAdapterProtocol), (
            "DockerAdapter should be instance of DockerAdapterProtocol"
        )
