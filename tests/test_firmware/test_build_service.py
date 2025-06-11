"""Tests for refactored BuildService using multi-method architecture."""

from pathlib import Path
from unittest.mock import Mock, patch

from glovebox.config.compile_methods import CompilationConfig, DockerCompileConfig
from glovebox.config.profile import KeyboardProfile
from glovebox.firmware.build_service import BuildService, create_build_service
from glovebox.firmware.models import BuildResult, FirmwareOutputFiles
from glovebox.firmware.options import BuildServiceCompileOpts
from glovebox.protocols.compile_protocols import CompilerProtocol


class TestBuildService:
    """Tests for the refactored BuildService."""

    def test_service_initialization(self):
        """Test BuildService initialization."""
        service = BuildService(loglevel="DEBUG")

        assert service.service_name == "BuildService"
        assert service.service_version == "2.0.0"
        assert service.loglevel == "DEBUG"

    def test_service_factory(self):
        """Test BuildService factory function."""
        service = create_build_service(loglevel="INFO")

        assert isinstance(service, BuildService)
        assert service.loglevel == "INFO"

    @patch("glovebox.firmware.build_service.select_compiler_with_fallback")
    def test_compile_success(self, mock_select_compiler):
        """Test successful compilation."""
        # Mock compiler
        mock_compiler = Mock(spec=CompilerProtocol)
        mock_compiler.compile.return_value = BuildResult(
            success=True, messages=["Compilation successful"]
        )
        mock_select_compiler.return_value = mock_compiler

        # Create service and options
        service = BuildService()
        opts = BuildServiceCompileOpts(
            keymap_path=Path("test.keymap"),
            kconfig_path=Path("test.conf"),
            output_dir=Path("output"),
        )

        result = service.compile(opts)

        assert result.success is True
        assert "Compilation successful" in result.messages
        mock_select_compiler.assert_called_once()
        mock_compiler.compile.assert_called_once()

    @patch("glovebox.firmware.build_service.select_compiler_with_fallback")
    def test_compile_failure(self, mock_select_compiler):
        """Test compilation failure."""
        # Mock compiler that fails
        mock_compiler = Mock(spec=CompilerProtocol)
        mock_compiler.compile.return_value = BuildResult(
            success=False, errors=["Compilation failed"]
        )
        mock_select_compiler.return_value = mock_compiler

        service = BuildService()
        opts = BuildServiceCompileOpts(
            keymap_path=Path("test.keymap"),
            kconfig_path=Path("test.conf"),
            output_dir=Path("output"),
        )

        result = service.compile(opts)

        assert result.success is False
        assert "Compilation failed" in result.errors

    @patch("glovebox.firmware.build_service.select_compiler_with_fallback")
    def test_compile_with_profile(self, mock_select_compiler):
        """Test compilation with keyboard profile."""
        # Mock compiler
        mock_compiler = Mock(spec=CompilerProtocol)
        mock_compiler.compile.return_value = BuildResult(success=True)
        mock_select_compiler.return_value = mock_compiler

        # Mock profile with compile methods
        mock_profile = Mock(spec=KeyboardProfile)
        mock_keyboard_config = Mock()
        mock_keyboard_config.compile_methods = [
            DockerCompileConfig(image="custom:latest")
        ]
        mock_profile.keyboard_config = mock_keyboard_config

        service = BuildService()
        opts = BuildServiceCompileOpts(
            keymap_path=Path("test.keymap"),
            kconfig_path=Path("test.conf"),
            output_dir=Path("output"),
        )

        result = service.compile(opts, keyboard_profile=mock_profile)

        assert result.success is True
        mock_select_compiler.assert_called_once()

        # Verify the profile's compile methods were used
        call_args = mock_select_compiler.call_args[0]
        assert len(call_args[0]) == 1  # One config from profile
        assert isinstance(call_args[0][0], DockerCompileConfig)

    @patch("glovebox.firmware.build_service.select_compiler_with_fallback")
    def test_compile_without_profile_uses_defaults(self, mock_select_compiler):
        """Test compilation without profile uses default configuration."""
        # Mock compiler
        mock_compiler = Mock(spec=CompilerProtocol)
        mock_compiler.compile.return_value = BuildResult(success=True)
        mock_select_compiler.return_value = mock_compiler

        service = BuildService()
        opts = BuildServiceCompileOpts(
            keymap_path=Path("test.keymap"),
            kconfig_path=Path("test.conf"),
            output_dir=Path("output"),
            repo="custom/zmk",
            branch="feature",
        )

        result = service.compile(opts, keyboard_profile=None)

        assert result.success is True

        # Verify default configuration was created
        call_args = mock_select_compiler.call_args[0]
        assert len(call_args[0]) == 1  # One default config
        config = call_args[0][0]
        assert isinstance(config, DockerCompileConfig)
        assert config.repository == "custom/zmk"
        assert config.branch == "feature"

    @patch("glovebox.firmware.build_service.select_compiler_with_fallback")
    def test_compile_from_files_success(self, mock_select_compiler):
        """Test compile_from_files method."""
        # Mock compiler
        mock_compiler = Mock(spec=CompilerProtocol)
        mock_compiler.compile.return_value = BuildResult(success=True)
        mock_select_compiler.return_value = mock_compiler

        service = BuildService()

        result = service.compile_from_files(
            keymap_file_path=Path("test.keymap"),
            kconfig_file_path=Path("test.conf"),
            output_dir=Path("output"),
            branch="develop",
            jobs=8,
        )

        assert result.success is True

        # Verify options were passed correctly
        call_args = mock_select_compiler.call_args[0]
        config = call_args[0][0]
        assert config.branch == "develop"
        assert config.jobs == 8

    @patch("glovebox.firmware.build_service.select_compiler_with_fallback")
    def test_compile_exception_handling(self, mock_select_compiler):
        """Test exception handling in compile method."""
        # Mock select_compiler to raise exception
        mock_select_compiler.side_effect = Exception("Selection failed")

        service = BuildService()
        opts = BuildServiceCompileOpts(
            keymap_path=Path("test.keymap"),
            kconfig_path=Path("test.conf"),
            output_dir=Path("output"),
        )

        result = service.compile(opts)

        assert result.success is False
        assert "Compilation failed" in result.errors[0]
        assert "Selection failed" in result.errors[0]

    def test_get_compile_method_configs_with_profile(self):
        """Test _get_compile_method_configs with profile."""
        service = BuildService()

        # Mock profile with compile methods
        mock_profile = Mock(spec=KeyboardProfile)
        mock_keyboard_config = Mock()
        mock_keyboard_config.compile_methods = [
            DockerCompileConfig(image="profile:latest"),
            CompilationConfig(strategy="zmk_config"),
        ]
        mock_profile.keyboard_config = mock_keyboard_config

        opts = BuildServiceCompileOpts(
            keymap_path=Path("test.keymap"),
            kconfig_path=Path("test.conf"),
            output_dir=Path("output"),
        )

        configs = service._get_compile_method_configs(mock_profile, opts)

        assert len(configs) == 2
        assert isinstance(configs[0], DockerCompileConfig)
        assert configs[0].image == "profile:latest"
        assert isinstance(configs[1], CompilationConfig)

    def test_get_compile_method_configs_without_profile(self):
        """Test _get_compile_method_configs without profile."""
        service = BuildService()

        opts = BuildServiceCompileOpts(
            keymap_path=Path("test.keymap"),
            kconfig_path=Path("test.conf"),
            output_dir=Path("output"),
            repo="test/repo",
            branch="test-branch",
            jobs=4,
        )

        configs = service._get_compile_method_configs(None, opts)

        assert len(configs) == 1
        config = configs[0]
        assert isinstance(config, DockerCompileConfig)
        assert config.repository == "test/repo"
        assert config.branch == "test-branch"
        assert config.jobs == 4


