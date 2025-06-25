"""Tests for layout edit command value parsing functionality."""

import pytest

from glovebox.cli.commands.layout.edit import parse_value, parse_zmk_behavior_string


class TestParseZmkBehaviorString:
    """Test ZMK behavior string parsing."""

    def test_simple_keypress(self):
        """Test simple keypress behavior."""
        result = parse_zmk_behavior_string("&kp Q")
        expected = {
            "value": "&kp",
            "params": [{"value": "Q", "params": []}]
        }
        assert result == expected

    def test_transparent_behavior(self):
        """Test transparent behavior with no parameters."""
        result = parse_zmk_behavior_string("&trans")
        expected = {
            "value": "&trans",
            "params": []
        }
        assert result == expected

    def test_none_behavior(self):
        """Test none behavior with no parameters."""
        result = parse_zmk_behavior_string("&none")
        expected = {
            "value": "&none",
            "params": []
        }
        assert result == expected

    def test_mod_tap_behavior(self):
        """Test mod-tap behavior with two parameters."""
        result = parse_zmk_behavior_string("&mt LCTRL A")
        expected = {
            "value": "&mt",
            "params": [
                {"value": "LCTRL", "params": []},
                {"value": "A", "params": []}
            ]
        }
        assert result == expected

    def test_layer_tap_behavior(self):
        """Test layer-tap behavior with two parameters."""
        result = parse_zmk_behavior_string("&lt 1 SPACE")
        expected = {
            "value": "&lt",
            "params": [
                {"value": "1", "params": []},
                {"value": "SPACE", "params": []}
            ]
        }
        assert result == expected

    def test_hold_tap_behavior(self):
        """Test hold-tap behavior with two parameters."""
        result = parse_zmk_behavior_string("&ht LSHIFT A")
        expected = {
            "value": "&ht",
            "params": [
                {"value": "LSHIFT", "params": []},
                {"value": "A", "params": []}
            ]
        }
        assert result == expected

    def test_complex_key_name(self):
        """Test behavior with complex key name."""
        result = parse_zmk_behavior_string("&kp C_BRI_UP")
        expected = {
            "value": "&kp",
            "params": [{"value": "C_BRI_UP", "params": []}]
        }
        assert result == expected

    def test_function_key(self):
        """Test behavior with function key."""
        result = parse_zmk_behavior_string("&kp F12")
        expected = {
            "value": "&kp",
            "params": [{"value": "F12", "params": []}]
        }
        assert result == expected

    def test_arrow_key(self):
        """Test behavior with arrow key."""
        result = parse_zmk_behavior_string("&kp UP")
        expected = {
            "value": "&kp",
            "params": [{"value": "UP", "params": []}]
        }
        assert result == expected

    def test_macro_behavior_with_multiple_params(self):
        """Test macro behavior with multiple parameters."""
        result = parse_zmk_behavior_string("&macro_press LCTRL LSHIFT")
        expected = {
            "value": "&macro_press",
            "params": [
                {"value": "LCTRL", "params": []},
                {"value": "LSHIFT", "params": []}
            ]
        }
        assert result == expected

    def test_custom_behavior_name(self):
        """Test custom behavior name."""
        result = parse_zmk_behavior_string("&my_custom_behavior")
        expected = {
            "value": "&my_custom_behavior",
            "params": []
        }
        assert result == expected

    def test_custom_behavior_with_params(self):
        """Test custom behavior with parameters."""
        result = parse_zmk_behavior_string("&HRM_left_index_tap_v1B_TKZ A")
        expected = {
            "value": "&HRM_left_index_tap_v1B_TKZ",
            "params": [{"value": "A", "params": []}]
        }
        assert result == expected

    def test_empty_string_raises_error(self):
        """Test that empty string raises error."""
        with pytest.raises(ValueError, match="Invalid behavior string"):
            parse_zmk_behavior_string("")

    def test_whitespace_only_raises_error(self):
        """Test that whitespace-only string raises error."""
        with pytest.raises(ValueError, match="Invalid behavior string"):
            parse_zmk_behavior_string("   ")

    def test_behavior_with_extra_whitespace(self):
        """Test behavior string with extra whitespace is handled correctly."""
        result = parse_zmk_behavior_string("  &kp   A  ")
        expected = {
            "value": "&kp",
            "params": [{"value": "A", "params": []}]
        }
        assert result == expected

    def test_behavior_with_numeric_parameter(self):
        """Test behavior with numeric parameter."""
        result = parse_zmk_behavior_string("&to 2")
        expected = {
            "value": "&to",
            "params": [{"value": "2", "params": []}]
        }
        assert result == expected

    def test_behavior_with_mixed_params(self):
        """Test behavior with mix of letter and number parameters."""
        result = parse_zmk_behavior_string("&combo_layer 1 A")
        expected = {
            "value": "&combo_layer",
            "params": [
                {"value": "1", "params": []},
                {"value": "A", "params": []}
            ]
        }
        assert result == expected


