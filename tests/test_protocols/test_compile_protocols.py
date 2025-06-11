"""Tests for compile protocol implementations."""

from pathlib import Path
from typing import Protocol, runtime_checkable
from unittest.mock import Mock

import pytest

from glovebox.config.compile_methods import (
    CompileMethodConfig,
    DockerCompileConfig,
    CompilationConfig,
    WestWorkspaceConfig,
)
from glovebox.firmware.models import BuildResult
from glovebox.protocols.compile_protocols import (
    CompilerProtocol,
    GenericDockerCompilerProtocol,
)


class TestCompilerProtocol:
    """Tests for CompilerProtocol interface."""

    def test_protocol_is_runtime_checkable(self):
        """Test that CompilerProtocol is runtime checkable."""
        assert hasattr(CompilerProtocol, "__instancecheck__")

        # Create a mock that implements the protocol
        mock_compiler = Mock()
        mock_compiler.compile = Mock(return_value=BuildResult(success=True))
        mock_compiler.check_available = Mock(return_value=True)
        mock_compiler.validate_config = Mock(return_value=True)

        # Runtime check should work
        assert isinstance(mock_compiler, CompilerProtocol)

    def test_protocol_methods_required(self):
        """Test that protocol methods are properly defined."""
        # Check that protocol has the expected methods
        assert hasattr(CompilerProtocol, "compile")
        assert hasattr(CompilerProtocol, "check_available")
        assert hasattr(CompilerProtocol, "validate_config")

    def test_incomplete_implementation_fails_check(self):
        """Test that incomplete implementations fail runtime check."""
        # Mock with missing methods
        incomplete_mock = Mock()
        incomplete_mock.compile = Mock()
        # Missing check_available and validate_config

        # Should not pass isinstance check
        assert not isinstance(incomplete_mock, CompilerProtocol)

    def test_method_signatures(self):
        """Test that protocol method signatures are correct."""

        # Create a proper implementation
        class TestCompiler:
            def compile(
                self,
                keymap_file: Path,
                config_file: Path,
                output_dir: Path,
                config: CompileMethodConfig,
            ) -> BuildResult:
                return BuildResult(success=True)

            def check_available(self) -> bool:
                return True

            def validate_config(self, config: CompileMethodConfig) -> bool:
                return True

        compiler = TestCompiler()
        assert isinstance(compiler, CompilerProtocol)

        # Test method calls
        result = compiler.compile(
            keymap_file=Path("test.keymap"),
            config_file=Path("test.conf"),
            output_dir=Path("output"),
            config=DockerCompileConfig(),
        )
        assert isinstance(result, BuildResult)

        assert compiler.check_available() is True
        assert compiler.validate_config(DockerCompileConfig()) is True


