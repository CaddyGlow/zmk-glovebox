"""Tests for keyboard-only profile functionality."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from glovebox.cli.helpers.profile import (
    create_profile_from_option,
    get_effective_profile,
)
from glovebox.config.keyboard_profile import (
    create_keyboard_profile,
)
from glovebox.config.models import KeyboardConfig, UserConfigData
from glovebox.core.errors import ConfigError


class TestKeyboardOnlyProfileValidation:
    """Tests for keyboard-only profile validation."""

    def test_keyboard_only_profile_validation(self):
        """Test that keyboard-only profile format is accepted."""
        # Test keyboard-only format
        config = UserConfigData(profile="glove80")
        assert config.profile == "glove80"

        # Test keyboard/firmware format still works
        config = UserConfigData(profile="glove80/v25.05")
        assert config.profile == "glove80/v25.05"

    def test_invalid_profile_formats(self):
        """Test that invalid profile formats are rejected."""
        # Empty profile
        with pytest.raises(ValidationError) as exc_info:
            UserConfigData(profile="")
        assert "Profile must be in format" in str(exc_info.value)

        # Profile with multiple slashes
        with pytest.raises(ValidationError) as exc_info:
            UserConfigData(profile="keyboard/firmware/extra")
        assert "Profile must be in format" in str(exc_info.value)

        # Profile with empty parts
        with pytest.raises(ValidationError) as exc_info:
            UserConfigData(profile="keyboard/")
        assert "Profile must be in format" in str(exc_info.value)

        # Profile with empty keyboard part
        with pytest.raises(ValidationError) as exc_info:
            UserConfigData(profile="/firmware")
        assert "Profile must be in format" in str(exc_info.value)

    def test_profile_whitespace_handling(self):
        """Test that whitespace in profiles is handled correctly."""
        # Keyboard-only with whitespace
        config = UserConfigData(profile="  glove80  ")
        assert config.profile == "glove80"

        # Keyboard/firmware with whitespace
        config = UserConfigData(profile="glove80/v25.05")
        assert config.profile == "glove80/v25.05"


class TestKeyboardConfigDefaults:
    """Tests for KeyboardConfig default values."""

    def test_minimal_keyboard_config(self):
        """Test KeyboardConfig with minimal required fields."""
        minimal_config = {
            "keyboard": "test_minimal",
            "description": "Test minimal keyboard",
            "vendor": "Test Vendor",
            "key_count": 10,
            "compile_methods": [
                {
                    "method_type": "docker",
                    "image": "test_image",
                    "repository": "test/repo",
                    "branch": "main",
                    "fallback_methods": ["local"],
                }
            ],
            "flash_methods": [
                {
                    "method_type": "usb",
                    "device_query": "test_query",
                    "mount_timeout": 30,
                    "copy_timeout": 60,
                    "sync_after_copy": True,
                    "fallback_methods": ["dfu"],
                },
                {
                    "method_type": "dfu",
                    "vid": "1234",
                    "pid": "5678",
                    "interface": 0,
                    "alt_setting": 0,
                    "timeout": 30,
                    "fallback_methods": [],
                },
            ],
            # Note: No firmwares or keymap sections
        }

        config = KeyboardConfig.model_validate(minimal_config)

        # Verify defaults are applied
        assert config.firmwares == {}
        assert config.keymap is not None
        assert config.keymap.includes == []
        assert config.keymap.system_behaviors == []
        assert config.keymap.kconfig_options == {}
        assert config.keymap.formatting.default_key_width == 4
        assert config.keymap.formatting.key_gap == " "

    def test_keyboard_config_with_partial_sections(self):
        """Test KeyboardConfig with partial firmwares/keymap sections."""
        config_data = {
            "keyboard": "test_partial",
            "description": "Test partial keyboard",
            "vendor": "Test Vendor",
            "key_count": 10,
            "compile_methods": [
                {
                    "method_type": "docker",
                    "image": "test_image",
                    "repository": "test/repo",
                    "branch": "main",
                    "fallback_methods": ["local"],
                }
            ],
            "flash_methods": [
                {
                    "method_type": "usb",
                    "device_query": "test_query",
                    "mount_timeout": 30,
                    "copy_timeout": 60,
                    "sync_after_copy": True,
                    "fallback_methods": ["dfu"],
                },
                {
                    "method_type": "dfu",
                    "vid": "1234",
                    "pid": "5678",
                    "interface": 0,
                    "alt_setting": 0,
                    "timeout": 30,
                    "fallback_methods": [],
                },
            ],
            "firmwares": {
                "v1.0": {
                    "version": "v1.0",
                    "description": "Version 1.0",
                    "build_options": {"repository": "test/repo", "branch": "v1.0"},
                }
            },
            # keymap section missing - should get defaults
        }

        config = KeyboardConfig.model_validate(config_data)

        # Verify firmwares are preserved and keymap gets defaults
        assert len(config.firmwares) == 1
        assert "v1.0" in config.firmwares
        assert config.keymap is not None
        assert config.keymap.includes == []


class TestKeyboardOnlyProfileCreation:
    """Tests for creating keyboard-only profiles."""

    def test_create_keyboard_profile_without_firmware(self):
        """Test creating a KeyboardProfile without firmware."""
        # Create a minimal keyboard config for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            keyboards_dir = Path(temp_dir) / "keyboards"
            keyboards_dir.mkdir()

            config_data = {
                "keyboard": "test_keyboard",
                "description": "Test keyboard",
                "vendor": "Test Vendor",
                "key_count": 10,
                "compile_methods": [
                    {
                        "method_type": "docker",
                        "image": "test_image",
                        "repository": "test/repo",
                        "branch": "main",
                        "fallback_methods": [],
                    }
                ],
                "flash_methods": [
                    {
                        "method_type": "usb",
                        "device_query": "test_query",
                        "mount_timeout": 30,
                        "copy_timeout": 60,
                        "sync_after_copy": True,
                        "fallback_methods": [],
                    }
                ],
            }

            config_file = keyboards_dir / "test_keyboard.yaml"
            with config_file.open("w") as f:
                yaml.dump(config_data, f)

            # Set environment variable to include our temp directory
            original_path = os.environ.get("GLOVEBOX_KEYBOARD_PATH", "")
            os.environ["GLOVEBOX_KEYBOARD_PATH"] = str(keyboards_dir)

            try:
                # Test creating keyboard-only profile
                profile = create_keyboard_profile(
                    "test_keyboard", firmware_version=None
                )

                assert profile.keyboard_name == "test_keyboard"
                assert profile.firmware_version is None
                assert profile.firmware_config is None
                assert profile.system_behaviors == []
                assert profile.kconfig_options == {}

            finally:
                # Restore environment
                if original_path:
                    os.environ["GLOVEBOX_KEYBOARD_PATH"] = original_path
                else:
                    os.environ.pop("GLOVEBOX_KEYBOARD_PATH", None)

    def test_create_keyboard_profile_with_firmware(self):
        """Test creating a KeyboardProfile with firmware still works."""
        # Create a keyboard config with firmware for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            keyboards_dir = Path(temp_dir) / "keyboards"
            keyboards_dir.mkdir()

            config_data = {
                "keyboard": "test_keyboard_fw",
                "description": "Test keyboard with firmware",
                "vendor": "Test Vendor",
                "key_count": 10,
                "flash": {
                    "method": "usb_mount",
                    "query": "test_query",
                    "usb_vid": "1234",
                    "usb_pid": "5678",
                },
                "build": {
                    "method": "docker",
                    "docker_image": "test_image",
                    "repository": "test/repo",
                    "branch": "main",
                },
                "firmwares": {
                    "v1.0": {
                        "version": "v1.0",
                        "description": "Version 1.0",
                        "build_options": {"repository": "test/repo", "branch": "v1.0"},
                    }
                },
            }

            config_file = keyboards_dir / "test_keyboard_fw.yaml"
            with config_file.open("w") as f:
                yaml.dump(config_data, f)

            # Set environment variable to include our temp directory
            original_path = os.environ.get("GLOVEBOX_KEYBOARD_PATH", "")
            os.environ["GLOVEBOX_KEYBOARD_PATH"] = str(keyboards_dir)

            try:
                # Test creating profile with firmware
                profile = create_keyboard_profile(
                    "test_keyboard_fw", firmware_version="v1.0"
                )

                assert profile.keyboard_name == "test_keyboard_fw"
                assert profile.firmware_version == "v1.0"
                assert profile.firmware_config is not None
                assert profile.firmware_config.version == "v1.0"

            finally:
                # Restore environment
                if original_path:
                    os.environ["GLOVEBOX_KEYBOARD_PATH"] = original_path
                else:
                    os.environ.pop("GLOVEBOX_KEYBOARD_PATH", None)


class TestProfileHelperFunctions:
    """Tests for profile helper functions."""

    def test_get_effective_profile_keyboard_only(self):
        """Test get_effective_profile with keyboard-only format."""
        # Test explicit keyboard-only profile
        effective = get_effective_profile("glove80")
        assert effective == "glove80"

        # Test explicit keyboard/firmware profile
        effective = get_effective_profile("glove80/v25.05")
        assert effective == "glove80/v25.05"

        # Test fallback when no profile provided
        effective = get_effective_profile(None)
        assert effective == "glove80/v25.05"  # DEFAULT_PROFILE

    def test_get_effective_profile_with_user_config(self):
        """Test get_effective_profile with user config providing keyboard-only default."""
        from glovebox.config.models import UserConfigData
        from glovebox.config.user_config import UserConfig

        # Create a real user config with keyboard-only profile
        config_data = UserConfigData(profile="custom_keyboard")

        # Mock user config with proper structure
        mock_user_config = UserConfig()
        mock_user_config._config = config_data

        # User config should be used when no explicit profile
        effective = get_effective_profile(None, mock_user_config)
        assert effective == "custom_keyboard"

        # Explicit profile should override user config
        effective = get_effective_profile("explicit_keyboard", mock_user_config)
        assert effective == "explicit_keyboard"

    def test_create_profile_from_option_keyboard_only(self):
        """Test create_profile_from_option with keyboard-only format."""
        # Create a minimal keyboard config for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            keyboards_dir = Path(temp_dir) / "keyboards"
            keyboards_dir.mkdir()

            config_data = {
                "keyboard": "test_option",
                "description": "Test keyboard for option parsing",
                "vendor": "Test Vendor",
                "key_count": 10,
                "flash": {
                    "method": "usb_mount",
                    "query": "test_query",
                    "usb_vid": "1234",
                    "usb_pid": "5678",
                },
                "build": {
                    "method": "docker",
                    "docker_image": "test_image",
                    "repository": "test/repo",
                    "branch": "main",
                },
            }

            config_file = keyboards_dir / "test_option.yaml"
            with config_file.open("w") as f:
                yaml.dump(config_data, f)

            # Set environment variable to include our temp directory
            original_path = os.environ.get("GLOVEBOX_KEYBOARD_PATH", "")
            os.environ["GLOVEBOX_KEYBOARD_PATH"] = str(keyboards_dir)

            try:
                # Test parsing keyboard-only profile option
                profile = create_profile_from_option("test_option")

                assert profile.keyboard_name == "test_option"
                assert profile.firmware_version is None
                assert profile.firmware_config is None

            finally:
                # Restore environment
                if original_path:
                    os.environ["GLOVEBOX_KEYBOARD_PATH"] = original_path
                else:
                    os.environ.pop("GLOVEBOX_KEYBOARD_PATH", None)


class TestKeyboardOnlyProfileErrorHandling:
    """Tests for error handling in keyboard-only profiles."""

    def test_nonexistent_keyboard_error_handling(self):
        """Test error handling for nonexistent keyboard."""
        with pytest.raises(ConfigError) as exc_info:
            create_keyboard_profile("nonexistent_keyboard")

        assert "Keyboard configuration not found" in str(exc_info.value)

    def test_firmware_not_found_with_keyboard_only_fallback(self):
        """Test that specifying nonexistent firmware fails, but keyboard-only works."""
        # Create a keyboard config without firmwares
        with tempfile.TemporaryDirectory() as temp_dir:
            keyboards_dir = Path(temp_dir) / "keyboards"
            keyboards_dir.mkdir()

            config_data = {
                "keyboard": "test_no_firmware",
                "description": "Test keyboard without firmwares",
                "vendor": "Test Vendor",
                "key_count": 10,
                "flash": {
                    "method": "usb_mount",
                    "query": "test_query",
                    "usb_vid": "1234",
                    "usb_pid": "5678",
                },
                "build": {
                    "method": "docker",
                    "docker_image": "test_image",
                    "repository": "test/repo",
                    "branch": "main",
                },
                # No firmwares section
            }

            config_file = keyboards_dir / "test_no_firmware.yaml"
            with config_file.open("w") as f:
                yaml.dump(config_data, f)

            original_path = os.environ.get("GLOVEBOX_KEYBOARD_PATH", "")
            os.environ["GLOVEBOX_KEYBOARD_PATH"] = str(keyboards_dir)

            try:
                # Requesting specific firmware should fail
                with pytest.raises(ConfigError) as exc_info:
                    create_keyboard_profile("test_no_firmware", "nonexistent_firmware")

                assert "Firmware 'nonexistent_firmware' not found" in str(
                    exc_info.value
                )

                # But keyboard-only should work
                profile = create_keyboard_profile("test_no_firmware", None)
                assert profile.keyboard_name == "test_no_firmware"
                assert profile.firmware_version is None

            finally:
                if original_path:
                    os.environ["GLOVEBOX_KEYBOARD_PATH"] = original_path
                else:
                    os.environ.pop("GLOVEBOX_KEYBOARD_PATH", None)


class TestKeyboardOnlyProfileIntegration:
    """Integration tests for keyboard-only profiles."""

    def test_end_to_end_keyboard_only_workflow(self):
        """Test complete workflow with keyboard-only profile."""
        # Create a realistic keyboard config
        with tempfile.TemporaryDirectory() as temp_dir:
            keyboards_dir = Path(temp_dir) / "keyboards"
            keyboards_dir.mkdir()

            config_data = {
                "keyboard": "integration_test",
                "description": "Integration test keyboard",
                "vendor": "Test Vendor",
                "key_count": 80,
                "compile_methods": [
                    {
                        "method_type": "docker",
                        "image": "zmkfirmware/zmk-build-arm:stable",
                        "repository": "zmkfirmware/zmk",
                        "branch": "main",
                        "fallback_methods": ["local"],
                    }
                ],
                "flash_methods": [
                    {
                        "method_type": "usb",
                        "device_query": "vendor=Test and removable=true",
                        "mount_timeout": 30,
                        "copy_timeout": 60,
                        "sync_after_copy": True,
                        "fallback_methods": ["dfu"],
                    },
                    {
                        "method_type": "dfu",
                        "vid": "0x1234",
                        "pid": "0x5678",
                        "interface": 0,
                        "alt_setting": 0,
                        "timeout": 30,
                        "fallback_methods": [],
                    },
                ],
            }

            config_file = keyboards_dir / "integration_test.yaml"
            with config_file.open("w") as f:
                yaml.dump(config_data, f)

            original_path = os.environ.get("GLOVEBOX_KEYBOARD_PATH", "")
            os.environ["GLOVEBOX_KEYBOARD_PATH"] = str(keyboards_dir)

            try:
                # 1. Test user config with keyboard-only profile
                user_config = UserConfigData(profile="integration_test")
                assert user_config.profile == "integration_test"

                # 2. Test profile creation
                profile = create_keyboard_profile("integration_test")
                assert profile.keyboard_name == "integration_test"
                assert profile.firmware_version is None

                # 3. Test profile helper
                helper_profile = create_profile_from_option("integration_test")
                assert helper_profile.keyboard_name == "integration_test"
                assert helper_profile.firmware_version is None

                # 4. Test accessing properties safely
                assert helper_profile.system_behaviors == []
                assert helper_profile.kconfig_options == {}

            finally:
                if original_path:
                    os.environ["GLOVEBOX_KEYBOARD_PATH"] = original_path
                else:
                    os.environ.pop("GLOVEBOX_KEYBOARD_PATH", None)

    def test_filename_priority_with_keyboard_only_profile(self):
        """Test that filename takes priority over internal keyboard field."""
        with tempfile.TemporaryDirectory() as temp_dir:
            keyboards_dir = Path(temp_dir) / "keyboards"
            keyboards_dir.mkdir()

            # Config with different filename vs internal keyboard field
            config_data = {
                "keyboard": "internal_name",  # Different from filename
                "description": "Test filename priority",
                "vendor": "Test Vendor",
                "key_count": 10,
                "flash": {
                    "method": "usb_mount",
                    "query": "test_query",
                    "usb_vid": "1234",
                    "usb_pid": "5678",
                },
                "build": {
                    "method": "docker",
                    "docker_image": "test_image",
                    "repository": "test/repo",
                    "branch": "main",
                },
            }

            # Save with filename different from keyboard field
            config_file = keyboards_dir / "filename_priority.yaml"
            with config_file.open("w") as f:
                yaml.dump(config_data, f)

            original_path = os.environ.get("GLOVEBOX_KEYBOARD_PATH", "")
            os.environ["GLOVEBOX_KEYBOARD_PATH"] = str(keyboards_dir)

            try:
                # Load by filename (not by internal keyboard field)
                profile = create_keyboard_profile("filename_priority")

                # Filename should win
                assert profile.keyboard_name == "filename_priority"
                assert profile.keyboard_config.keyboard == "filename_priority"

                # Test with user config keyboard-only profile
                user_config = UserConfigData(profile="filename_priority")
                helper_profile = create_profile_from_option(user_config.profile)
                assert helper_profile.keyboard_name == "filename_priority"

            finally:
                if original_path:
                    os.environ["GLOVEBOX_KEYBOARD_PATH"] = original_path
                else:
                    os.environ.pop("GLOVEBOX_KEYBOARD_PATH", None)
