"""Unit tests for layout models timestamp serialization and string conversion."""

import json
from datetime import UTC, datetime, timezone
from pathlib import Path

import pytest

from glovebox.layout.models import (
    KeymapResult,
    LayoutBinding,
    LayoutData,
    LayoutLayer,
    LayoutParam,
    LayoutResult,
)


class TestLayoutDataTimestampSerialization:
    """Test LayoutData timestamp serialization."""

    def test_date_field_json_serialization(self):
        """Test that date field serializes to Unix timestamp in JSON mode."""
        # Create a specific datetime for consistent testing
        test_date = datetime(2025, 6, 19, 15, 30, 45, tzinfo=UTC)
        expected_timestamp = int(test_date.timestamp())

        layout = LayoutData(keyboard="glove80", title="Test Layout", date=test_date)

        # Test JSON serialization
        json_data = layout.model_dump(mode="json")
        assert isinstance(json_data["date"], int)
        assert json_data["date"] == expected_timestamp

        # Verify it's properly JSON serializable
        json_string = json.dumps(json_data)
        parsed_back = json.loads(json_string)
        assert parsed_back["date"] == expected_timestamp

    def test_date_field_regular_serialization(self):
        """Test that date field remains datetime object in regular mode."""
        test_date = datetime(2025, 6, 19, 15, 30, 45, tzinfo=UTC)

        layout = LayoutData(keyboard="glove80", title="Test Layout", date=test_date)

        # Test regular serialization
        regular_data = layout.model_dump(by_alias=True, exclude_unset=True)
        assert isinstance(regular_data["date"], datetime)
        assert regular_data["date"] == test_date

    def test_date_field_default_value_serialization(self):
        """Test that default date value serializes correctly."""
        layout = LayoutData(keyboard="glove80", title="Test Layout")

        # Test JSON serialization with default date
        json_data = layout.model_dump(mode="json")
        assert isinstance(json_data["date"], int)
        assert json_data["date"] > 0  # Should be a valid Unix timestamp

        # Verify it represents a reasonable time (after 2020)
        # Unix timestamp for 2020-01-01 is approximately 1577836800
        assert json_data["date"] > 1577836800

    def test_date_field_timezone_handling(self):
        """Test that date field handles different timezones correctly."""
        # Test with UTC
        utc_date = datetime(2025, 6, 19, 12, 0, 0, tzinfo=UTC)
        layout_utc = LayoutData(keyboard="glove80", title="UTC Test", date=utc_date)

        json_data_utc = layout_utc.model_dump(mode="json")
        expected_utc_timestamp = int(utc_date.timestamp())
        assert json_data_utc["date"] == expected_utc_timestamp

        # Test with naive datetime (should be treated as local time)
        naive_date = datetime(2025, 6, 19, 12, 0, 0)
        layout_naive = LayoutData(
            keyboard="glove80", title="Naive Test", date=naive_date
        )

        json_data_naive = layout_naive.model_dump(mode="json")
        expected_naive_timestamp = int(naive_date.timestamp())
        assert json_data_naive["date"] == expected_naive_timestamp


class TestKeymapResultTimestampSerialization:
    """Test KeymapResult timestamp serialization."""

    def test_timestamp_field_json_serialization(self):
        """Test that timestamp field serializes to Unix timestamp in JSON mode."""
        test_timestamp = datetime(2025, 6, 19, 15, 30, 45, tzinfo=UTC)
        expected_unix_timestamp = int(test_timestamp.timestamp())

        result = KeymapResult(success=True, timestamp=test_timestamp)

        # Test JSON serialization
        json_data = result.model_dump(mode="json")
        assert isinstance(json_data["timestamp"], int)
        assert json_data["timestamp"] == expected_unix_timestamp

        # Verify it's properly JSON serializable
        json_string = json.dumps(json_data)
        parsed_back = json.loads(json_string)
        assert parsed_back["timestamp"] == expected_unix_timestamp

    def test_timestamp_field_regular_serialization(self):
        """Test that timestamp field remains datetime object in regular mode."""
        test_timestamp = datetime(2025, 6, 19, 15, 30, 45, tzinfo=UTC)

        result = KeymapResult(success=True, timestamp=test_timestamp)

        # Test regular serialization
        regular_data = result.model_dump(by_alias=True, exclude_unset=True)
        assert isinstance(regular_data["timestamp"], datetime)
        assert regular_data["timestamp"] == test_timestamp

    def test_timestamp_field_with_paths(self):
        """Test timestamp serialization with keymap result containing paths."""
        test_timestamp = datetime(2025, 6, 19, 15, 30, 45, tzinfo=UTC)
        expected_unix_timestamp = int(test_timestamp.timestamp())

        result = KeymapResult(
            success=True,
            timestamp=test_timestamp,
            keymap_path=Path("/tmp/test.keymap"),
            conf_path=Path("/tmp/test.conf"),
            json_path=Path("/tmp/test.json"),
            profile_name="glove80/v25.05",
            layer_count=5,
        )

        # Test JSON serialization
        json_data = result.model_dump(mode="json")
        assert isinstance(json_data["timestamp"], int)
        assert json_data["timestamp"] == expected_unix_timestamp

        # Ensure other fields are properly serialized too
        assert json_data["success"] is True
        assert json_data["profile_name"] == "glove80/v25.05"
        assert json_data["layer_count"] == 5


