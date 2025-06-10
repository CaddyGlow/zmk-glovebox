"""Tests for method selection and fallback logic."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.config.compile_methods import (
    CompileMethodConfig,
    DockerCompileConfig,
    LocalCompileConfig,
)
from glovebox.config.flash_methods import (
    DFUFlashConfig,
    FlashMethodConfig,
    USBFlashConfig,
)
from glovebox.firmware.flash.models import BlockDevice, FlashResult
from glovebox.firmware.method_selector import (
    CompilerNotAvailableError,
    FlasherNotAvailableError,
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

        configs = [DockerCompileConfig(), LocalCompileConfig(zmk_path=Path("/opt/zmk"))]

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

        configs = [DockerCompileConfig()]

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

        configs = [DockerCompileConfig(), LocalCompileConfig(zmk_path=Path("/opt/zmk"))]

        with patch(
            "glovebox.firmware.method_selector.compiler_registry"
        ) as mock_registry:
            mock_registry.create_method.return_value = unavailable_compiler
            mock_registry.get_available_methods.return_value = ["docker", "local"]

            with pytest.raises(CompilerNotAvailableError) as exc_info:
                select_compiler_with_fallback(configs)

            assert "No available compilers from configs" in str(exc_info.value)
            assert "Available methods: ['docker', 'local']" in str(exc_info.value)

    def test_select_compiler_creation_error(self):
        """Test handling of compiler creation errors."""
        available_compiler = Mock(spec=CompilerProtocol)
        available_compiler.check_available.return_value = True

        configs = [DockerCompileConfig(), LocalCompileConfig(zmk_path=Path("/opt/zmk"))]

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

        configs = [DockerCompileConfig()]

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
        fallback_config = LocalCompileConfig(zmk_path=Path("/opt/zmk"))

        with patch(
            "glovebox.firmware.method_selector.compiler_registry"
        ) as mock_registry:
            # Mock the registry to return appropriate configs
            mock_registry._config_types = {"local": LocalCompileConfig}

            configs = get_compiler_with_fallback_chain([primary_config])

            assert len(configs) == 2
            assert configs[0] == primary_config
            assert isinstance(configs[1], LocalCompileConfig)
            assert configs[1].method_type == "local"


class TestFlasherSelection:
    """Tests for flasher selection logic."""

    def test_select_first_available_flasher(self):
        """Test selecting the first available flasher."""
        available_flasher = Mock(spec=FlasherProtocol)
        available_flasher.check_available.return_value = True

        unavailable_flasher = Mock(spec=FlasherProtocol)
        unavailable_flasher.check_available.return_value = False

        configs = [
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

        configs = [USBFlashConfig(device_query="removable=true")]

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

        configs = [
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

            assert "No available flashers from configs" in str(exc_info.value)
            assert "Available methods: ['usb', 'dfu']" in str(exc_info.value)

    def test_select_flasher_creation_error(self):
        """Test handling of flasher creation errors."""
        available_flasher = Mock(spec=FlasherProtocol)
        available_flasher.check_available.return_value = True

        configs = [
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

        with patch(
            "glovebox.firmware.method_selector.flasher_registry"
        ) as mock_registry:
            # Mock the registry to return appropriate configs
            mock_registry._config_types = {"dfu": DFUFlashConfig}

            configs = get_flasher_with_fallback_chain(primary_config)

            assert len(configs) == 2
            assert configs[0] == primary_config
            assert isinstance(configs[1], DFUFlashConfig)
            assert configs[1].method_type == "dfu"


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

            configs = get_compiler_with_fallback_chain([primary_config])

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

        configs = get_compiler_with_fallback_chain([primary_config])

        assert len(configs) == 1
        assert configs[0] == primary_config

    def test_chain_building_unknown_fallback_method(self):
        """Test chain building with unknown fallback method."""
        primary_config = DockerCompileConfig(fallback_methods=["unknown_method"])

        with patch(
            "glovebox.firmware.method_selector.compiler_registry"
        ) as mock_registry:
            mock_registry._config_types = {}  # Empty registry

            configs = get_compiler_with_fallback_chain([primary_config])

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
                path="/dev/dfu",
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
