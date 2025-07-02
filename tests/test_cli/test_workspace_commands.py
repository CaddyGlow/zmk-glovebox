"""Tests for CLI workspace management commands."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest


pytestmark = [pytest.mark.docker, pytest.mark.integration]
from typer.testing import CliRunner

from glovebox.cli.app import app
from glovebox.cli.commands import register_all_commands
from glovebox.compilation.cache.models import (
    WorkspaceCacheMetadata,
    WorkspaceCacheResult,
)
from glovebox.compilation.cache.workspace_cache_service import ZmkWorkspaceCacheService
from glovebox.config.models.cache import CacheLevel
from glovebox.core.cache.cache_coordinator import reset_shared_cache_instances


class TestWorkspaceCreateCommand:
    """Test the workspace create CLI command."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        reset_shared_cache_instances()
        # Register all commands to ensure workspace commands are available
        register_all_commands(app)

    def teardown_method(self):
        """Clean up test environment."""
        reset_shared_cache_instances()

    def test_workspace_create_basic_success(self, isolated_cli_environment):
        """Test basic workspace creation with valid repo spec."""
        # Mock the workspace cache service
        with patch(
            "glovebox.cli.commands.cache.workspace.get_cache_manager_and_service"
        ) as mock_get_service:
            mock_cache_manager = Mock()
            mock_workspace_service = Mock(spec=ZmkWorkspaceCacheService)
            mock_user_config = Mock()

            # Mock successful workspace creation
            mock_metadata = Mock(spec=WorkspaceCacheMetadata)
            mock_metadata.repository = "moergo-sc/zmk"
            mock_metadata.branch = "main"
            mock_metadata.workspace_path = Path("/tmp/cached_workspace")
            mock_metadata.size_bytes = 1024 * 1024  # 1MB
            mock_metadata.cached_components = ["zmk", "zephyr", ".west"]
            mock_metadata.docker_image = "zmkfirmware/zmk-dev-arm:stable"
            mock_metadata.creation_profile = None

            mock_result = WorkspaceCacheResult(
                success=True,
                workspace_path=Path("/tmp/cached_workspace"),
                metadata=mock_metadata,
                created_new=True,
            )
            mock_workspace_service.create_workspace_from_spec.return_value = mock_result

            mock_get_service.return_value = (
                mock_cache_manager,
                mock_workspace_service,
                mock_user_config,
            )

            result = self.runner.invoke(
                app, ["cache", "workspace", "create", "moergo-sc/zmk@main"]
            )

        assert result.exit_code == 0
        assert "Workspace created successfully" in result.stdout
        assert "moergo-sc/zmk" in result.stdout
        assert "main" in result.stdout
        # Verify the call was made with the expected parameters (progress_coordinator is created internally)
        mock_workspace_service.create_workspace_from_spec.assert_called_once()
        call_args = mock_workspace_service.create_workspace_from_spec.call_args
        assert call_args[1]["repo_spec"] == "moergo-sc/zmk@main"
        assert call_args[1]["keyboard_profile"] is None
        assert call_args[1]["docker_image"] is None
        assert call_args[1]["force_recreate"] is False
        assert (
            call_args[1]["progress_coordinator"] is not None
        )  # Progress coordinator is created internally

    def test_workspace_create_with_profile(self, isolated_cli_environment):
        """Test workspace creation with keyboard profile."""
        with patch(
            "glovebox.cli.commands.cache.workspace.get_cache_manager_and_service"
        ) as mock_get_service:
            mock_cache_manager = Mock()
            mock_workspace_service = Mock(spec=ZmkWorkspaceCacheService)
            mock_user_config = Mock()

            # Mock successful workspace creation
            mock_metadata = Mock(spec=WorkspaceCacheMetadata)
            mock_metadata.repository = "moergo-sc/zmk"
            mock_metadata.branch = "v26.01"
            mock_metadata.workspace_path = Path("/tmp/cached_workspace")
            mock_metadata.size_bytes = 2048 * 1024  # 2MB
            mock_metadata.cached_components = ["zmk", "zephyr"]
            mock_metadata.docker_image = "custom/image:tag"
            mock_metadata.creation_profile = "glove80"

            mock_result = WorkspaceCacheResult(
                success=True,
                workspace_path=Path("/tmp/cached_workspace"),
                metadata=mock_metadata,
                created_new=True,
            )
            mock_workspace_service.create_workspace_from_spec.return_value = mock_result

            mock_get_service.return_value = (
                mock_cache_manager,
                mock_workspace_service,
                mock_user_config,
            )

            # Mock keyboard profile creation
            with patch(
                "glovebox.config.create_keyboard_profile"
            ) as mock_create_profile:
                mock_profile = Mock()
                mock_create_profile.return_value = mock_profile

                result = self.runner.invoke(
                    app,
                    [
                        "cache",
                        "workspace",
                        "create",
                        "moergo-sc/zmk@v26.01",
                        "--profile",
                        "glove80/v25.05",
                    ],
                )

        assert result.exit_code == 0
        assert "Workspace created successfully" in result.stdout
        assert "glove80" in result.stdout
        mock_create_profile.assert_called_once_with("glove80", "v25.05")

    def test_workspace_create_with_docker_image(self, isolated_cli_environment):
        """Test workspace creation with custom Docker image."""
        with patch(
            "glovebox.cli.commands.cache.workspace.get_cache_manager_and_service"
        ) as mock_get_service:
            mock_cache_manager = Mock()
            mock_workspace_service = Mock(spec=ZmkWorkspaceCacheService)
            mock_user_config = Mock()

            # Mock successful workspace creation
            mock_metadata = Mock(spec=WorkspaceCacheMetadata)
            mock_metadata.repository = "zmkfirmware/zmk"
            mock_metadata.branch = "v3.5.0"
            mock_metadata.workspace_path = Path("/tmp/cached_workspace")
            mock_metadata.docker_image = "custom/zmk:latest"

            mock_result = WorkspaceCacheResult(
                success=True,
                workspace_path=Path("/tmp/cached_workspace"),
                metadata=mock_metadata,
                created_new=True,
            )
            mock_workspace_service.create_workspace_from_spec.return_value = mock_result

            mock_get_service.return_value = (
                mock_cache_manager,
                mock_workspace_service,
                mock_user_config,
            )

            result = self.runner.invoke(
                app,
                [
                    "cache",
                    "workspace",
                    "create",
                    "zmkfirmware/zmk@v3.5.0",
                    "--docker-image",
                    "custom/zmk:latest",
                ],
            )

        assert result.exit_code == 0
        mock_workspace_service.create_workspace_from_spec.assert_called_once()
        call_args = mock_workspace_service.create_workspace_from_spec.call_args
        assert call_args[1]["docker_image"] == "custom/zmk:latest"

    def test_workspace_create_with_force_flag(self, isolated_cli_environment):
        """Test workspace creation with force recreation."""
        with patch(
            "glovebox.cli.commands.cache.workspace.get_cache_manager_and_service"
        ) as mock_get_service:
            mock_cache_manager = Mock()
            mock_workspace_service = Mock(spec=ZmkWorkspaceCacheService)
            mock_user_config = Mock()

            # Mock successful workspace creation
            mock_metadata = Mock()
            mock_result = WorkspaceCacheResult(
                success=True,
                workspace_path=Path("/tmp/cached_workspace"),
                metadata=mock_metadata,
                created_new=True,
            )
            mock_workspace_service.create_workspace_from_spec.return_value = mock_result

            mock_get_service.return_value = (
                mock_cache_manager,
                mock_workspace_service,
                mock_user_config,
            )

            result = self.runner.invoke(
                app, ["cache", "workspace", "create", "moergo-sc/zmk@main", "--force"]
            )

        assert result.exit_code == 0
        call_args = mock_workspace_service.create_workspace_from_spec.call_args
        assert call_args[1]["force_recreate"] is True

    def test_workspace_create_failure(self, isolated_cli_environment):
        """Test workspace creation failure handling."""
        with patch(
            "glovebox.cli.commands.cache.workspace.get_cache_manager_and_service"
        ) as mock_get_service:
            mock_cache_manager = Mock()
            mock_workspace_service = Mock(spec=ZmkWorkspaceCacheService)
            mock_user_config = Mock()

            # Mock failed workspace creation
            mock_result = WorkspaceCacheResult(
                success=False,
                error_message="Failed to clone repository",
            )
            mock_workspace_service.create_workspace_from_spec.return_value = mock_result

            mock_get_service.return_value = (
                mock_cache_manager,
                mock_workspace_service,
                mock_user_config,
            )

            result = self.runner.invoke(
                app, ["cache", "workspace", "create", "invalid/repo@branch"]
            )

        assert result.exit_code == 1
        assert "Failed to create workspace" in result.stdout
        assert "Failed to clone repository" in result.stdout

    def test_workspace_create_invalid_profile(self, isolated_cli_environment):
        """Test workspace creation with invalid profile."""
        with patch(
            "glovebox.cli.commands.cache.workspace.get_cache_manager_and_service"
        ) as mock_get_service:
            mock_cache_manager = Mock()
            mock_workspace_service = Mock(spec=ZmkWorkspaceCacheService)
            mock_user_config = Mock()
            mock_get_service.return_value = (
                mock_cache_manager,
                mock_workspace_service,
                mock_user_config,
            )

            # Mock profile creation failure
            with patch(
                "glovebox.config.create_keyboard_profile"
            ) as mock_create_profile:
                mock_create_profile.side_effect = Exception("Invalid profile")

                result = self.runner.invoke(
                    app,
                    [
                        "cache",
                        "workspace",
                        "create",
                        "moergo-sc/zmk@main",
                        "--profile",
                        "invalid-profile",
                    ],
                )

        assert result.exit_code == 1
        assert "Invalid keyboard profile" in result.stdout

    def test_workspace_create_exception_handling(self, isolated_cli_environment):
        """Test workspace create command exception handling."""
        with patch(
            "glovebox.cli.commands.cache.workspace.get_cache_manager_and_service"
        ) as mock_get_service:
            mock_get_service.side_effect = Exception("Service initialization failed")

            result = self.runner.invoke(
                app, ["cache", "workspace", "create", "moergo-sc/zmk@main"]
            )

        assert result.exit_code == 1
        assert "Error:" in result.stdout