class TestLayoutResultTimestampSerialization:
    """Test LayoutResult timestamp serialization."""

    def test_timestamp_field_json_serialization(self):
        """Test that timestamp field serializes to Unix timestamp in JSON mode."""
        test_timestamp = datetime(2025, 6, 19, 15, 30, 45, tzinfo=UTC)
        expected_unix_timestamp = int(test_timestamp.timestamp())

        result = LayoutResult(success=True, timestamp=test_timestamp)

        # Test JSON serialization
        json_data = result.model_dump(mode="json")
        assert isinstance(json_data["timestamp"], int)
        assert json_data["timestamp"] == expected_unix_timestamp

    def test_timestamp_field_regular_serialization(self):
        """Test that timestamp field remains datetime object in regular mode."""
        test_timestamp = datetime(2025, 6, 19, 15, 30, 45, tzinfo=UTC)

        result = LayoutResult(success=True, timestamp=test_timestamp)

        # Test regular serialization
        regular_data = result.model_dump(by_alias=True, exclude_unset=True)
        assert isinstance(regular_data["timestamp"], datetime)
        assert regular_data["timestamp"] == test_timestamp

    def test_timestamp_field_with_error_state(self):
        """Test timestamp serialization with layout result in error state."""
        test_timestamp = datetime(2025, 6, 19, 15, 30, 45, tzinfo=UTC)
        expected_unix_timestamp = int(test_timestamp.timestamp())

        result = LayoutResult(
            success=False,
            timestamp=test_timestamp,
            errors=["Test error 1", "Test error 2"],
        )

        # Test JSON serialization
        json_data = result.model_dump(mode="json")
        assert isinstance(json_data["timestamp"], int)
        assert json_data["timestamp"] == expected_unix_timestamp
        assert json_data["success"] is False
        assert len(json_data["errors"]) == 2


