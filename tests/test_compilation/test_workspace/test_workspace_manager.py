"""Test WorkspaceManager base class."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from glovebox.compilation.workspace.workspace_manager import (
    WorkspaceManager,
    WorkspaceManagerError,
    create_workspace_manager,
)


class ConcreteWorkspaceManager(WorkspaceManager):
    """Concrete implementation for testing."""

    def initialize_workspace(self, **context) -> bool:
        """Initialize test workspace."""
        return True

    def validate_workspace(self, workspace_path: Path) -> bool:
        """Validate test workspace."""
        return workspace_path.exists() and workspace_path.is_dir()

    def cleanup_workspace(self, workspace_path: Path) -> bool:
        """Clean up test workspace."""
        return True


class TestWorkspaceManager:
    """Test WorkspaceManager base functionality."""

    def setup_method(self):
        """Set up test instance."""
        self.manager = ConcreteWorkspaceManager()

    def test_initialization_default_workspace_root(self):
        """Test manager initialization with default workspace root."""
        manager = ConcreteWorkspaceManager()
        expected_root = Path.cwd() / ".workspace"
        assert manager.workspace_root == expected_root
        assert hasattr(manager, "logger")

    def test_initialization_custom_workspace_root(self):
        """Test manager initialization with custom workspace root."""
        custom_root = Path("/tmp/custom_workspace")
        manager = ConcreteWorkspaceManager(workspace_root=custom_root)
        assert manager.workspace_root == custom_root

    def test_ensure_workspace_directory(self):
        """Test workspace directory creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "new_workspace"
            assert not workspace_path.exists()

            self.manager.ensure_workspace_directory(workspace_path)
            assert workspace_path.exists()
            assert workspace_path.is_dir()

    def test_ensure_workspace_directory_existing(self):
        """Test workspace directory creation when it already exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir)
            assert workspace_path.exists()

            # Should not raise an error
            self.manager.ensure_workspace_directory(workspace_path)
            assert workspace_path.exists()

    def test_ensure_workspace_directory_nested(self):
        """Test workspace directory creation with nested paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "nested" / "workspace" / "dir"
            assert not workspace_path.exists()

            self.manager.ensure_workspace_directory(workspace_path)
            assert workspace_path.exists()
            assert workspace_path.is_dir()

    def test_ensure_workspace_directory_permission_error(self):
        """Test workspace directory creation with permission error."""
        with patch("pathlib.Path.mkdir") as mock_mkdir:
            mock_mkdir.side_effect = PermissionError("Permission denied")
            workspace_path = Path("/tmp/test_workspace")

            with pytest.raises(
                WorkspaceManagerError, match="Failed to create workspace directory"
            ):
                self.manager.ensure_workspace_directory(workspace_path)

    def test_check_workspace_permissions_valid(self):
        """Test workspace permissions check for valid directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir)
            result = self.manager.check_workspace_permissions(workspace_path)
            assert result is True

    def test_check_workspace_permissions_nonexistent(self):
        """Test workspace permissions check for nonexistent directory."""
        workspace_path = Path("/nonexistent/workspace")
        result = self.manager.check_workspace_permissions(workspace_path)
        assert result is False

    def test_check_workspace_permissions_read_only(self):
        """Test workspace permissions check for read-only directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir)

            # Mock touch to raise PermissionError
            with patch.object(Path, "touch", side_effect=PermissionError):
                result = self.manager.check_workspace_permissions(workspace_path)
                assert result is False

    def test_get_workspace_info_existing(self):
        """Test workspace info for existing directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir)

            # Create a test file
            test_file = workspace_path / "test.txt"
            test_file.write_text("test content")

            info = self.manager.get_workspace_info(workspace_path)

            assert info["path"] == str(workspace_path.resolve())
            assert info["exists"] is True
            assert info["is_directory"] is True
            assert info["readable"] is True
            assert info["writable"] is True
            assert info["size_bytes"] > 0
            assert "created" in info
            assert "modified" in info
            assert "permissions" in info

    def test_get_workspace_info_nonexistent(self):
        """Test workspace info for nonexistent directory."""
        workspace_path = Path("/nonexistent/workspace")
        info = self.manager.get_workspace_info(workspace_path)

        assert info["path"] == str(workspace_path.resolve())
        assert info["exists"] is False
        assert info["is_directory"] is False
        assert info["size_bytes"] == 0
        assert "created" not in info
        assert "modified" not in info

    def test_get_workspace_info_with_error(self):
        """Test workspace info when stat operations fail."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir)

            with patch.object(Path, "stat", side_effect=OSError("Stat failed")):
                info = self.manager.get_workspace_info(workspace_path)
                assert "error" in info
                assert "Stat failed" in info["error"]

    def test_abstract_methods_implemented(self):
        """Test that concrete implementation has all abstract methods."""
        manager = ConcreteWorkspaceManager()

        # Test initialize_workspace
        result = manager.initialize_workspace(test_param="value")
        assert result is True

        # Test validate_workspace
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir)
            result = manager.validate_workspace(workspace_path)
            assert result is True

        # Test cleanup_workspace
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir)
            result = manager.cleanup_workspace(workspace_path)
            assert result is True


