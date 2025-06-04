"""Utilities for data serialization and conversion."""

import json
import logging
from datetime import datetime
from typing import Any, TypeVar, Union


# Type variable for generic return type
T = TypeVar("T")

logger = logging.getLogger(__name__)


def make_json_serializable(data: Any) -> Any:
    """Convert data to be JSON serializable.

    This function recursively processes data structures to make them
    JSON serializable by handling common non-serializable types like
    datetime objects.

    Args:
        data: The data to make JSON serializable, can be a dict, list, or other type

    Returns:
        A version of the data with all non-serializable types converted

    Examples:
        >>> from datetime import datetime
        >>> data = {"date": datetime.now(), "values": [1, 2, 3]}
        >>> serializable = make_json_serializable(data)
        >>> # Result has datetime converted to ISO format string
        >>> # serializable = {"date": "2025-06-01T12:34:56.789012", "values": [1, 2, 3]}
    """

    def convert_value(value: Any) -> Any:
        """Convert a value to a JSON serializable format.

        Args:
            value: The value to convert

        Returns:
            A JSON serializable version of the value
        """
        if isinstance(value, datetime):
            return value.isoformat()
        elif isinstance(value, dict):
            return {k: convert_value(v) for k, v in value.items()}
        elif isinstance(value, list | set | tuple):
            return [convert_value(item) for item in value]
        elif hasattr(value, "to_dict") and callable(value.to_dict):
            return convert_value(value.to_dict())
        else:
            return value

    result = convert_value(data)
    return result


def normalize_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize a dictionary for consistent processing.

    This function handles common data normalization tasks:
    - Ensures all string values are stripped
    - Converts empty strings to None in certain contexts
    - Ensures list values have consistent types
    - Removes None values where appropriate

    Args:
        data: The dictionary to normalize

    Returns:
        Normalized dictionary ready for processing

    Examples:
        >>> data = {"name": " Test  ", "tags": ["  tag1", "tag2  "], "value": ""}
        >>> normalize_dict(data)
        {'name': 'Test', 'tags': ['tag1', 'tag2'], 'value': None}
    """
    result = {}

    for key, value in data.items():
        # Process string values
        if isinstance(value, str):
            value = value.strip()
            # Convert empty strings to None for selected fields
            if value == "" and key in ["value", "description", "details"]:
                value = None

        # Process list values
        elif isinstance(value, list):
            # Normalize strings in lists
            if all(isinstance(item, str) for item in value):
                value = [
                    item.strip() if isinstance(item, str) else item for item in value
                ]
            # Process lists of dictionaries recursively
            elif all(isinstance(item, dict) for item in value):
                value = [normalize_dict(item) for item in value]

        # Process nested dictionaries recursively
        elif isinstance(value, dict):
            value = normalize_dict(value)

        # Skip None values for selected fields to reduce output size
        if value is None and key in ["notes", "tags", "metadata"]:
            continue

        result[key] = value

    return result


def parse_iso_datetime(date_string: str) -> datetime:
    """Parse an ISO 8601 datetime string to a datetime object.

    Args:
        date_string: String in ISO 8601 format (e.g. "2025-06-01T12:34:56.789012")

    Returns:
        A datetime object

    Raises:
        ValueError: If the string is not a valid ISO 8601 datetime

    Examples:
        >>> parse_iso_datetime("2025-06-01T12:34:56.789012")
        datetime.datetime(2025, 6, 1, 12, 34, 56, 789012)
    """
    try:
        return datetime.fromisoformat(date_string)
    except ValueError as e:
        logger.error(f"Failed to parse datetime string: {date_string}")
        raise ValueError(f"Invalid datetime format: {date_string}") from e


class GloveboxJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for Glovebox data.

    This encoder handles special types like datetime objects, sets, and objects
    with to_dict methods, making them serializable to JSON.

    Usage:
        json.dumps(data, cls=GloveboxJSONEncoder)
    """

    def default(self, obj: Any) -> Any:
        """Handle non-JSON-serializable objects.

        Args:
            obj: The object to encode

        Returns:
            A JSON-serializable version of the object
        """
        if isinstance(obj, datetime):
            # Convert datetime to UNIX timestamp (seconds since epoch)
            # This matches the Moergo JSON format
            return int(obj.timestamp())
        elif isinstance(obj, set):
            return list(obj)
        elif hasattr(obj, "to_dict") and callable(obj.to_dict):
            return obj.to_dict()
        # Let the parent class handle standard types or raise TypeError
        return super().default(obj)
