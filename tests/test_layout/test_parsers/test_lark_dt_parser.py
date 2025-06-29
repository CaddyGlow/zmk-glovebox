"""Tests for Lark-based device tree parser with enhanced grammar support."""

import pytest

from glovebox.layout.parsers.ast_nodes import (
    DTConditional,
    DTNode,
    DTValue,
    DTValueType,
)
from glovebox.layout.parsers.lark_dt_parser import LarkDTParser, create_lark_dt_parser


class TestBasicLarkParsing:
    """Test basic Lark device tree parsing functionality."""

    def test_create_parser(self):
        """Test creating a Lark parser instance."""
        parser = create_lark_dt_parser()
        assert parser is not None
        assert isinstance(parser, LarkDTParser)

    def test_parse_simple_node(self):
        """Test parsing a simple device tree node."""
        content = """
        / {
            test_node {
                property = "value";
            };
        };
        """

        parser = create_lark_dt_parser()
        roots = parser.parse(content)

        assert len(roots) == 1
        root = roots[0]
        assert isinstance(root, DTNode)

        # Check that test_node is a child
        test_node = root.get_child("test_node")
        assert test_node is not None

        # Check property
        prop = test_node.get_property("property")
        assert prop is not None
        assert prop.value.value == "value"

    def test_parse_array_values(self):
        """Test parsing array values."""
        content = """
        / {
            node {
                positions = <0 1 2 3>;
                bindings = <&kp Q>, <&kp W>;
            };
        };
        """

        parser = create_lark_dt_parser()
        roots = parser.parse(content)

        root = roots[0]
        node = root.get_child("node")

        # Test numeric array
        positions = node.get_property("positions")
        assert positions.value.type == DTValueType.ARRAY
        assert positions.value.value == ["0", "1", "2", "3"]

        # Test reference array
        bindings = node.get_property("bindings")
        assert bindings.value.type == DTValueType.ARRAY
        assert len(bindings.value.value) == 2


