"""Tests for KeyboardConfig integration with new configuration sections."""

import pytest
from pydantic import ValidationError

from glovebox.config.models import (
    BehaviorConfig,
    BehaviorMapping,
    DisplayConfig,
    DisplayFormatting,
    KeyboardConfig,
    ValidationLimits,
    ZmkConfig,
    ZmkPatterns,
)


class TestKeyboardConfigDefaults:
    """Tests for KeyboardConfig default behavior with new sections."""

    def test_keyboard_config_with_all_defaults(self):
        """Test KeyboardConfig creates all new sections with defaults."""
        config_data = {
            "keyboard": "test_keyboard",
            "description": "Test keyboard with defaults",
            "vendor": "Test Vendor",
            "key_count": 42,
        }

        config = KeyboardConfig.model_validate(config_data)

        # Verify basic fields
        assert config.keyboard == "test_keyboard"
        assert config.description == "Test keyboard with defaults"
        assert config.vendor == "Test Vendor"
        assert config.key_count == 42

        # Verify new sections exist with defaults
        assert config.behavior is not None
        assert config.display is not None
        assert config.zmk is not None

        # Verify behavior section defaults
        assert config.behavior.behavior_mappings == []
        assert config.behavior.modifier_mappings == []
        assert config.behavior.magic_layer_command == "&magic LAYER_Magic 0"
        assert config.behavior.reset_behavior_alias == "&sys_reset"

        # Verify display section defaults
        assert config.display.layout_structure is None
        assert config.display.formatting.header_width == 80
        assert config.display.formatting.none_display == "&none"

        # Verify zmk section defaults
        assert config.zmk.compatible_strings.macro == "zmk,behavior-macro"
        assert len(config.zmk.hold_tap_flavors) == 4
        assert config.zmk.patterns.layer_define == "LAYER_{}"
        assert config.zmk.file_extensions.keymap == ".keymap"
        assert config.zmk.validation_limits.max_layers == 10

    def test_keyboard_config_minimal_required_fields(self):
        """Test KeyboardConfig works with only required fields."""
        minimal_config = {
            "keyboard": "minimal",
            "description": "Minimal test keyboard",
            "vendor": "Test",
            "key_count": 1,
        }

        config = KeyboardConfig.model_validate(minimal_config)

        # Should still create all sections with defaults
        assert config.behavior is not None
        assert config.display is not None
        assert config.zmk is not None
        assert config.keymap is not None
        assert config.firmwares == {}


