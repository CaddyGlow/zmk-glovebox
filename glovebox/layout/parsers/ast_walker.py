"""AST walker infrastructure for device tree traversal."""

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from glovebox.layout.parsers.ast_nodes import DTNode, DTProperty, DTVisitor


logger = logging.getLogger(__name__)


class DTWalker:
    """Walker for traversing device tree AST with filtering capabilities."""

    def __init__(self, root: DTNode) -> None:
        """Initialize walker.

        Args:
            root: Root node to walk
        """
        self.root = root

    def find_nodes(self, predicate: Callable[[DTNode], bool]) -> list[DTNode]:
        """Find all nodes matching predicate.

        Args:
            predicate: Function to test nodes

        Returns:
            List of matching nodes
        """
        results = []
        for node in self.root.walk():
            if predicate(node):
                results.append(node)
        return results

    def find_nodes_by_compatible(self, compatible: str) -> list[DTNode]:
        """Find nodes with specific compatible string.

        Args:
            compatible: Compatible string to search for

        Returns:
            List of matching nodes
        """
        return self.root.find_nodes_by_compatible(compatible)

    def find_nodes_by_name(self, name: str) -> list[DTNode]:
        """Find nodes with specific name.

        Args:
            name: Node name to search for

        Returns:
            List of matching nodes
        """
        return self.find_nodes(lambda node: node.name == name)

    def find_nodes_by_label(self, label: str) -> list[DTNode]:
        """Find nodes with specific label.

        Args:
            label: Node label to search for

        Returns:
            List of matching nodes
        """
        return self.find_nodes(lambda node: node.label == label)

    def find_nodes_by_path_pattern(self, pattern: str) -> list[DTNode]:
        """Find nodes whose path contains pattern.

        Args:
            pattern: Path pattern to search for

        Returns:
            List of matching nodes
        """
        return self.find_nodes(lambda node: pattern in node.path)

    def find_properties(
        self, predicate: Callable[[DTProperty], bool]
    ) -> list[tuple[DTNode, DTProperty]]:
        """Find all properties matching predicate.

        Args:
            predicate: Function to test properties

        Returns:
            List of (node, property) tuples
        """
        results = []
        for node in self.root.walk():
            for prop in node.properties.values():
                if predicate(prop):
                    results.append((node, prop))
        return results

    def find_properties_by_name(self, name: str) -> list[tuple[DTNode, DTProperty]]:
        """Find properties with specific name.

        Args:
            name: Property name to search for

        Returns:
            List of (node, property) tuples
        """
        return self.find_properties(lambda prop: prop.name == name)


class BehaviorExtractor(DTVisitor):
    """Extract behavior definitions from device tree AST."""

    def __init__(self) -> None:
        """Initialize extractor."""
        self.behaviors: list[DTNode] = []
        self.macros: list[DTNode] = []
        self.combos: list[DTNode] = []
        self.tap_dances: list[DTNode] = []
        self.hold_taps: list[DTNode] = []
        self.logger = logging.getLogger(__name__)

    def visit_node(self, node: DTNode) -> Any:
        """Visit a device tree node and extract behaviors.

        Args:
            node: Node to visit

        Returns:
            None
        """
        # Check if node has compatible property
        compatible_prop = node.get_property("compatible")
        if not compatible_prop or not compatible_prop.value:
            return

        compatible_value = compatible_prop.value.value
        if not isinstance(compatible_value, str):
            return

        # Extract different behavior types based on compatible string
        if "zmk,behavior-hold-tap" in compatible_value:
            self.hold_taps.append(node)
            self.behaviors.append(node)
        elif "zmk,behavior-macro" in compatible_value:
            self.macros.append(node)
            self.behaviors.append(node)
        elif "zmk,behavior-tap-dance" in compatible_value:
            self.tap_dances.append(node)
            self.behaviors.append(node)
        elif "zmk,behavior" in compatible_value:
            # Generic behavior
            self.behaviors.append(node)

    def visit_property(self, prop: DTProperty) -> Any:
        """Visit a property (not used for behavior extraction).

        Args:
            prop: Property to visit

        Returns:
            None
        """
        pass

    def extract_combos(self, root: DTNode) -> list[DTNode]:
        """Extract combo definitions from combos section.

        Args:
            root: Root node to search

        Returns:
            List of combo nodes
        """
        combos = []
        walker = DTWalker(root)

        # Find combos sections
        combos_sections = walker.find_nodes_by_name("combos")

        for section in combos_sections:
            # All children of combos section are combo definitions
            for child in section.children.values():
                combos.append(child)

        self.combos = combos
        return combos


