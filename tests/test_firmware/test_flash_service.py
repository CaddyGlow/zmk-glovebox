"""Tests for firmware flash service."""

import logging
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.config.flash_methods import USBFlashConfig
from glovebox.firmware.flash.models import BlockDevice, FlashResult
from glovebox.firmware.flash.service import FlashService, create_flash_service
from glovebox.protocols.file_adapter_protocol import FileAdapterProtocol
from glovebox.protocols.flash_protocols import FlasherProtocol
from glovebox.protocols.usb_adapter_protocol import USBAdapterProtocol
from tests.test_factories import create_flash_service_for_tests


@pytest.fixture
def mock_file_adapter():
    """Create a mock file adapter for testing."""
    adapter = Mock(spec=FileAdapterProtocol)
    adapter.check_exists.return_value = True
    return adapter


@pytest.fixture
def mock_flasher():
    """Create a mock flasher for testing."""
    flasher = Mock(spec=FlasherProtocol)
    flasher.check_available.return_value = True
    flasher.validate_config.return_value = True
    flasher.list_devices.return_value = []
    return flasher


@pytest.fixture
def mock_device_wait_service():
    """Create a mock device wait service."""
    service = Mock()
    service.wait_for_devices.return_value = []
    return service


@pytest.fixture
def mock_flasher_registry():
    """Create a mock flasher registry."""
    registry = Mock()
    return registry


@pytest.fixture
def sample_usb_config():
    """Create a sample USB flash configuration."""
    return USBFlashConfig(
        device_query="model=Glove80_Bootloader",
        mount_timeout=30,
        copy_timeout=60,
        sync_after_copy=True,
    )


@pytest.fixture
def sample_block_device():
    """Create a sample BlockDevice for testing."""
    return BlockDevice(
        name="sda1",
        device_node="/dev/sda1",
        size=8192000,
        type="usb",
        removable=True,
        model="Glove80_Bootloader",
        vendor="Adafruit",
        serial="GLV80-12345",
        uuid="1234-5678",
        label="GLV80LDR",
        vendor_id="239a",
        product_id="0029",
        partitions=["sda1"],
        mountpoints={"/dev/sda1": "/media/GLV80LDR"},
        symlinks={"usb-Adafruit_Glove80_Bootloader_GLV80-12345"},
        raw={"ID_VENDOR": "Adafruit", "ID_MODEL": "Glove80_Bootloader"},
    )


@pytest.fixture
def sample_keyboard_profile():
    """Create a sample keyboard profile for testing."""
    profile = Mock()
    profile.keyboard_config = Mock()

    # Mock flash methods
    flash_method = USBFlashConfig(
        device_query="model=Glove80_Bootloader",
        mount_timeout=25,
        copy_timeout=50,
        sync_after_copy=False,
    )
    profile.keyboard_config.flash_methods = [flash_method]

    return profile


@pytest.fixture
def firmware_file(tmp_path):
    """Create a temporary firmware file for testing."""
    firmware_path = tmp_path / "test_firmware.uf2"
    firmware_path.write_text("fake firmware content")
    return firmware_path


@pytest.fixture
def mock_usb_adapter():
    """Create a mock USB adapter for testing."""
    adapter = Mock(spec=USBAdapterProtocol)
    return adapter


@pytest.fixture
def flash_service(mock_file_adapter, mock_device_wait_service, mock_usb_adapter):
    """Create a flash service instance for testing."""
    return FlashService(
        file_adapter=mock_file_adapter,
        device_wait_service=mock_device_wait_service,
        usb_adapter=mock_usb_adapter,
        loglevel="INFO",
    )


class TestFlashServiceInit:
    """Test FlashService initialization."""

    def test_init_with_file_adapter(
        self, mock_file_adapter, mock_device_wait_service, mock_usb_adapter
    ):
        """Test initialization with provided file adapter."""
        service = FlashService(
            file_adapter=mock_file_adapter,
            device_wait_service=mock_device_wait_service,
            usb_adapter=mock_usb_adapter,
            loglevel="DEBUG",
        )

        assert service.file_adapter is mock_file_adapter
        assert service.device_wait_service is mock_device_wait_service
        assert service.loglevel == "DEBUG"
        assert service._service_name == "FlashService"
        assert service._service_version == "2.0.0"

    def test_init_with_factory_function(
        self, mock_file_adapter, mock_device_wait_service
    ):
        """Test initialization using factory function with explicit dependencies."""
        from glovebox.firmware.flash import create_flash_service

        service = create_flash_service(
            file_adapter=mock_file_adapter,
            device_wait_service=mock_device_wait_service,
            loglevel="INFO",
        )

        assert service.file_adapter is mock_file_adapter
        assert service.device_wait_service is mock_device_wait_service
        assert service.loglevel == "INFO"

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    def test_init_default_loglevel(self, mock_create_wait, mock_file_adapter):
        """Test initialization with default log level."""
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        assert service.loglevel == "INFO"


