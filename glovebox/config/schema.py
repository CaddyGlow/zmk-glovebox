"""
JSON schema for keyboard configuration validation.

This module provides a JSON schema for validating keyboard configuration files.
The schema is based on the structure of the KeyboardConfig dataclass and
ensures that all required fields are present and have the correct types.
"""

from typing import Any


# Schema for parameter
PARAMETER_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "type": {"type": "string"},
        "min": {"type": "integer"},
        "max": {"type": "integer"},
        "values": {"type": "array"},
    },
    "required": ["name", "type"],
}

# Schema for behavior command
BEHAVIOR_COMMAND_SCHEMA = {
    "type": "object",
    "properties": {
        "code": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": "string"},
        "flatten": {"type": "boolean"},
        "additionalParams": {"type": "array", "items": PARAMETER_SCHEMA},
    },
    "required": ["code"],
}

# Schema for system behavior
SYSTEM_BEHAVIOR_SCHEMA = {
    "type": "object",
    "properties": {
        "code": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": "string"},
        "expected_params": {"type": "integer"},
        "origin": {"type": "string"},
        "params": {
            "type": "array",
            "items": {"oneOf": [{"type": "string"}, PARAMETER_SCHEMA]},
        },
        "url": {"type": "string"},
        "isMacroControlBehavior": {"type": "boolean"},
        "includes": {"type": "array", "items": {"type": "string"}},
        "commands": {"type": "array", "items": BEHAVIOR_COMMAND_SCHEMA},
    },
    "required": ["code", "name", "expected_params", "origin", "params"],
}

# Schema for KConfig option
KCONFIG_OPTION_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "type": {"type": "string"},
        "default": {},  # Any type is valid for default
        "description": {"type": "string"},
    },
    "required": ["name", "type", "default", "description"],
}

# Schema for flash config
FLASH_CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "method": {"type": "string"},
        "query": {"type": "string"},
        "usb_vid": {"type": "string"},
        "usb_pid": {"type": "string"},
    },
    "required": ["method", "query", "usb_vid", "usb_pid"],
}

# Schema for build config
BUILD_CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "method": {"type": "string"},
        "docker_image": {"type": "string"},
        "repository": {"type": "string"},
        "branch": {"type": "string"},
    },
    "required": ["method", "docker_image", "repository", "branch"],
}

# Schema for visual layout
VISUAL_LAYOUT_SCHEMA = {
    "type": "object",
    "properties": {
        "rows": {
            "type": "array",
            "items": {"type": "array", "items": {"type": "integer"}},
        }
    },
    "required": ["rows"],
}

# Schema for formatting config
FORMATTING_CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "default_key_width": {"type": "integer"},
        "key_gap": {"type": "string"},
        "base_indent": {"type": "string"},
    },
    "required": ["default_key_width", "key_gap"],
}

# Schema for build options
BUILD_OPTIONS_SCHEMA = {
    "type": "object",
    "properties": {"repository": {"type": "string"}, "branch": {"type": "string"}},
    "required": ["repository", "branch"],
}

# Schema for firmware config
FIRMWARE_CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "version": {"type": "string"},
        "description": {"type": "string"},
        "build_options": BUILD_OPTIONS_SCHEMA,
        "kconfig": {"type": "object", "additionalProperties": KCONFIG_OPTION_SCHEMA},
    },
    "required": ["version", "description", "build_options"],
}

# Schema for keymap section
KEYMAP_SECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "includes": {"type": "array", "items": {"type": "string"}},
        "formatting": {
            "type": "object",
            "properties": {
                "default_key_width": {"type": "integer"},
                "key_gap": {"type": "string"},
                "base_indent": {"type": "string"},
                "rows": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "integer"}},
                },
            },
            "required": ["default_key_width", "key_gap"],
        },
        "system_behaviors": {"type": "array", "items": SYSTEM_BEHAVIOR_SCHEMA},
        "kconfig_options": {
            "type": "object",
            "additionalProperties": KCONFIG_OPTION_SCHEMA,
        },
        "keymap_dtsi": {"type": "string"},
        "system_behaviors_dts": {"type": "string"},
        "key_position_header": {"type": "string"},
    },
    "required": ["includes", "formatting", "system_behaviors", "kconfig_options"],
}

# Complete keyboard configuration schema
KEYBOARD_CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "keyboard": {"type": "string"},
        "description": {"type": "string"},
        "vendor": {"type": "string"},
        "key_count": {"type": "integer"},
        "flash": FLASH_CONFIG_SCHEMA,
        "build": BUILD_CONFIG_SCHEMA,
        "firmwares": {"type": "object", "additionalProperties": FIRMWARE_CONFIG_SCHEMA},
        "keymap": KEYMAP_SECTION_SCHEMA,
    },
    "required": [
        "keyboard",
        "description",
        "vendor",
        "key_count",
        "flash",
        "build",
    ],
}


def validate_keyboard_config(config: dict[str, Any]) -> dict[str, Any]:
    """
    Validate a keyboard configuration against the schema.

    Args:
        config: The keyboard configuration to validate

    Returns:
        The validated configuration (unmodified)

    Raises:
        ConfigError: If the configuration is invalid
    """
    # Basic validation - check required fields
    for field in KEYBOARD_CONFIG_SCHEMA["required"]:
        if field not in config:
            from glovebox.core.errors import ConfigError

            raise ConfigError(f"Missing required field: {field}")

    # Return the config - schema validation is optional for now
    return config
