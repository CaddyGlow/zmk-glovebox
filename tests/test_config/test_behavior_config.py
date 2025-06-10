"""Tests for behavior configuration models."""

import pytest
from pydantic import ValidationError

from glovebox.config.models import BehaviorConfig, BehaviorMapping, ModifierMapping


class TestBehaviorMapping:
    """Tests for BehaviorMapping model."""

    def test_valid_behavior_mapping(self):
        """Test valid behavior mapping creation."""
        mapping = BehaviorMapping(behavior_name="&kp", behavior_class="KPBehavior")

        assert mapping.behavior_name == "&kp"
        assert mapping.behavior_class == "KPBehavior"

    def test_behavior_mapping_with_complex_names(self):
        """Test behavior mapping with complex behavior names."""
        mapping = BehaviorMapping(behavior_name="&mt", behavior_class="ModTapBehavior")

        assert mapping.behavior_name == "&mt"
        assert mapping.behavior_class == "ModTapBehavior"

    def test_behavior_mapping_required_fields(self):
        """Test that required fields are enforced."""
        with pytest.raises(ValidationError):
            BehaviorMapping.model_validate(
                {"behavior_name": "&kp"}
            )  # Missing behavior_class

        with pytest.raises(ValidationError):
            BehaviorMapping.model_validate(
                {"behavior_class": "KPBehavior"}
            )  # Missing behavior_name


class TestModifierMapping:
    """Tests for ModifierMapping model."""

    def test_valid_modifier_mapping(self):
        """Test valid modifier mapping creation."""
        mapping = ModifierMapping(long_form="LALT", short_form="LA")

        assert mapping.long_form == "LALT"
        assert mapping.short_form == "LA"

    def test_modifier_mapping_variants(self):
        """Test different modifier mapping variants."""
        mappings = [
            ModifierMapping(long_form="LCTL", short_form="LC"),
            ModifierMapping(long_form="RSHIFT", short_form="RS"),
            ModifierMapping(long_form="LGUI", short_form="LG"),
        ]

        assert len(mappings) == 3
        assert mappings[0].long_form == "LCTL"
        assert mappings[1].short_form == "RS"

    def test_modifier_mapping_required_fields(self):
        """Test that required fields are enforced."""
        with pytest.raises(ValidationError):
            ModifierMapping.model_validate({"long_form": "LALT"})  # Missing short_form

        with pytest.raises(ValidationError):
            ModifierMapping.model_validate({"short_form": "LA"})  # Missing long_form


class TestBehaviorConfig:
    """Tests for BehaviorConfig model."""

    def test_default_behavior_config(self):
        """Test behavior config with defaults."""
        config = BehaviorConfig()

        assert config.behavior_mappings == []
        assert config.modifier_mappings == []
        assert config.magic_layer_command == "&magic LAYER_Magic 0"
        assert config.reset_behavior_alias == "&sys_reset"

    def test_behavior_config_with_mappings(self):
        """Test behavior config with custom mappings."""
        behavior_mappings = [
            BehaviorMapping(behavior_name="&kp", behavior_class="KPBehavior"),
            BehaviorMapping(behavior_name="&mt", behavior_class="ModTapBehavior"),
        ]

        modifier_mappings = [
            ModifierMapping(long_form="LALT", short_form="LA"),
            ModifierMapping(long_form="LCTL", short_form="LC"),
        ]

        config = BehaviorConfig(
            behavior_mappings=behavior_mappings,
            modifier_mappings=modifier_mappings,
            magic_layer_command="&magic LAYER_Custom 1",
            reset_behavior_alias="&custom_reset",
        )

        assert len(config.behavior_mappings) == 2
        assert len(config.modifier_mappings) == 2
        assert config.magic_layer_command == "&magic LAYER_Custom 1"
        assert config.reset_behavior_alias == "&custom_reset"

    def test_behavior_config_serialization(self):
        """Test behavior config serialization."""
        config = BehaviorConfig(
            behavior_mappings=[
                BehaviorMapping(behavior_name="&none", behavior_class="SimpleBehavior"),
                BehaviorMapping(
                    behavior_name="&trans", behavior_class="SimpleBehavior"
                ),
            ],
            modifier_mappings=[
                ModifierMapping(long_form="LSHIFT", short_form="LS"),
            ],
        )

        # Test that it can be converted to dict
        config_dict = config.model_dump()

        assert "behavior_mappings" in config_dict
        assert "modifier_mappings" in config_dict
        assert len(config_dict["behavior_mappings"]) == 2
        assert len(config_dict["modifier_mappings"]) == 1

    def test_behavior_config_from_dict(self):
        """Test behavior config creation from dictionary."""
        config_dict = {
            "behavior_mappings": [
                {"behavior_name": "&kp", "behavior_class": "KPBehavior"},
                {"behavior_name": "&lt", "behavior_class": "LayerTapBehavior"},
            ],
            "modifier_mappings": [
                {"long_form": "LALT", "short_form": "LA"},
                {"long_form": "RALT", "short_form": "RA"},
            ],
            "magic_layer_command": "&magic LAYER_Test 0",
            "reset_behavior_alias": "&test_reset",
        }

        config = BehaviorConfig.model_validate(config_dict)

        assert len(config.behavior_mappings) == 2
        assert config.behavior_mappings[0].behavior_name == "&kp"
        assert config.behavior_mappings[1].behavior_class == "LayerTapBehavior"
        assert len(config.modifier_mappings) == 2
        assert config.modifier_mappings[0].long_form == "LALT"
        assert config.magic_layer_command == "&magic LAYER_Test 0"
        assert config.reset_behavior_alias == "&test_reset"

    def test_empty_behavior_config_validation(self):
        """Test that empty behavior config is valid."""
        config = BehaviorConfig(behavior_mappings=[], modifier_mappings=[])

        assert config.behavior_mappings == []
        assert config.modifier_mappings == []
        assert config.magic_layer_command == "&magic LAYER_Magic 0"
        assert config.reset_behavior_alias == "&sys_reset"