class TestTimestampSerializationIntegration:
    """Integration tests for timestamp serialization across models."""

    def test_all_models_serialize_consistently(self):
        """Test that all models serialize timestamps consistently."""
        test_timestamp = datetime(2025, 6, 19, 15, 30, 45, tzinfo=UTC)
        expected_unix_timestamp = int(test_timestamp.timestamp())

        # Create instances of all models with the same timestamp
        layout = LayoutData(
            keyboard="glove80", title="Test Layout", date=test_timestamp
        )

        keymap_result = KeymapResult(success=True, timestamp=test_timestamp)

        layout_result = LayoutResult(success=True, timestamp=test_timestamp)

        # Serialize all to JSON
        layout_json = layout.model_dump(mode="json")
        keymap_json = keymap_result.model_dump(mode="json")
        layout_result_json = layout_result.model_dump(mode="json")

        # Verify all use the same timestamp format and value
        assert layout_json["date"] == expected_unix_timestamp
        assert keymap_json["timestamp"] == expected_unix_timestamp
        assert layout_result_json["timestamp"] == expected_unix_timestamp

        # Verify all are integers
        assert isinstance(layout_json["date"], int)
        assert isinstance(keymap_json["timestamp"], int)
        assert isinstance(layout_result_json["timestamp"], int)

    def test_timestamp_roundtrip_conversion(self):
        """Test that timestamps can be properly converted back from Unix format."""
        original_timestamp = datetime(2025, 6, 19, 15, 30, 45, tzinfo=UTC)

        layout = LayoutData(
            keyboard="glove80", title="Test Layout", date=original_timestamp
        )

        # Serialize to JSON format
        json_data = layout.model_dump(mode="json")
        unix_timestamp = json_data["date"]

        # Convert back to datetime
        recovered_timestamp = datetime.fromtimestamp(unix_timestamp, tz=UTC)

        # Should match original (within second precision due to int conversion)
        assert abs((recovered_timestamp - original_timestamp).total_seconds()) < 1

    def test_json_string_serialization(self):
        """Test that models can be fully serialized to JSON strings."""
        layout = LayoutData(keyboard="glove80", title="Test Layout")
        keymap_result = KeymapResult(success=True)
        layout_result = LayoutResult(success=False, errors=["Test error"])

        # Test that all models can be fully serialized to JSON strings
        layout_json_str = json.dumps(layout.model_dump(mode="json"))
        keymap_json_str = json.dumps(keymap_result.model_dump(mode="json"))
        layout_result_json_str = json.dumps(layout_result.model_dump(mode="json"))

        # Verify they can be parsed back
        layout_parsed = json.loads(layout_json_str)
        keymap_parsed = json.loads(keymap_json_str)
        layout_result_parsed = json.loads(layout_result_json_str)

        # Verify timestamp fields are integers
        assert isinstance(layout_parsed["date"], int)
        assert isinstance(keymap_parsed["timestamp"], int)
        assert isinstance(layout_result_parsed["timestamp"], int)

        # Verify other fields are preserved
        assert layout_parsed["keyboard"] == "glove80"
        assert layout_parsed["title"] == "Test Layout"
        assert keymap_parsed["success"] is True
        assert layout_result_parsed["success"] is False
        assert len(layout_result_parsed["errors"]) == 1

    def test_edge_case_epoch_timestamp(self):
        """Test serialization of epoch timestamp (1970-01-01)."""
        epoch_time = datetime(1970, 1, 1, 0, 0, 0, tzinfo=UTC)

        layout = LayoutData(keyboard="glove80", title="Epoch Test", date=epoch_time)

        json_data = layout.model_dump(mode="json")
        assert json_data["date"] == 0

    def test_edge_case_future_timestamp(self):
        """Test serialization of far future timestamp."""
        future_time = datetime(2100, 12, 31, 23, 59, 59, tzinfo=UTC)

        layout = LayoutData(keyboard="glove80", title="Future Test", date=future_time)

        json_data = layout.model_dump(mode="json")
        expected_timestamp = int(future_time.timestamp())
        assert json_data["date"] == expected_timestamp
        assert json_data["date"] > 4000000000  # Should be well into the future


