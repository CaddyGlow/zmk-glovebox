"""Tests for include directive configuration loading."""

import tempfile
from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest
import yaml

from glovebox.config.include_loader import IncludeConfigLoader, create_include_loader
from glovebox.core.errors import ConfigError


class TestIncludeConfigLoader:
    """Tests for the IncludeConfigLoader class."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.loader = IncludeConfigLoader([self.temp_dir])

    def teardown_method(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def _create_config_file(self, filename: str, content: dict[str, Any]) -> Path:
        """Create a configuration file for testing."""
        file_path = self.temp_dir / filename
        with file_path.open("w") as f:
            yaml.dump(content, f)
        return file_path

    def test_load_simple_config_without_includes(self):
        """Test loading a simple configuration without includes."""
        config_content = {
            "keyboard": "test_keyboard",
            "description": "Test keyboard",
            "vendor": "Test Vendor",
            "key_count": 42,
        }

        self._create_config_file("test_keyboard.yaml", config_content)

        result = self.loader.load_keyboard_config("test_keyboard")

        assert result.keyboard == "test_keyboard"
        assert result.description == "Test keyboard"
        assert result.vendor == "Test Vendor"
        assert result.key_count == 42

    def test_load_config_with_simple_include(self):
        """Test loading configuration with a simple include."""
        # Create base configuration
        base_config = {
            "keyboard": "base_keyboard",
            "description": "Base keyboard description",
            "vendor": "Base Vendor",
            "key_count": 50,
            "behavior": {
                "behavior_mappings": [
                    {"behavior_name": "&kp", "behavior_class": "KPBehavior"}
                ]
            },
        }

        # Create main configuration with include
        main_config = {
            "include": ["base_keyboard.yaml"],
            "keyboard": "main_keyboard",
            "description": "Main keyboard with includes",
            "display": {"formatting": {"header_width": 100, "none_display": "NONE"}},
        }

        self._create_config_file("base_keyboard.yaml", base_config)
        self._create_config_file("main_keyboard.yaml", main_config)

        result = self.loader.load_keyboard_config("main_keyboard")

        # Main config should override base config
        assert result.keyboard == "main_keyboard"
        assert result.description == "Main keyboard with includes"
        assert result.vendor == "Base Vendor"  # From base
        assert result.key_count == 50  # From base

        # Behavior from base should be preserved
        assert len(result.behavior.behavior_mappings) == 1
        assert result.behavior.behavior_mappings[0].behavior_name == "&kp"

        # Display from main should be present
        assert result.display.formatting.header_width == 100
        assert result.display.formatting.none_display == "NONE"

    def test_load_config_with_multiple_includes(self):
        """Test loading configuration with multiple includes."""
        # Create behavior configuration
        behavior_config = {
            "behavior": {
                "behavior_mappings": [
                    {"behavior_name": "&kp", "behavior_class": "KPBehavior"},
                    {"behavior_name": "&mt", "behavior_class": "ModTapBehavior"},
                ],
                "magic_layer_command": "&magic LAYER_Test 0",
            }
        }

        # Create display configuration
        display_config = {
            "display": {
                "layout_structure": {
                    "rows": {
                        "row0": [[0, 1, 2], [3, 4, 5]],
                        "row1": [[6, 7, 8], [9, 10, 11]],
                    }
                },
                "formatting": {"header_width": 120, "key_width": 10},
            }
        }

        # Create ZMK configuration
        zmk_config = {
            "zmk": {
                "patterns": {"layer_define": "CUSTOM_LAYER_{}"},
                "validation_limits": {"max_layers": 15, "max_macro_params": 5},
            }
        }

        # Create main configuration
        main_config = {
            "include": ["behavior.yaml", "display.yaml", "zmk.yaml"],
            "keyboard": "composite_keyboard",
            "description": "Keyboard assembled from multiple includes",
            "vendor": "Composite Vendor",
            "key_count": 80,
        }

        self._create_config_file("behavior.yaml", behavior_config)
        self._create_config_file("display.yaml", display_config)
        self._create_config_file("zmk.yaml", zmk_config)
        self._create_config_file("composite_keyboard.yaml", main_config)

        result = self.loader.load_keyboard_config("composite_keyboard")

        # Main configuration
        assert result.keyboard == "composite_keyboard"
        assert result.description == "Keyboard assembled from multiple includes"
        assert result.vendor == "Composite Vendor"
        assert result.key_count == 80

        # Behavior configuration
        assert len(result.behavior.behavior_mappings) == 2
        assert result.behavior.magic_layer_command == "&magic LAYER_Test 0"

        # Display configuration
        assert result.display.layout_structure is not None
        assert len(result.display.layout_structure.rows) == 2
        assert result.display.formatting.header_width == 120

        # ZMK configuration
        assert result.zmk.patterns.layer_define == "CUSTOM_LAYER_{}"
        assert result.zmk.validation_limits.max_layers == 15

    def test_nested_includes(self):
        """Test loading configuration with nested includes."""
        # Create base configuration
        base_config = {
            "keyboard": "base",
            "description": "Base configuration",
            "vendor": "Base Vendor",
            "key_count": 60,
        }

        # Create intermediate configuration that includes base
        intermediate_config = {
            "include": ["base.yaml"],
            "behavior": {
                "behavior_mappings": [
                    {"behavior_name": "&none", "behavior_class": "SimpleBehavior"}
                ]
            },
        }

        # Create final configuration that includes intermediate
        final_config = {
            "include": ["intermediate.yaml"],
            "keyboard": "final_keyboard",
            "description": "Final keyboard configuration",
            "display": {"formatting": {"header_width": 90}},
        }

        self._create_config_file("base.yaml", base_config)
        self._create_config_file("intermediate.yaml", intermediate_config)
        self._create_config_file("final_keyboard.yaml", final_config)

        result = self.loader.load_keyboard_config("final_keyboard")

        # Should have values from all levels
        assert result.keyboard == "final_keyboard"  # Final override
        assert result.description == "Final keyboard configuration"  # Final override
        assert result.vendor == "Base Vendor"  # From base
        assert result.key_count == 60  # From base
        assert len(result.behavior.behavior_mappings) == 1  # From intermediate
        assert result.display.formatting.header_width == 90  # From final

    def test_include_with_relative_paths(self):
        """Test include resolution with relative paths."""
        # Create subdirectory
        subdir = self.temp_dir / "shared"
        subdir.mkdir()

        # Create shared configuration in subdirectory
        shared_config = {
            "vendor": "Shared Vendor",
            "behavior": {
                "behavior_mappings": [
                    {"behavior_name": "&shared", "behavior_class": "SharedBehavior"}
                ]
            },
        }

        shared_file = subdir / "shared.yaml"
        with shared_file.open("w") as f:
            yaml.dump(shared_config, f)

        # Create main configuration that includes relative path
        main_config = {
            "include": ["shared/shared.yaml"],
            "keyboard": "relative_test",
            "description": "Test relative includes",
            "key_count": 55,
        }

        self._create_config_file("relative_test.yaml", main_config)

        result = self.loader.load_keyboard_config("relative_test")

        assert result.keyboard == "relative_test"
        assert result.vendor == "Shared Vendor"  # From shared
        assert result.key_count == 55
        assert len(result.behavior.behavior_mappings) == 1

    def test_include_without_extension(self):
        """Test include resolution without file extension."""
        # Create included file
        included_config = {
            "vendor": "Extension Test Vendor",
            "key_count": 33,
        }

        self._create_config_file("no_extension.yaml", included_config)

        # Create main configuration that includes without extension
        main_config = {
            "include": ["no_extension"],  # No .yaml extension
            "keyboard": "extension_test",
            "description": "Test extension resolution",
        }

        self._create_config_file("extension_test.yaml", main_config)

        result = self.loader.load_keyboard_config("extension_test")

        assert result.keyboard == "extension_test"
        assert result.vendor == "Extension Test Vendor"
        assert result.key_count == 33

    def test_circular_include_detection(self):
        """Test detection of circular includes."""
        # Create config A that includes B
        config_a = {
            "include": ["config_b.yaml"],
            "keyboard": "config_a",
            "description": "Config A",
        }

        # Create config B that includes A (circular)
        config_b = {
            "include": ["config_a.yaml"],
            "vendor": "Config B Vendor",
        }

        self._create_config_file("config_a.yaml", config_a)
        self._create_config_file("config_b.yaml", config_b)

        with pytest.raises(ConfigError, match="Circular include detected"):
            self.loader.load_keyboard_config("config_a")

    def test_missing_include_file(self):
        """Test error handling for missing include files."""
        main_config = {
            "include": ["missing_file.yaml"],
            "keyboard": "missing_test",
            "description": "Test missing include",
        }

        self._create_config_file("missing_test.yaml", main_config)

        with pytest.raises(ConfigError, match="Include file not found"):
            self.loader.load_keyboard_config("missing_test")

    def test_configuration_caching(self):
        """Test that configurations are properly cached."""
        config_content = {
            "keyboard": "cache_test",
            "description": "Test caching",
            "vendor": "Cache Vendor",
            "key_count": 77,
        }

        self._create_config_file("cache_test.yaml", config_content)

        # Load twice
        result1 = self.loader.load_keyboard_config("cache_test")
        result2 = self.loader.load_keyboard_config("cache_test")

        # Should be the same content
        assert result1.keyboard == result2.keyboard
        assert result1.description == result2.description

        # Verify caching worked by checking internal state
        assert len(self.loader._loaded_files) > 0

    def test_cache_clearing(self):
        """Test cache clearing functionality."""
        config_content = {
            "keyboard": "clear_test",
            "description": "Test cache clearing",
            "vendor": "Clear Vendor",
            "key_count": 88,
        }

        self._create_config_file("clear_test.yaml", config_content)

        # Load configuration
        self.loader.load_keyboard_config("clear_test")

        # Verify cache has content
        assert len(self.loader._loaded_files) > 0

        # Clear cache
        self.loader.clear_cache()

        # Verify cache is empty
        assert len(self.loader._loaded_files) == 0

    def test_list_merging(self):
        """Test that lists are properly merged during include processing."""
        # Create base configuration with a list
        base_config = {
            "compile_methods": [
                {
                    "method_type": "moergo",
                    "image": "base_image",
                    "repository": "test/repo",
                    "branch": "main",
                },
            ]
        }

        # Create main configuration with additional list items
        main_config = {
            "include": ["base.yaml"],
            "keyboard": "list_merge_test",
            "description": "Test list merging",
            "vendor": "Test Vendor",
            "key_count": 42,
            "compile_methods": [
                {
                    "method_type": "zmk",
                    "image": "local_image",
                    "repository": "test/local",
                    "branch": "main",
                },
            ],
        }

        self._create_config_file("base.yaml", base_config)
        self._create_config_file("list_merge_test.yaml", main_config)

        result = self.loader.load_keyboard_config("list_merge_test")

        # Lists should be merged (base + main)
        assert len(result.compile_methods) == 2
        methods = [method.method_type for method in result.compile_methods]
        assert "moergo" in methods
        assert "zmk" in methods

    def test_dictionary_merging(self):
        """Test that dictionaries are properly merged during include processing."""
        # Create base configuration with nested dictionary
        base_config = {
            "zmk": {
                "compatible_strings": {
                    "macro": "base,macro",
                    "hold_tap": "base,hold-tap",
                },
                "patterns": {"layer_define": "BASE_{}"},
            }
        }

        # Create main configuration with additional dictionary keys
        main_config = {
            "include": ["base.yaml"],
            "keyboard": "dict_merge_test",
            "description": "Test dictionary merging",
            "vendor": "Test Vendor",
            "key_count": 42,
            "zmk": {
                "compatible_strings": {"combos": "main,combos"},  # Add new key
                "validation_limits": {"max_layers": 20},  # Add new section
            },
        }

        self._create_config_file("base.yaml", base_config)
        self._create_config_file("dict_merge_test.yaml", main_config)

        result = self.loader.load_keyboard_config("dict_merge_test")

        # Dictionaries should be merged
        assert result.zmk.compatible_strings.macro == "base,macro"  # From base
        assert result.zmk.compatible_strings.hold_tap == "base,hold-tap"  # From base
        assert result.zmk.compatible_strings.combos == "main,combos"  # From main
        assert result.zmk.patterns.layer_define == "BASE_{}"  # From base
        assert result.zmk.validation_limits.max_layers == 20  # From main

    def test_include_with_string_instead_of_list(self):
        """Test include with single string instead of list."""
        # Create base configuration
        base_config = {
            "vendor": "String Include Vendor",
            "key_count": 99,
        }

        # Create main configuration with string include
        main_config = {
            "include": "base.yaml",  # String instead of list
            "keyboard": "string_include_test",
            "description": "Test string include",
        }

        self._create_config_file("base.yaml", base_config)
        self._create_config_file("string_include_test.yaml", main_config)

        result = self.loader.load_keyboard_config("string_include_test")

        assert result.keyboard == "string_include_test"
        assert result.vendor == "String Include Vendor"
        assert result.key_count == 99


class TestIncludeLoaderFactory:
    """Tests for the include loader factory function."""

    def test_create_include_loader(self):
        """Test creating an include loader with factory function."""
        search_paths = [Path("/test/path1"), Path("/test/path2")]
        loader = create_include_loader(search_paths)

        assert isinstance(loader, IncludeConfigLoader)
        assert loader.search_paths == search_paths


class TestIncludeLoaderIntegration:
    """Integration tests for include loader with real configurations."""

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
        with file_path.open("w") as f:
            f.write(content)
        return file_path

    def test_realistic_keyboard_with_includes(self):
        """Test a realistic keyboard configuration using includes."""
        # Create shared behavior configuration
        behavior_yaml = dedent("""
            behavior:
              behavior_mappings:
                - behavior_name: "&none"
                  behavior_class: "SimpleBehavior"
                - behavior_name: "&trans"
                  behavior_class: "SimpleBehavior"
                - behavior_name: "&kp"
                  behavior_class: "KPBehavior"
                - behavior_name: "&lt"
                  behavior_class: "LayerTapBehavior"
                - behavior_name: "&mt"
                  behavior_class: "ModTapBehavior"
              modifier_mappings:
                - long_form: "LSHIFT"
                  short_form: "LS"
                - long_form: "LCTL"
                  short_form: "LC"
                - long_form: "LALT"
                  short_form: "LA"
                - long_form: "LGUI"
                  short_form: "LG"
              magic_layer_command: "&magic LAYER_Magic 0"
              reset_behavior_alias: "&sys_reset"
        """)

        # Create shared ZMK configuration
        zmk_yaml = dedent("""
            zmk:
              compatible_strings:
                macro: "zmk,behavior-macro"
                hold_tap: "zmk,behavior-hold-tap"
                combos: "zmk,combos"
              hold_tap_flavors:
                - "tap-preferred"
                - "hold-preferred"
                - "balanced"
                - "tap-unless-interrupted"
              patterns:
                layer_define: "LAYER_{}"
                node_name_sanitize: "[^A-Z0-9_]"
              validation_limits:
                max_layers: 10
                max_macro_params: 2
        """)

        # Create main keyboard configuration
        keyboard_yaml = dedent("""
            include:
              - "shared/behavior.yaml"
              - "shared/zmk.yaml"

            keyboard: "ergodox_ez"
            description: "ErgoDox EZ ergonomic keyboard"
            vendor: "ZSA Technology Labs"
            key_count: 76

            display:
              layout_structure:
                rows:
                  left_hand:
                    - [0, 1, 2, 3, 4, 5, 6]
                    - [14, 15, 16, 17, 18, 19]
                  right_hand:
                    - [7, 8, 9, 10, 11, 12, 13]
                    - [20, 21, 22, 23, 24, 25, 26, 27]
                  thumbs:
                    - [52, 53, 54, 55, 56, 57]
                    - [58, 59, 60, 61, 62, 63]
              formatting:
                header_width: 120
                none_display: "___"
                trans_display: "▽▽▽"
                key_width: 6
                center_small_rows: true
                horizontal_spacer: " │ "

            compile_methods:
              - strategy: "zmk"
                image: "zmkfirmware/zmk-build-arm:stable"
                repository: "zmkfirmware/zmk"
                branch: "main"

            flash_methods:
              - device_query: "vendor=ZSA and removable=true"
                mount_timeout: 30
                copy_timeout: 60
                sync_after_copy: true
        """)

        # Create subdirectory for shared files
        shared_dir = self.temp_dir / "shared"
        shared_dir.mkdir()

        # Create configuration files
        self._create_config_file("shared/behavior.yaml", behavior_yaml)
        self._create_config_file("shared/zmk.yaml", zmk_yaml)
        self._create_config_file("ergodox_ez.yaml", keyboard_yaml)

        # Load the configuration
        result = self.loader.load_keyboard_config("ergodox_ez")

        # Verify main configuration
        assert result.keyboard == "ergodox_ez"
        assert result.description == "ErgoDox EZ ergonomic keyboard"
        assert result.vendor == "ZSA Technology Labs"
        assert result.key_count == 76

        # Verify behavior configuration from include
        assert len(result.behavior.behavior_mappings) == 5
        behavior_names = {
            mapping.behavior_name for mapping in result.behavior.behavior_mappings
        }
        assert "&kp" in behavior_names
        assert "&mt" in behavior_names
        assert len(result.behavior.modifier_mappings) == 4

        # Verify ZMK configuration from include
        assert result.zmk.compatible_strings.macro == "zmk,behavior-macro"
        assert len(result.zmk.hold_tap_flavors) == 4
        assert result.zmk.patterns.layer_define == "LAYER_{}"

        # Verify display configuration from main file
        assert result.display.layout_structure is not None
        assert len(result.display.layout_structure.rows) == 3
        assert result.display.formatting.header_width == 120

        # Verify method configurations from main file
        assert len(result.compile_methods) == 1
        assert result.compile_methods[0].method_type == "zmk"
        assert len(result.flash_methods) == 1
        assert result.flash_methods[0].device_query == "vendor=ZSA and removable=true"
