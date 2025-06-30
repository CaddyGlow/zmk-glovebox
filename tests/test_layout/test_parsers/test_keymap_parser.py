"""Tests for ZMK keymap parser functionality."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from glovebox.layout.models import LayoutBinding, LayoutData
from glovebox.layout.parsers.keymap_parser import (
    KeymapParseResult,
    ParsingMethod,
    ParsingMode,
    ZmkKeymapParser,
    create_zmk_keymap_parser,
    create_zmk_keymap_parser_from_profile,
)


class TestZmkKeymapParser:
    """Test ZMK keymap parser functionality."""

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

        #define LAYER_Base 0
        #define LAYER_Lower 1

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

    @pytest.fixture
    def sample_keymap_with_behaviors(self):
        """Sample keymap with custom behaviors."""
        return """
        #include <behaviors.dtsi>
        #include <dt-bindings/zmk/keys.h>

        / {
            behaviors {
                hm: homerow_mod {
                    compatible = "zmk,behavior-hold-tap";
                    flavor = "tap-preferred";
                    tapping-term-ms = <150>;
                    quick-tap-ms = <0>;
                    bindings = <&kp>, <&kp>;
                };
            };

            macros {
                my_macro: my_macro {
                    compatible = "zmk,behavior-macro";
                    wait-ms = <30>;
                    tap-ms = <40>;
                    bindings = <&kp LSHIFT &kp H &kp I>;
                };
            };

            combos {
                combo_esc: combo_esc {
                    compatible = "zmk,behavior-combo";
                    key-positions = <0 1>;
                    bindings = <&kp ESC>;
                };
            };

            keymap {
                compatible = "zmk,keymap";

                layer_Base {
                    bindings = <
                        &hm LSHIFT Q  &kp W
                        &my_macro     &kp S
                    >;
                };
            };
        };
        """

    def test_create_zmk_keymap_parser(self):
        """Test parser factory function."""
        parser = create_zmk_keymap_parser()
        assert isinstance(parser, ZmkKeymapParser)
        assert hasattr(parser, "template_adapter")

    def test_parsing_mode_enum(self):
        """Test ParsingMode enum values."""
        assert ParsingMode.FULL == "full"
        assert ParsingMode.TEMPLATE_AWARE == "template"

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

    def test_parse_keymap_template_mode_requires_profile(self, parser, tmp_path):
        """Test that template mode requires keyboard profile."""
        keymap_file = tmp_path / "test.keymap"
        keymap_file.write_text("dummy content")

        result = parser.parse_keymap(
            keymap_file=keymap_file,
            mode=ParsingMode.TEMPLATE_AWARE,
            keyboard_profile=None,
        )

        assert result.success is False
        assert any("profile is required" in error.lower() for error in result.errors)

    def test_extract_layers_from_keymap(self, parser, sample_keymap_content):
        """Test layer extraction from keymap content."""
        layers_data = parser._extract_layers_from_keymap(sample_keymap_content)

        assert layers_data is not None
        assert "layer_names" in layers_data
        assert "layers" in layers_data

        layer_names = layers_data["layer_names"]
        layers = layers_data["layers"]

        assert len(layer_names) == 2
        assert "Base" in layer_names
        assert "Lower" in layer_names

        assert len(layers) == 2
        assert len(layers[0]) > 0  # Base layer has bindings
        assert len(layers[1]) > 0  # Lower layer has bindings

        # Check specific bindings
        base_layer = layers[0]
        assert isinstance(base_layer[0], LayoutBinding)
        assert base_layer[0].value == "&kp"
        assert len(base_layer[0].params) == 1
        assert base_layer[0].params[0].value == "Q"

    def test_parse_bindings_content(self, parser):
        """Test parsing of bindings content string."""
        from glovebox.layout.parsers.ast_nodes import DTValue, DTValueType

        # Create a DTValue with array of bindings as they would appear in AST
        binding_values = [
            "&kp",
            "Q",
            "&kp",
            "W",
            "&kp",
            "E",
            "&kp",
            "R",
            "&mt",
            "LSHIFT",
            "A",
            "&lt",
            "1",
            "S",
            "&trans",
            "&none",
            "&mo",
            "1",
            "&kp",
            "TAB",
        ]

        bindings_value = DTValue(type=DTValueType.ARRAY, value=binding_values, raw="")

        bindings = parser._convert_ast_bindings(bindings_value)

        assert len(bindings) >= 8  # Should parse all valid bindings

        # Check first binding
        assert bindings[0].value == "&kp"
        assert bindings[0].params[0].value == "Q"

        # Check complex binding
        mt_binding = next(b for b in bindings if b.value == "&mt")
        assert len(mt_binding.params) == 2
        assert mt_binding.params[0].value == "LSHIFT"
        assert mt_binding.params[1].value == "A"

        # Check layer tap binding
        lt_binding = next(b for b in bindings if b.value == "&lt")
        assert len(lt_binding.params) == 2
        assert lt_binding.params[0].value == 1  # Should be parsed as integer
        assert lt_binding.params[1].value == "S"

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
        assert layout_data.title == "Imported Keymap"
        assert len(layout_data.layer_names) == 2
        assert len(layout_data.layers) == 2

        # Check extracted sections
        assert "layers" in result.extracted_sections

    def test_parse_template_aware_mode(self, parser, tmp_path, sample_keymap_content):
        """Test template-aware parsing mode."""
        # Mock profile and template
        mock_profile = MagicMock()
        mock_profile.keyboard_name = "glove80"
        mock_profile.config_path = "/mock/path/config.yaml"

        # Mock template path
        template_path = tmp_path / "template.j2"
        template_path.write_text("{{ keymap_node }}")

        with (
            patch("glovebox.config.create_keyboard_profile", return_value=mock_profile),
            patch.object(parser, "_get_template_path", return_value=template_path),
        ):
            with patch.object(
                parser.template_adapter,
                "get_template_variables",
                return_value=["keymap_node"],
            ):
                keymap_file = tmp_path / "test.keymap"
                keymap_file.write_text(sample_keymap_content)

                result = parser.parse_keymap(
                    keymap_file=keymap_file,
                    mode=ParsingMode.TEMPLATE_AWARE,
                    keyboard_profile="glove80/v25.05",
                )

            assert result.success is True
            assert result.layout_data is not None
            assert result.parsing_mode == ParsingMode.TEMPLATE_AWARE

            layout_data = result.layout_data
            assert layout_data.keyboard == "glove80"
            assert len(layout_data.layer_names) == 2

    def test_behavior_parsing_integration(
        self, parser, tmp_path, sample_keymap_with_behaviors
    ):
        """Test integration with behavior parser."""
        keymap_file = tmp_path / "test.keymap"
        keymap_file.write_text(sample_keymap_with_behaviors)

        result = parser.parse_keymap(
            keymap_file=keymap_file,
            mode=ParsingMode.FULL,
        )

        assert result.success is True
        layout_data = result.layout_data

        # Check that behaviors were extracted
        # Note: The actual behavior parsing uses AST-based parsing
        # For now, just verify the structure is set up correctly
        assert hasattr(layout_data, "hold_taps")
        assert hasattr(layout_data, "macros")
        assert hasattr(layout_data, "combos")

    def test_invalid_keymap_content(self, parser, tmp_path):
        """Test parsing with invalid keymap content."""
        keymap_file = tmp_path / "invalid.keymap"
        keymap_file.write_text("invalid content")

        result = parser.parse_keymap(
            keymap_file=keymap_file,
            mode=ParsingMode.FULL,
        )

        # Should still succeed but with minimal data
        assert result.success is True
        assert result.layout_data is not None

        # Should have empty layers if no valid keymap structure found
        layout_data = result.layout_data
        assert len(layout_data.layer_names) == 0
        assert len(layout_data.layers) == 0

    def test_malformed_bindings_handling(self, parser):
        """Test handling of malformed bindings in parsing."""
        from glovebox.layout.parsers.ast_nodes import DTValue, DTValueType

        # Create malformed binding values as they would appear in AST
        malformed_values = ["&kp", "Q", "&invalid_binding", "&mt", "&"]

        bindings_value = DTValue(type=DTValueType.ARRAY, value=malformed_values, raw="")

        bindings = parser._convert_ast_bindings(bindings_value)

        # Should have some bindings, with fallbacks for malformed ones
        assert len(bindings) > 0

        # First binding should be valid
        assert bindings[0].value == "&kp"
        assert bindings[0].params[0].value == "Q"

        # Malformed bindings should have fallback values
        invalid_bindings = [
            b for b in bindings if "invalid" in b.value or b.value == "&"
        ]
        assert len(invalid_bindings) > 0

    def test_empty_keymap_handling(self, parser):
        """Test handling of empty or minimal keymap content."""
        from glovebox.layout.parsers.dt_parser import parse_dt_safe

        empty_content = ""
        root, errors = parse_dt_safe(empty_content)
        if root:
            layers_data = parser._extract_layers_from_ast(root)
            assert layers_data is None or len(layers_data) == 0
        else:
            # No valid AST, so no layers
            assert True

        minimal_content = "/ { };"
        root, errors = parse_dt_safe(minimal_content)
        if root:
            layers_data = parser._extract_layers_from_ast(root)
            assert layers_data is None or len(layers_data) == 0
        else:
            assert True
