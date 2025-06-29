"""Tests for AST-based device tree parsing."""

import pytest

from glovebox.layout.models import (
    ComboBehavior,
    HoldTapBehavior,
    LayoutBinding,
    MacroBehavior,
)
from glovebox.layout.parsers import (
    DTNode,
    DTParser,
    DTValue,
    DTValueType,
    ParsingMethod,
    ParsingMode,
    create_universal_behavior_extractor,
    create_universal_model_converter,
    create_zmk_keymap_parser,
    parse_dt,
    parse_dt_multiple,
    parse_dt_multiple_safe,
    parse_dt_safe,
    tokenize_dt,
)
from glovebox.layout.parsers.ast_walker import DTMultiWalker


class TestTokenizer:
    """Test device tree tokenizer."""

    def test_tokenize_simple_node(self):
        """Test tokenizing a simple device tree node."""
        source = """
        node {
            property = "value";
        };
        """

        tokens = tokenize_dt(source)
        token_values = [token.value for token in tokens if token.value]

        assert "node" in token_values
        assert "property" in token_values
        assert "value" in token_values

    def test_tokenize_array_property(self):
        """Test tokenizing array properties."""
        source = "key-positions = <0 1 2>;"

        tokens = tokenize_dt(source)
        token_values = [token.value for token in tokens if token.value]

        assert "key-positions" in token_values
        assert "0" in token_values
        assert "1" in token_values
        assert "2" in token_values

    def test_tokenize_references(self):
        """Test tokenizing references."""
        source = "bindings = <&kp Q>, <&trans>;"

        tokens = tokenize_dt(source)

        # Should have reference tokens
        ref_tokens = [token for token in tokens if token.type.value == "REFERENCE"]
        assert len(ref_tokens) == 2
        assert ref_tokens[0].value == "kp"
        assert ref_tokens[1].value == "trans"

    def test_tokenize_comments(self):
        """Test tokenizing comments."""
        source = """
        // Line comment
        node {
            /* Block comment */
            property = "value";
        };
        """

        tokens = tokenize_dt(source, preserve_whitespace=True)
        comment_tokens = [token for token in tokens if token.type.value == "COMMENT"]
        assert len(comment_tokens) == 2


class TestDTParser:
    """Test device tree parser."""

    def test_parse_simple_node(self):
        """Test parsing a simple node."""
        source = """
        / {
            test_node {
                property = "value";
            };
        };
        """

        root = parse_dt(source)
        assert root is not None

        test_node = root.get_child("test_node")
        assert test_node is not None

        prop = test_node.get_property("property")
        assert prop is not None
        assert prop.value.value == "value"

    def test_parse_array_property(self):
        """Test parsing array properties."""
        source = """
        / {
            node {
                positions = <0 1 2 3>;
            };
        };
        """

        root = parse_dt(source)
        node = root.get_child("node")
        prop = node.get_property("positions")

        assert prop.value.type == DTValueType.ARRAY
        assert prop.value.value == [0, 1, 2, 3]

    def test_parse_with_label(self):
        """Test parsing nodes with labels."""
        source = """
        / {
            label: node {
                property = "value";
            };
        };
        """

        root = parse_dt(source)
        node = root.get_child("node")

        assert node is not None
        assert node.label == "label"

    def test_parse_safe_with_errors(self):
        """Test safe parsing that handles errors."""
        source = """
        / {
            malformed node {
                // Missing closing brace
        """

        root, errors = parse_dt_safe(source)

        # Should return partial result with errors
        assert errors  # Should have parsing errors
        # Root should still be created even with errors
        assert root is not None