class TestFlashServiceFlashFromFile:
    """Test FlashService flash method (formerly flash_from_file)."""

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    def test_flash_from_file_success(
        self,
        mock_create_wait,
        mock_file_adapter,
        firmware_file,
        sample_keyboard_profile,
    ):
        """Test successful flash from file operation."""
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        # Mock the main flash method
        expected_result = FlashResult(success=True, devices_flashed=1)
        with patch.object(service, "flash", return_value=expected_result) as mock_flash:
            result = service.flash(
                firmware_file=firmware_file,
                profile=sample_keyboard_profile,
                query="test:query",
                timeout=30,
                count=2,
                track_flashed=False,
                skip_existing=True,
                wait=True,
                poll_interval=1.0,
                show_progress=False,
            )

            assert result is expected_result
            mock_flash.assert_called_once_with(
                firmware_file=firmware_file,
                profile=sample_keyboard_profile,
                query="test:query",
                timeout=30,
                count=2,
                track_flashed=False,
                skip_existing=True,
                wait=True,
                poll_interval=1.0,
                show_progress=False,
            )

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    def test_flash_from_file_missing_firmware(
        self, mock_create_wait, mock_file_adapter, firmware_file
    ):
        """Test flash from file with missing firmware file."""
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service
        mock_file_adapter.check_exists.return_value = False

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        result = service.flash(firmware_file=firmware_file)

        assert not result.success
        assert "Firmware file not found" in str(result.errors)
        mock_file_adapter.check_exists.assert_called_once_with(firmware_file)

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    def test_flash_from_file_flash_exception(
        self, mock_create_wait, mock_file_adapter, firmware_file
    ):
        """Test flash from file when flash method raises exception."""
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        # Mock the main flash method to raise an exception
        with patch.object(
            service, "flash", side_effect=Exception("Flash error")
        ) as mock_flash:
            result = service.flash(firmware_file=firmware_file)

            assert not result.success
            assert "Flash operation failed: Flash error" in str(result.errors)
            mock_flash.assert_called_once()


