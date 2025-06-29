"""Integration tests for enhanced grammar functionality with real-world examples."""

import pytest

from glovebox.layout.parsers.lark_dt_parser import create_lark_dt_parser


class TestEnhancedGrammarIntegration:
    """Test the enhanced grammar with comprehensive real-world patterns."""

    def test_complex_preprocessor_suite(self):
        """Test comprehensive suite of enhanced preprocessor features."""
        content = """
        #if __has_include(<dt-bindings/zmk/rgb_colors.h>)
        #include <dt-bindings/zmk/rgb_colors.h>

        #define RED_RGB  RGB_COLOR_HSB(0,100,50)
        #if defined(RED) || defined(RED_RGB) || \\
            defined(R)
        #error "Naming conflict: 3-letter color abbreviation already defined!"
        #endif
        #define RED &ug RED_RGB
        #endif

        #if OPERATING_SYSTEM == 'M'
        #define OS_SPECIFIC_KEY &kp LCMD
        #elif OPERATING_SYSTEM == 'L'
        #define OS_SPECIFIC_KEY &kp LCTRL
        #else
        #define OS_SPECIFIC_KEY &kp LWIN
        #endif

        / {
            behaviors {
                custom_behavior {
                    compatible = "zmk,behavior-hold-tap";
                    #binding-cells = <2>;
                    tapping-term-ms = <150>;
                    flavor = tap_preferred;
                };
            };

            keymap {
                layer {
                    bindings = <&kp Q &OS_SPECIFIC_KEY>;
                };
            };
        };
        """

        parser = create_lark_dt_parser()
        roots = parser.parse(content)

        # Should parse successfully - this represents the level of complexity
        # we successfully handle with our enhanced grammar
        assert len(roots) >= 1

        # Should find actual device tree content
        content_root = None
        for root in roots:
            if root.children:
                content_root = root
                break

        assert content_root is not None
        assert content_root.get_child("behaviors") is not None
        assert content_root.get_child("keymap") is not None

        # Check that hash-prefixed properties work
        behaviors = content_root.get_child("behaviors")
        custom_behavior = behaviors.get_child("custom_behavior")
        binding_cells = custom_behavior.get_property("#binding-cells")
        assert binding_cells is not None
        assert binding_cells.value.value == ["2"]

        # Check identifier values work
        flavor = custom_behavior.get_property("flavor")
        assert flavor is not None
        assert flavor.value.value == "tap_preferred"

    def test_line_continuation_comprehensive(self):
        """Test comprehensive line continuation handling."""
        content = """
        #if defined(COLOR_A) || defined(COLOR_B) || \\
            defined(COLOR_C) || defined(COLOR_D) || \\
            defined(COLOR_E)
        #define MULTI_COLOR_SUPPORT true
        #endif

        #define COMPLEX_MACRO_WITH_CONTINUATION \\
            &some_behavior_reference PARAM1 PARAM2

        / {
            node {
                property = "value";
            };
        };
        """

        parser = create_lark_dt_parser()
        roots = parser.parse(content)

        # Should successfully handle multiple line continuations
        assert len(roots) >= 1

    def test_include_statement_variations(self):
        """Test various include statement formats."""
        content = """
        #include <behaviors.dtsi>
        #include "custom_behaviors.dtsi"
        #include <dt-bindings/zmk/keys.h>
        #include <dt-bindings/zmk/bt.h>
        #include "local/path/file.h"

        / {
            node {
                property = "value";
            };
        };
        """

        parser = create_lark_dt_parser()
        roots = parser.parse(content)

        # Should handle mixed include formats
        assert len(roots) >= 1

    def test_complex_property_patterns(self):
        """Test complex property name and value patterns."""
        content = """
        / {
            behavior {
                #binding-cells = <2>;
                #foo-bar-baz = <1>;
                compatible = "zmk,behavior-hold-tap";
                flavor = hold_preferred;
                tapping-term-ms = <150>;
                property-with-dashes = <0>;
                UPPERCASE_PROPERTY = UPPERCASE_VALUE;
                mixed_Case_Property = mixed_Case_Value;
            };
        };
        """

        parser = create_lark_dt_parser()
        roots = parser.parse(content)

        assert len(roots) == 1
        root = roots[0]
        behavior = root.get_child("behavior")

        # All property types should be parsed correctly
        assert behavior.get_property("#binding-cells") is not None
        assert behavior.get_property("#foo-bar-baz") is not None
        assert behavior.get_property("compatible") is not None
        assert behavior.get_property("flavor") is not None
        assert behavior.get_property("tapping-term-ms") is not None
        assert behavior.get_property("property-with-dashes") is not None
        assert behavior.get_property("UPPERCASE_PROPERTY") is not None
        assert behavior.get_property("mixed_Case_Property") is not None

    def test_builtin_function_patterns(self):
        """Test various builtin function patterns in preprocessor directives."""
        content = """
        #if __has_include(<dt-bindings/zmk/rgb_colors.h>)
        #include <dt-bindings/zmk/rgb_colors.h>
        #endif

        #if __has_include("local_config.h")
        #include "local_config.h"
        #endif

        #if defined(FEATURE_A) && __has_include(<optional_feature.h>)
        #define FEATURE_A_ENABLED
        #endif

        / {
            node {
                property = "value";
            };
        };
        """

        parser = create_lark_dt_parser()
        roots = parser.parse(content)

        # Should handle various builtin function patterns
        assert len(roots) >= 1

    def test_character_literal_comparisons(self):
        """Test character literal comparisons in preprocessor expressions."""
        content = """
        #if OS_TYPE == 'M'
        #define OS_MODIFIER &kp LCMD
        #elif OS_TYPE == 'L'
        #define OS_MODIFIER &kp LCTRL
        #elif OS_TYPE == 'W'
        #define OS_MODIFIER &kp LWIN
        #else
        #define OS_MODIFIER &kp LALT
        #endif

        / {
            keymap {
                layer {
                    bindings = <&OS_MODIFIER>;
                };
            };
        };
        """

        parser = create_lark_dt_parser()
        roots = parser.parse(content)

        # Should handle character literal comparisons
        assert len(roots) >= 1

    def test_progress_vs_original_failure(self):
        """Test that we've made significant progress from the original parsing failures."""
        # This represents the type of complex content that was failing originally
        content = """
        #if defined(RED) || defined(RED_RGB) || \\
            defined(GREEN) || defined(BLUE)
        #error "Color conflict detected!"
        #endif

        #if __has_include(<dt-bindings/zmk/rgb_colors.h>)
        #include <dt-bindings/zmk/rgb_colors.h>
        #define RED &ug RED_RGB
        #endif

        #if OPERATING_SYSTEM == 'M'
        #define CMD_KEY &kp LCMD
        #else
        #define CMD_KEY &kp LCTRL
        #endif

        / {
            behaviors {
                custom_ht: custom_hold_tap {
                    compatible = "zmk,behavior-hold-tap";
                    #binding-cells = <2>;
                    flavor = balanced;
                    tapping-term-ms = <200>;
                    bindings = <&kp>, <&kp>;
                };
            };

            keymap {
                compatible = "zmk,keymap";

                default_layer {
                    bindings = <
                        &kp Q     &kp W     &kp E
                        &custom_ht LCTRL A  &kp S
                    >;
                };
            };
        };
        """

        parser = create_lark_dt_parser()
        roots = parser.parse(content)

        # This content would have failed completely before our enhancements
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

        custom_ht = behaviors.get_child("custom_hold_tap")
        assert custom_ht is not None
        assert custom_ht.label == "custom_ht"

        # Check hash-prefixed property works
        binding_cells = custom_ht.get_property("#binding-cells")
        assert binding_cells is not None

        # Check keymap structure
        keymap = content_root.get_child("keymap")
        assert keymap is not None

        layer = keymap.get_child("default_layer")
        assert layer is not None

        bindings = layer.get_property("bindings")
        assert bindings is not None