class TestKeyboardConfigCustomSections:
    """Tests for KeyboardConfig with custom configuration sections."""

    def test_keyboard_config_with_custom_behavior_section(self):
        """Test KeyboardConfig with custom behavior configuration."""
        config_data = {
            "keyboard": "custom_behavior",
            "description": "Test keyboard with custom behavior",
            "vendor": "Test Vendor",
            "key_count": 60,
            "behavior": {
                "behavior_mappings": [
                    {"behavior_name": "&kp", "behavior_class": "KPBehavior"},
                    {"behavior_name": "&mt", "behavior_class": "ModTapBehavior"},
                ],
                "modifier_mappings": [
                    {"long_form": "LALT", "short_form": "LA"},
                    {"long_form": "LCTL", "short_form": "LC"},
                ],
                "magic_layer_command": "&magic LAYER_Custom 1",
                "reset_behavior_alias": "&custom_reset",
            },
        }

        config = KeyboardConfig.model_validate(config_data)

        # Verify custom behavior configuration
        assert len(config.behavior.behavior_mappings) == 2
        assert config.behavior.behavior_mappings[0].behavior_name == "&kp"
        assert config.behavior.behavior_mappings[1].behavior_class == "ModTapBehavior"
        assert len(config.behavior.modifier_mappings) == 2
        assert config.behavior.modifier_mappings[0].long_form == "LALT"
        assert config.behavior.magic_layer_command == "&magic LAYER_Custom 1"
        assert config.behavior.reset_behavior_alias == "&custom_reset"

        # Other sections should still have defaults
        assert config.display.layout_structure is None
        assert config.zmk.compatible_strings.macro == "zmk,behavior-macro"

    def test_keyboard_config_with_custom_display_section(self):
        """Test KeyboardConfig with custom display configuration."""
        config_data = {
            "keyboard": "custom_display",
            "description": "Test keyboard with custom display",
            "vendor": "Test Vendor",
            "key_count": 80,
            "display": {
                "layout_structure": {
                    "rows": {
                        "row0": [[0, 1, 2, 3, 4], [5, 6, 7, 8, 9]],
                        "row1": [[10, 11, 12, 13, 14], [15, 16, 17, 18, 19]],
                    }
                },
                "formatting": {
                    "header_width": 100,
                    "none_display": "NONE",
                    "trans_display": "TRANS",
                    "key_width": 10,
                    "center_small_rows": False,
                    "horizontal_spacer": " ║ ",
                },
            },
        }

        config = KeyboardConfig.model_validate(config_data)

        # Verify custom display configuration
        assert config.display.layout_structure is not None
        assert len(config.display.layout_structure.rows) == 2
        assert config.display.layout_structure.rows["row0"] == [
            [0, 1, 2, 3, 4],
            [5, 6, 7, 8, 9],
        ]
        assert config.display.formatting.header_width == 100
        assert config.display.formatting.none_display == "NONE"
        assert config.display.formatting.trans_display == "TRANS"
        assert config.display.formatting.key_width == 10
        assert config.display.formatting.center_small_rows is False
        assert config.display.formatting.horizontal_spacer == " ║ "

        # Other sections should still have defaults
        assert config.behavior.magic_layer_command == "&magic LAYER_Magic 0"
        assert config.zmk.patterns.layer_define == "LAYER_{}"

    def test_keyboard_config_with_custom_zmk_section(self):
        """Test KeyboardConfig with custom ZMK configuration."""
        config_data = {
            "keyboard": "custom_zmk",
            "description": "Test keyboard with custom ZMK config",
            "vendor": "Test Vendor",
            "key_count": 72,
            "zmk": {
                "compatible_strings": {
                    "macro": "custom,behavior-macro",
                    "hold_tap": "custom,behavior-hold-tap",
                    "combos": "custom,combos",
                },
                "hold_tap_flavors": ["custom-preferred", "custom-balanced"],
                "patterns": {
                    "layer_define": "CUSTOM_LAYER_{}",
                    "node_name_sanitize": "[^A-Z0-9_-]",
                },
                "file_extensions": {
                    "keymap": ".custom_keymap",
                    "conf": ".custom_conf",
                    "dtsi": ".custom_dtsi",
                    "metadata": ".custom_json",
                },
                "validation_limits": {
                    "max_layers": 20,
                    "max_macro_params": 5,
                    "required_holdtap_bindings": 3,
                    "warn_many_layers_threshold": 15,
                },
            },
        }

        config = KeyboardConfig.model_validate(config_data)

        # Verify custom ZMK configuration
        assert config.zmk.compatible_strings.macro == "custom,behavior-macro"
        assert config.zmk.compatible_strings.hold_tap == "custom,behavior-hold-tap"
        assert config.zmk.compatible_strings.combos == "custom,combos"
        assert config.zmk.hold_tap_flavors == ["custom-preferred", "custom-balanced"]
        assert config.zmk.patterns.layer_define == "CUSTOM_LAYER_{}"
        assert config.zmk.patterns.node_name_sanitize == "[^A-Z0-9_-]"
        assert config.zmk.file_extensions.keymap == ".custom_keymap"
        assert config.zmk.file_extensions.conf == ".custom_conf"
        assert config.zmk.validation_limits.max_layers == 20
        assert config.zmk.validation_limits.max_macro_params == 5

        # Other sections should still have defaults
        assert config.behavior.magic_layer_command == "&magic LAYER_Magic 0"
        assert config.display.formatting.header_width == 80

    def test_keyboard_config_with_all_custom_sections(self):
        """Test KeyboardConfig with all sections customized."""
        config_data = {
            "keyboard": "fully_custom",
            "description": "Fully customized keyboard configuration",
            "vendor": "Custom Vendor",
            "key_count": 104,
            "behavior": {
                "behavior_mappings": [
                    {"behavior_name": "&none", "behavior_class": "SimpleBehavior"},
                    {"behavior_name": "&trans", "behavior_class": "SimpleBehavior"},
                ],
                "modifier_mappings": [
                    {"long_form": "LSHIFT", "short_form": "LS"},
                    {"long_form": "RSHIFT", "short_form": "RS"},
                ],
                "magic_layer_command": "&magic LAYER_Custom 0",
                "reset_behavior_alias": "&custom_reset",
            },
            "display": {
                "layout_structure": {
                    "rows": {
                        "main": [[0, 1, 2, 3], [4, 5, 6, 7]],
                        "thumbs": [[8, 9], [10, 11]],
                    }
                },
                "formatting": {
                    "header_width": 120,
                    "none_display": "___",
                    "trans_display": "===",
                    "key_width": 8,
                    "center_small_rows": True,
                    "horizontal_spacer": " │ ",
                },
            },
            "zmk": {
                "compatible_strings": {
                    "macro": "full-custom,macro",
                    "hold_tap": "full-custom,hold-tap",
                    "combos": "full-custom,combos",
                },
                "hold_tap_flavors": ["full-custom-preferred"],
                "patterns": {
                    "layer_define": "FULL_CUSTOM_{}",
                    "node_name_sanitize": "[^A-Z0-9_]",
                },
                "validation_limits": {
                    "max_layers": 25,
                    "max_macro_params": 10,
                    "required_holdtap_bindings": 4,
                    "warn_many_layers_threshold": 20,
                },
            },
        }

        config = KeyboardConfig.model_validate(config_data)

        # Verify all custom configurations are preserved
        assert config.keyboard == "fully_custom"
        assert config.key_count == 104

        # Behavior section
        assert len(config.behavior.behavior_mappings) == 2
        assert config.behavior.behavior_mappings[0].behavior_name == "&none"
        assert config.behavior.magic_layer_command == "&magic LAYER_Custom 0"

        # Display section
        assert config.display.layout_structure is not None
        assert len(config.display.layout_structure.rows) == 2
        assert config.display.formatting.header_width == 120
        assert config.display.formatting.none_display == "___"

        # ZMK section
        assert config.zmk.compatible_strings.macro == "full-custom,macro"
        assert config.zmk.hold_tap_flavors == ["full-custom-preferred"]
        assert config.zmk.patterns.layer_define == "FULL_CUSTOM_{}"
        assert config.zmk.validation_limits.max_layers == 25


