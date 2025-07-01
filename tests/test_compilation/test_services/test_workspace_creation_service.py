"""Tests for workspace creation service."""

import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.compilation.parsers.repository_spec_parser import RepositorySpec
from glovebox.compilation.services.workspace_creation_service import (
    WorkspaceCreationResult,
    WorkspaceCreationService,
    create_workspace_creation_service,
)
from glovebox.config.user_config import UserConfig
from glovebox.core.file_operations import FileCopyService
from glovebox.models.docker import DockerUserContext
from glovebox.protocols import (
    DockerAdapterProtocol,
    FileAdapterProtocol,
    MetricsProtocol,
)


class TestWorkspaceCreationResult:
    """Test WorkspaceCreationResult model functionality."""

    def test_workspace_creation_result_basic_properties(self):
        """Test basic properties of WorkspaceCreationResult."""
        result = WorkspaceCreationResult(
            success=True,
            docker_image_used="zmkfirmware/zmk-dev-arm:stable",
            west_init_success=True,
            west_update_success=True,
            git_clone_success=True,
            creation_duration_seconds=45.5,
        )

        assert result.success is True
        assert result.docker_image_used == "zmkfirmware/zmk-dev-arm:stable"
        assert result.west_init_success is True
        assert result.west_update_success is True
        assert result.git_clone_success is True
        assert result.creation_duration_seconds == 45.5

    def test_workspace_creation_result_failure(self):
        """Test WorkspaceCreationResult for failure cases."""
        result = WorkspaceCreationResult(
            success=False,
            error_message="Failed to clone repository",
            docker_image_used="zmkfirmware/zmk-dev-arm:stable",
            west_init_success=True,
            git_clone_success=False,
            creation_duration_seconds=12.3,
        )

        assert result.success is False
        assert result.error_message == "Failed to clone repository"
        assert result.west_init_success is True
        assert result.git_clone_success is False


