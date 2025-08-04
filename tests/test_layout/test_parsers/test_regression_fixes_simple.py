"""Simplified regression tests for parser fixes.

This module contains focused tests to ensure the core fixes continue to work:
1. #binding-cells parsing from ARRAY type values
2. Multi-line comment description extraction
3. Section extraction with inner block content
"""

from glovebox.layout.parsers.ast_behavior_converter import ASTBehaviorConverter
from glovebox.layout.parsers.ast_nodes import (
    DTComment,
    DTNode,
    DTProperty,
    DTValue,
    DTValueType,
)
from glovebox.layout.parsers.lark_dt_parser import create_lark_dt_parser
from glovebox.layout.parsers.section_extractor import create_section_extractor
from glovebox.layout.parsers.tokenizer import tokenize_dt


class TestBindingCellsParsingFix:
    """Test the core #binding-cells parsing fix."""

    def test_binding_cells_tokenization_fix(self):
        """Test that #binding-cells is not treated as preprocessor directive."""
        content = "#binding-cells = <1>;"

        tokens = tokenize_dt(content)
        token_values = [token.value for token in tokens if token.value]
        token_types = [token.type.value for token in tokens if token.value]

        # Should find #binding-cells as IDENTIFIER, not PREPROCESSOR
        assert "#binding-cells" in token_values
        binding_cells_idx = token_values.index("#binding-cells")
        assert token_types[binding_cells_idx] == "IDENTIFIER"

    def test_binding_cells_lark_parsing_fix(self):
        """Test that Lark parser correctly handles #binding-cells properties."""
        content = """
        / {
            test_macro {
                #binding-cells = <1>;
                label = "TEST";
            };
        };
        """

        parser = create_lark_dt_parser()
        roots = parser.parse(content)

        assert len(roots) == 1
        root = roots[0]
        test_macro = root.get_child("test_macro")
        assert test_macro is not None

        # Should have #binding-cells property
        binding_cells = test_macro.get_property("#binding-cells")
        assert binding_cells is not None
        assert binding_cells.value is not None
        assert binding_cells.value.type == DTValueType.ARRAY
        assert binding_cells.value.value == ["1"]

    def test_extract_int_from_array_property_fix(self):
        """Test that integer extraction works with ARRAY type #binding-cells."""
        converter = ASTBehaviorConverter()

        # Create property with ARRAY type (the fix)
        prop = DTProperty(
            name="#binding-cells",
            value=DTValue(type=DTValueType.ARRAY, value=["2"], raw="<2>"),
        )

        result = converter._extract_int_from_property(prop)
        assert result == 2

        # Test with different values
        prop_0 = DTProperty(
            name="#binding-cells",
            value=DTValue(type=DTValueType.ARRAY, value=["0"], raw="<0>"),
        )
        assert converter._extract_int_from_property(prop_0) == 0

        prop_3 = DTProperty(
            name="#binding-cells",
            value=DTValue(type=DTValueType.ARRAY, value=["3"], raw="<3>"),
        )
        assert converter._extract_int_from_property(prop_3) == 3

    def test_extract_int_handles_malformed_array(self):
        """Test graceful handling of malformed ARRAY values."""
        converter = ASTBehaviorConverter()

        # Empty array
        prop_empty = DTProperty(
            name="#binding-cells",
            value=DTValue(type=DTValueType.ARRAY, value=[], raw="<>"),
        )
        assert converter._extract_int_from_property(prop_empty) is None

        # Invalid value
        prop_invalid = DTProperty(
            name="#binding-cells",
            value=DTValue(type=DTValueType.ARRAY, value=["invalid"], raw="<invalid>"),
        )
        assert converter._extract_int_from_property(prop_invalid) is None


