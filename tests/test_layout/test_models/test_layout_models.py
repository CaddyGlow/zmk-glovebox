"""Unit tests for layout models timestamp serialization."""

import json
from datetime import UTC, datetime, timezone
from pathlib import Path

import pytest

from glovebox.layout.models import KeymapResult, LayoutData, LayoutResult


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
        regular_data = layout.model_dump()
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
        regular_data = result.model_dump()
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
        regular_data = result.model_dump()
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