class TestKeyboardConfigSerialization:
    """Tests for KeyboardConfig serialization with new sections."""

    def test_keyboard_config_serialization_with_defaults(self):
        """Test KeyboardConfig serialization includes all sections."""
        config = KeyboardConfig(
            keyboard="serial_test",
            description="Test serialization",
            vendor="Test Vendor",
            key_count=50,
        )

        config_dict = config.model_dump()

        # Verify all sections are present in serialized output
        assert "keyboard" in config_dict
        assert "behavior" in config_dict
        assert "display" in config_dict
        assert "zmk" in config_dict
        assert "keymap" in config_dict

        # Verify nested structure
        assert "behavior_mappings" in config_dict["behavior"]
        assert "modifier_mappings" in config_dict["behavior"]
        assert "formatting" in config_dict["display"]
        assert "compatible_strings" in config_dict["zmk"]
        assert "hold_tap_flavors" in config_dict["zmk"]

    def test_keyboard_config_round_trip_serialization(self):
        """Test KeyboardConfig can be serialized and deserialized."""
        original_config = KeyboardConfig(
            keyboard="round_trip",
            description="Round trip test",
            vendor="Test Vendor",
            key_count=61,
            behavior=BehaviorConfig(
                behavior_mappings=[
                    BehaviorMapping(
                        behavior_name="&test", behavior_class="TestBehavior"
                    )
                ],
                magic_layer_command="&magic LAYER_Test 1",
            ),
            display=DisplayConfig(
                formatting=DisplayFormatting(header_width=90, none_display="TEST")
            ),
            zmk=ZmkConfig(
                patterns=ZmkPatterns(layer_define="TEST_{}"),
                validation_limits=ValidationLimits(max_layers=15),
            ),
        )

        # Serialize to dict
        config_dict = original_config.model_dump()

        # Deserialize back to model
        restored_config = KeyboardConfig.model_validate(config_dict)

        # Verify all data is preserved
        assert restored_config.keyboard == original_config.keyboard
        assert restored_config.key_count == original_config.key_count

        # Behavior section
        assert len(restored_config.behavior.behavior_mappings) == 1
        assert (
            restored_config.behavior.behavior_mappings[0].behavior_name
            == original_config.behavior.behavior_mappings[0].behavior_name
        )
        assert (
            restored_config.behavior.magic_layer_command
            == original_config.behavior.magic_layer_command
        )

        # Display section
        assert (
            restored_config.display.formatting.header_width
            == original_config.display.formatting.header_width
        )
        assert (
            restored_config.display.formatting.none_display
            == original_config.display.formatting.none_display
        )

        # ZMK section
        assert (
            restored_config.zmk.patterns.layer_define
            == original_config.zmk.patterns.layer_define
        )
        assert (
            restored_config.zmk.validation_limits.max_layers
            == original_config.zmk.validation_limits.max_layers
        )


