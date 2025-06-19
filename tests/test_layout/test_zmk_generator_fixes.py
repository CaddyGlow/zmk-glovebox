"""Tests for ZMK generator fixes covering all the issues we resolved."""

from unittest.mock import Mock

import pytest

from glovebox.config.models.zmk import MACRO_PLACEHOLDER, ZmkCompatibleStrings
from glovebox.layout.behavior.formatter import BehaviorFormatterImpl
from glovebox.layout.models import (
    ComboBehavior,
    HoldTapBehavior,
    LayoutBinding,
    LayoutData,
    LayoutParam,
    MacroBehavior,
    SystemBehavior,
)
from glovebox.layout.zmk_generator import ZmkFileContentGenerator
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


class MockKeyboardProfile:
    """Mock keyboard profile for testing."""

    def __init__(self):
        self.keyboard_config = Mock()
        self.keyboard_config.key_count = 80
        self.keyboard_config.zmk = Mock()
        self.keyboard_config.zmk.compatible_strings = ZmkCompatibleStrings()

        # Set up validation limits properly
        validation_limits = Mock()
        validation_limits.required_holdtap_bindings = 2
        validation_limits.max_macro_params = 2
        self.keyboard_config.zmk.validation_limits = validation_limits

        # Set up hold_tap_flavors as a proper list
        self.keyboard_config.zmk.hold_tap_flavors = [
            "tap-preferred",
            "hold-preferred",
            "balanced",
            "tap-unless-interrupted",
        ]

        # Set up patterns properly
        patterns = Mock()
        patterns.layer_define = "LAYER_{layer_name} {layer_index}"
        patterns.node_name_sanitize = r"[^A-Z0-9_]"
        self.keyboard_config.zmk.patterns = patterns


@pytest.fixture
def behavior_registry():
    """Create a mock behavior registry for testing."""
    registry = MockBehaviorRegistry()

    # Register common behaviors
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

    # Register a custom behavior that expects 2 parameters
    registry.register_behavior(
        SystemBehavior(
            code="&CAPSWord_v1_TKZ",
            name="Caps Word Helper",
            description="Tap for caps_word, hold for key press",
            expected_params=2,
            origin="layout",
            params=[],
        )
    )

    return registry


@pytest.fixture
def behavior_formatter(behavior_registry):
    """Create a behavior formatter with the mock registry."""
    return BehaviorFormatterImpl(behavior_registry)


@pytest.fixture
def zmk_generator(behavior_formatter):
    """Create a ZMK generator with the behavior formatter."""
    return ZmkFileContentGenerator(behavior_formatter)


@pytest.fixture
def mock_profile():
    """Create a mock keyboard profile."""
    return MockKeyboardProfile()


class TestMacroCompatibleStrings:
    """Test macro compatible strings and binding-cells based on parameters."""

    def test_macro_zero_params(self, zmk_generator, mock_profile):
        """Test macro with no parameters uses standard compatible string."""
        macro = MacroBehavior(
            name="&simple_macro_TKZ",
            description="Simple macro with no params",
            bindings=[
                LayoutBinding(value="&kp", params=[LayoutParam(value="A", params=[])])
            ],
            params=None,
        )

        result = zmk_generator.generate_macros_dtsi(mock_profile, [macro])

        assert 'compatible = "zmk,behavior-macro";' in result
        assert "#binding-cells = <0>;" in result

    def test_macro_one_param(self, zmk_generator, mock_profile):
        """Test macro with one parameter uses one-param compatible string."""
        macro = MacroBehavior(
            name="&AS_Shifted_v1_TKZ",
            description="AutoShift Helper",
            bindings=[
                LayoutBinding(value="&macro_press", params=[]),
                LayoutBinding(
                    value="&kp", params=[LayoutParam(value="LSHFT", params=[])]
                ),
                LayoutBinding(value="&macro_param_1to1", params=[]),
                LayoutBinding(value="&kp", params=[LayoutParam(value="N1", params=[])]),
            ],
            params=["code"],
        )

        result = zmk_generator.generate_macros_dtsi(mock_profile, [macro])

        assert 'compatible = "zmk,behavior-macro-one-param";' in result
        assert "#binding-cells = <1>;" in result

    def test_macro_two_params(self, zmk_generator, mock_profile):
        """Test macro with two parameters uses two-param compatible string."""
        macro = MacroBehavior(
            name="&complex_macro_TKZ",
            description="Complex macro with two params",
            bindings=[
                LayoutBinding(value="&macro_param_1to1", params=[]),
                LayoutBinding(value="&macro_param_2to1", params=[]),
            ],
            params=["param1", "param2"],
        )

        result = zmk_generator.generate_macros_dtsi(mock_profile, [macro])

        assert 'compatible = "zmk,behavior-macro-two-param";' in result
        assert "#binding-cells = <2>;" in result


