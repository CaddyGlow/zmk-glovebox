"""Tests for flash protocol implementations."""

from pathlib import Path
from typing import Protocol, runtime_checkable
from unittest.mock import Mock

import pytest

from glovebox.config.flash_methods import FlashMethodConfig, USBFlashConfig
from glovebox.firmware.flash.models import BlockDevice, FlashResult
from glovebox.protocols.flash_protocols import FlasherProtocol


class TestFlasherProtocol:
    """Tests for FlasherProtocol interface."""

    def test_protocol_is_runtime_checkable(self):
        """Test that FlasherProtocol is runtime checkable."""
        assert hasattr(FlasherProtocol, "__instancecheck__")

        # Create a mock that implements the protocol
        mock_flasher = Mock()
        mock_flasher.flash_device = Mock(return_value=FlashResult(success=True))
        mock_flasher.list_devices = Mock(return_value=[])
        mock_flasher.check_available = Mock(return_value=True)
        mock_flasher.validate_config = Mock(return_value=True)

        # Runtime check should work
        assert isinstance(mock_flasher, FlasherProtocol)

    def test_protocol_methods_required(self):
        """Test that protocol methods are properly defined."""
        # Check that protocol has the expected methods
        assert hasattr(FlasherProtocol, "flash_device")
        assert hasattr(FlasherProtocol, "list_devices")
        assert hasattr(FlasherProtocol, "check_available")
        assert hasattr(FlasherProtocol, "validate_config")

    def test_incomplete_implementation_fails_check(self):
        """Test that incomplete implementations fail runtime check."""
        # Mock with missing methods
        incomplete_mock = Mock()
        incomplete_mock.flash_device = Mock()
        # Missing list_devices, check_available, and validate_config

        # Should not pass isinstance check
        assert not isinstance(incomplete_mock, FlasherProtocol)

    def test_method_signatures(self):
        """Test that protocol method signatures are correct."""

        # Create a proper implementation
        class TestFlasher:
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

        flasher = TestFlasher()
        assert isinstance(flasher, FlasherProtocol)

        # Test method calls
        device = BlockDevice(
            name="test_device",
            device_node="/dev/test",
            serial="12345",
            vendor="Test",
            model="TestDevice",
            removable=True,
        )

        result = flasher.flash_device(
            device=device,
            firmware_file=Path("firmware.uf2"),
            config=USBFlashConfig(device_query="removable=true"),
        )
        assert isinstance(result, FlashResult)

        devices = flasher.list_devices(USBFlashConfig(device_query="removable=true"))
        assert isinstance(devices, list)


