"""Tests for the behavior formatter."""

import pytest

from glovebox.config.models import BehaviorConfig, BehaviorMapping, ModifierMapping
from glovebox.layout.behavior.formatter import BehaviorFormatterImpl
from glovebox.layout.models import (
    LayoutBinding,
    LayoutParam,
    SystemBehavior,
)
from glovebox.protocols.behavior_protocols import BehaviorRegistryProtocol


class MockBehaviorRegistry:
    """Mock implementation of BehaviorRegistryProtocol for testing."""

    def __init__(self):
        """Initialize the mock registry."""
        self.behaviors = {}

    def register_behavior(self, behavior):
        """Register a behavior in the registry."""
        self.behaviors[behavior.code] = behavior

    def get_behavior_info(self, name):
        """Get information about a registered behavior."""
        return self.behaviors.get(name)

    def list_behaviors(self):
        """List all registered behaviors."""
        return self.behaviors


@pytest.fixture
def behavior_registry():
    """Create a mock behavior registry for testing."""
    registry = MockBehaviorRegistry()

    # Register some common behaviors
    registry.register_behavior(
        SystemBehavior(
            code="&kp",
            name="Key Press",
            description="Key press behavior",
            expected_params=1,
            origin="zmk_core",
            params=[],
        )
    )

    registry.register_behavior(
        SystemBehavior(
            code="&mo",
            name="Momentary Layer",
            description="Momentary layer shift",
            expected_params=1,
            origin="zmk_core",
            params=[],
        )
    )

    registry.register_behavior(
        SystemBehavior(
            code="&lt",
            name="Layer Tap",
            description="Layer tap behavior",
            expected_params=2,
            origin="zmk_core",
            params=[],
        )
    )

    registry.register_behavior(
        SystemBehavior(
            code="&none",
            name="None",
            description="No-op behavior",
            expected_params=0,
            origin="zmk_core",
            params=[],
        )
    )

    return registry


@pytest.fixture
def behavior_formatter(behavior_registry):
    """Create a behavior formatter with the mock registry."""
    keycode_map = {
        "A": "A",
        "B": "B",
        "SPACE": "SPACE",
        "ENTER": "ENTER",
    }
    return BehaviorFormatterImpl(behavior_registry, keycode_map=keycode_map)


def test_formatter_instantiation(behavior_registry):
    """Test that the formatter can be instantiated with our protocol."""
    # This test verifies that BehaviorFormatterImpl accepts our BehaviorRegistryProtocol
    formatter = BehaviorFormatterImpl(behavior_registry)
    assert formatter._registry is behavior_registry
    assert isinstance(formatter._registry, BehaviorRegistryProtocol)


def test_format_simple_binding(behavior_formatter):
    """Test formatting a simple binding."""
    binding = LayoutBinding(value="&kp", params=[LayoutParam(value="A")])
    result = behavior_formatter.format_binding(binding)
    assert result == "&kp A"


def test_format_zero_param_binding(behavior_formatter):
    """Test formatting a binding with no parameters."""
    binding = LayoutBinding(value="&none", params=[])
    result = behavior_formatter.format_binding(binding)
    assert result == "&none"


def test_format_multi_param_binding(behavior_formatter):
    """Test formatting a binding with multiple parameters."""
    binding = LayoutBinding(
        value="&lt", params=[LayoutParam(value="1"), LayoutParam(value="SPACE")]
    )
    result = behavior_formatter.format_binding(binding)
    assert result == "&lt 1 SPACE"


def test_format_binding_with_nested_params(behavior_formatter):
    """Test formatting a binding with nested parameters (modifiers)."""
    # Create a binding with nested structure for testing modifiers
    binding = LayoutBinding(
        value="&kp",
        params=[LayoutParam(value="LSHFT", params=[LayoutParam(value="A")])],
    )

    result = behavior_formatter.format_binding(binding)
    assert result == "&kp LS(A)"


def test_format_custom_behavior(behavior_formatter, behavior_registry):
    """Test formatting a custom behavior."""
    # Register a custom behavior
    behavior_registry.register_behavior(
        SystemBehavior(
            code="&custom_behavior",
            name="Custom Behavior",
            description="A custom test behavior",
            expected_params=2,
            origin="user",
            params=[],
        )
    )

    binding = LayoutBinding(
        value="&custom_behavior",
        params=[LayoutParam(value="1"), LayoutParam(value="2")],
    )

    result = behavior_formatter.format_binding(binding)
    assert result == "&custom_behavior 1 2"


def test_behavior_with_missing_params(behavior_formatter, behavior_registry):
    """Test a behavior with missing parameters generates an appropriate error."""
    binding = LayoutBinding(
        value="&lt",
        params=[
            LayoutParam(value="1")
            # Missing second parameter
        ],
    )

    result = behavior_formatter.format_binding(binding)
    # The formatter should properly handle the error case for missing parameters
    assert "&error" in result
    assert "requires exactly 2 parameters" in result


