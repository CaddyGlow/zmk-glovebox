"""Test define resolution in keymap parsing."""

import pytest

from glovebox.layout.models import LayoutBinding, LayoutData
from glovebox.layout.parsers.ast_behavior_converter import ASTBehaviorConverter
from glovebox.layout.parsers.keymap_parser import ZmkKeymapParser
from glovebox.layout.parsers.keymap_processors import FullKeymapProcessor
from glovebox.layout.parsers.parsing_models import ParsingContext


class TestDefineResolution:
    """Test preprocessor define resolution in parsers."""

    def test_ast_behavior_converter_resolve_token(self):
        """Test basic token resolution."""
        defines = {"LAYER_Base": "0", "LAYER_Lower": "1", "MY_CUSTOM": "42"}
        converter = ASTBehaviorConverter(defines)

        # Test define resolution
        assert converter._resolve_token("LAYER_Base") == "0"
        assert converter._resolve_token("LAYER_Lower") == "1"
        assert converter._resolve_token("MY_CUSTOM") == "42"

        # Test non-define tokens pass through
        assert converter._resolve_token("SPACE") == "SPACE"
        assert converter._resolve_token("123") == "123"

    def test_ast_behavior_converter_resolve_binding_string(self):
        """Test binding string resolution."""
        defines = {"LAYER_Base": "0", "LAYER_Lower": "1", "LAYER_Magic": "2"}
        converter = ASTBehaviorConverter(defines)

        # Test layer behavior resolution
        assert converter._resolve_binding_string("&mo LAYER_Lower") == "&mo 1"
        assert converter._resolve_binding_string("&lt LAYER_Base SPACE") == "&lt 0 SPACE"
        assert converter._resolve_binding_string("&to LAYER_Magic") == "&to 2"
        assert converter._resolve_binding_string("&tog LAYER_Lower") == "&tog 1"

        # Test that behavior references are not resolved
        assert converter._resolve_binding_string("&kp A") == "&kp A"
        assert converter._resolve_binding_string("&none") == "&none"

        # Test complex cases
        assert (
            converter._resolve_binding_string("&lt LAYER_Lower LC(SPACE)")
            == "&lt 1 LC(SPACE)"
        )

    def test_keymap_parser_resolve_binding_string(self):
        """Test keymap parser binding resolution."""
        parser = ZmkKeymapParser()
        parser.defines = {"LAYER_Gaming": "1", "THUMB_KEY": "53"}

        # Test resolution
        assert parser._resolve_binding_string("&mo LAYER_Gaming") == "&mo 1"
        assert parser._resolve_binding_string("&combo_pos THUMB_KEY") == "&combo_pos 53"

        # Test multiple tokens
        assert (
            parser._resolve_binding_string("&lt LAYER_Gaming THUMB_KEY")
            == "&lt 1 53"
        )

    def test_full_processor_extracts_defines(self):
        """Test that FullKeymapProcessor extracts defines from AST."""
        keymap_content = """
#define LAYER_Base 0
#define LAYER_Lower 1
#define LAYER_Magic 2
#define MY_TIMEOUT 200

/ {
    keymap {
        compatible = "zmk,keymap";
        
        layer_Base {
            bindings = <&mo LAYER_Lower &trans>;
        };
    };
};
"""
        context = ParsingContext(
            keymap_content=keymap_content,
            keyboard_name="test_keyboard",
        )

        processor = FullKeymapProcessor()
        layout_data = processor.process(context)

        # Check defines were extracted and stored in context
        assert hasattr(context, 'defines'), "Context should have defines attribute"
        
        # Also check if layout_data was successfully created
        assert layout_data is not None, "Layout data should be created"
        
        assert context.defines == {
            "LAYER_Base": "0",  
            "LAYER_Lower": "1",
            "LAYER_Magic": "2",
            "MY_TIMEOUT": "200",
        }

    def test_define_resolution_in_parsed_layout(self):
        """Test end-to-end define resolution in parsed layout."""
        keymap_content = """
#define LAYER_Base 0
#define LAYER_Gaming 1
#define LAYER_Symbols 2

/ {
    behaviors {
        lower: lower {
            compatible = "zmk,behavior-tap-dance";
            #binding-cells = <0>;
            bindings = <&mo LAYER_Gaming>, <&to LAYER_Gaming>;
        };
    };
    
    keymap {
        compatible = "zmk,keymap";
        
        layer_Base {
            bindings = <
                &kp Q &mo LAYER_Gaming &lt LAYER_Symbols SPACE
                &to LAYER_Base &tog LAYER_Gaming &trans
            >;
        };
        
        layer_Gaming {
            bindings = <
                &trans &trans &trans
                &to LAYER_Base &trans &trans
            >;
        };
        
        layer_Symbols {
            bindings = <
                &trans &trans &trans
                &trans &trans &trans
            >;
        };
    };
};
"""
        context = ParsingContext(
            keymap_content=keymap_content,
            keyboard_name="test_keyboard",
        )

        processor = FullKeymapProcessor()
        layout_data = processor.process(context)

        assert layout_data is not None
        assert len(layout_data.layers) == 3

        # Check that layer references were resolved to numbers
        base_layer = layout_data.layers[0]

        # Find the bindings with layer references
        mo_binding = None
        lt_binding = None
        to_binding = None
        tog_binding = None

        for binding in base_layer:
            if binding.value == "&mo":
                mo_binding = binding
            elif binding.value == "&lt":
                lt_binding = binding
            elif binding.value == "&to":
                to_binding = binding
            elif binding.value == "&tog":
                tog_binding = binding

        # Verify layer parameters were resolved from defines
        assert mo_binding is not None
        assert len(mo_binding.params) == 1
        assert mo_binding.params[0].value == 1  # LAYER_Gaming -> 1

        assert lt_binding is not None
        assert len(lt_binding.params) == 2
        assert lt_binding.params[0].value == 2  # LAYER_Symbols -> 2
        assert lt_binding.params[1].value == "SPACE"

        assert to_binding is not None
        assert len(to_binding.params) == 1
        assert to_binding.params[0].value == 0  # LAYER_Base -> 0

        assert tog_binding is not None
        assert len(tog_binding.params) == 1
        assert tog_binding.params[0].value == 1  # LAYER_Gaming -> 1

    def test_behavior_with_defines_in_behaviors_section(self):
        """Test that defines are resolved in custom behavior definitions."""
        keymap_content = """
#define LAYER_Lower 1

/ {
    behaviors {
        lower: lower {
            compatible = "zmk,behavior-tap-dance";
            #binding-cells = <0>;
            bindings = <&mo LAYER_Lower>, <&to LAYER_Lower>;
        };
    };
};
"""
        context = ParsingContext(
            keymap_content=keymap_content,
            keyboard_name="test_keyboard",
        )

        processor = FullKeymapProcessor()
        layout_data = processor.process(context)

        assert layout_data is not None
        # Note: tap-dance behaviors are not currently extracted, but the test
        # verifies that the parsing doesn't fail with defines

    def test_defines_without_values(self):
        """Test handling of defines without values."""
        defines = {"ENABLE_FEATURE": "", "LAYER_Base": "0"}
        converter = ASTBehaviorConverter(defines)

        # Empty defines should resolve to empty string
        assert converter._resolve_token("ENABLE_FEATURE") == ""
        assert converter._resolve_binding_string("&custom ENABLE_FEATURE") == "&custom "

    def test_nested_function_with_defines(self):
        """Test resolution in nested function calls."""
        defines = {"LAYER_Nav": "1"}
        converter = ASTBehaviorConverter(defines)

        # Test that defines inside function calls are resolved
        result = converter._resolve_binding_string("&mt LC(LAYER_Nav) A")
        assert result == "&mt LC(1) A"

        # Test multiple levels
        result = converter._resolve_binding_string("&custom LA(LC(LAYER_Nav))")
        assert result == "&custom LA(LC(1))"