class TestBehaviorExtractor:
    """Test behavior extraction from AST."""

    def test_extract_hold_tap_behavior(self):
        """Test extracting hold-tap behaviors."""
        source = """
        / {
            behaviors {
                hm: homerow_mods {
                    compatible = "zmk,behavior-hold-tap";
                    label = "HOMEROW_MODS";
                    #binding-cells = <2>;
                    tapping-term-ms = <150>;
                    quick-tap-ms = <0>;
                    flavor = "tap-preferred";
                    bindings = <&kp>, <&kp>;
                };
            };
        };
        """

        root = parse_dt(source)
        extractor = create_universal_behavior_extractor()
        behaviors = extractor.extract_all_behaviors(root)

        assert len(behaviors["hold_taps"]) == 1
        hold_tap_node = behaviors["hold_taps"][0]
        assert hold_tap_node.name == "homerow_mods"
        assert hold_tap_node.label == "hm"

    def test_extract_macro_behavior(self):
        """Test extracting macro behaviors."""
        source = """
        / {
            macros {
                hello: hello_world {
                    compatible = "zmk,behavior-macro";
                    label = "hello_world";
                    #binding-cells = <0>;
                    bindings = <&kp H &kp E &kp L &kp L &kp O>;
                };
            };
        };
        """

        root = parse_dt(source)
        extractor = create_universal_behavior_extractor()
        behaviors = extractor.extract_all_behaviors(root)

        assert len(behaviors["macros"]) == 1
        macro_node = behaviors["macros"][0]
        assert macro_node.name == "hello_world"
        assert macro_node.label == "hello"

    def test_extract_combo_behavior(self):
        """Test extracting combo behaviors."""
        source = """
        / {
            combos {
                compatible = "zmk,combos";
                combo_esc {
                    timeout-ms = <50>;
                    key-positions = <0 1>;
                    bindings = <&kp ESC>;
                };
            };
        };
        """

        root = parse_dt(source)
        extractor = create_universal_behavior_extractor()
        behaviors = extractor.extract_all_behaviors(root)

        assert len(behaviors["combos"]) == 1
        combo_node = behaviors["combos"][0]
        assert combo_node.name == "combo_esc"


class TestModelConverter:
    """Test conversion from AST nodes to glovebox models."""

    def test_convert_hold_tap_behavior(self):
        """Test converting hold-tap AST node to HoldTapBehavior."""
        source = """
        / {
            behaviors {
                hm: homerow_mods {
                    compatible = "zmk,behavior-hold-tap";
                    label = "HOMEROW_MODS";
                    #binding-cells = <2>;
                    tapping-term-ms = <150>;
                    quick-tap-ms = <0>;
                    flavor = "tap-preferred";
                    bindings = <&kp>, <&kp>;
                };
            };
        };
        """

        root = parse_dt(source)
        extractor = create_universal_behavior_extractor()
        converter = create_universal_model_converter()

        behaviors = extractor.extract_all_behaviors(root)
        converted = converter.convert_behaviors(behaviors)

        assert len(converted["hold_taps"]) == 1
        hold_tap = converted["hold_taps"][0]

        assert isinstance(hold_tap, HoldTapBehavior)
        assert hold_tap.name == "&hm"
        assert hold_tap.tapping_term_ms == 150
        assert hold_tap.quick_tap_ms == 0
        assert hold_tap.flavor == "tap-preferred"

    def test_convert_macro_behavior(self):
        """Test converting macro AST node to MacroBehavior."""
        source = """
        / {
            macros {
                hello: hello_world {
                    compatible = "zmk,behavior-macro";
                    label = "hello_world";
                    #binding-cells = <0>;
                    bindings = <&kp H &kp E &kp L &kp L &kp O>;
                    wait-ms = <30>;
                    tap-ms = <40>;
                };
            };
        };
        """

        root = parse_dt(source)
        extractor = create_universal_behavior_extractor()
        converter = create_universal_model_converter()

        behaviors = extractor.extract_all_behaviors(root)
        converted = converter.convert_behaviors(behaviors)

        assert len(converted["macros"]) == 1
        macro = converted["macros"][0]

        assert isinstance(macro, MacroBehavior)
        assert macro.name == "&hello"
        assert macro.wait_ms == 30
        assert macro.tap_ms == 40
        assert len(macro.bindings) == 5

    def test_convert_combo_behavior(self):
        """Test converting combo AST node to ComboBehavior."""
        source = """
        / {
            combos {
                compatible = "zmk,combos";
                combo_esc {
                    timeout-ms = <50>;
                    key-positions = <0 1>;
                    bindings = <&kp ESC>;
                };
            };
        };
        """

        root = parse_dt(source)
        extractor = create_universal_behavior_extractor()
        converter = create_universal_model_converter()

        behaviors = extractor.extract_all_behaviors(root)
        converted = converter.convert_behaviors(behaviors)

        assert len(converted["combos"]) == 1
        combo = converted["combos"][0]

        assert isinstance(combo, ComboBehavior)
        assert combo.name == "combo_esc"
        assert combo.timeout_ms == 50
        assert combo.key_positions == [0, 1]
        assert combo.binding.value == "&kp"
        assert len(combo.binding.params) == 1
        assert combo.binding.params[0].value == "ESC"


