"""Tests for flash method configuration models."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from glovebox.config.flash_methods import (
    BootloaderFlashConfig,
    DFUFlashConfig,
    FlashMethodConfig,
    USBFlashConfig,
    WiFiFlashConfig,
)


class TestUSBFlashConfig:
    """Tests for USBFlashConfig model."""

    def test_required_fields(self):
        """Test that required fields are enforced."""
        with pytest.raises(ValidationError) as exc_info:
            USBFlashConfig()  # type: ignore[call-arg]
        assert "device_query" in str(exc_info.value)

    def test_default_values(self):
        """Test default values for USB flash configuration."""
        config = USBFlashConfig(device_query="removable=true")

        assert config.method_type == "usb"
        assert config.device_query == "removable=true"
        assert config.mount_timeout == 30
        assert config.copy_timeout == 60
        assert config.sync_after_copy is True
        assert config.fallback_methods == []

    def test_custom_values(self):
        """Test creation with custom values."""
        config = USBFlashConfig(
            device_query="vendor=Adafruit and serial~=GLV80-.*",
            mount_timeout=45,
            copy_timeout=120,
            sync_after_copy=False,
            fallback_methods=["dfu", "bootloader"],
        )

        assert config.method_type == "usb"
        assert config.device_query == "vendor=Adafruit and serial~=GLV80-.*"
        assert config.mount_timeout == 45
        assert config.copy_timeout == 120
        assert config.sync_after_copy is False
        assert config.fallback_methods == ["dfu", "bootloader"]

    def test_timeout_validation(self):
        """Test timeout field validation."""
        # Valid timeouts
        config = USBFlashConfig(device_query="test", mount_timeout=1, copy_timeout=1)
        assert config.mount_timeout == 1
        assert config.copy_timeout == 1

    def test_boolean_validation(self):
        """Test boolean field validation."""
        config = USBFlashConfig(device_query="test", sync_after_copy=True)
        assert config.sync_after_copy is True

        config = USBFlashConfig(device_query="test", sync_after_copy=False)
        assert config.sync_after_copy is False


class TestDFUFlashConfig:
    """Tests for DFUFlashConfig model."""

    def test_required_fields(self):
        """Test that required fields are enforced."""
        with pytest.raises(ValidationError) as exc_info:
            DFUFlashConfig()  # type: ignore[call-arg]
        error_str = str(exc_info.value)
        assert "vid" in error_str
        assert "pid" in error_str

    def test_default_values(self):
        """Test default values for DFU flash configuration."""
        config = DFUFlashConfig(vid="1234", pid="5678")

        assert config.method_type == "dfu"
        assert config.vid == "1234"
        assert config.pid == "5678"
        assert config.interface == 0
        assert config.alt_setting == 0
        assert config.timeout == 30
        assert config.fallback_methods == []

    def test_custom_values(self):
        """Test creation with custom values."""
        config = DFUFlashConfig(
            vid="ABCD",
            pid="EFGH",
            interface=1,
            alt_setting=2,
            timeout=60,
            fallback_methods=["usb"],
        )

        assert config.method_type == "dfu"
        assert config.vid == "ABCD"
        assert config.pid == "EFGH"
        assert config.interface == 1
        assert config.alt_setting == 2
        assert config.timeout == 60
        assert config.fallback_methods == ["usb"]

    def test_vid_pid_formats(self):
        """Test various VID/PID format handling."""
        # Hex strings
        config = DFUFlashConfig(vid="0x1234", pid="0xABCD")
        assert config.vid == "0x1234"
        assert config.pid == "0xABCD"

        # Decimal strings
        config = DFUFlashConfig(vid="4660", pid="43981")
        assert config.vid == "4660"
        assert config.pid == "43981"


class TestBootloaderFlashConfig:
    """Tests for BootloaderFlashConfig model."""

    def test_required_fields(self):
        """Test that required fields are enforced."""
        with pytest.raises(ValidationError) as exc_info:
            BootloaderFlashConfig()  # type: ignore[call-arg]
        assert "protocol" in str(exc_info.value)

    def test_default_values(self):
        """Test default values for bootloader flash configuration."""
        config = BootloaderFlashConfig(protocol="uart")

        assert config.method_type == "bootloader"
        assert config.protocol == "uart"
        assert config.port is None
        assert config.baud_rate == 115200
        assert config.reset_sequence == []
        assert config.fallback_methods == []

    def test_uart_configuration(self):
        """Test UART bootloader configuration."""
        config = BootloaderFlashConfig(
            protocol="uart",
            port="/dev/ttyUSB0",
            baud_rate=9600,
            reset_sequence=["DTR", "RTS"],
            fallback_methods=["usb"],
        )

        assert config.method_type == "bootloader"
        assert config.protocol == "uart"
        assert config.port == "/dev/ttyUSB0"
        assert config.baud_rate == 9600
        assert config.reset_sequence == ["DTR", "RTS"]
        assert config.fallback_methods == ["usb"]

    def test_spi_configuration(self):
        """Test SPI bootloader configuration."""
        config = BootloaderFlashConfig(
            protocol="spi",
            port="/dev/spidev0.0",
            reset_sequence=["RESET_LOW", "DELAY_100", "RESET_HIGH"],
        )

        assert config.protocol == "spi"
        assert config.port == "/dev/spidev0.0"
        assert config.reset_sequence == ["RESET_LOW", "DELAY_100", "RESET_HIGH"]

    def test_i2c_configuration(self):
        """Test I2C bootloader configuration."""
        config = BootloaderFlashConfig(protocol="i2c", port="/dev/i2c-1")

        assert config.protocol == "i2c"
        assert config.port == "/dev/i2c-1"


class TestWiFiFlashConfig:
    """Tests for WiFiFlashConfig model."""

    def test_required_fields(self):
        """Test that required fields are enforced."""
        with pytest.raises(ValidationError) as exc_info:
            WiFiFlashConfig()  # type: ignore[call-arg]
        assert "host" in str(exc_info.value)

    def test_default_values(self):
        """Test default values for WiFi flash configuration."""
        config = WiFiFlashConfig(host="192.168.1.100")

        assert config.method_type == "wifi"
        assert config.host == "192.168.1.100"
        assert config.port == 8080
        assert config.protocol == "http"
        assert config.auth_token is None
        assert config.fallback_methods == []

    def test_http_configuration(self):
        """Test HTTP WiFi flash configuration."""
        config = WiFiFlashConfig(
            host="keyboard.local",
            port=8080,
            protocol="http",
            auth_token="secret123",
            fallback_methods=["usb"],
        )

        assert config.method_type == "wifi"
        assert config.host == "keyboard.local"
        assert config.port == 8080
        assert config.protocol == "http"
        assert config.auth_token == "secret123"
        assert config.fallback_methods == ["usb"]

    def test_mqtt_configuration(self):
        """Test MQTT WiFi flash configuration."""
        config = WiFiFlashConfig(
            host="mqtt.example.com", port=1883, protocol="mqtt", auth_token="mqtt_token"
        )

        assert config.protocol == "mqtt"
        assert config.port == 1883
        assert config.auth_token == "mqtt_token"

    def test_websocket_configuration(self):
        """Test WebSocket WiFi flash configuration."""
        config = WiFiFlashConfig(
            host="ws.keyboard.dev", port=9001, protocol="websocket"
        )

        assert config.protocol == "websocket"
        assert config.port == 9001

    def test_hostname_formats(self):
        """Test various hostname format handling."""
        # IP address
        config = WiFiFlashConfig(host="10.0.0.1")
        assert config.host == "10.0.0.1"

        # Hostname
        config = WiFiFlashConfig(host="keyboard")
        assert config.host == "keyboard"

        # FQDN
        config = WiFiFlashConfig(host="keyboard.example.com")
        assert config.host == "keyboard.example.com"


class TestFlashMethodConfigInheritance:
    """Tests for FlashMethodConfig base class behavior."""

    def test_abstract_base_class(self):
        """Test that FlashMethodConfig cannot be instantiated directly."""
        # FlashMethodConfig is abstract but Pydantic allows it
        config = FlashMethodConfig(method_type="test")
        assert config.method_type == "test"
        assert config.fallback_methods == []

    def test_fallback_methods_inheritance(self):
        """Test that all concrete classes inherit fallback_methods behavior."""
        usb_config = USBFlashConfig(device_query="test", fallback_methods=["dfu"])
        dfu_config = DFUFlashConfig(vid="1234", pid="5678", fallback_methods=["usb"])

        assert usb_config.fallback_methods == ["dfu"]
        assert dfu_config.fallback_methods == ["usb"]

    def test_polymorphic_behavior(self):
        """Test that configs can be treated polymorphically."""
        configs = [
            USBFlashConfig(device_query="removable=true"),
            DFUFlashConfig(vid="1234", pid="5678"),
            BootloaderFlashConfig(protocol="uart"),
            WiFiFlashConfig(host="192.168.1.1"),
        ]

        # All should have method_type and fallback_methods
        for config in configs:
            assert hasattr(config, "method_type")
            assert hasattr(config, "fallback_methods")
            assert isinstance(config.method_type, str)
            assert isinstance(config.fallback_methods, list)


class TestConfigurationValidation:
    """Tests for comprehensive configuration validation."""

    def test_valid_configurations(self):
        """Test various valid configuration combinations."""
        valid_configs = [
            USBFlashConfig(
                device_query="vendor=Custom and removable=true",
                mount_timeout=60,
                sync_after_copy=True,
            ),
            DFUFlashConfig(vid="0x1234", pid="0x5678", interface=1, timeout=45),
            BootloaderFlashConfig(
                protocol="uart",
                port="/dev/ttyACM0",
                baud_rate=57600,
                reset_sequence=["DTR"],
            ),
            WiFiFlashConfig(
                host="keyboard.local",
                port=9090,
                protocol="websocket",
                auth_token="secure_token",
            ),
        ]

        for config in valid_configs:
            # Should not raise any validation errors
            assert config is not None
            assert config.method_type in ["usb", "dfu", "bootloader", "wifi"]

    def test_model_serialization(self):
        """Test that models can be serialized to dict."""
        config = USBFlashConfig(
            device_query="test query",
            mount_timeout=90,
            copy_timeout=180,
            sync_after_copy=False,
            fallback_methods=["dfu"],
        )

        config_dict = config.model_dump()

        assert config_dict["method_type"] == "usb"
        assert config_dict["device_query"] == "test query"
        assert config_dict["mount_timeout"] == 90
        assert config_dict["copy_timeout"] == 180
        assert config_dict["sync_after_copy"] is False
        assert config_dict["fallback_methods"] == ["dfu"]

    def test_model_deserialization(self):
        """Test that models can be created from dict."""
        config_dict = {
            "method_type": "dfu",
            "vid": "ABCD",
            "pid": "EFGH",
            "interface": 2,
            "alt_setting": 1,
            "timeout": 120,
            "fallback_methods": ["usb", "bootloader"],
        }

        config = DFUFlashConfig.model_validate(config_dict)

        assert config.method_type == "dfu"
        assert config.vid == "ABCD"
        assert config.pid == "EFGH"
        assert config.interface == 2
        assert config.alt_setting == 1
        assert config.timeout == 120
        assert config.fallback_methods == ["usb", "bootloader"]

    def test_mixed_fallback_methods(self):
        """Test configurations with multiple fallback methods."""
        config = USBFlashConfig(
            device_query="complex query", fallback_methods=["dfu", "bootloader", "wifi"]
        )

        assert len(config.fallback_methods) == 3
        assert "dfu" in config.fallback_methods
        assert "bootloader" in config.fallback_methods
        assert "wifi" in config.fallback_methods