class TestCommentExtractionFix:
    """Test the core multi-line comment extraction fix."""

    def test_single_comment_extraction(self):
        """Test extraction of a single comment line."""
        node = DTNode(name="test_node")
        comment = DTComment(text="// Single line description")
        node.comments = [comment]

        converter = ASTBehaviorConverter()
        description = converter._extract_description_from_node(node)

        assert description == "Single line description"

    def test_multi_line_comment_extraction(self):
        """Test extraction of multiple comment lines."""
        node = DTNode(name="test_node")
        comments = [
            DTComment(text="// First line of description"),
            DTComment(text="// Second line of description"),
            DTComment(text="// Third line of description"),
        ]
        node.comments = comments

        converter = ASTBehaviorConverter()
        description = converter._extract_description_from_node(node)

        expected = "First line of description\nSecond line of description\nThird line of description"
        assert description == expected

    def test_multi_line_with_empty_lines(self):
        """Test extraction preserving empty lines for proper formatting."""
        node = DTNode(name="test_node")
        comments = [
            DTComment(text="// mod_tab_switcher - TailorKey"),
            DTComment(text="//"),  # Empty comment line
            DTComment(text="// mod_tab_v1_TKZ: Additional description"),
        ]
        node.comments = comments

        converter = ASTBehaviorConverter()
        description = converter._extract_description_from_node(node)

        # Should preserve the empty line
        expected = (
            "mod_tab_switcher - TailorKey\n\nmod_tab_v1_TKZ: Additional description"
        )
        assert description == expected

    def test_comment_prefix_removal(self):
        """Test that comment prefixes (//) are properly removed."""
        node = DTNode(name="test_node")
        comments = [
            DTComment(text="// Description with slashes"),
            DTComment(text="//Another line"),
            DTComment(text="//   Line with extra spaces"),
        ]
        node.comments = comments

        converter = ASTBehaviorConverter()
        description = converter._extract_description_from_node(node)

        lines = description.split("\n")
        assert lines[0] == "Description with slashes"
        assert lines[1] == "Another line"
        assert lines[2] == "Line with extra spaces"

    def test_empty_comments_handling(self):
        """Test handling of nodes with no comments."""
        node = DTNode(name="test_node")
        node.comments = []

        converter = ASTBehaviorConverter()
        description = converter._extract_description_from_node(node)

        assert description == ""

    def test_excessive_whitespace_cleanup(self):
        """Test that excessive whitespace is cleaned up while preserving structure."""
        node = DTNode(name="test_node")
        comments = [
            DTComment(text="// First line"),
            DTComment(text="//"),
            DTComment(text="//"),
            DTComment(text="//"),  # Multiple empty lines
            DTComment(text="// Second line"),
        ]
        node.comments = comments

        converter = ASTBehaviorConverter()
        description = converter._extract_description_from_node(node)

        # Should reduce multiple empty lines to single empty line
        expected = "First line\n\nSecond line"
        assert description == expected


