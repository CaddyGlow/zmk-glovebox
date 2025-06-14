"""Tests for firmware executor."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.cli.executors.firmware import FirmwareExecutor
from glovebox.cli.strategies.base import CompilationParams
from glovebox.config.profile import KeyboardProfile


def create_test_params(tmp_path, **kwargs) -> CompilationParams:
    """Create test compilation parameters."""
    keymap_file = tmp_path / "test.keymap"
    kconfig_file = tmp_path / "test.conf"
    output_dir = tmp_path / "build"

    keymap_file.touch()
    kconfig_file.touch()
    output_dir.mkdir(parents=True, exist_ok=True)

    defaults = {
        "keymap_file": keymap_file,
        "kconfig_file": kconfig_file,
        "output_dir": output_dir,
        "branch": None,
        "repo": None,
        "jobs": None,
        "verbose": False,
        "no_cache": False,
        "docker_uid": None,
        "docker_gid": None,
        "docker_username": None,
        "docker_home": None,
        "docker_container_home": None,
        "no_docker_user_mapping": False,
        "board_targets": None,
        "preserve_workspace": False,
        "force_cleanup": False,
        "clear_cache": False,
    }
    defaults.update(kwargs)
    return CompilationParams(**defaults)


class TestFirmwareExecutor:
    """Test firmware executor."""

    @patch("glovebox.cli.executors.firmware.create_compilation_service")
    def test_compile_success(self, mock_create_service, tmp_path):
        """Test successful compilation."""
        # Setup mocks
        mock_service = Mock()
        mock_result = Mock(success=True, messages=["Build complete"])
        mock_service.compile.return_value = mock_result
        mock_create_service.return_value = mock_service

        # Create executor
        executor = FirmwareExecutor()

        # Create test data
        params = create_test_params(tmp_path)
        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "test"

        # Execute
        result = executor.compile(params, profile, "zmk_config")

        # Verify
        assert result == mock_result
        mock_create_service.assert_called_once_with("zmk_config")
        mock_service.compile.assert_called_once()

        # Check call arguments
        call_args = mock_service.compile.call_args
        assert call_args.kwargs["keymap_file"] == params.keymap_file
        assert call_args.kwargs["config_file"] == params.kconfig_file
        assert call_args.kwargs["output_dir"] == params.output_dir
        assert call_args.kwargs["keyboard_profile"] == profile

    @patch("glovebox.cli.executors.firmware.create_compilation_service")
    def test_compile_with_auto_strategy_detection(self, mock_create_service, tmp_path):
        """Test compilation with automatic strategy detection."""
        # Setup mocks
        mock_service = Mock()
        mock_result = Mock(success=True)
        mock_service.compile.return_value = mock_result
        mock_create_service.return_value = mock_service

        # Create executor
        executor = FirmwareExecutor()

        # Create test data
        params = create_test_params(tmp_path)
        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "planck"  # Should trigger ZMK strategy

        # Execute without explicit strategy
        result = executor.compile(params, profile)

        # Verify
        assert result == mock_result
        mock_service.compile.assert_called_once()

    @patch("glovebox.cli.executors.firmware.create_compilation_service")
    def test_compile_with_cache_clear(self, mock_create_service, tmp_path):
        """Test compilation with cache clearing."""
        # Setup mocks
        mock_service = Mock()
        mock_result = Mock(success=True)
        mock_service.compile.return_value = mock_result
        mock_create_service.return_value = mock_service

        # Create executor
        executor = FirmwareExecutor()

        # Create test data with clear_cache
        params = create_test_params(tmp_path, clear_cache=True)
        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "test"

        # Execute
        with patch("glovebox.cli.executors.firmware.logger") as mock_logger:
            result = executor.compile(params, profile, "zmk_config")

        # Verify cache clear was logged
        mock_logger.info.assert_any_call(
            "Cache clearing requested but not yet implemented"
        )
        assert result == mock_result

    @patch("glovebox.cli.executors.firmware.create_compilation_service")
    def test_compile_with_moergo_strategy(self, mock_create_service, tmp_path):
        """Test compilation with Moergo strategy."""
        # Setup mocks
        mock_service = Mock()
        mock_result = Mock(success=True, messages=["Moergo build complete"])
        mock_service.compile.return_value = mock_result
        mock_create_service.return_value = mock_service

        # Create executor
        executor = FirmwareExecutor()

        # Create test data
        params = create_test_params(tmp_path, branch="v25.05")
        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "glove80"

        # Execute
        result = executor.compile(params, profile, "moergo")

        # Verify
        assert result == mock_result
        mock_service.compile.assert_called_once()

        # Verify config was built correctly
        call_args = mock_service.compile.call_args
        config = call_args.kwargs["config"]
        # Config should be MoergoCompilationConfig with proper settings
        assert hasattr(config, "branch")

    @patch("glovebox.cli.executors.firmware.create_compilation_service")
    def test_compile_with_docker_overrides(self, mock_create_service, tmp_path):
        """Test compilation with Docker parameter overrides."""
        # Setup mocks
        mock_service = Mock()
        mock_result = Mock(success=True)
        mock_service.compile.return_value = mock_result
        mock_create_service.return_value = mock_service

        # Create executor
        executor = FirmwareExecutor()

        # Create test data with Docker overrides
        params = create_test_params(
            tmp_path,
            docker_uid=1000,
            docker_gid=1000,
            no_docker_user_mapping=True,
        )
        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "test"

        # Execute
        result = executor.compile(params, profile, "zmk_config")

        # Verify
        assert result == mock_result

        # Verify Docker settings were applied to config
        call_args = mock_service.compile.call_args
        config = call_args.kwargs["config"]
        assert config.docker_user.manual_uid == 1000
        assert config.docker_user.manual_gid == 1000
        assert config.docker_user.enable_user_mapping is False

    @patch("glovebox.cli.executors.firmware.create_compilation_service")
    def test_compile_failure_handling(self, mock_create_service, tmp_path):
        """Test handling of compilation failures."""
        # Setup mocks
        mock_service = Mock()
        mock_result = Mock(success=False, errors=["Build failed"])
        mock_service.compile.return_value = mock_result
        mock_create_service.return_value = mock_service

        # Create executor
        executor = FirmwareExecutor()

        # Create test data
        params = create_test_params(tmp_path)
        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "test"

        # Execute
        result = executor.compile(params, profile, "zmk_config")

        # Verify failure is returned (not raised)
        assert result == mock_result
        assert result.success is False

    def test_executor_initialization(self):
        """Test executor initialization."""
        executor = FirmwareExecutor()

        assert executor.config_builder is not None
        assert hasattr(executor.config_builder, "build")
