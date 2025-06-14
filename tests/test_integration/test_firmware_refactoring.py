"""Integration tests for firmware refactoring.

Tests the complete strategy pattern implementation across all components:
- Strategy infrastructure and factory
- Configuration builders
- Firmware executor
- End-to-end integration with CLI components
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.cli.builders.compilation_config import CompilationConfigBuilder
from glovebox.cli.executors.firmware import FirmwareExecutor
from glovebox.cli.strategies.base import CompilationParams
from glovebox.cli.strategies.factory import (
    CompilationStrategyFactory,
    create_strategy_by_name,
    create_strategy_for_profile,
    get_strategy_factory,
    list_available_strategies,
)
from glovebox.config.compile_methods import (
    MoergoCompilationConfig,
    ZmkCompilationConfig,
)
from glovebox.config.profile import KeyboardProfile


def create_test_params(tmp_path, **kwargs) -> CompilationParams:
    """Create test compilation parameters with real files."""
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
        "verbose": None,
        "no_cache": None,
        "docker_uid": None,
        "docker_gid": None,
        "docker_username": None,
        "docker_home": None,
        "docker_container_home": None,
        "no_docker_user_mapping": None,
        "board_targets": None,
        "preserve_workspace": None,
        "force_cleanup": None,
        "clear_cache": None,
    }
    defaults.update(kwargs)
    return CompilationParams(**defaults)


class TestStrategyFactoryIntegration:
    """Test strategy factory integration."""

    def test_factory_initialization_and_strategy_listing(self):
        """Test factory initializes with all expected strategies."""
        strategy_names = list_available_strategies()

        # Should have at least ZMK and Moergo strategies
        assert "zmk_config" in strategy_names
        assert "moergo" in strategy_names
        assert len(strategy_names) >= 2

    def test_strategy_selection_for_zmk_profile(self):
        """Test automatic strategy selection for ZMK profiles."""
        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "planck"

        strategy = create_strategy_for_profile(profile)
        assert strategy.name == "zmk_config"
        assert strategy.supports_profile(profile)

    def test_strategy_selection_for_moergo_profile(self):
        """Test automatic strategy selection for Moergo profiles."""
        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "glove80"

        strategy = create_strategy_for_profile(profile)
        assert strategy.name == "moergo"
        assert strategy.supports_profile(profile)

    def test_manual_strategy_creation(self):
        """Test manual strategy creation by name."""
        zmk_strategy = create_strategy_by_name("zmk_config")
        assert zmk_strategy.name == "zmk_config"

        moergo_strategy = create_strategy_by_name("moergo")
        assert moergo_strategy.name == "moergo"

    def test_strategy_factory_singleton_behavior(self):
        """Test that factory maintains singleton behavior."""
        factory1 = get_strategy_factory()
        factory2 = get_strategy_factory()
        assert factory1 is factory2


class TestCompilationConfigBuilderIntegration:
    """Test compilation config builder integration."""

    def test_config_builder_with_zmk_strategy(self, tmp_path):
        """Test config builder produces correct ZMK configuration."""
        builder = CompilationConfigBuilder()
        params = create_test_params(tmp_path, jobs=4, no_cache=True)

        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "planck"

        config = builder.build(params, profile, "zmk_config")

        assert isinstance(config, ZmkCompilationConfig)
        assert config.jobs == 4
        assert config.cache.enabled is False
        assert config.docker_user.enable_user_mapping is True

    def test_config_builder_with_moergo_strategy(self, tmp_path):
        """Test config builder produces correct Moergo configuration."""
        builder = CompilationConfigBuilder()
        params = create_test_params(tmp_path, branch="v26.01")

        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "glove80"

        config = builder.build(params, profile, "moergo")

        assert isinstance(config, MoergoCompilationConfig)
        assert config.branch == "v26.01"
        assert config.docker_user.enable_user_mapping is False

    def test_config_builder_with_auto_detection(self, tmp_path):
        """Test config builder with automatic strategy detection."""
        builder = CompilationConfigBuilder()
        params = create_test_params(tmp_path)

        # Test ZMK auto-detection
        zmk_profile = Mock(spec=KeyboardProfile)
        zmk_profile.keyboard_name = "planck"

        zmk_config = builder.build(params, zmk_profile)
        assert isinstance(zmk_config, ZmkCompilationConfig)

        # Test Moergo auto-detection
        moergo_profile = Mock(spec=KeyboardProfile)
        moergo_profile.keyboard_name = "glove80"

        moergo_config = builder.build(params, moergo_profile)
        assert isinstance(moergo_config, MoergoCompilationConfig)

    def test_config_builder_docker_overrides(self, tmp_path):
        """Test config builder applies Docker parameter overrides."""
        builder = CompilationConfigBuilder()
        params = create_test_params(
            tmp_path,
            docker_uid=1001,
            docker_gid=1001,
            no_docker_user_mapping=True,
        )

        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "planck"

        config = builder.build(params, profile, "zmk_config")

        assert config.docker_user.manual_uid == 1001
        assert config.docker_user.manual_gid == 1001
        assert config.docker_user.enable_user_mapping is False


class TestFirmwareExecutorIntegration:
    """Test firmware executor integration."""

    @patch("glovebox.cli.executors.firmware.create_compilation_service")
    def test_executor_with_explicit_strategy(self, mock_create_service, tmp_path):
        """Test executor with explicit strategy specification."""
        # Setup mocks
        mock_service = Mock()
        mock_result = Mock(success=True, messages=["Build complete"])
        mock_service.compile.return_value = mock_result
        mock_create_service.return_value = mock_service

        # Create executor and test data
        executor = FirmwareExecutor()
        params = create_test_params(tmp_path, jobs=2)
        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "planck"

        # Execute with explicit strategy
        result = executor.compile(params, profile, "zmk_config")

        # Verify service creation and compilation
        assert result == mock_result
        mock_create_service.assert_called_once_with("zmk_config")
        mock_service.compile.assert_called_once()

        # Verify call arguments
        call_args = mock_service.compile.call_args
        assert call_args.kwargs["keymap_file"] == params.keymap_file
        assert call_args.kwargs["config_file"] == params.kconfig_file
        assert call_args.kwargs["output_dir"] == params.output_dir
        assert call_args.kwargs["keyboard_profile"] == profile

    @patch("glovebox.cli.executors.firmware.create_compilation_service")
    def test_executor_with_auto_strategy_detection(self, mock_create_service, tmp_path):
        """Test executor with automatic strategy detection."""
        # Setup mocks
        mock_service = Mock()
        mock_result = Mock(success=True)
        mock_service.compile.return_value = mock_result
        mock_create_service.return_value = mock_service

        # Create executor and test data
        executor = FirmwareExecutor()
        params = create_test_params(tmp_path)
        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "glove80"  # Should trigger Moergo strategy

        # Execute without explicit strategy
        result = executor.compile(params, profile)

        # Should auto-detect Moergo strategy
        assert result == mock_result
        mock_create_service.assert_called_once_with("moergo")

    @patch("glovebox.cli.executors.firmware.create_compilation_service")
    def test_executor_cache_clearing_integration(self, mock_create_service, tmp_path):
        """Test executor handles cache clearing parameter."""
        # Setup mocks
        mock_service = Mock()
        mock_result = Mock(success=True)
        mock_service.compile.return_value = mock_result
        mock_create_service.return_value = mock_service

        # Create executor and test data
        executor = FirmwareExecutor()
        params = create_test_params(tmp_path, clear_cache=True)
        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "planck"

        # Execute with cache clearing
        with patch("glovebox.cli.executors.firmware.logger") as mock_logger:
            result = executor.compile(params, profile, "zmk_config")

        # Verify cache clearing was noted
        mock_logger.info.assert_any_call(
            "Cache clearing requested but not yet implemented"
        )
        assert result == mock_result


class TestEndToEndIntegration:
    """Test complete end-to-end integration."""

    @patch("glovebox.cli.executors.firmware.create_compilation_service")
    def test_complete_zmk_workflow(self, mock_create_service, tmp_path):
        """Test complete ZMK compilation workflow."""
        # Setup mocks
        mock_service = Mock()
        mock_result = Mock(success=True, messages=["ZMK build successful"])
        mock_service.compile.return_value = mock_result
        mock_create_service.return_value = mock_service

        # Create components
        executor = FirmwareExecutor()
        params = create_test_params(
            tmp_path,
            jobs=4,
            verbose=True,
            docker_uid=1000,
            docker_gid=1000,
        )
        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "planck"

        # Execute complete workflow
        result = executor.compile(params, profile, "zmk_config")

        # Verify successful execution
        assert result.success is True
        assert "ZMK build successful" in result.messages

        # Verify configuration was built correctly
        call_args = mock_service.compile.call_args
        config = call_args.kwargs["config"]
        assert isinstance(config, ZmkCompilationConfig)
        assert config.jobs == 4
        assert config.docker_user.manual_uid == 1000

    @patch("glovebox.cli.executors.firmware.create_compilation_service")
    def test_complete_moergo_workflow(self, mock_create_service, tmp_path):
        """Test complete Moergo compilation workflow."""
        # Setup mocks
        mock_service = Mock()
        mock_result = Mock(success=True, messages=["Moergo build successful"])
        mock_service.compile.return_value = mock_result
        mock_create_service.return_value = mock_service

        # Create components
        executor = FirmwareExecutor()
        params = create_test_params(
            tmp_path,
            branch="v25.05",
            no_docker_user_mapping=True,
        )
        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "glove80"

        # Execute complete workflow
        result = executor.compile(params, profile, "moergo")

        # Verify successful execution
        assert result.success is True
        assert "Moergo build successful" in result.messages

        # Verify configuration was built correctly
        call_args = mock_service.compile.call_args
        config = call_args.kwargs["config"]
        assert isinstance(config, MoergoCompilationConfig)
        assert config.branch == "v25.05"
        assert config.docker_user.enable_user_mapping is False

    @patch("glovebox.cli.executors.firmware.create_compilation_service")
    def test_strategy_fallback_behavior(self, mock_create_service, tmp_path):
        """Test strategy fallback behavior for unknown keyboards."""
        # Setup mocks
        mock_service = Mock()
        mock_result = Mock(success=True)
        mock_service.compile.return_value = mock_result
        mock_create_service.return_value = mock_service

        # Create components
        executor = FirmwareExecutor()
        params = create_test_params(tmp_path)
        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "unknown_keyboard"  # Not recognized by any strategy

        # Execute - should fall back to ZMK strategy
        result = executor.compile(params, profile)

        # Should use ZMK as fallback
        mock_create_service.assert_called_once_with("zmk_config")
        assert result == mock_result


class TestErrorHandlingIntegration:
    """Test error handling across integrated components."""

    @patch("glovebox.cli.executors.firmware.create_compilation_service")
    def test_compilation_failure_handling(self, mock_create_service, tmp_path):
        """Test handling of compilation failures."""
        # Setup mocks for failure
        mock_service = Mock()
        mock_result = Mock(
            success=False, errors=["Build failed", "Missing dependencies"]
        )
        mock_service.compile.return_value = mock_result
        mock_create_service.return_value = mock_service

        # Create components
        executor = FirmwareExecutor()
        params = create_test_params(tmp_path)
        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "planck"

        # Execute and verify failure is returned (not raised)
        result = executor.compile(params, profile, "zmk_config")

        assert result.success is False
        assert "Build failed" in result.errors
        assert "Missing dependencies" in result.errors

    def test_invalid_strategy_name_handling(self, tmp_path):
        """Test handling of invalid strategy names."""
        builder = CompilationConfigBuilder()
        params = create_test_params(tmp_path)
        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "test"

        # Should raise exception for invalid strategy name
        from glovebox.cli.strategies.factory import StrategyNotFoundError

        with pytest.raises(StrategyNotFoundError):
            builder.build(params, profile, "invalid_strategy")

    def test_missing_file_validation(self, tmp_path):
        """Test validation of missing input files."""
        builder = CompilationConfigBuilder()

        # Create params with non-existent files
        params = CompilationParams(
            keymap_file=Path("nonexistent.keymap"),
            kconfig_file=Path("nonexistent.conf"),
            output_dir=tmp_path / "build",
            branch=None,
            repo=None,
            jobs=None,
            verbose=False,
            no_cache=False,
            docker_uid=None,
            docker_gid=None,
            docker_username=None,
            docker_home=None,
            docker_container_home=None,
            no_docker_user_mapping=False,
            board_targets=None,
            preserve_workspace=False,
            force_cleanup=False,
            clear_cache=False,
        )

        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "planck"

        # Should raise exception for missing files
        with pytest.raises(ValueError):
            builder.build(params, profile, "zmk_config")


class TestComponentInteroperability:
    """Test interoperability between components."""

    def test_strategy_config_builder_compatibility(self, tmp_path):
        """Test that strategies produce configs compatible with builder."""
        from glovebox.cli.strategies.moergo import create_moergo_strategy
        from glovebox.cli.strategies.zmk_config import create_zmk_config_strategy

        params = create_test_params(tmp_path)
        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "test"

        # Test ZMK strategy compatibility
        zmk_strategy = create_zmk_config_strategy()
        zmk_config = zmk_strategy.build_config(params, profile)
        assert hasattr(zmk_config, "docker_user")
        assert hasattr(zmk_config, "jobs")

        # Test Moergo strategy compatibility
        moergo_strategy = create_moergo_strategy()
        moergo_config = moergo_strategy.build_config(params, profile)
        assert hasattr(moergo_config, "docker_user")
        assert hasattr(moergo_config, "branch")

    def test_executor_builder_integration(self, tmp_path):
        """Test that executor properly integrates with config builder."""
        executor = FirmwareExecutor()

        # Verify executor has config builder
        assert hasattr(executor, "config_builder")
        assert hasattr(executor.config_builder, "build")

        # Test that executor can build configs
        params = create_test_params(tmp_path)
        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "planck"

        config = executor.config_builder.build(params, profile, "zmk_config")
        assert isinstance(config, ZmkCompilationConfig)


class TestPerformanceIntegration:
    """Test performance characteristics of integrated components."""

    def test_strategy_factory_performance(self):
        """Test that strategy factory operations are efficient."""
        import time

        # Test factory initialization time
        start_time = time.time()
        factory = get_strategy_factory()
        init_time = time.time() - start_time

        # Should initialize quickly (< 100ms)
        assert init_time < 0.1

        # Test strategy retrieval time
        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "planck"

        start_time = time.time()
        strategy = factory.get_strategy_for_profile(profile)
        retrieval_time = time.time() - start_time

        # Should retrieve quickly (< 10ms)
        assert retrieval_time < 0.01
        assert strategy.name == "zmk_config"

    def test_config_building_performance(self, tmp_path):
        """Test that config building is efficient."""
        import time

        builder = CompilationConfigBuilder()
        params = create_test_params(tmp_path)
        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "planck"

        # Test config building time
        start_time = time.time()
        config = builder.build(params, profile, "zmk_config")
        build_time = time.time() - start_time

        # Should build quickly (< 50ms)
        assert build_time < 0.05
        assert isinstance(config, ZmkCompilationConfig)
