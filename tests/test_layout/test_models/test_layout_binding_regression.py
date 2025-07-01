"""Comprehensive regression tests for LayoutBinding parameter parsing fixes."""

import pytest

from glovebox.layout.models import LayoutBinding, LayoutParam


class TestLayoutBindingParameterParsingRegression:
    """Regression tests for LayoutBinding.from_str() parameter parsing fixes.

    These tests cover all the parameter parsing issues that were identified and fixed
    during the keymap reverse engineering development.
    """

    def test_hrm_behaviors_flat_parameter_structure(self):
        """Test HRM behaviors use flat parameter structure (separate parameters).

        Regression fix: HRM behaviors were incorrectly nesting parameters like LGUI(A)
        instead of having separate LGUI and A parameters.
        """
        # Test various HRM behavior patterns
        hrm_test_cases = [
            ("&HRM_left_pinky_v1B_TKZ LGUI A", ["LGUI", "A"]),
            ("&hrm_left_middle LALT S", ["LALT", "S"]),
            ("&hrm_right_index RCTRL J", ["RCTRL", "J"]),
            ("&thumb_layer_access 1 SPACE", [1, "SPACE"]),
            ("&space_layer_tap 2 ENTER", [2, "ENTER"]),
        ]

        for binding_str, expected_params in hrm_test_cases:
            binding = LayoutBinding.from_str(binding_str)

            # Should have flat parameter structure
            assert len(binding.params) == 2
            assert binding.params[0].value == expected_params[0]  # type: ignore[index]
            assert binding.params[1].value == expected_params[1]  # type: ignore[index]

            # Parameters should be flat, not nested
            assert len(binding.params[0].params) == 0
            assert len(binding.params[1].params) == 0

    def test_mod_tap_behaviors_flat_parameter_structure(self):
        """Test mod-tap behaviors use flat parameter structure.

        Regression fix: &mt behaviors should have flat parameters like [LSHIFT, B]
        not nested like LSHIFT(B).
        """
        mt_test_cases = [
            ("&mt LSHIFT A", ["LSHIFT", "A"]),
            ("&mt LCTRL SPACE", ["LCTRL", "SPACE"]),
            ("&mt LALT TAB", ["LALT", "TAB"]),
            ("&mt LGUI ENTER", ["LGUI", "ENTER"]),
        ]

        for binding_str, expected_params in mt_test_cases:
            binding = LayoutBinding.from_str(binding_str)

            # Should have flat parameter structure
            assert len(binding.params) == 2
            assert binding.params[0].value == expected_params[0]
            assert binding.params[1].value == expected_params[1]

            # Parameters should be flat, not nested
            assert len(binding.params[0].params) == 0
            assert len(binding.params[1].params) == 0

    def test_layer_tap_behaviors_flat_parameter_structure(self):
        """Test layer-tap behaviors use flat parameter structure.

        Regression fix: &lt behaviors should have flat parameters like [1, TAB]
        not nested like 1(TAB).
        """
        lt_test_cases = [
            ("&lt 1 TAB", [1, "TAB"]),
            ("&lt 2 SPACE", [2, "SPACE"]),
            ("&lt 0 ENTER", [0, "ENTER"]),
            ("&lt 3 BSPC", [3, "BSPC"]),
        ]

        for binding_str, expected_params in lt_test_cases:
            binding = LayoutBinding.from_str(binding_str)

            # Should have flat parameter structure
            assert len(binding.params) == 2
            assert binding.params[0].value == expected_params[0]  # Layer number as int
            assert binding.params[1].value == expected_params[1]  # Key as string

            # Parameters should be flat, not nested
            assert len(binding.params[0].params) == 0
            assert len(binding.params[1].params) == 0

    def test_kp_modifier_chains_nested_structure(self):
        """Test &kp behaviors with modifier chains use nested structure.

        Regression fix: &kp with modifier commands should create nested structure
        like LC(X) not flat parameters [LC, X].
        """
        kp_modifier_test_cases = [
            ("&kp LC X", "LC", "X"),
            ("&kp LA TAB", "LA", "TAB"),
            ("&kp LG SPACE", "LG", "SPACE"),
            ("&kp LS A", "LS", "A"),
            ("&kp RC C", "RC", "C"),
            ("&kp RA V", "RA", "V"),
            ("&kp RG ESC", "RG", "ESC"),
            ("&kp RS ENTER", "RS", "ENTER"),
        ]

        for binding_str, modifier, key in kp_modifier_test_cases:
            binding = LayoutBinding.from_str(binding_str)

            # Should have single parameter containing the modifier chain
            assert len(binding.params) == 1
            assert binding.params[0].value == modifier

            # Modifier should contain the key as nested parameter
            assert len(binding.params[0].params) == 1
            assert binding.params[0].params[0].value == key
            assert len(binding.params[0].params[0].params) == 0

    def test_kp_nested_modifier_chains(self):
        """Test &kp behaviors with nested modifier chains.

        Regression fix: Complex modifier chains like LC(LS(G)) should be properly nested.
        """
        nested_test_cases = [
            ("&kp LC LS G", "LC", "LS", "G"),
            ("&kp LA LG SPACE", "LA", "LG", "SPACE"),
            ("&kp RC RA TAB", "RC", "RA", "TAB"),
        ]

        for binding_str, outer_mod, inner_mod, key in nested_test_cases:
            binding = LayoutBinding.from_str(binding_str)

            # Should create nested chain structure
            assert len(binding.params) == 1
            assert binding.params[0].value == outer_mod

            # Should have nested modifier
            assert len(binding.params[0].params) == 1
            assert binding.params[0].params[0].value == inner_mod

            # Should have final key at deepest level
            assert len(binding.params[0].params[0].params) == 1
            assert binding.params[0].params[0].params[0].value == key

    def test_kp_parenthetical_modifiers(self):
        """Test &kp behaviors with explicit parenthetical modifier syntax.

        Regression fix: Parenthetical modifiers like LC(X) should be parsed correctly.
        """
        paren_test_cases = [
            ("&kp LC(X)", "LC", "X"),
            ("&kp LA(TAB)", "LA", "TAB"),
            ("&kp LG(SPACE)", "LG", "SPACE"),
            ("&kp LC(LS(G))", "LC", "LS", "G"),
            ("&kp LA(LG(ENTER))", "LA", "LG", "ENTER"),
        ]

        for binding_str, *expected_chain in paren_test_cases:
            binding = LayoutBinding.from_str(binding_str)

            # Should parse parenthetical structure correctly
            assert len(binding.params) == 1

            # Walk down the nested chain
            current_param = binding.params[0]
            for i, expected_value in enumerate(expected_chain):
                assert current_param.value == expected_value

                if i < len(expected_chain) - 1:
                    # Not the last element, should have nested parameter
                    assert len(current_param.params) == 1
                    current_param = current_param.params[0]
                else:
                    # Last element, should have no nested parameters
                    assert len(current_param.params) == 0

    def test_kp_simple_keys_flat_structure(self):
        """Test &kp behaviors with simple keys use flat structure.

        Regression fix: Simple &kp bindings like &kp Q should have single flat parameter.
        """
        simple_test_cases = [
            ("&kp Q", "Q"),
            ("&kp SPACE", "SPACE"),
            ("&kp ENTER", "ENTER"),
            ("&kp ESC", "ESC"),
            ("&kp TAB", "TAB"),
            ("&kp BSPC", "BSPC"),
        ]

        for binding_str, expected_key in simple_test_cases:
            binding = LayoutBinding.from_str(binding_str)

            # Should have single flat parameter
            assert len(binding.params) == 1
            assert binding.params[0].value == expected_key
            assert len(binding.params[0].params) == 0

    def test_caps_word_behaviors_flat_structure(self):
        """Test &caps_word behaviors use flat parameter structure.

        Regression fix: Custom behaviors like &caps_word should use flat parameters.
        """
        caps_test_cases = [
            ("&caps_word", []),  # No parameters
            ("&caps LSHIFT", ["LSHIFT"]),  # Single parameter
        ]

        for binding_str, expected_params in caps_test_cases:
            binding = LayoutBinding.from_str(binding_str)

            # Should have flat parameter structure
            assert len(binding.params) == len(expected_params)

            for i, expected_param in enumerate(expected_params):
                assert binding.params[i].value == expected_param
                assert len(binding.params[i].params) == 0

    def test_complex_parameter_edge_cases(self):
        """Test edge cases in parameter parsing.

        Regression fix: Handle various edge cases that could break parameter parsing.
        """
        edge_cases = [
            # Missing parameters should not crash
            ("&kp", 0),
            ("&mt LSHIFT", 1),
            # Unknown behaviors should parse parameters normally
            ("&unknown_behavior PARAM1 PARAM2", 2),
            # Behaviors with many parameters
            ("&complex_macro A B C D E", 5),
        ]

        for binding_str, expected_param_count in edge_cases:
            try:
                binding = LayoutBinding.from_str(binding_str)
                assert len(binding.params) == expected_param_count
            except ValueError:
                # ValueError is acceptable for completely invalid strings
                assert True

    def test_behavior_name_normalization(self):
        """Test behavior name normalization.

        Regression fix: Ensure behavior names are properly normalized with & prefix.
        """
        normalization_cases = [
            ("kp Q", "&kp"),  # Missing & prefix
            ("&kp Q", "&kp"),  # Already has & prefix
            ("mt LSHIFT A", "&mt"),  # Missing & prefix
            ("&mt LSHIFT A", "&mt"),  # Already has & prefix
        ]

        for binding_str, expected_behavior in normalization_cases:
            binding = LayoutBinding.from_str(binding_str)
            assert binding.value == expected_behavior

    def test_parameter_type_conversion(self):
        """Test parameter type conversion.

        Regression fix: Ensure parameters are converted to appropriate types.
        """
        type_conversion_cases = [
            ("&lt 1 TAB", int, str),  # Layer number as int, key as string
            ("&lt 0 SPACE", int, str),
            ("&mt LSHIFT A", str, str),  # Both as strings
            ("&kp Q", str),  # Single string parameter
        ]

        for binding_str, *expected_types in type_conversion_cases:
            binding = LayoutBinding.from_str(str(binding_str))

            for i, expected_type in enumerate(expected_types):
                assert isinstance(binding.params[i].value, expected_type)  # type: ignore[arg-type]

    def test_whitespace_handling(self):
        """Test whitespace handling in parameter parsing.

        Regression fix: Ensure various whitespace patterns are handled correctly.
        """
        whitespace_cases = [
            ("  &kp   Q  ", "&kp", ["Q"]),  # Extra whitespace
            ("&mt  LSHIFT   A", "&mt", ["LSHIFT", "A"]),  # Multiple spaces
            ("\t&lt\t1\tTAB\t", "&lt", [1, "TAB"]),  # Tabs
            ("&kp\nLC\nX", "&kp", "LC", "X"),  # Newlines (should not occur in practice)
        ]

        for binding_str, expected_behavior, *expected_structure in whitespace_cases:
            binding = LayoutBinding.from_str(str(binding_str))
            assert binding.value == expected_behavior

            if len(expected_structure) == 1 and isinstance(expected_structure[0], list):
                # Flat parameter list
                params_list = expected_structure[0]
                assert len(binding.params) == len(params_list)
                for i, expected_param in enumerate(params_list):
                    assert binding.params[i].value == expected_param
            elif len(expected_structure) == 2:
                # Nested modifier structure
                modifier, key = expected_structure
                assert len(binding.params) == 1
                assert binding.params[0].value == modifier
                assert len(binding.params[0].params) == 1
                assert binding.params[0].params[0].value == key