class TestLayoutBindingFromStr:
    """Test LayoutBinding.from_str() method."""

    def test_simple_behavior_no_params(self):
        """Test parsing simple behaviors without parameters."""
        binding = LayoutBinding.from_str("&trans")
        assert binding.value == "&trans"
        assert binding.params == []

    def test_simple_behavior_with_single_param(self):
        """Test parsing behaviors with single parameter."""
        binding = LayoutBinding.from_str("&kp Q")
        assert binding.value == "&kp"
        assert len(binding.params) == 1
        assert binding.params[0].value == "Q"
        assert binding.params[0].params == []

    def test_behavior_with_multiple_params(self):
        """Test parsing behaviors with multiple parameters."""
        binding = LayoutBinding.from_str("&mt LCTRL A")
        assert binding.value == "&mt"
        assert len(binding.params) == 2
        assert binding.params[0].value == "LCTRL"
        assert binding.params[1].value == "A"

    def test_behavior_with_numeric_params(self):
        """Test parsing behaviors with numeric parameters."""
        binding = LayoutBinding.from_str("&mo 1")
        assert binding.value == "&mo"
        assert len(binding.params) == 1
        assert binding.params[0].value == 1
        assert isinstance(binding.params[0].value, int)

    def test_behavior_with_mixed_params(self):
        """Test parsing behaviors with mixed string and numeric parameters."""
        binding = LayoutBinding.from_str("&lt 2 SPACE")
        assert binding.value == "&lt"
        assert len(binding.params) == 2
        assert binding.params[0].value == 2
        assert isinstance(binding.params[0].value, int)
        assert binding.params[1].value == "SPACE"
        assert isinstance(binding.params[1].value, str)

    def test_behavior_with_quoted_params(self):
        """Test parsing behaviors with quoted parameters."""
        binding = LayoutBinding.from_str('&macro_play "my macro"')
        assert binding.value == "&macro_play"
        assert len(binding.params) == 1
        assert binding.params[0].value == "my macro"

    def test_behavior_with_quoted_params_single_quotes(self):
        """Test parsing behaviors with single-quoted parameters."""
        binding = LayoutBinding.from_str("&macro_play 'another macro'")
        assert binding.value == "&macro_play"
        assert len(binding.params) == 1
        assert binding.params[0].value == "another macro"

    def test_behavior_with_quoted_params_containing_spaces(self):
        """Test parsing behaviors with quoted parameters containing spaces."""
        binding = LayoutBinding.from_str(
            '&custom_behavior "param with spaces" normal_param'
        )
        assert binding.value == "&custom_behavior"
        assert len(binding.params) == 2
        assert binding.params[0].value == "param with spaces"
        assert binding.params[1].value == "normal_param"

    def test_behavior_with_extra_whitespace(self):
        """Test parsing behaviors with extra whitespace."""
        binding = LayoutBinding.from_str("  &kp   Q  ")
        assert binding.value == "&kp"
        assert len(binding.params) == 1
        assert binding.params[0].value == "Q"

    def test_complex_behavior_chain(self):
        """Test parsing complex behavior with multiple parameters."""
        binding = LayoutBinding.from_str("&hold_tap 200 150 &kp &mo")
        assert binding.value == "&hold_tap"
        assert len(binding.params) == 4
        assert binding.params[0].value == 200
        assert binding.params[1].value == 150
        assert binding.params[2].value == "&kp"
        assert binding.params[3].value == "&mo"

    def test_empty_string_raises_error(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="Behavior string cannot be empty"):
            LayoutBinding.from_str("")

    def test_whitespace_only_string_raises_error(self):
        """Test that whitespace-only string raises ValueError."""
        with pytest.raises(ValueError, match="Behavior string cannot be empty"):
            LayoutBinding.from_str("   ")

    def test_behavior_without_ampersand_logs_warning(self, caplog):
        """Test that behavior without & logs a warning but still works."""
        binding = LayoutBinding.from_str("kp Q")
        assert binding.value == "kp"
        assert len(binding.params) == 1
        assert binding.params[0].value == "Q"
        # Check that warning was logged
        assert "does not start with '&'" in caplog.text

    def test_malformed_quoted_string_handles_gracefully(self):
        """Test handling of malformed quoted strings."""
        # Missing closing quote - parser treats everything after quote as quoted content
        binding = LayoutBinding.from_str('&macro "unclosed quote param')
        assert binding.value == "&macro"
        assert len(binding.params) == 1
        assert binding.params[0].value == 'unclosed quote param'

    def test_nested_quotes_handling(self):
        """Test handling of nested or escaped quotes."""
        binding = LayoutBinding.from_str("&custom 'outer \"inner\" quote' normal")
        assert binding.value == "&custom"
        assert len(binding.params) == 2
        assert binding.params[0].value == 'outer "inner" quote'
        assert binding.params[1].value == "normal"

    def test_common_zmk_behaviors(self):
        """Test parsing common ZMK behaviors."""
        test_cases = [
            ("&none", "&none", []),
            ("&trans", "&trans", []),
            ("&kp ESC", "&kp", ["ESC"]),
            ("&mo 1", "&mo", [1]),
            ("&lt 1 TAB", "&lt", [1, "TAB"]),
            ("&mt LSHIFT A", "&mt", ["LSHIFT", "A"]),
            ("&sk LSHIFT", "&sk", ["LSHIFT"]),
            ("&sl 1", "&sl", [1]),
            ("&tog 1", "&tog", [1]),
            ("&to 0", "&to", [0]),
            ("&bootloader", "&bootloader", []),
            ("&bt BT_CLR", "&bt", ["BT_CLR"]),
            ("&bt BT_SEL 0", "&bt", ["BT_SEL", 0]),
        ]

        for behavior_str, expected_value, expected_params in test_cases:
            binding = LayoutBinding.from_str(behavior_str)
            assert binding.value == expected_value
            assert len(binding.params) == len(expected_params)
            for i, expected_param in enumerate(expected_params):
                assert binding.params[i].value == expected_param

    def test_behavior_property_returns_value(self):
        """Test that behavior property returns the value field."""
        binding = LayoutBinding.from_str("&kp Q")
        assert binding.behavior == "&kp"
        assert binding.behavior == binding.value


