"""Tests for refactored FlashService using multi-method architecture."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.config.flash_methods import DFUFlashConfig, USBFlashConfig
from glovebox.config.profile import KeyboardProfile
from glovebox.firmware.flash.models import BlockDevice, FlashResult
from glovebox.firmware.flash.service import FlashService, create_flash_service
from glovebox.protocols import FileAdapterProtocol
from glovebox.protocols.flash_protocols import FlasherProtocol


class TestFlashService:
    """Tests for the refactored FlashService."""

    def test_service_initialization(self):
        """Test FlashService initialization."""
        mock_file_adapter = Mock(spec=FileAdapterProtocol)
        service = FlashService(file_adapter=mock_file_adapter, loglevel="DEBUG")

        assert service._service_name == "FlashService"
        assert service._service_version == "2.0.0"
        assert service.file_adapter == mock_file_adapter
        assert service.loglevel == "DEBUG"

    def test_service_factory(self):
        """Test FlashService factory function."""
        service = create_flash_service(loglevel="INFO")

        assert isinstance(service, FlashService)
        assert service.loglevel == "INFO"
        assert service.file_adapter is not None

    @patch("glovebox.firmware.flash.service.select_flasher_with_fallback")
    def test_flash_success(self, mock_select_flasher):
        """Test successful flash operation."""
        # Mock flasher
        mock_flasher = Mock(spec=FlasherProtocol)
        mock_flasher.list_devices.return_value = [
            BlockDevice(
                name="test_device",
                path="/dev/test",
                serial="TEST123",
                vendor="Test",
                model="TestDevice",
                removable=True,
            )
        ]
        mock_flasher.flash_device.return_value = FlashResult(
            success=True, messages=["Flash successful"], devices_flashed=1
        )
        mock_select_flasher.return_value = mock_flasher

        # Mock file adapter
        mock_file_adapter = Mock(spec=FileAdapterProtocol)
        mock_file_adapter.check_exists.return_value = True

        service = FlashService(file_adapter=mock_file_adapter)

        result = service.flash(
            firmware_file=Path("firmware.uf2"), query="removable=true"
        )

        assert result.success is True
        assert result.devices_flashed == 1
        assert "Successfully flashed 1 device(s)" in result.messages
        mock_select_flasher.assert_called_once()
        mock_flasher.flash_device.assert_called_once()

    @patch("glovebox.firmware.flash.service.select_flasher_with_fallback")
    def test_flash_no_devices(self, mock_select_flasher):
        """Test flash operation when no devices are found."""
        # Mock flasher with no devices
        mock_flasher = Mock(spec=FlasherProtocol)
        mock_flasher.list_devices.return_value = []
        mock_select_flasher.return_value = mock_flasher

        mock_file_adapter = Mock(spec=FileAdapterProtocol)
        mock_file_adapter.check_exists.return_value = True

        service = FlashService(file_adapter=mock_file_adapter)

        result = service.flash(
            firmware_file=Path("firmware.uf2"), query="vendor=NotFound"
        )

        assert result.success is False
        assert "No compatible devices found" in result.errors

    @patch("glovebox.firmware.flash.service.select_flasher_with_fallback")
    def test_flash_device_failure(self, mock_select_flasher):
        """Test flash operation when device flashing fails."""
        # Mock flasher with failing device
        mock_flasher = Mock(spec=FlasherProtocol)
        mock_flasher.list_devices.return_value = [
            BlockDevice(
                name="failing_device",
                path="/dev/fail",
                serial="FAIL123",
                vendor="Fail",
                model="FailDevice",
                removable=True,
            )
        ]
        mock_flasher.flash_device.return_value = FlashResult(
            success=False, errors=["Flash operation failed"], devices_failed=1
        )
        mock_select_flasher.return_value = mock_flasher

        mock_file_adapter = Mock(spec=FileAdapterProtocol)
        mock_file_adapter.check_exists.return_value = True

        service = FlashService(file_adapter=mock_file_adapter)

        result = service.flash(firmware_file=Path("firmware.uf2"), count=1)

        assert result.success is False
        assert result.devices_failed == 1
        assert "1 device(s) failed to flash" in result.errors

    @patch("glovebox.firmware.flash.service.select_flasher_with_fallback")
    def test_flash_with_profile(self, mock_select_flasher):
        """Test flash operation with keyboard profile."""
        # Mock flasher
        mock_flasher = Mock(spec=FlasherProtocol)
        mock_flasher.list_devices.return_value = [
            BlockDevice(
                name="profile_device",
                path="/dev/profile",
                serial="PROF123",
                vendor="Profile",
                model="ProfileDevice",
                removable=True,
            )
        ]
        mock_flasher.flash_device.return_value = FlashResult(success=True)
        mock_select_flasher.return_value = mock_flasher

        # Mock profile with flash methods
        mock_profile = Mock(spec=KeyboardProfile)
        mock_profile.keyboard_config.flash_methods = [
            USBFlashConfig(device_query="vendor=Profile")
        ]

        mock_file_adapter = Mock(spec=FileAdapterProtocol)
        mock_file_adapter.check_exists.return_value = True

        service = FlashService(file_adapter=mock_file_adapter)

        result = service.flash(firmware_file=Path("firmware.uf2"), profile=mock_profile)

        assert result.success is True

        # Verify profile's flash methods were used
        call_args = mock_select_flasher.call_args[0]
        assert len(call_args[0]) == 1
        assert isinstance(call_args[0][0], USBFlashConfig)

    def test_flash_from_file_success(self):
        """Test flash_from_file method."""
        mock_file_adapter = Mock(spec=FileAdapterProtocol)
        mock_file_adapter.check_exists.return_value = True

        service = FlashService(file_adapter=mock_file_adapter)

        with patch.object(service, "flash") as mock_flash:
            mock_flash.return_value = FlashResult(success=True)

            result = service.flash_from_file(
                firmware_file_path=Path("firmware.uf2"),
                query="removable=true",
                timeout=120,
                count=2,
            )

            assert result.success is True
            mock_flash.assert_called_once_with(
                firmware_file=Path("firmware.uf2"),
                profile=None,
                query="removable=true",
                timeout=120,
                count=2,
                track_flashed=True,
                skip_existing=False,
            )

    def test_flash_from_file_not_found(self):
        """Test flash_from_file when firmware file doesn't exist."""
        mock_file_adapter = Mock(spec=FileAdapterProtocol)
        mock_file_adapter.check_exists.return_value = False

        service = FlashService(file_adapter=mock_file_adapter)

        result = service.flash_from_file(firmware_file_path=Path("nonexistent.uf2"))

        assert result.success is False
        assert "Firmware file not found" in result.errors[0]

    @patch("glovebox.firmware.flash.service.select_flasher_with_fallback")
    def test_list_devices_success(self, mock_select_flasher):
        """Test list_devices method."""
        # Mock flasher with devices
        mock_flasher = Mock(spec=FlasherProtocol)
        mock_flasher.list_devices.return_value = [
            BlockDevice(
                name="device1",
                path="/dev/device1",
                serial="DEV001",
                vendor="Vendor1",
                model="Model1",
                removable=True,
            ),
            BlockDevice(
                name="device2",
                path="/dev/device2",
                serial="DEV002",
                vendor="Vendor2",
                model="Model2",
                removable=False,
            ),
        ]
        mock_select_flasher.return_value = mock_flasher

        service = FlashService()

        result = service.list_devices(query="all")

        assert result.success is True
        assert "Found 2 device(s) matching query" in result.messages
        assert len(result.device_details) == 2

        # Check device details
        device_info = result.device_details[0]
        assert device_info["name"] == "device1"
        assert device_info["serial"] == "DEV001"
        assert device_info["vendor"] == "Vendor1"
        assert device_info["removable"] is True

    @patch("glovebox.firmware.flash.service.select_flasher_with_fallback")
    def test_list_devices_no_devices(self, mock_select_flasher):
        """Test list_devices when no devices are found."""
        mock_flasher = Mock(spec=FlasherProtocol)
        mock_flasher.list_devices.return_value = []
        mock_select_flasher.return_value = mock_flasher

        service = FlashService()

        result = service.list_devices(query="nonexistent")

        assert result.success is True
        assert "No devices found matching query" in result.messages
        assert len(result.device_details) == 0

    def test_get_flash_method_configs_with_profile(self):
        """Test _get_flash_method_configs with profile."""
        service = FlashService()

        # Mock profile with flash methods
        mock_profile = Mock(spec=KeyboardProfile)
        mock_profile.keyboard_config.flash_methods = [
            USBFlashConfig(device_query="profile query"),
            DFUFlashConfig(vid="1234", pid="5678"),
        ]

        configs = service._get_flash_method_configs(mock_profile, "")

        assert len(configs) == 2
        assert isinstance(configs[0], USBFlashConfig)
        assert configs[0].device_query == "profile query"
        assert isinstance(configs[1], DFUFlashConfig)

    def test_get_flash_method_configs_without_profile(self):
        """Test _get_flash_method_configs without profile."""
        service = FlashService()

        configs = service._get_flash_method_configs(None, "custom query")

        assert len(configs) == 1
        config = configs[0]
        assert isinstance(config, USBFlashConfig)
        assert config.device_query == "custom query"

    def test_get_flash_method_configs_default_fallback(self):
        """Test _get_flash_method_configs with default fallback."""
        service = FlashService()

        configs = service._get_flash_method_configs(None, "")

        assert len(configs) == 1
        config = configs[0]
        assert isinstance(config, USBFlashConfig)
        assert config.device_query == "removable=true"  # Default fallback

    def test_get_device_query_from_profile(self):
        """Test _get_device_query_from_profile method."""
        service = FlashService()

        # Mock profile with flash config
        mock_flash_config = Mock()
        mock_flash_config.query = "profile query"
        mock_flash_config.usb_vid = "1234"
        mock_flash_config.usb_pid = "5678"

        mock_profile = Mock(spec=KeyboardProfile)
        mock_profile.keyboard_config.flash = mock_flash_config

        # Test with query
        query = service._get_device_query_from_profile(mock_profile)
        assert query == "profile query"

        # Test with VID/PID when no query
        mock_flash_config.query = None
        query = service._get_device_query_from_profile(mock_profile)
        assert "vid=1234" in query
        assert "pid=5678" in query
        assert "removable=true" in query

    def test_get_device_query_from_profile_no_profile(self):
        """Test _get_device_query_from_profile with no profile."""
        service = FlashService()

        query = service._get_device_query_from_profile(None)
        assert query == "removable=true"


