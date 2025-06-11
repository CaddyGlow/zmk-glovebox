"""Tests for GenericDockerCompiler facade."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.config.compile_methods import CompilationConfig
from glovebox.firmware.compile.generic_docker_compiler import (
    GenericDockerCompiler,
    create_generic_docker_compiler,
)
from glovebox.firmware.models import BuildResult
from glovebox.protocols import DockerAdapterProtocol, FileAdapterProtocol


class TestGenericDockerCompiler:
    """Tests for GenericDockerCompiler facade functionality."""

    @pytest.fixture
    def mock_docker_adapter(self):
        """Create mock docker adapter."""
        adapter = Mock(spec=DockerAdapterProtocol)
        adapter.is_available.return_value = True
        return adapter

    @pytest.fixture
    def mock_file_adapter(self):
        """Create mock file adapter."""
        adapter = Mock(spec=FileAdapterProtocol)
        adapter.check_exists.return_value = True
        return adapter

    @pytest.fixture
    def mock_compilation_coordinator(self):
        """Create mock compilation coordinator."""
        coordinator = Mock()
        coordinator.compile.return_value = BuildResult(success=True)
        coordinator.get_available_strategies.return_value = [
            "west",
            "zmk_config",
            "cmake",
        ]
        return coordinator

    @pytest.fixture
    def compiler(
        self, mock_docker_adapter, mock_file_adapter, mock_compilation_coordinator
    ):
        """Create compiler instance with mocked dependencies."""
        with patch(
            "glovebox.firmware.compile.generic_docker_compiler.create_compilation_coordinator"
        ) as mock_coord_factory:
            mock_coord_factory.return_value = mock_compilation_coordinator
            return GenericDockerCompiler(
                docker_adapter=mock_docker_adapter,
                file_adapter=mock_file_adapter,
            )

    @pytest.fixture
    def basic_config(self):
        """Create basic valid configuration."""
        return CompilationConfig(
            image="zmkfirmware/zmk-build-arm:stable",
            build_strategy="west",
        )

    def test_initialization(self, mock_docker_adapter, mock_file_adapter):
        """Test GenericDockerCompiler initialization."""
        with patch(
            "glovebox.firmware.compile.generic_docker_compiler.create_compilation_coordinator"
        ):
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
            patch(
                "glovebox.firmware.compile.generic_docker_compiler.create_compilation_coordinator"
            ),
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
        config = CompilationConfig(image="", build_strategy="west")
        assert compiler.validate_config(config) is False

    def test_validate_config_invalid_strategy(self, compiler):
        """Test config validation with invalid build strategy."""
        config = CompilationConfig(
            image="test:latest", build_strategy="invalid_strategy"
        )
        assert compiler.validate_config(config) is False

    def test_validate_config_missing_strategy(self, compiler):
        """Test config validation with missing build strategy."""
        config = CompilationConfig(image="test:latest", build_strategy="")
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
        assert "not found" in result.errors[0]

    def test_compile_success(
        self, compiler, mock_compilation_coordinator, basic_config
    ):
        """Test successful compilation delegated to coordinator."""
        with tempfile.TemporaryDirectory() as temp_dir:
            keymap_file = Path(temp_dir) / "keymap.keymap"
            config_file = Path(temp_dir) / "config.conf"
            output_dir = Path(temp_dir) / "output"

            keymap_file.touch()
            config_file.touch()
            output_dir.mkdir()

            expected_result = BuildResult(success=True)
            mock_compilation_coordinator.compile.return_value = expected_result

            result = compiler.compile(
                keymap_file, config_file, output_dir, basic_config
            )

            assert result.success is True
            mock_compilation_coordinator.compile.assert_called_once_with(
                keymap_file, config_file, output_dir, basic_config, None
            )

    def test_compile_coordinator_failure(
        self, compiler, mock_compilation_coordinator, basic_config
    ):
        """Test compilation failure from coordinator."""
        with tempfile.TemporaryDirectory() as temp_dir:
            keymap_file = Path(temp_dir) / "keymap.keymap"
            config_file = Path(temp_dir) / "config.conf"
            output_dir = Path(temp_dir) / "output"

            keymap_file.touch()
            config_file.touch()
            output_dir.mkdir()

            expected_result = BuildResult(success=False)
            expected_result.add_error("Compilation failed")
            mock_compilation_coordinator.compile.return_value = expected_result

            result = compiler.compile(
                keymap_file, config_file, output_dir, basic_config
            )

            assert result.success is False
            assert "Compilation failed" in result.errors

    def test_get_available_strategies(self, compiler, mock_compilation_coordinator):
        """Test getting available strategies from coordinator."""
        expected_strategies = ["west", "zmk_config", "cmake"]
        mock_compilation_coordinator.get_available_strategies.return_value = (
            expected_strategies
        )

        strategies = compiler.get_available_strategies()

        assert strategies == expected_strategies
        mock_compilation_coordinator.get_available_strategies.assert_called_once()

    def test_create_generic_docker_compiler(self):
        """Test factory function."""
        with patch(
            "glovebox.firmware.compile.generic_docker_compiler.create_compilation_coordinator"
        ):
            compiler = create_generic_docker_compiler()
            assert isinstance(compiler, GenericDockerCompiler)

    def test_compile_exception_handling(
        self, compiler, mock_compilation_coordinator, basic_config
    ):
        """Test exception handling in compile method."""
        with tempfile.TemporaryDirectory() as temp_dir:
            keymap_file = Path(temp_dir) / "keymap.keymap"
            config_file = Path(temp_dir) / "config.conf"
            output_dir = Path(temp_dir) / "output"

            keymap_file.touch()
            config_file.touch()
            output_dir.mkdir()

            # Mock coordinator to raise exception
            mock_compilation_coordinator.compile.side_effect = Exception("Test error")

            result = compiler.compile(
                keymap_file, config_file, output_dir, basic_config
            )

            assert result.success is False
            assert "Unexpected error: Test error" in result.errors[0]