class TestParseValue:
    """Test general value parsing function."""

    def test_parse_zmk_behavior_keypress(self):
        """Test parsing ZMK keypress behavior."""
        result = parse_value("&kp Q")
        expected = {
            "value": "&kp",
            "params": [{"value": "Q", "params": []}]
        }
        assert result == expected

    def test_parse_zmk_behavior_transparent(self):
        """Test parsing ZMK transparent behavior."""
        result = parse_value("&trans")
        expected = {
            "value": "&trans",
            "params": []
        }
        assert result == expected

    def test_parse_zmk_behavior_mod_tap(self):
        """Test parsing ZMK mod-tap behavior."""
        result = parse_value("&mt LCTRL A")
        expected = {
            "value": "&mt",
            "params": [
                {"value": "LCTRL", "params": []},
                {"value": "A", "params": []}
            ]
        }
        assert result == expected

    def test_parse_json_object(self):
        """Test parsing JSON object bypasses ZMK parsing."""
        json_str = '{"value": "&kp", "params": [{"value": "Q", "params": []}]}'
        result = parse_value(json_str)
        expected = {
            "value": "&kp",
            "params": [{"value": "Q", "params": []}]
        }
        assert result == expected

    def test_parse_json_array(self):
        """Test parsing JSON array."""
        result = parse_value('["a", "b", "c"]')
        assert result == ["a", "b", "c"]

    def test_parse_boolean_true(self):
        """Test parsing boolean true."""
        assert parse_value("true") is True
        assert parse_value("True") is True
        assert parse_value("TRUE") is True

    def test_parse_boolean_false(self):
        """Test parsing boolean false."""
        assert parse_value("false") is False
        assert parse_value("False") is False
        assert parse_value("FALSE") is False

    def test_parse_integer(self):
        """Test parsing integer."""
        assert parse_value("42") == 42
        assert parse_value("-10") == -10
        assert parse_value("0") == 0

    def test_parse_float(self):
        """Test parsing float."""
        assert parse_value("3.14") == 3.14
        assert parse_value("-2.5") == -2.5

    def test_parse_import_syntax(self):
        """Test parsing import syntax."""
        result = parse_value("from:other.json$.variables")
        assert result == ("import", "other.json$.variables")

    def test_parse_regular_string(self):
        """Test parsing regular string."""
        assert parse_value("hello") == "hello"
        assert parse_value("test string") == "test string"

    def test_parse_string_starting_with_non_ampersand(self):
        """Test that strings not starting with & are treated as regular strings."""
        assert parse_value("kp Q") == "kp Q"
        assert parse_value("trans") == "trans"
        assert parse_value("none") == "none"

    def test_parse_zmk_like_string_without_ampersand(self):
        """Test that ZMK-like strings without & are treated as regular strings."""
        assert parse_value("kp A") == "kp A"
        assert parse_value("mt LCTRL A") == "mt LCTRL A"

    def test_parse_edge_cases(self):
        """Test edge cases in value parsing."""
        # Empty string
        assert parse_value("") == ""

        # String with only ampersand
        assert parse_value("&") == {"value": "&", "params": []}

        # String with JSON-like content but invalid JSON
        assert parse_value('{"invalid": json}') == '{"invalid": json}'


