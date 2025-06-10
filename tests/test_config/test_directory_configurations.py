"""Tests for directory-based configuration loading."""

import tempfile
from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest
import yaml

from glovebox.config.include_loader import IncludeConfigLoader, create_include_loader
from glovebox.config.keyboard_profile import (
    create_keyboard_profile_with_includes,
    load_keyboard_config_with_includes,
)
from glovebox.config.user_config import create_user_config
from glovebox.core.errors import ConfigError


class TestDirectoryBasedConfigurations:
    """Tests for directory-based keyboard configurations."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.loader = IncludeConfigLoader([self.temp_dir])

    def teardown_method(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def _create_config_file(self, filename: str, content: str) -> Path:
        """Create a configuration file from string content."""
        file_path = self.temp_dir / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("w") as f:
            f.write(content)
        return file_path

    def _create_config_dict(self, filename: str, content: dict[str, Any]) -> Path:
        """Create a configuration file from dictionary content."""
        file_path = self.temp_dir / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("w") as f:
            yaml.dump(content, f)
        return file_path

    def test_load_from_directory_with_keyboard_yaml(self):
        """Test loading configuration from directory with keyboard.yaml."""
        config_yaml = dedent("""
            keyboard: "dir_test"
            description: "Directory-based test keyboard"
            vendor: "Directory Vendor"
            key_count: 60

            behavior:
              behavior_mappings:
                - behavior_name: "&kp"
                  behavior_class: "KPBehavior"
              magic_layer_command: "&magic LAYER_Directory 0"

            display:
              formatting:
                header_width: 100
                none_display: "EMPTY"
        """)

        # Create directory structure
        self._create_config_file("dir_test/keyboard.yaml", config_yaml)

        result = self.loader.load_keyboard_config("dir_test")

        assert result.keyboard == "dir_test"
        assert result.description == "Directory-based test keyboard"
        assert result.vendor == "Directory Vendor"
        assert result.key_count == 60
        assert len(result.behavior.behavior_mappings) == 1
        assert result.behavior.behavior_mappings[0].behavior_name == "&kp"
        assert result.display.formatting.header_width == 100

    def test_load_from_directory_with_named_yaml(self):
        """Test loading configuration from directory with {keyboard_name}.yaml."""
        config_yaml = dedent("""
            keyboard: "named_test"
            description: "Named file in directory"
            vendor: "Named Vendor"
            key_count: 70

            zmk:
              patterns:
                layer_define: "NAMED_{}"
              validation_limits:
                max_layers: 12
        """)

        # Create directory structure with named file
        self._create_config_file("named_test/named_test.yaml", config_yaml)

        result = self.loader.load_keyboard_config("named_test")

        assert result.keyboard == "named_test"
        assert result.description == "Named file in directory"
        assert result.vendor == "Named Vendor"
        assert result.key_count == 70
        assert result.zmk.patterns.layer_define == "NAMED_{}"
        assert result.zmk.validation_limits.max_layers == 12

    def test_load_from_directory_with_includes(self):
        """Test loading directory-based configuration with includes."""
        # Create shared configuration in directory
        shared_yaml = dedent("""
            behavior:
              behavior_mappings:
                - behavior_name: "&shared"
                  behavior_class: "SharedBehavior"
              modifier_mappings:
                - long_form: "LSHIFT"
                  short_form: "LS"
        """)

        # Create main configuration that includes shared
        main_yaml = dedent("""
            include:
              - "shared.yaml"

            keyboard: "include_dir_test"
            description: "Directory with includes"
            vendor: "Include Directory Vendor"
            key_count: 80

            display:
              formatting:
                header_width: 120
                trans_display: "TRANS"
        """)

        # Create directory structure
        self._create_config_file("include_dir_test/shared.yaml", shared_yaml)
        self._create_config_file("include_dir_test/keyboard.yaml", main_yaml)

        result = self.loader.load_keyboard_config("include_dir_test")

        # Main configuration
        assert result.keyboard == "include_dir_test"
        assert result.description == "Directory with includes"
        assert result.vendor == "Include Directory Vendor"
        assert result.key_count == 80

        # From shared include
        assert len(result.behavior.behavior_mappings) == 1
        assert result.behavior.behavior_mappings[0].behavior_name == "&shared"
        assert len(result.behavior.modifier_mappings) == 1
        assert result.behavior.modifier_mappings[0].long_form == "LSHIFT"

        # From main configuration
        assert result.display.formatting.header_width == 120
        assert result.display.formatting.trans_display == "TRANS"

    def test_load_from_directory_with_subdirectory_includes(self):
        """Test loading directory-based configuration with subdirectory includes."""
        # Create shared configuration in subdirectory
        base_yaml = dedent("""
            vendor: "Base Vendor"
            key_count: 50

            zmk:
              compatible_strings:
                macro: "base,macro"
                hold_tap: "base,hold-tap"
        """)

        behavior_yaml = dedent("""
            behavior:
              behavior_mappings:
                - behavior_name: "&kp"
                  behavior_class: "KPBehavior"
                - behavior_name: "&mt"
                  behavior_class: "ModTapBehavior"
        """)

        # Create main configuration
        main_yaml = dedent("""
            include:
              - "shared/base.yaml"
              - "shared/behavior.yaml"

            keyboard: "subdir_test"
            description: "Test with subdirectory includes"

            display:
              formatting:
                header_width: 110
        """)

        # Create directory structure
        self._create_config_file("subdir_test/shared/base.yaml", base_yaml)
        self._create_config_file("subdir_test/shared/behavior.yaml", behavior_yaml)
        self._create_config_file("subdir_test/keyboard.yaml", main_yaml)

        result = self.loader.load_keyboard_config("subdir_test")

        # Main configuration
        assert result.keyboard == "subdir_test"
        assert result.description == "Test with subdirectory includes"

        # From base include
        assert result.vendor == "Base Vendor"
        assert result.key_count == 50
        assert result.zmk.compatible_strings.macro == "base,macro"

        # From behavior include
        assert len(result.behavior.behavior_mappings) == 2
        behavior_names = {m.behavior_name for m in result.behavior.behavior_mappings}
        assert "&kp" in behavior_names
        assert "&mt" in behavior_names

        # From main configuration
        assert result.display.formatting.header_width == 110

    def test_precedence_single_file_over_directory(self):
        """Test that single-file configurations take precedence over directories."""
        # Create single file configuration
        single_file_content = {
            "keyboard": "precedence_test",
            "description": "Single file configuration",
            "vendor": "Single File Vendor",
            "key_count": 42,
        }

        # Create directory configuration
        dir_config_yaml = dedent("""
            keyboard: "precedence_test"
            description: "Directory configuration"
            vendor: "Directory Vendor"
            key_count: 84
        """)

        # Create both configurations
        self._create_config_dict("precedence_test.yaml", single_file_content)
        self._create_config_file("precedence_test/keyboard.yaml", dir_config_yaml)

        result = self.loader.load_keyboard_config("precedence_test")

        # Should load from single file (higher precedence)
        assert result.keyboard == "precedence_test"
        assert result.description == "Single file configuration"
        assert result.vendor == "Single File Vendor"
        assert result.key_count == 42

    def test_directory_with_yml_extension(self):
        """Test loading from directory with .yml extension."""
        config_yml = dedent("""
            keyboard: "yml_test"
            description: "YML extension test"
            vendor: "YML Vendor"
            key_count: 55
        """)

        # Create directory with .yml file
        self._create_config_file("yml_test/keyboard.yml", config_yml)

        result = self.loader.load_keyboard_config("yml_test")

        assert result.keyboard == "yml_test"
        assert result.description == "YML extension test"
        assert result.vendor == "YML Vendor"
        assert result.key_count == 55

    def test_directory_precedence_keyboard_over_named(self):
        """Test that keyboard.yaml takes precedence over {name}.yaml in directory."""
        # Create keyboard.yaml
        keyboard_yaml = dedent("""
            keyboard: "precedence_dir_test"
            description: "From keyboard.yaml"
            vendor: "Keyboard YAML Vendor"
            key_count: 33
        """)

        # Create {name}.yaml
        named_yaml = dedent("""
            keyboard: "precedence_dir_test"
            description: "From named.yaml"
            vendor: "Named YAML Vendor"
            key_count: 66
        """)

        # Create both files in directory
        self._create_config_file("precedence_dir_test/keyboard.yaml", keyboard_yaml)
        self._create_config_file(
            "precedence_dir_test/precedence_dir_test.yaml", named_yaml
        )

        result = self.loader.load_keyboard_config("precedence_dir_test")

        # Should load from keyboard.yaml (higher precedence)
        assert result.keyboard == "precedence_dir_test"
        assert result.description == "From keyboard.yaml"
        assert result.vendor == "Keyboard YAML Vendor"
        assert result.key_count == 33

    def test_error_empty_directory(self):
        """Test error handling for empty directory."""
        # Create empty directory
        empty_dir = self.temp_dir / "empty_test"
        empty_dir.mkdir()

        with pytest.raises(ConfigError, match="Keyboard configuration not found"):
            self.loader.load_keyboard_config("empty_test")

    def test_nested_includes_in_directory(self):
        """Test nested includes within a directory structure."""
        # Create base configuration
        base_yaml = dedent("""
            vendor: "Nested Base Vendor"
            key_count: 75
        """)

        # Create intermediate configuration that includes base
        intermediate_yaml = dedent("""
            include:
              - "base.yaml"

            behavior:
              behavior_mappings:
                - behavior_name: "&intermediate"
                  behavior_class: "IntermediateBehavior"
        """)

        # Create main configuration that includes intermediate
        main_yaml = dedent("""
            include:
              - "intermediate.yaml"

            keyboard: "nested_dir_test"
            description: "Nested includes in directory"

            display:
              formatting:
                header_width: 130
        """)

        # Create directory structure
        self._create_config_file("nested_dir_test/base.yaml", base_yaml)
        self._create_config_file("nested_dir_test/intermediate.yaml", intermediate_yaml)
        self._create_config_file("nested_dir_test/keyboard.yaml", main_yaml)

        result = self.loader.load_keyboard_config("nested_dir_test")

        # Main configuration
        assert result.keyboard == "nested_dir_test"
        assert result.description == "Nested includes in directory"

        # From base (through intermediate)
        assert result.vendor == "Nested Base Vendor"
        assert result.key_count == 75

        # From intermediate
        assert len(result.behavior.behavior_mappings) == 1
        assert result.behavior.behavior_mappings[0].behavior_name == "&intermediate"

        # From main
        assert result.display.formatting.header_width == 130


class TestDirectoryConfigurationIntegration:
    """Integration tests for directory-based configurations with profile system."""

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
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("w") as f:
            f.write(content)
        return file_path

    def test_keyboard_profile_with_directory_config(self):
        """Test creating keyboard profile from directory-based configuration."""
        # Create firmware configuration
        firmware_yaml = dedent("""
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

        # Create main configuration with includes
        main_yaml = dedent("""
            include:
              - "firmware.yaml"

            keyboard: "profile_dir_test"
            description: "Profile with directory config"
            vendor: "Profile Directory Vendor"
            key_count: 88

            behavior:
              behavior_mappings:
                - behavior_name: "&profile"
                  behavior_class: "ProfileBehavior"
        """)

        # Create directory structure
        self._create_config_file("profile_dir_test/firmware.yaml", firmware_yaml)
        self._create_config_file("profile_dir_test/keyboard.yaml", main_yaml)

        # Create user config with temp directory
        user_config = create_user_config()
        user_config.add_keyboard_path(self.temp_dir)

        # Create keyboard profile
        profile = create_keyboard_profile_with_includes(
            "profile_dir_test", "v1.0", user_config
        )

        # Verify profile
        assert profile.keyboard_name == "profile_dir_test"
        assert profile.firmware_version == "v1.0"

        # Verify keyboard configuration
        assert profile.keyboard_config.keyboard == "profile_dir_test"
        assert profile.keyboard_config.description == "Profile with directory config"
        assert profile.keyboard_config.vendor == "Profile Directory Vendor"
        assert profile.keyboard_config.key_count == 88

        # From firmware include
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

    def test_load_config_function_with_directory(self):
        """Test load_keyboard_config_with_includes function with directory config."""
        config_yaml = dedent("""
            keyboard: "function_dir_test"
            description: "Function test with directory"
            vendor: "Function Directory Vendor"
            key_count: 99

            zmk:
              patterns:
                layer_define: "FUNCTION_{}"
              validation_limits:
                max_layers: 20
        """)

        # Create directory structure
        self._create_config_file("function_dir_test/keyboard.yaml", config_yaml)

        # Create user config with temp directory
        user_config = create_user_config()
        user_config.add_keyboard_path(self.temp_dir)

        # Load configuration
        result = load_keyboard_config_with_includes("function_dir_test", user_config)

        assert result.keyboard == "function_dir_test"
        assert result.description == "Function test with directory"
        assert result.vendor == "Function Directory Vendor"
        assert result.key_count == 99
        assert result.zmk.patterns.layer_define == "FUNCTION_{}"
        assert result.zmk.validation_limits.max_layers == 20

    def test_keyboard_only_profile_with_directory(self):
        """Test keyboard-only profile with directory-based configuration."""
        config_yaml = dedent("""
            keyboard: "keyboard_only_dir_test"
            description: "Keyboard-only directory test"
            vendor: "Keyboard Only Directory Vendor"
            key_count: 44

            display:
              formatting:
                header_width: 90
                none_display: "VOID"
        """)

        # Create directory structure (no firmwares section)
        self._create_config_file("keyboard_only_dir_test/keyboard.yaml", config_yaml)

        # Create user config with temp directory
        user_config = create_user_config()
        user_config.add_keyboard_path(self.temp_dir)

        # Create keyboard-only profile
        profile = create_keyboard_profile_with_includes(
            "keyboard_only_dir_test", None, user_config
        )

        # Verify profile
        assert profile.keyboard_name == "keyboard_only_dir_test"
        assert profile.firmware_version is None
        assert profile.firmware_config is None

        # Verify keyboard configuration
        assert profile.keyboard_config.keyboard == "keyboard_only_dir_test"
        assert profile.keyboard_config.description == "Keyboard-only directory test"
        assert profile.keyboard_config.vendor == "Keyboard Only Directory Vendor"
        assert profile.keyboard_config.key_count == 44
        assert profile.keyboard_config.display.formatting.header_width == 90

        # Verify safe access for keyboard-only profile
        assert profile.system_behaviors == []
        assert profile.kconfig_options == {}