class TestWorkspaceCreationService:
    """Test WorkspaceCreationService functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.mock_docker_adapter = Mock(spec=DockerAdapterProtocol)
        self.mock_file_adapter = Mock(spec=FileAdapterProtocol)
        self.mock_user_config = Mock(spec=UserConfig)
        self.mock_session_metrics = Mock(spec=MetricsProtocol)
        self.mock_copy_service = Mock(spec=FileCopyService)

        self.service = WorkspaceCreationService(
            docker_adapter=self.mock_docker_adapter,
            file_adapter=self.mock_file_adapter,
            user_config=self.mock_user_config,
            session_metrics=self.mock_session_metrics,
            copy_service=self.mock_copy_service,
        )

    def test_initialization(self):
        """Test service initialization."""
        assert self.service.docker_adapter == self.mock_docker_adapter
        assert self.service.file_adapter == self.mock_file_adapter
        assert self.service.user_config == self.mock_user_config
        assert self.service.session_metrics == self.mock_session_metrics
        assert self.service.copy_service == self.mock_copy_service
        assert hasattr(self.service, "repository_parser")
        assert hasattr(self.service, "logger")

    def test_initialization_with_default_copy_service(self):
        """Test service initialization with default copy service."""
        service = WorkspaceCreationService(
            docker_adapter=self.mock_docker_adapter,
            file_adapter=self.mock_file_adapter,
            user_config=self.mock_user_config,
            session_metrics=self.mock_session_metrics,
        )

        assert service.copy_service is not None
        assert isinstance(service.copy_service, FileCopyService)

    @patch("glovebox.compilation.services.workspace_creation_service.time.time")
    def test_create_workspace_invalid_spec(self, mock_time):
        """Test create_workspace with invalid repository specification."""
        mock_time.return_value = 1000.0

        # Mock metrics
        mock_counter = Mock()
        self.mock_session_metrics.Counter.return_value = mock_counter
        self.mock_session_metrics.Histogram.return_value = Mock()

        result = self.service.create_workspace("invalid-spec")

        assert result.success is False
        assert "Invalid repository specification" in result.error_message
        mock_counter.labels.assert_called_with("unknown", "unknown", "failed_parsing")

    @patch("glovebox.compilation.services.workspace_creation_service.time.time")
    def test_create_workspace_metrics_integration(self, mock_time):
        """Test create_workspace with metrics integration."""
        mock_time.side_effect = [1000.0, 1045.5]  # Start and end times

        # Mock metrics
        mock_counter = Mock()
        mock_histogram = Mock()
        mock_timer = Mock()
        mock_histogram.time.return_value.__enter__ = Mock(return_value=mock_timer)
        mock_histogram.time.return_value.__exit__ = Mock(return_value=None)

        self.mock_session_metrics.Counter.return_value = mock_counter
        self.mock_session_metrics.Histogram.return_value = mock_histogram

        # Mock the internal method to return success
        with patch.object(self.service, "_create_workspace_internal") as mock_internal:
            mock_internal.return_value = WorkspaceCreationResult(
                success=True,
                creation_duration_seconds=45.5,
            )

            result = self.service.create_workspace("moergo-sc/zmk@main")

        assert result.success is True
        self.mock_session_metrics.set_context.assert_called_once()
        mock_counter.labels.assert_called_with("moergo-sc/zmk", "main", "success")

    def test_determine_docker_image_explicit(self):
        """Test _determine_docker_image with explicit image."""
        result = self.service._determine_docker_image(
            docker_image="custom/image:tag",
            keyboard_profile=None,
        )

        assert result == "custom/image:tag"

    def test_determine_docker_image_from_profile(self):
        """Test _determine_docker_image from keyboard profile."""
        mock_profile = Mock()
        mock_compilation_config = Mock()
        mock_compilation_config.image = "profile/image:tag"
        mock_profile.compilation_config = mock_compilation_config

        result = self.service._determine_docker_image(
            docker_image=None,
            keyboard_profile=mock_profile,
        )

        assert result == "profile/image:tag"

    def test_determine_docker_image_default(self):
        """Test _determine_docker_image with default fallback."""
        result = self.service._determine_docker_image(
            docker_image=None,
            keyboard_profile=None,
        )

        assert result == "zmkfirmware/zmk-dev-arm:stable"

    def test_determine_docker_image_profile_without_image(self):
        """Test _determine_docker_image with profile but no image."""
        mock_profile = Mock()
        mock_profile.compilation_config = None

        result = self.service._determine_docker_image(
            docker_image=None,
            keyboard_profile=mock_profile,
        )

        assert result == "zmkfirmware/zmk-dev-arm:stable"

    @patch(
        "glovebox.compilation.services.workspace_creation_service.tempfile.TemporaryDirectory"
    )
    def test_create_workspace_internal_west_init_failure(self, mock_temp_dir):
        """Test _create_workspace_internal with west init failure."""
        # Mock temporary directory
        temp_path = Path("/tmp/test_workspace")
        mock_temp_dir.return_value.__enter__.return_value = str(temp_path)
        mock_temp_dir.return_value.__exit__.return_value = None

        # Mock repository spec
        repo_spec = RepositorySpec(
            repository="moergo-sc/zmk",
            organization="moergo-sc",
            repo_name="zmk",
            branch="main",
            original_spec="moergo-sc/zmk@main",
        )

        # Mock west initialization failure
        with patch.object(
            self.service, "_initialize_west_workspace", return_value=False
        ):
            result = self.service._create_workspace_internal(
                repository_spec=repo_spec,
                keyboard_profile=None,
                docker_image="test/image:tag",
                force_recreate=False,
                progress_callback=None,
                progress_coordinator=None,
                creation_start_time=1000.0,
            )

        assert result.success is False
        assert "Failed to initialize west workspace" in result.error_message
        assert result.docker_image_used == "test/image:tag"
        assert result.west_init_success is False

    def test_run_docker_commands_success(self):
        """Test _run_docker_commands with successful execution."""
        # Mock successful Docker execution
        self.mock_docker_adapter.run_container.return_value = (0, [], [])

        # Mock user context detection
        with patch(
            "glovebox.compilation.services.workspace_creation_service.DockerUserContext.detect_current_user"
        ) as mock_user:
            mock_user.return_value = DockerUserContext(
                uid=1000, gid=1000, username="testuser"
            )

            result = self.service._run_docker_commands(
                commands=["echo 'test'"],
                docker_image="test/image:tag",
                workspace_path=Path("/tmp/workspace"),
                operation_name="Test Operation",
                progress_coordinator=None,
            )

        assert result is True
        self.mock_docker_adapter.run_container.assert_called_once()

    def test_run_docker_commands_failure(self):
        """Test _run_docker_commands with Docker execution failure."""
        # Mock failed Docker execution
        self.mock_docker_adapter.run_container.return_value = (1, [], ["Error"])

        # Mock user context detection
        with patch(
            "glovebox.compilation.services.workspace_creation_service.DockerUserContext.detect_current_user"
        ) as mock_user:
            mock_user.return_value = DockerUserContext(
                uid=1000, gid=1000, username="testuser"
            )

            result = self.service._run_docker_commands(
                commands=["false"],
                docker_image="test/image:tag",
                workspace_path=Path("/tmp/workspace"),
                operation_name="Test Operation",
                progress_coordinator=None,
            )

        assert result is False

    def test_run_docker_commands_exception(self):
        """Test _run_docker_commands with exception during execution."""
        # Mock Docker adapter to raise exception
        self.mock_docker_adapter.run_container.side_effect = Exception("Docker error")

        # Mock user context detection
        with patch(
            "glovebox.compilation.services.workspace_creation_service.DockerUserContext.detect_current_user"
        ) as mock_user:
            mock_user.return_value = DockerUserContext(
                uid=1000, gid=1000, username="testuser"
            )

            result = self.service._run_docker_commands(
                commands=["echo 'test'"],
                docker_image="test/image:tag",
                workspace_path=Path("/tmp/workspace"),
                operation_name="Test Operation",
                progress_coordinator=None,
            )

        assert result is False

    def test_generate_west_manifest(self):
        """Test _generate_west_manifest creates proper YAML content."""
        repo_spec = RepositorySpec(
            repository="moergo-sc/zmk",
            organization="moergo-sc",
            repo_name="zmk",
            branch="v26.01",
            original_spec="moergo-sc/zmk@v26.01",
        )

        manifest_content = self.service._generate_west_manifest(repo_spec)

        # Basic validation of YAML content
        assert "manifest:" in manifest_content
        assert "remotes:" in manifest_content
        assert "projects:" in manifest_content
        assert "zmkfirmware" in manifest_content
        assert "moergo-sc" in manifest_content
        assert "v26.01" in manifest_content

        # Validate it's proper YAML
        import yaml

        manifest_data = yaml.safe_load(manifest_content)
        assert "manifest" in manifest_data
        assert "remotes" in manifest_data["manifest"]
        assert "projects" in manifest_data["manifest"]

    def test_create_workspace_metadata(self):
        """Test _create_workspace_metadata creates proper metadata."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir)

            # Create some test workspace components
            (workspace_path / "zmk").mkdir()
            (workspace_path / "zephyr").mkdir()
            (workspace_path / ".west").mkdir()
            (workspace_path / "config").mkdir()

            # Create a test file to calculate size
            test_file = workspace_path / "test.txt"
            test_file.write_text("test content")

            repo_spec = RepositorySpec(
                repository="moergo-sc/zmk",
                organization="moergo-sc",
                repo_name="zmk",
                branch="main",
                original_spec="moergo-sc/zmk@main",
            )

            mock_profile = Mock()
            mock_profile.name = "test_profile"

            metadata = self.service._create_workspace_metadata(
                workspace_path=workspace_path,
                repository_spec=repo_spec,
                docker_image="test/image:tag",
                keyboard_profile=mock_profile,
            )

            assert metadata.repository == "moergo-sc/zmk"
            assert metadata.branch == "main"
            assert metadata.docker_image == "test/image:tag"
            assert metadata.creation_profile == "test_profile"
            assert metadata.creation_method == "direct"
            assert metadata.west_manifest_path == "config/west.yml"
            assert "zmk" in metadata.cached_components
            assert "zephyr" in metadata.cached_components
            assert ".west" in metadata.cached_components
            assert "config" in metadata.cached_components
            assert metadata.size_bytes > 0

    def test_initialize_west_workspace_success(self):
        """Test _initialize_west_workspace with successful execution."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir)

            repo_spec = RepositorySpec(
                repository="moergo-sc/zmk",
                organization="moergo-sc",
                repo_name="zmk",
                branch="main",
                original_spec="moergo-sc/zmk@main",
            )

            # Mock successful Docker execution
            with patch.object(self.service, "_run_docker_commands", return_value=True):
                result = self.service._initialize_west_workspace(
                    workspace_path=workspace_path,
                    repository_spec=repo_spec,
                    docker_image="test/image:tag",
                    progress_coordinator=None,
                )

            assert result is True
            # Check that west.yml was created
            west_yml = workspace_path / "config" / "west.yml"
            assert west_yml.exists()

    def test_clone_and_checkout_repository_success(self):
        """Test _clone_and_checkout_repository with successful execution."""
        workspace_path = Path("/tmp/workspace")

        repo_spec = RepositorySpec(
            repository="moergo-sc/zmk",
            organization="moergo-sc",
            repo_name="zmk",
            branch="main",
            original_spec="moergo-sc/zmk@main",
        )

        # Mock successful Docker execution
        with patch.object(self.service, "_run_docker_commands", return_value=True):
            result = self.service._clone_and_checkout_repository(
                workspace_path=workspace_path,
                repository_spec=repo_spec,
                docker_image="test/image:tag",
                progress_coordinator=None,
            )

        assert result is True

    def test_update_workspace_dependencies_success(self):
        """Test _update_workspace_dependencies with successful execution."""
        workspace_path = Path("/tmp/workspace")

        # Mock successful Docker execution
        with patch.object(self.service, "_run_docker_commands", return_value=True):
            result = self.service._update_workspace_dependencies(
                workspace_path=workspace_path,
                docker_image="test/image:tag",
                progress_coordinator=None,
            )

        assert result is True


class TestWorkspaceCreationServiceIntegration:
    """Integration tests for workspace creation service."""

    def setup_method(self):
        """Set up test environment."""
        self.mock_docker_adapter = Mock(spec=DockerAdapterProtocol)
        self.mock_file_adapter = Mock(spec=FileAdapterProtocol)
        self.mock_user_config = Mock(spec=UserConfig)
        self.mock_session_metrics = Mock(spec=MetricsProtocol)

        self.service = WorkspaceCreationService(
            docker_adapter=self.mock_docker_adapter,
            file_adapter=self.mock_file_adapter,
            user_config=self.mock_user_config,
            session_metrics=self.mock_session_metrics,
        )

    @patch(
        "glovebox.compilation.services.workspace_creation_service.tempfile.TemporaryDirectory"
    )
    @patch("glovebox.compilation.services.workspace_creation_service.time.time")
    def test_full_workspace_creation_success(self, mock_time, mock_temp_dir):
        """Test complete successful workspace creation flow."""
        # Mock time progression
        mock_time.side_effect = [1000.0, 1045.5]  # Start and end times

        # Mock temporary directory
        temp_path = Path("/tmp/test_workspace")
        mock_temp_dir.return_value.__enter__.return_value = str(temp_path)
        mock_temp_dir.return_value.__exit__.return_value = None

        # Mock metrics
        mock_counter = Mock()
        mock_histogram = Mock()
        mock_timer = Mock()
        mock_histogram.time.return_value = mock_timer
        mock_histogram.time.return_value.__enter__ = Mock(return_value=mock_timer)
        mock_histogram.time.return_value.__exit__ = Mock(return_value=None)

        self.mock_session_metrics.Counter.return_value = mock_counter
        self.mock_session_metrics.Histogram.return_value = mock_histogram

        # Mock all Docker operations to succeed
        with (
            patch.object(self.service, "_run_docker_commands", return_value=True),
            patch.object(self.service, "_create_workspace_metadata") as mock_metadata,
        ):
            mock_metadata.return_value = Mock(
                repository="moergo-sc/zmk",
                branch="main",
                docker_image="test/image:tag",
            )

            result = self.service.create_workspace("moergo-sc/zmk@main")

        assert result.success is True
        assert result.docker_image_used == "zmkfirmware/zmk-dev-arm:stable"
        assert result.west_init_success is True
        assert result.git_clone_success is True
        assert result.west_update_success is True

        # Verify metrics were called
        self.mock_session_metrics.set_context.assert_called_once()
        mock_counter.labels.assert_called_with("moergo-sc/zmk", "main", "success")

    @patch("glovebox.compilation.services.workspace_creation_service.time.time")
    def test_workspace_creation_with_progress_coordinator(self, mock_time):
        """Test workspace creation with progress coordinator integration."""
        mock_time.side_effect = [1000.0, 1045.5]

        # Mock progress coordinator
        mock_progress_coordinator = Mock()

        # Mock metrics
        self.mock_session_metrics.Counter.return_value = Mock()
        self.mock_session_metrics.Histogram.return_value = Mock()

        # Mock the internal method to return success
        with patch.object(self.service, "_create_workspace_internal") as mock_internal:
            mock_internal.return_value = WorkspaceCreationResult(
                success=True,
                creation_duration_seconds=45.5,
            )

            result = self.service.create_workspace(
                repo_spec="moergo-sc/zmk@main",
                progress_coordinator=mock_progress_coordinator,
            )

        assert result.success is True
        # Verify progress coordinator was used
        mock_progress_coordinator.transition_to_phase.assert_called()


class TestCreateWorkspaceCreationService:
    """Test factory function for workspace creation service."""

    def test_create_workspace_creation_service(self):
        """Test factory function creates service instance."""
        mock_docker_adapter = Mock(spec=DockerAdapterProtocol)
        mock_file_adapter = Mock(spec=FileAdapterProtocol)
        mock_user_config = Mock(spec=UserConfig)
        mock_session_metrics = Mock(spec=MetricsProtocol)

        service = create_workspace_creation_service(
            docker_adapter=mock_docker_adapter,
            file_adapter=mock_file_adapter,
            user_config=mock_user_config,
            session_metrics=mock_session_metrics,
        )

        assert isinstance(service, WorkspaceCreationService)
        assert service.docker_adapter == mock_docker_adapter
        assert service.file_adapter == mock_file_adapter
        assert service.user_config == mock_user_config
        assert service.session_metrics == mock_session_metrics

    def test_factory_with_copy_service(self):
        """Test factory function with optional copy service."""
        mock_docker_adapter = Mock(spec=DockerAdapterProtocol)
        mock_file_adapter = Mock(spec=FileAdapterProtocol)
        mock_user_config = Mock(spec=UserConfig)
        mock_session_metrics = Mock(spec=MetricsProtocol)
        mock_copy_service = Mock(spec=FileCopyService)

        service = create_workspace_creation_service(
            docker_adapter=mock_docker_adapter,
            file_adapter=mock_file_adapter,
            user_config=mock_user_config,
            session_metrics=mock_session_metrics,
            copy_service=mock_copy_service,
        )

        assert service.copy_service == mock_copy_service
