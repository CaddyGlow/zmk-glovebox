"""Test ZMK config compilation service."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from glovebox.compilation.helpers.zmk_helpers import (
    build_zmk_compilation_commands,
    build_zmk_fallback_commands,
    build_zmk_init_commands,
    setup_zmk_workspace_paths,
)
from glovebox.compilation.models.build_matrix import BuildMatrix, BuildTarget
from glovebox.compilation.models.compilation_params import (
    ZmkCompilationParams,
    ZmkWorkspaceParams,
)
from glovebox.compilation.services.zmk_config_service import (
    ZmkConfigCompilationService,
    create_zmk_config_service,
)
from glovebox.config.compile_methods import (
    CompilationConfig,
    ZmkWorkspaceConfig,
)
from glovebox.firmware.models import FirmwareOutputFiles


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
        assert service.workspace_manager is not None

    def test_create_zmk_config_service(self):
        """Test factory function creates service correctly."""
        service = create_zmk_config_service()
        assert isinstance(service, ZmkConfigCompilationService)

    def test_validate_configuration_valid(self):
        """Test configuration validation with valid config."""
        config = self._create_mock_config()
        config.zmk_config_repo = Mock()
        config.zmk_config_repo.config_repo_url = "https://github.com/test/config"
        config.zmk_config_repo.build_root = Mock()
        config.zmk_config_repo.build_root.container_path = "build"

        result = self.service.validate_config(config)
        assert result is True

    def test_validate_configuration_missing_repo(self):
        """Test configuration validation with missing repo."""
        config = self._create_mock_config()
        config.zmk_config_repo = None

        # This should still be valid for dynamic mode
        result = self.service.validate_config(config)
        assert result is True

    def test_set_docker_adapter(self):
        """Test setting Docker adapter."""
        adapter = Mock()
        self.service.set_docker_adapter(adapter)
        assert self.service._docker_adapter == adapter


class TestZmkHelperFunctions:
    """Test ZMK helper functions."""

    def test_setup_zmk_workspace_paths(self):
        """Test workspace path setup helper."""
        # Create test configuration
        config = Mock(spec=CompilationConfig)
        zmk_config = Mock(spec=ZmkWorkspaceConfig)
        zmk_config.workspace_path = Mock()
        zmk_config.build_root = Mock()
        zmk_config.config_path = Mock()
        config.zmk_config_repo = zmk_config

        params = ZmkCompilationParams(
            keymap_file=Path("/test/keymap.keymap"),
            config_file=Path("/test/config.conf"),
            compilation_config=config,
        )

        # Test the helper function
        setup_zmk_workspace_paths(params)

        # Verify paths were set
        assert zmk_config.workspace_path.host_path is not None
        assert zmk_config.build_root.host_path is not None
        assert zmk_config.config_path.host_path is not None
        assert zmk_config.build_root.container_path == "/build"
        assert zmk_config.config_path.container_path == "/config"

    def test_build_zmk_init_commands(self):
        """Test initialization command building."""
        zmk_config = Mock()
        zmk_config.workspace_path = Mock()
        zmk_config.workspace_path.container_path = "/workspace"
        zmk_config.config_path_absolute = "/config"
        zmk_config.build_root = Mock()
        zmk_config.build_root.container_path = "/build"

        workspace_params = ZmkWorkspaceParams(
            workspace_path=Path("/tmp/workspace"), zmk_config=zmk_config
        )

        commands = build_zmk_init_commands(workspace_params)

        assert len(commands) == 4
        assert "cd /workspace" in commands
        assert "west init -l /config /build" in commands
        assert "west update" in commands
        assert "west zephyr-export" in commands

    def test_build_zmk_compilation_commands(self):
        """Test compilation command building from matrix."""
        # Create build matrix
        targets = [
            BuildTarget(
                board="nice_nano_v2",
                shield="corne_left",
                artifact_name="corne_left",
                cmake_args=["-DBOARD_ROOT=/boards"],
            ),
            BuildTarget(
                board="nice_nano_v2",
                shield="corne_right",
                artifact_name="corne_right",
            ),
        ]
        build_matrix = BuildMatrix(targets=targets)

        # Create workspace params
        zmk_config = Mock()
        zmk_config.build_root_absolute = Path("/build")
        zmk_config.config_path_absolute = "/config"

        workspace_params = ZmkWorkspaceParams(
            workspace_path=Path("/tmp/workspace"), zmk_config=zmk_config
        )

        commands = build_zmk_compilation_commands(build_matrix, workspace_params)

        assert len(commands) == 2

        # Check left target command
        left_cmd = commands[0]
        assert "west build -s zmk/app -b nice_nano_v2" in left_cmd
        assert "-d /build/corne_left" in left_cmd
        assert "-DZMK_CONFIG=/config" in left_cmd
        assert "-DSHIELD=corne_left" in left_cmd
        assert "-DBOARD_ROOT=/boards" in left_cmd

        # Check right target command
        right_cmd = commands[1]
        assert "west build -s zmk/app -b nice_nano_v2" in right_cmd
        assert "-d /build/corne_right" in right_cmd
        assert "-DZMK_CONFIG=/config" in right_cmd
        assert "-DSHIELD=corne_right" in right_cmd

    def test_build_zmk_fallback_commands_single_board(self):
        """Test fallback command building for single board."""
        zmk_config = Mock()
        zmk_config.build_root = Mock()
        zmk_config.build_root.container_path = "/build"
        zmk_config.config_path_absolute = "/config"

        workspace_params = ZmkWorkspaceParams(
            workspace_path=Path("/tmp/workspace"), zmk_config=zmk_config
        )

        commands = build_zmk_fallback_commands(workspace_params, ["nice_nano_v2"])

        assert len(commands) == 1
        command = commands[0]
        assert "west build -s zmk/app -b nice_nano_v2" in command
        assert "-d /build" in command
        assert "-DZMK_CONFIG=/config" in command

    def test_build_zmk_fallback_commands_multiple_boards(self):
        """Test fallback command building for multiple boards."""
        zmk_config = Mock()
        zmk_config.build_root = Mock()
        zmk_config.build_root.container_path = "/build"
        zmk_config.config_path_absolute = "/config"

        workspace_params = ZmkWorkspaceParams(
            workspace_path=Path("/tmp/workspace"), zmk_config=zmk_config
        )

        board_targets = ["board1", "board2"]
        commands = build_zmk_fallback_commands(workspace_params, board_targets)

        assert len(commands) == 2

        assert "west build -s zmk/app -b board1" in commands[0]
        assert "-d /build_board1" in commands[0]
        assert "-DZMK_CONFIG=/config" in commands[0]

        assert "west build -s zmk/app -b board2" in commands[1]
        assert "-d /build_board2" in commands[1]
        assert "-DZMK_CONFIG=/config" in commands[1]


class TestZmkCompilationParams:
    """Test ZMK compilation parameter classes."""

    def test_should_use_dynamic_generation_no_profile(self):
        """Test dynamic generation decision without keyboard profile."""
        config = Mock(spec=CompilationConfig)
        params = ZmkCompilationParams(
            keymap_file=Path("/test.keymap"),
            config_file=Path("/test.conf"),
            compilation_config=config,
            keyboard_profile=None,
        )

        assert params.should_use_dynamic_generation is False

    def test_should_use_dynamic_generation_no_repo(self):
        """Test dynamic generation decision without repo config."""
        from glovebox.config.profile import KeyboardProfile

        config = Mock(spec=CompilationConfig)
        config.zmk_config_repo = None

        profile = Mock(spec=KeyboardProfile)

        params = ZmkCompilationParams(
            keymap_file=Path("/test.keymap"),
            config_file=Path("/test.conf"),
            compilation_config=config,
            keyboard_profile=profile,
        )

        assert params.should_use_dynamic_generation is True

    def test_should_use_dynamic_generation_empty_url(self):
        """Test dynamic generation decision with empty repo URL."""
        from glovebox.config.profile import KeyboardProfile

        config = Mock(spec=CompilationConfig)
        zmk_config = Mock(spec=ZmkWorkspaceConfig)
        zmk_config.config_repo_url = ""
        config.zmk_config_repo = zmk_config

        profile = Mock(spec=KeyboardProfile)

        params = ZmkCompilationParams(
            keymap_file=Path("/test.keymap"),
            config_file=Path("/test.conf"),
            compilation_config=config,
            keyboard_profile=profile,
        )

        assert params.should_use_dynamic_generation is True

    def test_should_use_dynamic_generation_with_url(self):
        """Test dynamic generation decision with valid repo URL."""
        from glovebox.config.profile import KeyboardProfile

        config = Mock(spec=CompilationConfig)
        zmk_config = Mock(spec=ZmkWorkspaceConfig)
        zmk_config.config_repo_url = "https://github.com/test/config"
        config.zmk_config_repo = zmk_config

        profile = Mock(spec=KeyboardProfile)

        params = ZmkCompilationParams(
            keymap_file=Path("/test.keymap"),
            config_file=Path("/test.conf"),
            compilation_config=config,
            keyboard_profile=profile,
        )

        assert params.should_use_dynamic_generation is False


class TestZmkConfigServiceIntegration:
    """Test ZMK config service integration workflows."""

    def setup_method(self):
        """Set up test instance."""
        self.service = create_zmk_config_service()
        self.service.workspace_manager = Mock()
        self.mock_docker_adapter = Mock()
        self.service.set_docker_adapter(self.mock_docker_adapter)

    def test_service_error_propagation(self):
        """Test error propagation in service methods."""
        # This test ensures the service properly handles errors
        # without calling removed methods

        config = Mock(spec=CompilationConfig)
        config.image = "test-image"
        config.zmk_config_repo = None  # This should trigger an error

        keymap_file = Path("/tmp/test.keymap")
        config_file = Path("/tmp/test.conf")
        output_dir = Path("/tmp/output")

        # The compile method should handle missing zmk_config_repo gracefully
        result = self.service.compile(keymap_file, config_file, output_dir, config)

        # Should fail due to missing zmk_config_repo
        assert result.success is False
        assert len(result.errors) > 0
