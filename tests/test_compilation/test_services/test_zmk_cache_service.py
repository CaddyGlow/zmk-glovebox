"""Tests for ZmkCacheService."""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from glovebox.compilation.models import ZmkCompilationConfig
from glovebox.compilation.models.build_matrix import BuildMatrix, BuildTarget
from glovebox.compilation.services.zmk_cache_service import (
    ZmkCacheService,
    create_zmk_cache_service,
)
from glovebox.core.cache import create_default_cache
from glovebox.core.metrics.session_metrics import SessionMetrics


class TestZmkCacheService:
    """Test ZmkCacheService functionality."""

    @pytest.fixture
    def mock_user_config(self):
        """Mock user config for testing."""
        config = Mock()
        config.cache_strategy = "shared"
        return config

    @pytest.fixture
    def cache_manager(self):
        """Create cache manager for testing."""
        return create_default_cache(tag="test")

    @pytest.fixture
    def mock_session_metrics(self, cache_manager):
        """Mock session metrics for testing."""
        return SessionMetrics(cache_manager=cache_manager, session_uuid="test-session")

    @pytest.fixture
    def cache_service(self, mock_user_config, cache_manager, mock_session_metrics):
        """Create ZmkCacheService for testing."""
        return create_zmk_cache_service(
            user_config=mock_user_config,
            cache_manager=cache_manager,
            session_metrics=mock_session_metrics,
        )

    @pytest.fixture
    def zmk_config(self):
        """Standard ZMK compilation config."""
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
    def zmk_config_no_cache(self):
        """ZMK config with caching disabled."""
        return ZmkCompilationConfig(
            method_type="zmk_config",
            repository="zmkfirmware/zmk",
            branch="main",
            image="zmkfirmware/zmk-build-arm:stable",
            use_cache=False,
            build_matrix=BuildMatrix(
                include=[BuildTarget(board="nice_nano_v2", artifact_name="test_board")]
            ),
        )

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

    def test_service_creation(
        self, mock_user_config, cache_manager, mock_session_metrics
    ):
        """Test cache service creation."""
        service = create_zmk_cache_service(
            user_config=mock_user_config,
            cache_manager=cache_manager,
            session_metrics=mock_session_metrics,
        )

        assert service is not None
        assert service.workspace_cache_service is not None
        assert service.build_cache_service is not None

    def test_get_cached_workspace_cache_disabled(
        self, cache_service, zmk_config_no_cache
    ):
        """Test workspace cache when caching is disabled."""
        workspace_path, cache_used, cache_type = cache_service.get_cached_workspace(
            zmk_config_no_cache
        )

        assert workspace_path is None
        assert cache_used is False
        assert cache_type is None

    def test_get_cached_workspace_cache_miss(self, cache_service, zmk_config):
        """Test workspace cache miss."""
        workspace_path, cache_used, cache_type = cache_service.get_cached_workspace(
            zmk_config
        )

        assert workspace_path is None
        assert cache_used is False
        assert cache_type is None

    def test_workspace_cache_roundtrip(self, cache_service, zmk_config):
        """Test caching and retrieving workspace."""
        # Create a test workspace
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir)

            # Create ZMK directory structure
            (workspace_path / "zmk").mkdir()
            (workspace_path / "zmk" / "app").mkdir()
            (workspace_path / "modules").mkdir()
            (workspace_path / "zephyr").mkdir()

            # Cache the workspace
            cache_service.cache_workspace(workspace_path, zmk_config)

            # Retrieve from cache
            cached_workspace, cache_used, cache_type = (
                cache_service.get_cached_workspace(zmk_config)
            )

            assert cached_workspace is not None
            assert cache_used is True
            assert cache_type in ["repo_branch", "repo_only"]
            assert cached_workspace.exists()
            assert (cached_workspace / "zmk").exists()

    def test_get_cached_build_result_cache_disabled(
        self, cache_service, test_files, zmk_config_no_cache
    ):
        """Test build cache when caching is disabled."""
        keymap_file, config_file = test_files

        cached_build = cache_service.get_cached_build_result(
            keymap_file, config_file, zmk_config_no_cache
        )

        assert cached_build is None

    def test_get_cached_build_result_cache_miss(
        self, cache_service, test_files, zmk_config
    ):
        """Test build cache miss."""
        keymap_file, config_file = test_files

        cached_build = cache_service.get_cached_build_result(
            keymap_file, config_file, zmk_config
        )

        assert cached_build is None

    def test_build_cache_roundtrip(self, cache_service, test_files, zmk_config):
        """Test caching and retrieving build result."""
        keymap_file, config_file = test_files

        # Create a test build directory
        with tempfile.TemporaryDirectory() as temp_dir:
            build_path = Path(temp_dir)

            # Create build artifacts
            (build_path / "zmk.uf2").write_bytes(b"fake firmware")
            (build_path / "zmk.hex").write_text("fake hex content")

            # Cache the build result
            cache_service.cache_build_result(
                keymap_file, config_file, zmk_config, build_path
            )

            # Retrieve from cache
            cached_build = cache_service.get_cached_build_result(
                keymap_file, config_file, zmk_config
            )

            assert cached_build is not None
            assert cached_build.exists()
            assert (cached_build / "zmk.uf2").exists()
            assert (cached_build / "zmk.hex").exists()