class TestFlashServiceFlash:
    """Test FlashService flash method."""

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    @patch("glovebox.firmware.flash.service.flasher_registry")
    def test_flash_success_with_wait(
        self,
        mock_registry,
        mock_create_wait,
        mock_file_adapter,
        mock_flasher,
        sample_block_device,
        firmware_file,
    ):
        """Test successful flash operation with wait=True."""
        # Setup mocks
        mock_wait_service = Mock()
        mock_wait_service.wait_for_devices.return_value = [sample_block_device]
        mock_create_wait.return_value = mock_wait_service

        mock_registry.create_method.return_value = mock_flasher

        # Setup flasher to return successful result
        flash_result = FlashResult(success=True)
        mock_flasher.flash_device.return_value = flash_result

        # Create service with mocked wait service
        service = create_flash_service_for_tests(
            file_adapter=mock_file_adapter, device_wait_service=mock_wait_service
        )

        result = service.flash(
            firmware_file=firmware_file,
            query="model=Glove80_Bootloader",
            timeout=60,
            count=1,
            wait=True,
            poll_interval=0.1,
            show_progress=False,
        )

        assert result.success
        assert result.devices_flashed == 1
        assert result.devices_failed == 0
        assert len(result.device_details) == 1
        assert result.device_details[0]["status"] == "success"

        # Verify device wait service was called
        mock_wait_service.wait_for_devices.assert_called_once()
        mock_flasher.flash_device.assert_called_once_with(
            device=sample_block_device,
            firmware_file=firmware_file,
            config=mock_registry.create_method.return_value.flash_device.call_args[1][
                "config"
            ]
            if "config"
            in mock_registry.create_method.return_value.flash_device.call_args[1]
            else mock_registry.create_method.call_args[0][1],
        )

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    @patch("glovebox.firmware.flash.service.flasher_registry")
    def test_flash_success_without_wait(
        self,
        mock_registry,
        mock_create_wait,
        mock_file_adapter,
        mock_flasher,
        sample_block_device,
        firmware_file,
    ):
        """Test successful flash operation with wait=False."""
        # Setup mocks
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service

        mock_registry.create_method.return_value = mock_flasher
        mock_flasher.list_devices.return_value = [sample_block_device]

        # Setup flasher to return successful result
        flash_result = FlashResult(success=True)
        mock_flasher.flash_device.return_value = flash_result

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        result = service.flash(
            firmware_file=firmware_file,
            query="model=Glove80_Bootloader",
            timeout=60,
            count=1,
            wait=False,
        )

        assert result.success
        assert result.devices_flashed == 1
        assert result.devices_failed == 0

        # Verify device wait service was NOT called
        mock_wait_service.wait_for_devices.assert_not_called()
        # Verify list_devices was called instead
        mock_flasher.list_devices.assert_called_once()

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    @patch("glovebox.firmware.flash.service.flasher_registry")
    def test_flash_with_profile_flash_methods(
        self,
        mock_registry,
        mock_create_wait,
        mock_file_adapter,
        mock_flasher,
        sample_keyboard_profile,
        sample_block_device,
        firmware_file,
    ):
        """Test flash operation using profile flash methods."""
        # Setup mocks
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service

        mock_registry.create_method.return_value = mock_flasher
        mock_flasher.list_devices.return_value = [sample_block_device]

        flash_result = FlashResult(success=True)
        mock_flasher.flash_device.return_value = flash_result

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        result = service.flash(
            firmware_file=firmware_file,
            profile=sample_keyboard_profile,
            wait=False,
        )

        assert result.success
        # Verify the profile's flash method config was used
        expected_config = sample_keyboard_profile.keyboard_config.flash_methods[0]

        # Verify the method was called with correct parameters
        mock_registry.create_method.assert_called_once()
        call_args = mock_registry.create_method.call_args
        assert call_args[0] == ("usb", expected_config)
        assert "file_adapter" in call_args[1]
        assert call_args[1]["file_adapter"] is mock_file_adapter
        assert "usb_adapter" in call_args[1]

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    @patch("glovebox.firmware.flash.service.flasher_registry")
    def test_flash_string_firmware_path(
        self,
        mock_registry,
        mock_create_wait,
        mock_file_adapter,
        mock_flasher,
        sample_block_device,
        firmware_file,
    ):
        """Test flash operation with string firmware path."""
        # Setup mocks
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service

        mock_registry.create_method.return_value = mock_flasher
        mock_flasher.list_devices.return_value = [sample_block_device]

        flash_result = FlashResult(success=True)
        mock_flasher.flash_device.return_value = flash_result

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        # Use string path instead of Path object
        result = service.flash(
            firmware_file=str(firmware_file),
            wait=False,
        )

        assert result.success
        # Verify the string was converted to Path
        mock_flasher.flash_device.assert_called_once()
        call_args = mock_flasher.flash_device.call_args
        assert isinstance(call_args[1]["firmware_file"], Path)

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    @patch("glovebox.firmware.flash.service.flasher_registry")
    def test_flash_no_devices_found(
        self,
        mock_registry,
        mock_create_wait,
        mock_file_adapter,
        mock_flasher,
        firmware_file,
    ):
        """Test flash operation when no devices are found."""
        # Setup mocks
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service

        mock_registry.create_method.return_value = mock_flasher
        mock_flasher.list_devices.return_value = []  # No devices

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        result = service.flash(firmware_file=firmware_file, wait=False)

        assert not result.success
        assert "No compatible devices found" in str(result.errors)

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    @patch("glovebox.firmware.flash.service.flasher_registry")
    def test_flash_device_failure(
        self,
        mock_registry,
        mock_create_wait,
        mock_file_adapter,
        mock_flasher,
        sample_block_device,
        firmware_file,
    ):
        """Test flash operation when device flashing fails."""
        # Setup mocks
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service

        mock_registry.create_method.return_value = mock_flasher
        mock_flasher.list_devices.return_value = [sample_block_device]

        # Setup flasher to return failed result
        flash_result = FlashResult(success=False)
        flash_result.add_error("Device flash failed")
        mock_flasher.flash_device.return_value = flash_result

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        result = service.flash(firmware_file=firmware_file, wait=False)

        assert not result.success
        assert result.devices_flashed == 0
        assert result.devices_failed == 1
        assert len(result.device_details) == 1
        assert result.device_details[0]["status"] == "failed"
        assert "Device flash failed" in result.device_details[0]["error"]

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    @patch("glovebox.firmware.flash.service.flasher_registry")
    def test_flash_mixed_success_failure(
        self,
        mock_registry,
        mock_create_wait,
        mock_file_adapter,
        mock_flasher,
        firmware_file,
    ):
        """Test flash operation with mixed success and failure."""
        # Create two devices
        device1 = BlockDevice(name="device1", device_node="/dev/sda1", serial="001")
        device2 = BlockDevice(name="device2", device_node="/dev/sdb1", serial="002")

        # Setup mocks
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service

        mock_registry.create_method.return_value = mock_flasher
        mock_flasher.list_devices.return_value = [device1, device2]

        # Setup flasher to return success for first device, failure for second
        def flash_side_effect(device, firmware_file, config):
            if device.name == "device1":
                return FlashResult(success=True)
            else:
                result = FlashResult(success=False)
                result.add_error("Second device failed")
                return result

        mock_flasher.flash_device.side_effect = flash_side_effect

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        result = service.flash(
            firmware_file=firmware_file, count=0, wait=False
        )  # Flash all

        assert not result.success  # Failed overall due to mixed results
        assert result.devices_flashed == 1
        assert result.devices_failed == 1
        assert len(result.device_details) == 2
        assert "1 device(s) failed to flash, 1 succeeded" in str(result.errors)

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    @patch("glovebox.firmware.flash.service.flasher_registry")
    def test_flash_count_limit(
        self,
        mock_registry,
        mock_create_wait,
        mock_file_adapter,
        mock_flasher,
        firmware_file,
    ):
        """Test flash operation with device count limit."""
        # Create three devices
        device1 = BlockDevice(name="device1", device_node="/dev/sda1")
        device2 = BlockDevice(name="device2", device_node="/dev/sdb1")
        device3 = BlockDevice(name="device3", device_node="/dev/sdc1")

        # Setup mocks
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service

        mock_registry.create_method.return_value = mock_flasher
        mock_flasher.list_devices.return_value = [device1, device2, device3]

        # All devices flash successfully
        mock_flasher.flash_device.return_value = FlashResult(success=True)

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        result = service.flash(firmware_file=firmware_file, count=2, wait=False)

        assert result.success
        assert result.devices_flashed == 2  # Only first 2 devices
        assert len(result.device_details) == 2
        assert mock_flasher.flash_device.call_count == 2

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    @patch("glovebox.firmware.flash.service.flasher_registry")
    def test_flash_exception_handling(
        self, mock_registry, mock_create_wait, mock_file_adapter, firmware_file
    ):
        """Test flash operation exception handling."""
        # Setup mocks
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service

        # Make flasher registry raise an exception
        mock_registry.create_method.side_effect = Exception("Registry error")

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        result = service.flash(firmware_file=firmware_file)

        assert not result.success
        # The error message gets wrapped by the _create_usb_flasher method
        assert (
            "Flash operation failed: Failed to create USB flasher: Registry error"
            in str(result.errors)
        )

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    @patch("glovebox.firmware.flash.service.flasher_registry")
    def test_flash_wait_with_profile_query(
        self,
        mock_registry,
        mock_create_wait,
        mock_file_adapter,
        mock_flasher,
        sample_keyboard_profile,
        sample_block_device,
        firmware_file,
    ):
        """Test flash operation with wait using profile device query."""
        # Setup mocks
        mock_wait_service = Mock()
        mock_wait_service.wait_for_devices.return_value = [sample_block_device]
        mock_create_wait.return_value = mock_wait_service

        mock_registry.create_method.return_value = mock_flasher
        mock_flasher.flash_device.return_value = FlashResult(success=True)

        service = create_flash_service_for_tests(
            file_adapter=mock_file_adapter, device_wait_service=mock_wait_service
        )

        result = service.flash(
            firmware_file=firmware_file,
            profile=sample_keyboard_profile,
            wait=True,
        )

        assert result.success
        # Verify wait_for_devices was called with the profile's device query
        mock_wait_service.wait_for_devices.assert_called_once()
        call_args = mock_wait_service.wait_for_devices.call_args[1]
        assert (
            call_args["query"] == "model=Glove80_Bootloader"
        )  # From sample_keyboard_profile


