"""Tests for method registry system."""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Generic, TypeVar, Union
from unittest.mock import Mock

import pytest


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile

from glovebox.config.compile_methods import CompileMethodConfig, DockerCompileConfig
from glovebox.config.flash_methods import FlashMethodConfig, USBFlashConfig
from glovebox.firmware.flash.models import BlockDevice, FlashResult
from glovebox.firmware.method_registry import (
    MethodRegistry,
    compiler_registry,
    flasher_registry,
)
from glovebox.firmware.models import BuildResult
from glovebox.protocols.compile_protocols import CompilerProtocol
from glovebox.protocols.flash_protocols import FlasherProtocol


class TestMethodRegistry:
    """Tests for MethodRegistry generic class."""

    def test_registry_initialization(self):
        """Test that MethodRegistry initializes correctly."""
        registry: MethodRegistry[Any, Any] = MethodRegistry()

        assert hasattr(registry, "_methods")
        assert hasattr(registry, "_config_types")
        assert registry._methods == {}
        assert registry._config_types == {}

    def test_method_registration(self):
        """Test method registration functionality."""
        registry: MethodRegistry[Any, Any] = MethodRegistry()

        # Create a test implementation
        class TestImplementation:
            def __init__(self, config=None, **kwargs):
                self.config = config
                self.kwargs = kwargs

        # Create a test config type
        class TestConfig:
            def __init__(self):
                self.method_type = "test"

        # Register the method
        registry.register_method(
            method_name="test_method",
            implementation=TestImplementation,
            config_type=TestConfig,
        )

        assert "test_method" in registry._methods
        assert "test_method" in registry._config_types
        assert registry._methods["test_method"] == TestImplementation
        assert registry._config_types["test_method"] == TestConfig

    def test_method_creation(self):
        """Test method creation from registry."""
        registry: MethodRegistry[Any, Any] = MethodRegistry()

        class TestImplementation:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
                self.created = True

        class TestConfig:
            def __init__(self):
                self.method_type = "test"

        # Register and create
        registry.register_method("test", TestImplementation, TestConfig)

        config = TestConfig()
        instance = registry.create_method("test", config, extra_param="value")

        assert isinstance(instance, TestImplementation)
        assert instance.kwargs["extra_param"] == "value"
        assert instance.created is True

    def test_unknown_method_error(self):
        """Test error handling for unknown methods."""
        registry: MethodRegistry[Any, Any] = MethodRegistry()

        class TestConfig:
            pass

        with pytest.raises(ValueError) as exc_info:
            registry.create_method("unknown", TestConfig())

        assert "Unknown method: unknown" in str(exc_info.value)

    def test_config_type_validation(self):
        """Test configuration type validation."""
        registry: MethodRegistry[Any, Any] = MethodRegistry()

        class TestImplementation:
            def __init__(self, config=None, **kwargs):
                pass

        class TestConfig:
            pass

        class WrongConfig:
            pass

        registry.register_method("test", TestImplementation, TestConfig)

        # Valid config should work
        valid_config = TestConfig()
        instance = registry.create_method("test", valid_config)
        assert instance is not None

        # Wrong config type should fail
        wrong_config = WrongConfig()
        with pytest.raises(TypeError) as exc_info:
            registry.create_method("test", wrong_config)

        assert "Expected TestConfig" in str(exc_info.value)
        assert "got WrongConfig" in str(exc_info.value)

    def test_get_available_methods(self):
        """Test getting list of available methods."""
        registry: MethodRegistry[Any, Any] = MethodRegistry()

        class AvailableImplementation:
            def __init__(self, config=None, **kwargs):
                pass

            def check_available(self):
                return True

        class UnavailableImplementation:
            def __init__(self, config=None, **kwargs):
                pass

            def check_available(self):
                return False

        class TestConfig:
            def __init__(self):
                pass

        # Register both implementations
        registry.register_method("available", AvailableImplementation, TestConfig)
        registry.register_method("unavailable", UnavailableImplementation, TestConfig)

        available_methods = registry.get_available_methods()

        assert "available" in available_methods
        assert "unavailable" not in available_methods

    def test_get_available_methods_error_handling(self):
        """Test that get_available_methods handles errors gracefully."""
        registry: MethodRegistry[Any, Any] = MethodRegistry()

        class ErrorImplementation:
            def __init__(self, config=None, **kwargs):
                raise Exception("Initialization error")

        class TestConfig:
            def __init__(self):
                pass

        registry.register_method("error", ErrorImplementation, TestConfig)

        # Should not raise exception, just exclude the erroring method
        available_methods = registry.get_available_methods()
        assert "error" not in available_methods


