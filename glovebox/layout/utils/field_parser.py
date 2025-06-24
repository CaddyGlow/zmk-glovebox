"""Field path parsing utilities for layout editing operations."""

from typing import Any


def parse_field_path(field_path: str) -> list[str]:
    """Parse field path into parts, handling array indices.

    Supports dot notation and bracket notation for nested field access.
    Examples: 'title', 'layer_names[0]', 'config_parameters[0].paramName'

    Args:
        field_path: Field path string with dot notation and array indexing

    Returns:
        List of path parts including bracket notation for indices
    """
    parts = []
    current_part = ""
    i = 0

    while i < len(field_path):
        char = field_path[i]
        if char == "[":
            # Find matching closing bracket
            if current_part:
                parts.append(current_part)
                current_part = ""
            bracket_count = 1
            index_start = i + 1
            i += 1
            while i < len(field_path) and bracket_count > 0:
                if field_path[i] == "[":
                    bracket_count += 1
                elif field_path[i] == "]":
                    bracket_count -= 1
                i += 1
            index_str = field_path[index_start : i - 1]
            parts.append(f"[{index_str}]")
        elif char == ".":
            if current_part:
                parts.append(current_part)
                current_part = ""
            i += 1
        else:
            current_part += char
            i += 1

    if current_part:
        parts.append(current_part)

    return parts


def _resolve_pydantic_field_alias(model: Any, field_name: str) -> str | None:
    """Resolve a Pydantic field alias to the actual Python attribute name.

    Args:
        model: Pydantic model instance
        field_name: Field name that might be an alias

    Returns:
        Actual Python attribute name if field_name is an alias, None otherwise
    """
    # Check if this is a Pydantic model
    if not hasattr(model, "model_fields"):
        return None

    # Iterate through model fields to find alias matches
    for python_name, field_info in model.model_fields.items():
        # Check if field_name matches the alias
        if hasattr(field_info, "alias") and field_info.alias == field_name:
            return str(python_name)

    return None


def extract_field_value_from_model(model: Any, field_path: str) -> Any:
    """Extract a field value directly from a Pydantic model.

    Args:
        model: Pydantic model instance
        field_path: Field path with dot notation and array indexing

    Returns:
        Field value from the model

    Raises:
        KeyError: If field path is not found
        ValueError: If array index is invalid
    """
    parts = parse_field_path(field_path)
    current = model

    for part in parts:
        if part.startswith("[") and part.endswith("]"):
            # Array index access
            index_str = part[1:-1]
            try:
                index = int(index_str)
                if hasattr(current, "__getitem__"):
                    current = current[index]
                else:
                    raise ValueError(
                        f"Cannot index non-indexable value with [{index_str}]"
                    )
            except (ValueError, IndexError) as e:
                raise ValueError(f"Invalid array index: {index_str}") from e
        else:
            # Attribute/key access
            if isinstance(current, dict):
                # For dictionaries, access keys directly
                if part in current:
                    current = current[part]
                else:
                    raise KeyError(f"Key '{part}' not found in dictionary")
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                # Check if this is a Pydantic model with field aliases
                resolved_field = _resolve_pydantic_field_alias(current, part)
                if resolved_field is not None:
                    current = getattr(current, resolved_field)
                else:
                    raise KeyError(f"Field '{part}' not found")

    return current


def set_field_value_on_model(model: Any, field_path: str, value: Any) -> None:
    """Set a field value directly on a Pydantic model.

    Args:
        model: Pydantic model instance
        field_path: Field path with dot notation and array indexing
        value: Value to set

    Raises:
        KeyError: If field path is not found
        ValueError: If array index is invalid
    """
    parts = parse_field_path(field_path)
    current = model

    # Navigate to the parent
    for part in parts[:-1]:
        if part.startswith("[") and part.endswith("]"):
            # Array index access
            index_str = part[1:-1]
            try:
                index = int(index_str)
                if hasattr(current, "__getitem__"):
                    current = current[index]
                else:
                    raise ValueError(
                        f"Cannot index non-indexable value with [{index_str}]"
                    )
            except (ValueError, IndexError) as e:
                raise ValueError(f"Invalid array index: {index_str}") from e
        else:
            # Attribute/key access
            if isinstance(current, dict):
                # For dictionaries, create missing keys
                if part not in current:
                    current[part] = {}
                current = current[part]
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                raise KeyError(f"Field '{part}' not found")

    # Set the final field
    final_part = parts[-1]
    if final_part.startswith("[") and final_part.endswith("]"):
        # Array index access
        index_str = final_part[1:-1]
        try:
            index = int(index_str)
            if hasattr(current, "__setitem__"):
                # For lists, extend if index is beyond current length
                if isinstance(current, list) and index >= len(current):
                    # Extend list with None values up to the desired index
                    current.extend([None] * (index - len(current) + 1))
                current[index] = value
            else:
                raise ValueError(
                    f"Cannot set index on non-indexable value with [{index_str}]"
                )
        except (ValueError, IndexError) as e:
            raise ValueError(f"Invalid array index: {index_str}") from e
    else:
        # Attribute/key access for final field
        if isinstance(current, dict):
            # For dictionaries, always allow creating new keys
            current[final_part] = value
        elif hasattr(current, final_part):
            setattr(current, final_part, value)
        else:
            # For Pydantic models, try to set the attribute even if it doesn't exist
            # This handles optional fields that may not be initialized
            try:
                setattr(current, final_part, value)
            except AttributeError:
                raise KeyError(f"Field '{final_part}' not found") from None