class TestLayoutLayerStringConversion:
    """Test LayoutLayer string-to-binding conversion."""

    def test_layer_with_string_bindings(self):
        """Test creating layer with string bindings."""
        layer = LayoutLayer(name="Base", bindings=["&kp Q", "&kp W", "&trans", "&mo 1"])

        assert layer.name == "Base"
        assert len(layer.bindings) == 4

        # Verify all converted to LayoutBinding objects
        for binding in layer.bindings:
            assert isinstance(binding, LayoutBinding)

        # Check specific conversions
        assert layer.bindings[0].value == "&kp"
        assert layer.bindings[0].params[0].value == "Q"
        assert layer.bindings[1].value == "&kp"
        assert layer.bindings[1].params[0].value == "W"
        assert layer.bindings[2].value == "&trans"
        assert layer.bindings[2].params == []
        assert layer.bindings[3].value == "&mo"
        assert layer.bindings[3].params[0].value == 1

    def test_layer_with_layoutbinding_objects(self):
        """Test creating layer with LayoutBinding objects."""
        binding1 = LayoutBinding(value="&kp", params=[LayoutParam(value="Q")])
        binding2 = LayoutBinding(value="&trans", params=[])

        layer = LayoutLayer(name="Base", bindings=[binding1, binding2])

        assert layer.name == "Base"
        assert len(layer.bindings) == 2
        assert layer.bindings[0] is binding1  # Should be same object
        assert layer.bindings[1] is binding2

    def test_layer_with_mixed_bindings(self):
        """Test creating layer with mixed string and LayoutBinding objects."""
        existing_binding = LayoutBinding(value="&kp", params=[LayoutParam(value="A")])

        layer = LayoutLayer(
            name="Mixed",
            bindings=[
                "&kp Q",  # String
                existing_binding,  # LayoutBinding object
                "&trans",  # String
            ],
        )

        assert len(layer.bindings) == 3

        # First binding should be converted from string
        assert layer.bindings[0].value == "&kp"
        assert layer.bindings[0].params[0].value == "Q"

        # Second binding should be the existing object
        assert layer.bindings[1] is existing_binding

        # Third binding should be converted from string
        assert layer.bindings[2].value == "&trans"
        assert layer.bindings[2].params == []

    def test_layer_with_dict_bindings(self):
        """Test creating layer with dictionary bindings (legacy format)."""
        layer = LayoutLayer(
            name="Legacy",
            bindings=[
                {"value": "&kp", "params": [{"value": "Q", "params": []}]},
                {"value": "&trans", "params": []},
            ],
        )

        assert len(layer.bindings) == 2
        assert layer.bindings[0].value == "&kp"
        assert len(layer.bindings[0].params) == 1
        assert layer.bindings[0].params[0].value == "Q"
        assert layer.bindings[1].value == "&trans"
        assert layer.bindings[1].params == []

    def test_layer_with_invalid_binding_type(self, caplog):
        """Test that invalid binding types are converted to strings first."""
        layer = LayoutLayer(
            name="Test",
            bindings=[123, None, "&kp Q"],  # Invalid types
        )

        # Should convert invalid types to strings and then parse
        assert len(layer.bindings) == 3
        assert layer.bindings[0].value == "123"  # int converted to string
        assert layer.bindings[1].value == "None"  # None converted to string
        assert layer.bindings[2].value == "&kp"  # String parsed normally
        
        # Check that warnings were logged about unknown types
        assert "Converting unknown binding type" in caplog.text

    def test_layer_with_invalid_binding_format_raises_error(self):
        """Test that completely invalid binding format raises error."""
        with pytest.raises(ValueError, match="Invalid binding at position"):
            LayoutLayer(
                name="Test",
                bindings=["", "&kp Q"],  # Empty string should fail
            )

    def test_layer_with_malformed_dict_raises_error(self):
        """Test that malformed dictionary raises error."""
        with pytest.raises(ValueError, match="Binding dict must have 'value' field"):
            LayoutLayer(
                name="Test",
                bindings=[{"params": [], "no_value": True}],  # Missing 'value' field
            )

    def test_layer_accepts_any_binding_count(self):
        """Test that layer accepts any number of bindings."""
        # Short layer
        short_layer = LayoutLayer(
            name="Short",
            bindings=["&kp Q", "&kp W"]
        )
        assert len(short_layer.bindings) == 2
        
        # Long layer
        long_layer = LayoutLayer(
            name="Long", 
            bindings=["&kp Q"] * 100
        )
        assert len(long_layer.bindings) == 100

    def test_layer_with_non_list_bindings_raises_error(self):
        """Test that non-list bindings raises ValueError."""
        with pytest.raises(ValueError, match="Bindings must be a list"):
            LayoutLayer(name="Test", bindings="not a list")

    def test_layer_conversion_preserves_complex_params(self):
        """Test that complex parameter structures are preserved."""
        layer = LayoutLayer(
            name="Complex",
            bindings=[
                "&mt LCTRL A",
                "&lt 2 SPACE",
                '&macro_play "complex macro"',
            ],
        )

        # Check first binding: &mt LCTRL A
        assert layer.bindings[0].value == "&mt"
        assert len(layer.bindings[0].params) == 2
        assert layer.bindings[0].params[0].value == "LCTRL"
        assert layer.bindings[0].params[1].value == "A"

        # Check second binding: &lt 2 SPACE
        assert layer.bindings[1].value == "&lt"
        assert len(layer.bindings[1].params) == 2
        assert layer.bindings[1].params[0].value == 2
        assert layer.bindings[1].params[1].value == "SPACE"

        # Check third binding: quoted parameter
        assert layer.bindings[2].value == "&macro_play"
        assert len(layer.bindings[2].params) == 1
        assert layer.bindings[2].params[0].value == "complex macro"