class TestProtocolImplementation:
    """Tests for actual protocol implementation compliance."""

    def test_valid_flasher_implementation(self):
        """Test a valid flasher implementation."""

        class ValidFlasher:
            def __init__(self):
                self.available_devices = [
                    BlockDevice(
                        name="test_device",
                        device_node="/dev/test",
                        serial="12345",
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
                if device not in self.available_devices:
                    return FlashResult(success=False, errors=["Device not found"])

                if not firmware_file.exists():
                    return FlashResult(
                        success=False, errors=["Firmware file not found"]
                    )

                return FlashResult(
                    success=True,
                    messages=["Flash operation successful"],
                    devices_flashed=1,
                )

            def list_devices(self, config: FlashMethodConfig) -> list[BlockDevice]:
                return self.available_devices

            def check_available(self) -> bool:
                return True

            def validate_config(self, config: FlashMethodConfig) -> bool:
                return True

        flasher = ValidFlasher()
        assert isinstance(flasher, FlasherProtocol)

        # Test device listing
        devices = flasher.list_devices(USBFlashConfig(device_query="removable=true"))
        assert len(devices) == 1
        assert devices[0].name == "test_device"

        # Test successful flash (mock file existence)
        device = devices[0]
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(Path, "exists", lambda self: True)
            result = flasher.flash_device(
                device=device,
                firmware_file=Path("firmware.uf2"),
                config=USBFlashConfig(device_query="removable=true"),
            )
            assert result.success is True
            assert "Flash operation successful" in result.messages
            assert result.devices_flashed == 1

    def test_flasher_with_failure_states(self):
        """Test flasher implementation with various failure states."""

        class FailingFlasher:
            def __init__(self, has_devices=True):
                self.has_devices = has_devices
                self.devices = (
                    [
                        BlockDevice(
                            name="failing_device",
                            device_node="/dev/fail",
                            serial="FAIL123",
                            vendor="Fail",
                            model="FailDevice",
                            removable=True,
                        )
                    ]
                    if has_devices
                    else []
                )

            def flash_device(
                self,
                device: BlockDevice,
                firmware_file: Path,
                config: FlashMethodConfig,
            ) -> FlashResult:
                if not self.has_devices:
                    return FlashResult(success=False, errors=["No devices available"])

                # Simulate flash failure
                return FlashResult(
                    success=False, errors=["Flash operation failed"], devices_failed=1
                )

            def list_devices(self, config: FlashMethodConfig) -> list[BlockDevice]:
                return self.devices

            def check_available(self) -> bool:
                return True

            def validate_config(self, config: FlashMethodConfig) -> bool:
                return True

        # Test with no devices
        no_device_flasher = FailingFlasher(has_devices=False)
        assert isinstance(no_device_flasher, FlasherProtocol)

        devices = no_device_flasher.list_devices(USBFlashConfig(device_query="test"))
        assert len(devices) == 0

        # Test flash failure
        failing_flasher = FailingFlasher(has_devices=True)
        devices = failing_flasher.list_devices(USBFlashConfig(device_query="test"))
        assert len(devices) == 1

        result = failing_flasher.flash_device(
            device=devices[0],
            firmware_file=Path("firmware.uf2"),
            config=USBFlashConfig(device_query="test"),
        )
        assert result.success is False
        assert "Flash operation failed" in result.errors
        assert result.devices_failed == 1

    def test_protocol_type_checking(self):
        """Test that protocol enforces proper type checking."""

        class TypedFlasher:
            def flash_device(
                self,
                device: BlockDevice,
                firmware_file: Path,
                config: FlashMethodConfig,
            ) -> FlashResult:
                # Verify input types
                assert isinstance(device, BlockDevice)
                assert isinstance(firmware_file, Path)
                assert isinstance(config, FlashMethodConfig)

                return FlashResult(success=True)

            def list_devices(self, config: FlashMethodConfig) -> list[BlockDevice]:
                assert isinstance(config, FlashMethodConfig)
                return []

            def check_available(self) -> bool:
                return True

            def validate_config(self, config: FlashMethodConfig) -> bool:
                return True

        flasher = TypedFlasher()
        assert isinstance(flasher, FlasherProtocol)

        # Test with correct types
        device = BlockDevice(
            name="typed_device",
            device_node="/dev/typed",
            serial="TYPE123",
            vendor="Type",
            model="TypeDevice",
            removable=True,
        )

        result = flasher.flash_device(
            device=device,
            firmware_file=Path("firmware.uf2"),
            config=USBFlashConfig(device_query="test"),
        )
        assert result.success is True

        devices = flasher.list_devices(USBFlashConfig(device_query="test"))
        assert isinstance(devices, list)


class TestProtocolExtensibility:
    """Tests for protocol extensibility and inheritance."""

    def test_protocol_subclassing(self):
        """Test that protocols can be extended."""

        @runtime_checkable
        class ExtendedFlasherProtocol(FlasherProtocol, Protocol):
            def get_flash_info(self) -> dict[str, str]:
                """Get flasher information."""
                ...

            def check_device_compatibility(self, device: BlockDevice) -> bool:
                """Check if device is compatible."""
                ...

        class ExtendedFlasher:
            def flash_device(
                self,
                device: BlockDevice,
                firmware_file: Path,
                config: FlashMethodConfig,
            ) -> FlashResult:
                return FlashResult(success=True)

            def list_devices(self, config: FlashMethodConfig) -> list[BlockDevice]:
                return []

            def get_flash_info(self) -> dict[str, str]:
                return {"flasher": "extended", "version": "1.0.0"}

            def check_device_compatibility(self, device: BlockDevice) -> bool:
                return device.removable

            def check_available(self) -> bool:
                return True

            def validate_config(self, config: FlashMethodConfig) -> bool:
                return True

        flasher = ExtendedFlasher()
        assert isinstance(flasher, FlasherProtocol)
        assert isinstance(flasher, ExtendedFlasherProtocol)

        assert flasher.get_flash_info()["flasher"] == "extended"

        device = BlockDevice(
            name="test",
            device_node="/dev/test",
            serial="123",
            vendor="Test",
            model="Test",
            removable=True,
        )
        assert flasher.check_device_compatibility(device) is True

    def test_multiple_protocol_implementations(self):
        """Test that a class can implement multiple protocols."""

        @runtime_checkable
        class MonitoringProtocol(Protocol):
            def start_monitoring(self) -> bool:
                """Start device monitoring."""
                ...

            def stop_monitoring(self) -> bool:
                """Stop device monitoring."""
                ...

        class MonitoringFlasher:
            def __init__(self):
                self.monitoring = False

            def flash_device(
                self,
                device: BlockDevice,
                firmware_file: Path,
                config: FlashMethodConfig,
            ) -> FlashResult:
                return FlashResult(success=True)

            def list_devices(self, config: FlashMethodConfig) -> list[BlockDevice]:
                return []

            def start_monitoring(self) -> bool:
                self.monitoring = True
                return True

            def stop_monitoring(self) -> bool:
                self.monitoring = False
                return True

            def check_available(self) -> bool:
                return True

            def validate_config(self, config: FlashMethodConfig) -> bool:
                return True

        flasher = MonitoringFlasher()
        assert isinstance(flasher, FlasherProtocol)
        assert isinstance(flasher, MonitoringProtocol)

        # Test monitoring functionality
        assert flasher.start_monitoring() is True
        assert flasher.monitoring is True
        assert flasher.stop_monitoring() is True
        assert flasher.monitoring is False

    def test_device_filtering_implementation(self):
        """Test flasher implementation with device filtering."""

        class FilteringFlasher:
            def __init__(self):
                self.all_devices = [
                    BlockDevice(
                        name="removable_device",
                        device_node="/dev/removable",
                        serial="REM123",
                        vendor="Removable",
                        model="RemovableDevice",
                        removable=True,
                    ),
                    BlockDevice(
                        name="fixed_device",
                        device_node="/dev/fixed",
                        serial="FIX123",
                        vendor="Fixed",
                        model="FixedDevice",
                        removable=False,
                    ),
                ]

            def flash_device(
                self,
                device: BlockDevice,
                firmware_file: Path,
                config: FlashMethodConfig,
            ) -> FlashResult:
                compatible_devices = self.list_devices(config)
                if device not in compatible_devices:
                    return FlashResult(
                        success=False,
                        errors=["Device not compatible with configuration"],
                    )

                return FlashResult(success=True, devices_flashed=1)

            def list_devices(self, config: FlashMethodConfig) -> list[BlockDevice]:
                # Simple filtering based on config
                if isinstance(config, USBFlashConfig):
                    if "removable=true" in config.device_query:
                        return [d for d in self.all_devices if d.removable]
                    elif "removable=false" in config.device_query:
                        return [d for d in self.all_devices if not d.removable]

                return self.all_devices

            def check_available(self) -> bool:
                return True

            def validate_config(self, config: FlashMethodConfig) -> bool:
                return True

        flasher = FilteringFlasher()
        assert isinstance(flasher, FlasherProtocol)

        # Test removable device filtering
        removable_config = USBFlashConfig(device_query="removable=true")
        removable_devices = flasher.list_devices(removable_config)
        assert len(removable_devices) == 1
        assert removable_devices[0].removable is True

        # Test fixed device filtering
        fixed_config = USBFlashConfig(device_query="removable=false")
        fixed_devices = flasher.list_devices(fixed_config)
        assert len(fixed_devices) == 1
        assert fixed_devices[0].removable is False

        # Test compatibility checking in flash_device
        result = flasher.flash_device(
            device=removable_devices[0],
            firmware_file=Path("firmware.uf2"),
            config=removable_config,
        )
        assert result.success is True

        # Test incompatible device
        result = flasher.flash_device(
            device=fixed_devices[0],
            firmware_file=Path("firmware.uf2"),
            config=removable_config,  # Requires removable=true
        )
        assert result.success is False
        assert "Device not compatible" in result.errors[0]