class TestHoldTapBindingReferences:
    """Test hold-tap behaviors allow parameterless behavior references."""

    def test_hold_tap_with_parameterless_behaviors(self, zmk_generator, mock_profile):
        """Test hold-tap with behaviors that have no parameters in binding definition."""
        hold_tap = HoldTapBehavior(
            name="&space_v3_TKZ",
            description="Space layer access",
            bindings=["&mo", "&kp"],
            tappingTermMs=200,
            flavor="balanced",
            quickTapMs=150,
        )

        result = zmk_generator.generate_behaviors_dtsi(mock_profile, [hold_tap])

        # Should generate clean binding references without errors
        assert "bindings = <&mo>, <&kp>;" in result
        assert "&error" not in result

    def test_hold_tap_binding_context_switching(self, behavior_formatter):
        """Test that hold-tap binding context is properly switched."""
        # Test normal context (should validate parameters)
        behavior_formatter.set_hold_tap_binding_context(False)
        binding = LayoutBinding(value="&mo", params=[])
        result = behavior_formatter.format_binding(binding)
        assert "&error" in result  # Should error in normal context

        # Test hold-tap context (should allow bare reference)
        behavior_formatter.set_hold_tap_binding_context(True)
        result = behavior_formatter.format_binding(binding)
        assert result == "&mo"  # Should be bare reference


class TestComboLayersRendering:
    """Test combo layers render as numeric indices instead of define statements."""

    def test_combo_layers_as_indices(self, zmk_generator, mock_profile):
        """Test combo layers are rendered as numeric indices."""
        combo = ComboBehavior(
            name="combo_sticky_meh_rght_v1_TKZ",
            description="Sticky meh modifiers",
            binding=LayoutBinding(
                value="&sk", params=[LayoutParam(value="LA(LC(LSHFT))", params=[])]
            ),
            keyPositions=[73, 74],
            timeoutMs=50,
            layers=[0, 2],  # Should render as <0 2>
        )

        layer_names = ["LAYER_HRM_WINLINX", "LAYER_SOMETHING", "LAYER_AUTOSHIFT"]
        result = zmk_generator.generate_combos_dtsi(mock_profile, [combo], layer_names)

        assert "layers = <0 2>;" in result
        # Should NOT contain define statements
        assert "#define LAYER_HRM_WINLINX" not in result
        assert "#define LAYER_AUTOSHIFT" not in result

    def test_combo_with_invalid_layer_index(self, zmk_generator, mock_profile):
        """Test combo with invalid layer index is handled gracefully."""
        combo = ComboBehavior(
            name="combo_test",
            description="Test combo",
            binding=LayoutBinding(
                value="&kp", params=[LayoutParam(value="A", params=[])]
            ),
            keyPositions=[0, 1],
            layers=[0, 5],  # 5 is invalid (only 3 layers)
        )

        layer_names = ["LAYER_1", "LAYER_2", "LAYER_3"]
        result = zmk_generator.generate_combos_dtsi(mock_profile, [combo], layer_names)

        # Should only include valid layer index
        assert "layers = <0>;" in result


class TestMacroPlaceholderUsage:
    """Test missing parameters use MACRO_PLACEHOLDER instead of '0'."""

    def test_custom_behavior_missing_params_uses_placeholder(
        self, behavior_formatter, behavior_registry
    ):
        """Test custom behavior with missing params uses MACRO_PLACEHOLDER."""
        binding = LayoutBinding(
            value="&CAPSWord_v1_TKZ",
            params=[LayoutParam(value="LSHFT", params=[])],  # Only 1 param, expects 2
        )

        result = behavior_formatter.format_binding(binding)

        assert result == f"&CAPSWord_v1_TKZ LSHFT {MACRO_PLACEHOLDER}"
        assert "0" not in result  # Should not use generic "0"

    def test_macro_placeholder_constant(self):
        """Test that MACRO_PLACEHOLDER constant is properly defined."""
        assert MACRO_PLACEHOLDER == "MACRO_PLACEHOLDER"
        assert isinstance(MACRO_PLACEHOLDER, str)


