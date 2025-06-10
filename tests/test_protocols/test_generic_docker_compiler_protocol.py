"""Tests for GenericDockerCompilerProtocol."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from glovebox.config.compile_methods import (
    GenericDockerCompileConfig,
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
        mock_compiler.initialize_workspace = Mock(return_value=True)
        mock_compiler.execute_build_strategy = Mock(
            return_value=BuildResult(success=True)
        )
        mock_compiler.manage_west_workspace = Mock(return_value=True)
        mock_compiler.cache_workspace = Mock(return_value=True)

        # Runtime check should work
        assert isinstance(mock_compiler, GenericDockerCompilerProtocol)

    def test_protocol_methods_required(self):
        """Test that protocol methods are properly defined."""
        # Check that protocol has the expected methods
        assert hasattr(GenericDockerCompilerProtocol, "compile")
        assert hasattr(GenericDockerCompilerProtocol, "check_available")
        assert hasattr(GenericDockerCompilerProtocol, "validate_config")
        assert hasattr(GenericDockerCompilerProtocol, "build_image")
        assert hasattr(GenericDockerCompilerProtocol, "initialize_workspace")
        assert hasattr(GenericDockerCompilerProtocol, "execute_build_strategy")
        assert hasattr(GenericDockerCompilerProtocol, "manage_west_workspace")
        assert hasattr(GenericDockerCompilerProtocol, "cache_workspace")

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
                config: GenericDockerCompileConfig,
            ) -> BuildResult:
                return BuildResult(success=True)

            def check_available(self) -> bool:
                return True

            def validate_config(self, config: GenericDockerCompileConfig) -> bool:
                return True

            def build_image(self, config: GenericDockerCompileConfig) -> BuildResult:
                return BuildResult(success=True)

            def initialize_workspace(self, config: GenericDockerCompileConfig) -> bool:
                return True

            def execute_build_strategy(
                self, strategy: str, commands: list[str]
            ) -> BuildResult:
                return BuildResult(success=True)

            def manage_west_workspace(
                self, workspace_config: WestWorkspaceConfig
            ) -> bool:
                return True

            def cache_workspace(self, workspace_path: Path) -> bool:
                return True

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
                config: GenericDockerCompileConfig,
            ) -> BuildResult:
                return BuildResult(success=True)

            def check_available(self) -> bool:
                return True

            def validate_config(self, config: GenericDockerCompileConfig) -> bool:
                return isinstance(config, GenericDockerCompileConfig)

            def build_image(self, config: GenericDockerCompileConfig) -> BuildResult:
                return BuildResult(success=True, messages=["Image built"])

            def initialize_workspace(self, config: GenericDockerCompileConfig) -> bool:
                return True

            def execute_build_strategy(
                self, strategy: str, commands: list[str]
            ) -> BuildResult:
                return BuildResult(
                    success=True, messages=[f"Executed {strategy} strategy"]
                )

            def manage_west_workspace(
                self, workspace_config: WestWorkspaceConfig
            ) -> bool:
                return True

            def cache_workspace(self, workspace_path: Path) -> bool:
                return True

        compiler = TestGenericCompiler()
        assert isinstance(compiler, GenericDockerCompilerProtocol)

        # Test method calls with proper types
        config = GenericDockerCompileConfig(
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

        assert compiler.initialize_workspace(config) is True

        strategy_result = compiler.execute_build_strategy("west", ["west build"])
        assert isinstance(strategy_result, BuildResult)
        assert "Executed west strategy" in strategy_result.messages

        workspace_config = WestWorkspaceConfig()
        assert compiler.manage_west_workspace(workspace_config) is True

        assert compiler.cache_workspace(Path("/workspace")) is True

    def test_generic_compiler_with_west_workspace(self):
        """Test generic compiler implementation with west workspace features."""

        class WestEnabledCompiler:
            def __init__(self):
                self.workspace_initialized = False
                self.cached_workspaces = set()

            def compile(
                self,
                keymap_file: Path,
                config_file: Path,
                output_dir: Path,
                config: GenericDockerCompileConfig,
            ) -> BuildResult:
                if (
                    config.build_strategy == "west"
                    and config.west_workspace
                    and not self.workspace_initialized
                ):
                    self.initialize_workspace(config)

                return BuildResult(success=True, messages=["Compilation completed"])

            def check_available(self) -> bool:
                return True

            def validate_config(self, config: GenericDockerCompileConfig) -> bool:
                return not (
                    config.build_strategy == "west" and not config.west_workspace
                )

            def build_image(self, config: GenericDockerCompileConfig) -> BuildResult:
                return BuildResult(success=True)

            def initialize_workspace(self, config: GenericDockerCompileConfig) -> bool:
                if config.west_workspace:
                    self.workspace_initialized = True
                    if config.cache_workspace:
                        self.cache_workspace(Path(config.west_workspace.workspace_path))
                return True

            def execute_build_strategy(
                self, strategy: str, commands: list[str]
            ) -> BuildResult:
                if strategy == "west":
                    return BuildResult(success=True, messages=["West build completed"])
                return BuildResult(
                    success=False, errors=[f"Unsupported strategy: {strategy}"]
                )

            def manage_west_workspace(
                self, workspace_config: WestWorkspaceConfig
            ) -> bool:
                return True

            def cache_workspace(self, workspace_path: Path) -> bool:
                self.cached_workspaces.add(str(workspace_path))
                return True

        compiler = WestEnabledCompiler()
        assert isinstance(compiler, GenericDockerCompilerProtocol)

        # Test with west configuration
        west_config = WestWorkspaceConfig(
            manifest_url="https://github.com/zmkfirmware/zmk.git",
            workspace_path="/test-workspace",
        )

        config = GenericDockerCompileConfig(
            image="zmkfirmware/zmk-build-arm:stable",
            build_strategy="west",
            west_workspace=west_config,
            cache_workspace=True,
        )

        # Test validation
        assert compiler.validate_config(config) is True

        # Test compilation workflow
        result = compiler.compile(
            Path("test.keymap"),
            Path("test.conf"),
            Path("output"),
            config,
        )
        assert result.success is True
        assert compiler.workspace_initialized is True
        assert "/test-workspace" in compiler.cached_workspaces

        # Test strategy execution
        strategy_result = compiler.execute_build_strategy("west", ["west build"])
        assert strategy_result.success is True
        assert "West build completed" in strategy_result.messages

        # Test unsupported strategy
        bad_strategy_result = compiler.execute_build_strategy("unsupported", [])
        assert bad_strategy_result.success is False
        assert "Unsupported strategy" in bad_strategy_result.errors[0]

    def test_protocol_inheritance_compatibility(self):
        """Test that GenericDockerCompilerProtocol maintains compatibility."""
        from glovebox.config.compile_methods import (
            CompileMethodConfig,
            DockerCompileConfig,
        )
        from glovebox.protocols.compile_protocols import CompilerProtocol

        class BaseCompatibleCompiler:
            """Implementation that works with both protocols."""

            def compile(
                self,
                keymap_file: Path,
                config_file: Path,
                output_dir: Path,
                config: CompileMethodConfig,  # Accept base type
            ) -> BuildResult:
                if isinstance(config, GenericDockerCompileConfig):
                    return BuildResult(
                        success=True, messages=["Generic Docker compilation"]
                    )
                return BuildResult(success=True, messages=["Standard compilation"])

            def check_available(self) -> bool:
                return True

            def validate_config(self, config: CompileMethodConfig) -> bool:
                return True

            # Generic compiler specific methods
            def build_image(self, config: GenericDockerCompileConfig) -> BuildResult:
                return BuildResult(success=True)

            def initialize_workspace(self, config: GenericDockerCompileConfig) -> bool:
                return True

            def execute_build_strategy(
                self, strategy: str, commands: list[str]
            ) -> BuildResult:
                return BuildResult(success=True)

            def manage_west_workspace(
                self, workspace_config: WestWorkspaceConfig
            ) -> bool:
                return True

            def cache_workspace(self, workspace_path: Path) -> bool:
                return True

        compiler = BaseCompatibleCompiler()

        # Should implement both protocols
        assert isinstance(compiler, CompilerProtocol)
        assert isinstance(compiler, GenericDockerCompilerProtocol)

        # Test with base config
        base_result = compiler.compile(
            Path("test.keymap"),
            Path("test.conf"),
            Path("output"),
            DockerCompileConfig(),
        )
        assert "Standard compilation" in base_result.messages

        # Test with generic config
        generic_result = compiler.compile(
            Path("test.keymap"),
            Path("test.conf"),
            Path("output"),
            GenericDockerCompileConfig(),
        )
        assert "Generic Docker compilation" in generic_result.messages

    def test_caching_workflow_integration(self):
        """Test integration of caching workflow with protocol."""

        class CachingCompiler:
            def __init__(self):
                self.cache_hits = 0
                self.cache_misses = 0
                self.cached_paths = set()

            def compile(
                self,
                keymap_file: Path,
                config_file: Path,
                output_dir: Path,
                config: GenericDockerCompileConfig,
            ) -> BuildResult:
                if config.cache_workspace and config.west_workspace:
                    workspace_path = Path(config.west_workspace.workspace_path)
                    if str(workspace_path) in self.cached_paths:
                        self.cache_hits += 1
                        return BuildResult(
                            success=True, messages=["Used cached workspace"]
                        )
                    else:
                        self.cache_misses += 1
                        self.cache_workspace(workspace_path)
                        return BuildResult(
                            success=True, messages=["Built and cached workspace"]
                        )

                return BuildResult(success=True, messages=["Standard build"])

            def check_available(self) -> bool:
                return True

            def validate_config(self, config: GenericDockerCompileConfig) -> bool:
                return True

            def build_image(self, config: GenericDockerCompileConfig) -> BuildResult:
                return BuildResult(success=True)

            def initialize_workspace(self, config: GenericDockerCompileConfig) -> bool:
                return True

            def execute_build_strategy(
                self, strategy: str, commands: list[str]
            ) -> BuildResult:
                return BuildResult(success=True)

            def manage_west_workspace(
                self, workspace_config: WestWorkspaceConfig
            ) -> bool:
                return True

            def cache_workspace(self, workspace_path: Path) -> bool:
                self.cached_paths.add(str(workspace_path))
                return True

        compiler = CachingCompiler()
        assert isinstance(compiler, GenericDockerCompilerProtocol)

        config = GenericDockerCompileConfig(
            image="test:latest",
            build_strategy="west",
            west_workspace=WestWorkspaceConfig(workspace_path="/test-workspace"),
            cache_workspace=True,
        )

        # First build - cache miss
        result1 = compiler.compile(
            Path("test.keymap"), Path("test.conf"), Path("output"), config
        )
        assert result1.success is True
        assert "Built and cached workspace" in result1.messages
        assert compiler.cache_misses == 1
        assert compiler.cache_hits == 0

        # Second build - cache hit
        result2 = compiler.compile(
            Path("test.keymap"), Path("test.conf"), Path("output"), config
        )
        assert result2.success is True
        assert "Used cached workspace" in result2.messages
        assert compiler.cache_misses == 1
        assert compiler.cache_hits == 1