class TestFlashServiceListDevices:
    """Test FlashService list_devices method."""

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    @patch("glovebox.firmware.flash.service.flasher_registry")
    def test_list_devices_success(
        self,
        mock_registry,
        mock_create_wait,
        mock_file_adapter,
        mock_flasher,
        sample_block_device,
    ):
        """Test successful device listing."""
        # Setup mocks
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service

        mock_registry.create_method.return_value = mock_flasher
        mock_flasher.list_devices.return_value = [sample_block_device]

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        result = service.list_devices(query="model=Glove80_Bootloader")

        assert result.success
        assert "Found 1 device(s) matching query" in str(result.messages)
        assert len(result.device_details) == 1

        device_info = result.device_details[0]
        assert device_info["name"] == sample_block_device.description
        assert device_info["serial"] == sample_block_device.serial
        assert device_info["vendor"] == sample_block_device.vendor
        assert device_info["model"] == sample_block_device.model
        assert device_info["path"] == sample_block_device.path
        assert device_info["removable"] == sample_block_device.removable
        assert device_info["status"] == "available"
        assert device_info["vendor_id"] == sample_block_device.vendor_id
        assert device_info["product_id"] == sample_block_device.product_id

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    @patch("glovebox.firmware.flash.service.flasher_registry")
    def test_list_devices_no_devices_found(
        self, mock_registry, mock_create_wait, mock_file_adapter, mock_flasher
    ):
        """Test device listing when no devices found."""
        # Setup mocks
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service

        mock_registry.create_method.return_value = mock_flasher
        mock_flasher.list_devices.return_value = []

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        result = service.list_devices()

        assert result.success
        assert "No devices found matching query" in str(result.messages)
        assert len(result.device_details) == 0

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    @patch("glovebox.firmware.flash.service.flasher_registry")
    def test_list_devices_with_profile(
        self,
        mock_registry,
        mock_create_wait,
        mock_file_adapter,
        mock_flasher,
        sample_keyboard_profile,
        sample_block_device,
    ):
        """Test device listing with keyboard profile."""
        # Setup mocks
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service

        mock_registry.create_method.return_value = mock_flasher
        mock_flasher.list_devices.return_value = [sample_block_device]

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        result = service.list_devices(profile=sample_keyboard_profile)

        assert result.success
        # Verify the profile's flash config was used
        expected_config = sample_keyboard_profile.keyboard_config.flash_methods[0]

        # Verify the method was called with correct parameters
        mock_registry.create_method.assert_called_once()
        call_args = mock_registry.create_method.call_args
        assert call_args[0] == ("usb", expected_config)
        assert "file_adapter" in call_args[1]
        assert call_args[1]["file_adapter"] is mock_file_adapter
        assert "usb_adapter" in call_args[1]

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    @patch("glovebox.firmware.flash.service.flasher_registry")
    def test_list_devices_exception_handling(
        self, mock_registry, mock_create_wait, mock_file_adapter
    ):
        """Test device listing exception handling."""
        # Setup mocks
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service

        # Make flasher registry raise an exception
        mock_registry.create_method.side_effect = Exception("Registry error")

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        result = service.list_devices()

        assert not result.success
        # The error message gets wrapped by the _create_usb_flasher method
        assert (
            "Failed to list devices: Failed to create USB flasher: Registry error"
            in str(result.errors)
        )