class TestEnhancedPreprocessorDirectives:
    """Test enhanced preprocessor directive parsing."""

    def _find_conditionals_root(self, roots: list[DTNode]) -> DTNode | None:
        """Helper to find root node containing conditionals."""
        for root in roots:
            if root.conditionals:
                return root
        return None

    def _find_content_root(self, roots: list[DTNode]) -> DTNode | None:
        """Helper to find root node containing actual content."""
        for root in roots:
            if root.children or root.properties:
                return root
        return None

    def test_basic_preprocessor_parsing(self):
        """Test basic preprocessor directive parsing."""
        content = """
        #if defined(CONFIG_FEATURE)
        / {
            node {
                property = "value";
            };
        };
        #endif
        """

        parser = create_lark_dt_parser()
        roots = parser.parse(content)

        # Should parse successfully
        assert len(roots) >= 1

    def test_logical_operators_in_preprocessor(self):
        """Test logical operators in preprocessor expressions."""
        content = """
        #if defined(RED) || defined(GREEN)
        / {
            node {
                property = "value";
            };
        };
        #endif
        """

        parser = create_lark_dt_parser()
        roots = parser.parse(content)

        # Should parse successfully
        assert len(roots) >= 1

    def test_hash_prefixed_properties(self):
        """Test properties with hash prefixes like #binding-cells."""
        content = """
        / {
            behavior {
                #binding-cells = <2>;
                #foo-bar = <1>;
            };
        };
        """

        parser = create_lark_dt_parser()
        roots = parser.parse(content)

        assert len(roots) == 1
        root = roots[0]
        behavior = root.get_child("behavior")

        # Check hash-prefixed properties
        binding_cells = behavior.get_property("#binding-cells")
        assert binding_cells is not None
        assert binding_cells.value.type == DTValueType.ARRAY
        assert binding_cells.value.value == ["2"]

        foo_bar = behavior.get_property("#foo-bar")
        assert foo_bar is not None
        assert foo_bar.value.value == ["1"]

    def test_define_with_references(self):
        """Test #define directives with reference tokens."""
        content = """
        #define RED &ug RED_RGB
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

    def test_builtin_functions_in_preprocessor(self):
        """Test builtin functions like __has_include() in preprocessor directives."""
        content = """
        #if __has_include(<dt-bindings/zmk/rgb_colors.h>)
        / {
            node {
                property = "rgb_enabled";
            };
        };
        #endif
        """

        parser = create_lark_dt_parser()
        roots = parser.parse(content)

        # Should parse successfully
        assert len(roots) >= 1


class TestLineContinuationHandling:
    """Test line continuation handling in preprocessor directives."""

    def test_simple_line_continuation(self):
        """Test simple line continuation with backslash."""
        content = """
        #if defined(RED) || defined(RED_RGB) || \\
            defined(BLUE) || defined(BLUE_RGB)
        / {
            node {
                property = "multi_color";
            };
        };
        #endif
        """

        parser = create_lark_dt_parser()
        roots = parser.parse(content)

        # Should parse successfully with line continuations processed
        assert len(roots) >= 1

    def test_define_with_line_continuation(self):
        """Test #define directive with line continuation."""
        content = """
        #define LONG_MACRO_NAME \\
            &some_long_behavior_reference
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


class TestIncludeStatements:
    """Test include statement parsing."""

    def test_quoted_include(self):
        """Test quoted include statements."""
        content = """
        #include "behaviors.dtsi"
        #include "dt-bindings/zmk/keys.h"
        / {
            node {
                property = "value";
            };
        };
        """

        parser = create_lark_dt_parser()
        roots = parser.parse(content)

        # Should parse successfully with includes
        assert len(roots) >= 1

    def test_angle_bracket_include(self):
        """Test angle bracket include statements."""
        content = """
        #include <dt-bindings/zmk/keys.h>
        #include <dt-bindings/zmk/bt.h>
        / {
            node {
                property = "value";
            };
        };
        """

        parser = create_lark_dt_parser()
        roots = parser.parse(content)

        # Should parse successfully with includes
        assert len(roots) >= 1


class TestIdentifierValues:
    """Test identifier values in properties."""

    def test_identifier_property_values(self):
        """Test identifier values like LEFT_PINKY_HOLDING_TYPE."""
        content = """
        / {
            behavior {
                flavor = tap_preferred;
                type = LEFT_PINKY_HOLDING_TYPE;
                mode = CUSTOM_MODE_VALUE;
            };
        };
        """

        parser = create_lark_dt_parser()
        roots = parser.parse(content)

        assert len(roots) == 1
        root = roots[0]
        behavior = root.get_child("behavior")

        # Check identifier values
        flavor = behavior.get_property("flavor")
        assert flavor is not None
        assert flavor.value.value == "tap_preferred"

        type_prop = behavior.get_property("type")
        assert type_prop is not None
        assert type_prop.value.value == "LEFT_PINKY_HOLDING_TYPE"

        mode = behavior.get_property("mode")
        assert mode is not None
        assert mode.value.value == "CUSTOM_MODE_VALUE"


class TestComplexRealWorldExamples:
    """Test complex real-world examples from ZMK keymap files."""

    def test_simple_color_definitions(self):
        """Test simplified color definition pattern."""
        content = """
        #define RED &ug RED_RGB
        / {
            behaviors {
                custom_behavior {
                    compatible = "zmk,behavior-hold-tap";
                    #binding-cells = <2>;
                };
            };
        };
        """

        parser = create_lark_dt_parser()
        roots = parser.parse(content)

        # Should parse successfully
        assert len(roots) >= 1

        # Should find the behavior in one of the roots
        found_behavior = False
        for root in roots:
            behaviors = root.get_child("behaviors")
            if behaviors:
                custom_behavior = behaviors.get_child("custom_behavior")
                if custom_behavior:
                    found_behavior = True
                    break

        assert found_behavior

    def test_nested_function_calls(self):
        """Test nested function calls in array values."""
        content = """
        / {
            macro {
                bindings = <&macro_wait_time 500>,
                          <&macro_tap &kp H &kp E &kp L>,
                          <&macro_pause_for_release>,
                          <&kp L &kp O>;
            };
        };
        """

        parser = create_lark_dt_parser()
        roots = parser.parse(content)

        # Should parse successfully
        assert len(roots) == 1
        root = roots[0]
        macro = root.get_child("macro")

        bindings = macro.get_property("bindings")
        assert bindings is not None
        assert bindings.value.type == DTValueType.ARRAY
        # Should have multiple binding entries
        assert len(bindings.value.value) > 1


class TestErrorHandling:
    """Test error handling and safe parsing."""

    def test_parse_safe_basic(self):
        """Test safe parsing with valid content."""
        content = """
        / {
            node {
                property = "value";
            };
        };
        """

        parser = create_lark_dt_parser()
        roots, errors = parser.parse_safe(content)

        assert len(roots) == 1
        assert len(errors) == 0

    def test_parse_safe_with_syntax_error(self):
        """Test safe parsing with syntax errors."""
        content = """
        / {
            node {
                property = invalid_syntax_here
            };
        """  # Missing closing brace

        parser = create_lark_dt_parser()
        roots, errors = parser.parse_safe(content)

        # Should capture errors
        assert len(errors) > 0


class TestRegressionPrevention:
    """Test cases to prevent regression of previously working functionality."""

    def test_basic_device_tree_still_works(self):
        """Ensure basic device tree parsing still works after grammar enhancements."""
        content = """
        / {
            compatible = "test,device";
            
            behaviors {
                ht: hold_tap {
                    compatible = "zmk,behavior-hold-tap";
                    label = "HOLD_TAP";
                    #binding-cells = <2>;
                    tapping-term-ms = <150>;
                    quick-tap-ms = <0>;
                    flavor = "tap-preferred";
                    bindings = <&kp>, <&kp>;
                };
            };
            
            keymap {
                compatible = "zmk,keymap";
                
                default_layer {
                    bindings = <
                        &kp Q    &kp W    &kp E
                        &ht LCTRL A   &kp S    &kp D
                    >;
                };
            };
        };
        """

        parser = create_lark_dt_parser()
        roots = parser.parse(content)

        assert len(roots) == 1
        root = roots[0]

        # Check basic structure
        assert root.get_property("compatible") is not None
        assert root.get_child("behaviors") is not None
        assert root.get_child("keymap") is not None

        # Check behavior extraction
        behaviors = root.get_child("behaviors")
        hold_tap = behaviors.get_child("hold_tap")
        assert hold_tap is not None
        assert hold_tap.label == "ht"

        # Check keymap structure
        keymap = root.get_child("keymap")
        layer = keymap.get_child("default_layer")
        assert layer is not None

        bindings = layer.get_property("bindings")
        assert bindings is not None
        assert bindings.value.type == DTValueType.ARRAY