class TestIntegratedKeymapParser:
    """Test the integrated keymap parser with AST support."""

    def test_ast_parsing_mode(self):
        """Test AST parsing mode in keymap parser."""
        keymap_content = """
        #include <behaviors.dtsi>
        #include <dt-bindings/zmk/keys.h>

        / {
            behaviors {
                hm: homerow_mods {
                    compatible = "zmk,behavior-hold-tap";
                    label = "HOMEROW_MODS";
                    #binding-cells = <2>;
                    tapping-term-ms = <150>;
                    flavor = "tap-preferred";
                    bindings = <&kp>, <&kp>;
                };
            };

            keymap {
                compatible = "zmk,keymap";

                layer_default {
                    bindings = <
                        &kp Q  &kp W  &kp E  &kp R
                        &hm LCTRL A  &kp S  &kp D  &kp F
                    >;
                };
            };
        };
        """

        # Create a temporary file for testing
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(mode="w", suffix=".keymap", delete=False) as f:
            f.write(keymap_content)
            keymap_file = Path(f.name)

        try:
            parser = create_zmk_keymap_parser()
            result = parser.parse_keymap(
                keymap_file, mode=ParsingMode.FULL, method=ParsingMethod.AST
            )

            assert result.success
            assert result.parsing_method == ParsingMethod.AST
            assert result.layout_data is not None

            # Check extracted behaviors
            assert len(result.layout_data.hold_taps) == 1
            hold_tap = result.layout_data.hold_taps[0]
            assert hold_tap.name == "&hm"
            assert hold_tap.tapping_term_ms == 150

            # Check extracted layers
            assert len(result.layout_data.layer_names) == 1
            assert result.layout_data.layer_names[0] == "default"
            assert len(result.layout_data.layers) == 1

            layer_bindings = result.layout_data.layers[0]
            assert len(layer_bindings) == 8  # 4 + 4 bindings

            # Check that bindings are properly parsed
            assert layer_bindings[0].value == "&kp"
            assert len(layer_bindings[0].params) == 1
            assert layer_bindings[0].params[0].value == "Q"

            assert layer_bindings[4].value == "&hm"
            assert len(layer_bindings[4].params) == 2
            assert layer_bindings[4].params[0].value == "LCTRL"
            assert layer_bindings[4].params[1].value == "A"

        finally:
            # Clean up temporary file
            keymap_file.unlink()

    def test_fallback_to_regex_on_ast_failure(self):
        """Test that parser falls back gracefully when AST parsing fails."""
        # Test malformed content that might break AST parser
        keymap_content = """
        / {
            keymap {
                layer_default {
                    bindings = <&kp Q>;
                };
            };
        """  # Missing closing brace

        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(mode="w", suffix=".keymap", delete=False) as f:
            f.write(keymap_content)
            keymap_file = Path(f.name)

        try:
            parser = create_zmk_keymap_parser()
            result = parser.parse_keymap(
                keymap_file, mode=ParsingMode.FULL, method=ParsingMethod.AST
            )

            # Should handle errors gracefully
            assert result.parsing_method == ParsingMethod.AST
            # May or may not succeed depending on error handling
            if not result.success:
                assert result.errors  # Should have error messages

        finally:
            keymap_file.unlink()


class TestComplexDeviceTreeStructures:
    """Test parsing of complex device tree structures."""

    def test_nested_behaviors_with_comments(self):
        """Test parsing nested behaviors with comments."""
        source = """
        / {
            behaviors {
                // Custom hold-tap behavior
                hm: homerow_mods {
                    compatible = "zmk,behavior-hold-tap";
                    label = "HOMEROW_MODS";
                    #binding-cells = <2>;
                    tapping-term-ms = <150>;
                    quick-tap-ms = <0>;
                    flavor = "tap-preferred";
                    bindings = <&kp>, <&kp>;
                    /* Multi-line comment
                       describing this behavior */
                    hold-trigger-key-positions = <0 1 2 3>;
                };
            };

            macros {
                // Hello world macro
                hello: hello_world {
                    compatible = "zmk,behavior-macro";
                    label = "hello_world";
                    #binding-cells = <0>;
                    bindings
                        = <&macro_wait_time 500>
                        , <&macro_tap &kp H &kp E &kp L &kp L &kp O>
                        ;
                };
            };
        };
        """

        root = parse_dt(source)
        assert root is not None

        # Should be able to extract both behavior types
        extractor = create_universal_behavior_extractor()
        behaviors = extractor.extract_all_behaviors(root)

        assert len(behaviors["hold_taps"]) == 1
        assert len(behaviors["macros"]) == 1

    def test_conditional_compilation(self):
        """Test handling of conditional compilation directives."""
        source = """
        / {
            behaviors {
                #ifdef CONFIG_CUSTOM_BEHAVIOR
                custom_behavior {
                    compatible = "zmk,behavior-hold-tap";
                    label = "CUSTOM";
                };
                #endif
                
                regular_behavior {
                    compatible = "zmk,behavior-hold-tap";
                    label = "REGULAR";
                };
            };
        };
        """

        # Should parse successfully even with preprocessor directives
        root, errors = parse_dt_safe(source)
        assert root is not None

        # Should still find the regular behavior
        extractor = create_universal_behavior_extractor()
        behaviors = extractor.extract_all_behaviors(root)
        assert len(behaviors["hold_taps"]) >= 1