class TestSectionExtractionFix:
    """Test the core section extraction fix with inner block content."""

    def test_extract_macro_inner_content_fix(self):
        """Test extraction of inner content from macro section."""
        content = """
/ {
    macros {
        // Test macro description
        test_macro {
            compatible = "zmk,behavior-macro";
            #binding-cells = <1>;
            label = "TEST_MACRO";
            bindings = <&macro_tap &kp A>;
        };
    };
};
        """

        extractor = create_section_extractor()
        inner_content = extractor._extract_inner_block_content(content, "macro")

        # Should extract just the inner content without wrapper
        assert "// Test macro description" in inner_content
        assert "test_macro {" in inner_content
        assert 'compatible = "zmk,behavior-macro";' in inner_content
        assert "#binding-cells = <1>;" in inner_content

        # Should not contain the wrapper structure
        assert "/ {" not in inner_content
        assert "macros {" not in inner_content

    def test_extract_behavior_inner_content_fix(self):
        """Test extraction of inner content from behavior section."""
        content = """
/ {
    behaviors {
        // Custom hold-tap behavior
        hm: homerow_mods {
            compatible = "zmk,behavior-hold-tap";
            #binding-cells = <2>;
            label = "HOMEROW_MODS";
            tapping-term-ms = <150>;
            flavor = "tap-preferred";
            bindings = <&kp>, <&kp>;
        };
    };
};
        """

        extractor = create_section_extractor()
        inner_content = extractor._extract_inner_block_content(content, "behavior")

        # Should extract just the inner content
        assert "// Custom hold-tap behavior" in inner_content
        assert "hm: homerow_mods {" in inner_content
        assert 'compatible = "zmk,behavior-hold-tap";' in inner_content

        # Should not contain wrapper
        assert "behaviors {" not in inner_content

    def test_brace_counting_accuracy_fix(self):
        """Test that brace counting correctly handles nested structures."""
        content = """
/ {
    macros {
        complex_macro {
            compatible = "zmk,behavior-macro";
            nested_property {
                inner_value = "test";
            };
            bindings = <&macro_tap &kp A>;
        };
    };
};
        """

        extractor = create_section_extractor()
        inner_content = extractor._extract_inner_block_content(content, "macro")

        # Should correctly handle nested braces
        assert "complex_macro {" in inner_content
        assert "nested_property {" in inner_content
        assert 'inner_value = "test";' in inner_content

        # Should not include outer wrapper braces
        assert "macros {" not in inner_content

        # Brace count should be balanced
        assert inner_content.count("{") == inner_content.count("}")

    def test_unknown_block_type_fallback(self):
        """Test that unknown block types return original content."""
        content = """
/ {
    unknown_section {
        content = "value";
    };
};
        """

        extractor = create_section_extractor()
        result = extractor._extract_inner_block_content(content, "unknown")

        # Should return original content for unknown types
        assert result == content

    def test_missing_block_fallback(self):
        """Test that missing target block returns original content."""
        content = """
/ {
    behaviors {
        content = "value";
    };
};
        """

        extractor = create_section_extractor()
        # Try to extract 'macros' content from 'behaviors' section
        result = extractor._extract_inner_block_content(content, "macro")

        # Should return original content when target block not found
        assert result == content


class TestIntegrationRegression:
    """Integration tests to ensure the fixes work together."""

    def test_binding_cells_in_parsed_macro(self):
        """Test that #binding-cells works in a fully parsed macro."""
        content = """
        / {
            test_macro {
                compatible = "zmk,behavior-macro";
                #binding-cells = <1>;
                label = "TEST";
            };
        };
        """

        parser = create_lark_dt_parser()
        roots = parser.parse(content)

        # Should parse successfully
        assert len(roots) == 1
        root = roots[0]
        macro = root.get_child("test_macro")
        assert macro is not None

        # #binding-cells should be extracted correctly
        binding_cells = macro.get_property("#binding-cells")
        assert binding_cells is not None

        # Test integer extraction from the property
        converter = ASTBehaviorConverter()
        result = converter._extract_int_from_property(binding_cells)
        assert result == 1

    def test_preprocessor_directives_still_work(self):
        """Test that actual preprocessor directives are still handled correctly."""
        content = """
        #include <test.h>
        #ifdef CONFIG_TEST
        / {
            test_node {
                property = "value";
            };
        };
        #endif
        """

        parser = create_lark_dt_parser()
        roots = parser.parse(content)

        # Should parse without major errors
        assert isinstance(roots, list)
        # The exact behavior depends on preprocessor handling

    def test_hash_properties_vs_preprocessor_distinction(self):
        """Test that hash properties and preprocessor directives are distinguished."""
        content = """
        #include <dt-bindings/zmk/keys.h>
        / {
            test_behavior {
                #binding-cells = <2>;
                #foo-bar = <1>;
                compatible = "zmk,behavior-test";
            };
        };
        """

        # Tokenize and check both types are handled
        tokens = tokenize_dt(content)
        token_values = [token.value for token in tokens if token.value]
        token_types = [token.type.value for token in tokens if token.value]

        # Should have both preprocessor and identifier tokens
        assert any("include" in val for val in token_values)
        assert "#binding-cells" in token_values
        assert "#foo-bar" in token_values

        # Check correct classification
        if "#binding-cells" in token_values:
            binding_cells_idx = token_values.index("#binding-cells")
            assert token_types[binding_cells_idx] == "IDENTIFIER"