def test_format_invalid_behavior(behavior_formatter):
    """Test formatting an invalid behavior."""
    binding = LayoutBinding(value="&invalid", params=[])
    result = behavior_formatter.format_binding(binding)
    # Should return an error binding or similar
    assert "&error" in result or "invalid" in result.lower()


class TestBehaviorConfigurationSupport:
    """Tests for behavior configuration support."""

    def test_formatter_with_behavior_config(self, behavior_registry):
        """Test formatter with custom behavior configuration."""
        # Create custom behavior configuration
        behavior_config = BehaviorConfig(
            behavior_mappings=[
                BehaviorMapping(behavior_name="&kp", behavior_class="KPBehavior"),
                BehaviorMapping(
                    behavior_name="&custom", behavior_class="SimpleBehavior"
                ),
            ],
            modifier_mappings=[
                ModifierMapping(long_form="LALT", short_form="LA"),
                ModifierMapping(long_form="CUSTOM_MOD", short_form="CM"),
            ],
            magic_layer_command="&magic LAYER_Custom 1",
            reset_behavior_alias="&custom_reset",
        )

        # Create formatter with configuration
        formatter = BehaviorFormatterImpl(behavior_registry, behavior_config)

        # Test that behavior mappings are applied
        assert "&custom" in formatter._behavior_classes
        assert formatter._behavior_classes["&custom"].__name__ == "SimpleBehavior"

        # Test that modifier mappings are applied
        assert formatter._modifier_map["CUSTOM_MOD"] == "CM"
        assert formatter._modifier_map["LALT"] == "LA"  # Should still have defaults

    def test_configured_modifier_mapping(self, behavior_registry):
        """Test that configured modifier mappings are used."""
        behavior_config = BehaviorConfig(
            modifier_mappings=[
                ModifierMapping(long_form="CUSTOM_ALT", short_form="CA"),
            ]
        )

        formatter = BehaviorFormatterImpl(behavior_registry, behavior_config)

        # Create a binding with the custom modifier
        binding = LayoutBinding(
            value="&kp",
            params=[LayoutParam(value="CUSTOM_ALT", params=[LayoutParam(value="A")])],
        )

        result = formatter.format_binding(binding)
        assert result == "&kp CA(A)"

    def test_configured_reset_behavior_alias(self, behavior_registry):
        """Test that configured reset behavior alias is used."""
        behavior_config = BehaviorConfig(reset_behavior_alias="&custom_reset")

        formatter = BehaviorFormatterImpl(behavior_registry, behavior_config)

        # Test reset behavior uses custom alias
        binding = LayoutBinding(value="&reset", params=[])
        result = formatter.format_binding(binding)
        assert result == "&custom_reset"

    def test_configured_magic_layer_command(self, behavior_registry):
        """Test that configured magic layer command is used."""
        behavior_config = BehaviorConfig(magic_layer_command="&magic LAYER_Custom 1")

        formatter = BehaviorFormatterImpl(behavior_registry, behavior_config)

        # Test magic behavior uses custom command
        binding = LayoutBinding(value="&magic", params=[])
        result = formatter.format_binding(binding)
        assert result == "&magic LAYER_Custom 1"

    def test_backward_compatibility_without_config(self, behavior_registry):
        """Test that formatter works without configuration (backward compatibility)."""
        # Create formatter without behavior config (old way)
        formatter = BehaviorFormatterImpl(behavior_registry)

        # Should still work with default mappings
        binding = LayoutBinding(value="&kp", params=[LayoutParam(value="A")])
        result = formatter.format_binding(binding)
        assert result == "&kp A"

        # Should use default modifier mappings
        binding = LayoutBinding(
            value="&kp",
            params=[LayoutParam(value="LALT", params=[LayoutParam(value="A")])],
        )
        result = formatter.format_binding(binding)
        assert result == "&kp LA(A)"

        # Should use default reset alias
        binding = LayoutBinding(value="&reset", params=[])
        result = formatter.format_binding(binding)
        assert result == "&sys_reset"

        # Should use default magic command
        binding = LayoutBinding(value="&magic", params=[])
        result = formatter.format_binding(binding)
        assert result == "&magic LAYER_Magic 0"

    def test_configuration_override_defaults(self, behavior_registry):
        """Test that configuration properly overrides defaults."""
        behavior_config = BehaviorConfig(
            modifier_mappings=[
                ModifierMapping(
                    long_form="LALT", short_form="CUSTOM_ALT"
                ),  # Override default
            ]
        )

        formatter = BehaviorFormatterImpl(behavior_registry, behavior_config)

        # Should use overridden mapping
        binding = LayoutBinding(
            value="&kp",
            params=[LayoutParam(value="LALT", params=[LayoutParam(value="A")])],
        )
        result = formatter.format_binding(binding)
        assert result == "&kp CUSTOM_ALT(A)"

        # Should still have other defaults
        binding = LayoutBinding(
            value="&kp",
            params=[LayoutParam(value="LCTL", params=[LayoutParam(value="A")])],
        )
        result = formatter.format_binding(binding)
        assert result == "&kp LC(A)"

    def test_unknown_behavior_class_warning(self, behavior_registry):
        """Test that unknown behavior classes generate warnings."""
        behavior_config = BehaviorConfig(
            behavior_mappings=[
                BehaviorMapping(
                    behavior_name="&unknown", behavior_class="UnknownBehavior"
                ),
            ]
        )

        # Should log warning for unknown behavior class but still work
        formatter = BehaviorFormatterImpl(behavior_registry, behavior_config)

        # Unknown behavior should not be in the mapping
        assert "&unknown" not in formatter._behavior_classes


