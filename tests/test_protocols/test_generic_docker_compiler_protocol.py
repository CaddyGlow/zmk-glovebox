"""Tests for GenericDockerCompilerProtocol."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from glovebox.config.compile_methods import (
    CompilationConfig,
    WestWorkspaceConfig,
)
from glovebox.firmware.models import BuildResult
from glovebox.protocols.compile_protocols import GenericDockerCompilerProtocol


class TestGenericDockerCompilerProtocol:
    """Tests for GenericDockerCompilerProtocol interface."""

    def test_protocol_is_runtime_checkable(self):
        """Test that GenericDockerCompilerProtocol is runtime checkable."""
        assert hasattr(GenericDockerCompilerProtocol, "__instancecheck__")

        # Create a mock that implements the protocol
        mock_compiler = Mock()
        mock_compiler.compile = Mock(return_value=BuildResult(success=True))
        mock_compiler.check_available = Mock(return_value=True)
        mock_compiler.validate_config = Mock(return_value=True)
        mock_compiler.build_image = Mock(return_value=BuildResult(success=True))
        mock_compiler.get_available_strategies = Mock(
            return_value=["west", "zmk_config"]
        )

        # Runtime check should work
        assert isinstance(mock_compiler, GenericDockerCompilerProtocol)

    def test_protocol_methods_required(self):
        """Test that protocol methods are properly defined."""
        # Check that protocol has the expected methods
        assert hasattr(GenericDockerCompilerProtocol, "compile")
        assert hasattr(GenericDockerCompilerProtocol, "check_available")
        assert hasattr(GenericDockerCompilerProtocol, "validate_config")
        assert hasattr(GenericDockerCompilerProtocol, "build_image")
        assert hasattr(GenericDockerCompilerProtocol, "get_available_strategies")

    def test_incomplete_implementation_fails_check(self):
        """Test that incomplete implementations fail runtime check."""
        # Mock with missing methods
        incomplete_mock = Mock()
        incomplete_mock.compile = Mock()
        incomplete_mock.check_available = Mock()
        # Missing other required methods

        # Should not pass isinstance check
        assert not isinstance(incomplete_mock, GenericDockerCompilerProtocol)

    def test_complete_implementation_passes_check(self):
        """Test that complete implementations pass runtime check."""

        class CompleteGenericCompiler:
            def compile(
                self,
                keymap_file: Path,
                config_file: Path,
                output_dir: Path,
                config: CompilationConfig,
            ) -> BuildResult:
                return BuildResult(success=True)

            def check_available(self) -> bool:
                return True

            def validate_config(self, config: CompilationConfig) -> bool:
                return True

            def build_image(self, config: CompilationConfig) -> BuildResult:
                return BuildResult(success=True)

            def get_available_strategies(self) -> list[str]:
                return ["west", "zmk_config"]

        compiler = CompleteGenericCompiler()
        assert isinstance(compiler, GenericDockerCompilerProtocol)

    def test_method_signatures(self):
        """Test that protocol method signatures are correct."""

        class TestGenericCompiler:
            def compile(
                self,
                keymap_file: Path,
                config_file: Path,
                output_dir: Path,
                config: CompilationConfig,
            ) -> BuildResult:
                return BuildResult(success=True)

            def check_available(self) -> bool:
                return True

            def validate_config(self, config: CompilationConfig) -> bool:
                return isinstance(config, CompilationConfig)

            def build_image(self, config: CompilationConfig) -> BuildResult:
                return BuildResult(success=True, messages=["Image built"])

            def get_available_strategies(self) -> list[str]:
                return ["west", "zmk_config"]

        compiler = TestGenericCompiler()
        assert isinstance(compiler, GenericDockerCompilerProtocol)

        # Test method calls with proper types
        config = CompilationConfig(
            image="test:latest",
            build_strategy="west",
        )

        result = compiler.compile(
            keymap_file=Path("test.keymap"),
            config_file=Path("test.conf"),
            output_dir=Path("output"),
            config=config,
        )
        assert isinstance(result, BuildResult)
        assert result.success is True

        assert compiler.check_available() is True
        assert compiler.validate_config(config) is True

        build_result = compiler.build_image(config)
        assert isinstance(build_result, BuildResult)
        assert "Image built" in build_result.messages

        strategies = compiler.get_available_strategies()
        assert isinstance(strategies, list)
        assert "west" in strategies
        assert "zmk_config" in strategies