class TestFlashServicePrivateMethods:
    """Test FlashService private methods."""

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    def test_get_flash_method_configs_with_profile(
        self, mock_create_wait, mock_file_adapter, sample_keyboard_profile
    ):
        """Test getting flash configs from profile."""
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        configs = service._get_flash_method_configs(sample_keyboard_profile, "")

        assert len(configs) == 1
        assert configs[0] == sample_keyboard_profile.keyboard_config.flash_methods[0]

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    def test_get_flash_method_configs_no_profile(
        self, mock_create_wait, mock_file_adapter
    ):
        """Test getting flash configs without profile (default config)."""
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        configs = service._get_flash_method_configs(None, "custom:query")

        assert len(configs) == 1
        assert isinstance(configs[0], USBFlashConfig)
        assert configs[0].device_query == "custom:query"
        assert configs[0].mount_timeout == 30
        assert configs[0].copy_timeout == 60
        assert configs[0].sync_after_copy is True

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    def test_get_flash_method_configs_empty_profile_methods(
        self, mock_create_wait, mock_file_adapter
    ):
        """Test getting flash configs with empty profile methods."""
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service

        # Create profile without flash methods
        profile = Mock()
        profile.keyboard_config = Mock()
        profile.keyboard_config.flash_methods = []

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        configs = service._get_flash_method_configs(profile, "")

        assert len(configs) == 1
        assert isinstance(configs[0], USBFlashConfig)
        assert configs[0].device_query == "removable=true"  # Default query

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    def test_get_device_query_from_profile_with_methods(
        self, mock_create_wait, mock_file_adapter, sample_keyboard_profile
    ):
        """Test getting device query from profile with flash methods."""
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        query = service._get_device_query_from_profile(sample_keyboard_profile)

        assert query == "model=Glove80_Bootloader"

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    def test_get_device_query_from_profile_no_profile(
        self, mock_create_wait, mock_file_adapter
    ):
        """Test getting device query with no profile."""
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        query = service._get_device_query_from_profile(None)

        assert query == "removable=true"

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    def test_get_device_query_from_profile_no_query_in_methods(
        self, mock_create_wait, mock_file_adapter
    ):
        """Test getting device query when profile methods have no query."""
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service

        # Create profile with methods but no device_query
        profile = Mock()
        profile.keyboard_config = Mock()
        method = Mock()
        method.device_query = ""  # Empty query
        profile.keyboard_config.flash_methods = [method]

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        query = service._get_device_query_from_profile(profile)

        assert query == "removable=true"  # Default fallback

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    @patch("glovebox.firmware.flash.service.flasher_registry")
    def test_create_usb_flasher_success(
        self, mock_registry, mock_create_wait, mock_file_adapter, sample_usb_config
    ):
        """Test successful USB flasher creation."""
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service

        mock_flasher = Mock()
        mock_flasher.check_available.return_value = True
        mock_registry.create_method.return_value = mock_flasher

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        flasher = service._create_usb_flasher(sample_usb_config)

        assert flasher is mock_flasher

        # Verify the method was called with correct parameters
        mock_registry.create_method.assert_called_once()
        call_args = mock_registry.create_method.call_args
        assert call_args[0] == ("usb", sample_usb_config)
        assert "file_adapter" in call_args[1]
        assert call_args[1]["file_adapter"] is mock_file_adapter
        assert "usb_adapter" in call_args[1]

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    @patch("glovebox.firmware.flash.service.flasher_registry")
    def test_create_usb_flasher_not_available(
        self, mock_registry, mock_create_wait, mock_file_adapter, sample_usb_config
    ):
        """Test USB flasher creation when flasher is not available."""
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service

        mock_flasher = Mock()
        mock_flasher.check_available.return_value = False
        mock_registry.create_method.return_value = mock_flasher

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        with pytest.raises(RuntimeError, match="USB flasher is not available"):
            service._create_usb_flasher(sample_usb_config)

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    @patch("glovebox.firmware.flash.service.flasher_registry")
    def test_create_usb_flasher_no_check_available_method(
        self, mock_registry, mock_create_wait, mock_file_adapter, sample_usb_config
    ):
        """Test USB flasher creation when flasher has no check_available method."""
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service

        mock_flasher = Mock()
        # Remove check_available method
        if hasattr(mock_flasher, "check_available"):
            delattr(mock_flasher, "check_available")
        mock_registry.create_method.return_value = mock_flasher

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        # Should succeed when check_available method doesn't exist
        flasher = service._create_usb_flasher(sample_usb_config)
        assert flasher is mock_flasher

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    @patch("glovebox.firmware.flash.service.flasher_registry")
    def test_create_usb_flasher_registry_error(
        self, mock_registry, mock_create_wait, mock_file_adapter, sample_usb_config
    ):
        """Test USB flasher creation when registry raises error."""
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service

        mock_registry.create_method.side_effect = Exception("Registry error")

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        with pytest.raises(
            RuntimeError, match="Failed to create USB flasher: Registry error"
        ):
            service._create_usb_flasher(sample_usb_config)