class TestParseValueIntegration:
    """Integration tests for value parsing in layout editing context."""

    def test_all_common_zmk_behaviors(self):
        """Test parsing all common ZMK behaviors."""
        behaviors = [
            ("&kp A", {"value": "&kp", "params": [{"value": "A", "params": []}]}),
            ("&trans", {"value": "&trans", "params": []}),
            ("&none", {"value": "&none", "params": []}),
            ("&mt LCTRL A", {"value": "&mt", "params": [{"value": "LCTRL", "params": []}, {"value": "A", "params": []}]}),
            ("&lt 1 SPACE", {"value": "&lt", "params": [{"value": "1", "params": []}, {"value": "SPACE", "params": []}]}),
            ("&to 2", {"value": "&to", "params": [{"value": "2", "params": []}]}),
            ("&tog 1", {"value": "&tog", "params": [{"value": "1", "params": []}]}),
            ("&mo 1", {"value": "&mo", "params": [{"value": "1", "params": []}]}),
            ("&sl 1", {"value": "&sl", "params": [{"value": "1", "params": []}]}),
        ]

        for behavior_str, expected in behaviors:
            result = parse_value(behavior_str)
            assert result == expected, f"Failed for behavior: {behavior_str}"

    def test_mixed_value_types_in_sequence(self):
        """Test parsing different types of values in sequence."""
        test_values = [
            "&kp Q",           # ZMK behavior
            "true",            # Boolean
            "42",              # Integer
            "3.14",            # Float
            '{"test": "value"}',  # JSON
            "regular string",  # String
            "from:import.json" # Import
        ]

        expected_results = [
            {"value": "&kp", "params": [{"value": "Q", "params": []}]},
            True,
            42,
            3.14,
            {"test": "value"},
            "regular string",
            ("import", "import.json")
        ]

        for value, expected in zip(test_values, expected_results, strict=False):
            result = parse_value(value)
            assert result == expected, f"Failed for value: {value}"

    def test_zmk_behaviors_with_special_keys(self):
        """Test ZMK behaviors with special key names."""
        special_keys = [
            ("&kp ESC", {"value": "&kp", "params": [{"value": "ESC", "params": []}]}),
            ("&kp TAB", {"value": "&kp", "params": [{"value": "TAB", "params": []}]}),
            ("&kp ENTER", {"value": "&kp", "params": [{"value": "ENTER", "params": []}]}),
            ("&kp SPACE", {"value": "&kp", "params": [{"value": "SPACE", "params": []}]}),
            ("&kp BSPC", {"value": "&kp", "params": [{"value": "BSPC", "params": []}]}),
            ("&kp DEL", {"value": "&kp", "params": [{"value": "DEL", "params": []}]}),
            ("&kp UP", {"value": "&kp", "params": [{"value": "UP", "params": []}]}),
            ("&kp DOWN", {"value": "&kp", "params": [{"value": "DOWN", "params": []}]}),
            ("&kp LEFT", {"value": "&kp", "params": [{"value": "LEFT", "params": []}]}),
            ("&kp RIGHT", {"value": "&kp", "params": [{"value": "RIGHT", "params": []}]}),
            ("&kp F1", {"value": "&kp", "params": [{"value": "F1", "params": []}]}),
            ("&kp F12", {"value": "&kp", "params": [{"value": "F12", "params": []}]}),
            ("&kp C_BRI_UP", {"value": "&kp", "params": [{"value": "C_BRI_UP", "params": []}]}),
            ("&kp C_VOL_DN", {"value": "&kp", "params": [{"value": "C_VOL_DN", "params": []}]}),
        ]

        for behavior_str, expected in special_keys:
            result = parse_value(behavior_str)
            assert result == expected, f"Failed for behavior: {behavior_str}"
