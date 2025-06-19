"""Tests for ZMK configuration models."""

import pytest
from pydantic import ValidationError

from glovebox.config.models import (
    FileExtensions,
    ValidationLimits,
    ZmkCompatibleStrings,
    ZmkConfig,
    ZmkPatterns,
)


class TestZmkCompatibleStrings:
    """Tests for ZmkCompatibleStrings model."""

    def test_default_zmk_compatible_strings(self):
        """Test ZmkCompatibleStrings with default values."""
        compatible = ZmkCompatibleStrings()

        assert compatible.macro == "zmk,behavior-macro"
        assert compatible.hold_tap == "zmk,behavior-hold-tap"
        assert compatible.combos == "zmk,combos"

    def test_custom_zmk_compatible_strings(self):
        """Test ZmkCompatibleStrings with custom values."""
        compatible = ZmkCompatibleStrings(
            macro="custom,behavior-macro",
            hold_tap="custom,behavior-hold-tap",
            combos="custom,combos",
        )

        assert compatible.macro == "custom,behavior-macro"
        assert compatible.hold_tap == "custom,behavior-hold-tap"
        assert compatible.combos == "custom,combos"

    def test_zmk_compatible_strings_serialization(self):
        """Test ZmkCompatibleStrings serialization."""
        compatible = ZmkCompatibleStrings(
            macro="test,macro", hold_tap="test,hold-tap", combos="test,combos"
        )

        compatible_dict = compatible.model_dump(
            by_alias=True, exclude_unset=True, mode="json"
        )

        assert compatible_dict["macro"] == "test,macro"
        assert compatible_dict["hold_tap"] == "test,hold-tap"
        assert compatible_dict["combos"] == "test,combos"

    def test_zmk_compatible_strings_from_dict(self):
        """Test ZmkCompatibleStrings creation from dictionary."""
        data = {
            "macro": "dict,behavior-macro",
            "hold_tap": "dict,behavior-hold-tap",
            "combos": "dict,combos",
        }

        compatible = ZmkCompatibleStrings.model_validate(data)

        assert compatible.macro == "dict,behavior-macro"
        assert compatible.hold_tap == "dict,behavior-hold-tap"
        assert compatible.combos == "dict,combos"


class TestZmkPatterns:
    """Tests for ZmkPatterns model."""

    def test_default_zmk_patterns(self):
        """Test ZmkPatterns with default values."""
        patterns = ZmkPatterns()

        assert patterns.layer_define == "LAYER_{}"
        assert patterns.node_name_sanitize == "[^A-Z0-9_]"

    def test_custom_zmk_patterns(self):
        """Test ZmkPatterns with custom values."""
        patterns = ZmkPatterns(
            layer_define="CUSTOM_LAYER_{}", node_name_sanitize="[^a-zA-Z0-9_]"
        )

        assert patterns.layer_define == "CUSTOM_LAYER_{}"
        assert patterns.node_name_sanitize == "[^a-zA-Z0-9_]"

    def test_zmk_patterns_serialization(self):
        """Test ZmkPatterns serialization."""
        patterns = ZmkPatterns(layer_define="TEST_{}", node_name_sanitize="[^A-Z]")

        patterns_dict = patterns.model_dump(
            by_alias=True, exclude_unset=True, mode="json"
        )

        assert patterns_dict["layer_define"] == "TEST_{}"
        assert patterns_dict["node_name_sanitize"] == "[^A-Z]"

    def test_zmk_patterns_from_dict(self):
        """Test ZmkPatterns creation from dictionary."""
        data = {
            "layer_define": "DICT_LAYER_{}",
            "node_name_sanitize": "[^0-9A-Z_]",
        }

        patterns = ZmkPatterns.model_validate(data)

        assert patterns.layer_define == "DICT_LAYER_{}"
        assert patterns.node_name_sanitize == "[^0-9A-Z_]"