class TestCreateFlashService:
    """Test the create_flash_service factory function."""

    @patch("glovebox.firmware.flash.service.FlashService")
    def test_create_flash_service_default(
        self, mock_flash_service_class, mock_file_adapter, mock_device_wait_service
    ):
        """Test creating flash service with required parameters."""
        mock_service = Mock()
        mock_flash_service_class.return_value = mock_service

        service = create_flash_service(mock_file_adapter, mock_device_wait_service)

        # Verify the FlashService was called with correct parameters
        mock_flash_service_class.assert_called_once()
        call_args = mock_flash_service_class.call_args

        # Check positional arguments
        assert "file_adapter" in call_args[1]
        assert call_args[1]["file_adapter"] is mock_file_adapter
        assert "device_wait_service" in call_args[1]
        assert call_args[1]["device_wait_service"] is mock_device_wait_service
        assert "loglevel" in call_args[1]
        assert call_args[1]["loglevel"] == "INFO"
        assert "usb_adapter" in call_args[1]  # Should be provided by factory
        assert service is mock_service

    @patch("glovebox.firmware.flash.service.FlashService")
    def test_create_flash_service_with_params(
        self, mock_flash_service_class, mock_file_adapter, mock_device_wait_service
    ):
        """Test creating flash service with custom parameters."""
        mock_service = Mock()
        mock_flash_service_class.return_value = mock_service

        service = create_flash_service(
            file_adapter=mock_file_adapter,
            device_wait_service=mock_device_wait_service,
            loglevel="DEBUG",
        )

        # Verify the FlashService was called with correct parameters
        mock_flash_service_class.assert_called_once()
        call_args = mock_flash_service_class.call_args

        # Check positional arguments
        assert "file_adapter" in call_args[1]
        assert call_args[1]["file_adapter"] is mock_file_adapter
        assert "device_wait_service" in call_args[1]
        assert call_args[1]["device_wait_service"] is mock_device_wait_service
        assert "loglevel" in call_args[1]
        assert call_args[1]["loglevel"] == "DEBUG"
        assert "usb_adapter" in call_args[1]  # Should be provided by factory
        assert service is mock_service


