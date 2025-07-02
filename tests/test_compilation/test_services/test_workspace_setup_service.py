"""Tests for WorkspaceSetupService."""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

pytestmark = pytest.mark.integration

from glovebox.compilation.models import ZmkCompilationConfig
from glovebox.compilation.models.build_matrix import BuildMatrix, BuildTarget
from glovebox.compilation.services.workspace_setup_service import (
    WorkspaceSetupService,
    create_workspace_setup_service,
)
from glovebox.core.cache import create_default_cache
from glovebox.core.metrics.session_metrics import SessionMetrics


class TestWorkspaceSetupService:
    """Test WorkspaceSetupService functionality."""

    @pytest.fixture
    def mock_file_adapter(self):
        """Mock file adapter for testing."""
        adapter = Mock()
        adapter.write_text.return_value = None
        return adapter

    @pytest.fixture
    def mock_session_metrics(self):
        """Mock session metrics for testing."""
        cache_manager = create_default_cache(tag="test")
        return SessionMetrics(cache_manager=cache_manager, session_uuid="test-session")

    @pytest.fixture
    def workspace_service(self, mock_file_adapter, mock_session_metrics):
        """Create WorkspaceSetupService for testing."""
        return create_workspace_setup_service(
            file_adapter=mock_file_adapter,
            session_metrics=mock_session_metrics,
        )

    @pytest.fixture
    def zmk_config(self):
        """Standard ZMK compilation config."""
        return ZmkCompilationConfig(
            method_type="zmk_config",
            repository="zmkfirmware/zmk",
            branch="main",
            image_="zmkfirmware/zmk-build-arm:stable",
            use_cache=True,
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

    def test_service_creation(self, mock_file_adapter, mock_session_metrics):
        """Test workspace setup service creation."""
        service = create_workspace_setup_service(
            file_adapter=mock_file_adapter,
            session_metrics=mock_session_metrics,
        )

        assert service is not None
        assert service.file_adapter is mock_file_adapter
        assert service.session_metrics is mock_session_metrics

    def test_setup_workspace(self, workspace_service, test_files, zmk_config):
        """Test workspace setup creates proper directory structure."""
        keymap_file, config_file = test_files

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir)

            workspace_service.setup_workspace(
                keymap_file, config_file, zmk_config, workspace_path
            )

            # Check config directory exists
            config_dir = workspace_path / "config"
            assert config_dir.exists()

            # Check files were copied
            assert (config_dir / keymap_file.name).exists()
            assert (config_dir / config_file.name).exists()

            # Check build.yaml was created
            assert (workspace_path / "build.yaml").exists()

    def test_get_or_create_workspace_cache_miss(
        self, workspace_service, test_files, zmk_config
    ):
        """Test workspace creation when cache miss occurs."""
        keymap_file, config_file = test_files

        def mock_get_cached_workspace(config):
            return None, False, None

        workspace_path, cache_used, cache_type = (
            workspace_service.get_or_create_workspace(
                keymap_file,
                config_file,
                zmk_config,
                mock_get_cached_workspace,
            )
        )

        assert workspace_path is not None
        assert workspace_path.exists()
        assert cache_used is False
        assert cache_type is None

        # Verify workspace structure
        assert (workspace_path / "config").exists()
        assert (workspace_path / "config" / keymap_file.name).exists()

    def test_get_or_create_workspace_cache_hit(
        self, workspace_service, test_files, zmk_config
    ):
        """Test workspace restoration when cache hit occurs."""
        keymap_file, config_file = test_files

        # Create a fake cached workspace
        with tempfile.TemporaryDirectory() as cached_temp:
            cached_workspace = Path(cached_temp)
            (cached_workspace / "zmk").mkdir()
            (cached_workspace / "zmk" / "app").mkdir()
            (cached_workspace / "modules").mkdir()
            (cached_workspace / "zephyr").mkdir()

            def mock_get_cached_workspace(config):
                return cached_workspace, True, "repo_branch"

            workspace_path, cache_used, cache_type = (
                workspace_service.get_or_create_workspace(
                    keymap_file,
                    config_file,
                    zmk_config,
                    mock_get_cached_workspace,
                )
            )

            assert workspace_path is not None
            assert workspace_path.exists()
            assert cache_used is True
            assert cache_type == "repo_branch"

            # Verify cached content was restored
            assert (workspace_path / "zmk").exists()
            assert (workspace_path / "zmk" / "app").exists()
