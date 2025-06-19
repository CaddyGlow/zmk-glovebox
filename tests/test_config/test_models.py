"""Tests for configuration models using Pydantic Settings.

This module tests the UserConfigData model and its validation,
including profile validation, environment variable integration,
and nested configuration structures.
"""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from glovebox.config.models import (
    FirmwareFlashConfig,
    UserConfigData,
    UserFirmwareConfig,
)


class TestFirmwareFlashConfig:
    """Tests for FirmwareFlashConfig model."""

    def test_default_values(self):
        """Test default values for firmware flash configuration."""
        config = FirmwareFlashConfig()

        assert config.timeout == 60
        assert config.count == 2
        assert config.track_flashed is True
        assert config.skip_existing is False

    def test_valid_values(self):
        """Test creation with valid values."""
        config = FirmwareFlashConfig(
            timeout=120, count=5, track_flashed=False, skip_existing=True
        )

        assert config.timeout == 120
        assert config.count == 5
        assert config.track_flashed is False
        assert config.skip_existing is True

    def test_timeout_validation(self):
        """Test timeout field validation."""
        # Valid timeout
        config = FirmwareFlashConfig(timeout=1)
        assert config.timeout == 1

        # Invalid timeout (negative)
        with pytest.raises(ValidationError) as exc_info:
            FirmwareFlashConfig(timeout=-1)
        assert "greater than or equal to 1" in str(exc_info.value)

        # Invalid timeout (zero)
        with pytest.raises(ValidationError) as exc_info:
            FirmwareFlashConfig(timeout=0)
        assert "greater than or equal to 1" in str(exc_info.value)

    def test_count_validation(self):
        """Test count field validation."""
        # Valid counts
        config = FirmwareFlashConfig(count=0)  # 0 means infinite
        assert config.count == 0

        config = FirmwareFlashConfig(count=10)
        assert config.count == 10

        # Invalid count (negative)
        with pytest.raises(ValidationError) as exc_info:
            FirmwareFlashConfig(count=-1)
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_type_conversion(self):
        """Test automatic type conversion."""
        # String to int conversion
        config = FirmwareFlashConfig(timeout=120, count=5)
        assert config.timeout == 120
        assert config.count == 5

        # String to bool conversion
        config = FirmwareFlashConfig(track_flashed=False, skip_existing=True)
        assert config.track_flashed is False
        assert config.skip_existing is True


class TestUserFirmwareConfig:
    """Tests for UserFirmwareConfig model."""

    def test_default_nested_structure(self):
        """Test default nested firmware configuration."""
        config = UserFirmwareConfig()

        assert isinstance(config.flash, FirmwareFlashConfig)
        assert config.flash.timeout == 60
        assert config.flash.count == 2
        assert config.flash.track_flashed is True
        assert config.flash.skip_existing is False

    def test_nested_configuration(self):
        """Test creating nested configuration."""
        config = UserFirmwareConfig(
            flash=FirmwareFlashConfig(
                timeout=180, count=10, track_flashed=False, skip_existing=True
            )
        )

        assert config.flash.timeout == 180
        assert config.flash.count == 10
        assert config.flash.track_flashed is False
        assert config.flash.skip_existing is True

    def test_dict_initialization(self):
        """Test initializing with nested dictionary."""
        config = UserFirmwareConfig(
            flash=FirmwareFlashConfig(
                timeout=300,
                count=1,
                track_flashed=False,
                skip_existing=True,
            )
        )

        assert config.flash.timeout == 300
        assert config.flash.count == 1
        assert config.flash.track_flashed is False
        assert config.flash.skip_existing is True


