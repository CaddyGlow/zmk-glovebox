"""Test west workspace manager."""

import tempfile
from pathlib import Path
from unittest.mock import Mock

from glovebox.compilation.workspace.west_workspace_manager import (
    WestWorkspaceManager,
    create_west_workspace_manager,
)
from glovebox.config.compile_methods import WestWorkspaceConfig


class TestWestWorkspaceManager:
    """Test west workspace manager functionality."""

    def setup_method(self):
        """Set up test instance."""
        self.file_adapter = Mock()
        self.docker_adapter = Mock()
        self.manager = WestWorkspaceManager(self.file_adapter, self.docker_adapter)

    def test_initialization(self):
        """Test manager initialization."""
        manager = WestWorkspaceManager()
        assert hasattr(manager, "file_adapter")
        assert hasattr(manager, "docker_adapter")

    def test_create_west_workspace_manager(self):
        """Test factory function."""
        manager = create_west_workspace_manager()
        assert isinstance(manager, WestWorkspaceManager)

    def test_initialize_workspace_success(self):
        """Test successful workspace initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "workspace"
            keymap_file = Path(temp_dir) / "keymap.keymap"
            config_file = Path(temp_dir) / "config.conf"

            # Create test files
            keymap_file.write_text("/* test keymap */")
            config_file.write_text("CONFIG_TEST=y")

            workspace_config = WestWorkspaceConfig(
                workspace_path=str(workspace_path),
                config_path="config",
                manifest_url="https://github.com/zmkfirmware/zmk",
                manifest_revision="main",
                west_commands=[],
            )

            # Mock file adapter operations
            self.file_adapter.check_exists.side_effect = lambda path: path.exists()
            self.file_adapter.create_directory.side_effect = lambda path: path.mkdir(
                parents=True, exist_ok=True
            )
            self.file_adapter.read_text.side_effect = lambda path: path.read_text()
            self.file_adapter.write_text.side_effect = (
                lambda path, content: path.write_text(content)
            )

            # Mock Docker container execution success
            self.docker_adapter.run_container.return_value = (0, [], [])

            result = self.manager.initialize_west_workspace(
                workspace_config, keymap_file, config_file
            )

            assert result is True
            self.docker_adapter.run_container.assert_called_once()

    def test_initialize_workspace_context_success(self):
        """Test workspace initialization via context interface."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "workspace"
            keymap_file = Path(temp_dir) / "keymap.keymap"
            config_file = Path(temp_dir) / "config.conf"

            # Create test files
            keymap_file.write_text("/* test keymap */")
            config_file.write_text("CONFIG_TEST=y")

            workspace_config = WestWorkspaceConfig(
                workspace_path=str(workspace_path),
                config_path="config",
                manifest_url="https://github.com/zmkfirmware/zmk",
                manifest_revision="main",
                west_commands=[],
            )

            # Mock file adapter operations
            self.file_adapter.check_exists.side_effect = lambda path: path.exists()
            self.file_adapter.create_directory.side_effect = lambda path: path.mkdir(
                parents=True, exist_ok=True
            )
            self.file_adapter.read_text.side_effect = lambda path: path.read_text()
            self.file_adapter.write_text.side_effect = (
                lambda path, content: path.write_text(content)
            )

            # Mock Docker container execution success
            self.docker_adapter.run_container.return_value = (0, [], [])

            result = self.manager.initialize_workspace(
                workspace_config=workspace_config,
                keymap_file=keymap_file,
                config_file=config_file,
            )

            assert result is True

    def test_initialize_workspace_missing_parameters(self):
        """Test workspace initialization with missing parameters."""
        result = self.manager.initialize_workspace(
            workspace_config=None,
            keymap_file=None,
        )

        assert result is False

    def test_initialize_workspace_no_docker_adapter(self):
        """Test workspace initialization without Docker adapter."""
        # Temporarily set docker_adapter to None for testing
        original_adapter = self.manager.docker_adapter
        self.manager.docker_adapter = None  # type: ignore[assignment]

        workspace_config = Mock(spec=WestWorkspaceConfig)
        keymap_file = Path("/tmp/keymap.keymap")
        config_file = Path("/tmp/config.conf")

        try:
            result = self.manager.initialize_west_workspace(
                workspace_config, keymap_file, config_file
            )

            assert result is False
        finally:
            # Restore original adapter
            self.manager.docker_adapter = original_adapter

    def test_initialize_workspace_docker_failure(self):
        """Test workspace initialization with Docker failure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "workspace"
            keymap_file = Path(temp_dir) / "keymap.keymap"
            config_file = Path(temp_dir) / "config.conf"

            workspace_config = WestWorkspaceConfig(
                workspace_path=str(workspace_path),
                config_path="config",
                manifest_url="https://github.com/zmkfirmware/zmk",
                manifest_revision="main",
                west_commands=[],
            )

            # Mock file adapter operations
            self.file_adapter.check_exists.return_value = False
            self.file_adapter.create_directory.return_value = None
            self.file_adapter.read_text.return_value = "test content"
            self.file_adapter.write_text.return_value = None

            # Mock Docker container execution failure
            self.docker_adapter.run_container.return_value = (1, [], ["Error"])

            result = self.manager.initialize_west_workspace(
                workspace_config, keymap_file, config_file
            )

            assert result is False

    def test_initialize_workspace_file_copy_failure(self):
        """Test workspace initialization with file copy failure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "workspace"
            keymap_file = Path(temp_dir) / "keymap.keymap"
            config_file = Path(temp_dir) / "config.conf"

            workspace_config = WestWorkspaceConfig(
                workspace_path=str(workspace_path),
                config_path="config",
                manifest_url="https://github.com/zmkfirmware/zmk",
                manifest_revision="main",
                west_commands=[],
            )

            # Mock file adapter operations
            self.file_adapter.check_exists.return_value = False
            self.file_adapter.create_directory.return_value = None
            self.file_adapter.read_text.side_effect = Exception("File read error")
            self.file_adapter.write_text.return_value = None

            # Mock Docker container execution success
            self.docker_adapter.run_container.return_value = (0, [], [])

            # Should continue despite file copy failure
            result = self.manager.initialize_west_workspace(
                workspace_config, keymap_file, config_file
            )

            assert result is True

    def test_initialize_workspace_with_west_commands(self):
        """Test workspace initialization with additional west commands."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "workspace"
            keymap_file = Path(temp_dir) / "keymap.keymap"
            config_file = Path(temp_dir) / "config.conf"

            workspace_config = WestWorkspaceConfig(
                workspace_path=str(workspace_path),
                config_path="config",
                manifest_url="https://github.com/zmkfirmware/zmk",
                manifest_revision="main",
                west_commands=["west zephyr-export", "west build"],
            )

            # Mock file adapter operations
            self.file_adapter.check_exists.return_value = False
            self.file_adapter.create_directory.return_value = None
            self.file_adapter.read_text.return_value = "test content"
            self.file_adapter.write_text.return_value = None

            # Mock Docker container execution success
            self.docker_adapter.run_container.return_value = (0, [], [])

            result = self.manager.initialize_west_workspace(
                workspace_config, keymap_file, config_file
            )

            assert result is True

            # Verify Docker was called with west commands
            call_args = self.docker_adapter.run_container.call_args
            assert "west zephyr-export" in call_args[1]["command"][2]
            assert "west build" in call_args[1]["command"][2]

    def test_initialize_workspace_exception_handling(self):
        """Test workspace initialization exception handling."""
        workspace_config = WestWorkspaceConfig(
            workspace_path="/tmp/workspace",
            config_path="config",
            manifest_url="https://github.com/zmkfirmware/zmk",
            manifest_revision="main",
            west_commands=[],
        )

        keymap_file = Path("/tmp/keymap.keymap")
        config_file = Path("/tmp/config.conf")

        # Mock file adapter to raise exception
        self.file_adapter.check_exists.side_effect = Exception("Filesystem error")

        result = self.manager.initialize_west_workspace(
            workspace_config, keymap_file, config_file
        )

        assert result is False


class TestWestWorkspaceManagerIntegration:
    """Test west workspace manager integration scenarios."""

    def setup_method(self):
        """Set up test instance."""
        self.manager = create_west_workspace_manager()

    def test_workspace_lifecycle(self):
        """Test complete workspace lifecycle."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "lifecycle_workspace"
            keymap_file = Path(temp_dir) / "test.keymap"
            config_file = Path(temp_dir) / "test.conf"

            # Create test files
            keymap_file.write_text("/* test keymap */")
            config_file.write_text("CONFIG_TEST=y")

            workspace_config = WestWorkspaceConfig(
                workspace_path=str(workspace_path),
                config_path="config",
                manifest_url="https://github.com/zmkfirmware/zmk",
                manifest_revision="main",
                west_commands=["west zephyr-export"],
            )

            # Mock the manager's adapters for testing
            self.manager.file_adapter = Mock()
            self.manager.docker_adapter = Mock()

            # Mock file operations
            self.manager.file_adapter.check_exists.side_effect = (
                lambda path: path.exists()
            )
            self.manager.file_adapter.create_directory.side_effect = (
                lambda path: path.mkdir(parents=True, exist_ok=True)
            )
            self.manager.file_adapter.read_text.side_effect = (
                lambda path: path.read_text()
            )
            self.manager.file_adapter.write_text.side_effect = (
                lambda path, content: path.write_text(content)
            )

            # Mock Docker operations
            self.manager.docker_adapter.run_container.return_value = (0, [], [])

            # Test initialization
            result = self.manager.initialize_west_workspace(
                workspace_config, keymap_file, config_file
            )

            assert result is True

            # Verify workspace validation would pass
            assert self.manager.validate_workspace(workspace_path) is True

    def test_workspace_error_scenarios(self):
        """Test various workspace error scenarios."""
        workspace_config = WestWorkspaceConfig(
            workspace_path="/nonexistent/workspace",
            config_path="config",
            manifest_url="https://github.com/zmkfirmware/zmk",
            manifest_revision="main",
            west_commands=[],
        )

        error_scenarios = [
            ("docker_failure", (1, [], ["Docker error"])),
            ("docker_timeout", Exception("Container timeout")),
        ]

        for scenario_name, docker_result in error_scenarios:
            # Mock the manager's adapters for testing
            self.manager.file_adapter = Mock()
            self.manager.docker_adapter = Mock()

            # Mock file operations
            self.manager.file_adapter.check_exists.return_value = False
            self.manager.file_adapter.create_directory.return_value = None
            self.manager.file_adapter.read_text.return_value = "test"
            self.manager.file_adapter.write_text.return_value = None

            if scenario_name == "docker_failure":
                self.manager.docker_adapter.run_container.return_value = docker_result
            else:
                self.manager.docker_adapter.run_container.side_effect = docker_result

            keymap_file = Path("/tmp/test.keymap")
            config_file = Path("/tmp/test.conf")

            result = self.manager.initialize_west_workspace(
                workspace_config, keymap_file, config_file
            )

            assert result is False
