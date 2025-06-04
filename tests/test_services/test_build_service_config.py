"""Tests for BuildService with keyboard configuration API."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.adapters.docker_adapter import DockerAdapter
from glovebox.adapters.file_adapter import FileAdapter
from glovebox.config.models import BuildConfig, KeyboardConfig
from glovebox.config.profile import KeyboardProfile
from glovebox.core.errors import BuildError
from glovebox.models.results import BuildResult
from glovebox.services.build_service import BuildService, create_build_service


class TestBuildServiceWithKeyboardConfig:
    """Test BuildService with the new keyboard configuration API."""

    def setup_method(self):
        """Set up test environment."""
        self.mock_file_adapter = Mock(spec=FileAdapter)
        self.mock_docker_adapter = Mock(spec=DockerAdapter)
        self.service = BuildService(self.mock_docker_adapter, self.mock_file_adapter)

    @patch("glovebox.services.build_service.get_available_keyboards")
    def test_validate_with_keyboard_config(
        self, mock_get_keyboards, mock_keyboard_config
    ):
        """Test validation with the keyboard configuration API."""
        # Setup mocks
        mock_get_keyboards.return_value = ["test_keyboard", "glove80"]

        # Test with a valid config
        valid_config = {
            "keyboard": "test_keyboard",
            "keymap_path": "/path/to/keymap.keymap",
            "kconfig_path": "/path/to/config.conf",
        }

        result = self.service.validate(valid_config)
        assert result.success is True

        # Verify the keyboard was checked against available keyboards
        mock_get_keyboards.assert_called_once()

    @patch("glovebox.config.keyboard_config.load_keyboard_config_raw")
    @patch("glovebox.config.keyboard_config.get_available_keyboards")
    def test_validate_invalid_keyboard(self, mock_get_keyboards, mock_load_config):
        """Test validation with an invalid keyboard."""
        # Setup mocks
        mock_get_keyboards.return_value = ["test_keyboard", "glove80"]

        # Test with an invalid keyboard
        invalid_config = {
            "keyboard": "nonexistent_keyboard",
            "keymap_path": "/path/to/keymap.keymap",
            "kconfig_path": "/path/to/config.conf",
        }

        result = self.service.validate(invalid_config)
        assert result.success is False
        assert "Unsupported keyboard" in result.errors[0]

    def test_get_build_environment_with_profile(self, mock_keyboard_config):
        """Test getting build environment using KeyboardProfile."""
        # Create a mock profile
        mock_build_config = Mock(spec=BuildConfig)
        mock_build_config.docker_image = "test-zmk-build"
        mock_build_config.branch = "test-branch"
        mock_build_config.repository = "test/zmk"
        mock_build_config.method = "docker"

        mock_keyboard_config_obj = Mock(spec=KeyboardConfig)
        mock_keyboard_config_obj.keyboard = "test_keyboard"
        mock_keyboard_config_obj.build = mock_build_config

        mock_profile = Mock(spec=KeyboardProfile)
        mock_profile.keyboard_config = mock_keyboard_config_obj
        mock_profile.keyboard_name = "test_keyboard"
        mock_profile.firmware_version = "test_version"

        # Test getting build environment with profile
        config = {"keyboard": "test_keyboard"}
        env = self.service.get_build_environment(config, mock_profile)

        # Verify the environment contains build settings from the profile
        assert "KEYBOARD" in env
        assert env["KEYBOARD"] == "test_keyboard"
        assert "DOCKER_IMAGE" in env
        assert env["DOCKER_IMAGE"] == "test-zmk-build"
        assert "BRANCH" in env
        assert env["BRANCH"] == "test-branch"
        assert "REPO" in env
        assert env["REPO"] == "test/zmk"

    @patch("glovebox.services.build_service.load_keyboard_config_raw")
    def test_get_build_environment_from_keyboard_config(
        self, mock_load_config, mock_keyboard_config
    ):
        """Test getting build environment using keyboard configuration."""
        # Setup mocks
        mock_load_config.return_value = mock_keyboard_config

        # Test getting build environment
        config = {
            "keyboard": "glove80"
        }  # Use glove80 to avoid test_keyboard special case
        env = self.service.get_build_environment(config)

        # Verify the keyboard config was loaded
        mock_load_config.assert_called_once_with("glove80")

        # Verify the environment contains build settings from the keyboard config
        assert "KEYBOARD" in env
        assert env["KEYBOARD"] == "glove80"

        # We should get values from the mock_keyboard_config via the mock_load_config
        assert "DOCKER_IMAGE" in env
        assert env["DOCKER_IMAGE"] == mock_keyboard_config["build"]["docker_image"]
        assert "BRANCH" in env
        assert env["BRANCH"] == mock_keyboard_config["build"]["branch"]
        assert "REPO" in env
        assert env["REPO"] == mock_keyboard_config["build"]["repository"]

    @patch("glovebox.config.keyboard_config.create_profile_from_keyboard_name")
    def test_compile_with_profile(
        self, mock_create_profile, mock_keyboard_config, tmp_path
    ):
        """Test compilation using KeyboardProfile."""
        # Create a mock profile
        mock_build_config = Mock(spec=BuildConfig)
        mock_build_config.docker_image = "test-zmk-build"
        mock_build_config.branch = "test-branch"
        mock_build_config.repository = "test/zmk"
        mock_build_config.method = "docker"

        mock_keyboard_config_obj = Mock(spec=KeyboardConfig)
        mock_keyboard_config_obj.keyboard = "test_keyboard"
        mock_keyboard_config_obj.build = mock_build_config

        mock_profile = Mock(spec=KeyboardProfile)
        mock_profile.keyboard_config = mock_keyboard_config_obj
        mock_profile.keyboard_name = "test_keyboard"
        mock_profile.firmware_version = "test_version"

        # Setup other mocks
        self.mock_docker_adapter.is_available.return_value = True
        self.mock_file_adapter.exists.return_value = True
        self.mock_docker_adapter.run_container.return_value = (
            0,
            ["Build successful"],
            [],
        )
        self.mock_file_adapter.list_files.return_value = [tmp_path / "firmware.uf2"]

        # Test configuration
        build_config = {
            "keymap_path": str(tmp_path / "keymap.keymap"),
            "kconfig_path": str(tmp_path / "config.conf"),
            "output_dir": str(tmp_path),
        }

        # Run compilation with explicit profile
        result = self.service.compile(build_config, mock_profile)

        # Verify results
        assert result.success is True

        # Verify Docker container was run with parameters from profile
        mock_run_args = self.mock_docker_adapter.run_container.call_args
        assert mock_run_args is not None

        # Verify profile wasn't created from keyboard name
        mock_create_profile.assert_not_called()

    @patch("glovebox.services.build_service.create_profile_from_keyboard_name")
    @patch("glovebox.services.build_service.get_available_keyboards")
    def test_compile_with_keyboard_config(
        self, mock_get_available, mock_create_profile, mock_keyboard_config, tmp_path
    ):
        """Test compilation using keyboard name (creates profile internally)."""
        # Setup mocks
        mock_get_available.return_value = ["test_keyboard", "glove80"]
        self.mock_docker_adapter.is_available.return_value = True
        self.mock_file_adapter.exists.return_value = True
        self.mock_docker_adapter.run_container.return_value = (
            0,
            ["Build successful"],
            [],
        )
        self.mock_file_adapter.list_files.return_value = [tmp_path / "firmware.uf2"]

        # Create a mock profile for the helper
        mock_build_config = Mock(spec=BuildConfig)
        mock_build_config.docker_image = "test-zmk-build"
        mock_build_config.branch = "test-branch"
        mock_build_config.repository = "test/zmk"
        mock_build_config.method = "docker"

        mock_keyboard_config_obj = Mock(spec=KeyboardConfig)
        mock_keyboard_config_obj.keyboard = "test_keyboard"
        mock_keyboard_config_obj.build = mock_build_config

        mock_profile = Mock(spec=KeyboardProfile)
        mock_profile.keyboard_config = mock_keyboard_config_obj
        mock_profile.keyboard_name = "test_keyboard"
        mock_profile.firmware_version = "test_version"

        # Setup create_profile_from_keyboard_name to return the mock profile
        mock_create_profile.return_value = mock_profile

        # Test configuration
        build_config = {
            "keyboard": "test_keyboard",
            "keymap_path": str(tmp_path / "keymap.keymap"),
            "kconfig_path": str(tmp_path / "config.conf"),
            "output_dir": str(tmp_path),
        }

        # Run compilation
        result = self.service.compile(build_config)

        # Verify results
        assert result.success is True

        # Verify profile was created from keyboard name
        mock_create_profile.assert_called_once_with("test_keyboard")

        # Verify Docker container was run with parameters from profile
        mock_run_args = self.mock_docker_adapter.run_container.call_args
        assert mock_run_args is not None
        # Verify docker image is from the profile
        _, kwargs = mock_run_args
        assert "image" in kwargs
        assert "test-zmk-build:latest" in kwargs["image"]


@pytest.mark.parametrize(
    "field,value,expected_success",
    [
        ("keyboard", "test_keyboard", True),
        ("keyboard", "nonexistent", False),
        ("keymap_path", "/path/to/keymap.keymap", True),
        ("keymap_path", None, False),
    ],
)
def test_validate_config_parameterized(
    field, value, expected_success, mock_keyboard_config
):
    """Test validation with parameterized fields."""
    service = BuildService()

    # Create a valid base config
    valid_config = {
        "keyboard": "test_keyboard",
        "keymap_path": "/path/to/keymap.keymap",
        "kconfig_path": "/path/to/config.conf",
    }

    # Modify the config based on the test parameter
    if value is None:
        valid_config.pop(field, None)
    else:
        valid_config[field] = value

    # Mock the keyboard config functions
    with patch(
        "glovebox.config.keyboard_config.get_available_keyboards"
    ) as mock_get_keyboards:
        # Make test_keyboard available for all tests
        mock_get_keyboards.return_value = ["test_keyboard", "glove80"]

        # Only for the nonexistent keyboard test, we provide a different list
        if field == "keyboard" and value == "nonexistent":
            mock_get_keyboards.return_value = ["glove80"]

        # Run validation
        result = service.validate(valid_config)

        # Check result
        assert result.success is expected_success
