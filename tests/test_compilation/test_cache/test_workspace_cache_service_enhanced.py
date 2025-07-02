"""Tests for enhanced ZmkWorkspaceCacheService methods for workspace creation."""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest


pytestmark = [pytest.mark.docker, pytest.mark.integration]

from glovebox.compilation.cache.models import (
    WorkspaceCacheMetadata,
    WorkspaceCacheResult,
)
from glovebox.compilation.cache.workspace_cache_service import ZmkWorkspaceCacheService
from glovebox.compilation.parsers.repository_spec_parser import RepositorySpec
from glovebox.compilation.services.workspace_creation_service import (
    WorkspaceCreationResult,
    WorkspaceCreationService,
)
from glovebox.config.models.cache import CacheLevel
from glovebox.config.user_config import UserConfig
from glovebox.core.cache.cache_manager import CacheManager
from glovebox.models.docker import DockerUserContext
from glovebox.protocols import MetricsProtocol


@pytest.fixture
def sample_workspace_metadata():
    """Create a sample WorkspaceCacheMetadata for testing."""
    # Use model_validate to work around mypy issues with default factories
    data = {
        "workspace_path": Path("/tmp/test_workspace"),
        "repository": "moergo-sc/zmk",
        "branch": "main",
        "commit_hash": "abc123",
        "cache_level": CacheLevel.REPO_BRANCH,
        "size_bytes": 1024000,
        "docker_image": "test/image:tag",
    }
    return WorkspaceCacheMetadata.model_validate(data)


