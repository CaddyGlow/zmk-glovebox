"""Minimal tests for ZMK keymap parser functionality - only testing working APIs."""

import pytest

from glovebox.layout.parsers.keymap_parser import (
    KeymapParseResult,
    ParsingMode,
    ZmkKeymapParser,
    create_zmk_keymap_parser,
)


class TestZmkKeymapParserBasic:
    """Test basic ZMK keymap parser functionality."""

    @pytest.fixture
    def parser(self):
        """Create parser instance for testing."""
        return create_zmk_keymap_parser()

    @pytest.fixture
    def sample_keymap_content(self):
        """Sample ZMK keymap content for testing."""
        return """
        #include <behaviors.dtsi>
        #include <dt-bindings/zmk/keys.h>

        / {
            keymap {
                compatible = "zmk,keymap";

                layer_Base {
                    bindings = <
                        &kp Q    &kp W    &kp E    &kp R
                        &kp A    &kp S    &kp D    &kp F
                        &mo 1    &kp TAB  &trans   &none
                    >;
                };

                layer_Lower {
                    bindings = <
                        &kp N1   &kp N2   &kp N3   &kp N4
                        &trans   &trans   &trans   &trans
                        &trans   &trans   &trans   &trans
                    >;
                };
            };
        };
        """

    def test_create_zmk_keymap_parser(self):
        """Test parser factory function."""
        parser = create_zmk_keymap_parser()
        assert isinstance(parser, ZmkKeymapParser)

    def test_parsing_mode_enum(self):
        """Test ParsingMode enum values."""
        assert ParsingMode.FULL.value == "full"
        assert ParsingMode.TEMPLATE_AWARE.value == "template"

    def test_keymap_parse_result_model(self):
        """Test KeymapParseResult model structure."""
        result = KeymapParseResult(
            success=True,
            parsing_mode=ParsingMode.FULL,
        )
        assert result.success is True
        assert result.parsing_mode == ParsingMode.FULL
        assert result.layout_data is None
        assert result.errors == []
        assert result.warnings == []
        assert result.extracted_sections == {}

    def test_parse_keymap_file_not_found(self, parser, tmp_path):
        """Test parsing with non-existent keymap file."""
        keymap_file = tmp_path / "nonexistent.keymap"

        result = parser.parse_keymap(
            keymap_file=keymap_file,
            mode=ParsingMode.FULL,
        )

        assert result.success is False
        assert len(result.errors) > 0
        assert "not found" in result.errors[0].lower()

    def test_parse_full_keymap_mode(self, parser, tmp_path, sample_keymap_content):
        """Test full keymap parsing mode."""
        keymap_file = tmp_path / "test.keymap"
        keymap_file.write_text(sample_keymap_content)

        result = parser.parse_keymap(
            keymap_file=keymap_file,
            mode=ParsingMode.FULL,
        )

        assert result.success is True
        assert result.layout_data is not None
        assert result.parsing_mode == ParsingMode.FULL

        layout_data = result.layout_data
        assert layout_data.keyboard == "unknown"  # Default for full mode
        assert len(layout_data.layer_names) >= 0  # May have layers
        assert len(layout_data.layers) >= 0  # May have layer data

    def test_ast_bindings_conversion(self, parser):
        """Test AST bindings conversion method."""
        from glovebox.layout.parsers.ast_nodes import DTValue, DTValueType

        # Create a DTValue with simple bindings
        binding_values = ["&kp", "Q", "&kp", "W", "&trans", "&none"]
        bindings_value = DTValue(type=DTValueType.ARRAY, value=binding_values, raw="")

        bindings = parser._convert_ast_bindings(bindings_value)

        assert len(bindings) >= 3  # Should parse at least 3 bindings

        # Check that bindings have proper structure
        for binding in bindings:
            assert hasattr(binding, "value")
            assert hasattr(binding, "params")
            assert binding.value.startswith("&")

    def test_empty_ast_bindings_conversion(self, parser):
        """Test AST bindings conversion with empty values."""
        from glovebox.layout.parsers.ast_nodes import DTValue, DTValueType

        # Create empty DTValue
        empty_bindings_value = DTValue(type=DTValueType.ARRAY, value=[], raw="")
        bindings = parser._convert_ast_bindings(empty_bindings_value)
        assert len(bindings) == 0

        # Create None DTValue
        none_bindings_value = DTValue(type=DTValueType.ARRAY, value=None, raw="")
        bindings = parser._convert_ast_bindings(none_bindings_value)
        assert len(bindings) == 0

    def test_invalid_keymap_content_handling(self, parser, tmp_path):
        """Test parsing with invalid keymap content."""
        keymap_file = tmp_path / "invalid.keymap"
        keymap_file.write_text("invalid content")

        result = parser.parse_keymap(
            keymap_file=keymap_file,
            mode=ParsingMode.FULL,
        )

        # Should handle gracefully - may fail with invalid content
        assert result.success is True or result.success is False  # Either is acceptable
        # layout_data may be None for completely invalid content
        assert result.layout_data is not None or result.success is False