class TestUserConfigData:
    """Tests for UserConfigData model using Pydantic Settings."""

    def test_default_values(self, clean_environment):
        """Test default configuration values."""
        config = UserConfigData()

        assert config.profile == "glove80/v25.05"
        assert config.log_level == "INFO"
        assert config.keyboard_paths == []
        assert config.firmware.flash.timeout == 60
        assert config.firmware.flash.count == 2
        assert config.firmware.flash.track_flashed is True
        assert config.firmware.flash.skip_existing is False

    def test_custom_values(self, clean_environment):
        """Test creating configuration with custom values."""
        config = UserConfigData(
            profile="custom/v1.0",
            log_level="DEBUG",
            keyboard_paths=[Path("/path/to/keyboards")],
            firmware=UserFirmwareConfig(
                flash=FirmwareFlashConfig(
                    timeout=120,
                    count=5,
                    track_flashed=False,
                    skip_existing=True,
                )
            ),
        )

        assert config.profile == "custom/v1.0"
        assert config.log_level == "DEBUG"
        assert config.keyboard_paths == [Path("/path/to/keyboards")]
        assert config.firmware.flash.timeout == 120
        assert config.firmware.flash.count == 5
        assert config.firmware.flash.track_flashed is False
        assert config.firmware.flash.skip_existing is True

    def test_profile_validation(self, clean_environment, profile_test_cases):
        """Test profile validation with various inputs."""
        for profile, is_valid, _error_desc in profile_test_cases:
            if is_valid:
                config = UserConfigData(profile=profile)
                assert config.profile == profile
            else:
                with pytest.raises(ValidationError) as exc_info:
                    UserConfigData(profile=profile)
                error_msg = str(exc_info.value)
                assert "Profile must be in format 'keyboard/firmware'" in error_msg

    def test_log_level_validation(self, clean_environment, log_level_test_cases):
        """Test log level validation and normalization."""
        for level, is_valid, expected in log_level_test_cases:
            if is_valid:
                config = UserConfigData(log_level=level)
                assert config.log_level == expected
            else:
                with pytest.raises(ValidationError) as exc_info:
                    UserConfigData(log_level=level)
                error_msg = str(exc_info.value)
                assert "Log level must be one of" in error_msg

    def test_keyboard_paths_validation(self, clean_environment):
        """Test keyboard paths validation."""
        # Valid paths
        config = UserConfigData(keyboard_paths=[Path("/path/one"), Path("~/path/two")])
        assert config.keyboard_paths == [Path("/path/one"), Path("~/path/two")]

        # Empty list is valid
        config = UserConfigData(keyboard_paths=[])
        assert config.keyboard_paths == []

        # Mixed types should be converted to Path objects
        config = UserConfigData(
            keyboard_paths=[Path("path"), Path("123")]
        )  # Both as Path objects
        assert config.keyboard_paths == [Path("path"), Path("123")]

    def test_environment_variable_override(self, mock_environment):
        """Test environment variable override functionality."""
        config = UserConfigData()

        # Environment variables should override defaults
        assert config.profile == "env_keyboard/v2.0"
        assert config.log_level == "ERROR"
        assert config.firmware.flash.timeout == 180
        assert config.firmware.flash.count == 10
        assert config.firmware.flash.track_flashed is False
        assert config.firmware.flash.skip_existing is True

    def test_partial_environment_override(self, clean_environment):
        """Test partial environment variable override."""
        # Set only some environment variables
        os.environ["GLOVEBOX_PROFILE"] = "partial/override"
        os.environ["GLOVEBOX_FIRMWARE__FLASH__TIMEOUT"] = "999"

        config = UserConfigData()

        # Overridden values
        assert config.profile == "partial/override"
        assert config.firmware.flash.timeout == 999

        # Default values for non-overridden fields
        assert config.log_level == "INFO"
        assert config.firmware.flash.count == 2

    def test_invalid_environment_values(self, clean_environment):
        """Test handling of invalid environment variable values."""
        # Invalid profile format (empty string)
        os.environ["GLOVEBOX_PROFILE"] = ""

        with pytest.raises(ValidationError) as exc_info:
            UserConfigData()
        assert "Profile must be in format" in str(exc_info.value)

    def test_environment_variable_naming(self, clean_environment):
        """Test environment variable naming conventions."""
        # Test nested delimiter
        os.environ["GLOVEBOX_FIRMWARE__FLASH__TIMEOUT"] = "555"
        os.environ["GLOVEBOX_FIRMWARE__FLASH__SKIP_EXISTING"] = "true"

        config = UserConfigData()

        assert config.firmware.flash.timeout == 555
        assert config.firmware.flash.skip_existing is True

    def test_case_insensitive_env_vars(self, clean_environment):
        """Test case insensitive environment variables."""
        # Test mixed case environment variables
        os.environ["GLOVEBOX_PROFILE"] = "lowercase/test"
        os.environ["GLOVEBOX_LOG_LEVEL"] = "debug"

        config = UserConfigData()

        assert config.profile == "lowercase/test"
        assert config.log_level == "DEBUG"  # Should be normalized to uppercase

    def test_expanded_keyboard_paths(self, clean_environment):
        """Test keyboard path functionality."""
        config = UserConfigData(
            keyboard_paths=[
                Path("~/home/keyboards"),
                Path("$HOME/other"),
                Path("/absolute/path"),
            ]
        )

        # keyboard_paths are Path objects
        paths = config.keyboard_paths

        # Should return Path objects
        assert all(hasattr(path, "resolve") for path in paths)
        assert all(isinstance(path, Path) for path in paths)

        # Paths are stored as-is - expansion happens when resolved if needed
        path_strs = [str(path) for path in paths]
        assert "~/home/keyboards" in path_strs
        assert "$HOME/other" in path_strs
        assert "/absolute/path" in path_strs

    def test_dict_initialization(self, clean_environment):
        """Test initialization from dictionary (like YAML loading)."""
        config = UserConfigData(
            profile="dict/test",
            log_level="WARNING",
            keyboard_paths=[Path("/dict/path")],
            firmware=UserFirmwareConfig(
                flash=FirmwareFlashConfig(
                    timeout=777,
                    count=7,
                    track_flashed=False,
                    skip_existing=True,
                )
            ),
        )

        assert config.profile == "dict/test"
        assert config.log_level == "WARNING"
        assert config.keyboard_paths == [Path("/dict/path")]
        assert config.firmware.flash.timeout == 777
        assert config.firmware.flash.count == 7
        assert config.firmware.flash.track_flashed is False
        assert config.firmware.flash.skip_existing is True

    def test_extra_fields_ignored(self, clean_environment):
        """Test that extra fields are ignored due to extra='ignore'."""
        # Should not raise an error due to extra fields (extra fields are ignored)
        config = UserConfigData(profile="test/profile")
        assert config.profile == "test/profile"

        # Extra fields should not be accessible
        assert not hasattr(config, "unknown_field")
        assert not hasattr(config, "another_unknown")