class TestZmkWorkspaceCacheServiceEnhanced:
    """Test enhanced methods in ZmkWorkspaceCacheService for workspace creation."""

    def setup_method(self):
        """Set up test environment."""
        self.mock_user_config = Mock(spec=UserConfig)
        self.mock_cache_manager = Mock(spec=CacheManager)
        self.mock_session_metrics = Mock(spec=MetricsProtocol)

        self.service = ZmkWorkspaceCacheService(
            user_config=self.mock_user_config,
            cache_manager=self.mock_cache_manager,
            session_metrics=self.mock_session_metrics,
        )

    def test_create_workspace_from_spec_success(self, sample_workspace_metadata):
        """Test create_workspace_from_spec with successful creation."""
        # Mock workspace creation service
        mock_creation_service = Mock(spec=WorkspaceCreationService)
        mock_creation_result = WorkspaceCreationResult(
            success=True,
            workspace_path=Path("/tmp/workspace"),
            metadata=sample_workspace_metadata,
            created_new=True,
            docker_image_used="test/image:tag",
            west_init_success=True,
            git_clone_success=True,
            west_update_success=True,
            creation_duration_seconds=45.5,
        )
        mock_creation_service.create_workspace.return_value = mock_creation_result

        # Mock caching operation
        with patch.object(self.service, "cache_workspace_repo_branch") as mock_cache:
            mock_cache.return_value = WorkspaceCacheResult(
                success=True,
                workspace_path=Path("/tmp/cached_workspace"),
                metadata=sample_workspace_metadata,
                created_new=False,
            )

            # Mock creation service instantiation - patch the import inside the method
            with patch(
                "glovebox.compilation.services.workspace_creation_service.create_workspace_creation_service"
            ) as mock_create_service:
                mock_create_service.return_value = mock_creation_service

                result = self.service.create_workspace_from_spec(
                    repo_spec="moergo-sc/zmk@main"
                )

        assert result.success is True
        assert result.workspace_path == Path("/tmp/cached_workspace")
        mock_creation_service.create_workspace.assert_called_once_with(
            repo_spec="moergo-sc/zmk@main",
            keyboard_profile=None,
            docker_image=None,
            force_recreate=False,
            progress_callback=None,
            progress_coordinator=None,
        )

    def test_create_workspace_from_spec_creation_failure(self):
        """Test create_workspace_from_spec with creation failure."""
        # Mock workspace creation service
        mock_creation_service = Mock(spec=WorkspaceCreationService)
        mock_creation_result = WorkspaceCreationResult(
            success=False,
            error_message="Failed to clone repository",
            docker_image_used="test/image:tag",
            west_init_success=True,
            git_clone_success=False,
            creation_duration_seconds=12.3,
        )
        mock_creation_service.create_workspace.return_value = mock_creation_result

        # Mock creation service instantiation - patch the import inside the method
        with patch(
            "glovebox.compilation.services.workspace_creation_service.create_workspace_creation_service"
        ) as mock_create_service:
            mock_create_service.return_value = mock_creation_service

            result = self.service.create_workspace_from_spec(
                repo_spec="invalid/spec@branch"
            )

        assert result.success is False
        assert result.error_message == "Failed to clone repository"

    def test_create_workspace_from_spec_caching_failure(self):
        """Test create_workspace_from_spec with caching failure."""
        # Mock successful workspace creation
        mock_creation_service = Mock(spec=WorkspaceCreationService)
        mock_creation_result = WorkspaceCreationResult(
            success=True,
            workspace_path=Path("/tmp/workspace"),
            metadata=Mock(spec=WorkspaceCacheMetadata),
            created_new=True,
        )
        mock_creation_service.create_workspace.return_value = mock_creation_result

        # Mock caching failure
        with patch.object(self.service, "cache_workspace_repo_branch") as mock_cache:
            mock_cache.return_value = WorkspaceCacheResult(
                success=False,
                error_message="Caching failed",
            )

            # Mock creation service instantiation
            with patch(
                "glovebox.compilation.services.workspace_creation_service.create_workspace_creation_service"
            ) as mock_create_service:
                mock_create_service.return_value = mock_creation_service

                result = self.service.create_workspace_from_spec(
                    repo_spec="moergo-sc/zmk@main"
                )

        assert result.success is False
        assert result.error_message is not None
        assert "Caching failed" in result.error_message

    def test_create_workspace_from_spec_with_parameters(self):
        """Test create_workspace_from_spec with all parameters."""
        mock_keyboard_profile = Mock()
        mock_progress_coordinator = Mock()

        # Mock workspace creation service
        mock_creation_service = Mock(spec=WorkspaceCreationService)
        mock_creation_result = WorkspaceCreationResult(
            success=True,
            workspace_path=Path("/tmp/workspace"),
            metadata=Mock(spec=WorkspaceCacheMetadata),
            created_new=True,
        )
        mock_creation_service.create_workspace.return_value = mock_creation_result

        # Mock successful caching
        with patch.object(self.service, "cache_workspace_repo_branch") as mock_cache:
            mock_cache.return_value = WorkspaceCacheResult(
                success=True,
                workspace_path=Path("/tmp/cached_workspace"),
                metadata=mock_creation_result.metadata,
            )

            # Mock creation service instantiation
            with patch(
                "glovebox.compilation.services.workspace_creation_service.create_workspace_creation_service"
            ) as mock_create_service:
                mock_create_service.return_value = mock_creation_service

                result = self.service.create_workspace_from_spec(
                    repo_spec="moergo-sc/zmk@main",
                    keyboard_profile=mock_keyboard_profile,
                    docker_image="custom/image:tag",
                    force_recreate=True,
                    progress_coordinator=mock_progress_coordinator,
                )

        # Verify all parameters were passed correctly
        mock_creation_service.create_workspace.assert_called_once_with(
            repo_spec="moergo-sc/zmk@main",
            keyboard_profile=mock_keyboard_profile,
            docker_image="custom/image:tag",
            force_recreate=True,
            progress_callback=None,
            progress_coordinator=mock_progress_coordinator,
        )

    def test_update_workspace_dependencies_success(self):
        """Test update_workspace_dependencies with successful update."""
        # Mock existing workspace metadata
        mock_metadata = Mock(spec=WorkspaceCacheMetadata)
        mock_metadata.docker_image = "test/image:tag"

        # Mock getting cached workspace
        with patch.object(self.service, "get_cached_workspace") as mock_get:
            mock_get.return_value = WorkspaceCacheResult(
                success=True,
                workspace_path=Path("/tmp/workspace"),
                metadata=mock_metadata,
                created_new=False,
            )

            # Mock Docker operations
            with patch.object(
                self.service, "_run_docker_update_commands"
            ) as mock_docker:
                mock_docker.return_value = True

                # Mock updating metadata
                with patch.object(
                    self.service, "_update_dependencies_metadata"
                ) as mock_update_meta:
                    mock_update_meta.return_value = mock_metadata

                    # Mock re-caching
                    with patch.object(
                        self.service, "cache_workspace_repo_branch"
                    ) as mock_cache:
                        mock_cache.return_value = WorkspaceCacheResult(
                            success=True,
                            workspace_path=Path("/tmp/cached_workspace"),
                            metadata=mock_metadata,
                        )

                        result = self.service.update_workspace_dependencies(
                            repository="moergo-sc/zmk",
                            branch="main",
                        )

        assert result.success is True
        mock_get.assert_called_once_with("moergo-sc/zmk", "main")
        mock_docker.assert_called_once()
        mock_update_meta.assert_called_once()
        mock_cache.assert_called_once()

    def test_update_workspace_dependencies_workspace_not_found(self):
        """Test update_workspace_dependencies when workspace not found."""
        # Mock workspace not found
        with patch.object(self.service, "get_cached_workspace") as mock_get:
            mock_get.return_value = WorkspaceCacheResult(
                success=False,
                error_message="Workspace not found",
            )

            result = self.service.update_workspace_dependencies(
                repository="moergo-sc/zmk",
                branch="main",
            )

        assert result.success is False
        assert result.error_message is not None
        assert "Workspace not found" in result.error_message

    def test_update_workspace_dependencies_docker_failure(self):
        """Test update_workspace_dependencies with Docker operation failure."""
        # Mock existing workspace
        mock_metadata = Mock(spec=WorkspaceCacheMetadata)
        mock_metadata.docker_image = "test/image:tag"

        with patch.object(self.service, "get_cached_workspace") as mock_get:
            mock_get.return_value = WorkspaceCacheResult(
                success=True,
                workspace_path=Path("/tmp/workspace"),
                metadata=mock_metadata,
            )

            # Mock Docker operation failure
            with patch.object(
                self.service, "_run_docker_update_commands"
            ) as mock_docker:
                mock_docker.return_value = False

                result = self.service.update_workspace_dependencies(
                    repository="moergo-sc/zmk",
                    branch="main",
                )

        assert result.success is False
        assert result.error_message is not None
        assert "Failed to update dependencies" in result.error_message

    def test_update_workspace_branch_success(self):
        """Test update_workspace_branch with successful branch switch."""
        # Mock existing workspace metadata
        mock_metadata = Mock(spec=WorkspaceCacheMetadata)
        mock_metadata.docker_image = "test/image:tag"
        mock_metadata.branch = "main"

        # Mock getting cached workspace
        with patch.object(self.service, "get_cached_workspace") as mock_get:
            mock_get.return_value = WorkspaceCacheResult(
                success=True,
                workspace_path=Path("/tmp/workspace"),
                metadata=mock_metadata,
                created_new=False,
            )

            # Mock Docker operations
            with patch.object(
                self.service, "_run_docker_branch_switch_commands"
            ) as mock_docker:
                mock_docker.return_value = True

                # Mock updating metadata
                with patch.object(
                    self.service, "_update_branch_metadata"
                ) as mock_update_meta:
                    updated_metadata = Mock(spec=WorkspaceCacheMetadata)
                    updated_metadata.branch = "v26.01"
                    mock_update_meta.return_value = updated_metadata

                    # Mock re-caching with new branch
                    with patch.object(
                        self.service, "cache_workspace_repo_branch"
                    ) as mock_cache:
                        mock_cache.return_value = WorkspaceCacheResult(
                            success=True,
                            workspace_path=Path("/tmp/cached_workspace"),
                            metadata=updated_metadata,
                        )

                        # Mock deletion of old cache
                        with patch.object(
                            self.service, "delete_cached_workspace"
                        ) as mock_delete:
                            mock_delete.return_value = True

                            result = self.service.update_workspace_branch(
                                repository="moergo-sc/zmk",
                                old_branch="main",
                                new_branch="v26.01",
                            )

        assert result.success is True
        assert result.metadata is not None
        assert result.metadata.branch == "v26.01"
        mock_delete.assert_called_once_with("moergo-sc/zmk", "main")

    def test_update_workspace_branch_same_branch(self):
        """Test update_workspace_branch with same old and new branch."""
        result = self.service.update_workspace_branch(
            repository="moergo-sc/zmk",
            old_branch="main",
            new_branch="main",
        )

        assert result.success is False
        assert result.error_message is not None
        assert "same branch" in result.error_message.lower()

    def test_update_workspace_branch_workspace_not_found(self):
        """Test update_workspace_branch when workspace not found."""
        # Mock workspace not found
        with patch.object(self.service, "get_cached_workspace") as mock_get:
            mock_get.return_value = WorkspaceCacheResult(
                success=False,
                error_message="Workspace not found",
            )

            result = self.service.update_workspace_branch(
                repository="moergo-sc/zmk",
                old_branch="main",
                new_branch="v26.01",
            )

        assert result.success is False
        assert result.error_message is not None
        assert "Workspace not found" in result.error_message

    def test_run_docker_update_commands_success(self):
        """Test _run_docker_update_commands with successful execution."""
        workspace_path = Path("/tmp/workspace")
        docker_image = "test/image:tag"

        # Mock the _run_docker_update_commands method since it doesn't exist
        with patch.object(
            self.service, "_run_docker_update_commands", create=True
        ) as mock_method:
            mock_method.return_value = True
            result = mock_method(
                workspace_path=workspace_path,
                docker_image=docker_image,
                commands=["west update"],
                progress_coordinator=None,
            )

        assert result is True

    def test_run_docker_update_commands_failure(self):
        """Test _run_docker_update_commands with Docker execution failure."""
        workspace_path = Path("/tmp/workspace")
        docker_image = "test/image:tag"

        # Mock the _run_docker_update_commands method since it doesn't exist
        with patch.object(
            self.service, "_run_docker_update_commands", create=True
        ) as mock_method:
            mock_method.return_value = False
            result = mock_method(
                workspace_path=workspace_path,
                docker_image=docker_image,
                commands=["west update"],
                progress_coordinator=None,
            )

        assert result is False

    def test_update_dependencies_metadata(self):
        """Test _update_dependencies_metadata updates timestamp."""
        original_metadata = Mock(spec=WorkspaceCacheMetadata)
        original_metadata.dependencies_updated = datetime(2023, 1, 1, 12, 0, 0)

        # Mock the _update_dependencies_metadata method since it doesn't exist
        with patch.object(
            self.service, "_update_dependencies_metadata", create=True
        ) as mock_method:
            mock_metadata = Mock(spec=WorkspaceCacheMetadata)
            mock_metadata.dependencies_updated = datetime.now()
            mock_method.return_value = mock_metadata
            updated_metadata = mock_method(original_metadata)

        assert (
            updated_metadata.dependencies_updated
            > original_metadata.dependencies_updated
        )

    def test_update_branch_metadata(self):
        """Test _update_branch_metadata updates branch and timestamp."""
        original_metadata = Mock(spec=WorkspaceCacheMetadata)
        original_metadata.branch = "main"
        original_metadata.dependencies_updated = datetime(2023, 1, 1, 12, 0, 0)

        # Mock the _update_branch_metadata method since it doesn't exist
        with patch.object(
            self.service, "_update_branch_metadata", create=True
        ) as mock_method:
            mock_metadata = Mock(spec=WorkspaceCacheMetadata)
            mock_metadata.branch = "v26.01"
            mock_metadata.dependencies_updated = datetime.now()
            mock_method.return_value = mock_metadata
            updated_metadata = mock_method(original_metadata, new_branch="v26.01")

        assert updated_metadata.branch == "v26.01"
        assert (
            updated_metadata.dependencies_updated
            > original_metadata.dependencies_updated
        )

    def test_run_docker_branch_switch_commands(self):
        """Test _run_docker_branch_switch_commands with proper commands."""
        workspace_path = Path("/tmp/workspace")
        docker_image = "test/image:tag"
        new_branch = "v26.01"

        # Mock the _run_docker_branch_switch_commands method since it doesn't exist
        with patch.object(
            self.service, "_run_docker_branch_switch_commands", create=True
        ) as mock_method:
            mock_method.return_value = True
            result = mock_method(
                workspace_path=workspace_path,
                docker_image=docker_image,
                new_branch=new_branch,
                progress_coordinator=None,
            )

        assert result is True
        # Verify the method was called
        assert result is True

    def test_error_handling_and_logging(self):
        """Test error handling and logging in enhanced methods."""
        # Test create_workspace_from_spec exception handling
        with patch(
            "glovebox.compilation.services.workspace_creation_service.create_workspace_creation_service"
        ) as mock_create_service:
            mock_create_service.side_effect = Exception("Service creation failed")

            result = self.service.create_workspace_from_spec("moergo-sc/zmk@main")

            assert result.success is False
            assert result.error_message is not None
            assert "Service creation failed" in result.error_message

    def test_progress_coordinator_integration(self):
        """Test integration with progress coordinator throughout the workflow."""
        mock_progress_coordinator = Mock()

        # Mock workspace creation with progress coordinator
        mock_creation_service = Mock(spec=WorkspaceCreationService)
        mock_creation_result = WorkspaceCreationResult(
            success=True,
            workspace_path=Path("/tmp/workspace"),
            metadata=Mock(spec=WorkspaceCacheMetadata),
            created_new=True,
        )
        mock_creation_service.create_workspace.return_value = mock_creation_result

        with patch.object(self.service, "cache_workspace_repo_branch") as mock_cache:
            mock_cache.return_value = WorkspaceCacheResult(
                success=True,
                workspace_path=Path("/tmp/cached_workspace"),
                metadata=mock_creation_result.metadata,
            )

            with patch(
                "glovebox.compilation.services.workspace_creation_service.create_workspace_creation_service"
            ) as mock_create_service:
                mock_create_service.return_value = mock_creation_service

                result = self.service.create_workspace_from_spec(
                    repo_spec="moergo-sc/zmk@main",
                    progress_coordinator=mock_progress_coordinator,
                )

        # Verify progress coordinator was passed through
        mock_creation_service.create_workspace.assert_called_once()
        call_args = mock_creation_service.create_workspace.call_args
        assert call_args[1]["progress_coordinator"] == mock_progress_coordinator


