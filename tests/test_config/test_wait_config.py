"""Tests for wait configuration functionality."""

import os
from pathlib import Path

import pytest

from glovebox.config.models.user import UserConfigData
from glovebox.config.user_config import create_user_config


class TestWaitConfiguration:
    """Test wait configuration functionality."""

    def test_default_wait_config(self):
        """Test default wait configuration values."""
        config = UserConfigData()

        assert config.firmware.flash.wait is False
        assert config.firmware.flash.poll_interval == 0.5
        assert config.firmware.flash.show_progress is True
        assert config.firmware.flash.timeout == 60
        assert config.firmware.flash.count == 2

    def test_environment_variable_override(self):
        """Test wait config from environment variables."""
        env_vars = {
            "GLOVEBOX_FIRMWARE__FLASH__WAIT": "true",
            "GLOVEBOX_FIRMWARE__FLASH__POLL_INTERVAL": "1.0",
            "GLOVEBOX_FIRMWARE__FLASH__SHOW_PROGRESS": "false",
        }

        # Set environment variables
        for key, value in env_vars.items():
            os.environ[key] = value

        try:
            config = UserConfigData()

            assert config.firmware.flash.wait is True
            assert config.firmware.flash.poll_interval == 1.0
            assert config.firmware.flash.show_progress is False
        finally:
            # Clean up environment variables
            for key in env_vars:
                os.environ.pop(key, None)

    def test_config_file_wait_settings(self, tmp_path):
        """Test wait config from YAML file."""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text("""
firmware:
  flash:
    wait: true
    timeout: 120
    poll_interval: 2.0
    show_progress: false
""")

        user_config = create_user_config(cli_config_path=config_file)

        assert user_config._config.firmware.flash.wait is True
        assert user_config._config.firmware.flash.timeout == 120
        assert user_config._config.firmware.flash.poll_interval == 2.0
        assert user_config._config.firmware.flash.show_progress is False

    def test_poll_interval_validation(self):
        """Test poll_interval field validation."""
        # Valid values
        config = UserConfigData(firmware={"flash": {"poll_interval": 0.5}})
        assert config.firmware.flash.poll_interval == 0.5

        config = UserConfigData(firmware={"flash": {"poll_interval": 5.0}})
        assert config.firmware.flash.poll_interval == 5.0

        # Invalid values should raise validation error
        with pytest.raises(ValueError):
            UserConfigData(firmware={"flash": {"poll_interval": 0.05}})  # Too small

        with pytest.raises(ValueError):
            UserConfigData(firmware={"flash": {"poll_interval": 10.0}})  # Too large

    def test_wait_config_precedence(self, tmp_path):
        """Test configuration precedence: env vars > config file."""
        # Create config file with one set of values
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text("""
firmware:
  flash:
    wait: false
    poll_interval: 1.0
    show_progress: true
""")

        # Set environment variable to override
        os.environ["GLOVEBOX_FIRMWARE__FLASH__WAIT"] = "true"

        try:
            user_config = create_user_config(cli_config_path=config_file)

            # Environment variable should override config file
            assert user_config._config.firmware.flash.wait is True
            # Other values should come from config file
            assert user_config._config.firmware.flash.poll_interval == 1.0
            assert user_config._config.firmware.flash.show_progress is True
        finally:
            os.environ.pop("GLOVEBOX_FIRMWARE__FLASH__WAIT", None)

    def test_partial_wait_config(self):
        """Test partial wait configuration with defaults."""
        # Only specify some wait settings
        config = UserConfigData(firmware={"flash": {"wait": True}})

        # Should use default for unspecified values
        assert config.firmware.flash.wait is True
        assert config.firmware.flash.poll_interval == 0.5  # default
        assert config.firmware.flash.show_progress is True  # default

    def test_wait_config_with_other_flash_settings(self):
        """Test wait config combined with other flash settings."""
        config = UserConfigData(
            firmware={
                "flash": {
                    "wait": True,
                    "poll_interval": 1.5,
                    "show_progress": False,
                    "timeout": 90,
                    "count": 3,
                    "track_flashed": False,
                    "skip_existing": True,
                }
            }
        )

        # Wait settings
        assert config.firmware.flash.wait is True
        assert config.firmware.flash.poll_interval == 1.5
        assert config.firmware.flash.show_progress is False

        # Other flash settings
        assert config.firmware.flash.timeout == 90
        assert config.firmware.flash.count == 3
        assert config.firmware.flash.track_flashed is False
        assert config.firmware.flash.skip_existing is True

    def test_invalid_wait_config_types(self):
        """Test invalid wait configuration types."""
        # Invalid wait type
        with pytest.raises(ValueError):
            UserConfigData(firmware={"flash": {"wait": "maybe"}})

        # Invalid poll_interval type
        with pytest.raises(ValueError):
            UserConfigData(firmware={"flash": {"poll_interval": "fast"}})

        # Invalid show_progress type
        with pytest.raises(ValueError):
            UserConfigData(firmware={"flash": {"show_progress": "yes"}})

    def test_wait_config_edge_values(self):
        """Test wait configuration edge values."""
        # Minimum valid poll_interval
        config = UserConfigData(firmware={"flash": {"poll_interval": 0.1}})
        assert config.firmware.flash.poll_interval == 0.1

        # Maximum valid poll_interval
        config = UserConfigData(firmware={"flash": {"poll_interval": 5.0}})
        assert config.firmware.flash.poll_interval == 5.0

    def test_wait_config_serialization(self, tmp_path):
        """Test wait config can be serialized and deserialized."""
        # Create config with wait settings
        original_config = UserConfigData(
            firmware={
                "flash": {
                    "wait": True,
                    "poll_interval": 2.0,
                    "show_progress": False,
                }
            }
        )

        # Serialize to YAML
        config_file = tmp_path / "serialized_config.yaml"
        import yaml

        with config_file.open("w") as f:
            yaml.dump(original_config.model_dump(), f)

        # Load back and verify
        user_config = create_user_config(cli_config_path=config_file)
        assert user_config._config.firmware.flash.wait is True
        assert user_config._config.firmware.flash.poll_interval == 2.0
        assert user_config._config.firmware.flash.show_progress is False