class TestFileExtensions:
    """Tests for FileExtensions model."""

    def test_default_file_extensions(self):
        """Test FileExtensions with default values."""
        extensions = FileExtensions()

        assert extensions.keymap == ".keymap"
        assert extensions.conf == ".conf"
        assert extensions.dtsi == ".dtsi"
        assert extensions.metadata == ".json"

    def test_custom_file_extensions(self):
        """Test FileExtensions with custom values."""
        extensions = FileExtensions(
            keymap=".custom_keymap",
            conf=".custom_conf",
            dtsi=".custom_dtsi",
            metadata=".custom_json",
        )

        assert extensions.keymap == ".custom_keymap"
        assert extensions.conf == ".custom_conf"
        assert extensions.dtsi == ".custom_dtsi"
        assert extensions.metadata == ".custom_json"

    def test_file_extensions_serialization(self):
        """Test FileExtensions serialization."""
        extensions = FileExtensions(
            keymap=".test_keymap", conf=".test_conf", dtsi=".test_dtsi"
        )

        extensions_dict = extensions.model_dump(by_alias=True, mode="json")

        assert extensions_dict["keymap"] == ".test_keymap"
        assert extensions_dict["conf"] == ".test_conf"
        assert extensions_dict["dtsi"] == ".test_dtsi"
        assert extensions_dict["metadata"] == ".json"  # Default

    def test_file_extensions_from_dict(self):
        """Test FileExtensions creation from dictionary."""
        data = {
            "keymap": ".dict_keymap",
            "conf": ".dict_conf",
            "dtsi": ".dict_dtsi",
            "metadata": ".dict_metadata",
        }

        extensions = FileExtensions.model_validate(data)

        assert extensions.keymap == ".dict_keymap"
        assert extensions.conf == ".dict_conf"
        assert extensions.dtsi == ".dict_dtsi"
        assert extensions.metadata == ".dict_metadata"


class TestValidationLimits:
    """Tests for ValidationLimits model."""

    def test_default_validation_limits(self):
        """Test ValidationLimits with default values."""
        limits = ValidationLimits()

        assert limits.max_layers == 10
        assert limits.max_macro_params == 2
        assert limits.required_holdtap_bindings == 2
        assert limits.warn_many_layers_threshold == 10

    def test_custom_validation_limits(self):
        """Test ValidationLimits with custom values."""
        limits = ValidationLimits(
            max_layers=20,
            max_macro_params=5,
            required_holdtap_bindings=3,
            warn_many_layers_threshold=15,
        )

        assert limits.max_layers == 20
        assert limits.max_macro_params == 5
        assert limits.required_holdtap_bindings == 3
        assert limits.warn_many_layers_threshold == 15

    def test_validation_limits_positive_constraints(self):
        """Test that ValidationLimits enforces positive values."""
        # All fields should be positive
        with pytest.raises(ValidationError):
            ValidationLimits(max_layers=0)

        with pytest.raises(ValidationError):
            ValidationLimits(max_macro_params=0)

        with pytest.raises(ValidationError):
            ValidationLimits(required_holdtap_bindings=0)

        with pytest.raises(ValidationError):
            ValidationLimits(warn_many_layers_threshold=0)

        with pytest.raises(ValidationError):
            ValidationLimits(max_layers=-1)

    def test_validation_limits_serialization(self):
        """Test ValidationLimits serialization."""
        limits = ValidationLimits(
            max_layers=25, max_macro_params=3, required_holdtap_bindings=4
        )

        limits_dict = limits.model_dump(by_alias=True, mode="json")

        assert limits_dict["max_layers"] == 25
        assert limits_dict["max_macro_params"] == 3
        assert limits_dict["required_holdtap_bindings"] == 4
        assert limits_dict["warn_many_layers_threshold"] == 10  # Default

    def test_validation_limits_from_dict(self):
        """Test ValidationLimits creation from dictionary."""
        data = {
            "max_layers": 50,
            "max_macro_params": 10,
            "required_holdtap_bindings": 5,
            "warn_many_layers_threshold": 40,
        }

        limits = ValidationLimits.model_validate(data)

        assert limits.max_layers == 50
        assert limits.max_macro_params == 10
        assert limits.required_holdtap_bindings == 5
        assert limits.warn_many_layers_threshold == 40


