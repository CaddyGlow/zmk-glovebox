"""Tests for DockerPath and DockerPathSet."""

from pathlib import Path
from unittest.mock import patch

import pytest


pytestmark = [pytest.mark.docker, pytest.mark.integration]

from glovebox.models.docker_path import (
    DockerPath,
    DockerPathSet,
    # create_zmk_docker_paths,  # TODO: Function removed, update tests
)


class TestDockerPath:
    """Test DockerPath functionality."""

    def test_basic_creation(self):
        """Test basic DockerPath creation."""
        docker_path = DockerPath(
            host_path=Path("/host/path"), container_path="/container/path"
        )

        assert docker_path.host() == Path("/host/path").resolve()
        assert docker_path.container() == "/container/path"

    def test_vol_mapping(self):
        """Test volume mapping generation."""
        docker_path = DockerPath(
            host_path=Path("/host/workspace"), container_path="/workspace"
        )

        vol_mapping = docker_path.vol()
        expected_host = str(Path("/host/workspace").resolve())

        assert vol_mapping == (expected_host, "/workspace")

    def test_path_resolution(self):
        """Test path resolution with Path objects."""
        host_path = Path("/tmp/build")
        docker_path = DockerPath(host_path=host_path, container_path="/workspace")

        assert docker_path.host() == host_path.resolve()
        assert docker_path.container() == "/workspace"

    def test_join_subpaths(self):
        """Test joining subpaths to create new DockerPath."""
        base_path = DockerPath(
            host_path=Path("/host/workspace"), container_path="/workspace"
        )

        config_path = base_path.join("config")
        assert config_path.host() == Path("/host/workspace/config").resolve()
        assert config_path.container() == "/workspace/config"

        # Multiple subpaths
        nested_path = base_path.join("config", "keyboards", "glove80")
        assert (
            nested_path.host()
            == Path("/host/workspace/config/keyboards/glove80").resolve()
        )
        assert nested_path.container() == "/workspace/config/keyboards/glove80"

    def test_join_handles_double_slashes(self):
        """Test that join handles double slashes in container paths."""
        # Container path with trailing slash
        base_path = DockerPath(
            host_path=Path("/host/workspace"), container_path="/workspace/"
        )
        config_path = base_path.join("config")

        assert config_path.container() == "/workspace/config"

    def test_string_representations(self):
        """Test string and repr representations."""
        docker_path = DockerPath(
            host_path=Path("/host/path"), container_path="/container/path"
        )

        str_repr = str(docker_path)
        assert "/host/path" in str_repr
        assert "/container/path" in str_repr

        repr_str = repr(docker_path)
        assert "DockerPath" in repr_str
        assert "host_path=" in repr_str
        assert "container_path=" in repr_str


class TestDockerPathSet:
    """Test DockerPathSet functionality."""

    def test_basic_creation(self):
        """Test basic DockerPathSet creation."""
        path_set = DockerPathSet("/tmp/build")

        assert path_set.base_host_path == Path("/tmp/build").resolve()
        assert len(path_set.paths) == 0

    def test_add_paths(self):
        """Test adding paths to the set."""
        path_set = DockerPathSet("/tmp/build")

        path_set.add("workspace", "/workspace")
        path_set.add("config", "/workspace/config", "config")

        assert path_set.has("workspace")
        assert path_set.has("config")
        assert len(path_set.paths) == 2

    def test_add_method_chaining(self):
        """Test method chaining with add."""
        path_set = (
            DockerPathSet("/tmp/build")
            .add("workspace", "/workspace")
            .add("config", "/workspace/config")
            .add("build", "/workspace/build")
        )

        assert len(path_set.paths) == 3
        assert path_set.has("workspace")
        assert path_set.has("config")
        assert path_set.has("build")

    def test_get_path(self):
        """Test getting paths from the set."""
        path_set = DockerPathSet("/tmp/build")
        path_set.add("workspace", "/workspace")

        workspace_path = path_set.get("workspace")
        assert isinstance(workspace_path, DockerPath)
        assert workspace_path.container() == "/workspace"
        assert workspace_path.host() == Path("/tmp/build/workspace").resolve()

    def test_get_nonexistent_path(self):
        """Test getting non-existent path raises KeyError."""
        path_set = DockerPathSet("/tmp/build")

        with pytest.raises(KeyError, match="Docker path 'nonexistent' not found"):
            path_set.get("nonexistent")

    def test_add_without_base_path(self):
        """Test adding paths without base_host_path raises ValueError."""
        path_set = DockerPathSet()

        with pytest.raises(ValueError, match="base_host_path must be set"):
            path_set.add("workspace", "/workspace")

    def test_add_path_direct(self):
        """Test adding pre-created DockerPath instances."""
        path_set = DockerPathSet()
        docker_path = DockerPath(
            host_path=Path("/custom/host"), container_path="/custom/container"
        )

        path_set.add_path("custom", docker_path)

        assert path_set.has("custom")
        retrieved_path = path_set.get("custom")
        assert retrieved_path.host() == Path("/custom/host").resolve()
        assert retrieved_path.container() == "/custom/container"

    def test_volumes_generation(self):
        """Test generating all volume mappings."""
        path_set = (
            DockerPathSet("/tmp/build")
            .add("workspace", "/workspace")
            .add("config", "/workspace/config")
        )

        volumes = path_set.volumes()

        assert len(volumes) == 2
        expected_workspace = (str(Path("/tmp/build/workspace").resolve()), "/workspace")
        expected_config = (
            str(Path("/tmp/build/config").resolve()),
            "/workspace/config",
        )

        assert expected_workspace in volumes
        assert expected_config in volumes

    def test_names_listing(self):
        """Test listing all path names."""
        path_set = (
            DockerPathSet("/tmp/build")
            .add("workspace", "/workspace")
            .add("config", "/workspace/config")
            .add("build", "/workspace/build")
        )

        names = path_set.names()

        assert "workspace" in names
        assert "config" in names
        assert "build" in names
        assert len(names) == 3

    def test_custom_host_subpaths(self):
        """Test using custom host subpaths."""
        path_set = DockerPathSet("/tmp/build")

        # Custom subpath different from logical name
        path_set.add("config", "/workspace/config", "keyboard_config")

        config_path = path_set.get("config")
        assert config_path.host() == Path("/tmp/build/keyboard_config").resolve()
        assert config_path.container() == "/workspace/config"