class TestAbstractWorkspaceManager:
    """Test abstract WorkspaceManager behavior."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that WorkspaceManager cannot be instantiated directly."""
        with pytest.raises(TypeError, match="abstract"):
            WorkspaceManager()  # type: ignore[abstract]

    def test_create_workspace_manager_raises_not_implemented(self):
        """Test factory function raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="WorkspaceManager is abstract"):
            create_workspace_manager()


class TestWorkspaceManagerIntegration:
    """Test WorkspaceManager integration scenarios."""

    def setup_method(self):
        """Set up test instance."""
        self.manager = ConcreteWorkspaceManager()

    def test_full_workspace_lifecycle(self):
        """Test complete workspace lifecycle."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "test_workspace"

            # Initialize workspace
            self.manager.ensure_workspace_directory(workspace_path)
            assert workspace_path.exists()

            # Check permissions
            permissions_ok = self.manager.check_workspace_permissions(workspace_path)
            assert permissions_ok is True

            # Validate workspace
            is_valid = self.manager.validate_workspace(workspace_path)
            assert is_valid is True

            # Get workspace info
            info = self.manager.get_workspace_info(workspace_path)
            assert info["exists"] is True
            assert info["is_directory"] is True

            # Initialize with context
            success = self.manager.initialize_workspace(
                workspace_path=workspace_path, config={"test": "value"}
            )
            assert success is True

            # Cleanup workspace
            cleanup_success = self.manager.cleanup_workspace(workspace_path)
            assert cleanup_success is True

    def test_workspace_operations_with_files(self):
        """Test workspace operations with files and subdirectories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "file_workspace"
            self.manager.ensure_workspace_directory(workspace_path)

            # Create files and subdirectories
            (workspace_path / "config").mkdir()
            (workspace_path / "config" / "test.conf").write_text("config=value")
            (workspace_path / "keymap.keymap").write_text("keymap content")
            (workspace_path / "build").mkdir()
            (workspace_path / "build" / "output.uf2").write_bytes(b"firmware")

            # Test workspace info includes file sizes
            info = self.manager.get_workspace_info(workspace_path)
            assert info["size_bytes"] > 0
            assert info["exists"] is True
            assert info["is_directory"] is True

            # Test permissions still work with files
            permissions_ok = self.manager.check_workspace_permissions(workspace_path)
            assert permissions_ok is True

    def test_workspace_error_handling(self):
        """Test workspace error handling scenarios."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "error_workspace"

            # Test directory creation error handling
            with (
                patch("pathlib.Path.mkdir", side_effect=OSError("Mock error")),
                pytest.raises(WorkspaceManagerError),
            ):
                self.manager.ensure_workspace_directory(workspace_path)

            # Create workspace normally
            self.manager.ensure_workspace_directory(workspace_path)

            # Test permission checking with errors
            with (
                patch.object(self.manager, "logger") as mock_logger,
                patch("pathlib.Path.exists", side_effect=OSError("Access error")),
            ):
                result = self.manager.check_workspace_permissions(workspace_path)
                assert result is False
                mock_logger.error.assert_called()

    def test_workspace_manager_logging(self):
        """Test workspace manager logging behavior."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "log_workspace"

            with patch.object(self.manager, "logger") as mock_logger:
                # Test ensure_workspace_directory logging
                self.manager.ensure_workspace_directory(workspace_path)
                mock_logger.debug.assert_called_with(
                    "Ensured workspace directory: %s", workspace_path
                )

                # Test check_workspace_permissions logging
                mock_logger.reset_mock()
                self.manager.check_workspace_permissions(workspace_path)
                mock_logger.debug.assert_called_with(
                    "Workspace permissions verified: %s", workspace_path
                )
