"""Tests for FlashService with keyboard profile."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from glovebox.adapters.file_adapter import FileAdapter
from glovebox.adapters.usb_adapter import USBAdapter
from glovebox.config.models import FlashConfig, KeyboardConfig
from glovebox.flash.lsdev import BlockDevice
from glovebox.models.results import FlashResult
from glovebox.services.flash_service import FlashService, create_flash_service


class TestFlashServiceWithProfile:
    """Test FlashService with KeyboardProfile."""

    def setup_method(self):
        """Set up test environment."""
        self.mock_file_adapter = Mock(spec=FileAdapter)
        # Create a more complete mock for USBAdapter with all needed methods
        self.mock_usb_adapter = Mock()
        self.mock_usb_adapter.get_all_devices = Mock()
        self.mock_usb_adapter.mount = Mock()
        self.mock_usb_adapter.unmount = Mock()
        self.mock_usb_adapter.copy_file = Mock()

        self.service = FlashService(
            usb_adapter=self.mock_usb_adapter,
            file_adapter=self.mock_file_adapter,
            loglevel="INFO"
        )

        # Create a mock device
        self.mock_device = Mock(spec=BlockDevice)
        self.mock_device.name = "sda"
        self.mock_device.device_node = "/dev/sda"
        self.mock_device.path = "/dev/sda"
        self.mock_device.description = "Test Device"
        self.mock_device.removable = True
        self.mock_device.serial = "TEST123"
        self.mock_device.vendor = "Test"
        self.mock_device.model = "TestModel"

    def test_flash_with_profile_query(self):
        """Test flashing with query from keyboard profile."""
        # Create a mock profile with flash config
        mock_profile = Mock()
        mock_profile.keyboard_name = "test_keyboard"
        mock_profile.firmware_version = "test_version"

        # Create mock flash config
        mock_flash_config = Mock(spec=FlashConfig)
        mock_flash_config.query = "vendor=Test and removable=true"
        mock_flash_config.usb_vid = "0x1234"
        mock_flash_config.usb_pid = "0x5678"

        # Set up keyboard config for the profile
        mock_keyboard_config = Mock(spec=KeyboardConfig)
        mock_keyboard_config.keyboard = "test_keyboard"
        mock_keyboard_config.flash = mock_flash_config
        mock_profile.keyboard_config = mock_keyboard_config

        # Setup USB adapter mock
        self.mock_usb_adapter.get_all_devices.return_value = [self.mock_device]
        self.mock_usb_adapter.mount.return_value = ["/mnt/sda"]
        self.mock_usb_adapter.copy_file.return_value = True
        self.mock_usb_adapter.unmount.return_value = True
        self.mock_file_adapter.exists.return_value = True

        # Test flashing with profile query
        result = self.service.flash(
            firmware_file="/path/to/firmware.uf2",
            profile=mock_profile,  # Pass the profile
            query="",  # Empty query means use the one from profile
            timeout=1,
            count=1,
        )

        # Verify results
        assert result.success is True

        # Verify USB adapter was called with the profile's query
        self.mock_usb_adapter.get_all_devices.assert_called_once()
        call_args = self.mock_usb_adapter.get_all_devices.call_args[0]
        assert len(call_args) > 0
        assert mock_flash_config.query == call_args[0]

    def test_flash_with_explicit_query_override(self):
        """Test flashing with explicit query that overrides profile query."""
        # Create a mock profile with flash config
        mock_profile = Mock()
        mock_profile.keyboard_name = "test_keyboard"
        mock_profile.firmware_version = "test_version"

        # Create mock flash config
        mock_flash_config = Mock(spec=FlashConfig)
        mock_flash_config.query = "vendor=Test and removable=true"
        mock_flash_config.usb_vid = "0x1234"
        mock_flash_config.usb_pid = "0x5678"

        # Set up keyboard config for the profile
        mock_keyboard_config = Mock(spec=KeyboardConfig)
        mock_keyboard_config.keyboard = "test_keyboard"
        mock_keyboard_config.flash = mock_flash_config
        mock_profile.keyboard_config = mock_keyboard_config

        # Setup USB adapter mock
        self.mock_usb_adapter.get_all_devices.return_value = [self.mock_device]
        self.mock_usb_adapter.mount.return_value = ["/mnt/sda"]
        self.mock_usb_adapter.copy_file.return_value = True
        self.mock_usb_adapter.unmount.return_value = True
        self.mock_file_adapter.exists.return_value = True

        # Define explicit query
        explicit_query = "vendor=ExplicitTest and removable=true"

        # Test flashing with explicit query
        result = self.service.flash(
            firmware_file="/path/to/firmware.uf2",
            profile=mock_profile,
            query=explicit_query,  # This should override profile config
            timeout=1,
            count=1,
        )

        # Verify results
        assert result.success is True

        # Verify USB adapter was called with explicit query
        self.mock_usb_adapter.get_all_devices.assert_called_once()
        call_args = self.mock_usb_adapter.get_all_devices.call_args[0]
        assert len(call_args) > 0
        assert explicit_query == call_args[0]

    def test_flash_with_no_profile(self):
        """Test flashing when no profile is provided."""
        # No profile provided
        self.mock_usb_adapter.get_all_devices.return_value = []
        self.mock_file_adapter.exists.return_value = True
        # Make sure mount method is defined even if not used
        self.mock_usb_adapter.mount.return_value = []

        # Test flashing with no profile
        result = self.service.flash(
            firmware_file="/path/to/firmware.uf2",
            profile=None,
            query="",  # Empty query should use fallback
            timeout=1,
            count=1,
        )

        # Verify results - should not fail but use fallback query
        assert result.success is False  # No devices found with fallback query

        # Verify USB adapter was called with a fallback query
        assert self.mock_usb_adapter.get_all_devices.call_count >= 1
        # Get the first call arguments
        call_args = self.mock_usb_adapter.get_all_devices.call_args_list[0][0]
        assert len(call_args) > 0  # Should have some fallback query
        assert (
            "removable=true" in call_args[0]
        )  # Default query should include removable=true

    def test_list_devices_with_profile(self):
        """Test listing devices using profile query."""
        # Create a mock profile with flash config
        mock_profile = Mock()
        mock_profile.keyboard_name = "test_keyboard"
        mock_profile.firmware_version = "test_version"

        # Create mock flash config
        mock_flash_config = Mock(spec=FlashConfig)
        mock_flash_config.query = "vendor=Test and removable=true"
        mock_flash_config.usb_vid = "0x1234"
        mock_flash_config.usb_pid = "0x5678"

        # Set up keyboard config for the profile
        mock_keyboard_config = Mock(spec=KeyboardConfig)
        mock_keyboard_config.keyboard = "test_keyboard"
        mock_keyboard_config.flash = mock_flash_config
        mock_profile.keyboard_config = mock_keyboard_config

        # Setup USB adapter mock
        self.mock_usb_adapter.get_all_devices.return_value = [self.mock_device]

        # Test listing devices with profile
        result = self.service.list_devices(
            profile=mock_profile,
            query="",  # Empty query means use the profile's query
        )

        # Verify results
        assert result.success is True
        assert len(result.device_details) == 1
        assert result.device_details[0]["serial"] == "TEST123"

        # Verify USB adapter was called with profile query
        self.mock_usb_adapter.get_all_devices.assert_called_once_with(
            mock_flash_config.query
        )


@pytest.mark.parametrize(
    "profile,query,expected_query_source",
    [
        (True, "", "profile"),  # Use profile config
        (True, "custom_query", "explicit"),  # Use explicit query
        (False, "custom_query", "explicit"),  # No profile, use explicit
        (False, "", "default"),  # No profile, no query, use default
    ],
)
def test_query_resolution_parameterized(profile, query, expected_query_source):
    """Test query resolution with various parameters."""
    # Create mocked service
    mock_file_adapter = Mock(spec=FileAdapter)
    mock_usb_adapter = Mock()
    mock_usb_adapter.get_all_devices = Mock(return_value=[])

    service = FlashService(
        usb_adapter=mock_usb_adapter,
        file_adapter=mock_file_adapter,
        loglevel="INFO"
    )
    mock_file_adapter.exists.return_value = True

    # Setup profile if needed
    mock_profile = None
    if profile:
        mock_profile = Mock()
        mock_profile.keyboard_name = "test_keyboard"
        mock_profile.firmware_version = "test_version"

        # Create mock flash config
        mock_flash_config = Mock(spec=FlashConfig)
        mock_flash_config.query = "profile_query and removable=true"
        mock_flash_config.usb_vid = "0x1234"
        mock_flash_config.usb_pid = "0x5678"

        # Set up keyboard config for the profile
        mock_keyboard_config = Mock(spec=KeyboardConfig)
        mock_keyboard_config.keyboard = "test_keyboard"
        mock_keyboard_config.flash = mock_flash_config
        mock_profile.keyboard_config = mock_keyboard_config

    # Run the test
    service.flash(
        firmware_file="/path/to/firmware.uf2",
        profile=mock_profile,
        query=query,
        timeout=1,
        count=1,
    )

    # Verify the query was used at least once
    assert mock_usb_adapter.get_all_devices.call_count >= 1
    call_args = mock_usb_adapter.get_all_devices.call_args[0]
    assert len(call_args) > 0

    # Verify query based on expected source
    if expected_query_source == "profile":
        assert "profile_query" in call_args[0]
    elif expected_query_source == "explicit":
        assert query == call_args[0]
    elif expected_query_source == "default":
        assert "removable=true" in call_args[0]