class TestKeyboardConfigValidation:
    """Tests for KeyboardConfig validation with new sections."""

    def test_keyboard_config_required_fields_still_enforced(self):
        """Test that required fields are still enforced with new sections."""
        # Missing required keyboard field
        with pytest.raises(ValidationError):
            KeyboardConfig.model_validate(
                {
                    "description": "Missing keyboard name",
                    "vendor": "Test Vendor",
                    "key_count": 42,
                }
            )

        # Missing required description field
        with pytest.raises(ValidationError):
            KeyboardConfig.model_validate(
                {
                    "keyboard": "test_keyboard",
                    "vendor": "Test Vendor",
                    "key_count": 42,
                }
            )

        # Invalid key_count (zero)
        with pytest.raises(ValidationError):
            KeyboardConfig.model_validate(
                {
                    "keyboard": "test_keyboard",
                    "description": "Test description",
                    "vendor": "Test Vendor",
                    "key_count": 0,
                }
            )

    def test_keyboard_config_validates_nested_sections(self):
        """Test that nested section validation is properly enforced."""
        # Invalid behavior mapping
        with pytest.raises(ValidationError):
            KeyboardConfig.model_validate(
                {
                    "keyboard": "test_keyboard",
                    "description": "Test description",
                    "vendor": "Test Vendor",
                    "key_count": 42,
                    "behavior": {
                        "behavior_mappings": [
                            {
                                "behavior_name": "&kp"
                                # Missing behavior_class
                            }
                        ]
                    },
                }
            )

        # Invalid display formatting
        with pytest.raises(ValidationError):
            KeyboardConfig.model_validate(
                {
                    "keyboard": "test_keyboard",
                    "description": "Test description",
                    "vendor": "Test Vendor",
                    "key_count": 42,
                    "display": {"formatting": {"header_width": 0}},  # Invalid width
                }
            )

        # Invalid ZMK validation limits
        with pytest.raises(ValidationError):
            KeyboardConfig.model_validate(
                {
                    "keyboard": "test_keyboard",
                    "description": "Test description",
                    "vendor": "Test Vendor",
                    "key_count": 42,
                    "zmk": {
                        "validation_limits": {"max_layers": 0}  # Invalid max_layers
                    },
                }
            )