class TestCompilerRegistry:
    """Tests for global compiler registry."""

    def test_compiler_registry_exists(self):
        """Test that global compiler registry exists."""
        assert compiler_registry is not None
        assert isinstance(compiler_registry, MethodRegistry)

    def test_compiler_registration_and_creation(self):
        """Test compiler registration and creation."""

        # Create a test compiler
        class TestCompiler:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def compile(
                self,
                keymap_file: Path,
                config_file: Path,
                output_dir: Path,
                config: CompileMethodConfig,
                keyboard_profile: Union["KeyboardProfile", None] = None,
            ) -> BuildResult:
                return BuildResult(success=True)

            def check_available(self) -> bool:
                return True

            def validate_config(self, config: CompileMethodConfig) -> bool:
                return True

        # Register with the global registry
        compiler_registry.register_method(
            method_name="test_compiler",
            implementation=TestCompiler,
            config_type=DockerCompileConfig,
        )

        # Create instance
        config = DockerCompileConfig()
        compiler = compiler_registry.create_method("test_compiler", config)

        assert isinstance(compiler, TestCompiler)
        assert isinstance(compiler, CompilerProtocol)  # Should implement protocol

    def test_compiler_protocol_compliance(self):
        """Test that registered compilers comply with CompilerProtocol."""

        class ProtocolCompliantCompiler:
            def __init__(self, config=None, **kwargs):
                self.config = config

            def compile(
                self,
                keymap_file: Path,
                config_file: Path,
                output_dir: Path,
                config: CompileMethodConfig,
                keyboard_profile: Union["KeyboardProfile", None] = None,
            ) -> BuildResult:
                return BuildResult(
                    success=True,
                    messages=[f"Compiled {keymap_file} with {config.method_type}"],
                )

            def check_available(self) -> bool:
                return True

            def validate_config(self, config: CompileMethodConfig) -> bool:
                return isinstance(config, CompileMethodConfig)

        compiler_registry.register_method(
            "protocol_test", ProtocolCompliantCompiler, DockerCompileConfig
        )

        config = DockerCompileConfig()
        compiler = compiler_registry.create_method("protocol_test", config)

        # Test protocol methods
        assert compiler.check_available() is True
        assert compiler.validate_config(config) is True

        result = compiler.compile(
            Path("test.keymap"), Path("test.conf"), Path("output"), config
        )
        assert result.success is True
        assert "docker" in result.messages[0]


class TestFlasherRegistry:
    """Tests for global flasher registry."""

    def test_flasher_registry_exists(self):
        """Test that global flasher registry exists."""
        assert flasher_registry is not None
        assert isinstance(flasher_registry, MethodRegistry)

    def test_flasher_registration_and_creation(self):
        """Test flasher registration and creation."""

        # Create a test flasher
        class TestFlasher:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def flash_device(
                self,
                device: BlockDevice,
                firmware_file: Path,
                config: FlashMethodConfig,
            ) -> FlashResult:
                return FlashResult(success=True)

            def list_devices(self, config: FlashMethodConfig) -> list[BlockDevice]:
                return []

            def check_available(self) -> bool:
                return True

            def validate_config(self, config: FlashMethodConfig) -> bool:
                return True

        # Register with the global registry
        flasher_registry.register_method(
            method_name="test_flasher",
            implementation=TestFlasher,
            config_type=USBFlashConfig,
        )

        # Create instance
        config = USBFlashConfig(device_query="removable=true")
        flasher = flasher_registry.create_method("test_flasher", config)

        assert isinstance(flasher, TestFlasher)
        assert isinstance(flasher, FlasherProtocol)  # Should implement protocol

    def test_flasher_protocol_compliance(self):
        """Test that registered flashers comply with FlasherProtocol."""

        class ProtocolCompliantFlasher:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
                self.test_devices = [
                    BlockDevice(
                        name="test_device",
                        device_node="/dev/test",
                        serial="TEST123",
                        vendor="Test",
                        model="TestDevice",
                        removable=True,
                    )
                ]

            def flash_device(
                self,
                device: BlockDevice,
                firmware_file: Path,
                config: FlashMethodConfig,
            ) -> FlashResult:
                return FlashResult(
                    success=True,
                    messages=[f"Flashed {firmware_file} to {device.name}"],
                    devices_flashed=1,
                )

            def list_devices(self, config: FlashMethodConfig) -> list[BlockDevice]:
                return self.test_devices

            def check_available(self) -> bool:
                return True

            def validate_config(self, config: FlashMethodConfig) -> bool:
                return True

        flasher_registry.register_method(
            "protocol_test", ProtocolCompliantFlasher, USBFlashConfig
        )

        config = USBFlashConfig(device_query="removable=true")
        flasher = flasher_registry.create_method("protocol_test", config)

        # Test protocol methods
        devices = flasher.list_devices(config)
        assert len(devices) == 1
        assert devices[0].name == "test_device"

        result = flasher.flash_device(devices[0], Path("firmware.uf2"), config)
        assert result.success is True
        assert "firmware.uf2" in result.messages[0]
        assert result.devices_flashed == 1


