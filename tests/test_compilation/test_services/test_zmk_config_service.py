"""Test ZMK config compilation service."""

import tempfile
from pathlib import Path
from typing import cast
from unittest.mock import Mock, patch

import pytest

from glovebox.compilation.models.build_matrix import BuildMatrix, BuildTarget
from glovebox.compilation.services.zmk_config_service import (
    ZmkConfigCompilationService,
    create_zmk_config_service,
)
from glovebox.config.compile_methods import (
    GenericDockerCompileConfig,
    ZmkConfigRepoConfig,
)
from glovebox.firmware.models import BuildResult, FirmwareOutputFiles


class TestZmkConfigCompilationService:
    """Test ZMK config compilation service functionality."""

    def setup_method(self):
        """Set up test instance."""
        self.service = create_zmk_config_service()

        # Mock dependencies
        self.service.workspace_manager = Mock()
        self.service.build_matrix_resolver = Mock()
        self.service.artifact_collector = Mock()
        self.service.environment_manager = Mock()
        self.service.volume_manager = Mock()
        self.service.firmware_scanner = Mock()

        # Mock Docker adapter
        self.mock_docker_adapter = Mock()
        self.service.set_docker_adapter(self.mock_docker_adapter)

    def _create_mock_config(self, **overrides):
        """Create a mock GenericDockerCompileConfig with all required attributes."""
        config = Mock(spec=GenericDockerCompileConfig)

        # Set default values for all required attributes
        config.image = "zmkfirmware/zmk-build-arm:stable"
        config.board_targets = ["nice_nano_v2"]
        config.build_commands = []
        config.volume_templates = []
        config.environment_template = {}
        config.enable_user_mapping = True
        config.detect_user_automatically = True
        config.zmk_config_repo = None

        # Apply any overrides
        for key, value in overrides.items():
            setattr(config, key, value)

        return config

    def test_initialization(self):
        """Test service initialization."""
        service = ZmkConfigCompilationService()
        assert service.service_name == "zmk_config_compilation"
        assert service.service_version == "1.0.0"
        assert hasattr(service, "workspace_manager")
        assert hasattr(service, "build_matrix_resolver")
        assert hasattr(service, "artifact_collector")

    def test_create_zmk_config_service(self):
        """Test factory function creates service."""
        service = create_zmk_config_service()
        assert isinstance(service, ZmkConfigCompilationService)

    def test_validate_configuration_valid(self):
        """Test configuration validation with valid config."""
        config = Mock(spec=GenericDockerCompileConfig)
        config.zmk_config_repo = Mock(spec=ZmkConfigRepoConfig)
        config.zmk_config_repo.config_repo_url = "https://github.com/user/zmk-config"
        config.zmk_config_repo.workspace_path = "/tmp/workspace"

        result = self.service.validate_configuration(config)
        assert result is True

    def test_validate_configuration_missing_repo(self):
        """Test configuration validation with missing repo config."""
        config = Mock(spec=GenericDockerCompileConfig)
        config.zmk_config_repo = None

        result = self.service.validate_configuration(config)
        assert result is False

    def test_validate_configuration_missing_url(self):
        """Test configuration validation with missing repo URL (dynamic mode)."""
        config = Mock(spec=GenericDockerCompileConfig)
        config.zmk_config_repo = Mock(spec=ZmkConfigRepoConfig)
        config.zmk_config_repo.config_repo_url = ""
        config.zmk_config_repo.workspace_path = "/tmp/workspace"

        # Missing URL is now valid for dynamic generation mode
        result = self.service.validate_configuration(config)
        assert result is True

    def test_validate_configuration_missing_workspace(self):
        """Test configuration validation with missing workspace path."""
        config = Mock(spec=GenericDockerCompileConfig)
        config.zmk_config_repo = Mock(spec=ZmkConfigRepoConfig)
        config.zmk_config_repo.config_repo_url = "https://github.com/user/zmk-config"
        config.zmk_config_repo.workspace_path = ""

        result = self.service.validate_configuration(config)
        assert result is False

    def test_compile_success(self):
        """Test successful compilation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            keymap_file = Path(temp_dir) / "keymap.keymap"
            config_file = Path(temp_dir) / "config.conf"
            output_dir = Path(temp_dir) / "output"

            keymap_file.touch()
            config_file.touch()
            output_dir.mkdir()

            # Mock configuration
            zmk_config_repo = Mock(spec=ZmkConfigRepoConfig)
            zmk_config_repo.config_repo_url = "https://github.com/user/zmk-config"
            zmk_config_repo.workspace_path = str(Path(temp_dir) / "workspace")
            zmk_config_repo.config_path = "config"
            zmk_config_repo.build_yaml_path = "build.yaml"
            zmk_config_repo.config_repo_revision = "main"
            zmk_config_repo.west_commands = [
                "west init -l config",
                "west update",
            ]

            config = self._create_mock_config(
                zmk_config_repo=zmk_config_repo,
                board_targets=["nice_nano_v2"],
                build_commands=[],
            )

            # Mock workspace initialization
            self.service.workspace_manager.initialize_workspace.return_value = True

            # Mock build matrix resolution
            build_matrix = BuildMatrix(
                targets=[
                    BuildTarget(
                        board="nice_nano_v2",
                        shield="corne_left",
                        artifact_name="corne_left",
                    ),
                    BuildTarget(
                        board="nice_nano_v2",
                        shield="corne_right",
                        artifact_name="corne_right",
                    ),
                ],
                board_defaults=["nice_nano_v2"],
                shield_defaults=["corne_left", "corne_right"],
            )
            self.service.build_matrix_resolver.resolve_from_build_yaml.return_value = (
                build_matrix
            )

            # Mock Docker execution
            self.mock_docker_adapter.run_container.return_value = (0, [], [])

            # Mock artifact collection
            firmware_files = FirmwareOutputFiles(
                output_dir=output_dir,
                main_uf2=Path(temp_dir) / "firmware.uf2",
            )
            # Since we're using the protocol method collect_artifacts that returns a tuple
            self.service.artifact_collector.collect_artifacts.return_value = (
                [Path(temp_dir) / "firmware.uf2"],
                firmware_files,
            )

            # Mock environment and volume preparation
            self.service.environment_manager.prepare_environment.return_value = {
                "ENV": "test"
            }
            self.service.volume_manager.prepare_volumes.return_value = []

            result = self.service.compile(keymap_file, config_file, output_dir, config)

            assert result.success is True
            assert result.output_files.main_uf2 is not None

    def test_compile_missing_zmk_config(self):
        """Test compilation with missing ZMK config."""
        with tempfile.TemporaryDirectory() as temp_dir:
            keymap_file = Path(temp_dir) / "keymap.keymap"
            config_file = Path(temp_dir) / "config.conf"
            output_dir = Path(temp_dir) / "output"

            config = Mock(spec=GenericDockerCompileConfig)
            config.zmk_config_repo = None

            result = self.service.compile(keymap_file, config_file, output_dir, config)

            assert result.success is False
            assert any(
                "ZMK config repository configuration is required" in error
                for error in result.errors
            )

    def test_compile_workspace_initialization_failure(self):
        """Test compilation with workspace initialization failure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            keymap_file = Path(temp_dir) / "keymap.keymap"
            config_file = Path(temp_dir) / "config.conf"
            output_dir = Path(temp_dir) / "output"

            config = Mock(spec=GenericDockerCompileConfig)
            config.zmk_config_repo = Mock(spec=ZmkConfigRepoConfig)
            config.zmk_config_repo.config_repo_url = (
                "https://github.com/user/zmk-config"
            )
            config.zmk_config_repo.workspace_path = str(Path(temp_dir) / "workspace")

            # Mock workspace initialization failure
            self.service.workspace_manager.initialize_workspace.return_value = False

            result = self.service.compile(keymap_file, config_file, output_dir, config)

            assert result.success is False
            assert any(
                "Failed to initialize ZMK config workspace" in error
                for error in result.errors
            )

    def test_compile_no_artifacts(self):
        """Test compilation with no artifacts generated."""
        with tempfile.TemporaryDirectory() as temp_dir:
            keymap_file = Path(temp_dir) / "keymap.keymap"
            config_file = Path(temp_dir) / "config.conf"
            output_dir = Path(temp_dir) / "output"

            zmk_config_repo = Mock(spec=ZmkConfigRepoConfig)
            zmk_config_repo.config_repo_url = "https://github.com/user/zmk-config"
            zmk_config_repo.workspace_path = str(Path(temp_dir) / "workspace")
            zmk_config_repo.config_path = "config"
            zmk_config_repo.build_yaml_path = "build.yaml"
            zmk_config_repo.config_repo_revision = "main"
            zmk_config_repo.west_commands = [
                "west init -l config",
                "west update",
            ]

            config = self._create_mock_config(
                zmk_config_repo=zmk_config_repo, board_targets=[], build_commands=[]
            )

            # Mock successful workspace and build execution
            self.service.workspace_manager.initialize_workspace.return_value = True

            build_matrix = BuildMatrix(
                targets=[], board_defaults=[], shield_defaults=[]
            )
            self.service.build_matrix_resolver.resolve_from_build_yaml.return_value = (
                build_matrix
            )

            self.mock_docker_adapter.run_container.return_value = (0, [], [])

            # Mock no artifacts found
            firmware_files = FirmwareOutputFiles(output_dir=output_dir)
            # Since we're using the protocol method collect_artifacts that returns a tuple
            self.service.artifact_collector.collect_artifacts.return_value = (
                [Path(temp_dir) / "firmware.uf2"],
                firmware_files,
            )

            # Mock environment and volume preparation
            self.service.environment_manager.prepare_environment.return_value = {
                "ENV": "test"
            }
            self.service.volume_manager.prepare_volumes.return_value = []

            result = self.service.compile(keymap_file, config_file, output_dir, config)

            assert result.success is False
            assert any(
                "No firmware files generated" in error for error in result.errors
            )

    def test_generate_build_commands_from_matrix(self):
        """Test build command generation from build matrix."""
        build_matrix = BuildMatrix(
            targets=[
                BuildTarget(
                    board="nice_nano_v2",
                    shield="corne_left",
                    artifact_name="corne_left",
                ),
                BuildTarget(
                    board="nice_nano_v2",
                    shield=None,
                    artifact_name="nice_nano_v2",
                ),
            ],
            board_defaults=[],
            shield_defaults=[],
        )

        config = Mock(spec=GenericDockerCompileConfig)
        config.zmk_config_repo = Mock(spec=ZmkConfigRepoConfig)
        config.zmk_config_repo.west_commands = ["west init -l config", "west update"]
        config.board_targets = []
        config.build_commands = []

        commands = self.service._generate_build_commands(build_matrix, config)

        assert (
            len(commands) == 5
        )  # 2 west commands + 1 zephyr-export + 2 build commands
        assert "west init -l config" in commands
        assert "west update" in commands
        assert "west zephyr-export" in commands
        assert (
            "west build -s zmk/app -p always -b nice_nano_v2 -d build/corne_left -- -DSHIELD=corne_left"
            in commands
        )
        assert (
            "west build -s zmk/app -p always -b nice_nano_v2 -d build/nice_nano_v2"
            in commands
        )

    def test_generate_build_commands_from_config(self):
        """Test build command generation from config board targets."""
        build_matrix = BuildMatrix(targets=[], board_defaults=[], shield_defaults=[])

        config = Mock(spec=GenericDockerCompileConfig)
        config.zmk_config_repo = None  # No west commands in this case
        config.board_targets = ["nice_nano_v2", "bluemicro840_v1"]
        config.build_commands = []

        commands = self.service._generate_build_commands(build_matrix, config)

        assert len(commands) == 3  # 1 zephyr-export + 2 build commands
        assert "west zephyr-export" in commands
        assert (
            "west build -s zmk/app -p always -b nice_nano_v2 -d build/nice_nano_v2"
            in commands
        )
        assert (
            "west build -s zmk/app -p always -b bluemicro840_v1 -d build/bluemicro840_v1"
            in commands
        )

    def test_generate_build_commands_default(self):
        """Test default build command generation."""
        build_matrix = BuildMatrix(targets=[], board_defaults=[], shield_defaults=[])

        config = Mock(spec=GenericDockerCompileConfig)
        config.zmk_config_repo = None  # No west commands in this case
        config.board_targets = []
        config.build_commands = []

        commands = self.service._generate_build_commands(build_matrix, config)

        assert len(commands) == 2  # 1 zephyr-export + 1 default build command
        assert "west zephyr-export" in commands
        assert "west build -s zmk/app -p always" in commands

    def test_generate_build_commands_with_custom(self):
        """Test build command generation with custom commands."""
        build_matrix = BuildMatrix(targets=[], board_defaults=[], shield_defaults=[])

        config = Mock(spec=GenericDockerCompileConfig)
        config.zmk_config_repo = None  # No west commands in this case
        config.board_targets = []
        config.build_commands = ["custom command 1", "custom command 2"]

        commands = self.service._generate_build_commands(build_matrix, config)

        assert (
            len(commands) == 4
        )  # 1 zephyr-export + 1 default build + 2 custom commands
        assert "west zephyr-export" in commands
        assert "west build -s zmk/app -p always" in commands
        assert "custom command 1" in commands
        assert "custom command 2" in commands

    def test_generate_target_command_with_shield(self):
        """Test target command generation with shield."""
        target = BuildTarget(
            board="nice_nano_v2",
            shield="corne_left",
            artifact_name="corne_left",
        )

        command = self.service._generate_target_command(target)
        expected = "west build -s zmk/app -p always -b nice_nano_v2 -d build/corne_left -- -DSHIELD=corne_left"

        assert command == expected

    def test_generate_target_command_without_shield(self):
        """Test target command generation without shield."""
        target = BuildTarget(
            board="nice_nano_v2",
            shield=None,
            artifact_name="nice_nano_v2",
        )

        command = self.service._generate_target_command(target)
        expected = (
            "west build -s zmk/app -p always -b nice_nano_v2 -d build/nice_nano_v2"
        )

        assert command == expected

    def test_generate_target_command_auto_artifact_name(self):
        """Test target command generation with auto-generated artifact name."""
        target = BuildTarget(
            board="nice_nano_v2",
            shield="corne_left",
            artifact_name=None,
        )

        command = self.service._generate_target_command(target)
        expected = "west build -s zmk/app -p always -b nice_nano_v2 -d build/nice_nano_v2_corne_left -- -DSHIELD=corne_left"

        assert command == expected

    def test_set_docker_adapter(self):
        """Test setting Docker adapter."""
        mock_adapter = Mock()
        self.service.set_docker_adapter(mock_adapter)
        assert self.service._docker_adapter is mock_adapter

    def test_docker_execution_failure(self):
        """Test handling of Docker execution failure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            keymap_file = Path(temp_dir) / "keymap.keymap"
            config_file = Path(temp_dir) / "config.conf"
            output_dir = Path(temp_dir) / "output"

            zmk_config_repo = Mock(spec=ZmkConfigRepoConfig)
            zmk_config_repo.config_repo_url = "https://github.com/user/zmk-config"
            zmk_config_repo.workspace_path = str(Path(temp_dir) / "workspace")
            zmk_config_repo.config_path = "config"
            zmk_config_repo.build_yaml_path = "build.yaml"
            zmk_config_repo.config_repo_revision = "main"
            zmk_config_repo.west_commands = [
                "west init -l config",
                "west update",
            ]

            config = self._create_mock_config(
                zmk_config_repo=zmk_config_repo, board_targets=[], build_commands=[]
            )

            # Mock successful initialization
            self.service.workspace_manager.initialize_workspace.return_value = True

            build_matrix = BuildMatrix(
                targets=[], board_defaults=[], shield_defaults=[]
            )
            self.service.build_matrix_resolver.resolve_from_build_yaml.return_value = (
                build_matrix
            )

            # Mock Docker execution failure
            self.mock_docker_adapter.run_container.return_value = (
                1,
                [],
                ["Build failed"],
            )

            # Mock environment and volume preparation
            self.service.environment_manager.prepare_environment.return_value = {
                "ENV": "test"
            }
            self.service.volume_manager.prepare_volumes.return_value = []

            result = self.service.compile(keymap_file, config_file, output_dir, config)

            assert result.success is False
            assert any(
                "Build matrix execution failed" in error for error in result.errors
            )


class TestZmkConfigServiceIntegration:
    """Test ZMK config service integration scenarios."""

    def setup_method(self):
        """Set up test instance."""
        self.service = create_zmk_config_service()

    def test_service_integration_workflow(self):
        """Test complete service integration workflow."""
        with (
            patch.object(self.service, "workspace_manager") as mock_workspace,
            patch.object(self.service, "build_matrix_resolver") as mock_resolver,
            patch.object(self.service, "artifact_collector") as mock_collector,
            patch.object(self.service, "environment_manager") as mock_env,
            patch.object(self.service, "volume_manager") as mock_volume,
        ):
            # Setup mocks
            mock_workspace.initialize_workspace.return_value = True

            build_matrix = BuildMatrix(
                targets=[BuildTarget(board="test_board", shield="test_shield")],
                board_defaults=[],
                shield_defaults=[],
            )
            mock_resolver.resolve_from_build_yaml.return_value = build_matrix

            firmware_files = FirmwareOutputFiles(
                output_dir=Path("/tmp"),
                main_uf2=Path("/tmp/test.uf2"),
            )
            mock_collector.collect_artifacts.return_value = (
                [Path("/tmp/test.uf2")],
                firmware_files,
            )

            mock_env.prepare_environment.return_value = {"TEST": "env"}
            mock_volume.prepare_volumes.return_value = []

            # Mock Docker adapter
            mock_docker = Mock()
            mock_docker.run_container.return_value = (0, [], [])
            self.service.set_docker_adapter(mock_docker)

            # Test configuration
            config = Mock(spec=GenericDockerCompileConfig)
            config.zmk_config_repo = Mock(spec=ZmkConfigRepoConfig)
            config.zmk_config_repo.config_repo_url = "https://github.com/test/config"
            config.zmk_config_repo.workspace_path = "/tmp/workspace"
            config.zmk_config_repo.build_yaml_path = "build.yaml"
            config.zmk_config_repo.config_repo_revision = "main"
            config.zmk_config_repo.config_path = "config"
            config.zmk_config_repo.west_commands = [
                "west init -l config",
                "west update",
            ]
            config.image = "test:latest"
            config.board_targets = []
            config.build_commands = []
            config.enable_user_mapping = True
            config.detect_user_automatically = True

            with tempfile.TemporaryDirectory() as temp_dir:
                keymap_file = Path(temp_dir) / "test.keymap"
                config_file = Path(temp_dir) / "test.conf"
                output_dir = Path(temp_dir) / "output"

                keymap_file.touch()
                config_file.touch()
                output_dir.mkdir()

                result = self.service.compile(
                    keymap_file, config_file, output_dir, config
                )

                # Verify workflow steps
                assert result.success is True
                mock_workspace.initialize_workspace.assert_called_once()
                mock_resolver.resolve_from_build_yaml.assert_called_once()
                mock_collector.collect_artifacts.assert_called_once()
                mock_docker.run_container.assert_called_once()

    def test_service_error_propagation(self):
        """Test error propagation through service layers."""
        # Test various error scenarios
        test_scenarios = [
            (
                "workspace_error",
                "workspace_manager",
                "initialize_workspace",
                Exception("Workspace error"),
            ),
            (
                "matrix_error",
                "build_matrix_resolver",
                "resolve_from_build_yaml",
                Exception("Matrix error"),
            ),
            (
                "artifact_error",
                "artifact_collector",
                "collect_firmware_files",
                Exception("Artifact error"),
            ),
        ]

        for scenario_name, service_attr, _method_name, exception in test_scenarios:
            with (
                patch.object(self.service, "workspace_manager"),
                patch.object(self.service, "build_matrix_resolver"),
                patch.object(self.service, "artifact_collector"),
                patch.object(self.service, "environment_manager"),
                patch.object(self.service, "volume_manager"),
            ):
                # Setup the specific failure
                if scenario_name == "workspace_error":
                    getattr(
                        self.service, service_attr
                    ).initialize_workspace.side_effect = exception
                elif scenario_name == "matrix_error":
                    self.service.workspace_manager.initialize_workspace.return_value = (
                        True
                    )
                    getattr(
                        self.service, service_attr
                    ).resolve_from_build_yaml.side_effect = exception
                elif scenario_name == "artifact_error":
                    self.service.workspace_manager.initialize_workspace.return_value = (
                        True
                    )
                    self.service.build_matrix_resolver.resolve_from_build_yaml.return_value = BuildMatrix(
                        targets=[], board_defaults=[], shield_defaults=[]
                    )
                    self.service.environment_manager.prepare_environment.return_value = {}
                    self.service.volume_manager.prepare_volumes.return_value = []

                    # Mock Docker success
                    mock_docker = Mock()
                    mock_docker.run_container.return_value = (0, [], [])
                    self.service.set_docker_adapter(mock_docker)

                    getattr(
                        self.service, service_attr
                    ).collect_artifacts.side_effect = exception

                config = Mock(spec=GenericDockerCompileConfig)
                config.zmk_config_repo = Mock(spec=ZmkConfigRepoConfig)
                config.zmk_config_repo.config_repo_url = (
                    "https://github.com/test/config"
                )
                config.zmk_config_repo.workspace_path = "/tmp/workspace"

                with tempfile.TemporaryDirectory() as temp_dir:
                    keymap_file = Path(temp_dir) / "test.keymap"
                    config_file = Path(temp_dir) / "test.conf"
                    output_dir = Path(temp_dir) / "output"

                    result = self.service.compile(
                        keymap_file, config_file, output_dir, config
                    )

                    assert result.success is False
                    assert len(result.errors) > 0
