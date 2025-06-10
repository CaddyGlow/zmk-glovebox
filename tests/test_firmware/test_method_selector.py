"""Tests for method selection and fallback logic."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.config.compile_methods import (
    CompileMethodConfig,
    CrossCompileConfig,
    DockerCompileConfig,
    LocalCompileConfig,
    QemuCompileConfig,
)
from glovebox.config.flash_methods import (
    BootloaderFlashConfig,
    DFUFlashConfig,
    FlashMethodConfig,
    USBFlashConfig,
    WiFiFlashConfig,
)
from glovebox.firmware.flash.models import BlockDevice, FlashResult
from glovebox.firmware.method_selector import (
    CompilerNotAvailableError,
    FlasherNotAvailableError,
    _create_compiler_config_for_method,
    _create_compiler_fallback_configs,
    _create_flasher_config_for_method,
    _create_flasher_fallback_configs,
    get_compiler_with_fallback_chain,
    get_flasher_with_fallback_chain,
    select_compiler_with_fallback,
    select_flasher_with_fallback,
)
from glovebox.firmware.models import BuildResult
from glovebox.protocols.compile_protocols import CompilerProtocol
from glovebox.protocols.flash_protocols import FlasherProtocol


class TestCompilerSelection:
    """Tests for compiler selection logic."""

    def test_select_first_available_compiler(self):
        """Test selecting the first available compiler."""
        # Create mock compilers
        available_compiler = Mock(spec=CompilerProtocol)
        available_compiler.check_available.return_value = True

        unavailable_compiler = Mock(spec=CompilerProtocol)
        unavailable_compiler.check_available.return_value = False

        configs: list[CompileMethodConfig] = [
            DockerCompileConfig(),
            LocalCompileConfig(zmk_path=Path("/opt/zmk")),
        ]

        with patch(
            "glovebox.firmware.method_selector.compiler_registry"
        ) as mock_registry:
            mock_registry.create_method.side_effect = [
                unavailable_compiler,  # First config creates unavailable compiler
                available_compiler,  # Second config creates available compiler
            ]

            result = select_compiler_with_fallback(configs)

            assert result == available_compiler
            assert mock_registry.create_method.call_count == 2

    def test_select_compiler_no_fallback_needed(self):
        """Test selecting compiler when first option is available."""
        available_compiler = Mock(spec=CompilerProtocol)
        available_compiler.check_available.return_value = True

        configs: list[CompileMethodConfig] = [DockerCompileConfig()]

        with patch(
            "glovebox.firmware.method_selector.compiler_registry"
        ) as mock_registry:
            mock_registry.create_method.return_value = available_compiler

            result = select_compiler_with_fallback(configs)

            assert result == available_compiler
            assert mock_registry.create_method.call_count == 1

    def test_select_compiler_all_unavailable(self):
        """Test error when all compilers are unavailable."""
        unavailable_compiler = Mock(spec=CompilerProtocol)
        unavailable_compiler.check_available.return_value = False

        configs: list[CompileMethodConfig] = [
            DockerCompileConfig(),
            LocalCompileConfig(zmk_path=Path("/opt/zmk")),
        ]

        with patch(
            "glovebox.firmware.method_selector.compiler_registry"
        ) as mock_registry:
            mock_registry.create_method.return_value = unavailable_compiler
            mock_registry.get_available_methods.return_value = ["docker", "local"]

            with pytest.raises(CompilerNotAvailableError) as exc_info:
                select_compiler_with_fallback(configs)

            assert "No available compilers from 2 configurations" in str(exc_info.value)
            assert "Available methods: ['docker', 'local']" in str(exc_info.value)

    def test_select_compiler_creation_error(self):
        """Test handling of compiler creation errors."""
        available_compiler = Mock(spec=CompilerProtocol)
        available_compiler.check_available.return_value = True

        configs: list[CompileMethodConfig] = [
            DockerCompileConfig(),
            LocalCompileConfig(zmk_path=Path("/opt/zmk")),
        ]

        with patch(
            "glovebox.firmware.method_selector.compiler_registry"
        ) as mock_registry:
            mock_registry.create_method.side_effect = [
                Exception("Creation failed"),  # First config fails
                available_compiler,  # Second config succeeds
            ]

            result = select_compiler_with_fallback(configs)

            assert result == available_compiler

    def test_select_compiler_with_dependencies(self):
        """Test selecting compiler with dependency injection."""
        available_compiler = Mock(spec=CompilerProtocol)
        available_compiler.check_available.return_value = True

        configs: list[CompileMethodConfig] = [DockerCompileConfig()]

        mock_dependency = Mock()

        with patch(
            "glovebox.firmware.method_selector.compiler_registry"
        ) as mock_registry:
            mock_registry.create_method.return_value = available_compiler

            result = select_compiler_with_fallback(configs, dependency=mock_dependency)

            assert result == available_compiler
            mock_registry.create_method.assert_called_with(
                "docker", configs[0], dependency=mock_dependency
            )

    def test_get_compiler_with_fallback_chain(self):
        """Test building compiler fallback chain."""
        primary_config = DockerCompileConfig(fallback_methods=["local"])

        configs = get_compiler_with_fallback_chain(primary_config)

        # Should return the config chain including primary + fallbacks
        assert len(configs) >= 1  # At least the primary config
        assert configs[0] == primary_config
        # Should include fallback config for "local" method if created successfully


class TestFlasherSelection:
    """Tests for flasher selection logic."""

    def test_select_first_available_flasher(self):
        """Test selecting the first available flasher."""
        available_flasher = Mock(spec=FlasherProtocol)
        available_flasher.check_available.return_value = True

        unavailable_flasher = Mock(spec=FlasherProtocol)
        unavailable_flasher.check_available.return_value = False

        configs: list[FlashMethodConfig] = [
            USBFlashConfig(device_query="removable=true"),
            DFUFlashConfig(vid="1234", pid="5678"),
        ]

        with patch(
            "glovebox.firmware.method_selector.flasher_registry"
        ) as mock_registry:
            mock_registry.create_method.side_effect = [
                unavailable_flasher,  # First config creates unavailable flasher
                available_flasher,  # Second config creates available flasher
            ]

            result = select_flasher_with_fallback(configs)

            assert result == available_flasher
            assert mock_registry.create_method.call_count == 2

    def test_select_flasher_no_fallback_needed(self):
        """Test selecting flasher when first option is available."""
        available_flasher = Mock(spec=FlasherProtocol)
        available_flasher.check_available.return_value = True

        configs: list[FlashMethodConfig] = [
            USBFlashConfig(device_query="removable=true")
        ]

        with patch(
            "glovebox.firmware.method_selector.flasher_registry"
        ) as mock_registry:
            mock_registry.create_method.return_value = available_flasher

            result = select_flasher_with_fallback(configs)

            assert result == available_flasher
            assert mock_registry.create_method.call_count == 1

    def test_select_flasher_all_unavailable(self):
        """Test error when all flashers are unavailable."""
        unavailable_flasher = Mock(spec=FlasherProtocol)
        unavailable_flasher.check_available.return_value = False

        configs: list[FlashMethodConfig] = [
            USBFlashConfig(device_query="removable=true"),
            DFUFlashConfig(vid="1234", pid="5678"),
        ]

        with patch(
            "glovebox.firmware.method_selector.flasher_registry"
        ) as mock_registry:
            mock_registry.create_method.return_value = unavailable_flasher
            mock_registry.get_available_methods.return_value = ["usb", "dfu"]

            with pytest.raises(FlasherNotAvailableError) as exc_info:
                select_flasher_with_fallback(configs)

            assert "No available flashers from 2 configurations" in str(exc_info.value)
            assert "Available methods: ['usb', 'dfu']" in str(exc_info.value)

    def test_select_flasher_creation_error(self):
        """Test handling of flasher creation errors."""
        available_flasher = Mock(spec=FlasherProtocol)
        available_flasher.check_available.return_value = True

        configs: list[FlashMethodConfig] = [
            USBFlashConfig(device_query="removable=true"),
            DFUFlashConfig(vid="1234", pid="5678"),
        ]

        with patch(
            "glovebox.firmware.method_selector.flasher_registry"
        ) as mock_registry:
            mock_registry.create_method.side_effect = [
                Exception("Creation failed"),  # First config fails
                available_flasher,  # Second config succeeds
            ]

            result = select_flasher_with_fallback(configs)

            assert result == available_flasher

    def test_get_flasher_with_fallback_chain(self):
        """Test building flasher fallback chain."""
        primary_config = USBFlashConfig(
            device_query="removable=true", fallback_methods=["dfu"]
        )

        configs = get_flasher_with_fallback_chain(primary_config)

        # Should return the config chain including primary + fallbacks
        assert len(configs) >= 1  # At least the primary config
        assert configs[0] == primary_config
        # Should include fallback config for "dfu" method if created successfully


class TestFallbackChainBuilding:
    """Tests for fallback chain building logic."""

    def test_compiler_chain_with_multiple_fallbacks(self):
        """Test building compiler chain with multiple fallback methods."""
        primary_config = DockerCompileConfig(fallback_methods=["local", "cross"])

        with patch(
            "glovebox.firmware.method_selector.compiler_registry"
        ) as mock_registry:
            mock_registry._config_types = {
                "local": LocalCompileConfig,
                "cross": type("CrossCompileConfig", (), {"method_type": "cross"}),
            }

            configs = get_compiler_with_fallback_chain(primary_config)

            assert len(configs) == 3
            assert configs[0] == primary_config
            assert configs[1].method_type == "local"
            assert configs[2].method_type == "cross"

    def test_flasher_chain_with_multiple_fallbacks(self):
        """Test building flasher chain with multiple fallback methods."""
        primary_config = USBFlashConfig(
            device_query="removable=true", fallback_methods=["dfu", "bootloader"]
        )

        with patch(
            "glovebox.firmware.method_selector.flasher_registry"
        ) as mock_registry:
            mock_registry._config_types = {
                "dfu": DFUFlashConfig,
                "bootloader": type(
                    "BootloaderFlashConfig", (), {"method_type": "bootloader"}
                ),
            }

            configs = get_flasher_with_fallback_chain(primary_config)

            assert len(configs) == 3
            assert configs[0] == primary_config
            assert configs[1].method_type == "dfu"
            assert configs[2].method_type == "bootloader"

    def test_chain_building_empty_fallbacks(self):
        """Test chain building with empty fallback methods."""
        primary_config = DockerCompileConfig(fallback_methods=[])

        configs = get_compiler_with_fallback_chain(primary_config)

        assert len(configs) == 1
        assert configs[0] == primary_config

    def test_chain_building_unknown_fallback_method(self):
        """Test chain building with unknown fallback method."""
        primary_config = DockerCompileConfig(fallback_methods=["unknown_method"])

        with patch(
            "glovebox.firmware.method_selector.compiler_registry"
        ) as mock_registry:
            mock_registry._config_types = {}  # Empty registry

            configs = get_compiler_with_fallback_chain(primary_config)

            # Should only include primary config, skip unknown fallback
            assert len(configs) == 1
            assert configs[0] == primary_config

    def test_chain_building_multiple_primary_configs(self):
        """Test chain building with multiple primary configs."""
        config1 = DockerCompileConfig(fallback_methods=["local"])
        config2 = LocalCompileConfig(
            zmk_path=Path("/opt/zmk"), fallback_methods=["cross"]
        )

        with patch(
            "glovebox.firmware.method_selector.compiler_registry"
        ) as mock_registry:
            mock_registry._config_types = {
                "local": LocalCompileConfig,
                "cross": type("CrossCompileConfig", (), {"method_type": "cross"}),
            }

            configs = get_compiler_with_fallback_chain([config1, config2])

            # Should include primaries and their fallbacks
            assert len(configs) == 4
            assert configs[0] == config1
            assert configs[1].method_type == "local"  # config1's fallback
            assert configs[2] == config2
            assert configs[3].method_type == "cross"  # config2's fallback


class TestIntegrationScenarios:
    """Tests for realistic integration scenarios."""

    def test_realistic_compiler_selection_scenario(self):
        """Test a realistic compiler selection scenario."""
        # Scenario: Docker unavailable, fall back to local
        configs = [
            DockerCompileConfig(image="custom:latest"),
            LocalCompileConfig(zmk_path=Path("/opt/zmk")),
        ]

        docker_compiler = Mock(spec=CompilerProtocol)
        docker_compiler.check_available.return_value = False  # Docker not available

        local_compiler = Mock(spec=CompilerProtocol)
        local_compiler.check_available.return_value = True  # Local available
        local_compiler.compile.return_value = BuildResult(success=True)

        with patch(
            "glovebox.firmware.method_selector.compiler_registry"
        ) as mock_registry:
            mock_registry.create_method.side_effect = [docker_compiler, local_compiler]

            selected_compiler = select_compiler_with_fallback(configs)

            assert selected_compiler == local_compiler

            # Test actual compilation
            result = selected_compiler.compile(
                Path("test.keymap"), Path("test.conf"), Path("output"), configs[1]
            )
            assert result.success is True

    def test_realistic_flasher_selection_scenario(self):
        """Test a realistic flasher selection scenario."""
        # Scenario: USB device not found, fall back to DFU
        configs = [
            USBFlashConfig(device_query="vendor=Adafruit"),
            DFUFlashConfig(vid="1234", pid="5678"),
        ]

        usb_flasher = Mock(spec=FlasherProtocol)
        usb_flasher.check_available.return_value = False  # USB not available

        dfu_flasher = Mock(spec=FlasherProtocol)
        dfu_flasher.check_available.return_value = True  # DFU available
        dfu_flasher.list_devices.return_value = [
            BlockDevice(
                name="dfu_device",
                device_node="/dev/dfu",
                serial="DFU123",
                vendor="Test",
                model="DFUDevice",
                removable=False,
            )
        ]

        with patch(
            "glovebox.firmware.method_selector.flasher_registry"
        ) as mock_registry:
            mock_registry.create_method.side_effect = [usb_flasher, dfu_flasher]

            selected_flasher = select_flasher_with_fallback(configs)

            assert selected_flasher == dfu_flasher

            # Test device listing
            devices = selected_flasher.list_devices(configs[1])
            assert len(devices) == 1
            assert devices[0].name == "dfu_device"

    def test_complex_fallback_chain_execution(self):
        """Test complex fallback chain execution."""
        # Complex scenario with multiple fallbacks
        primary_config = DockerCompileConfig(fallback_methods=["local", "cross"])

        # All methods are unavailable except the last one
        docker_compiler = Mock(spec=CompilerProtocol)
        docker_compiler.check_available.return_value = False

        local_compiler = Mock(spec=CompilerProtocol)
        local_compiler.check_available.return_value = False

        cross_compiler = Mock(spec=CompilerProtocol)
        cross_compiler.check_available.return_value = True

        with patch(
            "glovebox.firmware.method_selector.compiler_registry"
        ) as mock_registry:
            mock_registry._config_types = {
                "local": LocalCompileConfig,
                "cross": type("CrossCompileConfig", (), {"method_type": "cross"}),
            }
            mock_registry.create_method.side_effect = [
                docker_compiler,  # Primary fails
                local_compiler,  # First fallback fails
                cross_compiler,  # Second fallback succeeds
            ]

            # Build and test fallback chain
            fallback_configs = get_compiler_with_fallback_chain(primary_config)
            selected_compiler = select_compiler_with_fallback(fallback_configs)

            assert selected_compiler == cross_compiler
            assert mock_registry.create_method.call_count == 3


class TestFallbackConfigCreation:
    """Tests for enhanced fallback configuration creation."""

    def test_create_docker_config(self):
        """Test creating Docker compiler configuration."""
        config = _create_compiler_config_for_method("docker")

        assert isinstance(config, DockerCompileConfig)
        assert config.method_type == "docker"
        assert config.image == "moergo-zmk-build:latest"
        assert config.repository == "moergo-sc/zmk"
        assert config.branch == "main"

    def test_create_local_config(self):
        """Test creating local compiler configuration."""
        config = _create_compiler_config_for_method("local")

        assert isinstance(config, LocalCompileConfig)
        assert config.method_type == "local"
        assert isinstance(config.zmk_path, Path)
        # Should use either existing path or default to /opt/zmk

    def test_create_cross_config(self):
        """Test creating cross-compilation configuration."""
        config = _create_compiler_config_for_method("cross")

        assert isinstance(config, CrossCompileConfig)
        assert config.method_type == "cross"
        assert config.target_arch == "arm"
        assert config.sysroot == Path("/usr/arm-linux-gnueabihf")
        assert config.toolchain_prefix == "arm-linux-gnueabihf-"

    def test_create_qemu_config(self):
        """Test creating QEMU compiler configuration."""
        config = _create_compiler_config_for_method("qemu")

        assert isinstance(config, QemuCompileConfig)
        assert config.method_type == "qemu"
        assert config.qemu_target == "native_posix"

    def test_create_unknown_compiler_config(self):
        """Test creating configuration for unknown compiler method."""
        config = _create_compiler_config_for_method("unknown_method")

        assert config is None

    def test_create_usb_flash_config(self):
        """Test creating USB flasher configuration."""
        config = _create_flasher_config_for_method("usb")

        assert isinstance(config, USBFlashConfig)
        assert config.method_type == "usb"
        assert config.device_query == "removable=true"
        assert config.mount_timeout == 30
        assert config.copy_timeout == 60

    def test_create_dfu_flash_config(self):
        """Test creating DFU flasher configuration."""
        config = _create_flasher_config_for_method("dfu")

        assert isinstance(config, DFUFlashConfig)
        assert config.method_type == "dfu"
        assert config.vid == "0x239A"
        assert config.pid == "0x000C"
        assert config.interface == 0
        assert config.timeout == 30

    def test_create_bootloader_flash_config(self):
        """Test creating bootloader flasher configuration."""
        config = _create_flasher_config_for_method("bootloader")

        assert isinstance(config, BootloaderFlashConfig)
        assert config.method_type == "bootloader"
        assert config.protocol == "uart"
        assert config.baud_rate == 115200

    def test_create_wifi_flash_config(self):
        """Test creating WiFi flasher configuration."""
        config = _create_flasher_config_for_method("wifi")

        assert isinstance(config, WiFiFlashConfig)
        assert config.method_type == "wifi"
        assert config.host == "keyboard.local"
        assert config.port == 8080
        assert config.protocol == "http"

    def test_create_unknown_flasher_config(self):
        """Test creating configuration for unknown flasher method."""
        config = _create_flasher_config_for_method("unknown_method")

        assert config is None

    def test_create_compiler_fallback_configs(self):
        """Test creating multiple compiler fallback configurations."""
        fallback_methods = ["docker", "local", "cross", "unknown"]
        configs = _create_compiler_fallback_configs(fallback_methods)

        # Should create configs for known methods, skip unknown
        assert len(configs) == 3

        config_types = [type(config) for config in configs]
        assert DockerCompileConfig in config_types
        assert LocalCompileConfig in config_types
        assert CrossCompileConfig in config_types

    def test_create_flasher_fallback_configs(self):
        """Test creating multiple flasher fallback configurations."""
        fallback_methods = ["usb", "dfu", "bootloader", "unknown"]
        configs = _create_flasher_fallback_configs(fallback_methods)

        # Should create configs for known methods, skip unknown
        assert len(configs) == 3

        config_types = [type(config) for config in configs]
        assert USBFlashConfig in config_types
        assert DFUFlashConfig in config_types
        assert BootloaderFlashConfig in config_types

    def test_enhanced_fallback_chain_integration(self):
        """Test integration of enhanced fallback config creation."""
        # Primary config with multiple fallbacks including unknown method
        primary_config = DockerCompileConfig(
            fallback_methods=["local", "unknown_method", "cross", "qemu"]
        )

        compiler = Mock(spec=CompilerProtocol)
        compiler.check_available.return_value = True

        with patch(
            "glovebox.firmware.method_selector.compiler_registry"
        ) as mock_registry:
            mock_registry.create_method.return_value = compiler

            result = get_compiler_with_fallback_chain(primary_config)

            # The function now returns configs, not a compiler
            # Use select_compiler_with_fallback to get the compiler
            selected_compiler = select_compiler_with_fallback(result)
            assert selected_compiler == compiler
            # Should try primary + valid fallbacks (unknown method skipped)
            assert mock_registry.create_method.call_count >= 1