class TestProtocolImplementation:
    """Tests for actual protocol implementation compliance."""

    def test_valid_compiler_implementation(self):
        """Test a valid compiler implementation."""

        class ValidCompiler:
            def __init__(self):
                self.available = True

            def compile(
                self,
                keymap_file: Path,
                config_file: Path,
                output_dir: Path,
                config: CompileMethodConfig,
            ) -> BuildResult:
                if not self.check_available():
                    return BuildResult(success=False, errors=["Compiler not available"])

                if not self.validate_config(config):
                    return BuildResult(success=False, errors=["Invalid configuration"])

                return BuildResult(success=True, messages=["Compilation successful"])

            def check_available(self) -> bool:
                return self.available

            def validate_config(self, config: CompileMethodConfig) -> bool:
                return isinstance(config, CompileMethodConfig)

        compiler = ValidCompiler()
        assert isinstance(compiler, CompilerProtocol)

        # Test successful compilation
        result = compiler.compile(
            Path("test.keymap"),
            Path("test.conf"),
            Path("output"),
            DockerCompileConfig(),
        )
        assert result.success is True
        assert "Compilation successful" in result.messages

        # Test availability check
        assert compiler.check_available() is True

        # Test config validation
        assert compiler.validate_config(DockerCompileConfig()) is True

    def test_compiler_with_failure_states(self):
        """Test compiler implementation with various failure states."""

        class FailingCompiler:
            def __init__(self, available: bool = True, valid_config: bool = True):
                self.available = available
                self.valid_config = valid_config

            def compile(
                self,
                keymap_file: Path,
                config_file: Path,
                output_dir: Path,
                config: CompileMethodConfig,
            ) -> BuildResult:
                if not self.check_available():
                    return BuildResult(success=False, errors=["Compiler not available"])

                if not self.validate_config(config):
                    return BuildResult(
                        success=False, errors=["Configuration validation failed"]
                    )

                # Simulate compilation failure
                return BuildResult(success=False, errors=["Compilation failed"])

            def check_available(self) -> bool:
                return self.available

            def validate_config(self, config: CompileMethodConfig) -> bool:
                return self.valid_config

        # Test unavailable compiler
        unavailable_compiler = FailingCompiler(available=False)
        assert isinstance(unavailable_compiler, CompilerProtocol)

        result = unavailable_compiler.compile(
            Path("test.keymap"),
            Path("test.conf"),
            Path("output"),
            DockerCompileConfig(),
        )
        assert result.success is False
        assert "Compiler not available" in result.errors

        # Test invalid config
        invalid_config_compiler = FailingCompiler(available=True, valid_config=False)
        result = invalid_config_compiler.compile(
            Path("test.keymap"),
            Path("test.conf"),
            Path("output"),
            DockerCompileConfig(),
        )
        assert result.success is False
        assert "Configuration validation failed" in result.errors

    def test_protocol_type_checking(self):
        """Test that protocol enforces proper type checking."""

        class TypedCompiler:
            def compile(
                self,
                keymap_file: Path,
                config_file: Path,
                output_dir: Path,
                config: CompileMethodConfig,
            ) -> BuildResult:
                # Verify input types
                assert isinstance(keymap_file, Path)
                assert isinstance(config_file, Path)
                assert isinstance(output_dir, Path)
                assert isinstance(config, CompileMethodConfig)

                return BuildResult(success=True)

            def check_available(self) -> bool:
                return True

            def validate_config(self, config: CompileMethodConfig) -> bool:
                return isinstance(config, CompileMethodConfig)

        compiler = TypedCompiler()
        assert isinstance(compiler, CompilerProtocol)

        # Test with correct types
        result = compiler.compile(
            Path("test.keymap"),
            Path("test.conf"),
            Path("output"),
            DockerCompileConfig(),
        )
        assert result.success is True


class TestProtocolExtensibility:
    """Tests for protocol extensibility and inheritance."""

    def test_protocol_subclassing(self):
        """Test that protocols can be extended."""

        @runtime_checkable
        class ExtendedCompilerProtocol(CompilerProtocol, Protocol):
            def get_version(self) -> str:
                """Get compiler version."""
                ...

            def get_build_info(self) -> dict[str, str]:
                """Get build information."""
                ...

        class ExtendedCompiler:
            def compile(
                self,
                keymap_file: Path,
                config_file: Path,
                output_dir: Path,
                config: CompileMethodConfig,
            ) -> BuildResult:
                return BuildResult(success=True)

            def check_available(self) -> bool:
                return True

            def validate_config(self, config: CompileMethodConfig) -> bool:
                return True

            def get_version(self) -> str:
                return "1.0.0"

            def get_build_info(self) -> dict[str, str]:
                return {"compiler": "test", "version": "1.0.0"}

        compiler = ExtendedCompiler()
        assert isinstance(compiler, CompilerProtocol)
        assert isinstance(compiler, ExtendedCompilerProtocol)

        assert compiler.get_version() == "1.0.0"
        assert compiler.get_build_info()["compiler"] == "test"

    def test_multiple_protocol_implementations(self):
        """Test that a class can implement multiple protocols."""

        @runtime_checkable
        class ConfigurableProtocol(Protocol):
            def configure(self, settings: dict[str, str]) -> bool:
                """Configure the implementation."""
                ...

        class MultiProtocolCompiler:
            def __init__(self):
                self.configured = False

            def compile(
                self,
                keymap_file: Path,
                config_file: Path,
                output_dir: Path,
                config: CompileMethodConfig,
            ) -> BuildResult:
                if not self.configured:
                    return BuildResult(success=False, errors=["Not configured"])
                return BuildResult(success=True)

            def check_available(self) -> bool:
                return True

            def validate_config(self, config: CompileMethodConfig) -> bool:
                return True

            def configure(self, settings: dict[str, str]) -> bool:
                self.configured = True
                return True

        compiler = MultiProtocolCompiler()
        assert isinstance(compiler, CompilerProtocol)
        assert isinstance(compiler, ConfigurableProtocol)

        # Test configuration
        assert compiler.configure({"setting": "value"}) is True

        result = compiler.compile(
            Path("test.keymap"),
            Path("test.conf"),
            Path("output"),
            DockerCompileConfig(),
        )
        assert result.success is True