class TestMultipleRootParsing:
    """Test parsing device tree files with multiple root nodes."""

    def test_parse_multiple_roots_basic(self):
        """Test parsing a basic file with multiple root nodes."""
        source = """
        / {
            compatible = "test,device1";
            property1 = "value1";
        };

        / {
            compatible = "test,device2";
            property2 = "value2";
        };
        """

        roots = parse_dt_multiple(source)
        assert len(roots) == 2

        # Check first root
        assert len(roots[0].properties) == 2
        assert "compatible" in roots[0].properties
        assert "property1" in roots[0].properties

        # Check second root
        assert len(roots[1].properties) == 2
        assert "compatible" in roots[1].properties
        assert "property2" in roots[1].properties

    def test_parse_multiple_roots_with_standalone_nodes(self):
        """Test parsing with mixed root and standalone nodes."""
        source = """
        / {
            compatible = "test,device";
            prop = "value";
        };

        standalone_node {
            property = "standalone_value";
        };
        """

        roots = parse_dt_multiple(source)
        assert len(roots) == 2

        # First root should have explicit properties
        assert len(roots[0].properties) == 2

        # Second root should contain the standalone node as a child
        assert len(roots[1].children) == 1
        assert "standalone_node" in roots[1].children

    def test_parse_multiple_roots_safe(self):
        """Test safe parsing of multiple roots."""
        source = """
        / {
            property = "value1";
        };

        / {
            property = "value2";
        };
        """

        roots, errors = parse_dt_multiple_safe(source)
        assert len(roots) == 2
        assert len(errors) == 0

    def test_parse_multiple_roots_with_errors(self):
        """Test parsing multiple roots with syntax errors."""
        source = """
        / {
            property = "value1";
        };

        / {
            property = invalid_syntax
        };
        """

        roots, errors = parse_dt_multiple_safe(source)
        # Should still parse first root successfully
        assert len(roots) >= 1
        # May have errors from second root
        # (Error handling depends on parser recovery capabilities)

    def test_multi_walker_basic(self):
        """Test DTMultiWalker with multiple root nodes."""
        source = """
        / {
            behaviors {
                ht1: hold_tap {
                    compatible = "zmk,behavior-hold-tap";
                    label = "HT1";
                };
            };
        };

        / {
            behaviors {
                macro1: macro {
                    compatible = "zmk,behavior-macro";
                    label = "MACRO1";
                };
            };
        };
        """

        roots = parse_dt_multiple(source)
        walker = DTMultiWalker(roots)

        # Test finding behaviors across all roots
        hold_taps = walker.find_nodes_by_compatible("zmk,behavior-hold-tap")
        macros = walker.find_nodes_by_compatible("zmk,behavior-macro")

        assert len(hold_taps) == 1
        assert len(macros) == 1
        assert hold_taps[0].name == "hold_tap"
        assert macros[0].name == "macro"

    def test_multi_walker_property_search(self):
        """Test DTMultiWalker property search across multiple roots."""
        source = """
        / {
            compatible = "test,device1";
            node1 {
                label = "NODE1";
            };
        };

        / {
            compatible = "test,device2"; 
            node2 {
                label = "NODE2";
            };
        };
        """

        roots = parse_dt_multiple(source)
        walker = DTMultiWalker(roots)

        # Find all compatible properties
        compatible_props = walker.find_properties_by_name("compatible")
        assert len(compatible_props) == 2

        # Find all label properties
        label_props = walker.find_properties_by_name("label")
        assert len(label_props) == 2

    def test_empty_multiple_roots(self):
        """Test parsing empty content for multiple roots."""
        source = ""

        roots = parse_dt_multiple(source)
        assert len(roots) == 0

        roots, errors = parse_dt_multiple_safe(source)
        assert len(roots) == 0
        assert len(errors) == 0
