"""Behavior type definitions for ZMK keyboard behaviors.

This module defines type classes for behaviors used in keyboard configuration
and keymap processing. These types ensure consistent representation of behaviors
across the application and improve type safety.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, TypeAlias

from .keymap import ParamValue


# Parameter type definitions
class ParameterType(Enum):
    """Enum for behavior parameter types."""

    INTEGER = auto()
    STRING = auto()
    BOOLEAN = auto()
    ENUM = auto()
    CODE = auto()
    LAYER = auto()
    COMMAND = auto()


# Type aliases for common parameter types
ParamList: TypeAlias = list["BehaviorParameter"]
CommandList: TypeAlias = list["BehaviorCommand"]
StringList: TypeAlias = list[str]
SystemParamList: TypeAlias = list["SystemBehaviorParam"]


@dataclass
class BehaviorParameter:
    """Definition of a parameter for a behavior."""

    name: str
    type: str
    min: int | None = None
    max: int | None = None
    values: list[Any] | None = None
    default: Any = None
    description: str = ""
    required: bool = False


@dataclass
class BehaviorCommand:
    """Definition of a command for a behavior."""

    code: str
    name: str | None = None
    description: str | None = None
    flatten: bool = False
    additional_params: ParamList | None = None


@dataclass
class RegistryBehavior:
    """Definition for a behavior in the registry.
    These are behaviors that are registered in the system and can be referenced
    by keymap bindings.
    """

    expected_params: int
    origin: str
    description: str
    params: ParamList
    url: str | None = None
    commands: CommandList | None = None
    includes: StringList | None = None


@dataclass
class SystemBehaviorParam:
    """Definition for system behavior parameter.
    These are parameters used within keymap behavior references.
    """

    value: Any = None
    params: SystemParamList = field(default_factory=list)


@dataclass
class SystemBehavior:
    """Definition for a behavior directly referenced in a keymap.
    This represents a complete behavior definition that can be used in a keymap,
    including all its parameters, commands, and metadata.
    """

    code: str
    name: str
    description: str | None
    expected_params: int
    origin: str
    params: ParamList
    url: str | None = None
    is_macro_control_behavior: bool = False
    includes: StringList | None = None
    commands: CommandList | None = None
    type: str | None = None
    parameters: dict[str, Any] | None = None
    bindings: dict[str, Any] | None = None


@dataclass
class KeymapBehavior:
    """Definition for a behavior reference in a keymap.
    This is a simplified representation of a behavior used in keymap bindings.
    It contains just the value and parameters needed for the binding.
    """

    value: str
    params: SystemParamList = field(default_factory=list)
