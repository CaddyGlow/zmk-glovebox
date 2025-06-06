"""Behavior type definitions for ZMK keyboard behaviors.

This module defines type classes for behaviors used in keyboard configuration
and keymap processing. These types ensure consistent representation of behaviors
across the application and improve type safety.
"""

from typing import Any, TypeAlias, TypedDict

from .keymap import ParamValue


# Type aliases for common parameter types
ParamList: TypeAlias = list["BehaviorParameter"]
CommandList: TypeAlias = list["BehaviorCommand"]
StringList: TypeAlias = list[str]
SystemParamList: TypeAlias = list["SystemBehaviorParam"]


class BehaviorParameter(TypedDict, total=False):
    """Type definition for a behavior parameter."""

    name: str
    type: str
    min: int | None
    max: int | None
    values: list[Any] | None
    default: Any
    description: str
    required: bool


class BehaviorCommand(TypedDict, total=False):
    """Type definition for a behavior command."""

    code: str
    name: str | None
    description: str | None
    flatten: bool
    additional_params: ParamList | None


class RegistryBehavior(TypedDict):
    """Type definition for a behavior in the registry.
    These are behaviors that are registered in the system and can be referenced
    by keymap bindings.
    """

    expected_params: int
    origin: str
    description: str
    url: str | None
    params: ParamList
    commands: CommandList | None
    includes: StringList | None


class SystemBehaviorParam(TypedDict, total=False):
    """Type definition for system behavior parameter.
    These are parameters used within keymap behavior references.
    """

    value: Any
    params: SystemParamList


# Recursive type reference
SystemBehaviorParam.__annotations__["params"] = SystemParamList


class SystemBehavior(TypedDict, total=False):
    """Type definition for a behavior directly referenced in a keymap.
    This represents a complete behavior definition that can be used in a keymap,
    including all its parameters, commands, and metadata.
    """

    type: str
    parameters: dict[str, Any]
    bindings: dict[str, Any]
    code: str
    name: str
    description: str | None
    expected_params: int
    origin: str
    params: ParamList
    url: str | None
    is_macro_control_behavior: bool
    includes: StringList | None
    commands: CommandList | None


class KeymapBehavior(TypedDict):
    """Type definition for a behavior reference in a keymap.
    This is a simplified representation of a behavior used in keymap bindings.
    It contains just the value and parameters needed for the binding.
    """

    value: str
    params: SystemParamList
