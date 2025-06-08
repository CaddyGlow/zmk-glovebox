"""Tests for BuildService with keyboard configuration API."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.config.profile import KeyboardProfile
from glovebox.core.errors import BuildError
from glovebox.firmware.build_service import BuildService, create_build_service
from glovebox.models.build import FirmwareOutputFiles
from glovebox.models.config import BuildConfig, KeyboardConfig
from glovebox.models.options import BuildServiceCompileOpts
from glovebox.models.results import BuildResult
from glovebox.protocols.docker_adapter_protocol import DockerAdapterProtocol
from glovebox.protocols.file_adapter_protocol import FileAdapterProtocol
from glovebox.utils import stream_process


class TestBuildServiceWithKeyboardConfig:
    """Test BuildService with the new keyboard configuration API."""

    def setup_method(self):
        """Set up test environment."""
        self.mock_file_adapter = Mock(spec=FileAdapterProtocol)
        self.mock_docker_adapter = Mock(spec=DockerAdapterProtocol)
        self.mock_output_middleware = Mock(spec=stream_process.OutputMiddleware)
        self.service = BuildService(
            self.mock_docker_adapter,
            self.mock_file_adapter,
            self.mock_output_middleware,
        )

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
        # Add the missing firmware_config attribute to avoid AttributeError
        mock_profile.firmware_config = Mock()
        mock_profile.firmware_config.build_options = None

        # Create build options
        build_opts = BuildServiceCompileOpts(
            keymap_path=Path("/path/to/keymap.keymap"),
            kconfig_path=Path("/path/to/config.conf"),
            output_dir=Path("/path/to/output"),
        )

        # Create a patch for the _find_firmware_files method
        output_files = FirmwareOutputFiles(output_dir=Path("/path/to/output"))

        # Test getting build environment with profile using patch.object
        with patch.object(
            self.service,
            "_find_firmware_files",
            return_value=([Path("/path/to/output/glove80.uf2")], output_files),
        ):
            env = self.service.get_build_environment(build_opts, mock_profile)

            # Verify the environment contains build settings from the profile
            assert "KEYBOARD" in env
            assert env["KEYBOARD"] == "test_keyboard"
            assert "DOCKER_IMAGE" in env
            assert env["DOCKER_IMAGE"] == "test-zmk-build"
            assert "BRANCH" in env
            assert env["BRANCH"] == "test-branch"  # Value from mock_build_config
            assert "REPO" in env
            assert env["REPO"] == "test/zmk"  # Value from mock_build_config

    def test_get_build_environment_from_keyboard_config(self, mock_keyboard_config):
        """Test getting build environment using keyboard configuration."""
        # Setup build options
        build_opts = BuildServiceCompileOpts(
            keymap_path=Path("/path/to/keymap.keymap"),
            kconfig_path=Path("/path/to/config.conf"),
            output_dir=Path("/path/to/output"),
        )

        # Create output files for the _find_firmware_files method
        output_files = FirmwareOutputFiles(output_dir=Path("/path/to/output"))

        # Create patch for the load_keyboard_config function
        with patch(
            "glovebox.firmware.build_service.load_keyboard_config"
        ) as mock_load_config:
            # Create a dictionary version of the mock for the test
            mock_config_dict = {
                "keyboard": mock_keyboard_config.keyboard,
                "build": {
                    "docker_image": mock_keyboard_config.build.docker_image,
                    "branch": mock_keyboard_config.build.branch,
                    "repository": mock_keyboard_config.build.repository,
                },
            }

            # Setup mocks
            mock_load_config.return_value = mock_config_dict

            # Patch the _find_firmware_files method
            with patch.object(
                self.service,
                "_find_firmware_files",
                return_value=([Path("/path/to/output/glove80.uf2")], output_files),
            ):
                # Need to mock is_available for test_keyboard special case
                with patch("sys.modules", {"__name__": ""}):
                    env = self.service.get_build_environment(build_opts)

                # Verify the environment contains settings from the BuildServiceCompileOpts
                assert "KEYBOARD" in env
                assert "DOCKER_IMAGE" in env
                assert "BRANCH" in env
                assert env["BRANCH"] == "main"  # Default from BuildServiceCompileOpts
                assert "REPO" in env
                assert (
                    env["REPO"] == "moergo-sc/zmk"
                )  # Default from BuildServiceCompileOpts

    def test_compile_with_profile(self, mock_keyboard_config, tmp_path):
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
        # Add the missing firmware_config attribute to avoid AttributeError
        mock_profile.firmware_config = Mock()
        mock_profile.firmware_config.build_options = None

        # Setup other mocks using patch.object
        with (
            patch.object(self.mock_docker_adapter, "is_available", return_value=True),
            patch.object(self.mock_file_adapter, "exists", return_value=True),
            patch.object(
                self.mock_docker_adapter,
                "run_container",
                return_value=(0, ["Build successful"], []),
            ),
            patch.object(
                self.mock_file_adapter,
                "list_files",
                return_value=[tmp_path / "firmware.uf2"],
            ),
        ):
            # Create a patch for the _find_firmware_files method
            output_files = FirmwareOutputFiles(
                main_uf2=tmp_path / "firmware.uf2", output_dir=tmp_path
            )

            # Test configuration
            build_opts = BuildServiceCompileOpts(
                keymap_path=tmp_path / "keymap.keymap",
                kconfig_path=tmp_path / "config.conf",
                output_dir=tmp_path,
            )

            # Run compilation with explicit profile using the patch
            with (
                patch.object(
                    self.service,
                    "_find_firmware_files",
                    return_value=([tmp_path / "firmware.uf2"], output_files),
                ),
                patch(
                    "glovebox.config.keyboard_config.create_profile_from_keyboard_name"
                ) as mock_create_profile,
            ):
                result = self.service.compile(build_opts, mock_profile)

                # Verify results
                assert result.success is True
                assert result.output_files is not None
                assert result.output_files.main_uf2 == tmp_path / "firmware.uf2"
                assert result.output_files.output_dir == tmp_path

                # Verify Docker container was run with parameters from profile
                self.mock_docker_adapter.run_container.assert_called_once()

                # Verify profile wasn't created from keyboard name
                mock_create_profile.assert_not_called()