class TestBuildServiceIntegration:
    """Integration tests for BuildService with method selection."""

    @patch("glovebox.firmware.build_service.select_compiler_with_fallback")
    def test_full_compilation_workflow(self, mock_select_compiler):
        """Test full compilation workflow with realistic data."""
        # Create a realistic compiler mock
        mock_compiler = Mock(spec=CompilerProtocol)
        mock_compiler.compile.return_value = BuildResult(
            success=True,
            messages=["Docker build started", "Build completed successfully"],
            output_files=FirmwareOutputFiles(
                output_dir=Path("output"), main_uf2=Path("output/firmware.uf2")
            ),
        )
        mock_select_compiler.return_value = mock_compiler

        service = BuildService(loglevel="DEBUG")

        # Mock realistic profile
        mock_profile = Mock(spec=KeyboardProfile)
        mock_keyboard_config = Mock()
        mock_keyboard_config.compile_methods = [
            DockerCompileConfig(
                image="moergo-zmk-build:latest",
                repository="moergo-sc/zmk",
                branch="main",
                jobs=8,
            )
        ]
        mock_profile.keyboard_config = mock_keyboard_config

        result = service.compile_from_files(
            keymap_file_path=Path("glove80.keymap"),
            kconfig_file_path=Path("glove80.conf"),
            output_dir=Path("build/glove80"),
            keyboard_profile=mock_profile,
            verbose=True,
        )

        assert result.success is True
        assert "Build completed successfully" in result.messages
        assert result.output_files is not None

        # Verify compiler was called with correct parameters
        mock_compiler.compile.assert_called_once()
        call_args = mock_compiler.compile.call_args
        assert call_args[1]["keymap_file"] == Path("glove80.keymap")
        assert call_args[1]["config_file"] == Path("glove80.conf")
        assert call_args[1]["output_dir"] == Path("build/glove80")

    @patch("glovebox.firmware.build_service.select_compiler_with_fallback")
    def test_fallback_scenario(self, mock_select_compiler):
        """Test fallback scenario where primary method fails."""
        # Mock the selection to simulate fallback
        docker_compiler = Mock(spec=CompilerProtocol)
        docker_compiler.check_available.return_value = False

        local_compiler = Mock(spec=CompilerProtocol)
        local_compiler.check_available.return_value = True
        local_compiler.compile.return_value = BuildResult(
            success=True, messages=["Local compilation successful"]
        )

        # Mock select_compiler to return the fallback compiler
        mock_select_compiler.return_value = local_compiler

        service = BuildService()

        # Profile with fallback methods
        mock_profile = Mock(spec=KeyboardProfile)
        mock_keyboard_config = Mock()
        mock_keyboard_config.compile_methods = [
            DockerCompileConfig(),  # Primary (would fail)
            CompilationConfig(strategy="west"),  # Fallback (succeeds)
        ]
        mock_profile.keyboard_config = mock_keyboard_config

        opts = BuildServiceCompileOpts(
            keymap_path=Path("test.keymap"),
            kconfig_path=Path("test.conf"),
            output_dir=Path("output"),
        )

        result = service.compile(opts, keyboard_profile=mock_profile)

        assert result.success is True
        assert "Local compilation successful" in result.messages

        # Verify both configs were passed to selector
        call_args = mock_select_compiler.call_args[0]
        assert len(call_args[0]) == 2

    @patch("glovebox.firmware.build_service.select_compiler_with_fallback")
    def test_error_recovery(self, mock_select_compiler):
        """Test error recovery and graceful degradation."""
        # Mock compiler that fails compilation but succeeds in selection
        mock_compiler = Mock(spec=CompilerProtocol)
        mock_compiler.compile.return_value = BuildResult(
            success=False, errors=["Keymap syntax error", "Build failed"]
        )
        mock_select_compiler.return_value = mock_compiler

        service = BuildService()
        opts = BuildServiceCompileOpts(
            keymap_path=Path("invalid.keymap"),
            kconfig_path=Path("invalid.conf"),
            output_dir=Path("output"),
        )

        result = service.compile(opts)

        assert result.success is False
        assert "Keymap syntax error" in result.errors
        assert "Build failed" in result.errors

        # Service should handle the failure gracefully
        assert len(result.errors) >= 2
