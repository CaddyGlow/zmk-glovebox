"""Tests for configuration models using Pydantic Settings.

This module tests the UserConfigData model and its validation,
including profile validation, environment variable integration,
and nested configuration structures.
"""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from glovebox.cli.helpers.theme import IconMode
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
        assert config.logging_config is not None
        assert config.profiles_paths == []
        assert config.icon_mode == IconMode.EMOJI  # Default value
        assert config.firmware.flash.timeout == 60
        assert config.firmware.flash.count == 2
        assert config.firmware.flash.track_flashed is True
        assert config.firmware.flash.skip_existing is False

    def test_custom_values(self, clean_environment):
        """Test creating configuration with custom values."""
        config = UserConfigData(
            profile="custom/v1.0",
            profiles_paths=[Path("/path/to/keyboards")],
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
        assert config.profiles_paths == [Path("/path/to/keyboards")]
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

    def test_logging_config_validation(self, clean_environment):
        """Test logging configuration validation."""
        config = UserConfigData()
        # Logging config should be properly initialized
        assert config.logging_config is not None
        assert len(config.logging_config.handlers) > 0

    def test_keyboard_paths_validation(self, clean_environment):
        """Test keyboard paths validation."""
        # Valid paths (note: ~ gets expanded by the field validator)
        config = UserConfigData(profiles_paths=[Path("/path/one"), Path("~/path/two")])
        assert len(config.profiles_paths) == 2
        assert config.profiles_paths[0] == Path("/path/one")
        # Second path will be expanded by expanduser()
        assert str(config.profiles_paths[1]).endswith("path/two")

        # Empty list is valid
        config = UserConfigData(profiles_paths=[])
        assert config.profiles_paths == []

        # Mixed types should be converted to Path objects
        config = UserConfigData(
            profiles_paths=[Path("path"), Path("123")]
        )  # Both as Path objects
        assert len(config.profiles_paths) == 2
        assert isinstance(config.profiles_paths[0], Path)
        assert isinstance(config.profiles_paths[1], Path)

    def test_environment_variable_override(self, mock_environment):
        """Test environment variable override functionality."""
        config = UserConfigData()

        # Environment variables should override defaults
        assert config.profile == "env_keyboard/v2.0"
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

        config = UserConfigData()

        assert config.profile == "lowercase/test"

    def test_expanded_keyboard_paths(self, clean_environment):
        """Test keyboard path functionality."""
        config = UserConfigData(
            profiles_paths=[
                Path("~/home/keyboards"),
                Path("$HOME/other"),
                Path("/absolute/path"),
            ]
        )

        # keyboard_paths are Path objects
        paths = config.profiles_paths

        # Should return Path objects
        assert all(hasattr(path, "resolve") for path in paths)
        assert all(isinstance(path, Path) for path in paths)

        # Paths get expanded by the field validator
        path_strs = [str(path) for path in paths]
        # After expansion, should contain the expanded paths
        assert any("home/keyboards" in path for path in path_strs)
        assert any("other" in path for path in path_strs)
        assert "/absolute/path" in path_strs

    def test_dict_initialization(self, clean_environment):
        """Test initialization from dictionary (like YAML loading)."""
        config = UserConfigData(
            profile="dict/test",
            profiles_paths=[Path("/dict/path")],
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
        assert config.profiles_paths == [Path("/dict/path")]
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
            profiles_paths=[
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
        assert len(config.profiles_paths) == 3
        assert config.firmware.flash.timeout == 300
        assert config.firmware.flash.count == 0
        assert config.firmware.flash.track_flashed is True
        assert config.firmware.flash.skip_existing is False

    def test_minimal_valid_configuration(self, clean_environment):
        """Test minimal valid configuration."""
        config = UserConfigData(profile="minimal/v1")

        # Should use defaults for unspecified fields
        assert config.profile == "minimal/v1"
        assert config.profiles_paths == []
        assert config.firmware.flash.timeout == 60

    def test_model_serialization(self, clean_environment):
        """Test that model can be serialized to dict."""
        config = UserConfigData(
            profile="serialize/test",
            profiles_paths=[Path("/test/path")],
        )

        # Test dict conversion
        config_dict = config.model_dump(by_alias=True, mode="json")

        assert config_dict["profile"] == "serialize/test"
        assert config_dict["profiles_paths"] == [
            "/test/path"
        ]  # Path objects are serialized to strings
        assert "firmware" in config_dict
        assert "flash" in config_dict["firmware"]


class TestIconModeIntegration:
    """Tests for IconMode enum integration in UserConfigData."""

    def test_icon_mode_default_value(self, clean_environment):
        """Test that icon_mode defaults to EMOJI."""
        config = UserConfigData()
        assert config.icon_mode == IconMode.EMOJI
        assert isinstance(config.icon_mode, IconMode)

    def test_icon_mode_string_validation(self, clean_environment):
        """Test validation of icon_mode from string values."""
        # Valid string values should convert to enum
        for mode_str, expected_enum in [
            ("emoji", IconMode.EMOJI),
            ("nerdfont", IconMode.NERDFONT),
            ("text", IconMode.TEXT),
            ("EMOJI", IconMode.EMOJI),  # Case insensitive
            ("NERDFONT", IconMode.NERDFONT),
            ("TEXT", IconMode.TEXT),
            (" emoji ", IconMode.EMOJI),  # Whitespace stripped
            (" NERDFONT ", IconMode.NERDFONT),
        ]:
            config = UserConfigData(icon_mode=mode_str)  # type: ignore[arg-type]
            assert config.icon_mode == expected_enum
            assert isinstance(config.icon_mode, IconMode)

    def test_icon_mode_enum_validation(self, clean_environment):
        """Test validation of icon_mode from IconMode enum values."""
        for enum_value in [IconMode.EMOJI, IconMode.NERDFONT, IconMode.TEXT]:
            config = UserConfigData(icon_mode=enum_value)
            assert config.icon_mode == enum_value
            assert isinstance(config.icon_mode, IconMode)

    def test_icon_mode_invalid_string(self, clean_environment):
        """Test that invalid string values raise ValidationError."""
        invalid_modes = ["invalid", "unknown", "123", "", "nerd_font", "emojis"]

        for invalid_mode in invalid_modes:
            with pytest.raises(ValidationError) as exc_info:
                UserConfigData(icon_mode=invalid_mode)  # type: ignore[arg-type]
            error_msg = str(exc_info.value)
            assert "Icon mode must be one of" in error_msg
            assert "['emoji', 'nerdfont', 'text']" in error_msg

    def test_icon_mode_invalid_type(self, clean_environment):
        """Test that invalid types raise ValidationError."""
        invalid_values: list[object] = [123, None, [], {}, True, False]

        for invalid_value in invalid_values:
            with pytest.raises(ValidationError) as exc_info:
                UserConfigData(icon_mode=invalid_value)  # type: ignore[arg-type]
            error_msg = str(exc_info.value)
            assert "Icon mode must be a string or IconMode enum" in error_msg

    def test_icon_mode_serialization(self, clean_environment):
        """Test that IconMode enum serializes to string in JSON mode."""
        config = UserConfigData(icon_mode=IconMode.NERDFONT)

        # Test model_dump with JSON mode
        serialized = config.model_dump(mode="json")
        assert serialized["icon_mode"] == "nerdfont"
        assert isinstance(serialized["icon_mode"], str)

        # Test model_dump_json
        json_str = config.model_dump_json()
        assert '"icon_mode":"nerdfont"' in json_str

    def test_icon_mode_round_trip(self, clean_environment):
        """Test that IconMode can be serialized and deserialized correctly."""
        for mode in [IconMode.EMOJI, IconMode.NERDFONT, IconMode.TEXT]:
            # Create config with enum
            config1 = UserConfigData(icon_mode=mode)

            # Serialize to dict (JSON mode)
            data = config1.model_dump(mode="json")

            # Deserialize back
            config2 = UserConfigData.model_validate(data)

            # Should match original
            assert config2.icon_mode == mode
            assert isinstance(config2.icon_mode, IconMode)

    def test_icon_mode_environment_variable(self, clean_environment):
        """Test icon_mode from environment variable."""
        test_cases = [
            ("emoji", IconMode.EMOJI),
            ("nerdfont", IconMode.NERDFONT),
            ("text", IconMode.TEXT),
            ("EMOJI", IconMode.EMOJI),
            ("TEXT", IconMode.TEXT),
        ]

        for env_value, expected_enum in test_cases:
            os.environ["GLOVEBOX_ICON_MODE"] = env_value
            try:
                config = UserConfigData()
                assert config.icon_mode == expected_enum
                assert isinstance(config.icon_mode, IconMode)
            finally:
                os.environ.pop("GLOVEBOX_ICON_MODE", None)

    def test_icon_mode_invalid_environment_variable(self, clean_environment):
        """Test that invalid environment variable values raise ValidationError."""
        os.environ["GLOVEBOX_ICON_MODE"] = "invalid_mode"

        try:
            with pytest.raises(ValidationError) as exc_info:
                UserConfigData()
            error_msg = str(exc_info.value)
            assert "Icon mode must be one of" in error_msg
        finally:
            os.environ.pop("GLOVEBOX_ICON_MODE", None)