class TestBehaviorConfigIntegration:
    """Integration tests for behavior configuration."""

    def test_complete_behavior_configuration(self):
        """Test a complete behavior configuration."""
        # Simulate a realistic behavior configuration
        config_data = {
            "behavior_mappings": [
                {"behavior_name": "&none", "behavior_class": "SimpleBehavior"},
                {"behavior_name": "&trans", "behavior_class": "SimpleBehavior"},
                {"behavior_name": "&kp", "behavior_class": "KPBehavior"},
                {"behavior_name": "&lt", "behavior_class": "LayerTapBehavior"},
                {"behavior_name": "&mt", "behavior_class": "ModTapBehavior"},
                {"behavior_name": "&sk", "behavior_class": "StickyKeyBehavior"},
                {"behavior_name": "&sl", "behavior_class": "StickyLayerBehavior"},
                {"behavior_name": "&mo", "behavior_class": "MomentaryLayerBehavior"},
                {"behavior_name": "&to", "behavior_class": "ToLayerBehavior"},
                {"behavior_name": "&tog", "behavior_class": "ToggleLayerBehavior"},
            ],
            "modifier_mappings": [
                {"long_form": "LSHIFT", "short_form": "LS"},
                {"long_form": "LCTL", "short_form": "LC"},
                {"long_form": "LALT", "short_form": "LA"},
                {"long_form": "LGUI", "short_form": "LG"},
                {"long_form": "RSHIFT", "short_form": "RS"},
                {"long_form": "RCTL", "short_form": "RC"},
                {"long_form": "RALT", "short_form": "RA"},
                {"long_form": "RGUI", "short_form": "RG"},
            ],
            "magic_layer_command": "&magic LAYER_Magic 0",
            "reset_behavior_alias": "&sys_reset",
        }

        config = BehaviorConfig.model_validate(config_data)

        # Verify all behavior mappings
        assert len(config.behavior_mappings) == 10
        behavior_names = {mapping.behavior_name for mapping in config.behavior_mappings}
        expected_behaviors = {
            "&none",
            "&trans",
            "&kp",
            "&lt",
            "&mt",
            "&sk",
            "&sl",
            "&mo",
            "&to",
            "&tog",
        }
        assert behavior_names == expected_behaviors

        # Verify all modifier mappings
        assert len(config.modifier_mappings) == 8
        modifier_forms = {mapping.long_form for mapping in config.modifier_mappings}
        expected_modifiers = {
            "LSHIFT",
            "LCTL",
            "LALT",
            "LGUI",
            "RSHIFT",
            "RCTL",
            "RALT",
            "RGUI",
        }
        assert modifier_forms == expected_modifiers

        # Verify special commands
        assert config.magic_layer_command == "&magic LAYER_Magic 0"
        assert config.reset_behavior_alias == "&sys_reset"