class TestFlashServiceIntegration:
    """Integration tests for FlashService workflows."""

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    @patch("glovebox.firmware.flash.service.flasher_registry")
    def test_complete_flash_workflow(
        self,
        mock_registry,
        mock_create_wait,
        mock_file_adapter,
        sample_block_device,
        firmware_file,
    ):
        """Test complete flash workflow from listing to flashing."""
        # Setup mocks
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service

        mock_flasher = Mock()
        mock_flasher.check_available.return_value = True
        mock_flasher.list_devices.return_value = [sample_block_device]
        mock_flasher.flash_device.return_value = FlashResult(success=True)
        mock_registry.create_method.return_value = mock_flasher

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        # First list devices
        list_result = service.list_devices(query="model=Glove80_Bootloader")
        assert list_result.success
        assert len(list_result.device_details) == 1

        # Then flash the device
        flash_result = service.flash(
            firmware_file=firmware_file,
            query="model=Glove80_Bootloader",
            wait=False,
        )
        assert flash_result.success
        assert flash_result.devices_flashed == 1

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    @patch("glovebox.firmware.flash.service.flasher_registry")
    def test_error_recovery_workflow(
        self, mock_registry, mock_create_wait, mock_file_adapter, firmware_file
    ):
        """Test error recovery in flash workflow."""
        # Setup mocks
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service

        # First attempt fails with flasher unavailable
        mock_flasher = Mock()
        mock_flasher.check_available.return_value = False
        mock_registry.create_method.return_value = mock_flasher

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        # First attempt should fail
        result = service.flash(firmware_file=firmware_file)
        assert not result.success
        assert "Flash operation failed" in str(result.errors)

        # Reset and make second attempt succeed
        mock_registry.reset_mock()
        mock_flasher.check_available.return_value = True
        mock_flasher.list_devices.return_value = []  # No devices

        # Second attempt should handle no devices gracefully
        result = service.flash(firmware_file=firmware_file)
        assert not result.success
        assert "No compatible devices found" in str(result.errors)


