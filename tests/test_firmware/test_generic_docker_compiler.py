"""Tests for GenericDockerCompiler."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from glovebox.config.compile_methods import (
    BuildTargetConfig,
    BuildYamlConfig,
    GenericDockerCompileConfig,
    WestWorkspaceConfig,
    ZmkConfigRepoConfig,
)
from glovebox.firmware.compile.generic_docker_compiler import (
    GenericDockerCompiler,
    create_generic_docker_compiler,
)
from glovebox.firmware.models import BuildResult, FirmwareOutputFiles
from glovebox.protocols import DockerAdapterProtocol, FileAdapterProtocol


class TestGenericDockerCompiler:
    """Tests for GenericDockerCompiler class."""

    @pytest.fixture
    def mock_docker_adapter(self):
        """Create mock docker adapter."""
        adapter = Mock(spec=DockerAdapterProtocol)
        adapter.is_available.return_value = True
        adapter.run_container.return_value = (0, ["Build successful"], [])
        return adapter

    @pytest.fixture
    def mock_file_adapter(self):
        """Create mock file adapter."""
        adapter = Mock(spec=FileAdapterProtocol)
        adapter.check_exists.return_value = True
        adapter.is_file.return_value = True
        adapter.is_dir.return_value = True
        adapter.read_text.return_value = "mock content"
        adapter.write_text.return_value = None
        adapter.create_directory.return_value = None
        adapter.list_files.return_value = [Path("/output/zmk.uf2")]
        adapter.list_directory.return_value = [Path("/output/build")]
        return adapter

    @pytest.fixture
    def compiler(self, mock_docker_adapter, mock_file_adapter):
        """Create GenericDockerCompiler instance with mocked dependencies."""
        return GenericDockerCompiler(
            docker_adapter=mock_docker_adapter,
            file_adapter=mock_file_adapter,
            output_middleware=None,
        )

    @pytest.fixture
    def basic_config(self):
        """Create basic GenericDockerCompileConfig."""
        return GenericDockerCompileConfig(
            image="zmkfirmware/zmk-build-arm:stable",
            build_strategy="west",
        )

    @pytest.fixture
    def west_config(self):
        """Create west workspace configuration."""
        return WestWorkspaceConfig(
            manifest_url="https://github.com/zmkfirmware/zmk.git",
            manifest_revision="main",
            workspace_path="/zmk-workspace",
            config_path="config",
        )

    @pytest.fixture
    def zmk_config_repo_config(self):
        """Create ZMK config repository configuration."""
        return ZmkConfigRepoConfig(
            config_repo_url="https://github.com/example/zmk-config.git",
            config_repo_revision="main",
            workspace_path="/zmk-config-workspace",
            config_path="config",
            build_yaml_path="build.yaml",
        )

    @pytest.fixture
    def complete_config(self, west_config):
        """Create complete GenericDockerCompileConfig with west workspace."""
        return GenericDockerCompileConfig(
            image="zmkfirmware/zmk-build-arm:stable",
            build_strategy="west",
            west_workspace=west_config,
            board_targets=["glove80_lh", "glove80_rh"],
            cache_workspace=True,
            build_commands=["west build -d build/left -b glove80_lh"],
            environment_template={"ZEPHYR_TOOLCHAIN_VARIANT": "zephyr"},
            volume_templates=["/workspace:/src:rw"],
        )

    @pytest.fixture
    def zmk_config_complete_config(self, zmk_config_repo_config):
        """Create complete GenericDockerCompileConfig with ZMK config repository."""
        return GenericDockerCompileConfig(
            image="zmkfirmware/zmk-build-arm:stable",
            build_strategy="zmk_config",
            zmk_config_repo=zmk_config_repo_config,
            board_targets=["nice_nano_v2"],
            cache_workspace=True,
            build_commands=[],
            environment_template={"ZEPHYR_TOOLCHAIN_VARIANT": "zephyr"},
            volume_templates=[],
        )

    def test_initialization(self, mock_docker_adapter, mock_file_adapter):
        """Test GenericDockerCompiler initialization."""
        compiler = GenericDockerCompiler(
            docker_adapter=mock_docker_adapter,
            file_adapter=mock_file_adapter,
        )

        assert compiler.docker_adapter is mock_docker_adapter
        assert compiler.file_adapter is mock_file_adapter
        assert compiler.output_middleware is not None

    def test_initialization_with_defaults(self):
        """Test initialization with default adapters."""
        with (
            patch(
                "glovebox.firmware.compile.generic_docker_compiler.create_docker_adapter"
            ) as mock_docker_factory,
            patch(
                "glovebox.firmware.compile.generic_docker_compiler.create_file_adapter"
            ) as mock_file_factory,
        ):
            mock_docker = Mock()
            mock_file = Mock()
            mock_docker_factory.return_value = mock_docker
            mock_file_factory.return_value = mock_file

            compiler = GenericDockerCompiler()

            assert compiler.docker_adapter is mock_docker
            assert compiler.file_adapter is mock_file
            mock_docker_factory.assert_called_once()
            mock_file_factory.assert_called_once()

    def test_check_available(self, compiler, mock_docker_adapter):
        """Test check_available method."""
        mock_docker_adapter.is_available.return_value = True
        assert compiler.check_available() is True

        mock_docker_adapter.is_available.return_value = False
        assert compiler.check_available() is False

    def test_validate_config_valid(self, compiler, basic_config):
        """Test config validation with valid configuration."""
        assert compiler.validate_config(basic_config) is True

    def test_validate_config_invalid_image(self, compiler):
        """Test config validation with missing image."""
        config = GenericDockerCompileConfig(image="", build_strategy="west")
        assert compiler.validate_config(config) is False

    def test_validate_config_invalid_strategy(self, compiler):
        """Test config validation with invalid build strategy."""
        config = GenericDockerCompileConfig(
            image="test:latest", build_strategy="invalid_strategy"
        )
        assert compiler.validate_config(config) is False

    def test_validate_config_missing_strategy(self, compiler):
        """Test config validation with missing build strategy."""
        config = GenericDockerCompileConfig(image="test:latest", build_strategy="")
        assert compiler.validate_config(config) is False

    def test_build_image(self, compiler, basic_config):
        """Test build_image method."""
        result = compiler.build_image(basic_config)

        assert result.success is True
        assert len(result.messages) > 0
        assert "Docker image" in result.messages[0]

    def test_build_image_docker_unavailable(
        self, compiler, mock_docker_adapter, basic_config
    ):
        """Test build_image when Docker is unavailable."""
        mock_docker_adapter.is_available.return_value = False

        result = compiler.build_image(basic_config)

        assert result.success is False
        assert "Docker is not available" in result.errors[0]

    def test_compile_docker_unavailable(
        self, compiler, mock_docker_adapter, basic_config
    ):
        """Test compile when Docker is unavailable."""
        mock_docker_adapter.is_available.return_value = False

        result = compiler.compile(
            Path("/keymap.keymap"),
            Path("/config.conf"),
            Path("/output"),
            basic_config,
        )

        assert result.success is False
        assert "Docker is not available" in result.errors[0]

    def test_compile_invalid_config(self, compiler, mock_docker_adapter):
        """Test compile with invalid configuration."""
        config = GenericDockerCompileConfig(image="", build_strategy="west")

        result = compiler.compile(
            Path("/keymap.keymap"),
            Path("/config.conf"),
            Path("/output"),
            config,
        )

        assert result.success is False
        assert "Configuration validation failed" in result.errors[0]

    def test_compile_missing_files(self, compiler, mock_file_adapter, basic_config):
        """Test compile with missing input files."""
        mock_file_adapter.check_exists.return_value = False

        result = compiler.compile(
            Path("/missing.keymap"),
            Path("/config.conf"),
            Path("/output"),
            basic_config,
        )

        assert result.success is False
        assert "Keymap file not found" in result.errors[0]

    def test_compile_west_strategy_success(
        self, compiler, mock_docker_adapter, mock_file_adapter, complete_config
    ):
        """Test successful west strategy compilation."""
        # Mock successful Docker run
        mock_docker_adapter.run_container.return_value = (0, ["Build completed"], [])

        # Mock finding firmware files with proper structure
        def check_exists_side_effect(path):
            # Simulate west build structure
            return str(path) in [
                "/output",
                "/output/build",
                "/output/build/left",
                "/output/build/left/zephyr",
                "/output/build/left/zephyr/zmk.uf2",
                "/output/build/right",
                "/output/build/right/zephyr",
                "/output/build/right/zephyr/zmk.uf2",
            ]

        def is_dir_side_effect(path):
            return str(path) in [
                "/output",
                "/output/build",
                "/output/build/left",
                "/output/build/left/zephyr",
                "/output/build/right",
                "/output/build/right/zephyr",
            ]

        mock_file_adapter.check_exists.side_effect = check_exists_side_effect
        mock_file_adapter.is_dir.side_effect = is_dir_side_effect
        mock_file_adapter.list_files.side_effect = [[], []]  # No files in base dirs
        mock_file_adapter.list_directory.side_effect = [
            [Path("/output/build")],  # output dir contains build
            [
                Path("/output/build/left"),
                Path("/output/build/right"),
            ],  # build dir contents
        ]

        result = compiler.compile(
            Path("/keymap.keymap"),
            Path("/config.conf"),
            Path("/output"),
            complete_config,
        )

        assert result.success is True
        assert len(result.messages) > 0
        # Check that compilation completed - the exact message may vary
        assert any("compilation completed" in msg.lower() for msg in result.messages)

    def test_compile_west_strategy_docker_failure(
        self, compiler, mock_docker_adapter, complete_config
    ):
        """Test west strategy compilation with Docker failure."""
        mock_docker_adapter.run_container.return_value = (1, [], ["Build failed"])

        result = compiler.compile(
            Path("/keymap.keymap"),
            Path("/config.conf"),
            Path("/output"),
            complete_config,
        )

        assert result.success is False
        assert "compilation failed with exit code 1" in result.errors[0].lower()

    def test_compile_cmake_strategy(
        self, compiler, mock_docker_adapter, mock_file_adapter
    ):
        """Test cmake strategy compilation."""
        config = GenericDockerCompileConfig(
            image="cmake:latest",
            build_strategy="cmake",
            build_commands=["cmake -B build", "cmake --build build"],
        )

        mock_docker_adapter.run_container.return_value = (
            0,
            ["CMake build successful"],
            [],
        )
        mock_file_adapter.list_files.return_value = [Path("/output/firmware.uf2")]

        result = compiler.compile(
            Path("/keymap.keymap"),
            Path("/config.conf"),
            Path("/output"),
            config,
        )

        assert result.success is True

    def test_compile_unsupported_strategy(self, compiler, basic_config):
        """Test compilation with unsupported build strategy."""
        config = GenericDockerCompileConfig(
            image="test:latest",
            build_strategy="unsupported",
        )

        result = compiler.compile(
            Path("/keymap.keymap"),
            Path("/config.conf"),
            Path("/output"),
            config,
        )

        assert result.success is False
        assert "unsupported build strategy: unsupported" in result.errors[0].lower()

    def test_initialize_workspace_west(self, compiler, west_config):
        """Test initialize_workspace with west configuration."""
        result = compiler.initialize_workspace(
            GenericDockerCompileConfig(
                build_strategy="west",
                west_workspace=west_config,
            )
        )

        # Should call manage_west_workspace
        assert result is True

    def test_initialize_workspace_non_west(self, compiler):
        """Test initialize_workspace with non-west strategy."""
        result = compiler.initialize_workspace(
            GenericDockerCompileConfig(build_strategy="cmake")
        )

        assert result is True

    def test_manage_west_workspace(self, compiler, mock_docker_adapter, west_config):
        """Test manage_west_workspace method."""
        mock_docker_adapter.run_container.return_value = (
            0,
            ["West init successful"],
            [],
        )

        result = compiler.manage_west_workspace(west_config)

        assert result is True
        mock_docker_adapter.run_container.assert_called()

    def test_manage_west_workspace_failure(
        self, compiler, mock_docker_adapter, west_config
    ):
        """Test manage_west_workspace with command failure."""
        mock_docker_adapter.run_container.return_value = (1, [], ["West init failed"])

        result = compiler.manage_west_workspace(west_config)

        assert result is False

    def test_cache_workspace(self, compiler, mock_file_adapter):
        """Test cache_workspace method."""
        workspace_path = Path("/zmk-workspace")

        # Mock cache directory doesn't exist initially
        def check_exists_side_effect(path):
            # Cache directory doesn't exist, but workspace exists
            return "glovebox_cache" not in str(path)

        mock_file_adapter.check_exists.side_effect = check_exists_side_effect

        with (
            patch("tempfile.gettempdir", return_value="/tmp"),
            patch("time.time", return_value=1234567890),
        ):
            result = compiler.cache_workspace(workspace_path)

            assert result is True
            mock_file_adapter.create_directory.assert_called()
            mock_file_adapter.write_text.assert_called()

    def test_cache_workspace_error(self, compiler, mock_file_adapter):
        """Test cache_workspace with error."""

        # Mock cache directory doesn't exist
        def check_exists_side_effect(path):
            return "glovebox_cache" not in str(path)

        mock_file_adapter.check_exists.side_effect = check_exists_side_effect
        mock_file_adapter.create_directory.side_effect = Exception("Permission denied")

        result = compiler.cache_workspace(Path("/zmk-workspace"))

        assert result is False

    def test_is_cache_valid_no_metadata(self, compiler, mock_file_adapter):
        """Test is_cache_valid when no metadata exists."""
        mock_file_adapter.check_exists.return_value = False

        result = compiler.is_cache_valid(
            Path("/workspace"), GenericDockerCompileConfig()
        )

        assert result is False

    def test_is_cache_valid_version_mismatch(self, compiler, mock_file_adapter):
        """Test is_cache_valid with version mismatch."""
        mock_file_adapter.check_exists.return_value = True
        mock_file_adapter.read_text.return_value = json.dumps({"cache_version": "0.9"})

        result = compiler.is_cache_valid(
            Path("/workspace"), GenericDockerCompileConfig()
        )

        assert result is False

    def test_is_cache_valid_expired(self, compiler, mock_file_adapter):
        """Test is_cache_valid with expired cache."""
        mock_file_adapter.check_exists.return_value = True

        # Create cache metadata that's older than 24 hours
        old_timestamp = 1234567890 - (25 * 3600)  # 25 hours ago
        metadata = {
            "cache_version": "1.0",
            "cached_at": str(old_timestamp),
            "manifest_hash": "test_hash",
            "config_hash": "test_hash",
        }
        mock_file_adapter.read_text.return_value = json.dumps(metadata)

        with patch("time.time", return_value=1234567890):
            result = compiler.is_cache_valid(
                Path("/workspace"), GenericDockerCompileConfig()
            )

        assert result is False

    def test_is_cache_valid_success(self, compiler, mock_file_adapter):
        """Test successful cache validation."""
        mock_file_adapter.check_exists.return_value = True

        # Create recent cache metadata
        recent_timestamp = 1234567890 - 3600  # 1 hour ago
        metadata = {
            "cache_version": "1.0",
            "cached_at": str(recent_timestamp),
            "manifest_hash": "test_hash",
            "config_hash": "test_hash",
        }
        mock_file_adapter.read_text.return_value = json.dumps(metadata)

        with (
            patch("time.time", return_value=1234567890),
            patch.object(
                compiler, "_calculate_manifest_hash", return_value="test_hash"
            ),
            patch.object(compiler, "_calculate_config_hash", return_value="test_hash"),
        ):
            result = compiler.is_cache_valid(
                Path("/workspace"), GenericDockerCompileConfig()
            )

        assert result is True

    def test_cleanup_old_caches(self, compiler, mock_file_adapter):
        """Test cleanup_old_caches method."""
        # Mock cache directory structure
        cache_dir = Path("/tmp/glovebox_cache/workspaces")
        mock_file_adapter.check_exists.return_value = True
        mock_file_adapter.list_directory.return_value = [cache_dir / "cache1"]
        mock_file_adapter.is_dir.return_value = True
        mock_file_adapter.list_files.return_value = [
            cache_dir / "cache1" / "workspace_metadata.json"
        ]

        # Mock old cache metadata
        old_timestamp = 1234567890 - (8 * 24 * 3600)  # 8 days ago
        metadata = {"cached_at": str(old_timestamp)}
        mock_file_adapter.read_text.return_value = json.dumps(metadata)

        with (
            patch("time.time", return_value=1234567890),
            patch("tempfile.gettempdir", return_value="/tmp"),
        ):
            result = compiler.cleanup_old_caches(max_age_days=7)

        assert result is True

    def test_find_firmware_files(self, compiler, mock_file_adapter):
        """Test _find_firmware_files method."""
        output_dir = Path("/output")

        # Mock file structure
        def check_exists_side_effect(path):
            # Only main directory and file exist, no zephyr subdirs
            return str(path) in ["/output", "/output/main.uf2"]

        def is_dir_side_effect(path):
            # Only output dir is a directory
            return str(path) == "/output"

        mock_file_adapter.check_exists.side_effect = check_exists_side_effect
        mock_file_adapter.is_dir.side_effect = is_dir_side_effect
        mock_file_adapter.list_files.side_effect = [
            [Path("/output/main.uf2")],  # Base directory
            [],  # Subdirectories
        ]
        mock_file_adapter.list_directory.return_value = [
            Path("/output/build"),
            Path("/output/subdir"),
        ]

        firmware_files, output_files = compiler._find_firmware_files(output_dir)

        assert len(firmware_files) == 1
        assert firmware_files[0] == Path("/output/main.uf2")
        assert isinstance(output_files, FirmwareOutputFiles)
        assert output_files.main_uf2 == Path("/output/main.uf2")

    def test_find_firmware_files_west_structure(self, compiler, mock_file_adapter):
        """Test _find_firmware_files with west build structure."""
        output_dir = Path("/output")

        # Mock west build structure
        mock_file_adapter.check_exists.side_effect = lambda path: str(path) in [
            "/output",
            "/output/build",
            "/output/build/left",
            "/output/build/left/zephyr",
            "/output/build/left/zephyr/zmk.uf2",
        ]
        mock_file_adapter.is_dir.side_effect = lambda path: str(path) in [
            "/output",
            "/output/build",
            "/output/build/left",
            "/output/build/left/zephyr",
        ]

        def mock_list_files(directory, pattern):
            if (
                str(directory) == "/output"
                and pattern == "*.uf2"
                or str(directory) == "/output/subdir"
                and pattern == "*.uf2"
            ):
                return []
            return []

        def mock_list_directory(directory):
            if str(directory) == "/output":
                return [Path("/output/build"), Path("/output/subdir")]
            elif str(directory) == "/output/build":
                return [Path("/output/build/left")]
            return []

        mock_file_adapter.list_files.side_effect = mock_list_files
        mock_file_adapter.list_directory.side_effect = mock_list_directory

        firmware_files, output_files = compiler._find_firmware_files(output_dir)

        assert len(firmware_files) == 1
        assert firmware_files[0] == Path("/output/build/left/zephyr/zmk.uf2")

    def test_prepare_west_environment(self, compiler, complete_config):
        """Test _prepare_west_environment method."""
        env = compiler._prepare_west_environment(complete_config)

        assert "ZEPHYR_TOOLCHAIN_VARIANT" in env
        assert env["ZEPHYR_TOOLCHAIN_VARIANT"] == "zephyr"
        assert "WEST_WORKSPACE" in env
        assert env["WEST_WORKSPACE"] == "/zmk-workspace"
        assert "ZMK_CONFIG" in env
        assert "JOBS" in env

    def test_prepare_cmake_environment(self, compiler):
        """Test _prepare_cmake_environment method."""
        config = GenericDockerCompileConfig(
            build_strategy="cmake",
            environment_template={"CC": "clang"},
        )

        env = compiler._prepare_cmake_environment(config)

        assert env["CMAKE_BUILD_TYPE"] == "Release"
        assert env["CC"] == "clang"
        assert "JOBS" in env

    def test_prepare_west_volumes(self, compiler, complete_config):
        """Test _prepare_west_volumes method."""
        volumes = compiler._prepare_west_volumes(
            Path("/keymap.keymap"),
            Path("/config.conf"),
            Path("/output"),
            complete_config,
        )

        assert len(volumes) > 0
        # Should have output directory mapping
        assert any("/build" in str(vol[1]) for vol in volumes)

    def test_prepare_cmake_volumes(self, compiler):
        """Test _prepare_cmake_volumes method."""
        volumes = compiler._prepare_cmake_volumes(
            Path("/keymap.keymap"),
            Path("/config.conf"),
            Path("/output"),
        )

        assert len(volumes) == 3  # output, keymap, config
        assert any("/build" in str(vol[1]) for vol in volumes)

    def test_validate_input_files_success(self, compiler, mock_file_adapter):
        """Test _validate_input_files with valid files."""
        mock_file_adapter.check_exists.return_value = True
        mock_file_adapter.is_file.return_value = True

        result = BuildResult(success=True)
        is_valid = compiler._validate_input_files(
            Path("/keymap.keymap"),
            Path("/config.conf"),
            result,
        )

        assert is_valid is True
        assert result.success is True

    def test_validate_input_files_missing_keymap(self, compiler, mock_file_adapter):
        """Test _validate_input_files with missing keymap."""

        def mock_check_exists(path):
            return str(path) != "/keymap.keymap"

        mock_file_adapter.check_exists.side_effect = mock_check_exists
        mock_file_adapter.is_file.return_value = True

        result = BuildResult(success=True)
        is_valid = compiler._validate_input_files(
            Path("/keymap.keymap"),
            Path("/config.conf"),
            result,
        )

        assert is_valid is False
        assert result.success is False
        assert "Keymap file not found" in result.errors[0]

    def test_execute_build_strategy(self, compiler):
        """Test execute_build_strategy method."""
        result = compiler.execute_build_strategy("west", ["west build"])

        assert result.success is True

    def test_create_default_middleware(self):
        """Test _create_default_middleware static method."""
        middleware = GenericDockerCompiler._create_default_middleware()

        assert middleware is not None
        # Test that it can process lines
        processed = middleware.process("test line", "stdout")
        assert processed == "test line"

    def test_validate_config_zmk_config_strategy(self, compiler):
        """Test config validation with zmk_config strategy."""
        config = GenericDockerCompileConfig(
            image="zmkfirmware/zmk-build-arm:stable", build_strategy="zmk_config"
        )
        assert compiler.validate_config(config) is True

    def test_initialize_workspace_zmk_config(self, compiler, zmk_config_repo_config):
        """Test initialize_workspace with zmk_config configuration."""
        config = GenericDockerCompileConfig(
            build_strategy="zmk_config",
            zmk_config_repo=zmk_config_repo_config,
        )

        with patch.object(
            compiler, "manage_zmk_config_repo", return_value=True
        ) as mock_manage:
            result = compiler.initialize_workspace(config)

            assert result is True
            mock_manage.assert_called_once_with(zmk_config_repo_config)

    def test_manage_zmk_config_repo(
        self, compiler, mock_docker_adapter, zmk_config_repo_config
    ):
        """Test manage_zmk_config_repo method."""
        mock_docker_adapter.run_container.return_value = (
            0,
            ["Config repo init successful"],
            [],
        )

        result = compiler.manage_zmk_config_repo(zmk_config_repo_config)

        assert result is True
        mock_docker_adapter.run_container.assert_called()

    def test_manage_zmk_config_repo_failure(
        self, compiler, mock_docker_adapter, zmk_config_repo_config
    ):
        """Test manage_zmk_config_repo with command failure."""
        mock_docker_adapter.run_container.return_value = (
            1,
            [],
            ["Config repo init failed"],
        )

        result = compiler.manage_zmk_config_repo(zmk_config_repo_config)

        assert result is False

    def test_parse_build_yaml_success(self, compiler, mock_file_adapter):
        """Test parse_build_yaml with valid YAML."""
        mock_file_adapter.check_exists.return_value = True
        mock_file_adapter.read_text.return_value = """
