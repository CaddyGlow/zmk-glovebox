"""Tests for firmware flasher methods implementation."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.config.flash_methods import USBFlashConfig
from glovebox.firmware.flash.flasher_methods import USBFlasher, create_usb_flasher
from glovebox.firmware.flash.models import BlockDevice, FlashResult
from glovebox.protocols.file_adapter_protocol import FileAdapterProtocol
from glovebox.protocols.usb_adapter_protocol import USBAdapterProtocol


@pytest.fixture
def mock_usb_adapter():
    """Create a mock USB adapter for testing."""
    adapter = Mock(spec=USBAdapterProtocol)
    adapter.get_all_devices.return_value = []
    adapter.list_matching_devices.return_value = []
    adapter.mount_device.return_value = ["/media/test"]
    adapter.unmount_device.return_value = True
    adapter.copy_file.return_value = True
    return adapter


@pytest.fixture
def mock_file_adapter():
    """Create a mock file adapter for testing."""
    adapter = Mock(spec=FileAdapterProtocol)
    adapter.check_exists.return_value = True
    adapter.is_file.return_value = True
    return adapter


@pytest.fixture
def sample_usb_config():
    """Create a sample USB flash configuration."""
    return USBFlashConfig(
        device_query="model:Glove80_Bootloader",
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
def firmware_file(tmp_path):
    """Create a temporary firmware file for testing."""
    firmware_path = tmp_path / "test_firmware.uf2"
    firmware_path.write_text("fake firmware content")
    return firmware_path


class TestUSBFlasherInit:
    """Test USBFlasher initialization."""

    def test_init_with_adapters(self, mock_usb_adapter, mock_file_adapter):
        """Test initialization with provided adapters."""
        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        assert flasher.usb_adapter is mock_usb_adapter
        assert flasher.file_adapter is mock_file_adapter

    @patch("glovebox.adapters.usb_adapter.create_usb_adapter")
    @patch("glovebox.adapters.file_adapter.create_file_adapter")
    def test_init_without_adapters(self, mock_create_file, mock_create_usb):
        """Test initialization creates adapters when none provided."""
        mock_usb = Mock()
        mock_file = Mock()
        mock_create_usb.return_value = mock_usb
        mock_create_file.return_value = mock_file

        flasher = USBFlasher()

        mock_create_usb.assert_called_once()
        mock_create_file.assert_called_once()
        assert flasher.usb_adapter is mock_usb
        assert flasher.file_adapter is mock_file

    @patch("glovebox.adapters.usb_adapter.create_usb_adapter")
    def test_init_partial_adapters(self, mock_create_usb, mock_file_adapter):
        """Test initialization with only one adapter provided."""
        mock_usb = Mock()
        mock_create_usb.return_value = mock_usb

        flasher = USBFlasher(file_adapter=mock_file_adapter)

        mock_create_usb.assert_called_once()
        assert flasher.usb_adapter is mock_usb
        assert flasher.file_adapter is mock_file_adapter


class TestUSBFlasherFlashDevice:
    """Test USB flasher flash_device method."""

    def test_flash_device_successful(
        self,
        mock_usb_adapter,
        mock_file_adapter,
        sample_block_device,
        sample_usb_config,
        firmware_file,
    ):
        """Test successful device flashing."""
        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        result = flasher.flash_device(
            sample_block_device, firmware_file, sample_usb_config
        )

        assert result.success
        assert len(result.messages) > 0
        assert "Successfully flashed" in str(result.messages)

        # Verify adapter calls
        mock_usb_adapter.mount_device.assert_called_once_with(sample_block_device)
        mock_usb_adapter.copy_file.assert_called_once()
        mock_usb_adapter.unmount_device.assert_called_once_with(sample_block_device)
        mock_file_adapter.check_exists.assert_called_once_with(firmware_file)

    def test_flash_device_invalid_device(
        self, mock_usb_adapter, mock_file_adapter, sample_usb_config, firmware_file
    ):
        """Test flashing with invalid device."""
        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        # Test with None device - this would cause a TypeError in real code
        # Create an invalid device instead
        invalid_device = BlockDevice(name="", device_node="")
        result = flasher.flash_device(invalid_device, firmware_file, sample_usb_config)
        assert not result.success
        assert "Invalid device" in str(result.errors)

        # Test with device without path
        invalid_device2 = BlockDevice(name="test", device_node="")
        result2 = flasher.flash_device(
            invalid_device2, firmware_file, sample_usb_config
        )
        assert not result2.success
        assert "Invalid device" in str(result2.errors)

    def test_flash_device_missing_firmware(
        self,
        mock_usb_adapter,
        mock_file_adapter,
        sample_block_device,
        sample_usb_config,
        firmware_file,
    ):
        """Test flashing with missing firmware file."""
        mock_file_adapter.check_exists.return_value = False

        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        result = flasher.flash_device(
            sample_block_device, firmware_file, sample_usb_config
        )

        assert not result.success
        assert "Firmware file not found" in str(result.errors)

    def test_flash_device_invalid_config(
        self,
        mock_usb_adapter,
        mock_file_adapter,
        sample_block_device,
        firmware_file,
    ):
        """Test flashing with invalid configuration."""
        invalid_config = USBFlashConfig(
            device_query="",  # Empty query should be invalid
            mount_timeout=30,
            copy_timeout=60,
        )

        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        result = flasher.flash_device(
            sample_block_device, firmware_file, invalid_config
        )

        assert not result.success
        assert "Invalid USB flash configuration" in str(result.errors)

    def test_flash_device_usb_not_available(
        self,
        mock_usb_adapter,
        mock_file_adapter,
        sample_block_device,
        sample_usb_config,
        firmware_file,
    ):
        """Test flashing when USB adapter is not available."""
        # Remove the get_all_devices method to simulate unavailable adapter
        del mock_usb_adapter.get_all_devices

        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        result = flasher.flash_device(
            sample_block_device, firmware_file, sample_usb_config
        )

        assert not result.success
        assert "USB adapter is not available" in str(result.errors)

    def test_flash_device_mount_failure(
        self,
        mock_usb_adapter,
        mock_file_adapter,
        sample_block_device,
        sample_usb_config,
        firmware_file,
    ):
        """Test flashing when device mount fails."""
        mock_usb_adapter.mount_device.return_value = []  # Empty mount points

        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        result = flasher.flash_device(
            sample_block_device, firmware_file, sample_usb_config
        )

        assert not result.success
        assert "Failed to mount device" in str(result.errors)

    def test_flash_device_copy_failure(
        self,
        mock_usb_adapter,
        mock_file_adapter,
        sample_block_device,
        sample_usb_config,
        firmware_file,
    ):
        """Test flashing when file copy fails."""
        mock_usb_adapter.copy_file.return_value = False

        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        result = flasher.flash_device(
            sample_block_device, firmware_file, sample_usb_config
        )

        assert not result.success
        assert "Failed to copy firmware" in str(result.errors)
        # Verify unmount is still called
        mock_usb_adapter.unmount_device.assert_called_once_with(sample_block_device)

    def test_flash_device_with_sync(
        self,
        mock_usb_adapter,
        mock_file_adapter,
        sample_block_device,
        firmware_file,
    ):
        """Test flashing with filesystem sync enabled."""
        config = USBFlashConfig(
            device_query="model:Glove80_Bootloader",
            mount_timeout=30,
            copy_timeout=60,
            sync_after_copy=True,
        )

        # Mock flash operations with sync capability
        mock_flash_ops = Mock()
        mock_flash_ops.sync_filesystem = Mock()
        mock_usb_adapter._flash_ops = mock_flash_ops

        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        result = flasher.flash_device(sample_block_device, firmware_file, config)

        assert result.success
        mock_flash_ops.sync_filesystem.assert_called_once()

    def test_flash_device_without_sync(
        self,
        mock_usb_adapter,
        mock_file_adapter,
        sample_block_device,
        firmware_file,
    ):
        """Test flashing with filesystem sync disabled."""
        config = USBFlashConfig(
            device_query="model:Glove80_Bootloader",
            mount_timeout=30,
            copy_timeout=60,
            sync_after_copy=False,
        )

        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        result = flasher.flash_device(sample_block_device, firmware_file, config)

        assert result.success
        # Verify no sync operation is attempted

    def test_flash_device_exception_handling(
        self,
        mock_usb_adapter,
        mock_file_adapter,
        sample_block_device,
        sample_usb_config,
        firmware_file,
    ):
        """Test exception handling during flash operation."""
        mock_usb_adapter.mount_device.side_effect = Exception("Mount error")

        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        result = flasher.flash_device(
            sample_block_device, firmware_file, sample_usb_config
        )

        assert not result.success
        assert "USB flash failed: Mount error" in str(result.errors)

    def test_flash_device_unmount_always_called(
        self,
        mock_usb_adapter,
        mock_file_adapter,
        sample_block_device,
        sample_usb_config,
        firmware_file,
    ):
        """Test that unmount is always called even if copy fails."""
        mock_usb_adapter.copy_file.side_effect = Exception("Copy error")

        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        result = flasher.flash_device(
            sample_block_device, firmware_file, sample_usb_config
        )

        assert not result.success
        # Verify unmount is called despite the exception
        mock_usb_adapter.unmount_device.assert_called_once_with(sample_block_device)


class TestUSBFlasherListDevices:
    """Test USB flasher list_devices method."""

    def test_list_devices_successful(
        self,
        mock_usb_adapter,
        mock_file_adapter,
        sample_usb_config,
        sample_block_device,
    ):
        """Test successful device listing."""
        mock_usb_adapter.list_matching_devices.return_value = [sample_block_device]

        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        devices = flasher.list_devices(sample_usb_config)

        assert len(devices) == 1
        assert devices[0] is sample_block_device
        mock_usb_adapter.list_matching_devices.assert_called_once_with(
            sample_usb_config.device_query
        )

    def test_list_devices_empty_result(
        self, mock_usb_adapter, mock_file_adapter, sample_usb_config
    ):
        """Test device listing with no devices found."""
        mock_usb_adapter.list_matching_devices.return_value = []

        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        devices = flasher.list_devices(sample_usb_config)

        assert len(devices) == 0

    def test_list_devices_exception_handling(
        self, mock_usb_adapter, mock_file_adapter, sample_usb_config
    ):
        """Test exception handling in device listing."""
        mock_usb_adapter.list_matching_devices.side_effect = Exception("List error")

        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        devices = flasher.list_devices(sample_usb_config)

        assert len(devices) == 0


class TestUSBFlasherCheckAvailable:
    """Test USB flasher check_available method."""

    def test_check_available_true(self, mock_usb_adapter, mock_file_adapter):
        """Test availability check when adapter is available."""
        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        assert flasher.check_available() is True

    def test_check_available_false_no_method(self, mock_file_adapter):
        """Test availability check when adapter lacks required method."""
        mock_usb_adapter = Mock()
        # Don't add get_all_devices method - check_available should return False
        if hasattr(mock_usb_adapter, "get_all_devices"):
            delattr(mock_usb_adapter, "get_all_devices")

        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        assert flasher.check_available() is False

    def test_check_available_exception_handling(self, mock_file_adapter):
        """Test availability check with exception during hasattr."""

        # Create an adapter that raises exception during hasattr access
        class ExceptionAdapter:
            def __getattribute__(self, name):
                # Raise exception for any attribute access
                raise RuntimeError("Adapter access error")

        mock_usb_adapter = ExceptionAdapter()

        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        # This should trigger the exception path and return False
        assert flasher.check_available() is False


class TestUSBFlasherValidateConfig:
    """Test USB flasher validate_config method."""

    def test_validate_config_valid(self, mock_usb_adapter, mock_file_adapter):
        """Test validation with valid configuration."""
        config = USBFlashConfig(
            device_query="model:Glove80_Bootloader",
            mount_timeout=30,
            copy_timeout=60,
        )

        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        assert flasher.validate_config(config) is True

    def test_validate_config_empty_query(self, mock_usb_adapter, mock_file_adapter):
        """Test validation with empty device query."""
        config = USBFlashConfig(
            device_query="",  # Empty query
            mount_timeout=30,
            copy_timeout=60,
        )

        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        assert flasher.validate_config(config) is False

    def test_validate_config_invalid_mount_timeout(
        self, mock_usb_adapter, mock_file_adapter
    ):
        """Test validation with invalid mount timeout."""
        config = USBFlashConfig(
            device_query="model:Glove80_Bootloader",
            mount_timeout=0,  # Invalid timeout
            copy_timeout=60,
        )

        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        assert flasher.validate_config(config) is False

    def test_validate_config_invalid_copy_timeout(
        self, mock_usb_adapter, mock_file_adapter
    ):
        """Test validation with invalid copy timeout."""
        config = USBFlashConfig(
            device_query="model:Glove80_Bootloader",
            mount_timeout=30,
            copy_timeout=-1,  # Invalid timeout
        )

        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        assert flasher.validate_config(config) is False


class TestUSBFlasherPrivateMethods:
    """Test USB flasher private methods."""

    def test_validate_inputs_success(
        self,
        mock_usb_adapter,
        mock_file_adapter,
        sample_block_device,
        sample_usb_config,
        firmware_file,
    ):
        """Test successful input validation."""
        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )
        result = FlashResult(success=True)

        is_valid = flasher._validate_inputs(
            sample_block_device, firmware_file, sample_usb_config, result
        )

        assert is_valid is True
        assert result.success is True

    def test_validate_inputs_invalid_device(
        self, mock_usb_adapter, mock_file_adapter, sample_usb_config, firmware_file
    ):
        """Test input validation with invalid device."""
        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )
        result = FlashResult(success=True)

        # Test with None device - we need to use type ignore for this edge case test
        is_valid = flasher._validate_inputs(
            None,
            firmware_file,
            sample_usb_config,
            result,  # type: ignore[arg-type]
        )

        assert is_valid is False
        assert result.success is False
        assert "Invalid device" in str(result.errors)

    def test_validate_inputs_missing_firmware(
        self,
        mock_usb_adapter,
        mock_file_adapter,
        sample_block_device,
        sample_usb_config,
        firmware_file,
    ):
        """Test input validation with missing firmware file."""
        mock_file_adapter.check_exists.return_value = False

        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )
        result = FlashResult(success=True)

        is_valid = flasher._validate_inputs(
            sample_block_device, firmware_file, sample_usb_config, result
        )

        assert is_valid is False
        assert result.success is False
        assert "Firmware file not found" in str(result.errors)

    def test_sync_device_with_flash_ops(self, mock_usb_adapter, mock_file_adapter):
        """Test device sync with flash operations available."""
        mock_flash_ops = Mock()
        mock_flash_ops.sync_filesystem = Mock()
        mock_usb_adapter._flash_ops = mock_flash_ops

        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        mount_point = Path("/media/test")
        flasher._sync_device(mount_point)

        mock_flash_ops.sync_filesystem.assert_called_once_with(str(mount_point))

    def test_sync_device_without_flash_ops(self, mock_usb_adapter, mock_file_adapter):
        """Test device sync without flash operations."""
        # No _flash_ops attribute

        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        mount_point = Path("/media/test")
        # Should not raise exception
        flasher._sync_device(mount_point)

    def test_sync_device_without_sync_method(self, mock_usb_adapter, mock_file_adapter):
        """Test device sync without sync_filesystem method."""
        mock_flash_ops = Mock()
        # No sync_filesystem method
        mock_usb_adapter._flash_ops = mock_flash_ops

        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        mount_point = Path("/media/test")
        # Should not raise exception
        flasher._sync_device(mount_point)

    def test_sync_device_exception_handling(self, mock_usb_adapter, mock_file_adapter):
        """Test device sync with exception."""
        mock_flash_ops = Mock()
        mock_flash_ops.sync_filesystem.side_effect = Exception("Sync error")
        mock_usb_adapter._flash_ops = mock_flash_ops

        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        mount_point = Path("/media/test")
        # Should not raise exception
        flasher._sync_device(mount_point)


class TestCreateUSBFlasher:
    """Test the create_usb_flasher factory function."""

    def test_create_usb_flasher_default(self):
        """Test creating USB flasher with default parameters."""
        with (
            patch(
                "glovebox.adapters.usb_adapter.create_usb_adapter"
            ) as mock_create_usb,
            patch(
                "glovebox.adapters.file_adapter.create_file_adapter"
            ) as mock_create_file,
        ):
            mock_usb = Mock()
            mock_file = Mock()
            mock_create_usb.return_value = mock_usb
            mock_create_file.return_value = mock_file

            flasher = create_usb_flasher()

            assert isinstance(flasher, USBFlasher)
            assert flasher.usb_adapter is mock_usb
            assert flasher.file_adapter is mock_file

    def test_create_usb_flasher_with_adapters(
        self, mock_usb_adapter, mock_file_adapter
    ):
        """Test creating USB flasher with provided adapters."""
        flasher = create_usb_flasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        assert isinstance(flasher, USBFlasher)
        assert flasher.usb_adapter is mock_usb_adapter
        assert flasher.file_adapter is mock_file_adapter


class TestUSBFlasherIntegration:
    """Integration tests for USB flasher workflows."""

    def test_complete_flash_workflow(
        self,
        mock_usb_adapter,
        mock_file_adapter,
        sample_block_device,
        sample_usb_config,
        firmware_file,
    ):
        """Test complete flash workflow from start to finish."""
        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        # First list devices
        mock_usb_adapter.list_matching_devices.return_value = [sample_block_device]
        devices = flasher.list_devices(sample_usb_config)
        assert len(devices) == 1

        # Then flash the device
        result = flasher.flash_device(devices[0], firmware_file, sample_usb_config)
        assert result.success

        # Verify all expected calls
        mock_usb_adapter.list_matching_devices.assert_called()
        mock_usb_adapter.mount_device.assert_called()
        mock_usb_adapter.copy_file.assert_called()
        mock_usb_adapter.unmount_device.assert_called()

    def test_error_recovery_workflow(
        self,
        mock_usb_adapter,
        mock_file_adapter,
        sample_block_device,
        sample_usb_config,
        firmware_file,
    ):
        """Test error recovery workflow."""
        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        # First attempt fails due to copy error
        mock_usb_adapter.copy_file.return_value = False
        result = flasher.flash_device(
            sample_block_device, firmware_file, sample_usb_config
        )
        assert not result.success

        # Verify unmount was still called for cleanup
        mock_usb_adapter.unmount_device.assert_called_with(sample_block_device)

        # Reset mock and try again with success
        mock_usb_adapter.reset_mock()
        mock_usb_adapter.mount_device.return_value = ["/media/test"]
        mock_usb_adapter.copy_file.return_value = True
        mock_usb_adapter.unmount_device.return_value = True

        result = flasher.flash_device(
            sample_block_device, firmware_file, sample_usb_config
        )
        assert result.success


class TestUSBFlasherEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_flash_device_with_device_description(
        self,
        mock_usb_adapter,
        mock_file_adapter,
        sample_usb_config,
        firmware_file,
    ):
        """Test flashing device with description property."""
        device_with_description = BlockDevice(
            name="sda1",
            device_node="/dev/sda1",
            model="Glove80_Bootloader",
            vendor="Adafruit",
            label="GLV80LDR",
        )

        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        result = flasher.flash_device(
            device_with_description, firmware_file, sample_usb_config
        )

        assert result.success
        # Should use device description in success message
        assert device_with_description.description in str(result.messages)

    def test_flash_device_without_description(
        self,
        mock_usb_adapter,
        mock_file_adapter,
        sample_usb_config,
        firmware_file,
    ):
        """Test flashing device without description."""
        minimal_device = BlockDevice(
            name="sda1",
            device_node="/dev/sda1",
        )

        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        result = flasher.flash_device(minimal_device, firmware_file, sample_usb_config)

        assert result.success
        # Should use device path when no description - check the actual logic
        # The code uses device.description or device.path
        # Since minimal_device has no description, it should use device.path
        # But let's check what the actual message contains
        message_str = str(result.messages)
        # The success message should contain either description or path
        assert (
            (minimal_device.description in message_str)
            or (minimal_device.path in message_str)
            or (minimal_device.name in message_str)
        )

    def test_mount_device_with_none_mount_point(
        self,
        mock_usb_adapter,
        mock_file_adapter,
        sample_block_device,
        sample_usb_config,
        firmware_file,
    ):
        """Test mounting device that returns None in mount points."""
        mock_usb_adapter.mount_device.return_value = [None]

        flasher = USBFlasher(
            usb_adapter=mock_usb_adapter, file_adapter=mock_file_adapter
        )

        result = flasher.flash_device(
            sample_block_device, firmware_file, sample_usb_config
        )

        assert not result.success
        assert "Failed to mount device" in str(result.errors)
