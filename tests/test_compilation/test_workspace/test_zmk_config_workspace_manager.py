"""Test ZmkConfigWorkspaceManager class."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.compilation.workspace.zmk_config_workspace_manager import (
    ZmkConfigWorkspaceManager,
    ZmkConfigWorkspaceManagerError,
    create_zmk_config_workspace_manager,
)
from glovebox.config.compile_methods import ZmkWorkspaceConfig


class TestZmkConfigWorkspaceManager:
    """Test ZmkConfigWorkspaceManager functionality."""

    def setup_method(self):
        """Set up test instance."""
        self.manager = ZmkConfigWorkspaceManager()

    def test_initialization(self):
        """Test manager initialization."""
        assert hasattr(self.manager, "logger")
        assert self.manager.workspace_root == Path.cwd() / ".workspace"

    def test_initialization_custom_root(self):
        """Test manager initialization with custom workspace root."""
        custom_root = Path("/tmp/custom_zmk_workspace")
        manager = ZmkConfigWorkspaceManager(workspace_root=custom_root)
        assert manager.workspace_root == custom_root

    def test_create_zmk_config_workspace_manager(self):
        """Test factory function."""
        manager = create_zmk_config_workspace_manager()
        assert isinstance(manager, ZmkConfigWorkspaceManager)

    def test_initialize_workspace_missing_config(self):
        """Test workspace initialization with missing config."""
        with pytest.raises(
            ZmkConfigWorkspaceManagerError, match="config_repo_config is required"
        ):
            self.manager.initialize_workspace()

    def test_initialize_workspace_invalid_config(self):
        """Test workspace initialization with invalid config."""
        with pytest.raises(
            ZmkConfigWorkspaceManagerError, match="config_repo_config is required"
        ):
            self.manager.initialize_workspace(config_repo_config="invalid")

    @patch("subprocess.run")
    def test_initialize_workspace_success(self, mock_run):
        """Test successful workspace initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "zmk_workspace"
            keymap_file = Path(temp_dir) / "keymap.keymap"
            config_file = Path(temp_dir) / "config.conf"

            # Create test files
            keymap_file.write_text("keymap content")
            config_file.write_text("config content")

            # Mock successful subprocess calls
            mock_run.return_value = Mock(returncode=0, stderr="", stdout="")

            config = ZmkWorkspaceConfig(
                config_repo_url="https://github.com/example/zmk-config.git",
                config_repo_revision="main",
            )

            with patch.object(
                self.manager, "copy_user_configuration", return_value=True
            ):
                result = self.manager.initialize_workspace(
                    config_repo_config=config,
                    workspace_path=workspace_path,
                    keymap_file=keymap_file,
                    config_file=config_file,
                )

            assert result is True
            assert workspace_path.exists()

    def test_validate_workspace_missing_directory(self):
        """Test workspace validation with missing directory."""
        workspace_path = Path("/nonexistent/workspace")
        result = self.manager.validate_workspace(workspace_path)
        assert result is False

    def test_validate_workspace_missing_west_yml(self):
        """Test workspace validation with missing west.yml."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir)
            result = self.manager.validate_workspace(workspace_path)
            assert result is False

    def test_validate_workspace_missing_config_dir(self):
        """Test workspace validation with missing config directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir)

            # Create west.yml but no config directory
            (workspace_path / "west.yml").write_text("manifest: {}")

            result = self.manager.validate_workspace(workspace_path)
            assert result is False

    def test_validate_workspace_missing_build_yaml(self):
        """Test workspace validation with missing build.yaml."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir)

            # Create west.yml and config directory but no build.yaml
            (workspace_path / "west.yml").write_text("manifest: {}")
            (workspace_path / "config").mkdir()

            result = self.manager.validate_workspace(workspace_path)
            assert result is False

    def test_validate_workspace_success(self):
        """Test successful workspace validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir)

            # Create all required files and directories
            (workspace_path / "west.yml").write_text("manifest: {}")
            (workspace_path / "config").mkdir()
            (workspace_path / "build.yaml").write_text("include: []")

            result = self.manager.validate_workspace(workspace_path)
            assert result is True

    def test_cleanup_workspace_nonexistent(self):
        """Test cleanup of nonexistent workspace."""
        workspace_path = Path("/nonexistent/workspace")
        result = self.manager.cleanup_workspace(workspace_path)
        assert result is True

    def test_cleanup_workspace_success(self):
        """Test successful workspace cleanup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir)

            # Create build and west directories
            build_dir = workspace_path / "build"
            west_dir = workspace_path / ".west"
            build_dir.mkdir()
            west_dir.mkdir()

            # Add some content
            (build_dir / "firmware.uf2").write_bytes(b"firmware")
            (west_dir / "config").write_text("west config")

            result = self.manager.cleanup_workspace(workspace_path)
            assert result is True
            assert not build_dir.exists()
            assert not west_dir.exists()

    @patch("subprocess.run")
    def test_clone_config_repository_success(self, mock_run):
        """Test successful config repository cloning."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "cloned_repo"

            # Mock successful git clone
            mock_run.return_value = Mock(returncode=0, stderr="", stdout="")

            config = ZmkWorkspaceConfig(
                config_repo_url="https://github.com/example/zmk-config.git",
                config_repo_revision="main",
            )

            result = self.manager.clone_config_repository(config, workspace_path)
            assert result is True

            # Verify git clone command was called correctly
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert call_args[0] == "git"
            assert call_args[1] == "clone"
            assert "--branch" in call_args
            assert "main" in call_args
            assert "--depth" in call_args
            assert "1" in call_args
            assert "https://github.com/example/zmk-config.git" in call_args

    @patch("subprocess.run")
    def test_clone_config_repository_no_ref(self, mock_run):
        """Test config repository cloning without git reference."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "cloned_repo"

            # Mock successful git clone
            mock_run.return_value = Mock(returncode=0, stderr="", stdout="")

            config = ZmkWorkspaceConfig(
                config_repo_url="https://github.com/example/zmk-config.git",
                config_repo_revision="",
            )

            result = self.manager.clone_config_repository(config, workspace_path)
            assert result is True

            # Verify git clone command was called without branch
            call_args = mock_run.call_args[0][0]
            assert "--branch" not in call_args

    @patch("subprocess.run")
    def test_clone_config_repository_failure(self, mock_run):
        """Test config repository cloning failure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "cloned_repo"

            # Mock failed git clone
            mock_run.return_value = Mock(returncode=1, stderr="Clone failed", stdout="")

            config = ZmkWorkspaceConfig(
                config_repo_url="https://github.com/example/zmk-config.git"
            )

            with pytest.raises(
                ZmkConfigWorkspaceManagerError, match="Git clone failed"
            ):
                self.manager.clone_config_repository(config, workspace_path)

    @patch("subprocess.run")
    def test_clone_config_repository_timeout(self, mock_run):
        """Test config repository cloning timeout."""
        import subprocess

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "cloned_repo"

            # Mock timeout
            mock_run.side_effect = subprocess.TimeoutExpired("git", 300)

            config = ZmkWorkspaceConfig(
                config_repo_url="https://github.com/example/zmk-config.git"
            )

            with pytest.raises(
                ZmkConfigWorkspaceManagerError, match="Git clone timed out"
            ):
                self.manager.clone_config_repository(config, workspace_path)

    @patch("subprocess.run")
    def test_initialize_west_workspace_success(self, mock_run):
        """Test successful west workspace initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir)

            # Mock successful west commands
            mock_run.return_value = Mock(returncode=0, stderr="", stdout="")

            result = self.manager.initialize_west_workspace(workspace_path)
            assert result is True

            # Verify both west init and west update were called
            assert mock_run.call_count == 2

            # Check first call (west init)
            first_call = mock_run.call_args_list[0][0][0]
            assert first_call[:3] == ["west", "init", "-l"]

            # Check second call (west update)
            second_call = mock_run.call_args_list[1][0][0]
            assert second_call == ["west", "update"]

    @patch("subprocess.run")
    def test_initialize_west_workspace_init_failure(self, mock_run):
        """Test west workspace initialization with init failure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir)

            # Mock failed west init
            mock_run.return_value = Mock(returncode=1, stderr="Init failed", stdout="")

            with pytest.raises(
                ZmkConfigWorkspaceManagerError, match="West init failed"
            ):
                self.manager.initialize_west_workspace(workspace_path)

    @patch("subprocess.run")
    def test_initialize_west_workspace_update_failure(self, mock_run):
        """Test west workspace initialization with update failure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir)

            # Mock successful init but failed update
            mock_run.side_effect = [
                Mock(returncode=0, stderr="", stdout=""),  # west init success
                Mock(
                    returncode=1, stderr="Update failed", stdout=""
                ),  # west update failure
            ]

            with pytest.raises(
                ZmkConfigWorkspaceManagerError, match="West update failed"
            ):
                self.manager.initialize_west_workspace(workspace_path)

    @patch("subprocess.run")
    def test_initialize_west_workspace_timeout(self, mock_run):
        """Test west workspace initialization timeout."""
        import subprocess

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir)

            # Mock timeout
            mock_run.side_effect = subprocess.TimeoutExpired("west", 120)

            with pytest.raises(
                ZmkConfigWorkspaceManagerError, match="West command timed out"
            ):
                self.manager.initialize_west_workspace(workspace_path)

    def test_copy_user_configuration_success(self):
        """Test successful user configuration copying."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "workspace"
            keymap_file = Path(temp_dir) / "source.keymap"
            config_file = Path(temp_dir) / "source.conf"

            # Create source files
            keymap_file.write_text("keymap content")
            config_file.write_text("config content")

            # Create workspace directory
            workspace_path.mkdir()

            result = self.manager.copy_user_configuration(
                workspace_path, keymap_file, config_file
            )
            assert result is True

            # Verify files were copied
            config_dir = workspace_path / "config"
            assert config_dir.exists()
            assert (config_dir / "source.keymap").exists()
            assert (config_dir / "source.conf").exists()
            assert (config_dir / "source.keymap").read_text() == "keymap content"
            assert (config_dir / "source.conf").read_text() == "config content"

    def test_copy_user_configuration_nonexistent_files(self):
        """Test user configuration copying with nonexistent source files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "workspace"
            keymap_file = Path(temp_dir) / "missing.keymap"
            config_file = Path(temp_dir) / "missing.conf"

            workspace_path.mkdir()

            # Should not fail with missing files
            result = self.manager.copy_user_configuration(
                workspace_path, keymap_file, config_file
            )
            assert result is True

            # Config directory should still be created
            config_dir = workspace_path / "config"
            assert config_dir.exists()


class TestZmkConfigWorkspaceManagerIntegration:
    """Test ZmkConfigWorkspaceManager integration scenarios."""

    def setup_method(self):
        """Set up test instance."""
        self.manager = ZmkConfigWorkspaceManager()

    @patch("subprocess.run")
    def test_full_workspace_lifecycle(self, mock_run):
        """Test complete ZMK config workspace lifecycle."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "zmk_workspace"
            keymap_file = Path(temp_dir) / "glove80.keymap"
            config_file = Path(temp_dir) / "glove80.conf"

            # Create test files
            keymap_file.write_text("ZMK keymap content")
            config_file.write_text("CONFIG_USB_HID=y")

            # Mock successful subprocess calls
            mock_run.return_value = Mock(returncode=0, stderr="", stdout="")

            config = ZmkWorkspaceConfig(
                config_repo_url="https://github.com/example/zmk-config.git",
                config_repo_revision="main",
            )

            # Initialize workspace
            result = self.manager.initialize_workspace(
                config_repo_config=config,
                workspace_path=workspace_path,
                keymap_file=keymap_file,
                config_file=config_file,
            )
            assert result is True
            assert workspace_path.exists()

            # Create validation files
            (workspace_path / "west.yml").write_text("manifest: {}")
            (workspace_path / "config").mkdir(exist_ok=True)
            (workspace_path / "build.yaml").write_text("include: []")

            # Validate workspace
            is_valid = self.manager.validate_workspace(workspace_path)
            assert is_valid is True

            # Create build artifacts
            build_dir = workspace_path / "build"
            west_dir = workspace_path / ".west"
            build_dir.mkdir()
            west_dir.mkdir()
            (build_dir / "firmware.uf2").write_bytes(b"firmware")

            # Cleanup workspace
            cleanup_success = self.manager.cleanup_workspace(workspace_path)
            assert cleanup_success is True
            assert not build_dir.exists()
            assert not west_dir.exists()

    def test_workspace_error_handling(self):
        """Test workspace error handling scenarios."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "error_workspace"

            # Test initialization error with invalid config
            with pytest.raises(ZmkConfigWorkspaceManagerError):
                self.manager.initialize_workspace(config_repo_config="invalid")

            # Test validation error handling
            with (
                patch.object(self.manager, "logger") as mock_logger,
                patch("pathlib.Path.exists", side_effect=OSError("Access error")),
                pytest.raises(ZmkConfigWorkspaceManagerError),
            ):
                self.manager.validate_workspace(workspace_path)

            # Test cleanup error handling
            with patch("shutil.rmtree", side_effect=OSError("Permission denied")):
                workspace_path.mkdir()
                (workspace_path / "build").mkdir()

                with pytest.raises(ZmkConfigWorkspaceManagerError):
                    self.manager.cleanup_workspace(workspace_path)

    def test_github_actions_pattern_compliance(self):
        """Test compliance with GitHub Actions workflow pattern."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir)

            # Create GitHub Actions-style workspace structure
            (workspace_path / "west.yml").write_text("""
manifest:
  defaults:
    remote: zmkfirmware
  projects:
    - name: zmk
      remote: zmkfirmware
            """)

            config_dir = workspace_path / "config"
            config_dir.mkdir()

            # Create build.yaml matching GitHub Actions pattern
            (workspace_path / "build.yaml").write_text("""
include:
  - board: glove80_lh
  - board: glove80_rh
            """)

            # Create typical config files
            (config_dir / "glove80.keymap").write_text("/* ZMK keymap */")
            (config_dir / "glove80.conf").write_text("CONFIG_ZMK_RGB_UNDERGLOW=y")

            # Should validate successfully
            result = self.manager.validate_workspace(workspace_path)
            assert result is True

    @patch("subprocess.run")
    def test_real_world_zmk_config_simulation(self, mock_run):
        """Test simulation of real-world ZMK config repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "zmk_config"
            keymap_file = Path(temp_dir) / "corne.keymap"
            config_file = Path(temp_dir) / "corne.conf"

            # Create realistic user files
            keymap_file.write_text("""