class TestZmkConfig:
    """Tests for ZmkConfig model."""

    def test_default_zmk_config(self):
        """Test ZmkConfig with all defaults."""
        config = ZmkConfig()

        # Check compatible strings defaults
        assert config.compatible_strings.macro == "zmk,behavior-macro"
        assert config.compatible_strings.hold_tap == "zmk,behavior-hold-tap"
        assert config.compatible_strings.combos == "zmk,combos"

        # Check hold tap flavors defaults
        expected_flavors = [
            "tap-preferred",
            "hold-preferred",
            "balanced",
            "tap-unless-interrupted",
        ]
        assert config.hold_tap_flavors == expected_flavors

        # Check patterns defaults
        assert config.patterns.layer_define == "LAYER_{}"
        assert config.patterns.node_name_sanitize == "[^A-Z0-9_]"

        # Check file extensions defaults
        assert config.file_extensions.keymap == ".keymap"
        assert config.file_extensions.conf == ".conf"
        assert config.file_extensions.dtsi == ".dtsi"
        assert config.file_extensions.metadata == ".json"

        # Check validation limits defaults
        assert config.validation_limits.max_layers == 10
        assert config.validation_limits.max_macro_params == 2

    def test_custom_zmk_config(self):
        """Test ZmkConfig with custom values."""
        config = ZmkConfig(
            compatible_strings=ZmkCompatibleStrings(
                macro="custom,macro", hold_tap="custom,hold-tap", combos="custom,combos"
            ),
            hold_tap_flavors=["custom-preferred", "balanced"],
            patterns=ZmkPatterns(layer_define="CUSTOM_{}", node_name_sanitize="[^A-Z]"),
            file_extensions=FileExtensions(keymap=".custom", conf=".custom_conf"),
            validation_limits=ValidationLimits(max_layers=20, max_macro_params=5),
        )

        # Verify custom values
        assert config.compatible_strings.macro == "custom,macro"
        assert config.hold_tap_flavors == ["custom-preferred", "balanced"]
        assert config.patterns.layer_define == "CUSTOM_{}"
        assert config.file_extensions.keymap == ".custom"
        assert config.validation_limits.max_layers == 20

    def test_zmk_config_serialization(self):
        """Test ZmkConfig serialization."""
        config = ZmkConfig(
            hold_tap_flavors=["test-preferred", "test-balanced"],
            patterns=ZmkPatterns(layer_define="TEST_{}"),
        )

        config_dict = config.model_dump(by_alias=True, mode="json")

        # Check nested structures
        assert "compatible_strings" in config_dict
        assert "hold_tap_flavors" in config_dict
        assert "patterns" in config_dict
        assert "file_extensions" in config_dict
        assert "validation_limits" in config_dict

        # Check specific values
        assert config_dict["hold_tap_flavors"] == ["test-preferred", "test-balanced"]
        assert config_dict["patterns"]["layer_define"] == "TEST_{}"

    def test_zmk_config_from_dict(self):
        """Test ZmkConfig creation from dictionary."""
        data = {
            "compatible_strings": {
                "macro": "dict,macro",
                "hold_tap": "dict,hold-tap",
                "combos": "dict,combos",
            },
            "hold_tap_flavors": ["dict-preferred", "dict-balanced"],
            "patterns": {
                "layer_define": "DICT_{}",
                "node_name_sanitize": "[^A-Z0-9]",
            },
            "file_extensions": {
                "keymap": ".dict_keymap",
                "conf": ".dict_conf",
                "dtsi": ".dict_dtsi",
                "metadata": ".dict_json",
            },
            "validation_limits": {
                "max_layers": 30,
                "max_macro_params": 8,
                "required_holdtap_bindings": 3,
                "warn_many_layers_threshold": 25,
            },
        }

        config = ZmkConfig.model_validate(data)

        # Verify nested values
        assert config.compatible_strings.macro == "dict,macro"
        assert config.hold_tap_flavors == ["dict-preferred", "dict-balanced"]
        assert config.patterns.layer_define == "DICT_{}"
        assert config.file_extensions.keymap == ".dict_keymap"
        assert config.validation_limits.max_layers == 30

    def test_partial_zmk_config_from_dict(self):
        """Test ZmkConfig with partial dictionary (should use defaults)."""
        data = {
            "hold_tap_flavors": ["partial-only"],
            "patterns": {"layer_define": "PARTIAL_{}"},
        }

        config = ZmkConfig.model_validate(data)

        # Custom values
        assert config.hold_tap_flavors == ["partial-only"]
        assert config.patterns.layer_define == "PARTIAL_{}"

        # Default values for unspecified sections
        assert config.compatible_strings.macro == "zmk,behavior-macro"  # Default
        assert config.file_extensions.keymap == ".keymap"  # Default
        assert config.validation_limits.max_layers == 10  # Default