class TestRegistryIntegration:
    """Tests for registry integration and advanced functionality."""

    def test_multiple_method_types(self):
        """Test registering multiple method types in same registry."""
        registry: MethodRegistry[Any, Any] = MethodRegistry()

        class Method1:
            def __init__(self, config=None, **kwargs):
                self.config = config
                self.method = "method1"

        class Method2:
            def __init__(self, config=None, **kwargs):
                self.config = config
                self.method = "method2"

        class Config1:
            pass

        class Config2:
            pass

        registry.register_method("type1", Method1, Config1)
        registry.register_method("type2", Method2, Config2)

        instance1 = registry.create_method("type1", Config1())
        instance2 = registry.create_method("type2", Config2())

        assert instance1.method == "method1"
        assert instance2.method == "method2"

    def test_dependency_injection(self):
        """Test dependency injection through registry."""
        registry: MethodRegistry[Any, Any] = MethodRegistry()

        class DependentImplementation:
            def __init__(self, config=None, adapter=None, service=None, **kwargs):
                self.config = config
                self.adapter = adapter
                self.service = service
                self.extra_kwargs = kwargs

        class TestConfig:
            pass

        registry.register_method("dependent", DependentImplementation, TestConfig)

        # Create with dependencies
        mock_adapter = Mock()
        mock_service = Mock()

        instance = registry.create_method(
            "dependent",
            TestConfig(),
            adapter=mock_adapter,
            service=mock_service,
            extra_param="value",
        )

        assert instance.adapter == mock_adapter
        assert instance.service == mock_service
        assert instance.extra_kwargs["extra_param"] == "value"

    def test_registry_isolation(self):
        """Test that different registry instances are isolated."""
        registry1: MethodRegistry[Any, Any] = MethodRegistry()
        registry2: MethodRegistry[Any, Any] = MethodRegistry()

        class Implementation1:
            def __init__(self, config=None, **kwargs):
                self.registry = "registry1"

        class Implementation2:
            def __init__(self, config=None, **kwargs):
                self.registry = "registry2"

        class TestConfig:
            pass

        registry1.register_method("test", Implementation1, TestConfig)
        registry2.register_method("test", Implementation2, TestConfig)

        instance1 = registry1.create_method("test", TestConfig())
        instance2 = registry2.create_method("test", TestConfig())

        assert instance1.registry == "registry1"
        assert instance2.registry == "registry2"

    def test_registry_method_override(self):
        """Test that registering same method name overrides previous registration."""
        registry: MethodRegistry[Any, Any] = MethodRegistry()

        class OriginalImplementation:
            def __init__(self, config=None, **kwargs):
                self.version = "original"

        class UpdatedImplementation:
            def __init__(self, config=None, **kwargs):
                self.version = "updated"

        class TestConfig:
            pass

        # Register original
        registry.register_method("test", OriginalImplementation, TestConfig)
        instance1 = registry.create_method("test", TestConfig())
        assert instance1.version == "original"

        # Register updated (should override)
        registry.register_method("test", UpdatedImplementation, TestConfig)
        instance2 = registry.create_method("test", TestConfig())
        assert instance2.version == "updated"