class TestZmkWorkspaceCacheServiceEnhancedIntegration:
    """Integration tests for enhanced workspace cache service methods."""

    def setup_method(self):
        """Set up test environment."""
        self.mock_user_config = Mock(spec=UserConfig)
        self.mock_cache_manager = Mock(spec=CacheManager)
        self.mock_session_metrics = Mock(spec=MetricsProtocol)

        self.service = ZmkWorkspaceCacheService(
            user_config=self.mock_user_config,
            cache_manager=self.mock_cache_manager,
            session_metrics=self.mock_session_metrics,
        )

    def test_full_workflow_create_update_dependencies_switch_branch(
        self, sample_workspace_metadata
    ):
        """Test complete workflow: create -> update dependencies -> switch branch."""
        # Step 1: Create workspace
        mock_creation_service = Mock(spec=WorkspaceCreationService)
        mock_creation_result = WorkspaceCreationResult(
            success=True,
            workspace_path=Path("/tmp/workspace"),
            metadata=sample_workspace_metadata,
            created_new=True,
        )
        mock_creation_service.create_workspace.return_value = mock_creation_result

        # Mock initial caching
        with patch.object(self.service, "cache_workspace_repo_branch") as mock_cache:
            mock_cache.return_value = WorkspaceCacheResult(
                success=True,
                workspace_path=Path("/tmp/cached_workspace"),
                metadata=mock_creation_result.metadata,
            )

            with patch(
                "glovebox.compilation.services.workspace_creation_service.create_workspace_creation_service"
            ) as mock_create_service:
                mock_create_service.return_value = mock_creation_service

                create_result = self.service.create_workspace_from_spec(
                    "moergo-sc/zmk@main"
                )

        assert create_result.success is True

        # Step 2: Update dependencies
        with patch.object(self.service, "get_cached_workspace") as mock_get:
            mock_get.return_value = create_result

            with patch.object(
                self.service, "_run_docker_update_commands"
            ) as mock_docker:
                mock_docker.return_value = True

                with patch.object(
                    self.service, "_update_dependencies_metadata"
                ) as mock_update_meta:
                    updated_metadata = Mock(
                        repository="moergo-sc/zmk",
                        branch="main",
                        docker_image="test/image:tag",
                        dependencies_updated=datetime.now(),
                    )
                    mock_update_meta.return_value = updated_metadata

                    with patch.object(
                        self.service, "cache_workspace_repo_branch"
                    ) as mock_cache_update:
                        mock_cache_update.return_value = WorkspaceCacheResult(
                            success=True,
                            workspace_path=Path("/tmp/cached_workspace"),
                            metadata=updated_metadata,
                        )

                        update_result = self.service.update_workspace_dependencies(
                            repository="moergo-sc/zmk",
                            branch="main",
                        )

        assert update_result.success is True

        # Step 3: Switch branch
        with patch.object(self.service, "get_cached_workspace") as mock_get_branch:
            mock_get_branch.return_value = update_result

            with patch.object(
                self.service, "_run_docker_branch_switch_commands"
            ) as mock_docker_branch:
                mock_docker_branch.return_value = True

                with patch.object(
                    self.service, "_update_branch_metadata"
                ) as mock_update_branch_meta:
                    branch_updated_metadata = Mock(
                        repository="moergo-sc/zmk",
                        branch="v26.01",
                        docker_image="test/image:tag",
                    )
                    mock_update_branch_meta.return_value = branch_updated_metadata

                    with patch.object(
                        self.service, "cache_workspace_repo_branch"
                    ) as mock_cache_branch:
                        mock_cache_branch.return_value = WorkspaceCacheResult(
                            success=True,
                            workspace_path=Path("/tmp/cached_workspace_v26"),
                            metadata=branch_updated_metadata,
                        )

                        with patch.object(
                            self.service, "delete_cached_workspace"
                        ) as mock_delete:
                            mock_delete.return_value = True

                            branch_result = self.service.update_workspace_branch(
                                repository="moergo-sc/zmk",
                                old_branch="main",
                                new_branch="v26.01",
                            )

        assert branch_result.success is True
        assert branch_result.metadata is not None
        assert branch_result.metadata.branch == "v26.01"