class TestWorkspaceNewCommand:
    """Test the workspace new CLI command (alias for create)."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        reset_shared_cache_instances()
        register_all_commands(app)

    def teardown_method(self):
        """Clean up test environment."""
        reset_shared_cache_instances()

    def test_workspace_new_basic_functionality(self, isolated_cli_environment):
        """Test that workspace new command works as create alias."""
        with patch(
            "glovebox.cli.commands.cache.workspace.get_cache_manager_and_service"
        ) as mock_get_service:
            mock_cache_manager = Mock()
            mock_workspace_service = Mock(spec=ZmkWorkspaceCacheService)
            mock_user_config = Mock()

            # Mock successful workspace creation
            mock_metadata = Mock(spec=WorkspaceCacheMetadata)
            mock_metadata.repository = "test/repo"
            mock_metadata.branch = "main"
            mock_metadata.workspace_path = Path("/tmp/test")

            mock_result = WorkspaceCacheResult(
                success=True,
                workspace_path=Path("/tmp/test"),
                metadata=mock_metadata,
                created_new=True,
            )
            mock_workspace_service.create_workspace_from_spec.return_value = mock_result

            mock_get_service.return_value = (
                mock_cache_manager,
                mock_workspace_service,
                mock_user_config,
            )

            result = self.runner.invoke(
                app, ["cache", "workspace", "new", "test/repo@main"]
            )

        assert result.exit_code == 0
        assert "Workspace created successfully" in result.stdout
        mock_workspace_service.create_workspace_from_spec.assert_called_once()

    def test_workspace_new_with_all_options(self, isolated_cli_environment):
        """Test workspace new command with all options."""
        with patch(
            "glovebox.cli.commands.cache.workspace.get_cache_manager_and_service"
        ) as mock_get_service:
            mock_cache_manager = Mock()
            mock_workspace_service = Mock(spec=ZmkWorkspaceCacheService)
            mock_user_config = Mock()

            # Mock successful workspace creation
            mock_metadata = Mock()
            mock_result = WorkspaceCacheResult(
                success=True,
                workspace_path=Path("/tmp/test"),
                metadata=mock_metadata,
                created_new=True,
            )
            mock_workspace_service.create_workspace_from_spec.return_value = mock_result

            mock_get_service.return_value = (
                mock_cache_manager,
                mock_workspace_service,
                mock_user_config,
            )

            # Mock keyboard profile creation
            with patch(
                "glovebox.config.create_keyboard_profile"
            ) as mock_create_profile:
                mock_profile = Mock()
                mock_create_profile.return_value = mock_profile

                result = self.runner.invoke(
                    app,
                    [
                        "cache",
                        "workspace",
                        "new",
                        "test/repo@branch",
                        "--profile",
                        "glove80",
                        "--docker-image",
                        "custom:tag",
                        "--force",
                    ],
                )

        assert result.exit_code == 0
        # Verify all parameters were passed correctly
        call_args = mock_workspace_service.create_workspace_from_spec.call_args
        assert call_args[1]["force_recreate"] is True
        assert call_args[1]["docker_image"] == "custom:tag"


class TestWorkspaceUpdateCommand:
    """Test the workspace update CLI command."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        reset_shared_cache_instances()
        register_all_commands(app)

    def teardown_method(self):
        """Clean up test environment."""
        reset_shared_cache_instances()

    def test_workspace_update_dependencies_only(self, isolated_cli_environment):
        """Test workspace update with dependencies only."""
        with patch(
            "glovebox.cli.commands.cache.workspace.get_cache_manager_and_service"
        ) as mock_get_service:
            mock_cache_manager = Mock()
            mock_workspace_service = Mock(spec=ZmkWorkspaceCacheService)
            mock_user_config = Mock()

            # Mock successful dependency update
            mock_metadata = Mock(spec=WorkspaceCacheMetadata)
            mock_metadata.repository = "moergo-sc/zmk"
            mock_metadata.branch = "main"
            mock_metadata.workspace_path = Path("/tmp/workspace")
            mock_metadata.dependencies_updated = "2024-01-01 12:00:00"
            mock_metadata.cached_components = ["zmk", "zephyr"]

            mock_result = WorkspaceCacheResult(
                success=True,
                workspace_path=Path("/tmp/workspace"),
                metadata=mock_metadata,
            )
            mock_workspace_service.update_workspace_dependencies.return_value = (
                mock_result
            )

            mock_get_service.return_value = (
                mock_cache_manager,
                mock_workspace_service,
                mock_user_config,
            )

            result = self.runner.invoke(
                app,
                [
                    "cache",
                    "workspace",
                    "update",
                    "moergo-sc/zmk",
                    "main",
                    "--dependencies-only",
                ],
            )

        assert result.exit_code == 0
        assert "updated dependencies" in result.stdout
        assert "moergo-sc/zmk" in result.stdout
        assert "main" in result.stdout
        mock_workspace_service.update_workspace_dependencies.assert_called_once_with(
            repository="moergo-sc/zmk",
            branch="main",
            progress_coordinator=None,
        )

    def test_workspace_update_switch_branch(self, isolated_cli_environment):
        """Test workspace update with branch switching."""
        with patch(
            "glovebox.cli.commands.cache.workspace.get_cache_manager_and_service"
        ) as mock_get_service:
            mock_cache_manager = Mock()
            mock_workspace_service = Mock(spec=ZmkWorkspaceCacheService)
            mock_user_config = Mock()

            # Mock successful branch switch
            mock_metadata = Mock(spec=WorkspaceCacheMetadata)
            mock_metadata.repository = "moergo-sc/zmk"
            mock_metadata.branch = "v26.01"  # New branch
            mock_metadata.workspace_path = Path("/tmp/workspace")
            mock_metadata.dependencies_updated = "2024-01-01 12:00:00"

            mock_result = WorkspaceCacheResult(
                success=True,
                workspace_path=Path("/tmp/workspace"),
                metadata=mock_metadata,
            )
            mock_workspace_service.update_workspace_branch.return_value = mock_result

            mock_get_service.return_value = (
                mock_cache_manager,
                mock_workspace_service,
                mock_user_config,
            )

            result = self.runner.invoke(
                app,
                [
                    "cache",
                    "workspace",
                    "update",
                    "moergo-sc/zmk",
                    "main",
                    "--new-branch",
                    "v26.01",
                ],
            )

        assert result.exit_code == 0
        assert "switched to branch v26.01" in result.stdout
        assert "v26.01" in result.stdout
        mock_workspace_service.update_workspace_branch.assert_called_once_with(
            repository="moergo-sc/zmk",
            old_branch="main",
            new_branch="v26.01",
            progress_coordinator=None,
        )

    def test_workspace_update_default_behavior(self, isolated_cli_environment):
        """Test workspace update default behavior (update dependencies)."""
        with patch(
            "glovebox.cli.commands.cache.workspace.get_cache_manager_and_service"
        ) as mock_get_service:
            mock_cache_manager = Mock()
            mock_workspace_service = Mock(spec=ZmkWorkspaceCacheService)
            mock_user_config = Mock()

            # Mock successful dependency update
            mock_metadata = Mock()
            mock_result = WorkspaceCacheResult(
                success=True,
                workspace_path=Path("/tmp/workspace"),
                metadata=mock_metadata,
            )
            mock_workspace_service.update_workspace_dependencies.return_value = (
                mock_result
            )

            mock_get_service.return_value = (
                mock_cache_manager,
                mock_workspace_service,
                mock_user_config,
            )

            result = self.runner.invoke(
                app, ["cache", "workspace", "update", "moergo-sc/zmk", "main"]
            )

        assert result.exit_code == 0
        mock_workspace_service.update_workspace_dependencies.assert_called_once()

    def test_workspace_update_missing_branch_argument(self, isolated_cli_environment):
        """Test workspace update with missing branch argument."""
        result = self.runner.invoke(
            app, ["cache", "workspace", "update", "moergo-sc/zmk"]
        )

        assert result.exit_code == 1
        assert (
            "Either branch argument or --new-branch option must be provided"
            in result.stdout
        )

    def test_workspace_update_conflicting_options(self, isolated_cli_environment):
        """Test workspace update with conflicting options."""
        result = self.runner.invoke(
            app,
            [
                "cache",
                "workspace",
                "update",
                "moergo-sc/zmk",
                "main",
                "--dependencies-only",
                "--new-branch",
                "v26.01",
            ],
        )

        assert result.exit_code == 1
        assert "Cannot use --dependencies-only with --new-branch" in result.stdout

    def test_workspace_update_new_branch_without_current_branch(
        self, isolated_cli_environment
    ):
        """Test workspace update new branch without specifying current branch."""
        result = self.runner.invoke(
            app,
            ["cache", "workspace", "update", "moergo-sc/zmk", "--new-branch", "v26.01"],
        )

        assert result.exit_code == 1
        assert (
            "Current branch must be specified when switching branches" in result.stdout
        )

    def test_workspace_update_failure(self, isolated_cli_environment):
        """Test workspace update failure handling."""
        with patch(
            "glovebox.cli.commands.cache.workspace.get_cache_manager_and_service"
        ) as mock_get_service:
            mock_cache_manager = Mock()
            mock_workspace_service = Mock(spec=ZmkWorkspaceCacheService)
            mock_user_config = Mock()

            # Mock failed update
            mock_result = WorkspaceCacheResult(
                success=False,
                error_message="Workspace not found",
            )
            mock_workspace_service.update_workspace_dependencies.return_value = (
                mock_result
            )

            mock_get_service.return_value = (
                mock_cache_manager,
                mock_workspace_service,
                mock_user_config,
            )

            result = self.runner.invoke(
                app,
                [
                    "cache",
                    "workspace",
                    "update",
                    "nonexistent/repo",
                    "main",
                    "--dependencies-only",
                ],
            )

        assert result.exit_code == 1
        assert "Failed to update workspace" in result.stdout
        assert "Workspace not found" in result.stdout

    def test_workspace_update_success_without_metadata(self, isolated_cli_environment):
        """Test workspace update success but without metadata."""
        with patch(
            "glovebox.cli.commands.cache.workspace.get_cache_manager_and_service"
        ) as mock_get_service:
            mock_cache_manager = Mock()
            mock_workspace_service = Mock(spec=ZmkWorkspaceCacheService)
            mock_user_config = Mock()

            # Mock successful update but no metadata
            mock_result = WorkspaceCacheResult(
                success=True,
                workspace_path=Path("/tmp/workspace"),
                metadata=None,  # No metadata
            )
            mock_workspace_service.update_workspace_dependencies.return_value = (
                mock_result
            )

            mock_get_service.return_value = (
                mock_cache_manager,
                mock_workspace_service,
                mock_user_config,
            )

            result = self.runner.invoke(
                app,
                [
                    "cache",
                    "workspace",
                    "update",
                    "moergo-sc/zmk",
                    "main",
                    "--dependencies-only",
                ],
            )

        assert result.exit_code == 0
        assert "updated dependencies" in result.stdout

    def test_workspace_update_exception_handling(self, isolated_cli_environment):
        """Test workspace update command exception handling."""
        with patch(
            "glovebox.cli.commands.cache.workspace.get_cache_manager_and_service"
        ) as mock_get_service:
            mock_get_service.side_effect = Exception("Service error")

            result = self.runner.invoke(
                app, ["cache", "workspace", "update", "moergo-sc/zmk", "main"]
            )

        assert result.exit_code == 1
        assert "Error:" in result.stdout