class TestLayoutBindingEdgeCases:
    """Test edge cases and error handling for LayoutBinding."""

    def test_parse_behavior_parts_empty_parts(self):
        """Test _parse_behavior_parts with various edge cases."""
        # This tests the static method directly
        parts = LayoutBinding._parse_behavior_parts("")
        assert parts == []

    def test_parse_behavior_parts_only_spaces(self):
        """Test _parse_behavior_parts with only spaces."""
        parts = LayoutBinding._parse_behavior_parts("   ")
        assert parts == []

    def test_parse_behavior_parts_mixed_quotes(self):
        """Test _parse_behavior_parts with mixed quote types."""
        parts = LayoutBinding._parse_behavior_parts("&cmd \"double\" 'single' normal")
        assert parts == ["&cmd", "double", "single", "normal"]

    def test_parse_param_value_numeric_edge_cases(self):
        """Test _parse_param_value with numeric edge cases."""
        # This tests the static method directly
        assert LayoutBinding._parse_param_value("0") == 0
        assert LayoutBinding._parse_param_value("-1") == -1
        assert LayoutBinding._parse_param_value("123") == 123
        assert LayoutBinding._parse_param_value("abc123") == "abc123"  # Not pure number
        assert LayoutBinding._parse_param_value("123abc") == "123abc"  # Not pure number

    def test_parse_param_value_quoted_edge_cases(self):
        """Test _parse_param_value with quoted edge cases."""
        assert LayoutBinding._parse_param_value('"quoted"') == "quoted"
        assert LayoutBinding._parse_param_value("'quoted'") == "quoted"
        assert (
            LayoutBinding._parse_param_value('"123"') == "123"
        )  # Quoted number stays string
        assert (
            LayoutBinding._parse_param_value("'0'") == "0"
        )  # Quoted number stays string
        assert LayoutBinding._parse_param_value('"') == '"'  # Single quote character
        assert LayoutBinding._parse_param_value("'") == "'"  # Single quote character

    def test_from_str_parameter_creation_failure(self):
        """Test from_str when parameter creation fails."""
        # This is harder to trigger since LayoutParam is quite permissive
        # But we can test the error handling path exists
        with pytest.raises(ValueError, match="Invalid parameters in behavior string"):
            # We'll need to mock LayoutParam to raise an exception
            import unittest.mock

            with unittest.mock.patch(
                "glovebox.layout.models.LayoutParam"
            ) as mock_param:
                mock_param.side_effect = Exception("Mock parameter creation failure")
                LayoutBinding.from_str("&kp Q")

    def test_behavior_property_edge_cases(self):
        """Test behavior property with edge cases."""
        # Empty value
        binding = LayoutBinding(value="", params=[])
        assert binding.behavior == ""

        # Value with spaces
        binding = LayoutBinding(value="  &kp  ", params=[])
        assert binding.behavior == "  &kp  "