class TestHoldTapBindingContext:
    """Tests for hold-tap binding context functionality."""

    def test_hold_tap_context_switching(self, behavior_formatter):
        """Test hold-tap context can be switched on and off."""
        # Default should be False
        assert not behavior_formatter._is_hold_tap_binding_context

        # Should be able to set to True
        behavior_formatter.set_hold_tap_binding_context(True)
        assert behavior_formatter._is_hold_tap_binding_context

        # Should be able to set back to False
        behavior_formatter.set_hold_tap_binding_context(False)
        assert not behavior_formatter._is_hold_tap_binding_context

    def test_layer_toggle_behavior_in_hold_tap_context(self, behavior_formatter):
        """Test LayerToggleBehavior handles hold-tap context correctly."""
        # In normal context, &mo without params should error
        behavior_formatter.set_hold_tap_binding_context(False)
        binding = LayoutBinding(value="&mo", params=[])
        result = behavior_formatter.format_binding(binding)
        assert "&error" in result
        assert "requires exactly 1 parameter" in result

        # In hold-tap context, &mo without params should work
        behavior_formatter.set_hold_tap_binding_context(True)
        result = behavior_formatter.format_binding(binding)
        assert result == "&mo"

        # With params should work in both contexts
        binding_with_param = LayoutBinding(
            value="&mo", params=[LayoutParam(value="1", params=[])]
        )
        result = behavior_formatter.format_binding(binding_with_param)
        assert result == "&mo 1"

    def test_custom_behavior_in_hold_tap_context(
        self, behavior_formatter, behavior_registry
    ):
        """Test CustomBehaviorRef handles hold-tap context correctly."""
        # Register a custom behavior that expects parameters
        behavior_registry.register_behavior(
            SystemBehavior(
                code="&custom_ht",
                name="Custom Hold-Tap",
                description="Custom behavior for testing",
                expected_params=2,
                origin="user",
                params=[],
            )
        )

        # In normal context, missing params should add MACRO_PLACEHOLDER
        behavior_formatter.set_hold_tap_binding_context(False)
        binding = LayoutBinding(
            value="&custom_ht",
            params=[LayoutParam(value="A", params=[])],  # Only 1 param, expects 2
        )
        result = behavior_formatter.format_binding(binding)
        assert "MACRO_PLACEHOLDER" in result

        # In hold-tap context, no params should give bare reference
        behavior_formatter.set_hold_tap_binding_context(True)
        binding_no_params = LayoutBinding(value="&custom_ht", params=[])
        result = behavior_formatter.format_binding(binding_no_params)
        assert result == "&custom_ht"


class TestMacroPlaceholder:
    """Tests for MACRO_PLACEHOLDER usage."""

    def test_macro_placeholder_import(self):
        """Test that MACRO_PLACEHOLDER can be imported."""
        from glovebox.config.models.zmk import MACRO_PLACEHOLDER

        assert MACRO_PLACEHOLDER == "MACRO_PLACEHOLDER"

    def test_custom_behavior_uses_macro_placeholder(
        self, behavior_formatter, behavior_registry
    ):
        """Test that missing parameters use MACRO_PLACEHOLDER instead of '0'."""
        # Register a behavior that expects 2 parameters
        behavior_registry.register_behavior(
            SystemBehavior(
                code="&test_behavior",
                name="Test Behavior",
                description="Test behavior for placeholder testing",
                expected_params=2,
                origin="layout",
                params=[],
            )
        )

        # Binding with only 1 parameter (missing 1)
        binding = LayoutBinding(
            value="&test_behavior", params=[LayoutParam(value="PARAM1", params=[])]
        )

        result = behavior_formatter.format_binding(binding)
        assert result == "&test_behavior PARAM1 MACRO_PLACEHOLDER"
        # Should NOT use "0"
        assert " 0" not in result
