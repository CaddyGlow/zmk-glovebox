"""Tests for ZmkWestService integration with new cache services."""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from glovebox.compilation.models import ZmkCompilationConfig
from glovebox.compilation.models.build_matrix import BuildMatrix, BuildTarget
from glovebox.compilation.services.zmk_west_service import create_zmk_west_service
from glovebox.config.profile import KeyboardProfile
from glovebox.core.cache import create_default_cache
from glovebox.core.metrics.session_metrics import SessionMetrics
from glovebox.firmware.models import BuildResult


class TestZmkWestServiceIntegration:
    """Integration tests for ZmkWestService with new cache services."""

    @pytest.fixture
    def mock_docker_adapter(self):
        """Mock Docker adapter for testing."""
        adapter = Mock()
        adapter.image_exists.return_value = True
        adapter.run_container.return_value = (0, [], [])  # Success
        return adapter

    @pytest.fixture
    def test_files(self, tmp_path):
        """Create test keymap and config files."""
        keymap_file = tmp_path / "test.keymap"
        keymap_file.write_text("""
            #include <behaviors.dtsi>
            #include <dt-bindings/zmk/keys.h>

            / {
                keymap {
                    compatible = "zmk,keymap";
                    default_layer {
                        bindings = <&kp A &kp B>;
                    };
                };
            };
        """)

        config_file = tmp_path / "test.conf"
        config_file.write_text('CONFIG_ZMK_KEYBOARD_NAME="test"\n')

        return keymap_file, config_file

    @pytest.fixture
    def zmk_config(self):
        """Standard ZMK compilation config for testing."""
        return ZmkCompilationConfig(
            method_type="zmk_config",
            repository="zmkfirmware/zmk",
            branch="main",
            image="zmkfirmware/zmk-build-arm:stable",
            use_cache=True,
            build_matrix=BuildMatrix(
                include=[BuildTarget(board="nice_nano_v2", artifact_name="test_board")]
            ),
        )

    @pytest.fixture
    def keyboard_profile(self):
        """Mock keyboard profile for testing."""
        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "test_keyboard"
        profile.firmware_version = "v25.05"
        return profile

    def test_service_creation_with_cache_services(
        self, mock_docker_adapter, isolated_config, mock_file_adapter
    ):
        """Test that ZmkWestService can be created with new cache services."""
        cache_manager = create_default_cache(tag="test")
        session_metrics = SessionMetrics(
            cache_manager=cache_manager, session_uuid="test-session"
        )

        service = create_zmk_west_service(
            docker_adapter=mock_docker_adapter,
            user_config=isolated_config,
            file_adapter=mock_file_adapter,
            cache_manager=cache_manager,
            session_metrics=session_metrics,
        )

        assert service is not None
        assert service.cache_service is not None
        assert service.cache_service.workspace_cache_service is not None
        assert service.cache_service.build_cache_service is not None
        assert service.cache_manager is cache_manager

    def test_cache_disabled_compilation(
        self,
        mock_docker_adapter,
        isolated_config,
        test_files,
        keyboard_profile,
        mock_file_adapter,
    ):
        """Test compilation with caching disabled."""
        keymap_file, config_file = test_files

        config = ZmkCompilationConfig(
            method_type="zmk_config",
            repository="zmkfirmware/zmk",
            branch="main",
            image="zmkfirmware/zmk-build-arm:stable",
            use_cache=False,  # Caching disabled
            build_matrix=BuildMatrix(
                include=[BuildTarget(board="nice_nano_v2", artifact_name="test_board")]
            ),
        )

        service = create_zmk_west_service(
            docker_adapter=mock_docker_adapter,
            user_config=isolated_config,
            file_adapter=mock_file_adapter,
            cache_manager=create_default_cache(tag="test"),
            session_metrics=SessionMetrics(
                cache_manager=create_default_cache(tag="test"),
                session_uuid="test-session",
            ),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            # Should not use cache when disabled
            cached_workspace, cache_used, cache_type = (
                service.cache_service.get_cached_workspace(config)
            )
            assert cached_workspace is None
            assert cache_used is False

            # Compilation should still work
            result = service.compile(
                keymap_file, config_file, output_dir, config, keyboard_profile
            )
            assert isinstance(result, BuildResult)

    def test_workspace_cache_integration(
        self, mock_docker_adapter, isolated_config, zmk_config, mock_file_adapter
    ):
        """Test workspace cache integration with new cache services."""
        service = create_zmk_west_service(
            docker_adapter=mock_docker_adapter,
            user_config=isolated_config,
            file_adapter=mock_file_adapter,
            cache_manager=create_default_cache(tag="test"),
            session_metrics=SessionMetrics(
                cache_manager=create_default_cache(tag="test"),
                session_uuid="test-session",
            ),
        )

        # First call should be cache miss
        cached_workspace, cache_used, cache_type = (
            service.cache_service.get_cached_workspace(zmk_config)
        )
        assert cached_workspace is None
        assert cache_used is False

        # Create a mock workspace and cache it
        with tempfile.TemporaryDirectory() as temp_workspace:
            workspace_path = Path(temp_workspace)

            # Create zmk directory structure
            zmk_dir = workspace_path / "zmk"
            zmk_dir.mkdir()
            (zmk_dir / "app").mkdir()

            modules_dir = workspace_path / "modules"
            modules_dir.mkdir()

            zephyr_dir = workspace_path / "zephyr"
            zephyr_dir.mkdir()

            # Cache the workspace
            service.cache_service.cache_workspace(workspace_path, zmk_config)

            # Second call should be cache hit
            cached_workspace, cache_used, cache_type = (
                service.cache_service.get_cached_workspace(zmk_config)
            )
            assert cached_workspace is not None
            assert cache_used is True
            assert cached_workspace.exists()
            assert (cached_workspace / "zmk").exists()

    def test_build_cache_integration(
        self,
        mock_docker_adapter,
        isolated_config,
        test_files,
        zmk_config,
        mock_file_adapter,
    ):
        """Test build cache integration with new cache services."""
        keymap_file, config_file = test_files

        service = create_zmk_west_service(
            docker_adapter=mock_docker_adapter,
            user_config=isolated_config,
            file_adapter=mock_file_adapter,
            cache_manager=create_default_cache(tag="test"),
            session_metrics=SessionMetrics(
                cache_manager=create_default_cache(tag="test"),
                session_uuid="test-session",
            ),
        )

        # First call should be cache miss
        cached_build = service.cache_service.get_cached_build_result(
            keymap_file, config_file, zmk_config
        )
        assert cached_build is None

        # Create a mock build directory and cache it
        with tempfile.TemporaryDirectory() as temp_build:
            build_path = Path(temp_build)

            # Create build artifacts
            (build_path / "zmk.uf2").write_bytes(b"fake firmware")
            (build_path / "zmk.hex").write_text("fake hex")

            # Cache the build result
            service.cache_service.cache_build_result(
                keymap_file, config_file, zmk_config, build_path
            )

            # Second call should be cache hit
            cached_build = service.cache_service.get_cached_build_result(
                keymap_file, config_file, zmk_config
            )
            assert cached_build is not None
            assert cached_build.exists()
            assert (cached_build / "zmk.uf2").exists()