class TestZmkConfigIntegration:
    """Integration tests for ZmkConfig."""

    def test_realistic_zmk_configuration(self):
        """Test a realistic ZMK configuration."""
        # Simulate a real-world ZMK configuration
        realistic_config = {
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
                "max_layers": 10,
                "max_macro_params": 2,
                "required_holdtap_bindings": 2,
                "warn_many_layers_threshold": 10,
            },
        }

        config = ZmkConfig.model_validate(realistic_config)

        # Verify all sections are properly configured
        assert config.compatible_strings.macro == "zmk,behavior-macro"
        assert len(config.hold_tap_flavors) == 4
        assert "balanced" in config.hold_tap_flavors
        assert config.patterns.layer_define == "LAYER_{}"
        assert config.file_extensions.keymap == ".keymap"
        assert config.validation_limits.max_layers == 10

    def test_custom_keyboard_zmk_configuration(self):
        """Test a custom keyboard's ZMK configuration."""
        # Simulate a custom keyboard with specific requirements
        custom_config = {
            "compatible_strings": {
                "macro": "custom-kb,behavior-macro",
                "hold_tap": "custom-kb,behavior-hold-tap",
                "combos": "custom-kb,combos",
            },
            "hold_tap_flavors": [
                "custom-tap-preferred",
                "custom-hold-preferred",
                "custom-balanced",
            ],
            "patterns": {
                "layer_define": "CUSTOM_LAYER_{}",
                "node_name_sanitize": "[^A-Z0-9_-]",  # Allow hyphens
            },
            "file_extensions": {
                "keymap": ".custom_keymap",
                "conf": ".custom_conf",
                "dtsi": ".custom_dtsi",
                "metadata": ".custom_metadata",
            },
            "validation_limits": {
                "max_layers": 20,  # More layers for complex layouts
                "max_macro_params": 5,  # More complex macros
                "required_holdtap_bindings": 3,
                "warn_many_layers_threshold": 15,
            },
        }

        config = ZmkConfig.model_validate(custom_config)

        # Verify custom configuration
        assert config.compatible_strings.macro == "custom-kb,behavior-macro"
        assert len(config.hold_tap_flavors) == 3
        assert "custom-balanced" in config.hold_tap_flavors
        assert config.patterns.layer_define == "CUSTOM_LAYER_{}"
        assert config.patterns.node_name_sanitize == "[^A-Z0-9_-]"
        assert config.file_extensions.keymap == ".custom_keymap"
        assert config.validation_limits.max_layers == 20
        assert config.validation_limits.max_macro_params == 5

    def test_zmk_config_edge_cases(self):
        """Test ZmkConfig edge cases and boundary conditions."""
        # Test with minimal valid configuration
        minimal_config = {
            "validation_limits": {
                "max_layers": 1,  # Minimum valid value
                "max_macro_params": 1,  # Minimum valid value
                "required_holdtap_bindings": 1,  # Minimum valid value
                "warn_many_layers_threshold": 1,  # Minimum valid value
            }
        }

        config = ZmkConfig.model_validate(minimal_config)

        # Should accept minimal valid values
        assert config.validation_limits.max_layers == 1
        assert config.validation_limits.max_macro_params == 1

        # Other sections should use defaults
        assert config.compatible_strings.macro == "zmk,behavior-macro"
        assert len(config.hold_tap_flavors) == 4

    def test_empty_zmk_config_uses_all_defaults(self):
        """Test that empty ZmkConfig uses all defaults."""
        config = ZmkConfig.model_validate({})

        # Should be identical to default constructor
        default_config = ZmkConfig()

        assert (
            config.compatible_strings.macro == default_config.compatible_strings.macro
        )
        assert config.hold_tap_flavors == default_config.hold_tap_flavors
        assert config.patterns.layer_define == default_config.patterns.layer_define
        assert config.file_extensions.keymap == default_config.file_extensions.keymap
        assert (
            config.validation_limits.max_layers
            == default_config.validation_limits.max_layers
        )