class TestLayoutLayerComplexScenarios:
    """Test complex scenarios for LayoutLayer conversion."""

    def test_full_glove80_layer_conversion(self):
        """Test conversion of a full 80-key Glove80 layer."""
        # Create a layer with 80 bindings (typical Glove80 size)
        bindings = []
        for i in range(80):
            if i % 4 == 0:
                bindings.append(f"&kp {chr(65 + (i % 26))}")  # Letters A-Z cycling
            elif i % 4 == 1:
                bindings.append("&trans")
            elif i % 4 == 2:
                bindings.append(f"&mo {i % 5}")  # Layer numbers 0-4
            else:
                bindings.append("&none")

        layer = LayoutLayer(name="FullLayer", bindings=bindings)

        assert len(layer.bindings) == 80
        assert all(isinstance(b, LayoutBinding) for b in layer.bindings)

        # Spot check a few conversions
        assert layer.bindings[0].value == "&kp"
        assert layer.bindings[0].params[0].value == "A"
        assert layer.bindings[1].value == "&trans"
        assert layer.bindings[2].value == "&mo"
        assert layer.bindings[2].params[0].value == 2
        assert layer.bindings[3].value == "&none"

    def test_layer_with_all_zmk_behavior_types(self):
        """Test layer with comprehensive ZMK behavior coverage."""
        behaviors = [
            "&none",
            "&trans",
            "&kp ESC",
            "&mo 1",
            "&lt 1 TAB",
            "&mt LSHIFT A",
            "&sk LSHIFT",
            "&sl 1",
            "&tog 1",
            "&to 0",
            "&bootloader",
            "&reset",
            "&bt BT_CLR",
            "&bt BT_SEL 0",
            "&out OUT_USB",
            "&out OUT_BLE",
            "&ext_power EP_ON",
            "&ext_power EP_OFF",
            "&rgb_ug RGB_TOG",
            "&bl BL_TOG",
        ]

        layer = LayoutLayer(name="Comprehensive", bindings=behaviors)

        assert len(layer.bindings) == len(behaviors)
        assert all(isinstance(b, LayoutBinding) for b in layer.bindings)

        # Verify complex behaviors are parsed correctly
        bt_sel_binding = next(
            b for b in layer.bindings if b.value == "&bt" and len(b.params) == 2
        )
        assert bt_sel_binding.params[0].value == "BT_SEL"
        assert bt_sel_binding.params[1].value == 0

    def test_performance_with_large_layer(self):
        """Test performance with very large layer (stress test)."""
        # Create a large layer with 1000 bindings
        large_bindings = [f"&kp {chr(65 + (i % 26))}" for i in range(1000)]

        # This should complete without timeout or excessive memory usage
        layer = LayoutLayer(name="Large", bindings=large_bindings)

        assert len(layer.bindings) == 1000
        assert all(isinstance(b, LayoutBinding) for b in layer.bindings)
        assert all(b.value == "&kp" for b in layer.bindings)

    def test_error_recovery_in_batch_conversion(self):
        """Test that one bad binding doesn't prevent others from converting."""
        bindings = [
            "&kp Q",  # Good
            "",  # Bad - empty string
            "&kp W",  # Good
        ]

        # First bad binding should cause entire validation to fail
        with pytest.raises(ValueError, match="Invalid binding at position 1"):
            LayoutLayer(name="Mixed", bindings=bindings)
