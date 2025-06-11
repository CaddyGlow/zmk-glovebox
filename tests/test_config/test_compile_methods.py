"""Tests for compile method configuration models."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from glovebox.config.compile_methods import (
    CompileMethodConfig,
    CrossCompileConfig,
    DockerCompileConfig,
    CompilationConfig,
    LocalCompileConfig,
    QemuCompileConfig,
    WestWorkspaceConfig,
    expand_path_variables,
)


class TestDockerCompileConfig:
    """Tests for DockerCompileConfig model."""

    def test_default_values(self):
        """Test default values for Docker compilation configuration."""
        config = DockerCompileConfig()

        assert config.method_type == "docker"
        assert config.image == "moergo-zmk-build:latest"
        assert config.repository == "moergo-sc/zmk"
        assert config.branch == "main"
        assert config.jobs is None
        assert config.fallback_methods == []

    def test_custom_values(self):
        """Test creation with custom values."""
        config = DockerCompileConfig(
            image="custom-zmk:v1.0",
            repository="custom/zmk-fork",
            branch="feature-branch",
            jobs=8,
            fallback_methods=["local", "cross"],
        )

        assert config.method_type == "docker"
        assert config.image == "custom-zmk:v1.0"
        assert config.repository == "custom/zmk-fork"
        assert config.branch == "feature-branch"
        assert config.jobs == 8
        assert config.fallback_methods == ["local", "cross"]

    def test_method_type_default(self):
        """Test that method_type has correct default value."""
        config = DockerCompileConfig()
        assert config.method_type == "docker"

        # Method type can be overridden but has a sensible default
        config = DockerCompileConfig(method_type="other")
        assert config.method_type == "other"  # Pydantic allows override

    def test_jobs_validation(self):
        """Test jobs field validation."""
        # Valid jobs values
        config = DockerCompileConfig(jobs=1)
        assert config.jobs == 1

        config = DockerCompileConfig(jobs=16)
        assert config.jobs == 16

        config = DockerCompileConfig(jobs=None)
        assert config.jobs is None


class TestLocalCompileConfig:
    """Tests for LocalCompileConfig model."""

    def test_required_fields(self):
        """Test that required fields are enforced."""
        # Missing zmk_path should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            LocalCompileConfig()  # type: ignore[call-arg]
        assert "zmk_path" in str(exc_info.value)

    def test_valid_configuration(self):
        """Test creation with valid configuration."""
        config = LocalCompileConfig(
            zmk_path=Path("/opt/zmk"),
            toolchain_path=Path("/opt/zephyr-sdk"),
            zephyr_base=Path("/opt/zephyr"),
            jobs=4,
            fallback_methods=["docker"],
        )

        assert config.method_type == "local"
        assert config.zmk_path == Path("/opt/zmk")
        assert config.toolchain_path == Path("/opt/zephyr-sdk")
        assert config.zephyr_base == Path("/opt/zephyr")
        assert config.jobs == 4
        assert config.fallback_methods == ["docker"]

    def test_optional_fields(self):
        """Test that optional fields have correct defaults."""
        config = LocalCompileConfig(zmk_path=Path("/opt/zmk"))

        assert config.method_type == "local"
        assert config.zmk_path == Path("/opt/zmk")
        assert config.toolchain_path is None
        assert config.zephyr_base is None
        assert config.jobs is None
        assert config.fallback_methods == []

    def test_path_conversion(self):
        """Test automatic string to Path conversion."""
        config = LocalCompileConfig(
            zmk_path=Path("/opt/zmk"),
            toolchain_path="/opt/toolchain",  # type: ignore[arg-type]
        )

        assert isinstance(config.zmk_path, Path)
        assert isinstance(config.toolchain_path, Path)
        assert config.zmk_path == Path("/opt/zmk")
        assert config.toolchain_path == Path("/opt/toolchain")


class TestCrossCompileConfig:
    """Tests for CrossCompileConfig model."""

    def test_required_fields(self):
        """Test that required fields are enforced."""
        with pytest.raises(ValidationError) as exc_info:
            CrossCompileConfig()  # type: ignore[call-arg]
        error_str = str(exc_info.value)
        assert "target_arch" in error_str
        assert "sysroot" in error_str
        assert "toolchain_prefix" in error_str

    def test_valid_configuration(self):
        """Test creation with valid configuration."""
        config = CrossCompileConfig(
            target_arch="arm",
            sysroot=Path("/usr/arm-linux-gnueabihf"),
            toolchain_prefix="arm-linux-gnueabihf-",
            cmake_toolchain=Path("/opt/cmake/arm-toolchain.cmake"),
            fallback_methods=["docker", "local"],
        )

        assert config.method_type == "cross"
        assert config.target_arch == "arm"
        assert config.sysroot == Path("/usr/arm-linux-gnueabihf")
        assert config.toolchain_prefix == "arm-linux-gnueabihf-"
        assert config.cmake_toolchain == Path("/opt/cmake/arm-toolchain.cmake")
        assert config.fallback_methods == ["docker", "local"]

    def test_optional_cmake_toolchain(self):
        """Test that cmake_toolchain is optional."""
        config = CrossCompileConfig(
            target_arch="x86_64",
            sysroot=Path("/usr/x86_64-linux-gnu"),
            toolchain_prefix="x86_64-linux-gnu-",
        )

        assert config.method_type == "cross"
        assert config.cmake_toolchain is None


class TestQemuCompileConfig:
    """Tests for QemuCompileConfig model."""

    def test_default_values(self):
        """Test default values for QEMU compilation configuration."""
        config = QemuCompileConfig()

        assert config.method_type == "qemu"
        assert config.qemu_target == "native_posix"
        assert config.test_runners == []
        assert config.fallback_methods == []

    def test_custom_values(self):
        """Test creation with custom values."""
        config = QemuCompileConfig(
            qemu_target="qemu_x86",
            test_runners=["pytest", "coverage"],
            fallback_methods=["docker"],
        )

        assert config.method_type == "qemu"
        assert config.qemu_target == "qemu_x86"
        assert config.test_runners == ["pytest", "coverage"]
        assert config.fallback_methods == ["docker"]


class TestCompileMethodConfigInheritance:
    """Tests for CompileMethodConfig base class behavior."""

    def test_abstract_base_class(self):
        """Test that CompileMethodConfig cannot be instantiated directly."""
        # This should work since CompileMethodConfig is abstract but Pydantic allows it
        # The ABC mixin provides the abstraction at the Python level
        config = CompileMethodConfig(method_type="test")
        assert config.method_type == "test"
        assert config.fallback_methods == []

    def test_fallback_methods_inheritance(self):
        """Test that all concrete classes inherit fallback_methods behavior."""
        docker_config = DockerCompileConfig(fallback_methods=["local"])
        local_config = LocalCompileConfig(
            zmk_path=Path("/opt/zmk"), fallback_methods=["docker"]
        )

        assert docker_config.fallback_methods == ["local"]
        assert local_config.fallback_methods == ["docker"]

    def test_polymorphic_behavior(self):
        """Test that configs can be treated polymorphically."""
        configs = [
            DockerCompileConfig(),
            CompilationConfig(),
            LocalCompileConfig(zmk_path=Path("/opt/zmk")),
            CrossCompileConfig(
                target_arch="arm", sysroot=Path("/usr/arm"), toolchain_prefix="arm-"
            ),
            QemuCompileConfig(),
        ]

        # All should have method_type and fallback_methods
        for config in configs:
            assert hasattr(config, "method_type")
            assert hasattr(config, "fallback_methods")
            assert isinstance(config.method_type, str)
            assert isinstance(config.fallback_methods, list)


class TestConfigurationValidation:
    """Tests for comprehensive configuration validation."""

    def test_valid_configurations(self):
        """Test various valid configuration combinations."""
        valid_configs = [
            DockerCompileConfig(image="custom:latest", branch="develop", jobs=8),
            LocalCompileConfig(
                zmk_path=Path("~/zmk"), toolchain_path=Path("~/toolchain"), jobs=None
            ),
            CrossCompileConfig(
                target_arch="aarch64",
                sysroot=Path("/opt/aarch64-sysroot"),
                toolchain_prefix="aarch64-linux-gnu-",
                cmake_toolchain=Path("/opt/toolchain.cmake"),
            ),
            QemuCompileConfig(
                qemu_target="qemu_arm", test_runners=["unit", "integration"]
            ),
        ]

        for config in valid_configs:
            # Should not raise any validation errors
            assert config is not None
            assert config.method_type in [
                "docker",
                "generic_docker",
                "local",
                "cross",
                "qemu",
            ]

    def test_model_serialization(self):
        """Test that models can be serialized to dict."""
        config = DockerCompileConfig(
            image="test:v1",
            repository="test/repo",
            branch="test-branch",
            jobs=4,
            fallback_methods=["local"],
        )

        config_dict = config.model_dump()

        assert config_dict["method_type"] == "docker"
        assert config_dict["image"] == "test:v1"
        assert config_dict["repository"] == "test/repo"
        assert config_dict["branch"] == "test-branch"
        assert config_dict["jobs"] == 4
        assert config_dict["fallback_methods"] == ["local"]

    def test_model_deserialization(self):
        """Test that models can be created from dict."""
        config_dict = {
            "method_type": "docker",
            "image": "test:v2",
            "repository": "test/fork",
            "branch": "feature",
            "jobs": 2,
            "fallback_methods": ["cross"],
        }

        config = DockerCompileConfig.model_validate(config_dict)

        assert config.method_type == "docker"
        assert config.image == "test:v2"
        assert config.repository == "test/fork"
        assert config.branch == "feature"
        assert config.jobs == 2
        assert config.fallback_methods == ["cross"]


class TestWestWorkspaceConfig:
    """Tests for WestWorkspaceConfig model."""

    def test_default_values(self):
        """Test default values for West workspace configuration."""
        config = WestWorkspaceConfig()

        assert config.manifest_url == "https://github.com/zmkfirmware/zmk.git"
        assert config.manifest_revision == "main"
        assert config.modules == []
        assert config.west_commands == []
        assert config.workspace_path == "/zmk-workspace"
        assert config.config_path == "config"

    def test_custom_values(self):
        """Test creation with custom values."""
        config = WestWorkspaceConfig(
            manifest_url="https://github.com/custom/zmk.git",
            manifest_revision="develop",
            modules=["module1", "module2"],
            west_commands=["west init", "west update", "west build"],
            workspace_path="/custom-workspace",
            config_path="custom-config",
        )

        assert config.manifest_url == "https://github.com/custom/zmk.git"
        assert config.manifest_revision == "develop"
        assert config.modules == ["module1", "module2"]
        assert config.west_commands == ["west init", "west update", "west build"]
        assert config.workspace_path == "/custom-workspace"
        assert config.config_path == "custom-config"

    def test_validation(self):
        """Test field validation."""
        # Valid URL
        config = WestWorkspaceConfig(manifest_url="https://example.com/repo.git")
        assert config.manifest_url == "https://example.com/repo.git"

        # Empty lists should work
        config = WestWorkspaceConfig(modules=[], west_commands=[])
        assert config.modules == []
        assert config.west_commands == []

    def test_workspace_path_expansion(self):
        """Test that workspace_path expands environment variables and user home."""
        import os
        from pathlib import Path

        # Test ~ expansion
        config = WestWorkspaceConfig(workspace_path="~/.zmk-workspace")
        expected_path = str(Path("~/.zmk-workspace").expanduser())
        assert config.workspace_path == expected_path

        # Test $HOME expansion
        config = WestWorkspaceConfig(workspace_path="$HOME/.zmk-workspace")
        expected_path = os.path.expandvars("$HOME/.zmk-workspace")
        assert config.workspace_path == expected_path

        # Test combination of environment variable and path
        config = WestWorkspaceConfig(workspace_path="$HOME/projects/zmk")
        expected_path = os.path.expandvars("$HOME/projects/zmk")
        assert config.workspace_path == expected_path


class TestPathExpansion:
    """Tests for path expansion helper functions."""

    def test_expand_path_variables_function(self):
        """Test the expand_path_variables helper function."""
        import os
        from pathlib import Path

        # Test ~ expansion
        result = expand_path_variables("~/.zmk-workspace")
        expected = str(Path("~/.zmk-workspace").expanduser())
        assert result == expected

        # Test $HOME expansion
        result = expand_path_variables("$HOME/.zmk-workspace")
        expected = os.path.expandvars("$HOME/.zmk-workspace")
        assert result == expected

        # Test absolute path (no expansion needed)
        result = expand_path_variables("/absolute/path")
        assert result == "/absolute/path"

        # Test relative path (no expansion needed)
        result = expand_path_variables("relative/path")
        assert result == "relative/path"

        # Test combined expansion
        result = expand_path_variables("$HOME/~/nested")
        # This should expand $HOME first, then handle ~ (though this is unusual)
        expected_home = os.path.expandvars("$HOME")
        expected = f"{expected_home}/~/nested"
        assert result == expected


class TestCompilationConfig:
    """Tests for CompilationConfig model."""

    def test_default_values(self):
        """Test default values for Generic Docker compilation configuration."""
        config = CompilationConfig()

        assert config.method_type == "generic_docker"
        assert config.build_strategy == "west"
        assert config.west_workspace is None
        assert config.build_commands == []
        assert config.environment_template == {}
        assert config.volume_templates == []
        assert config.board_targets == []
        assert config.cache_workspace is True
        assert config.fallback_methods == []

    def test_custom_values(self):
        """Test creation with custom values."""
        west_config = WestWorkspaceConfig(
            manifest_url="https://github.com/custom/zmk.git",
            workspace_path="/custom-workspace",
        )

        config = CompilationConfig(
            image="custom-zmk:latest",
            build_strategy="cmake",
            west_workspace=west_config,
            build_commands=["cmake -B build", "cmake --build build"],
            environment_template={"CC": "gcc", "CXX": "g++"},
            volume_templates=["/workspace:/src:rw"],
            board_targets=["nice_nano_v2", "pro_micro"],
            cache_workspace=False,
            fallback_methods=["docker", "local"],
        )

        assert config.method_type == "generic_docker"
        assert config.image == "custom-zmk:latest"
        assert config.build_strategy == "cmake"
        assert config.west_workspace == west_config
        assert config.build_commands == ["cmake -B build", "cmake --build build"]
        assert config.environment_template == {"CC": "gcc", "CXX": "g++"}
        assert config.volume_templates == ["/workspace:/src:rw"]
        assert config.board_targets == ["nice_nano_v2", "pro_micro"]
        assert config.cache_workspace is False
        assert config.fallback_methods == ["docker", "local"]

    def test_west_workspace_nesting(self):
        """Test nested west workspace configuration."""
        config = CompilationConfig(
            build_strategy="west",
            west_workspace=WestWorkspaceConfig(
                manifest_url="https://github.com/zmkfirmware/zmk.git",
                manifest_revision="v3.5.0",
                modules=["hal_nordic"],
                workspace_path="/zmk-build",
            ),
        )

        assert config.build_strategy == "west"
        assert config.west_workspace is not None
        assert (
            config.west_workspace.manifest_url
            == "https://github.com/zmkfirmware/zmk.git"
        )
        assert config.west_workspace.manifest_revision == "v3.5.0"
        assert config.west_workspace.modules == ["hal_nordic"]
        assert config.west_workspace.workspace_path == "/zmk-build"

    def test_build_strategy_validation(self):
        """Test build strategy field validation."""
        # Valid strategies
        valid_strategies = ["west", "cmake", "make", "ninja", "custom"]
        for strategy in valid_strategies:
            config = CompilationConfig(build_strategy=strategy)
            assert config.build_strategy == strategy

    def test_inheritance_from_docker_config(self):
        """Test that CompilationConfig inherits from DockerCompileConfig."""
        config = CompilationConfig(
            image="zmk:test",
            repository="test/zmk",
            branch="test-branch",
            jobs=8,
        )

        # Should have inherited fields from DockerCompileConfig
        assert config.image == "zmk:test"
        assert config.repository == "test/zmk"
        assert config.branch == "test-branch"
        assert config.jobs == 8

        # Should have new generic docker fields
        assert config.method_type == "generic_docker"
        assert config.build_strategy == "west"
        assert config.cache_workspace is True

    def test_model_serialization(self):
        """Test that generic docker config can be serialized."""
        west_config = WestWorkspaceConfig(
            manifest_url="https://github.com/zmk/zmk.git",
            workspace_path="/test-workspace",
        )

        config = CompilationConfig(
            image="test:v1",
            build_strategy="west",
            west_workspace=west_config,
            build_commands=["west build"],
            environment_template={"BOARD": "nice_nano_v2"},
            board_targets=["nice_nano_v2"],
            cache_workspace=True,
        )

        config_dict = config.model_dump()

        assert config_dict["method_type"] == "generic_docker"
        assert config_dict["image"] == "test:v1"
        assert config_dict["build_strategy"] == "west"
        assert (
            config_dict["west_workspace"]["manifest_url"]
            == "https://github.com/zmk/zmk.git"
        )
        assert config_dict["west_workspace"]["workspace_path"] == "/test-workspace"
        assert config_dict["build_commands"] == ["west build"]
        assert config_dict["environment_template"]["BOARD"] == "nice_nano_v2"
        assert config_dict["board_targets"] == ["nice_nano_v2"]
        assert config_dict["cache_workspace"] is True

    def test_model_deserialization(self):
        """Test that generic docker config can be created from dict."""
        config_dict = {
            "method_type": "generic_docker",
            "image": "zmkfirmware/zmk-build-arm:stable",
            "build_strategy": "west",
            "west_workspace": {
                "manifest_url": "https://github.com/zmkfirmware/zmk.git",
                "manifest_revision": "main",
                "modules": [],
                "west_commands": [],
                "workspace_path": "/zmk-workspace",
                "config_path": "config",
            },
            "build_commands": ["west build -d build -s app"],
            "environment_template": {"ZEPHYR_TOOLCHAIN_VARIANT": "zephyr"},
            "volume_templates": ["/workspace:/src:rw"],
            "board_targets": ["glove80_lh", "glove80_rh"],
            "cache_workspace": True,
            "fallback_methods": ["docker"],
        }

        config = CompilationConfig.model_validate(config_dict)

        assert config.method_type == "generic_docker"
        assert config.image == "zmkfirmware/zmk-build-arm:stable"
        assert config.build_strategy == "west"
        assert config.west_workspace is not None
        assert (
            config.west_workspace.manifest_url
            == "https://github.com/zmkfirmware/zmk.git"
        )
        assert config.west_workspace.manifest_revision == "main"
        assert config.build_commands == ["west build -d build -s app"]
        assert config.environment_template["ZEPHYR_TOOLCHAIN_VARIANT"] == "zephyr"
        assert config.volume_templates == ["/workspace:/src:rw"]
        assert config.board_targets == ["glove80_lh", "glove80_rh"]
        assert config.cache_workspace is True
        assert config.fallback_methods == ["docker"]

    def test_without_west_workspace(self):
        """Test generic docker config without west workspace."""
        config = CompilationConfig(
            build_strategy="cmake",
            build_commands=["cmake -B build", "make -C build"],
            west_workspace=None,
        )

        assert config.build_strategy == "cmake"
        assert config.west_workspace is None
        assert config.build_commands == ["cmake -B build", "make -C build"]

    def test_complex_configuration(self):
        """Test complex configuration with all features."""
        config = CompilationConfig(
            # Inherited Docker fields
            image="zmkfirmware/zmk-build-arm:stable",
            repository="zmkfirmware/zmk",
            branch="main",
            jobs=8,
            # Generic Docker specific fields
            build_strategy="west",
            west_workspace=WestWorkspaceConfig(
                manifest_url="https://github.com/zmkfirmware/zmk.git",
                manifest_revision="main",
                modules=["hal_nordic", "segger"],
                west_commands=[
                    "west init -l config",
                    "west update",
                    "west config build.board-warn false",
                ],
                workspace_path="/zmk-workspace",
                config_path="config",
            ),
            build_commands=[
                "west build -d build/left -s app -b glove80_lh",
                "west build -d build/right -s app -b glove80_rh",
            ],
            environment_template={
                "ZEPHYR_TOOLCHAIN_VARIANT": "zephyr",
                "ZEPHYR_SDK_INSTALL_DIR": "/opt/zephyr-sdk",
                "BOARD": "glove80_lh",
            },
            volume_templates=[
                "/zmk-workspace/config:/workspace/config:rw",
                "/zmk-workspace/.west:/workspace/.west:rw",
                "/build:/workspace/build:rw",
            ],
            board_targets=["glove80_lh", "glove80_rh"],
            cache_workspace=True,
            fallback_methods=["docker", "local"],
        )

        # Verify all fields are set correctly
        assert config.method_type == "generic_docker"
        assert config.image == "zmkfirmware/zmk-build-arm:stable"
        assert config.repository == "zmkfirmware/zmk"
        assert config.branch == "main"
        assert config.jobs == 8
        assert config.build_strategy == "west"
        assert config.west_workspace is not None
        assert len(config.west_workspace.modules) == 2
        assert "hal_nordic" in config.west_workspace.modules
        assert "segger" in config.west_workspace.modules
        assert len(config.build_commands) == 2
        assert "glove80_lh" in config.build_commands[0]
        assert "glove80_rh" in config.build_commands[1]
        assert len(config.environment_template) == 3
        assert config.environment_template["ZEPHYR_TOOLCHAIN_VARIANT"] == "zephyr"
        assert len(config.volume_templates) == 3
        assert len(config.board_targets) == 2
        assert config.cache_workspace is True
        assert config.fallback_methods == ["docker", "local"]

    def test_volume_template_expansion(self):
        """Test that volume_templates expand environment variables."""
        import os
        from pathlib import Path

        config = CompilationConfig(
            volume_templates=[
                "~/.cache:/workspace/.cache:rw",
                "$HOME/builds:/builds:ro",
                "/absolute/path:/container/path:rw",
            ]
        )

        # Check that paths are expanded
        expected_cache = str(Path("~/.cache").expanduser())
        expected_home = os.path.expandvars("$HOME")

        assert config.volume_templates[0] == f"{expected_cache}:/workspace/.cache:rw"
        assert config.volume_templates[1] == f"{expected_home}/builds:/builds:ro"
        assert (
            config.volume_templates[2] == "/absolute/path:/container/path:rw"
        )  # No expansion needed

    def test_environment_template_expansion(self):
        """Test that environment_template values expand environment variables."""
        import os
        from pathlib import Path

        config = CompilationConfig(
            environment_template={
                "HOME_DIR": "$HOME",
                "CACHE_DIR": "~/.cache",
                "ABSOLUTE_PATH": "/usr/bin",
                "COMBINED": "$HOME/projects/zmk",
            }
        )

        # Check that values are expanded
        expected_home = os.path.expandvars("$HOME")
        expected_cache = str(Path("~/.cache").expanduser())

        assert config.environment_template["HOME_DIR"] == expected_home
        assert config.environment_template["CACHE_DIR"] == expected_cache
        assert (
            config.environment_template["ABSOLUTE_PATH"] == "/usr/bin"
        )  # No expansion needed
        assert (
            config.environment_template["COMBINED"] == f"{expected_home}/projects/zmk"
        )

    def test_west_workspace_path_expansion_in_generic_config(self):
        """Test workspace path expansion when used within CompilationConfig."""
        import os
        from pathlib import Path

        config = CompilationConfig(
            build_strategy="west",
            west_workspace=WestWorkspaceConfig(workspace_path="~/.zmk-workspace"),
        )

        expected_path = str(Path("~/.zmk-workspace").expanduser())
        assert config.west_workspace is not None
        assert config.west_workspace.workspace_path == expected_path
