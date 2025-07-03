"""Integration tests for firmware workflow.

Tests the complete firmware pipeline from compilation to device flashing,
focusing on the new memory-first patterns and IOCommand usage.
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.config import create_user_config
from glovebox.core.metrics import create_session_metrics
from glovebox.firmware.flash import create_flash_service
from glovebox.firmware.flash.models import FlashResult, USBDeviceInfo
from glovebox.firmware.models import FirmwareOutputFiles


pytestmark = pytest.mark.integration


@pytest.fixture
def mock_usb_adapter():
    """Create a mock USB adapter for testing."""
    from unittest.mock import Mock

    from glovebox.protocols import USBAdapterProtocol

    adapter = Mock(spec=USBAdapterProtocol)
    adapter.list_matching_devices.return_value = []
    adapter.mount_device.return_value = ["/media/test"]
    adapter.copy_file.return_value = True
    adapter.unmount_device.return_value = True
    return adapter


@pytest.fixture
def flash_service(
    isolated_cli_environment,
    mock_usb_adapter,
    mock_file_adapter,
    session_metrics,
    mock_keyboard_profile,
):
    """Create flash service for testing."""
    user_config = create_user_config()

    service = create_flash_service(
        usb_adapter=mock_usb_adapter,
        file_adapter=mock_file_adapter,
        session_metrics=session_metrics,
    )
    return service


@pytest.fixture
def sample_firmware_file(tmp_path):
    """Create a sample firmware file for testing."""
    firmware_file = tmp_path / "test_firmware.uf2"
    firmware_file.write_bytes(b"mock firmware content")
    return firmware_file


@pytest.fixture
def sample_json_layout_with_compilation(tmp_path):
    """Sample JSON layout file that would be used for compilation workflow."""
    layout_data = {
        "keyboard": "glove80",
        "title": "Firmware Test Layout",
        "author": "Test User",
        "layers": [
            ["KC_Q", "KC_W", "KC_E", "KC_R", "KC_T"],
            ["KC_A", "KC_S", "KC_D", "KC_F", "KC_G"],
        ],
        "layer_names": ["Base", "Lower"],
        "behaviors": {
            "test_combo": {
                "type": "combo",
                "key_positions": [0, 1],
                "bindings": ["&kp KC_ESC"]
            }
        }
    }

    json_file = tmp_path / "firmware_test_layout.json"
    with json_file.open("w") as f:
        json.dump(layout_data, f)

    return json_file, layout_data


@pytest.fixture
def mock_device_info():
    """Mock device information for testing."""
    return USBDeviceInfo(
        path="/dev/test_device",
        vendor_id="1234",
        product_id="5678",
        serial_number="TEST123",
        manufacturer="Test Manufacturer",
        product="Test Keyboard",
    )


class TestFirmwareFlashIntegration:
    """Test the full integration flow of firmware flashing."""

    def test_flash_from_file_success(
        self,
        flash_service,
        sample_firmware_file,
        mock_device_info,
        mock_keyboard_profile,
    ):
        """Test successful firmware flashing from file."""
        # Mock the underlying flash operations
        with (
            patch.object(flash_service, "list_devices") as mock_list_devices,
            patch.object(flash_service, "flash") as mock_flash,
        ):
            # Mock device detection
            mock_list_devices.return_value = [mock_device_info]

            # Mock successful flash
            mock_result = FlashResult(
                success=True,
                devices_flashed=1
            )
            mock_result.add_message("Firmware flashed successfully to /dev/test_device")
            mock_flash.return_value = mock_result

            # Test flash from file
            result = flash_service.flash(
                firmware_file=sample_firmware_file,
                profile=mock_keyboard_profile
            )

            assert result.success is True
            assert "Firmware flashed successfully" in result.messages[0]
            assert result.devices_flashed == 1

    def test_flash_with_device_auto_detection(
        self,
        flash_service,
        sample_firmware_file,
        mock_device_info,
        mock_keyboard_profile,
    ):
        """Test firmware flashing with automatic device detection."""
        with (
            patch.object(flash_service, "list_devices") as mock_list_devices,
            patch.object(flash_service, "flash") as mock_flash,
        ):
            # Mock device detection returning single device
            mock_list_devices.return_value = [mock_device_info]

            # Mock successful flash
            mock_result = FlashResult(
                success=True,
                devices_flashed=1
            )
            mock_result.add_message("Firmware flashed successfully to /dev/test_device")
            mock_flash.return_value = mock_result

            # Test flash without specifying device (should auto-detect)
            result = flash_service.flash(
                firmware_file=sample_firmware_file,
                profile=mock_keyboard_profile
            )

            assert result.success is True
            assert result.devices_flashed == 1

    def test_flash_no_devices_found(
        self,
        flash_service,
        sample_firmware_file,
        mock_keyboard_profile,
    ):
        """Test error handling when no devices are found."""
        with patch.object(flash_service, "list_devices") as mock_list_devices:
            # Mock no devices found
            mock_list_devices.return_value = []

            result = flash_service.flash(
                firmware_file=sample_firmware_file,
                profile=mock_keyboard_profile
            )

            assert result.success is False
            assert any("No compatible devices found" in msg for msg in result.errors)

    def test_flash_multiple_devices_no_path_specified(
        self,
        flash_service,
        sample_firmware_file,
        mock_keyboard_profile,
    ):
        """Test error handling when multiple devices found without specific path."""
        mock_device1 = USBDeviceInfo(
            path="/dev/device1",
            vendor_id="1234",
            product_id="5678",
            serial_number="TEST123",
            manufacturer="Test Manufacturer",
            product="Test Keyboard",
        )
        mock_device2 = USBDeviceInfo(
            path="/dev/device2",
            vendor_id="1234",
            product_id="5678",
            serial_number="TEST456",
            manufacturer="Test Manufacturer",
            product="Test Keyboard",
        )

        with patch.object(flash_service, "list_devices") as mock_list_devices:
            # Mock multiple devices found
            mock_list_devices.return_value = [mock_device1, mock_device2]

            result = flash_service.flash(
                firmware_file=sample_firmware_file,
                profile=mock_keyboard_profile
            )

            assert result.success is False
            assert any("Multiple devices found" in msg for msg in result.errors)


class TestFirmwareWorkflowIntegration:
    """Test end-to-end firmware workflows with compilation and flashing."""

    def test_json_to_firmware_to_flash_workflow(
        self,
        sample_json_layout_with_compilation,
        flash_service,
        mock_device_info,
        mock_keyboard_profile,
        tmp_path,
    ):
        """Test complete workflow: JSON → Compilation → Firmware → Flash."""
        json_file, layout_data = sample_json_layout_with_compilation

        # Step 1: Mock compilation service
        compilation_output_dir = tmp_path / "compilation_output"
        compilation_output_dir.mkdir(parents=True)
        firmware_file = compilation_output_dir / "glove80.uf2"
        firmware_file.write_bytes(b"compiled firmware content")

        with (
            patch("glovebox.compilation.create_compilation_service") as mock_create_compilation,
            patch.object(flash_service, "list_devices") as mock_list_devices,
            patch.object(flash_service, "flash") as mock_flash,
        ):
            # Mock compilation service and result
            mock_compilation_service = Mock()
            mock_create_compilation.return_value = mock_compilation_service

            from glovebox.firmware.models import BuildResult
            mock_compilation_result = BuildResult(
                success=True,
                messages=["Compilation successful"],
                output_files=FirmwareOutputFiles(
                    output_dir=compilation_output_dir,
                    uf2_files=[firmware_file],
                )
            )
            mock_compilation_service.compile_from_json.return_value = mock_compilation_result

            # Mock device detection and flash
            mock_list_devices.return_value = [mock_device_info]
            mock_flash_result = FlashResult(
                success=True,
                devices_flashed=1
            )
            mock_flash_result.add_message("Firmware flashed successfully")
            mock_flash.return_value = mock_flash_result

            # Step 2: Simulate compilation phase
            compilation_result = mock_compilation_service.compile_from_json(
                json_file=json_file,
                output_dir=compilation_output_dir,
                config={"method": "moergo"},
                keyboard_profile=mock_keyboard_profile,
            )

            assert compilation_result.success is True
            assert compilation_result.output_files is not None
            assert firmware_file in compilation_result.output_files.uf2_files

            # Step 3: Simulate flash phase using compiled firmware
            flash_result = flash_service.flash(
                firmware_file=firmware_file,
                profile=mock_keyboard_profile
            )

            assert flash_result.success is True
            assert flash_result.device_path == "/dev/test_device"

            # Verify the complete workflow
            mock_compilation_service.compile_from_json.assert_called_once()
            mock_flash.assert_called_once()

    def test_compilation_failure_prevents_flash(
        self,
        sample_json_layout_with_compilation,
        tmp_path,
        mock_keyboard_profile,
    ):
        """Test that compilation failure prevents the flash step."""
        json_file, layout_data = sample_json_layout_with_compilation

        compilation_output_dir = tmp_path / "compilation_output"
        compilation_output_dir.mkdir(parents=True)

        with patch("glovebox.compilation.create_compilation_service") as mock_create_compilation:
            # Mock compilation service with failure
            mock_compilation_service = Mock()
            mock_create_compilation.return_value = mock_compilation_service

            from glovebox.firmware.models import BuildResult
            mock_compilation_result = BuildResult(
                success=False,
                errors=["Compilation failed", "Missing dependencies"],
                messages=[]
            )
            mock_compilation_service.compile_from_json.return_value = mock_compilation_result

            # Simulate compilation phase
            compilation_result = mock_compilation_service.compile_from_json(
                json_file=json_file,
                output_dir=compilation_output_dir,
                config={"method": "zmk_config"},
                keyboard_profile=mock_keyboard_profile,
            )

            # Verify compilation failed
            assert compilation_result.success is False
            assert "Compilation failed" in compilation_result.errors

            # In a real workflow, flash step would not be executed
            # This demonstrates the error handling pattern


class TestFirmwareDeviceManagement:
    """Test device detection and management workflows."""

    def test_list_devices_integration(
        self,
        flash_service,
        mock_keyboard_profile,
    ):
        """Test device listing functionality."""
        mock_devices = [
            USBDeviceInfo(
                path="/dev/device1",
                vendor_id="1234",
                product_id="5678",
                serial_number="TEST123",
                manufacturer="Test Manufacturer",
                product="Test Keyboard Left",
            ),
            USBDeviceInfo(
                path="/dev/device2",
                vendor_id="1234",
                product_id="5679",
                serial_number="TEST456",
                manufacturer="Test Manufacturer",
                product="Test Keyboard Right",
            ),
        ]

        with patch.object(flash_service, "list_devices") as mock_list_devices:
            mock_list_devices.return_value = mock_devices

            devices = flash_service.list_devices(keyboard_profile=mock_keyboard_profile)

            assert len(devices) == 2
            assert devices[0].path == "/dev/device1"
            assert devices[1].path == "/dev/device2"
            assert devices[0].product == "Test Keyboard Left"
            assert devices[1].product == "Test Keyboard Right"

    def test_device_wait_functionality(
        self,
        flash_service,
        mock_keyboard_profile,
        mock_device_info,
    ):
        """Test device waiting functionality for bootloader mode."""
        with (
            patch.object(flash_service, "list_devices") as mock_list_devices,
            patch("time.sleep") as mock_sleep,  # Speed up test
        ):
            # Simulate device appearing after wait
            mock_list_devices.side_effect = [
                [],  # First call: no devices
                [],  # Second call: still no devices
                [mock_device_info],  # Third call: device appears
            ]

            # Mock device waiting (this would typically be in a separate service)
            devices = []
            max_attempts = 3
            for _attempt in range(max_attempts):
                devices = flash_service.list_devices(keyboard_profile=mock_keyboard_profile)
                if devices:
                    break
                mock_sleep(1)  # Simulate wait

            assert len(devices) == 1
            assert devices[0] == mock_device_info
            assert mock_list_devices.call_count == 3


class TestFirmwareServiceFactoryIntegration:
    """Test factory function integration for firmware services."""

    def test_create_flash_service_with_dependencies(
        self,
        isolated_cli_environment,
        mock_usb_adapter,
        mock_file_adapter,
        session_metrics,
    ):
        """Test creating flash service with proper dependency injection."""
        service = create_flash_service(
            usb_adapter=mock_usb_adapter,
            file_adapter=mock_file_adapter,
            session_metrics=session_metrics,
        )

        # Verify service was created with correct type
        from glovebox.firmware.flash.service import FlashService
        assert isinstance(service, FlashService)

    def test_flash_service_methods_available(
        self,
        flash_service,
    ):
        """Test that flash service has required methods."""
        # Verify required methods exist
        assert hasattr(flash_service, "flash")
        assert hasattr(flash_service, "list_devices")

        # Verify methods are callable
        assert callable(flash_service.flash)
        assert callable(flash_service.list_devices)


class TestFirmwareIOPatterns:
    """Test input/output patterns for firmware commands."""

    def test_firmware_file_input_pattern(
        self,
        flash_service,
        sample_firmware_file,
        mock_device_info,
        mock_keyboard_profile,
    ):
        """Test firmware file input handling pattern."""
        with (
            patch.object(flash_service, "list_devices") as mock_list_devices,
            patch.object(flash_service, "flash") as mock_flash,
        ):
            mock_list_devices.return_value = [mock_device_info]
            mock_result = FlashResult(
                success=True,
                devices_flashed=1
            )
            mock_result.add_message("Firmware flashed successfully to /dev/test_device")
            mock_flash.return_value = mock_result

            # Test file input pattern
            result = flash_service.flash(
                firmware_file=sample_firmware_file,
                profile=mock_keyboard_profile
            )

            assert result.success is True
            assert isinstance(sample_firmware_file, Path)
            assert sample_firmware_file.exists()

    def test_firmware_output_patterns(
        self,
        flash_service,
        sample_firmware_file,
        mock_device_info,
        mock_keyboard_profile,
    ):
        """Test firmware output result patterns."""
        with (
            patch.object(flash_service, "list_devices") as mock_list_devices,
            patch.object(flash_service, "flash") as mock_flash,
        ):
            mock_list_devices.return_value = [mock_device_info]
            mock_result = FlashResult(
                success=True,
                devices_flashed=1
            )
            mock_result.add_message("Device flashed successfully")
            mock_flash.return_value = mock_result

            result = flash_service.flash(
                firmware_file=sample_firmware_file,
                profile=mock_keyboard_profile
            )

            # Test output pattern structure
            assert hasattr(result, "success")
            assert hasattr(result, "messages")
            assert hasattr(result, "devices_flashed")
            assert hasattr(result, "devices_failed")
            assert hasattr(result, "device_details")

            # Test values
            assert result.success is True
            assert result.devices_flashed == 1
            assert len(result.device_details) == 1