class TestSystematicParameterValidation:
    """Test systematic parameter validation across all behavior formatters."""

    def test_layer_toggle_behavior_validation(self, behavior_formatter):
        """Test LayerToggleBehavior parameter validation in different contexts."""
        # Normal context - should require parameter
        behavior_formatter.set_hold_tap_binding_context(False)
        binding = LayoutBinding(value="&mo", params=[])
        result = behavior_formatter.format_binding(binding)
        assert "&error" in result

        # Hold-tap context - should allow bare reference
        behavior_formatter.set_hold_tap_binding_context(True)
        result = behavior_formatter.format_binding(binding)
        assert result == "&mo"

        # With parameter in any context
        binding_with_param = LayoutBinding(
            value="&mo", params=[LayoutParam(value="1", params=[])]
        )
        result = behavior_formatter.format_binding(binding_with_param)
        assert result == "&mo 1"

    def test_one_param_behavior_validation(self, behavior_formatter, behavior_registry):
        """Test OneParamBehavior parameter validation in different contexts."""
        # Register a one-param behavior
        behavior_registry.register_behavior(
            SystemBehavior(
                code="&sk",
                name="Sticky Key",
                description="Sticky key behavior",
                expected_params=1,
                origin="zmk_core",
                params=[],
            )
        )

        # Normal context - should require parameter
        behavior_formatter.set_hold_tap_binding_context(False)
        binding = LayoutBinding(value="&sk", params=[])
        result = behavior_formatter.format_binding(binding)
        assert "&error" in result

        # Hold-tap context - should allow bare reference
        behavior_formatter.set_hold_tap_binding_context(True)
        result = behavior_formatter.format_binding(binding)
        assert result == "&sk"


class TestZmkCompatibleStrings:
    """Test ZMK compatible strings are properly defined."""

    def test_zmk_compatible_strings_model(self):
        """Test that all required compatible strings are defined."""
        strings = ZmkCompatibleStrings()

        assert strings.macro == "zmk,behavior-macro"
        assert strings.macro_one_param == "zmk,behavior-macro-one-param"
        assert strings.macro_two_param == "zmk,behavior-macro-two-param"
        assert strings.hold_tap == "zmk,behavior-hold-tap"
        assert strings.combos == "zmk,combos"
        assert strings.keymap == "zmk,keymap"


class TestIntegrationScenarios:
    """Test integration scenarios covering multiple fixes."""

    def test_complete_layout_with_all_fixes(self, zmk_generator, mock_profile):
        """Test a complete layout that exercises all the fixes."""
        # Create a layout with macros, hold-taps, and combos
        layout_data = LayoutData(
            keyboard="test_keyboard",
            uuid="test-uuid",
            title="Test Layout with All Fixes",
            layer_names=["DEFAULT", "LAYER1", "LAYER2"],
            layers=[
                [  # Layer 0
                    LayoutBinding(
                        value="&CAPSWord_v1_TKZ",
                        params=[LayoutParam(value="LSHFT", params=[])],
                    )
                    for _ in range(80)
                ],
                [  # Layer 1
                    LayoutBinding(
                        value="&kp", params=[LayoutParam(value="A", params=[])]
                    )
                    for _ in range(80)
                ],
                [  # Layer 2
                    LayoutBinding(
                        value="&mo", params=[LayoutParam(value="0", params=[])]
                    )
                    for _ in range(80)
                ],
            ],
            macros=[
                MacroBehavior(
                    name="&test_macro",
                    description="Test macro with one param",
                    bindings=[
                        LayoutBinding(value="&macro_param_1to1", params=[]),
                        LayoutBinding(
                            value="&kp", params=[LayoutParam(value="A", params=[])]
                        ),
                    ],
                    params=["code"],
                )
            ],
            holdTaps=[  # Use the alias
                HoldTapBehavior(
                    name="&test_ht",
                    description="Test hold-tap",
                    bindings=["&mo", "&kp"],
                    tappingTermMs=200,
                    flavor="balanced",
                )
            ],
            combos=[
                ComboBehavior(
                    name="test_combo",
                    description="Test combo",
                    binding=LayoutBinding(
                        value="&kp", params=[LayoutParam(value="ESC", params=[])]
                    ),
                    keyPositions=[0, 1],
                    layers=[0, 2],
                )
            ],
        )

        # Test macro generation
        macro_result = zmk_generator.generate_macros_dtsi(
            mock_profile, layout_data.macros
        )
        assert 'compatible = "zmk,behavior-macro-one-param";' in macro_result
        assert "#binding-cells = <1>;" in macro_result

        # Test hold-tap generation
        ht_result = zmk_generator.generate_behaviors_dtsi(
            mock_profile, layout_data.hold_taps
        )
        assert "bindings = <&mo>, <&kp>;" in ht_result
        assert "&error" not in ht_result

        # Test combo generation
        combo_result = zmk_generator.generate_combos_dtsi(
            mock_profile, layout_data.combos, layout_data.layer_names
        )
        assert "layers = <0 2>;" in combo_result
        assert "#define" not in combo_result
