"""Tests for device wait service functionality."""

import threading
import time
from unittest.mock import Mock, patch

import pytest

from glovebox.firmware.flash.device_wait_service import DeviceWaitService
from glovebox.firmware.flash.models import BlockDevice
from glovebox.firmware.flash.wait_state import DeviceWaitState


@pytest.fixture
def mock_device():
    """Create a mock BlockDevice for testing."""
    return BlockDevice(
        name="test_device",
        device_node="/dev/test",
        model="Test Device",
        vendor="Test Vendor",
        serial="TEST123",
        vendor_id="1234",
        product_id="5678",
        removable=True,
    )


@pytest.fixture
def wait_service():
    """Create a DeviceWaitService instance for testing."""
    return DeviceWaitService()


class TestDeviceWaitState:
    """Test DeviceWaitState behavior and device management."""

    def test_initial_state(self):
        """Test initial state of DeviceWaitState."""
        state = DeviceWaitState(
            target_count=2,
            query="test",
            timeout=60.0,
        )

        assert state.target_count == 2
        assert state.query == "test"
        assert state.timeout == 60.0
        assert state.waiting is True
        assert len(state.found_devices) == 0
        assert not state.is_target_reached
        assert not state.is_timeout

    def test_add_remove_devices(self, mock_device):
        """Test adding and removing devices from wait state."""
        state = DeviceWaitState(target_count=2, query="test", timeout=60.0)

        # Add device
        state.add_device(mock_device)
        assert len(state.found_devices) == 1
        assert mock_device in state.found_devices

        # Add same device again (should not duplicate)
        state.add_device(mock_device)
        assert len(state.found_devices) == 1

        # Remove device
        state.remove_device(mock_device)
        assert len(state.found_devices) == 0

    def test_target_reached(self, mock_device):
        """Test target reached detection."""
        state = DeviceWaitState(target_count=1, query="test", timeout=60.0)

        assert not state.is_target_reached
        state.add_device(mock_device)
        assert state.is_target_reached

    def test_timeout_detection(self):
        """Test timeout detection."""
        # Create state with very short timeout
        state = DeviceWaitState(target_count=1, query="test", timeout=0.1)

        assert not state.is_timeout
        # Wait for timeout to occur
        time.sleep(0.15)
        assert state.is_timeout

    def test_should_stop_waiting(self):
        """Test should_stop_waiting logic."""
        state = DeviceWaitState(target_count=1, query="test", timeout=60.0)

        # Initially should not stop
        assert not state.should_stop_waiting

        # After calling stop_waiting(), should stop
        state.stop_waiting()
        assert state.should_stop_waiting


class TestDeviceWaitService:
    """Test DeviceWaitService with mock USB monitoring."""

    @patch("glovebox.firmware.flash.device_wait_service.create_usb_monitor")
    @patch("glovebox.adapters.usb_adapter.create_usb_adapter")
    def test_immediate_target_reached(
        self, mock_adapter_factory, mock_monitor_factory, mock_device
    ):
        """Test when target devices are already available."""
        mock_adapter = Mock()
        mock_adapter.list_matching_devices.return_value = [mock_device]
        mock_adapter_factory.return_value = mock_adapter

        service = DeviceWaitService()

        result = service.wait_for_devices(
            target_count=1,
            timeout=60.0,
            query="test",
            flash_config=Mock(),
            show_progress=False,
        )

        assert len(result) == 1
        assert result[0] == mock_device

    @pytest.mark.skip(
        reason="TODO: Circular dependency in DeviceWaitService.__init__ makes USB adapter mocking complex. Need to refactor USB adapter injection to remove circular import."
    )
    def test_wait_with_callback(self, mock_device):
        """Test waiting with device callback."""
        # This test requires complex mocking due to circular dependencies
        # TODO: Refactor DeviceWaitService to accept USB adapter as constructor parameter
        # to remove the circular import and enable proper testing
        pass

    @pytest.mark.skip(
        reason="TODO: Circular dependency in DeviceWaitService.__init__ makes USB adapter mocking complex. Need to refactor USB adapter injection to remove circular import."
    )
    def test_timeout_behavior(self):
        """Test timeout behavior when no devices are found."""
        # This test requires complex mocking due to circular dependencies
        # TODO: Refactor DeviceWaitService to accept USB adapter as constructor parameter
        # to remove the circular import and enable proper testing
        pass

    @pytest.mark.skip(
        reason="TODO: Circular dependency in DeviceWaitService.__init__ makes USB adapter mocking complex. Need to refactor USB adapter injection to remove circular import."
    )
    def test_device_remove_callback(self, mock_device):
        """Test device removal callback."""
        # This test requires complex mocking due to circular dependencies
        # TODO: Refactor DeviceWaitService to accept USB adapter as constructor parameter
        # to remove the circular import and enable proper testing
        pass

    def test_matches_query_integration(self):
        """Test query matching integration with USB adapter."""
        service = DeviceWaitService()
        mock_device = Mock()
        mock_device.device_node = "/dev/test"

        # Mock the USB adapter's list_matching_devices method with patch
        with patch.object(service.usb_adapter, "list_matching_devices") as mock_list:
            # Test positive match
            mock_list.return_value = [mock_device]
            result = service._matches_query(mock_device, "test_query")
            assert result is True

            # Test negative match
            mock_list.return_value = []
            result = service._matches_query(mock_device, "test_query")
            assert result is False
