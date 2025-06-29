"""Tests for arithmetic expression parsing in preprocessor directives."""

import pytest

from glovebox.layout.parsers.lark_dt_parser import create_lark_dt_parser


class TestArithmeticExpressions:
    """Test arithmetic expression parsing in #define directives."""

    def test_simple_arithmetic_expression(self):
        """Test simple arithmetic expression like (6 - 3)."""
        content = """
        #define SIMPLE_CALC (6 - 3)
        / {
            node {
                property = "value";
            };
        };
        """

        parser = create_lark_dt_parser()
        roots = parser.parse(content)

        # Should parse successfully
        assert len(roots) >= 1

    def test_complex_arithmetic_expression(self):
        """Test complex arithmetic expression like ((6 - DIFFICULTY_LEVEL) * 100)."""
        content = """
        #define DIFFICULTY_LEVEL 3
        #define TAPPING_RESOLUTION ((6 - DIFFICULTY_LEVEL) * 100)
        #define ADJUSTED_TIME (TAPPING_RESOLUTION + 50)
        / {
            node {
                property = "value";
            };
        };
        """

        parser = create_lark_dt_parser()
        roots = parser.parse(content)

        # Should parse successfully
        assert len(roots) >= 1

    def test_arithmetic_with_nested_function_calls(self):
        """Test arithmetic combined with nested function calls."""
        content = """
        #define BASE_TIME 100
        #define MODIFIER_CALC (BASE_TIME * 2)
        #define NESTED_FUNC _C(LS(Z))
        #define COMPLEX_COMBO MODIFIER_CALC
        / {
            node {
                property = "value";
            };
        };
        """

        parser = create_lark_dt_parser()
        roots = parser.parse(content)

        # Should parse successfully
        assert len(roots) >= 1

    def test_arithmetic_operators_comprehensive(self):
        """Test all arithmetic operators."""
        content = """
        #define ADD_RESULT (10 + 5)
        #define SUB_RESULT (10 - 5)
        #define MUL_RESULT (10 * 5)
        #define DIV_RESULT (10 / 5)
        #define MOD_RESULT (10 % 3)
        #define SHIFT_LEFT (1 << 4)
        #define SHIFT_RIGHT (16 >> 2)
        / {
            node {
                property = "value";
            };
        };
        """

        parser = create_lark_dt_parser()
        roots = parser.parse(content)

        # Should parse successfully
        assert len(roots) >= 1

    def test_nested_parentheses_arithmetic(self):
        """Test deeply nested parentheses in arithmetic expressions."""
        content = """
        #define DEEPLY_NESTED (((6 - 2) * (3 + 1)) / 2)
        #define MIXED_CALC ((BASE_VALUE - OFFSET) * MULTIPLIER)
        / {
            node {
                property = "value";
            };
        };
        """

        parser = create_lark_dt_parser()
        roots = parser.parse(content)

        # Should parse successfully
        assert len(roots) >= 1

    def test_real_world_zmk_calculations(self):
        """Test real-world ZMK timing calculations."""
        content = """
        #define DIFFICULTY_LEVEL 3
        #define TAPPING_RESOLUTION ((6 - DIFFICULTY_LEVEL) * 100)
        #define HOMEY_HOLDING_TIME (TAPPING_RESOLUTION + 90)
        #define INDEX_HOLDING_TIME (TAPPING_RESOLUTION + 20)
        #define MIDDY_HOLDING_TIME (TAPPING_RESOLUTION + 60)
        #define PINKY_HOLDING_TIME (TAPPING_RESOLUTION + 110)
        
        / {
            behaviors {
                custom_ht: custom_hold_tap {
                    compatible = "zmk,behavior-hold-tap";
                    #binding-cells = <2>;
                    tapping-term-ms = <HOMEY_HOLDING_TIME>;
                    quick-tap-ms = <INDEX_HOLDING_TIME>;
                };
            };
        };
        """

        parser = create_lark_dt_parser()
        roots = parser.parse(content)

        # Should parse successfully
        assert len(roots) >= 1

        # Find the actual device tree content
        content_root = None
        for root in roots:
            if root.children:
                content_root = root
                break

        assert content_root is not None

        # Verify structure is correctly parsed
        behaviors = content_root.get_child("behaviors")
        assert behaviors is not None

        custom_ht = behaviors.get_child("custom_hold_tap")
        assert custom_ht is not None
        assert custom_ht.label == "custom_ht"

    def test_arithmetic_progression_from_original_failure(self):
        """Test that arithmetic expressions represent significant progress."""
        # This represents the type of arithmetic that was failing at line 1759
        content = """
        #if OPERATING_SYSTEM == 'M'
        #define _C      LG
        #define _REDO   _C(LS(Z))
        #define _HOME   _C(LEFT)
        #endif

        #ifndef TAPPING_RESOLUTION
        #define TAPPING_RESOLUTION ((6 - DIFFICULTY_LEVEL) * 100)
        #endif
        
        #define HOMEY_HOLDING_TIME (TAPPING_RESOLUTION + 90)
        #define INDEX_HOLDING_TIME (TAPPING_RESOLUTION + 20)
        
        / {
            behaviors {
                homey_behavior {
                    compatible = "zmk,behavior-hold-tap";
                    #binding-cells = <2>;
                    tapping-term-ms = <HOMEY_HOLDING_TIME>;
                    flavor = balanced;
                };
            };
        };
        """

        parser = create_lark_dt_parser()
        roots = parser.parse(content)

        # This content would have failed completely before arithmetic expression support
        # Now it should parse successfully, representing major progress
        assert len(roots) >= 1

        # Find the actual device tree content
        content_root = None
        for root in roots:
            if root.children:
                content_root = root
                break

        assert content_root is not None

        # Verify structure is correctly parsed
        behaviors = content_root.get_child("behaviors")
        assert behaviors is not None

        homey_behavior = behaviors.get_child("homey_behavior")
        assert homey_behavior is not None

        # Check that hash-prefixed property works
        binding_cells = homey_behavior.get_property("#binding-cells")
        assert binding_cells is not None

        # Check identifier values work
        flavor = homey_behavior.get_property("flavor")
        assert flavor is not None
        assert flavor.value.value == "balanced"