class TestConfigurationValidation:
    """Tests for comprehensive configuration validation."""

    def test_complex_valid_configuration(self, clean_environment):
        """Test a complex but valid configuration."""
        config = UserConfigData(
            profile="complex_keyboard/v2.1.0",
            log_level="debug",
            keyboard_paths=[
                Path("~/my-keyboards"),
                Path("/usr/local/share/keyboards"),
                Path("$HOME/.config/keyboards"),
            ],
            firmware=UserFirmwareConfig(
                flash=FirmwareFlashConfig(
                    timeout=300,
                    count=0,  # Infinite
                    track_flashed=True,
                    skip_existing=False,
                )
            ),
        )

        assert config.profile == "complex_keyboard/v2.1.0"
        assert config.log_level == "DEBUG"  # Normalized
        assert len(config.keyboard_paths) == 3
        assert config.firmware.flash.timeout == 300
        assert config.firmware.flash.count == 0
        assert config.firmware.flash.track_flashed is True
        assert config.firmware.flash.skip_existing is False

    def test_minimal_valid_configuration(self, clean_environment):
        """Test minimal valid configuration."""
        config = UserConfigData(profile="minimal/v1")

        # Should use defaults for unspecified fields
        assert config.profile == "minimal/v1"
        assert config.log_level == "INFO"
        assert config.keyboard_paths == []
        assert config.firmware.flash.timeout == 60

    def test_model_serialization(self, clean_environment):
        """Test that model can be serialized to dict."""
        config = UserConfigData(
            profile="serialize/test",
            log_level="ERROR",
            keyboard_paths=[Path("/test/path")],
        )

        # Test dict conversion
        config_dict = config.model_dump(by_alias=True, mode="json")

        assert config_dict["profile"] == "serialize/test"
        assert config_dict["log_level"] == "ERROR"
        assert config_dict["keyboard_paths"] == [
            "/test/path"
        ]  # Path objects are serialized to strings
        assert "firmware" in config_dict
        assert "flash" in config_dict["firmware"]
