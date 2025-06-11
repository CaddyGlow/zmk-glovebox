"""Tests for include loader integration with existing configuration system."""

import tempfile
from pathlib import Path
from textwrap import dedent

import pytest

from glovebox.config import (
    create_keyboard_profile_with_includes,
    load_keyboard_config_with_includes,
)
from glovebox.config.user_config import create_user_config
from glovebox.core.errors import ConfigError


class TestIncludeConfigurationIntegration:
    """Integration tests for include loader with existing configuration system."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def _create_config_file(self, filename: str, content: str) -> Path:
        """Create a configuration file from string content."""
        file_path = self.temp_dir / filename
        with file_path.open("w") as f:
            f.write(content)
        return file_path

    def test_load_keyboard_config_with_includes_function(self):
        """Test the load_keyboard_config_with_includes function."""
        # Create shared configuration
        shared_yaml = dedent("""
            behavior:
              behavior_mappings:
                - behavior_name: "&shared"
                  behavior_class: "SharedBehavior"
              magic_layer_command: "&magic LAYER_Shared 0"

            zmk:
              patterns:
                layer_define: "SHARED_{}"
        """)

        # Create main keyboard configuration
        keyboard_yaml = dedent("""
            include:
              - "shared.yaml"

            keyboard: "include_test"
            description: "Test keyboard with includes"
            vendor: "Test Vendor"
            key_count: 50

            display:
              formatting:
                header_width: 110
                none_display: "EMPTY"
        """)

        self._create_config_file("shared.yaml", shared_yaml)
        self._create_config_file("include_test.yaml", keyboard_yaml)

        # Create user config that includes our temp directory
        user_config = create_user_config()
        user_config.add_keyboard_path(self.temp_dir)

        # Load configuration
        result = load_keyboard_config_with_includes("include_test", user_config)

        # Verify merged configuration
        assert result.keyboard == "include_test"
        assert result.description == "Test keyboard with includes"
        assert result.vendor == "Test Vendor"
        assert result.key_count == 50

        # From shared configuration
        assert len(result.behavior.behavior_mappings) == 1
        assert result.behavior.behavior_mappings[0].behavior_name == "&shared"
        assert result.behavior.magic_layer_command == "&magic LAYER_Shared 0"
        assert result.zmk.patterns.layer_define == "SHARED_{}"

        # From main configuration
        assert result.display.formatting.header_width == 110
        assert result.display.formatting.none_display == "EMPTY"

    def test_create_keyboard_profile_with_includes_function(self):
        """Test the create_keyboard_profile_with_includes function."""
        # Create base configuration with firmware
        base_yaml = dedent("""
            firmwares:
              v1.0:
                version: "v1.0"
                description: "Version 1.0"
                build_options:
                  repository: "test/repo"
                  branch: "main"
                kconfig:
                  TEST_OPTION:
                    name: "TEST_OPTION"
                    type: "bool"
                    default: true
                    description: "Test option"
        """)

        # Create main keyboard configuration
        keyboard_yaml = dedent("""
            include:
              - "base.yaml"

            keyboard: "profile_test"
            description: "Test keyboard profile with includes"
            vendor: "Profile Test Vendor"
            key_count: 60

            behavior:
              behavior_mappings:
                - behavior_name: "&profile"
                  behavior_class: "ProfileBehavior"
        """)

        self._create_config_file("base.yaml", base_yaml)
        self._create_config_file("profile_test.yaml", keyboard_yaml)

        # Create user config that includes our temp directory
        user_config = create_user_config()
        user_config.add_keyboard_path(self.temp_dir)

        # Create keyboard profile with includes
        profile = create_keyboard_profile_with_includes(
            "profile_test", "v1.0", user_config
        )

        # Verify profile
        assert profile.keyboard_name == "profile_test"
        assert profile.firmware_version == "v1.0"

        # Verify keyboard configuration
        assert profile.keyboard_config.keyboard == "profile_test"
        assert (
            profile.keyboard_config.description == "Test keyboard profile with includes"
        )
        assert profile.keyboard_config.vendor == "Profile Test Vendor"
        assert profile.keyboard_config.key_count == 60

        # From base configuration
        assert "v1.0" in profile.keyboard_config.firmwares
        firmware = profile.keyboard_config.firmwares["v1.0"]
        assert firmware.version == "v1.0"
        assert firmware.build_options.repository == "test/repo"

        # From main configuration
        assert len(profile.keyboard_config.behavior.behavior_mappings) == 1
        assert (
            profile.keyboard_config.behavior.behavior_mappings[0].behavior_name
            == "&profile"
        )

        # Verify firmware config access
        assert profile.firmware_config is not None
        assert profile.firmware_config.version == "v1.0"

        # Verify kconfig options
        kconfig_options = profile.kconfig_options
        assert "TEST_OPTION" in kconfig_options
        assert kconfig_options["TEST_OPTION"].default is True

    def test_create_keyboard_only_profile_with_includes(self):
        """Test creating a keyboard-only profile with includes."""
        # Create shared configuration
        shared_yaml = dedent("""
            zmk:
              compatible_strings:
                macro: "shared,macro"
                hold_tap: "shared,hold-tap"
              validation_limits:
                max_layers: 8
        """)

        # Create main keyboard configuration (no firmwares section)
        keyboard_yaml = dedent("""
            include:
              - "shared.yaml"

            keyboard: "keyboard_only_test"
            description: "Keyboard-only test with includes"
            vendor: "Keyboard Only Vendor"
            key_count: 40

            display:
              formatting:
                header_width: 80
                trans_display: "PASS"
        """)

        self._create_config_file("shared.yaml", shared_yaml)
        self._create_config_file("keyboard_only_test.yaml", keyboard_yaml)

        # Create user config that includes our temp directory
        user_config = create_user_config()
        user_config.add_keyboard_path(self.temp_dir)

        # Create keyboard-only profile (no firmware version)
        profile = create_keyboard_profile_with_includes(
            "keyboard_only_test", None, user_config
        )

        # Verify profile
        assert profile.keyboard_name == "keyboard_only_test"
        assert profile.firmware_version is None
        assert profile.firmware_config is None

        # Verify keyboard configuration
        assert profile.keyboard_config.keyboard == "keyboard_only_test"
        assert profile.keyboard_config.description == "Keyboard-only test with includes"
        assert profile.keyboard_config.vendor == "Keyboard Only Vendor"
        assert profile.keyboard_config.key_count == 40

        # From shared configuration
        assert profile.keyboard_config.zmk.compatible_strings.macro == "shared,macro"
        assert (
            profile.keyboard_config.zmk.compatible_strings.hold_tap == "shared,hold-tap"
        )
        assert profile.keyboard_config.zmk.validation_limits.max_layers == 8

        # From main configuration
        assert profile.keyboard_config.display.formatting.header_width == 80
        assert profile.keyboard_config.display.formatting.trans_display == "PASS"

        # Verify safe access for keyboard-only profile
        assert profile.system_behaviors == []
        assert profile.kconfig_options == {}

    def test_error_handling_with_includes(self):
        """Test error handling when includes fail."""
        # Create main configuration with missing include
        keyboard_yaml = dedent("""
            include:
              - "missing_file.yaml"

            keyboard: "error_test"
            description: "Test error handling"
            vendor: "Error Vendor"
            key_count: 30
        """)

        self._create_config_file("error_test.yaml", keyboard_yaml)

        # Create user config that includes our temp directory
        user_config = create_user_config()
        user_config.add_keyboard_path(self.temp_dir)

        # Loading should fail with ConfigError
        with pytest.raises(ConfigError, match="Include file not found"):
            load_keyboard_config_with_includes("error_test", user_config)

        # Profile creation should also fail
        with pytest.raises(ConfigError, match="Include file not found"):
            create_keyboard_profile_with_includes("error_test", None, user_config)

    def test_include_loader_with_user_search_paths(self):
        """Test include loader respects user-configured search paths."""
        # Create subdirectory for user configurations
        user_keyboards_dir = self.temp_dir / "user_keyboards"
        user_keyboards_dir.mkdir()

        # Create shared configuration in user directory
        shared_yaml = dedent("""
            behavior:
              modifier_mappings:
                - long_form: "LSHIFT"
                  short_form: "LS"
                - long_form: "LCTL"
                  short_form: "LC"
        """)

        shared_file = user_keyboards_dir / "user_shared.yaml"
        with shared_file.open("w") as f:
            f.write(shared_yaml)

        # Create main configuration that includes from user directory
        keyboard_yaml = dedent("""
            include:
              - "user_shared.yaml"

            keyboard: "user_path_test"
            description: "Test user search paths"
            vendor: "User Path Vendor"
            key_count: 70
        """)

        self._create_config_file("user_path_test.yaml", keyboard_yaml)

        # Create user config with custom search paths
        user_config = create_user_config()
        user_config.add_keyboard_path(self.temp_dir)
        user_config.add_keyboard_path(user_keyboards_dir)

        # Load configuration
        result = load_keyboard_config_with_includes("user_path_test", user_config)

        # Verify configuration loaded successfully
        assert result.keyboard == "user_path_test"
        assert result.description == "Test user search paths"
        assert result.vendor == "User Path Vendor"
        assert result.key_count == 70

        # Verify included configuration from user directory
        assert len(result.behavior.modifier_mappings) == 2
        assert result.behavior.modifier_mappings[0].long_form == "LSHIFT"
        assert result.behavior.modifier_mappings[1].long_form == "LCTL"

    def test_complex_nested_includes_with_overrides(self):
        """Test complex nested includes with configuration overrides."""
        # Create base defaults
        defaults_yaml = dedent("""
            zmk:
              compatible_strings:
                macro: "default,macro"
                hold_tap: "default,hold-tap"
                combos: "default,combos"
              validation_limits:
                max_layers: 6
                max_macro_params: 2
        """)

        # Create keyboard family configuration
        family_yaml = dedent("""
            include:
              - "defaults.yaml"

            vendor: "Family Vendor"
            behavior:
              behavior_mappings:
                - behavior_name: "&family"
                  behavior_class: "FamilyBehavior"

            zmk:
              compatible_strings:
                macro: "family,macro"  # Override default
              validation_limits:
                max_layers: 8  # Override default
        """)

        # Create specific keyboard configuration
        keyboard_yaml = dedent("""
            include:
              - "family.yaml"

            keyboard: "complex_test"
            description: "Complex nested includes test"
            key_count: 85

            behavior:
              behavior_mappings:
                - behavior_name: "&specific"
                  behavior_class: "SpecificBehavior"
              magic_layer_command: "&magic LAYER_Specific 1"

            zmk:
              validation_limits:
                max_layers: 12  # Override family
                max_macro_params: 4  # Override default
        """)

        self._create_config_file("defaults.yaml", defaults_yaml)
        self._create_config_file("family.yaml", family_yaml)
        self._create_config_file("complex_test.yaml", keyboard_yaml)

        # Create user config
        user_config = create_user_config()
        user_config.add_keyboard_path(self.temp_dir)

        # Load configuration
        result = load_keyboard_config_with_includes("complex_test", user_config)

        # Verify configuration merging and overrides
        assert result.keyboard == "complex_test"
        assert result.description == "Complex nested includes test"
        assert result.key_count == 85
        assert result.vendor == "Family Vendor"  # From family

        # Verify behavior merging (list extension)
        assert len(result.behavior.behavior_mappings) == 2
        behavior_names = {
            mapping.behavior_name for mapping in result.behavior.behavior_mappings
        }
        assert "&family" in behavior_names  # From family
        assert "&specific" in behavior_names  # From specific
        assert (
            result.behavior.magic_layer_command == "&magic LAYER_Specific 1"
        )  # From specific

        # Verify ZMK configuration merging with overrides
        # Strings: family overrides default, but default for combos
        assert result.zmk.compatible_strings.macro == "family,macro"  # Family override
        assert result.zmk.compatible_strings.hold_tap == "default,hold-tap"  # Default
        assert result.zmk.compatible_strings.combos == "default,combos"  # Default

        # Validation limits: specific overrides all
        assert result.zmk.validation_limits.max_layers == 12  # Specific override
        assert result.zmk.validation_limits.max_macro_params == 4  # Specific override