# TODO: Update tests - create_zmk_docker_paths function was removed
# class TestCreateZmkDockerPaths:
#     """Test ZMK Docker paths factory function."""
#
#     def test_create_standard_zmk_paths(self):
#         """Test creating standard ZMK Docker path set."""
#         path_set = create_zmk_docker_paths("/tmp/zmk_build")

#         # Check all expected paths exist
#         expected_paths = ["workspace", "config", "build", "output", "cache"]
#         for path_name in expected_paths:
#             assert path_set.has(path_name)
#
#         # Check specific path mappings
#         workspace = path_set.get("workspace")
#         assert workspace.host() == Path("/tmp/zmk_build").resolve()
#         assert workspace.container() == "/workspace"
#
#         config = path_set.get("config")
#         assert config.host() == Path("/tmp/zmk_build/config").resolve()
#         assert config.container() == "/workspace/config"
#
#         build = path_set.get("build")
#         assert build.host() == Path("/tmp/zmk_build/build").resolve()
#         assert build.container() == "/workspace/build"
#
#     def test_zmk_paths_volume_mappings(self):
#         """Test ZMK paths generate correct volume mappings."""
#         path_set = create_zmk_docker_paths("/tmp/zmk_build")
#
#         volumes = path_set.volumes()
#
#         # Should have 5 volume mappings
#         assert len(volumes) == 5
#
#         # Check workspace mapping specifically
#         workspace_mapping = path_set.get("workspace").vol()
#         expected_host = str(Path("/tmp/zmk_build").resolve())
#         assert workspace_mapping == (expected_host, "/workspace")


class TestDockerPathIntegration:
    """Integration tests for Docker path functionality."""

    def test_typical_usage_workflow(self):
        """Test typical usage workflow."""
        # Create workspace path
        workspace = DockerPath(
            host_path=Path("/home/user/zmk-builds/build123"),
            container_path="/workspace",
        )

        # Get volume mapping for Docker
        volume_mapping = workspace.vol()
        expected_host = str(Path("/home/user/zmk-builds/build123").resolve())
        assert volume_mapping == (expected_host, "/workspace")

        # Create config subpath
        config = workspace.join("config")
        config_volume = config.vol()
        expected_config_host = str(
            Path("/home/user/zmk-builds/build123/config").resolve()
        )
        assert config_volume == (expected_config_host, "/workspace/config")

    def test_path_set_usage_workflow(self):
        """Test path set usage workflow."""
        # Create organized path set
        paths = (
            DockerPathSet("/tmp/build_session")
            .add("workspace", "/workspace")
            .add("config", "/workspace/config")
            .add("build", "/workspace/build")
        )

        # Use paths for Docker command
        workspace_vol = paths.get("workspace").vol()
        config_path = paths.get("config").container()

        # Verify results
        expected_workspace_host = str(Path("/tmp/build_session/workspace").resolve())
        assert workspace_vol == (expected_workspace_host, "/workspace")
        assert config_path == "/workspace/config"

        # Get all volumes for Docker run command
        all_volumes = paths.volumes()
        assert len(all_volumes) == 3

    def test_temp_directory_integration(self):
        """Test integration with temporary directories."""
        import tempfile

        with tempfile.TemporaryDirectory(prefix="zmk_build_") as temp_dir:
            # TODO: Update test - create_zmk_docker_paths function was removed
            # Create Docker paths using temp directory
            # path_set = create_zmk_docker_paths(temp_dir)
            #
            # # Verify paths point to temp directory
            # workspace = path_set.get("workspace")
            # assert str(workspace.host()).startswith(temp_dir)
            #
            # # Verify volume mapping works
            pass  # Test commented out
            # vol_mapping = workspace.vol()
            # assert vol_mapping[0] == str(Path(temp_dir).resolve())
            # assert vol_mapping[1] == "/workspace"