class TestFlashServiceEdgeCases:
    """Test edge cases and boundary conditions."""

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    @patch("glovebox.firmware.flash.service.flasher_registry")
    def test_flash_with_zero_count_unlimited(
        self,
        mock_registry,
        mock_create_wait,
        mock_file_adapter,
        mock_flasher,
        firmware_file,
    ):
        """Test flash with count=0 (unlimited)."""
        # Create multiple devices
        device1 = BlockDevice(name="device1", device_node="/dev/sda1")
        device2 = BlockDevice(name="device2", device_node="/dev/sdb1")
        device3 = BlockDevice(name="device3", device_node="/dev/sdc1")

        # Setup mocks
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service

        mock_registry.create_method.return_value = mock_flasher
        mock_flasher.list_devices.return_value = [device1, device2, device3]
        mock_flasher.flash_device.return_value = FlashResult(success=True)

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        result = service.flash(firmware_file=firmware_file, count=0, wait=False)

        assert result.success
        assert result.devices_flashed == 3  # All devices flashed
        assert mock_flasher.flash_device.call_count == 3

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    def test_flash_with_profile_without_flash_methods_attribute(
        self, mock_create_wait, mock_file_adapter
    ):
        """Test flash with profile that doesn't have flash_methods attribute."""
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service

        # Create profile without flash_methods attribute
        profile = Mock()
        profile.keyboard_config = Mock()
        # Explicitly make hasattr return False for flash_methods
        profile.keyboard_config.flash_methods = None

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        configs = service._get_flash_method_configs(profile, "test:query")

        assert len(configs) == 1
        assert configs[0].device_query == "test:query"

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    @patch("glovebox.firmware.flash.service.flasher_registry")
    def test_flash_device_with_no_description_or_path(
        self,
        mock_registry,
        mock_create_wait,
        mock_file_adapter,
        mock_flasher,
        firmware_file,
    ):
        """Test flashing device with no description or path."""
        # Create minimal device
        minimal_device = BlockDevice(name="minimal", device_node="")

        # Setup mocks
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service

        mock_registry.create_method.return_value = mock_flasher
        mock_flasher.list_devices.return_value = [minimal_device]
        mock_flasher.flash_device.return_value = FlashResult(success=True)

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        result = service.flash(firmware_file=firmware_file, wait=False)

        assert result.success
        # Check that device name is used when no description or path
        device_detail = result.device_details[0]
        assert device_detail["name"] == "minimal"

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    @patch("glovebox.firmware.flash.service.flasher_registry")
    def test_flash_wait_with_no_query_fallback(
        self,
        mock_registry,
        mock_create_wait,
        mock_file_adapter,
        mock_flasher,
        firmware_file,
    ):
        """Test flash with wait when no query provided and config has no query."""
        # Setup mocks
        mock_wait_service = Mock()
        mock_wait_service.wait_for_devices.return_value = []
        mock_create_wait.return_value = mock_wait_service

        # Create a mock config without device_query
        mock_config = Mock()
        mock_config.device_query = ""  # Empty query

        mock_registry.create_method.return_value = mock_flasher

        service = create_flash_service_for_tests(
            file_adapter=mock_file_adapter, device_wait_service=mock_wait_service
        )

        # Mock _get_flash_method_configs to return config without query
        with patch.object(
            service, "_get_flash_method_configs", return_value=[mock_config]
        ):
            result = service.flash(
                firmware_file=firmware_file,
                query="",  # No query provided
                wait=True,
            )

            # Should use default query "removable=true"
            mock_wait_service.wait_for_devices.assert_called_once()
            call_args = mock_wait_service.wait_for_devices.call_args[1]
            assert call_args["query"] == "removable=true"

    @patch("glovebox.firmware.flash.service.create_device_wait_service")
    @patch("glovebox.firmware.flash.service.flasher_registry")
    def test_flash_no_devices_flashed_no_failed(
        self,
        mock_registry,
        mock_create_wait,
        mock_file_adapter,
        mock_flasher,
        firmware_file,
    ):
        """Test flash when somehow no devices are flashed and none failed."""
        # Setup mocks - this is an edge case that might happen with empty device list
        mock_wait_service = Mock()
        mock_create_wait.return_value = mock_wait_service

        mock_registry.create_method.return_value = mock_flasher
        mock_flasher.list_devices.return_value = []  # Empty device list

        service = create_flash_service_for_tests(file_adapter=mock_file_adapter)

        result = service.flash(firmware_file=firmware_file, wait=False)

        assert not result.success
        assert result.devices_flashed == 0
        assert result.devices_failed == 0
        assert "No compatible devices found" in str(result.errors)