class TestFlashServiceIntegration:
    """Integration tests for FlashService with method selection."""

    @patch("glovebox.firmware.flash.service.select_flasher_with_fallback")
    def test_full_flash_workflow(self, mock_select_flasher):
        """Test full flash workflow with realistic data."""
        # Create realistic flasher mock
        test_device = BlockDevice(
            name="Glove80 Left",
            path="/dev/disk2",
            serial="GLV80-L-123456",
            vendor="Adafruit",
            model="Glove80",
            removable=True,
        )

        mock_flasher = Mock(spec=FlasherProtocol)
        mock_flasher.list_devices.return_value = [test_device]
        mock_flasher.flash_device.return_value = FlashResult(
            success=True,
            messages=[
                "Device mounted successfully",
                "Firmware copied",
                "Flash completed",
            ],
            devices_flashed=1,
        )
        mock_select_flasher.return_value = mock_flasher

        mock_file_adapter = Mock(spec=FileAdapterProtocol)
        mock_file_adapter.check_exists.return_value = True

        service = FlashService(file_adapter=mock_file_adapter, loglevel="DEBUG")

        # Mock realistic profile
        mock_profile = Mock(spec=KeyboardProfile)
        mock_profile.keyboard_config.flash_methods = [
            USBFlashConfig(
                device_query="vendor=Adafruit and serial~=GLV80-.* and removable=true",
                mount_timeout=30,
                copy_timeout=60,
                sync_after_copy=True,
            )
        ]

        result = service.flash_from_file(
            firmware_file_path=Path("glove80.uf2"), profile=mock_profile, count=1
        )

        assert result.success is True
        assert result.devices_flashed == 1
        assert "Successfully flashed 1 device(s)" in result.messages

        # Verify device details are captured
        assert len(result.device_details) == 1
        device_detail = result.device_details[0]
        assert device_detail["name"] == "Glove80 Left"
        assert device_detail["serial"] == "GLV80-L-123456"
        assert device_detail["status"] == "success"

    @patch("glovebox.firmware.flash.service.select_flasher_with_fallback")
    def test_fallback_scenario(self, mock_select_flasher):
        """Test fallback scenario where primary method fails."""
        # Mock the selection to simulate fallback
        usb_flasher = Mock(spec=FlasherProtocol)
        usb_flasher.list_devices.return_value = []  # No USB devices

        dfu_flasher = Mock(spec=FlasherProtocol)
        dfu_flasher.list_devices.return_value = [
            BlockDevice(
                name="DFU Device",
                path="/dev/dfu",
                serial="DFU123",
                vendor="DFU",
                model="DFUDevice",
                removable=False,
            )
        ]
        dfu_flasher.flash_device.return_value = FlashResult(
            success=True, messages=["DFU flash successful"]
        )

        # Mock select_flasher to return the fallback flasher
        mock_select_flasher.return_value = dfu_flasher

        mock_file_adapter = Mock(spec=FileAdapterProtocol)
        mock_file_adapter.check_exists.return_value = True

        service = FlashService(file_adapter=mock_file_adapter)

        # Profile with fallback methods
        mock_profile = Mock(spec=KeyboardProfile)
        mock_profile.keyboard_config.flash_methods = [
            USBFlashConfig(device_query="removable=true"),  # Primary (no devices)
            DFUFlashConfig(vid="1234", pid="5678"),  # Fallback (has devices)
        ]

        result = service.flash(firmware_file=Path("firmware.uf2"), profile=mock_profile)

        assert result.success is True

        # Verify both configs were passed to selector
        call_args = mock_select_flasher.call_args[0]
        assert len(call_args[0]) == 2

    @patch("glovebox.firmware.flash.service.select_flasher_with_fallback")
    def test_multiple_device_flash(self, mock_select_flasher):
        """Test flashing multiple devices."""
        devices = [
            BlockDevice(
                name="Device 1",
                path="/dev/device1",
                serial="DEV001",
                vendor="Test",
                model="Test1",
                removable=True,
            ),
            BlockDevice(
                name="Device 2",
                path="/dev/device2",
                serial="DEV002",
                vendor="Test",
                model="Test2",
                removable=True,
            ),
        ]

        mock_flasher = Mock(spec=FlasherProtocol)
        mock_flasher.list_devices.return_value = devices
        mock_flasher.flash_device.side_effect = [
            FlashResult(success=True),  # First device succeeds
            FlashResult(success=False, errors=["Flash failed"]),  # Second device fails
        ]
        mock_select_flasher.return_value = mock_flasher

        mock_file_adapter = Mock(spec=FileAdapterProtocol)
        mock_file_adapter.check_exists.return_value = True

        service = FlashService(file_adapter=mock_file_adapter)

        result = service.flash(
            firmware_file=Path("firmware.uf2"),
            count=2,  # Flash 2 devices
        )

        assert result.success is False  # Overall failure due to one failed device
        assert result.devices_flashed == 1
        assert result.devices_failed == 1
        assert "1 device(s) failed to flash" in result.errors

        # Check device details
        assert len(result.device_details) == 2
        assert result.device_details[0]["status"] == "success"
        assert result.device_details[1]["status"] == "failed"