class TestKeyboardConfigIntegration:
    """Integration tests for KeyboardConfig with new sections."""

    def test_realistic_keyboard_configuration(self):
        """Test a realistic keyboard configuration with all sections."""
        # Simulate a realistic keyboard configuration
        realistic_config = {
            "keyboard": "ergodox_ez",
            "description": "ErgoDox EZ ergonomic keyboard",
            "vendor": "ZSA Technology Labs",
            "key_count": 76,
            "behavior": {
                "behavior_mappings": [
                    {"behavior_name": "&none", "behavior_class": "SimpleBehavior"},
                    {"behavior_name": "&trans", "behavior_class": "SimpleBehavior"},
                    {"behavior_name": "&kp", "behavior_class": "KPBehavior"},
                    {"behavior_name": "&lt", "behavior_class": "LayerTapBehavior"},
                    {"behavior_name": "&mt", "behavior_class": "ModTapBehavior"},
                ],
                "modifier_mappings": [
                    {"long_form": "LSHIFT", "short_form": "LS"},
                    {"long_form": "LCTL", "short_form": "LC"},
                    {"long_form": "LALT", "short_form": "LA"},
                    {"long_form": "LGUI", "short_form": "LG"},
                ],
                "magic_layer_command": "&magic LAYER_Magic 0",
                "reset_behavior_alias": "&sys_reset",
            },
            "display": {
                "layout_structure": {
                    "rows": {
                        "left_hand": [
                            [0, 1, 2, 3, 4, 5, 6],
                            [14, 15, 16, 17, 18, 19],
                            [28, 29, 30, 31, 32, 33, 34],
                            [42, 43, 44, 45, 46],
                        ],
                        "right_hand": [
                            [7, 8, 9, 10, 11, 12, 13],
                            [20, 21, 22, 23, 24, 25, 26, 27],
                            [35, 36, 37, 38, 39, 40, 41],
                            [47, 48, 49, 50, 51],
                        ],
                        "thumbs": [[52, 53, 54, 55, 56, 57], [58, 59, 60, 61, 62, 63]],
                    }
                },
                "formatting": {
                    "header_width": 120,
                    "none_display": "___",
                    "trans_display": "▽▽▽",
                    "key_width": 6,
                    "center_small_rows": True,
                    "horizontal_spacer": " │ ",
                },
            },
            "zmk": {
                "compatible_strings": {
                    "macro": "zmk,behavior-macro",
                    "hold_tap": "zmk,behavior-hold-tap",
                    "combos": "zmk,combos",
                },
                "hold_tap_flavors": [
                    "tap-preferred",
                    "hold-preferred",
                    "balanced",
                    "tap-unless-interrupted",
                ],
                "patterns": {
                    "layer_define": "LAYER_{}",
                    "node_name_sanitize": "[^A-Z0-9_]",
                },
                "file_extensions": {
                    "keymap": ".keymap",
                    "conf": ".conf",
                    "dtsi": ".dtsi",
                    "metadata": ".json",
                },
                "validation_limits": {
                    "max_layers": 8,
                    "max_macro_params": 3,
                    "required_holdtap_bindings": 2,
                    "warn_many_layers_threshold": 6,
                },
            },
        }

        config = KeyboardConfig.model_validate(realistic_config)

        # Verify the configuration is valid and complete
        assert config.keyboard == "ergodox_ez"
        assert config.key_count == 76

        # Verify behavior configuration
        assert len(config.behavior.behavior_mappings) == 5
        behavior_names = {
            mapping.behavior_name for mapping in config.behavior.behavior_mappings
        }
        assert "&kp" in behavior_names
        assert "&mt" in behavior_names
        assert len(config.behavior.modifier_mappings) == 4

        # Verify display configuration
        assert config.display.layout_structure is not None
        assert len(config.display.layout_structure.rows) == 3
        assert "left_hand" in config.display.layout_structure.rows
        assert config.display.formatting.header_width == 120

        # Verify ZMK configuration
        assert config.zmk.compatible_strings.macro == "zmk,behavior-macro"
        assert len(config.zmk.hold_tap_flavors) == 4
        assert config.zmk.validation_limits.max_layers == 8

    def test_minimal_keyboard_with_selective_customization(self):
        """Test minimal keyboard with only some sections customized."""
        minimal_custom = {
            "keyboard": "minimal_custom",
            "description": "Minimal keyboard with selective customization",
            "vendor": "Test Vendor",
            "key_count": 36,
            # Only customize ZMK section, leave others as defaults
            "zmk": {
                "validation_limits": {
                    "max_layers": 5,  # Smaller keyboard, fewer layers
                    "max_macro_params": 1,  # Simple macros only
                }
            },
        }

        config = KeyboardConfig.model_validate(minimal_custom)

        # Verify custom ZMK settings
        assert config.zmk.validation_limits.max_layers == 5
        assert config.zmk.validation_limits.max_macro_params == 1
        # Other ZMK settings should be defaults
        assert config.zmk.compatible_strings.macro == "zmk,behavior-macro"
        assert config.zmk.patterns.layer_define == "LAYER_{}"

        # Other sections should use defaults
        assert config.behavior.behavior_mappings == []
        assert config.behavior.magic_layer_command == "&magic LAYER_Magic 0"
        assert config.display.layout_structure is None
        assert config.display.formatting.header_width == 80
