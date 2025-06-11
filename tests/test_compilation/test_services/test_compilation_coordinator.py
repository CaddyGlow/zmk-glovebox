"""Test Compilation Coordinator service."""

import tempfile
from pathlib import Path
from typing import cast
from unittest.mock import Mock

import pytest

from glovebox.compilation.protocols.compilation_protocols import (
    CompilationServiceProtocol,
)
from glovebox.compilation.services.compilation_coordinator import (
    CompilationCoordinator,
    create_compilation_coordinator,
)
from glovebox.config.compile_methods import (
    GenericDockerCompileConfig,
    WestWorkspaceConfig,
    ZmkConfigRepoConfig,
)
from glovebox.firmware.models import BuildResult


class TestCompilationCoordinator:
    """Test compilation coordinator functionality."""

    def setup_method(self):
        """Set up test instance."""
        # Create mock compilation services
        self.mock_zmk_config_service = Mock()
        self.mock_west_service = Mock()
        self.mock_cmake_service = Mock()

        compilation_services = cast(
            dict[str, CompilationServiceProtocol],
            {
                "zmk_config": self.mock_zmk_config_service,
                "west": self.mock_west_service,
                "cmake": self.mock_cmake_service,
            },
        )

        # Mock Docker adapter
        self.mock_docker_adapter = Mock()
        self.mock_docker_adapter.is_available.return_value = True

        self.coordinator = CompilationCoordinator(
            compilation_services=compilation_services,
            docker_adapter=self.mock_docker_adapter,
        )

    def test_initialization(self):
        """Test coordinator initialization."""
        coordinator = self.coordinator
        assert coordinator.service_name == "compilation_coordinator"
        assert coordinator.service_version == "1.0.0"
        assert len(coordinator.compilation_services) == 3
        assert "zmk_config" in coordinator.compilation_services
        assert "west" in coordinator.compilation_services
        assert "cmake" in coordinator.compilation_services

    def test_create_compilation_coordinator(self):
        """Test factory function creates coordinator."""
        coordinator = create_compilation_coordinator()
        assert isinstance(coordinator, CompilationCoordinator)

    def test_compile_zmk_config_strategy(self):
        """Test compilation using ZMK config strategy."""
        with tempfile.TemporaryDirectory() as temp_dir:
            keymap_file = Path(temp_dir) / "keymap.keymap"
            config_file = Path(temp_dir) / "config.conf"
            output_dir = Path(temp_dir) / "output"

            keymap_file.touch()
            config_file.touch()
            output_dir.mkdir()

            # Mock configuration for ZMK config strategy
            config = Mock(spec=GenericDockerCompileConfig)
            config.zmk_config_repo = Mock(spec=ZmkConfigRepoConfig)
            config.west_workspace = None
            config.build_strategy = "zmk_config"

            # Mock service availability and validation
            self.mock_zmk_config_service.check_available.return_value = True
            self.mock_zmk_config_service.validate_config.return_value = True

            # Mock successful compilation
            expected_result = BuildResult(success=True)
            self.mock_zmk_config_service.compile.return_value = expected_result

            result = self.coordinator.compile(
                keymap_file, config_file, output_dir, config
            )

            assert result.success is True
            self.mock_zmk_config_service.compile.assert_called_once_with(
                keymap_file, config_file, output_dir, config, keyboard_profile=None
            )

    def test_compile_west_strategy(self):
        """Test compilation using west strategy."""
        with tempfile.TemporaryDirectory() as temp_dir:
            keymap_file = Path(temp_dir) / "keymap.keymap"
            config_file = Path(temp_dir) / "config.conf"
            output_dir = Path(temp_dir) / "output"

            keymap_file.touch()
            config_file.touch()
            output_dir.mkdir()

            # Mock configuration for west strategy
            config = Mock(spec=GenericDockerCompileConfig)
            config.zmk_config_repo = None
            config.west_workspace = Mock(spec=WestWorkspaceConfig)
            config.build_strategy = "west"

            # Mock service availability and validation
            self.mock_west_service.check_available.return_value = True
            self.mock_west_service.validate_config.return_value = True

            # Mock successful compilation
            expected_result = BuildResult(success=True)
            self.mock_west_service.compile.return_value = expected_result

            result = self.coordinator.compile(
                keymap_file, config_file, output_dir, config
            )

            assert result.success is True
            self.mock_west_service.compile.assert_called_once_with(
                keymap_file, config_file, output_dir, config, keyboard_profile=None
            )

    def test_compile_cmake_strategy_fallback(self):
        """Test compilation using cmake strategy as fallback."""
        with tempfile.TemporaryDirectory() as temp_dir:
            keymap_file = Path(temp_dir) / "keymap.keymap"
            config_file = Path(temp_dir) / "config.conf"
            output_dir = Path(temp_dir) / "output"

            keymap_file.touch()
            config_file.touch()
            output_dir.mkdir()

            # Mock configuration with no specific strategy indicators
            config = Mock(spec=GenericDockerCompileConfig)
            config.zmk_config_repo = None
            config.west_workspace = None
            config.build_strategy = "cmake"

            # Mock service availability and validation
            self.mock_cmake_service.check_available.return_value = True
            self.mock_cmake_service.validate_config.return_value = True

            # Mock successful compilation
            expected_result = BuildResult(success=True)
            self.mock_cmake_service.compile.return_value = expected_result

            result = self.coordinator.compile(
                keymap_file, config_file, output_dir, config
            )

            assert result.success is True
            self.mock_cmake_service.compile.assert_called_once_with(
                keymap_file, config_file, output_dir, config, keyboard_profile=None
            )

    def test_compile_no_suitable_strategy(self):
        """Test compilation when no suitable strategy is found."""
        with tempfile.TemporaryDirectory() as temp_dir:
            keymap_file = Path(temp_dir) / "keymap.keymap"
            config_file = Path(temp_dir) / "config.conf"
            output_dir = Path(temp_dir) / "output"

            config = Mock(spec=GenericDockerCompileConfig)
            config.zmk_config_repo = None
            config.west_workspace = None
            config.build_strategy = "cmake"

            # Mock all services as unavailable
            self.mock_zmk_config_service.check_available.return_value = False
            self.mock_west_service.check_available.return_value = False
            self.mock_cmake_service.check_available.return_value = False

            result = self.coordinator.compile(
                keymap_file, config_file, output_dir, config
            )

            assert result.success is False
            assert any(
                "No suitable compilation strategy found" in error
                for error in result.errors
            )

    def test_compile_service_not_available(self):
        """Test compilation when selected service is not in services dict."""
        coordinator = CompilationCoordinator(compilation_services={})

        with tempfile.TemporaryDirectory() as temp_dir:
            keymap_file = Path(temp_dir) / "keymap.keymap"
            config_file = Path(temp_dir) / "config.conf"
            output_dir = Path(temp_dir) / "output"

            config = Mock(spec=GenericDockerCompileConfig)
            config.zmk_config_repo = Mock(spec=ZmkConfigRepoConfig)
            config.west_workspace = None
            config.build_strategy = "zmk_config"

            result = coordinator.compile(keymap_file, config_file, output_dir, config)

            assert result.success is False
            assert any(
                "No suitable compilation strategy found" in error
                for error in result.errors
            )

    def test_validate_config_valid(self):
        """Test configuration validation with valid config."""
        config = Mock(spec=GenericDockerCompileConfig)
        config.zmk_config_repo = Mock(spec=ZmkConfigRepoConfig)
        config.west_workspace = None
        config.build_strategy = "zmk_config"

        # Mock service availability and validation
        self.mock_zmk_config_service.check_available.return_value = True
        self.mock_zmk_config_service.validate_config.return_value = True

        result = self.coordinator.validate_config(config)
        assert result is True

    def test_validate_config_invalid(self):
        """Test configuration validation with invalid config."""
        config = Mock(spec=GenericDockerCompileConfig)
        config.zmk_config_repo = None
        config.west_workspace = None
        config.build_strategy = "cmake"

        # Mock all services as unavailable
        self.mock_zmk_config_service.check_available.return_value = False
        self.mock_west_service.check_available.return_value = False
        self.mock_cmake_service.check_available.return_value = False

        result = self.coordinator.validate_config(config)
        assert result is False

    def test_check_available_true(self):
        """Test availability check when services are available."""
        self.mock_zmk_config_service.check_available.return_value = True
        self.mock_docker_adapter.is_available.return_value = True

        result = self.coordinator.check_available()
        assert result is True

    def test_check_available_no_docker(self):
        """Test availability check when Docker is not available."""
        self.mock_docker_adapter.is_available.return_value = False

        result = self.coordinator.check_available()
        assert result is False

    def test_check_available_no_services(self):
        """Test availability check when no services are available."""
        self.mock_zmk_config_service.check_available.return_value = False
        self.mock_west_service.check_available.return_value = False
        self.mock_cmake_service.check_available.return_value = False
        self.mock_docker_adapter.is_available.return_value = True

        result = self.coordinator.check_available()
        assert result is False

    def test_get_available_strategies(self):
        """Test getting list of available strategies."""
        self.mock_zmk_config_service.check_available.return_value = True
        self.mock_west_service.check_available.return_value = False
        self.mock_cmake_service.check_available.return_value = True

        strategies = self.coordinator.get_available_strategies()
        assert "zmk_config" in strategies
        assert "west" not in strategies
        assert "cmake" in strategies

    def test_add_compilation_service(self):
        """Test adding a compilation service."""
        new_service = Mock()
        self.coordinator.add_compilation_service("new_strategy", new_service)

        coordinator = self.coordinator
        assert "new_strategy" in coordinator.compilation_services
        assert coordinator.compilation_services["new_strategy"] is new_service

    def test_docker_adapter_injection(self):
        """Test Docker adapter injection into services."""
        # Mock service with set_docker_adapter method
        self.mock_zmk_config_service.set_docker_adapter = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            keymap_file = Path(temp_dir) / "keymap.keymap"
            config_file = Path(temp_dir) / "config.conf"
            output_dir = Path(temp_dir) / "output"

            config = Mock(spec=GenericDockerCompileConfig)
            config.zmk_config_repo = Mock(spec=ZmkConfigRepoConfig)
            config.west_workspace = None
            config.build_strategy = "zmk_config"

            # Mock service availability and validation
            self.mock_zmk_config_service.check_available.return_value = True
            self.mock_zmk_config_service.validate_config.return_value = True
            self.mock_zmk_config_service.compile.return_value = BuildResult(
                success=True
            )

            self.coordinator.compile(keymap_file, config_file, output_dir, config)

            # Verify Docker adapter was injected (may be called multiple times during strategy selection and compilation)
            self.mock_zmk_config_service.set_docker_adapter.assert_called_with(
                self.mock_docker_adapter
            )

    def test_strategy_selection_priority(self):
        """Test strategy selection follows priority order."""
        # Mock configuration that matches multiple strategies
        config = Mock(spec=GenericDockerCompileConfig)
        config.zmk_config_repo = Mock(spec=ZmkConfigRepoConfig)
        config.west_workspace = Mock(spec=WestWorkspaceConfig)
        config.build_strategy = "zmk_config"

        # Mock all services as available and valid
        self.mock_zmk_config_service.check_available.return_value = True
        self.mock_zmk_config_service.validate_config.return_value = True
        self.mock_west_service.check_available.return_value = True
        self.mock_west_service.validate_config.return_value = True
        self.mock_cmake_service.check_available.return_value = True
        self.mock_cmake_service.validate_config.return_value = True

        # ZMK config should have priority
        coordinator = self.coordinator
        strategy = coordinator._select_compilation_strategy(config)
        assert strategy == "zmk_config"

    def test_exception_handling(self):
        """Test exception handling during compilation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            keymap_file = Path(temp_dir) / "keymap.keymap"
            config_file = Path(temp_dir) / "config.conf"
            output_dir = Path(temp_dir) / "output"

            config = Mock(spec=GenericDockerCompileConfig)
            config.zmk_config_repo = Mock(spec=ZmkConfigRepoConfig)
            config.west_workspace = None
            config.build_strategy = "zmk_config"

            # Mock service to raise exception
            self.mock_zmk_config_service.check_available.return_value = True
            self.mock_zmk_config_service.validate_config.return_value = True
            self.mock_zmk_config_service.compile.side_effect = Exception(
                "Service error"
            )

            result = self.coordinator.compile(
                keymap_file, config_file, output_dir, config
            )

            assert result.success is False
            assert any(
                "Compilation coordination failed" in error for error in result.errors
            )


class TestCompilationCoordinatorIntegration:
    """Test compilation coordinator integration scenarios."""

    def setup_method(self):
        """Set up test instance."""
        from glovebox.compilation import create_compilation_coordinator

        self.coordinator = create_compilation_coordinator()

    def test_real_service_integration(self):
        """Test integration with real compilation services."""
        # Test that the coordinator can load real services
        available_strategies = self.coordinator.get_available_strategies()
        assert isinstance(available_strategies, list)

        # Should include zmk_config and west strategies
        coordinator = self.coordinator
        assert "zmk_config" in coordinator.compilation_services
        assert "west" in coordinator.compilation_services

    def test_strategy_selection_integration(self):
        """Test strategy selection with real service instances."""
        # Test ZMK config strategy selection
        config_zmk = Mock(spec=GenericDockerCompileConfig)
        config_zmk.zmk_config_repo = Mock(spec=ZmkConfigRepoConfig)
        config_zmk.zmk_config_repo.config_repo_url = (
            "https://github.com/test/zmk-config"
        )
        config_zmk.zmk_config_repo.workspace_path = "/zmk-config-workspace"
        config_zmk.zmk_config_repo.config_path = "config"
        config_zmk.west_workspace = None
        config_zmk.build_strategy = "zmk_config"

        coordinator = self.coordinator
        strategy = coordinator._select_compilation_strategy(config_zmk)
        assert strategy in [
            "zmk_config",
            "west",
            "cmake",
            None,
        ]  # Depends on service availability

        # Test west strategy selection
        config_west = Mock(spec=GenericDockerCompileConfig)
        config_west.zmk_config_repo = None
        config_west.west_workspace = Mock(spec=WestWorkspaceConfig)
        config_west.west_workspace.workspace_path = "/west-workspace"
        config_west.west_workspace.manifest_url = "https://github.com/zmkfirmware/zmk"
        config_west.west_workspace.manifest_revision = "main"
        config_west.build_strategy = "west"

        coordinator = self.coordinator
        strategy = coordinator._select_compilation_strategy(config_west)
        assert strategy in ["west", "cmake", None]  # Depends on service availability

    def test_service_coordination_workflow(self):
        """Test complete service coordination workflow."""
        # Test that coordinator properly coordinates services
        config = Mock(spec=GenericDockerCompileConfig)
        config.zmk_config_repo = None
        config.west_workspace = None
        config.build_strategy = "cmake"

        # Should be able to validate config
        is_valid = self.coordinator.validate_config(config)
        assert isinstance(is_valid, bool)

        # Should be able to check availability
        coordinator = self.coordinator
        is_available = coordinator.check_available()
        assert isinstance(is_available, bool)
