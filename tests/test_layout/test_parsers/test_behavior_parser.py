"""Tests for behavior parser functionality."""

import pytest

from glovebox.layout.models import (
    ComboBehavior,
    HoldTapBehavior,
    LayoutBinding,
    MacroBehavior,
)
from glovebox.layout.parsers.behavior_parser import (
    BehaviorParser,
    create_behavior_parser,
)


class TestBehaviorParser:
    """Test behavior parser functionality."""

    @pytest.fixture
    def parser(self):
        """Create behavior parser instance for testing."""
        return create_behavior_parser()

    @pytest.fixture
    def sample_behaviors_content(self):
        """Sample behaviors section content."""
        return """
        hm: homerow_mod {
            compatible = "zmk,behavior-hold-tap";
            flavor = "tap-preferred";
            tapping-term-ms = <150>;
            quick-tap-ms = <0>;
            bindings = <&kp>, <&kp>;
        };

        ht_shift: hold_tap_shift {
            compatible = "zmk,behavior-hold-tap";
            flavor = "balanced";
            tapping-term-ms = <200>;
            quick-tap-ms = <100>;
            require-prior-idle-ms = <125>;
            hold-trigger-on-release;
            bindings = <&kp>, <&kp>;
        };
        """

    @pytest.fixture
    def sample_macros_content(self):
        """Sample macros section content."""
        return """
        hello_macro: hello_macro {
            compatible = "zmk,behavior-macro";
            wait-ms = <30>;
            tap-ms = <40>;
            bindings = <&kp H &kp E &kp L &kp L &kp O>;
        };

        shift_hello: shift_hello {
            compatible = "zmk,behavior-macro";
            wait-ms = <50>;
            bindings = <&kp LSHIFT &macro_tap &kp H &kp I>;
        };
        """

    @pytest.fixture
    def sample_combos_content(self):
        """Sample combos section content."""
        return """
        combo_esc: combo_esc {
            compatible = "zmk,behavior-combo";
            key-positions = <0 1>;
            bindings = <&kp ESC>;
        };

        combo_enter: combo_enter {
            compatible = "zmk,behavior-combo";
            timeout-ms = <50>;
            key-positions = <10 11 12>;
            layers = <0 1>;
            bindings = <&kp ENTER>;
        };
        """

    def test_create_behavior_parser(self):
        """Test behavior parser factory function."""
        parser = create_behavior_parser()
        assert isinstance(parser, BehaviorParser)

    def test_parse_behaviors_section_empty(self, parser):
        """Test parsing empty behaviors section."""
        result = parser.parse_behaviors_section("")
        assert "hold_taps" in result
        assert "macros" in result
        assert "combos" in result
        assert len(result["hold_taps"]) == 0

    def test_parse_hold_tap_behaviors(self, parser, sample_behaviors_content):
        """Test parsing hold-tap behavior definitions."""
        full_content = f"behaviors {{ {sample_behaviors_content} }}"
        result = parser.parse_behaviors_section(full_content)

        hold_taps = result["hold_taps"]
        assert len(hold_taps) == 2

        # Check first hold-tap
        hm = hold_taps[0]
        assert isinstance(hm, HoldTapBehavior)
        assert hm.name == "hm"
        assert hm.flavor == "tap-preferred"
        assert hm.tapping_term_ms == 150
        assert hm.quick_tap_ms == 0
        assert len(hm.bindings) == 2
        assert "&kp" in hm.bindings

        # Check second hold-tap with more properties
        ht_shift = hold_taps[1]
        assert ht_shift.name == "ht_shift"
        assert ht_shift.flavor == "balanced"
        assert ht_shift.tapping_term_ms == 200
        assert ht_shift.quick_tap_ms == 100
        assert ht_shift.require_prior_idle_ms == 125
        assert ht_shift.hold_trigger_on_release is True

    def test_parse_macros_section(self, parser, sample_macros_content):
        """Test parsing macro definitions."""
        full_content = f"macros {{ {sample_macros_content} }}"
        macros = parser.parse_macros_section(full_content)

        assert len(macros) == 2

        # Check first macro
        hello_macro = macros[0]
        assert isinstance(hello_macro, MacroBehavior)
        assert hello_macro.name == "hello_macro"
        assert hello_macro.wait_ms == 30
        assert hello_macro.tap_ms == 40
        assert len(hello_macro.bindings) > 0

        # Check that bindings are LayoutBinding objects
        for binding in hello_macro.bindings:
            assert isinstance(binding, LayoutBinding)

        # Check second macro
        shift_hello = macros[1]
        assert shift_hello.name == "shift_hello"
        assert shift_hello.wait_ms == 50
        assert shift_hello.tap_ms is None  # Not specified

    def test_parse_combos_section(self, parser, sample_combos_content):
        """Test parsing combo definitions."""
        full_content = f"combos {{ {sample_combos_content} }}"
        combos = parser.parse_combos_section(full_content)

        assert len(combos) == 2

        # Check first combo
        combo_esc = combos[0]
        assert isinstance(combo_esc, ComboBehavior)
        assert combo_esc.name == "combo_esc"
        assert combo_esc.key_positions == [0, 1]
        assert isinstance(combo_esc.binding, LayoutBinding)
        assert combo_esc.binding.value == "&kp"
        assert combo_esc.binding.params[0].value == "ESC"

        # Check second combo with more properties
        combo_enter = combos[1]
        assert combo_enter.name == "combo_enter"
        assert combo_enter.timeout_ms == 50
        assert combo_enter.key_positions == [10, 11, 12]
        assert combo_enter.layers == [0, 1]
        assert combo_enter.binding.value == "&kp"
        assert combo_enter.binding.params[0].value == "ENTER"

    def test_extract_dt_properties(self, parser):
        """Test device tree property extraction."""
        content = """
        flavor = "tap-preferred";
        tapping-term-ms = <150>;
        quick-tap-ms = <0>;
        hold-trigger-on-release;
        bindings = <&kp>, <&kp>;
        """

        properties = parser._extract_dt_properties(content)

        assert "flavor" in properties
        assert properties["flavor"] == '"tap-preferred"'
        assert "tapping_term_ms" in properties
        assert properties["tapping_term_ms"] == "<150>"
        assert "quick_tap_ms" in properties
        assert properties["quick_tap_ms"] == "<0>"
        assert "hold_trigger_on_release" in properties
        assert properties["hold_trigger_on_release"] == ""  # Boolean property
        assert "bindings" in properties
        assert properties["bindings"] == "<&kp>, <&kp>"

    def test_parse_numeric_value(self, parser):
        """Test numeric value parsing."""
        assert parser._parse_numeric_value("<150>") == 150
        assert parser._parse_numeric_value("<0>") == 0
        assert parser._parse_numeric_value("< 200 >") == 200
        assert parser._parse_numeric_value("invalid") is None
        assert parser._parse_numeric_value("") is None

    def test_parse_array_property(self, parser):
        """Test array property parsing."""
        assert parser._parse_array_property("<0 1 2>") == [0, 1, 2]
        assert parser._parse_array_property("<10 11 12>") == [10, 11, 12]
        assert parser._parse_array_property("< 0 >") == [0]
        assert parser._parse_array_property("<>") == []
        assert parser._parse_array_property("invalid") == []

    def test_parse_bindings_property(self, parser):
        """Test bindings property parsing."""
        bindings = parser._parse_bindings_property("<&kp>, <&kp>")
        assert len(bindings) == 2
        assert "&kp" in bindings

        bindings = parser._parse_bindings_property("<&mo>, <&lt>")
        assert len(bindings) == 2
        assert "&mo" in bindings
        assert "&lt" in bindings

    def test_parse_macro_bindings(self, parser):
        """Test macro bindings parsing."""
        bindings = parser._parse_macro_bindings("<&kp H, &kp E, &kp L, &kp L, &kp O>")

        assert len(bindings) == 5
        for binding in bindings:
            assert isinstance(binding, LayoutBinding)
            assert binding.value == "&kp"
            assert len(binding.params) == 1

        # Check specific letter parameters
        letters = [b.params[0].value for b in bindings]
        assert letters == ["H", "E", "L", "L", "O"]

    def test_parse_single_binding(self, parser):
        """Test single binding parsing for combos."""
        binding = parser._parse_single_binding("<&kp ESC>")

        assert isinstance(binding, LayoutBinding)
        assert binding.value == "&kp"
        assert len(binding.params) == 1
        assert binding.params[0].value == "ESC"

        # Test complex binding
        binding = parser._parse_single_binding("<&mt LSHIFT A>")
        assert binding.value == "&mt"
        assert len(binding.params) == 2
        assert binding.params[0].value == "LSHIFT"
        assert binding.params[1].value == "A"

    def test_invalid_behavior_definitions(self, parser):
        """Test handling of invalid behavior definitions."""
        invalid_content = """
        invalid_behavior: invalid {
            // Missing compatible property
            tapping-term-ms = <150>;
        };

        missing_bindings: missing {
            compatible = "zmk,behavior-hold-tap";
            // Missing required bindings property
        };
        """

        full_content = f"behaviors {{ {invalid_content} }}"
        result = parser.parse_behaviors_section(full_content)

        # Should handle gracefully and return empty list
        assert len(result["hold_taps"]) == 0

    def test_malformed_properties(self, parser):
        """Test handling of malformed device tree properties."""
        malformed_content = """
        flavor "missing equals"
        tapping-term-ms = ;
        = <150>;
        bindings = <&invalid>;
        """

        properties = parser._extract_dt_properties(malformed_content)

        # Should extract what it can and ignore malformed properties
        assert "bindings" in properties

    def test_empty_sections_handling(self, parser):
        """Test handling of empty behavior sections."""
        empty_behaviors = "behaviors { }"
        result = parser.parse_behaviors_section(empty_behaviors)
        assert len(result["hold_taps"]) == 0

        empty_macros = "macros { }"
        macros = parser.parse_macros_section(empty_macros)
        assert len(macros) == 0

        empty_combos = "combos { }"
        combos = parser.parse_combos_section(empty_combos)
        assert len(combos) == 0

    def test_complex_macro_bindings(self, parser):
        """Test parsing complex macro bindings with special syntax."""
        complex_content = """
        complex_macro: complex {
            compatible = "zmk,behavior-macro";
            bindings = <&macro_press &kp LSHIFT, &macro_tap &kp H &kp I, &macro_release &kp LSHIFT>;
        };
        """

        full_content = f"macros {{ {complex_content} }}"
        macros = parser.parse_macros_section(full_content)

        assert len(macros) == 1
        macro = macros[0]
        assert macro.name == "complex"

        # Should have parsed multiple bindings despite complex syntax
        assert len(macro.bindings) > 0

    def test_macro_parameter_parsing(self, parser):
        """Test parsing macro parameters from #binding-cells property."""
        # Test macro with no parameters
        zero_param_content = """
        simple_macro: simple_macro {
            compatible = "zmk,behavior-macro";
            #binding-cells = <0>;
            bindings = <&kp A>;
        };
        """
        full_content = f"macros {{ {zero_param_content} }}"
        macros = parser.parse_macros_section(full_content)
        assert len(macros) == 1
        assert macros[0].name == "simple_macro"
        assert macros[0].params is None

        # Test macro with one parameter
        one_param_content = """
        coded_macro: coded_macro {
            compatible = "zmk,behavior-macro-one-param";
            #binding-cells = <1>;
            bindings = <&macro_param_1to1 &kp A>;
        };
        """
        full_content = f"macros {{ {one_param_content} }}"
        macros = parser.parse_macros_section(full_content)
        assert len(macros) == 1
        assert macros[0].name == "coded_macro"
        assert macros[0].params == ["code"]

        # Test macro with two parameters
        two_param_content = """
        complex_macro: complex_macro {
            compatible = "zmk,behavior-macro-two-param";
            #binding-cells = <2>;
            bindings = <&macro_param_1to1 &macro_param_2to1>;
        };
        """
        full_content = f"macros {{ {two_param_content} }}"
        macros = parser.parse_macros_section(full_content)
        assert len(macros) == 1
        assert macros[0].name == "complex_macro"
        assert macros[0].params == ["param1", "param2"]

        # Test macro without #binding-cells property (should default to None)
        no_binding_cells_content = """
        default_macro: default_macro {
            compatible = "zmk,behavior-macro";
            bindings = <&kp B>;
        };
        """
        full_content = f"macros {{ {no_binding_cells_content} }}"
        macros = parser.parse_macros_section(full_content)
        assert len(macros) == 1
        assert macros[0].name == "default_macro"
        assert macros[0].params is None

        # Test macro with invalid #binding-cells value
        invalid_binding_cells_content = """
        invalid_macro: invalid_macro {
            compatible = "zmk,behavior-macro";
            #binding-cells = <5>;
            bindings = <&kp C>;
        };
        """
        full_content = f"macros {{ {invalid_binding_cells_content} }}"
        macros = parser.parse_macros_section(full_content)
        assert len(macros) == 1
        assert macros[0].name == "invalid_macro"
        assert macros[0].params is None  # Should fall back to None for invalid values
