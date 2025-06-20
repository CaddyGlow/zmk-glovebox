"""Tests for device wait service functionality."""

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
    mock_adapter = Mock()
    mock_monitor = Mock()
    return DeviceWaitService(usb_adapter=mock_adapter, usb_monitor=mock_monitor)


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

    def test_immediate_target_reached(self, mock_device):
        """Test when target devices are already available."""
        mock_adapter = Mock()
        mock_adapter.list_matching_devices.return_value = [mock_device]

        mock_monitor = Mock()

        service = DeviceWaitService(usb_adapter=mock_adapter, usb_monitor=mock_monitor)

        result = service.wait_for_devices(
            target_count=1,
            timeout=60.0,
            query="test",
            flash_config=Mock(),
            show_progress=False,
        )

        assert len(result) == 1
        assert result[0] == mock_device

    def test_wait_with_callback(self, mock_device):
        """Test waiting with device callback."""
        mock_usb_adapter = Mock()
        mock_usb_monitor = Mock()
        mock_flash_config = Mock()

        # Mock initial device list (empty)
        mock_usb_adapter.list_matching_devices.return_value = []

        service = DeviceWaitService(
            usb_adapter=mock_usb_adapter, usb_monitor=mock_usb_monitor
        )

        # Mock the device callback to simulate device arrival
        registered_callback = None

        def capture_callback(callback):
            nonlocal registered_callback
            registered_callback = callback

        mock_usb_monitor.register_callback.side_effect = capture_callback

        # Mock the _matches_query method to return True for our mock device
        def mock_matches_query(device, query):
            return device == mock_device and query == "test"

        # Patch the _matches_query method to always match our mock device
        with patch.object(service, "_matches_query", side_effect=mock_matches_query):
            # Start the wait in a separate thread to test callback behavior
            import threading
            import time

            result_container = []

            def wait_thread():
                result = service.wait_for_devices(
                    target_count=1,
                    timeout=2.0,
                    query="test",
                    flash_config=mock_flash_config,
                    poll_interval=0.1,
                    show_progress=False,
                )
                result_container.append(result)

            thread = threading.Thread(target=wait_thread)
            thread.start()

            # Give the thread time to start and register callback
            time.sleep(0.2)

            # Simulate device arrival via callback
            if registered_callback:
                registered_callback("add", mock_device)

            # Wait for thread to complete
            thread.join(timeout=3.0)

            # Verify results
            assert len(result_container) == 1
            assert len(result_container[0]) == 1
            assert result_container[0][0] == mock_device

        # Verify monitoring was set up and cleaned up
        mock_usb_monitor.register_callback.assert_called_once()
        mock_usb_monitor.start_monitoring.assert_called_once()
        mock_usb_monitor.unregister_callback.assert_called_once()
        mock_usb_monitor.stop_monitoring.assert_called_once()

    def test_timeout_behavior(self):
        """Test timeout behavior when no devices are found."""
        mock_usb_adapter = Mock()
        mock_usb_monitor = Mock()
        mock_flash_config = Mock()

        # Mock empty device list (no devices found)
        mock_usb_adapter.list_matching_devices.return_value = []

        service = DeviceWaitService(
            usb_adapter=mock_usb_adapter, usb_monitor=mock_usb_monitor
        )

        import time

        start_time = time.time()

        result = service.wait_for_devices(
            target_count=2,
            timeout=0.5,  # Short timeout
            query="test",
            flash_config=mock_flash_config,
            poll_interval=0.1,
            show_progress=False,
        )

        end_time = time.time()
        elapsed = end_time - start_time

        # Verify timeout behavior
        assert len(result) == 0  # No devices found
        assert elapsed >= 0.5  # At least the timeout duration
        assert elapsed < 1.0  # But not too much longer

        # Verify monitoring was set up and cleaned up
        mock_usb_monitor.register_callback.assert_called_once()
        mock_usb_monitor.start_monitoring.assert_called_once()
        mock_usb_monitor.unregister_callback.assert_called_once()
        mock_usb_monitor.stop_monitoring.assert_called_once()

    def test_device_remove_callback(self, mock_device):
        """Test device removal callback."""
        mock_usb_adapter = Mock()
        mock_usb_monitor = Mock()
        mock_flash_config = Mock()

        # Mock initial device list with our device already present
        mock_usb_adapter.list_matching_devices.return_value = [mock_device]

        service = DeviceWaitService(
            usb_adapter=mock_usb_adapter, usb_monitor=mock_usb_monitor
        )

        # Mock the device callback to simulate device removal
        registered_callback = None

        def capture_callback(callback):
            nonlocal registered_callback
            registered_callback = callback

        mock_usb_monitor.register_callback.side_effect = capture_callback

        # Start the wait in a separate thread
        import threading
        import time

        result_container = []

        def wait_thread():
            result = service.wait_for_devices(
                target_count=2,  # Need 2 devices, start with 1
                timeout=2.0,
                query="test",
                flash_config=mock_flash_config,
                poll_interval=0.1,
                show_progress=False,
            )
            result_container.append(result)

        thread = threading.Thread(target=wait_thread)
        thread.start()

        # Give the thread time to start and register callback
        time.sleep(0.2)

        # Simulate device removal via callback
        if registered_callback:
            registered_callback("remove", mock_device)

        # Wait for thread to complete (should timeout with 0 devices)
        thread.join(timeout=3.0)

        # Verify results - should have no devices after removal
        assert len(result_container) == 1
        assert len(result_container[0]) == 0  # Device was removed

        # Verify monitoring was set up and cleaned up
        mock_usb_monitor.register_callback.assert_called_once()
        mock_usb_monitor.start_monitoring.assert_called_once()
        mock_usb_monitor.unregister_callback.assert_called_once()
        mock_usb_monitor.stop_monitoring.assert_called_once()

    def test_matches_query_integration(self):
        """Test query matching integration with USB adapter."""
        mock_adapter = Mock()
        mock_monitor = Mock()
        service = DeviceWaitService(usb_adapter=mock_adapter, usb_monitor=mock_monitor)

        mock_device = Mock()
        mock_device.device_node = "/dev/test"

        # Test positive match
        mock_adapter.list_matching_devices.return_value = [mock_device]
        result = service._matches_query(mock_device, "test_query")
        assert result is True

        # Test negative match
        mock_adapter.list_matching_devices.return_value = []
        result = service._matches_query(mock_device, "test_query")
        assert result is False
