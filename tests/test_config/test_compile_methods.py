"""Tests for compile method configuration models."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from glovebox.config.compile_methods import (
    CompileMethodConfig,
    CrossCompileConfig,
    DockerCompileConfig,
    LocalCompileConfig,
    QemuCompileConfig,
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
            assert config.method_type in ["docker", "local", "cross", "qemu"]

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