def unset_field_value_on_model(model: Any, field_path: str) -> None:
    """Remove a field value from a Pydantic model.

    Args:
        model: Pydantic model instance
        field_path: Field path with dot notation and array indexing

    Raises:
        KeyError: If field path is not found
        ValueError: If array index is invalid or operation not supported
    """
    parts = parse_field_path(field_path)
    current = model

    # Navigate to the parent
    for part in parts[:-1]:
        if part.startswith("[") and part.endswith("]"):
            # Array index access
            index_str = part[1:-1]
            try:
                index = int(index_str)
                if hasattr(current, "__getitem__"):
                    current = current[index]
                else:
                    raise ValueError(
                        f"Cannot index non-indexable value with [{index_str}]"
                    )
            except (ValueError, IndexError) as e:
                raise ValueError(f"Invalid array index: {index_str}") from e
        else:
            # Attribute/key access
            if isinstance(current, dict):
                if part in current:
                    current = current[part]
                else:
                    raise KeyError(f"Key '{part}' not found in dictionary")
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                raise KeyError(f"Field '{part}' not found")

    # Remove the final field
    final_part = parts[-1]
    if final_part.startswith("[") and final_part.endswith("]"):
        # Array index access - remove from list
        index_str = final_part[1:-1]
        try:
            index = int(index_str)
            if isinstance(current, list):
                if 0 <= index < len(current):
                    current.pop(index)
                else:
                    raise ValueError(f"Index {index} out of range for list of length {len(current)}")
            else:
                raise ValueError(
                    f"Cannot remove index from non-list value with [{index_str}]"
                )
        except (ValueError, IndexError) as e:
            raise ValueError(f"Invalid array index: {index_str}") from e
    else:
        # Attribute/key access for final field
        if isinstance(current, dict):
            # For dictionaries, remove the key
            if final_part in current:
                del current[final_part]
            else:
                raise KeyError(f"Key '{final_part}' not found in dictionary")
        elif hasattr(current, final_part):
            # For Pydantic models, try to set to None or default value
            # This is safer than deleting attributes on Pydantic models
            try:
                setattr(current, final_part, None)
            except Exception as e:
                raise ValueError(f"Cannot unset field '{final_part}': {e}") from e
        else:
            raise KeyError(f"Field '{final_part}' not found")


def parse_field_value(value_str: str, value_type: str) -> Any:
    """Parse a string value based on the specified type.

    Args:
        value_str: String value to parse
        value_type: Type to parse as ('auto', 'string', 'number', 'boolean', 'json')

    Returns:
        Parsed value

    Raises:
        ValueError: If value cannot be parsed as specified type
    """
    import json

    if value_type == "string":
        return value_str
    elif value_type == "number":
        try:
            # Try integer first
            if "." not in value_str:
                return int(value_str)
            else:
                return float(value_str)
        except ValueError as e:
            raise ValueError(f"Cannot parse '{value_str}' as number") from e
    elif value_type == "boolean":
        if value_str.lower() in ("true", "1", "yes", "on"):
            return True
        elif value_str.lower() in ("false", "0", "no", "off"):
            return False
        else:
            raise ValueError(f"Cannot parse '{value_str}' as boolean")
    elif value_type == "json":
        try:
            return json.loads(value_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Cannot parse '{value_str}' as JSON: {e}") from e
    else:  # auto
        # Try to automatically determine the type
        if value_str.lower() in ("true", "false"):
            return value_str.lower() == "true"

        # Try number
        try:
            if "." in value_str:
                return float(value_str)
            else:
                return int(value_str)
        except ValueError:
            pass

        # Try JSON for complex types
        if value_str.startswith(("{", "[")):
            try:
                return json.loads(value_str)
            except json.JSONDecodeError:
                pass

        # Default to string
        return value_str