#include <behaviors.dtsi>
#include <dt-bindings/zmk/keys.h>

/ {
    keymap {
        compatible = "zmk,keymap";
        default_layer {
            bindings = <&kp Q &kp W &kp E>;
        };
    };
};
            """)

            config_file.write_text("""
CONFIG_ZMK_SLEEP=y
CONFIG_ZMK_IDLE_SLEEP_TIMEOUT=3600000
CONFIG_BT_CTLR_TX_PWR_PLUS_8=y
            """)

            # Mock successful git and west operations
            mock_run.return_value = Mock(returncode=0, stderr="", stdout="")

            config = ZmkWorkspaceConfig(
                config_repo_url="https://github.com/user/zmk-config.git",
                config_repo_revision="corne-config",
            )

            # Full workflow simulation
            result = self.manager.initialize_workspace(
                config_repo_config=config,
                workspace_path=workspace_path,
                keymap_file=keymap_file,
                config_file=config_file,
            )

            assert result is True

            # Verify git clone was called with correct parameters
            git_calls = [
                call for call in mock_run.call_args_list if call[0][0][0] == "git"
            ]
            assert len(git_calls) == 1
            git_args = git_calls[0][0][0]
            assert "corne-config" in git_args

            # Verify west commands were called
            west_calls = [
                call for call in mock_run.call_args_list if call[0][0][0] == "west"
            ]
            assert len(west_calls) == 2  # init and update