class MacroExtractor:
    """Extract macro definitions from device tree AST."""

    def __init__(self) -> None:
        """Initialize extractor."""
        self.logger = logging.getLogger(__name__)

    def extract_macros(self, root: DTNode) -> list[DTNode]:
        """Extract macro definitions from macros sections.

        Args:
            root: Root node to search

        Returns:
            List of macro nodes
        """
        macros = []
        walker = DTWalker(root)

        # Find macros sections
        macros_sections = walker.find_nodes_by_name("macros")

        for section in macros_sections:
            # All children of macros section are macro definitions
            for child in section.children.values():
                # Verify this is actually a macro
                compatible_prop = child.get_property("compatible")
                if compatible_prop and compatible_prop.value:
                    compatible_value = compatible_prop.value.value
                    if (
                        isinstance(compatible_value, str)
                        and "zmk,behavior-macro" in compatible_value
                    ):
                        macros.append(child)

        return macros


class HoldTapExtractor:
    """Extract hold-tap behavior definitions from device tree AST."""

    def __init__(self) -> None:
        """Initialize extractor."""
        self.logger = logging.getLogger(__name__)

    def extract_hold_taps(self, root: DTNode) -> list[DTNode]:
        """Extract hold-tap definitions from behaviors sections.

        Args:
            root: Root node to search

        Returns:
            List of hold-tap nodes
        """
        hold_taps = []
        walker = DTWalker(root)

        # Find behaviors sections
        behaviors_sections = walker.find_nodes_by_name("behaviors")

        for section in behaviors_sections:
            # Look for hold-tap behaviors in children
            for child in section.children.values():
                compatible_prop = child.get_property("compatible")
                if compatible_prop and compatible_prop.value:
                    compatible_value = compatible_prop.value.value
                    if (
                        isinstance(compatible_value, str)
                        and "zmk,behavior-hold-tap" in compatible_value
                    ):
                        hold_taps.append(child)

        return hold_taps


class ComboExtractor:
    """Extract combo definitions from device tree AST."""

    def __init__(self) -> None:
        """Initialize extractor."""
        self.logger = logging.getLogger(__name__)

    def extract_combos(self, root: DTNode) -> list[DTNode]:
        """Extract combo definitions from combos sections.

        Args:
            root: Root node to search

        Returns:
            List of combo nodes
        """
        combos = []
        walker = DTWalker(root)

        # Find combos sections
        combos_sections = walker.find_nodes_by_name("combos")

        for section in combos_sections:
            # All children of combos section should be combo definitions
            for child in section.children.values():
                # Verify required properties for combos
                has_key_positions = child.get_property("key-positions") is not None
                has_bindings = child.get_property("bindings") is not None

                if has_key_positions and has_bindings:
                    combos.append(child)
                else:
                    self.logger.warning(
                        "Combo node '%s' missing required properties (key-positions and/or bindings)",
                        child.name,
                    )

        return combos


class UniversalBehaviorExtractor:
    """Universal behavior extractor that finds all behavior types."""

    def __init__(self) -> None:
        """Initialize extractor."""
        self.logger = logging.getLogger(__name__)

    def extract_all_behaviors(self, root: DTNode) -> dict[str, list[DTNode]]:
        """Extract all behavior types from device tree.

        Args:
            root: Root node to search

        Returns:
            Dictionary mapping behavior types to node lists
        """
        results: dict[str, list[DTNode]] = {
            "hold_taps": [],
            "macros": [],
            "combos": [],
            "tap_dances": [],
            "other_behaviors": [],
        }

        # Use individual extractors
        hold_tap_extractor = HoldTapExtractor()
        macro_extractor = MacroExtractor()
        combo_extractor = ComboExtractor()

        results["hold_taps"] = hold_tap_extractor.extract_hold_taps(root)
        results["macros"] = macro_extractor.extract_macros(root)
        results["combos"] = combo_extractor.extract_combos(root)

        # Extract tap dances and other behaviors using general approach
        walker = DTWalker(root)
        all_behaviors = walker.find_nodes_by_compatible("zmk,behavior")

        for behavior in all_behaviors:
            compatible_prop = behavior.get_property("compatible")
            if not compatible_prop or not compatible_prop.value:
                continue

            compatible_value = compatible_prop.value.value
            if not isinstance(compatible_value, str):
                continue

            # Categorize behaviors
            if "zmk,behavior-tap-dance" in compatible_value:
                results["tap_dances"].append(behavior)
            elif (
                "zmk,behavior-hold-tap" not in compatible_value
                and "zmk,behavior-macro" not in compatible_value
            ):
                # Other behavior types
                results["other_behaviors"].append(behavior)

        return results


def create_behavior_extractor() -> BehaviorExtractor:
    """Create behavior extractor instance.

    Returns:
        Configured BehaviorExtractor
    """
    return BehaviorExtractor()


def create_universal_behavior_extractor() -> UniversalBehaviorExtractor:
    """Create universal behavior extractor instance.

    Returns:
        Configured UniversalBehaviorExtractor
    """
    return UniversalBehaviorExtractor()
