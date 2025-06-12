"""Test West compilation service."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from glovebox.compilation.services.west_compilation_service import (
    WestCompilationService,
    create_west_service,
)
from glovebox.config.compile_methods import (
    CompilationConfig,
    WestWorkspaceConfig,
)
from glovebox.firmware.models import FirmwareOutputFiles


class TestWestCompilationService:
    """Test West compilation service functionality."""

    def setup_method(self):
        """Set up test instance."""
        self.service = create_west_service()

        # Mock dependencies
        self.service.workspace_manager = Mock()
        self.service.build_matrix_resolver = Mock()
        self.service.artifact_collector = Mock()
        self.service.environment_manager = Mock()
        self.service.volume_manager = Mock()

        # Mock Docker adapter
        self.mock_docker_adapter = Mock()
        self.service.set_docker_adapter(self.mock_docker_adapter)

    def _create_mock_config(self, **overrides):
        """Create a mock CompilationConfig with all required attributes."""
        config = Mock(spec=CompilationConfig)

        # Set default values for all required attributes
        config.image = "zmkfirmware/zmk-build-arm:stable"
        config.board_targets = ["nice_nano_v2"]
        config.build_commands = []
        config.volume_templates = []
        config.environment_template = {}
        config.enable_user_mapping = True
        config.detect_user_automatically = True
        config.west_workspace = None

        # Apply any overrides
        for key, value in overrides.items():
            setattr(config, key, value)

        return config

    def test_initialization(self):
        """Test service initialization."""
        service = WestCompilationService()
        assert service.service_name == "west_compilation"
        assert service.service_version == "1.0.0"
        assert hasattr(service, "workspace_manager")
        assert hasattr(service, "build_matrix_resolver")
        assert hasattr(service, "artifact_collector")

    def test_create_west_service(self):
        """Test factory function creates service."""
        service = create_west_service()
        assert isinstance(service, WestCompilationService)

    def test_validate_configuration_valid_no_workspace(self):
        """Test configuration validation with no workspace config."""
        config = self._create_mock_config(west_workspace=None)

        result = self.service.validate_configuration(config)
        assert result is True

    def test_validate_configuration_valid_with_workspace(self):
        """Test configuration validation with valid workspace config."""
        config = Mock(spec=CompilationConfig)
        config.west_workspace = Mock(spec=WestWorkspaceConfig)
        config.west_workspace.workspace_path = "/tmp/workspace"
        config.west_workspace.manifest_url = "https://github.com/zmkfirmware/zmk"

        result = self.service.validate_configuration(config)
        assert result is True

    def test_validate_configuration_missing_workspace_path(self):
        """Test configuration validation with missing workspace path."""
        config = Mock(spec=CompilationConfig)
        config.west_workspace = Mock(spec=WestWorkspaceConfig)
        config.west_workspace.workspace_path = ""
        config.west_workspace.manifest_url = "https://github.com/zmkfirmware/zmk"

        result = self.service.validate_configuration(config)
        assert result is False

    def test_validate_configuration_missing_manifest_url(self):
        """Test configuration validation with missing manifest URL."""
        config = Mock(spec=CompilationConfig)
        config.west_workspace = Mock(spec=WestWorkspaceConfig)
        config.west_workspace.workspace_path = "/tmp/workspace"
        config.west_workspace.manifest_url = ""

        result = self.service.validate_configuration(config)
        assert result is False

    def test_compile_success_with_workspace(self):
        """Test successful compilation with workspace."""
        with tempfile.TemporaryDirectory() as temp_dir:
            keymap_file = Path(temp_dir) / "keymap.keymap"
            config_file = Path(temp_dir) / "config.conf"
            output_dir = Path(temp_dir) / "output"

            keymap_file.touch()
            config_file.touch()
            output_dir.mkdir()

            # Mock configuration
            west_workspace = Mock(spec=WestWorkspaceConfig)
            west_workspace.workspace_path = str(Path(temp_dir) / "workspace")
            west_workspace.config_path = "config"
            west_workspace.manifest_url = "https://github.com/zmkfirmware/zmk"
            west_workspace.manifest_revision = "main"

            config = self._create_mock_config(west_workspace=west_workspace)

            # Mock workspace initialization
            self.service.workspace_manager.initialize_workspace.return_value = True

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

            # Mock environment preparation
            self.service.environment_manager.prepare_environment.return_value = {
                "ENV": "test"
            }

            result = self.service.compile(keymap_file, config_file, output_dir, config)

            assert result.success is True
            assert result.output_files.main_uf2 is not None

    def test_compile_success_without_workspace(self):
        """Test successful compilation without workspace."""
        with tempfile.TemporaryDirectory() as temp_dir:
            keymap_file = Path(temp_dir) / "keymap.keymap"
            config_file = Path(temp_dir) / "config.conf"
            output_dir = Path(temp_dir) / "output"

            keymap_file.touch()
            config_file.touch()
            output_dir.mkdir()

            # Mock configuration without workspace
            config = self._create_mock_config(
                west_workspace=None,
                board_targets=[],
                build_commands=[],
                volume_templates=[],
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

            # Mock environment preparation
            self.service.environment_manager.prepare_environment.return_value = {
                "ENV": "test"
            }

            result = self.service.compile(keymap_file, config_file, output_dir, config)

            assert result.success is True
            assert result.output_files.main_uf2 is not None

    def test_compile_missing_docker_adapter(self):
        """Test compilation with missing Docker adapter."""
        with tempfile.TemporaryDirectory() as temp_dir:
            keymap_file = Path(temp_dir) / "keymap.keymap"
            config_file = Path(temp_dir) / "config.conf"
            output_dir = Path(temp_dir) / "output"

            config = Mock(spec=CompilationConfig)
            config.west_workspace = None

            # Remove Docker adapter
            self.service._docker_adapter = None

            result = self.service.compile(keymap_file, config_file, output_dir, config)

            assert result.success is False
            assert any(
                "Docker adapter not available" in error for error in result.errors
            )

    def test_compile_workspace_initialization_failure(self):
        """Test compilation with workspace initialization failure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            keymap_file = Path(temp_dir) / "keymap.keymap"
            config_file = Path(temp_dir) / "config.conf"
            output_dir = Path(temp_dir) / "output"

            config = Mock(spec=CompilationConfig)
            config.west_workspace = Mock(spec=WestWorkspaceConfig)
            config.west_workspace.workspace_path = str(Path(temp_dir) / "workspace")

            # Mock workspace initialization failure
            self.service.workspace_manager.initialize_workspace.return_value = False

            result = self.service.compile(keymap_file, config_file, output_dir, config)

            assert result.success is False
            assert any(
                "Failed to initialize west workspace" in error
                for error in result.errors
            )

    def test_compile_no_artifacts(self):
        """Test compilation with no artifacts generated."""
        with tempfile.TemporaryDirectory() as temp_dir:
            keymap_file = Path(temp_dir) / "keymap.keymap"
            config_file = Path(temp_dir) / "config.conf"
            output_dir = Path(temp_dir) / "output"

            config = self._create_mock_config(
                west_workspace=None,
                board_targets=[],
                build_commands=[],
                volume_templates=[],
            )

            # Mock successful Docker execution
            self.mock_docker_adapter.run_container.return_value = (0, [], [])

            # Mock no artifacts found
            firmware_files = FirmwareOutputFiles(output_dir=output_dir)
            # Since we're using the protocol method collect_artifacts that returns a tuple
            self.service.artifact_collector.collect_artifacts.return_value = (
                [],
                firmware_files,
            )

            # Mock environment preparation
            self.service.environment_manager.prepare_environment.return_value = {
                "ENV": "test"
            }

            result = self.service.compile(keymap_file, config_file, output_dir, config)

            assert result.success is False
            assert any(
                "No firmware files generated" in error for error in result.errors
            )

    def test_generate_build_commands_with_board_targets(self):
        """Test build command generation with board targets."""
        config = self._create_mock_config(
            board_targets=["nice_nano_v2", "bluemicro840_v1"], build_commands=[]
        )

        commands = self.service._generate_build_commands(config)

        assert len(commands) == 3  # west zephyr-export + 2 board targets
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
        config = self._create_mock_config(board_targets=[], build_commands=[])

        commands = self.service._generate_build_commands(config)

        assert len(commands) == 2  # west zephyr-export + default build
        assert "west zephyr-export" in commands
        assert "west build -s zmk/app -p always" in commands

    def test_generate_build_commands_with_custom(self):
        """Test build command generation with custom commands."""
        config = self._create_mock_config(
            board_targets=[], build_commands=["custom command 1", "custom command 2"]
        )

        commands = self.service._generate_build_commands(config)

        assert len(commands) == 4  # west zephyr-export + default build + 2 custom
        assert "west zephyr-export" in commands
        assert "west build -s zmk/app -p always" in commands
        assert "custom command 1" in commands
        assert "custom command 2" in commands

    def test_set_docker_adapter(self):
        """Test setting Docker adapter."""
        mock_adapter = Mock()
        self.service.set_docker_adapter(mock_adapter)
        assert self.service._docker_adapter is mock_adapter

    def test_check_available_with_adapter(self):
        """Test availability check with Docker adapter."""
        self.mock_docker_adapter.is_available.return_value = True
        assert self.service.check_available() is True

    def test_check_available_without_adapter(self):
        """Test availability check without Docker adapter."""
        self.service._docker_adapter = None
        assert self.service.check_available() is False

    def test_docker_execution_failure(self):
        """Test handling of Docker execution failure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            keymap_file = Path(temp_dir) / "keymap.keymap"
            config_file = Path(temp_dir) / "config.conf"
            output_dir = Path(temp_dir) / "output"

            config = self._create_mock_config(
                west_workspace=None,
                board_targets=[],
                build_commands=[],
                volume_templates=[],
            )

            # Mock Docker execution failure
            self.mock_docker_adapter.run_container.return_value = (
                1,
                [],
                ["Build failed"],
            )

            # Mock environment preparation
            self.service.environment_manager.prepare_environment.return_value = {
                "ENV": "test"
            }

            result = self.service.compile(keymap_file, config_file, output_dir, config)

            assert result.success is False
            assert any(
                "West compilation failed with exit code 1" in error
                for error in result.errors
            )

    def test_prepare_build_volumes_with_workspace(self):
        """Test volume preparation with workspace."""
        with tempfile.TemporaryDirectory() as temp_dir:
            keymap_file = Path(temp_dir) / "keymap.keymap"
            config_file = Path(temp_dir) / "config.conf"
            output_dir = Path(temp_dir) / "output"
            workspace_path = Path(temp_dir) / "workspace"

            # Create workspace directory
            workspace_path.mkdir()

            config = Mock(spec=CompilationConfig)
            config.west_workspace = Mock(spec=WestWorkspaceConfig)
            config.west_workspace.workspace_path = str(workspace_path)
            config.west_workspace.config_path = "config"
            config.volume_templates = []

            volumes = self.service._prepare_build_volumes(
                workspace_path, keymap_file, config_file, output_dir, config
            )

            # Check that volumes include output directory and workspace mapping
            volume_targets = [vol[1] for vol in volumes]
            assert "/build" in volume_targets
            assert any("keymap.keymap" in target for target in volume_targets)
            assert any("config.conf" in target for target in volume_targets)

    def test_prepare_build_volumes_without_workspace(self):
        """Test volume preparation without workspace."""
        with tempfile.TemporaryDirectory() as temp_dir:
            keymap_file = Path(temp_dir) / "keymap.keymap"
            config_file = Path(temp_dir) / "config.conf"
            output_dir = Path(temp_dir) / "output"

            config = Mock(spec=CompilationConfig)
            config.west_workspace = None
            config.volume_templates = []

            volumes = self.service._prepare_build_volumes(
                None, keymap_file, config_file, output_dir, config
            )

            # Check that volumes include output directory and default mappings
            volume_targets = [vol[1] for vol in volumes]
            assert "/build" in volume_targets
            assert any("keymap.keymap" in target for target in volume_targets)
            assert any("config.conf" in target for target in volume_targets)

    def test_parse_volume_template(self):
        """Test volume template parsing."""
        volumes: list[tuple[str, str]] = []
        template = "/host/path:/container/path:ro"

        self.service._parse_volume_template(template, volumes)

        assert len(volumes) == 1
        assert volumes[0] == ("/host/path", "/container/path:ro")

    def test_parse_volume_template_invalid(self):
        """Test volume template parsing with invalid template."""
        volumes: list[tuple[str, str]] = []
        template = "invalid_template"

        # Should not raise exception but log warning
        self.service._parse_volume_template(template, volumes)

        # Should not add invalid template
        assert len(volumes) == 0


class TestWestCompilationServiceIntegration:
    """Test West compilation service integration scenarios."""

    def setup_method(self):
        """Set up test instance."""
        self.service = create_west_service()

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

            firmware_files = FirmwareOutputFiles(
                output_dir=Path("/tmp"),
                main_uf2=Path("/tmp/test.uf2"),
            )
            mock_collector.collect_artifacts.return_value = (
                [Path("/tmp/test.uf2")],
                firmware_files,
            )

            mock_env.prepare_environment.return_value = {"TEST": "env"}

            # Mock Docker adapter
            mock_docker = Mock()
            mock_docker.run_container.return_value = (0, [], [])
            self.service.set_docker_adapter(mock_docker)

            # Test configuration
            config = Mock(spec=CompilationConfig)
            config.west_workspace = Mock(spec=WestWorkspaceConfig)
            config.west_workspace.workspace_path = "/tmp/workspace"
            config.west_workspace.config_path = "config"
            config.west_workspace.manifest_url = "https://github.com/zmkfirmware/zmk"
            config.west_workspace.manifest_revision = "main"
            config.image = "test:latest"
            config.board_targets = []
            config.build_commands = []
            config.volume_templates = []
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
                "artifact_error",
                "artifact_collector",
                "collect_artifacts",
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
                elif scenario_name == "artifact_error":
                    self.service.workspace_manager.initialize_workspace.return_value = (
                        True
                    )
                    self.service.environment_manager.prepare_environment.return_value = {}

                    # Mock Docker success
                    mock_docker = Mock()
                    mock_docker.run_container.return_value = (0, [], [])
                    self.service.set_docker_adapter(mock_docker)

                    getattr(
                        self.service, service_attr
                    ).collect_artifacts.side_effect = exception

                config = Mock(spec=CompilationConfig)
                config.west_workspace = Mock(spec=WestWorkspaceConfig)
                config.west_workspace.workspace_path = "/tmp/workspace"
                config.volume_templates = []

                with tempfile.TemporaryDirectory() as temp_dir:
                    keymap_file = Path(temp_dir) / "test.keymap"
                    config_file = Path(temp_dir) / "test.conf"
                    output_dir = Path(temp_dir) / "output"

                    result = self.service.compile(
                        keymap_file, config_file, output_dir, config
                    )

                    assert result.success is False
                    assert len(result.errors) > 0

    def test_build_compilation_command_with_build_root(self):
        """Test west build command generation with build_root specified."""
        # Create a configuration with build_root
        west_workspace = WestWorkspaceConfig(
            workspace_path="/tmp/workspace", build_root="/custom/build/path"
        )
        config = CompilationConfig(
            west_workspace=west_workspace, board_targets=["nice_nano_v2"]
        )

        workspace_path = Path("/tmp/workspace")

        # Get the build command
        command = self.service._build_compilation_command(workspace_path, config)

        # Verify the command includes the build root directory
        assert command == "west build -b nice_nano_v2 -d /custom/build/path"

    def test_build_compilation_command_without_build_root(self):
        """Test west build command generation without build_root."""
        # Create a configuration without build_root
        west_workspace = WestWorkspaceConfig(workspace_path="/tmp/workspace")
        config = CompilationConfig(
            west_workspace=west_workspace, board_targets=["nice_nano_v2"]
        )

        workspace_path = Path("/tmp/workspace")

        # Get the build command
        command = self.service._build_compilation_command(workspace_path, config)

        # Verify the command does not include the -d flag
        assert command == "west build -b nice_nano_v2"

    def test_build_compilation_command_no_west_workspace(self):
        """Test west build command generation with no west workspace config."""
        # Create a configuration without west_workspace
        config = CompilationConfig(board_targets=["nice_nano_v2"])

        workspace_path = Path("/tmp/workspace")

        # Get the build command
        command = self.service._build_compilation_command(workspace_path, config)

        # Verify the command works without west workspace config
        assert command == "west build -b nice_nano_v2"