class TestWorkspaceCommandsIntegration:
    """Integration tests for workspace commands."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        reset_shared_cache_instances()
        register_all_commands(app)

    def teardown_method(self):
        """Clean up test environment."""
        reset_shared_cache_instances()

    def test_workspace_commands_with_progress(self, isolated_cli_environment):
        """Test workspace commands with progress display."""
        with patch(
            "glovebox.cli.commands.cache.workspace.get_cache_manager_and_service"
        ) as mock_get_service:
            mock_cache_manager = Mock()
            mock_workspace_service = Mock(spec=ZmkWorkspaceCacheService)
            mock_user_config = Mock()

            # Mock successful creation
            mock_metadata = Mock()
            mock_result = WorkspaceCacheResult(
                success=True,
                workspace_path=Path("/tmp/workspace"),
                metadata=mock_metadata,
                created_new=True,
            )
            mock_workspace_service.create_workspace_from_spec.return_value = mock_result

            mock_get_service.return_value = (
                mock_cache_manager,
                mock_workspace_service,
                mock_user_config,
            )

            # Mock progress display components
            with (
                patch(
                    "glovebox.compilation.simple_progress.create_simple_compilation_display"
                ) as mock_display,
                patch(
                    "glovebox.compilation.simple_progress.create_simple_progress_coordinator"
                ) as mock_coordinator,
            ):
                mock_display_obj = Mock()
                mock_coordinator_obj = Mock()
                mock_display.return_value = mock_display_obj
                mock_coordinator.return_value = mock_coordinator_obj

                result = self.runner.invoke(
                    app,
                    [
                        "cache",
                        "workspace",
                        "create",
                        "moergo-sc/zmk@main",
                        "--progress",
                    ],
                )

            assert result.exit_code == 0
            # Verify progress components were used
            mock_display.assert_called_once()
            mock_coordinator.assert_called_once()
            mock_display_obj.start.assert_called_once()
            mock_display_obj.stop.assert_called_once()

    def test_workspace_commands_without_progress(self, isolated_cli_environment):
        """Test workspace commands with progress disabled."""
        with patch(
            "glovebox.cli.commands.cache.workspace.get_cache_manager_and_service"
        ) as mock_get_service:
            mock_cache_manager = Mock()
            mock_workspace_service = Mock(spec=ZmkWorkspaceCacheService)
            mock_user_config = Mock()

            # Mock successful creation
            mock_metadata = Mock()
            mock_result = WorkspaceCacheResult(
                success=True,
                workspace_path=Path("/tmp/workspace"),
                metadata=mock_metadata,
                created_new=True,
            )
            mock_workspace_service.create_workspace_from_spec.return_value = mock_result

            mock_get_service.return_value = (
                mock_cache_manager,
                mock_workspace_service,
                mock_user_config,
            )

            result = self.runner.invoke(
                app,
                ["cache", "workspace", "create", "moergo-sc/zmk@main", "--no-progress"],
            )

        assert result.exit_code == 0
        # Verify progress coordinator is None
        call_args = mock_workspace_service.create_workspace_from_spec.call_args
        assert call_args[1]["progress_coordinator"] is None

    def test_workspace_command_metrics_integration(self, isolated_cli_environment):
        """Test workspace commands with metrics integration."""
        with patch(
            "glovebox.cli.commands.cache.workspace.get_cache_manager_and_service"
        ) as mock_get_service:
            mock_cache_manager = Mock()
            mock_workspace_service = Mock(spec=ZmkWorkspaceCacheService)
            mock_user_config = Mock()

            # Mock successful creation
            mock_metadata = Mock()
            mock_result = WorkspaceCacheResult(
                success=True,
                workspace_path=Path("/tmp/workspace"),
                metadata=mock_metadata,
            )
            mock_workspace_service.create_workspace_from_spec.return_value = mock_result

            mock_get_service.return_value = (
                mock_cache_manager,
                mock_workspace_service,
                mock_user_config,
            )

            # Test with metrics decorator
            result = self.runner.invoke(
                app, ["cache", "workspace", "create", "moergo-sc/zmk@main"]
            )

        assert result.exit_code == 0
        # The @with_metrics decorator should handle metrics collection

    def test_workspace_help_commands(self, isolated_cli_environment):
        """Test workspace command help text."""
        # Test help for create command
        result = self.runner.invoke(app, ["cache", "workspace", "create", "--help"])

        assert result.exit_code == 0
        assert (
            "Create a new ZMK workspace from repository specification" in result.stdout
        )
        assert "org/repo@branch" in result.stdout
        assert "--profile" in result.stdout
        assert "--docker-image" in result.stdout
        assert "--force" in result.stdout

        # Test help for update command
        result = self.runner.invoke(app, ["cache", "workspace", "update", "--help"])

        assert result.exit_code == 0
        assert "Update existing cached workspace dependencies" in result.stdout
        assert "--new-branch" in result.stdout
        assert "--dependencies-only" in result.stdout
