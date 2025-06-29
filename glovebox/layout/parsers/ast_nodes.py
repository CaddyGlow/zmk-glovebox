"""AST node types for device tree parsing."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Union


class DTValueType(Enum):
    """Device tree value types."""

    STRING = "string"
    INTEGER = "integer"
    ARRAY = "array"
    REFERENCE = "reference"
    BOOLEAN = "boolean"


@dataclass
class DTValue:
    """Device tree property value."""

    type: DTValueType
    value: Any
    raw: str = ""  # Original text representation

    @classmethod
    def string(cls, value: str, raw: str = "") -> DTValue:
        """Create string value."""
        return cls(DTValueType.STRING, value, raw or f'"{value}"')

    @classmethod
    def integer(cls, value: int, raw: str = "") -> DTValue:
        """Create integer value."""
        return cls(DTValueType.INTEGER, value, raw or str(value))

    @classmethod
    def array(cls, values: list[int | str], raw: str = "") -> DTValue:
        """Create array value."""
        return cls(DTValueType.ARRAY, values, raw or f"<{' '.join(map(str, values))}>")

    @classmethod
    def reference(cls, ref: str, raw: str = "") -> DTValue:
        """Create reference value."""
        clean_ref = ref.lstrip("&")
        return cls(DTValueType.REFERENCE, clean_ref, raw or f"&{clean_ref}")

    @classmethod
    def boolean(cls, value: bool, raw: str = "") -> DTValue:
        """Create boolean value (property presence)."""
        return cls(DTValueType.BOOLEAN, value, raw or ("true" if value else "false"))


@dataclass
class DTProperty:
    """Device tree property."""

    name: str
    value: DTValue | None = None
    line: int = 0
    column: int = 0
    comments: list[str] = field(default_factory=list)

    @property
    def is_boolean_property(self) -> bool:
        """Check if this is a boolean property (no value)."""
        return self.value is None or self.value.type == DTValueType.BOOLEAN


@dataclass
class DTComment:
    """Device tree comment."""

    text: str
    line: int = 0
    column: int = 0
    is_block: bool = False  # True for /* */, False for //


@dataclass
class DTConditional:
    """Preprocessor conditional directive."""

    directive: str  # ifdef, ifndef, else, endif
    condition: str = ""  # The condition expression
    line: int = 0
    column: int = 0


class DTNode:
    """Device tree node."""

    def __init__(
        self,
        name: str = "",
        label: str = "",
        unit_address: str = "",
        line: int = 0,
        column: int = 0,
    ) -> None:
        """Initialize device tree node.

        Args:
            name: Node name
            label: Node label (before colon)
            unit_address: Unit address part (@address)
            line: Line number in source
            column: Column number in source
        """
        self.name = name
        self.label = label
        self.unit_address = unit_address
        self.line = line
        self.column = column
        self.properties: dict[str, DTProperty] = {}
        self.children: dict[str, DTNode] = {}
        self.comments: list[DTComment] = []
        self.conditionals: list[DTConditional] = []
        self.parent: DTNode | None = None

    @property
    def full_name(self) -> str:
        """Get full node name including unit address."""
        if self.unit_address:
            return f"{self.name}@{self.unit_address}"
        return self.name

    @property
    def path(self) -> str:
        """Get full path to this node."""
        if self.parent is None:
            return "/" if self.name == "" else f"/{self.name}"

        parent_path = self.parent.path
        if parent_path == "/":
            return f"/{self.full_name}"
        return f"{parent_path}/{self.full_name}"

    def add_property(self, prop: DTProperty) -> None:
        """Add property to node."""
        self.properties[prop.name] = prop

    def add_child(self, child: DTNode) -> None:
        """Add child node."""
        child.parent = self
        self.children[child.full_name] = child

    def get_property(self, name: str) -> DTProperty | None:
        """Get property by name."""
        return self.properties.get(name)

    def get_child(self, name: str) -> DTNode | None:
        """Get child node by name."""
        return self.children.get(name)

    def find_nodes_by_compatible(self, compatible: str) -> list[DTNode]:
        """Find all descendant nodes with given compatible string."""
        result = []

        # Check this node
        compat_prop = self.get_property("compatible")
        if (
            compat_prop
            and compat_prop.value
            and compat_prop.value.type == DTValueType.STRING
            and compatible in compat_prop.value.value
        ):
            result.append(self)

        # Check children recursively
        for child in self.children.values():
            result.extend(child.find_nodes_by_compatible(compatible))

        return result

    def find_node_by_path(self, path: str) -> DTNode | None:
        """Find node by absolute path."""
        if not path.startswith("/"):
            return None

        if path == "/":
            return self if self.name == "" else None

        parts = path.strip("/").split("/")
        current: DTNode | None = self

        for part in parts:
            if current is None:
                return None
            current = current.get_child(part)
            if current is None:
                return None

        return current

    def walk(self) -> list[DTNode]:
        """Walk all nodes in depth-first order."""
        nodes = [self]
        for child in self.children.values():
            nodes.extend(child.walk())
        return nodes

    def __repr__(self) -> str:
        """String representation."""
        label_part = f"{self.label}: " if self.label else ""
        props = len(self.properties)
        children = len(self.children)
        return (
            f"DTNode({label_part}{self.full_name}, {props} props, {children} children)"
        )


class DTVisitor(ABC):
    """Abstract visitor for traversing device tree AST."""

    @abstractmethod
    def visit_node(self, node: DTNode) -> Any:
        """Visit a device tree node."""

    @abstractmethod
    def visit_property(self, prop: DTProperty) -> Any:
        """Visit a device tree property."""

    def walk(self, root: DTNode) -> Any:
        """Walk the AST starting from root."""
        result = self.visit_node(root)

        for prop in root.properties.values():
            self.visit_property(prop)

        for child in root.children.values():
            self.walk(child)

        return result

    def walk_multiple(self, roots: list[DTNode]) -> list[Any]:
        """Walk multiple ASTs starting from multiple roots.

        Args:
            roots: List of root nodes to walk

        Returns:
            List of results from walking each root
        """
        results = []
        for root in roots:
            result = self.walk(root)
            results.append(result)
        return results


class DTParseError(Exception):
    """Device tree parsing error."""

    message: str
    line: int = 0
    column: int = 0
    context: str = ""

    def __init__(
        self, message: str, line: int = 0, column: int = 0, context: str = ""
    ) -> None:
        """Initialize DTParseError."""
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column
        self.context = context

    def __str__(self) -> str:
        """String representation of error."""
        location = (
            f" at line {self.line}, column {self.column}" if self.line > 0 else ""
        )
        context_part = f"\nContext: {self.context}" if self.context else ""
        return f"Parse error{location}: {self.message}{context_part}"