board: ["nice_nano_v2"]
shield: ["corne_left", "corne_right"]
include:
  - board: nice_nano_v2
    shield: corne_left
    cmake-args: ["-DEXTRA_CONFIG=left"]
    artifact-name: corne_left
  - board: nice_nano_v2
    shield: corne_right
    cmake-args: ["-DEXTRA_CONFIG=right"]
    artifact-name: corne_right
"""

        result = compiler.parse_build_yaml(Path("/build.yaml"))

        assert isinstance(result, BuildYamlConfig)
        assert result.board == ["nice_nano_v2"]
        assert result.shield == ["corne_left", "corne_right"]
        assert len(result.include) == 2
        assert result.include[0].board == "nice_nano_v2"
        assert result.include[0].shield == "corne_left"
        assert result.include[0].cmake_args == ["-DEXTRA_CONFIG=left"]
        assert result.include[0].artifact_name == "corne_left"

    def test_parse_build_yaml_missing_file(self, compiler, mock_file_adapter):
        """Test parse_build_yaml with missing file."""
        mock_file_adapter.check_exists.return_value = False

        result = compiler.parse_build_yaml(Path("/missing.yaml"))

        assert isinstance(result, BuildYamlConfig)
        assert result.board == []
        assert result.shield == []
        assert result.include == []

    def test_parse_build_yaml_invalid_format(self, compiler, mock_file_adapter):
        """Test parse_build_yaml with invalid YAML format."""
        mock_file_adapter.check_exists.return_value = True
        mock_file_adapter.read_text.return_value = "invalid yaml: [unclosed"

        result = compiler.parse_build_yaml(Path("/invalid.yaml"))

        assert isinstance(result, BuildYamlConfig)
        assert result.board == []
        assert result.shield == []
        assert result.include == []

    def test_compile_zmk_config_strategy_success(
        self,
        compiler,
        mock_docker_adapter,
        mock_file_adapter,
        zmk_config_complete_config,
    ):
        """Test successful zmk_config strategy compilation."""
        # Mock successful Docker run
        mock_docker_adapter.run_container.return_value = (0, ["Build completed"], [])

        # Mock finding firmware files
        mock_file_adapter.list_files.return_value = [Path("/output/firmware.uf2")]
        mock_file_adapter.list_directory.return_value = []

        # Mock build.yaml parsing
        with patch.object(compiler, "parse_build_yaml") as mock_parse:
            mock_parse.return_value = BuildYamlConfig(
                include=[
                    BuildTargetConfig(
                        board="nice_nano_v2",
                        shield="corne_left",
                        artifact_name="corne_left",
                    )
                ]
            )

            # Mock workspace initialization
            with patch.object(
                compiler, "_initialize_zmk_config_workspace", return_value=True
            ):
                result = compiler.compile(
                    Path("/keymap.keymap"),
                    Path("/config.conf"),
                    Path("/output"),
                    zmk_config_complete_config,
                )

        assert result.success is True
        assert len(result.messages) > 0
        assert any("compilation completed" in msg.lower() for msg in result.messages)

    def test_compile_zmk_config_strategy_missing_config(self, compiler):
        """Test zmk_config strategy compilation with missing config repository."""
        config = GenericDockerCompileConfig(
            image="zmkfirmware/zmk-build-arm:stable",
            build_strategy="zmk_config",
            zmk_config_repo=None,  # Missing config repo
        )

        result = compiler.compile(
            Path("/keymap.keymap"),
            Path("/config.conf"),
            Path("/output"),
            config,
        )

        assert result.success is False
        assert "ZMK config repository configuration is required" in result.errors[0]

    def test_prepare_zmk_config_environment(self, compiler, zmk_config_complete_config):
        """Test _prepare_zmk_config_environment method."""
        env = compiler._prepare_zmk_config_environment(
            zmk_config_complete_config, zmk_config_complete_config.zmk_config_repo
        )

        assert "ZEPHYR_TOOLCHAIN_VARIANT" in env
        assert env["ZEPHYR_TOOLCHAIN_VARIANT"] == "zephyr"
        assert "WEST_WORKSPACE" in env
        assert env["WEST_WORKSPACE"] == "/zmk-config-workspace"
        assert "ZMK_CONFIG" in env
        assert env["ZMK_CONFIG"] == "/zmk-config-workspace/config"
        assert "CONFIG_REPO_URL" in env
        assert "JOBS" in env

    def test_prepare_zmk_config_volumes(self, compiler, zmk_config_complete_config):
        """Test _prepare_zmk_config_volumes method."""
        volumes = compiler._prepare_zmk_config_volumes(
            Path("/keymap.keymap"),
            Path("/config.conf"),
            Path("/output"),
            zmk_config_complete_config,
            zmk_config_complete_config.zmk_config_repo,
        )

        assert len(volumes) > 0
        # Should have output directory mapping
        assert any("/build" in str(vol[1]) for vol in volumes)
        # Should have keymap and config file mappings
        assert any("keymap.keymap" in str(vol[1]) for vol in volumes)
        assert any("config.conf" in str(vol[1]) for vol in volumes)


class TestGenericDockerCompilerFactory:
    """Tests for create_generic_docker_compiler factory function."""

    def test_create_with_defaults(self):
        """Test factory function with default parameters."""
        with (
            patch(
                "glovebox.firmware.compile.generic_docker_compiler.create_docker_adapter"
            ) as mock_docker,
            patch(
                "glovebox.firmware.compile.generic_docker_compiler.create_file_adapter"
            ) as mock_file,
        ):
            mock_docker.return_value = Mock()
            mock_file.return_value = Mock()

            compiler = create_generic_docker_compiler()

            assert isinstance(compiler, GenericDockerCompiler)
            mock_docker.assert_called_once()
            mock_file.assert_called_once()

    def test_create_with_custom_adapters(self):
        """Test factory function with custom adapters."""
        docker_adapter = Mock(spec=DockerAdapterProtocol)
        file_adapter = Mock(spec=FileAdapterProtocol)
        middleware = Mock()

        compiler = create_generic_docker_compiler(
            docker_adapter=docker_adapter,
            file_adapter=file_adapter,
            output_middleware=middleware,
        )

        assert isinstance(compiler, GenericDockerCompiler)
        assert compiler.docker_adapter is docker_adapter
        assert compiler.file_adapter is file_adapter
        assert compiler.output_middleware is middleware


class TestGenericDockerCompilerIntegration:
    """Integration tests for GenericDockerCompiler."""

    def test_end_to_end_west_build(self):
        """Test end-to-end west build workflow."""
        # Create temporary files
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            keymap_file = temp_path / "keymap.keymap"
            config_file = temp_path / "config.conf"
            output_dir = temp_path / "output"

            keymap_file.write_text("// Test keymap")
            config_file.write_text("# Test config")
            output_dir.mkdir()

            # Mock successful Docker build
            with (
                patch(
                    "glovebox.firmware.compile.generic_docker_compiler.create_docker_adapter"
                ) as mock_docker_factory,
                patch(
                    "glovebox.firmware.compile.generic_docker_compiler.create_file_adapter"
                ) as mock_file_factory,
            ):
                mock_docker = Mock()
                mock_docker.is_available.return_value = True
                mock_docker.run_container.return_value = (0, ["Build successful"], [])
                mock_docker_factory.return_value = mock_docker

                mock_file = Mock()
                mock_file.check_exists.return_value = True
                mock_file.is_file.return_value = True
                mock_file.is_dir.return_value = True
                mock_file.read_text.return_value = "mock content"
                mock_file.write_text.return_value = None
                mock_file.create_directory.return_value = None
                mock_file.list_files.return_value = [output_dir / "zmk.uf2"]
                mock_file.list_directory.return_value = []
                mock_file_factory.return_value = mock_file

                compiler = GenericDockerCompiler()
                config = GenericDockerCompileConfig(
                    image="zmkfirmware/zmk-build-arm:stable",
                    build_strategy="west",
                    west_workspace=WestWorkspaceConfig(),
                )

                result = compiler.compile(keymap_file, config_file, output_dir, config)

                assert result.success is True
                mock_docker.run_container.assert_called()

    def test_workspace_caching_workflow(self):
        """Test workspace caching workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "workspace"
            workspace_path.mkdir()

            with patch(
                "glovebox.firmware.compile.generic_docker_compiler.create_file_adapter"
            ) as mock_file_factory:
                mock_file = Mock()
                mock_file.check_exists.return_value = True
                mock_file.is_dir.return_value = True
                mock_file.create_directory.return_value = None
                mock_file.write_text.return_value = None
                mock_file.read_text.return_value = "mock content"
                mock_file_factory.return_value = mock_file

                compiler = GenericDockerCompiler(file_adapter=mock_file)

                # Test caching
                result = compiler.cache_workspace(workspace_path)
                assert result is True

                # Test cache validation
                config = GenericDockerCompileConfig()
                is_valid = compiler.is_cache_valid(workspace_path, config)
                # Will be False due to missing metadata in mock, but method runs
                assert is_valid is False
