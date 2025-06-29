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


class DTMultiWalker:
    """Walker for traversing multiple device tree ASTs with filtering capabilities."""

    def __init__(self, roots: list[DTNode]) -> None:
        """Initialize multi-walker.

        Args:
            roots: List of root nodes to walk
        """
        self.roots = roots

    def find_nodes(self, predicate: Callable[[DTNode], bool]) -> list[DTNode]:
        """Find all nodes matching predicate across all roots.

        Args:
            predicate: Function to test nodes

        Returns:
            List of matching nodes
        """
        results = []
        for root in self.roots:
            for node in root.walk():
                if predicate(node):
                    results.append(node)
        return results

    def find_nodes_by_compatible(self, compatible: str) -> list[DTNode]:
        """Find nodes with specific compatible string across all roots.

        Args:
            compatible: Compatible string to search for

        Returns:
            List of matching nodes
        """
        results = []
        for root in self.roots:
            results.extend(root.find_nodes_by_compatible(compatible))
        return results

    def find_nodes_by_name(self, name: str) -> list[DTNode]:
        """Find nodes with specific name across all roots.

        Args:
            name: Node name to search for

        Returns:
            List of matching nodes
        """
        return self.find_nodes(lambda node: node.name == name)

    def find_nodes_by_label(self, label: str) -> list[DTNode]:
        """Find nodes with specific label across all roots.

        Args:
            label: Node label to search for

        Returns:
            List of matching nodes
        """
        return self.find_nodes(lambda node: node.label == label)

    def find_nodes_by_path_pattern(self, pattern: str) -> list[DTNode]:
        """Find nodes whose path contains pattern across all roots.

        Args:
            pattern: Path pattern to search for

        Returns:
            List of matching nodes
        """
        return self.find_nodes(lambda node: pattern in node.path)

    def find_properties(
        self, predicate: Callable[[DTProperty], bool]
    ) -> list[tuple[DTNode, DTProperty]]:
        """Find all properties matching predicate across all roots.

        Args:
            predicate: Function to test properties

        Returns:
            List of (node, property) tuples
        """
        results = []
        for root in self.roots:
            for node in root.walk():
                for prop in node.properties.values():
                    if predicate(prop):
                        results.append((node, prop))
        return results

    def find_properties_by_name(self, name: str) -> list[tuple[DTNode, DTProperty]]:
        """Find properties with specific name across all roots.

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


class MetadataExtractor:
    """Extract metadata and comments from device tree AST for round-trip preservation."""

    def __init__(self) -> None:
        """Initialize metadata extractor."""
        self.comments: list[dict[str, Any]] = []
        self.includes: list[dict[str, Any]] = []
        self.config_directives: list[dict[str, Any]] = []
        self.original_header: str = ""
        self.original_footer: str = ""
        self.custom_sections: dict[str, str] = {}
        self.logger = logging.getLogger(__name__)

    def extract_metadata(
        self, roots: list[DTNode], source_content: str = ""
    ) -> dict[str, Any]:
        """Extract comprehensive metadata from AST roots and source content.

        Args:
            roots: List of AST root nodes
            source_content: Original source file content for header/footer extraction

        Returns:
            Dictionary containing extracted metadata
        """
        # Extract comments from all nodes
        self._extract_comments_from_nodes(roots)

        # Extract includes and config directives
        self._extract_includes_and_directives(roots)

        # Extract header and footer sections from source content
        if source_content:
            self._extract_header_footer(source_content)

        # Build dependency information (Phase 4.3)
        dependencies = self._build_dependency_info()

        return {
            "comments": self.comments,
            "includes": self.includes,
            "config_directives": self.config_directives,
            "original_header": self.original_header,
            "original_footer": self.original_footer,
            "custom_sections": self.custom_sections,
            "dependencies": dependencies,
        }

    def _extract_comments_from_nodes(self, roots: list[DTNode]) -> None:
        """Extract comments from all nodes in the AST."""
        for root in roots:
            self._walk_node_for_comments(root, context="root")

    def _walk_node_for_comments(self, node: DTNode, context: str = "") -> None:
        """Recursively walk node to extract comments."""
        # Extract comments from this node
        for comment in node.comments:
            self.comments.append(
                {
                    "text": comment.text,
                    "line": comment.line,
                    "context": self._determine_comment_context(node, context),
                    "is_block": comment.is_block,
                }
            )

        # Extract comments from properties
        for prop in node.properties.values():
            for comment in prop.comments:
                self.comments.append(
                    {
                        "text": comment.text,
                        "line": comment.line,
                        "context": f"property:{prop.name}",
                        "is_block": False,  # Property comments are typically line comments
                    }
                )

        # Recursively process children
        for child in node.children.values():
            child_context = self._determine_child_context(child)
            self._walk_node_for_comments(child, child_context)

    def _determine_comment_context(self, node: DTNode, parent_context: str) -> str:
        """Determine the context of a comment based on its node."""
        if not node.name:
            return "header"

        # Check if this is a behavior node
        compatible_prop = node.get_property("compatible")
        if compatible_prop and compatible_prop.value:
            compatible_value = compatible_prop.value.value
            if isinstance(compatible_value, str) and "zmk,behavior" in compatible_value:
                return "behavior"

        # Check for special sections
        if node.name in ["combos", "behaviors", "keymap"]:
            return node.name

        return parent_context or "general"

    def _determine_child_context(self, child: DTNode) -> str:
        """Determine context for child nodes."""
        if child.name in ["combos", "behaviors", "keymap"]:
            return child.name
        return "child"

    def _extract_includes_and_directives(self, roots: list[DTNode]) -> None:
        """Extract include directives and config directives from AST."""
        for root in roots:
            # Look for conditional directives in the AST
            for conditional in root.conditionals:
                self.config_directives.append(
                    {
                        "directive": conditional.directive,
                        "condition": conditional.condition,
                        "value": "",
                        "line": conditional.line,
                    }
                )

    def _extract_header_footer(self, source_content: str) -> None:
        """Extract header and footer sections from source content."""
        lines = source_content.split("\n")

        # Enhanced extraction with include directive detection (Phase 4.2)
        self._extract_includes_from_source(lines)
        self._extract_config_directives_from_source(lines)

        # Find first significant content (usually first node declaration)
        first_content_line = 0
        last_content_line = len(lines) - 1

        # Look for first non-comment, non-empty line that looks like node content
        for i, line in enumerate(lines):
            stripped = line.strip()
            if (
                stripped
                and not stripped.startswith("//")
                and not stripped.startswith("/*")
                and not stripped.startswith("#")  # Skip preprocessor directives
                and ("{" in stripped or stripped.endswith(";"))
            ):
                first_content_line = i
                break

        # Look for last significant content line
        for i in range(len(lines) - 1, -1, -1):
            stripped = lines[i].strip()
            if (
                stripped
                and not stripped.startswith("//")
                and not stripped.startswith("*/")
                and not stripped.startswith("#")  # Skip preprocessor directives
                and ("}" in stripped or stripped.endswith(";"))
            ):
                last_content_line = i
                break

        # Extract header (everything before first content)
        if first_content_line > 0:
            self.original_header = "\n".join(lines[:first_content_line]).strip()

        # Extract footer (everything after last content)
        if last_content_line < len(lines) - 1:
            self.original_footer = "\n".join(lines[last_content_line + 1 :]).strip()

    def _extract_includes_from_source(self, lines: list[str]) -> None:
        """Extract include directives from source lines (Phase 4.2)."""
        import re

        include_pattern = re.compile(r'^\s*#include\s+[<"]([^>"]+)[>"]')

        for line_num, line in enumerate(lines, 1):
            match = include_pattern.match(line)
            if match:
                include_path = match.group(1)
                resolved_path = self._resolve_include_path(include_path, line)

                self.includes.append(
                    {
                        "path": include_path,
                        "line": line_num,
                        "resolved_path": resolved_path,
                    }
                )

    def _resolve_include_path(self, include_path: str, line: str) -> str:
        """Resolve include path to actual file path (Phase 4.3).

        Args:
            include_path: Include path from #include directive
            line: Full line text for context

        Returns:
            Resolved file path or empty string if not found
        """
        from pathlib import Path

        # Determine include type based on brackets vs quotes
        is_system_include = "<" in line and ">" in line
        is_local_include = '"' in line

        # Try common ZMK include search paths
        search_paths = []

        if is_system_include:
            # System includes: search in ZMK system directories
            search_paths.extend(
                [
                    Path("~/zmk/app/include") / include_path,
                    Path("/opt/zmk/include") / include_path,
                    Path("./zmk/app/include") / include_path,
                    Path("./include") / include_path,
                ]
            )

        if is_local_include:
            # Local includes: search relative to current directory
            search_paths.extend(
                [
                    Path(include_path),
                    Path("./config") / include_path,
                    Path("..") / include_path,
                ]
            )

        # Try to resolve each search path
        for search_path in search_paths:
            try:
                expanded_path = search_path.expanduser().resolve()
                if expanded_path.exists():
                    return str(expanded_path)
            except (OSError, RuntimeError):
                # Path resolution failed, continue to next
                continue

        # If no actual file found, return the original path with classification
        classification = "system" if is_system_include else "local"
        return f"[{classification}] {include_path}"

    def _extract_config_directives_from_source(self, lines: list[str]) -> None:
        """Extract configuration directives from source lines (Phase 4.2)."""
        import re

        # Pattern for various preprocessor directives
        directive_pattern = re.compile(r"^\s*#(\w+)(?:\s+(.*))?")

        for line_num, line in enumerate(lines, 1):
            match = directive_pattern.match(line)
            if match:
                directive = match.group(1)
                condition_or_value = match.group(2) or ""

                # Skip include directives as they're handled separately
                if directive == "include":
                    continue

                # Categorize directive types
                if directive in ["ifdef", "ifndef", "if"]:
                    self.config_directives.append(
                        {
                            "directive": directive,
                            "condition": condition_or_value,
                            "value": "",
                            "line": line_num,
                        }
                    )
                elif directive in ["define", "undef"]:
                    # Split define into name and value
                    parts = condition_or_value.split(None, 1)
                    condition = parts[0] if parts else ""
                    value = parts[1] if len(parts) > 1 else ""

                    self.config_directives.append(
                        {
                            "directive": directive,
                            "condition": condition,
                            "value": value,
                            "line": line_num,
                        }
                    )
                else:
                    # Handle other directives (else, endif, etc.)
                    self.config_directives.append(
                        {
                            "directive": directive,
                            "condition": condition_or_value,
                            "value": "",
                            "line": line_num,
                        }
                    )

    def _build_dependency_info(self) -> dict[str, Any]:
        """Build dependency information from extracted includes (Phase 4.3).

        Returns:
            Dictionary with dependency information
        """
        dependencies: dict[str, Any] = {
            "include_dependencies": [],
            "behavior_sources": {},
            "unresolved_includes": [],
        }

        for include in self.includes:
            include_path = include["path"]
            resolved_path = include["resolved_path"]

            # Add to dependencies list
            if resolved_path and not resolved_path.startswith("["):
                # Successfully resolved to actual file
                dependencies["include_dependencies"].append(resolved_path)

                # Try to infer behavior sources from common ZMK include patterns
                if "behaviors" in include_path.lower():
                    # This include likely provides behaviors
                    dependencies["behavior_sources"]["[behaviors_dtsi]"] = include_path
                elif "keys" in include_path.lower():
                    dependencies["behavior_sources"]["[key_definitions]"] = include_path
                elif "bt" in include_path.lower():
                    dependencies["behavior_sources"]["[bluetooth]"] = include_path
            else:
                # Unresolved include
                dependencies["unresolved_includes"].append(include_path)

        return dependencies


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
    """Universal behavior extractor that finds all behavior types and metadata."""

    def __init__(self) -> None:
        """Initialize extractor."""
        self.logger = logging.getLogger(__name__)

        # Enhanced behavior patterns for better detection
        self.behavior_patterns = {
            "hold_taps": [
                "zmk,behavior-hold-tap",
                "zmk,behavior-tap-hold",  # Alternative naming
            ],
            "macros": [
                "zmk,behavior-macro",
                "zmk,behavior-sequence",  # Custom macro types
            ],
            "tap_dances": [
                "zmk,behavior-tap-dance",
                "zmk,behavior-multi-tap",  # Alternative naming
            ],
            "combos": [
                "zmk,behavior-combo",  # Some custom implementations
            ],
            "caps_word": [
                "zmk,behavior-caps-word",
                "zmk,behavior-capsword",
            ],
            "sticky_keys": [
                "zmk,behavior-sticky-key",
                "zmk,behavior-sk",
            ],
            "layers": [
                "zmk,behavior-momentary-layer",
                "zmk,behavior-toggle-layer",
                "zmk,behavior-layer-tap",
            ],
            "mods": [
                "zmk,behavior-mod-morph",
                "zmk,behavior-modifier",
            ],
        }

        # Cache for improved performance
        self._behavior_cache: dict[str, list[DTNode]] = {}

        # Metadata extractor for enhanced preservation (Phase 4.1)
        self.metadata_extractor = MetadataExtractor()

        # AST behavior converter for comment-aware conversion
        self.ast_converter: Any = None

    def extract_all_behaviors(self, root: DTNode) -> dict[str, list[DTNode]]:
        """Extract all behavior types from single device tree root.

        Args:
            root: Root node to search

        Returns:
            Dictionary mapping behavior types to node lists
        """
        return self._extract_behaviors_from_roots([root])

    def extract_all_behaviors_multiple(
        self, roots: list[DTNode]
    ) -> dict[str, list[DTNode]]:
        """Extract all behavior types from multiple device tree roots.

        Args:
            roots: List of root nodes to search

        Returns:
            Dictionary mapping behavior types to node lists
        """
        return self._extract_behaviors_from_roots(roots)

    def extract_behaviors_with_metadata(
        self, roots: list[DTNode], source_content: str = ""
    ) -> tuple[dict[str, list[DTNode]], dict]:
        """Extract behaviors and metadata for enhanced round-trip preservation.

        Args:
            roots: List of root nodes to search
            source_content: Original source file content for metadata extraction

        Returns:
            Tuple of (behaviors dict, metadata dict)
        """
        # Extract behaviors using existing logic
        behaviors = self._extract_behaviors_from_roots(roots)

        # Extract metadata using metadata extractor
        metadata = self.metadata_extractor.extract_metadata(roots, source_content)

        return behaviors, metadata

    def extract_behaviors_as_models(
        self, roots: list[DTNode], source_content: str = ""
    ) -> tuple[dict[str, list[Any]], dict]:
        """Extract behaviors as behavior model objects with comments.

        Args:
            roots: List of root nodes to search
            source_content: Original source file content for metadata extraction

        Returns:
            Tuple of (behavior_models_dict, metadata_dict)
        """
        # Get the AST converter instance
        if self.ast_converter is None:
            from .ast_behavior_converter import create_ast_behavior_converter

            self.ast_converter = create_ast_behavior_converter()

        # Extract behavior nodes using existing logic
        behavior_nodes = self._extract_behaviors_from_roots(roots)

        # Convert nodes to behavior models
        behavior_models: dict[str, list[Any]] = {
            "hold_taps": [],
            "macros": [],
            "combos": [],
            "tap_dances": [],
            "caps_word": [],
            "sticky_keys": [],
            "layers": [],
            "mods": [],
            "other_behaviors": [],
        }

        # Convert hold-tap nodes
        for node in behavior_nodes.get("hold_taps", []):
            hold_tap = self.ast_converter.convert_hold_tap_node(node)
            if hold_tap:
                behavior_models["hold_taps"].append(hold_tap)

        # Convert macro nodes
        for node in behavior_nodes.get("macros", []):
            macro = self.ast_converter.convert_macro_node(node)
            if macro:
                behavior_models["macros"].append(macro)

        # Convert combo nodes
        for node in behavior_nodes.get("combos", []):
            combo = self.ast_converter.convert_combo_node(node)
            if combo:
                behavior_models["combos"].append(combo)

        # For other behavior types, we'll keep them as nodes for now
        # (could be extended with specific converters later)
        for behavior_type in [
            "tap_dances",
            "caps_word",
            "sticky_keys",
            "layers",
            "mods",
            "other_behaviors",
        ]:
            behavior_models[behavior_type] = behavior_nodes.get(behavior_type, [])

        # Extract metadata using metadata extractor
        metadata = self.metadata_extractor.extract_metadata(roots, source_content)

        # Log conversion summary
        converted_count = (
            len(behavior_models["hold_taps"])
            + len(behavior_models["macros"])
            + len(behavior_models["combos"])
        )
        self.logger.debug(
            "Converted %d behavior nodes to model objects: %d hold-taps, %d macros, %d combos",
            converted_count,
            len(behavior_models["hold_taps"]),
            len(behavior_models["macros"]),
            len(behavior_models["combos"]),
        )

        return behavior_models, metadata

    def _extract_behaviors_from_roots(
        self, roots: list[DTNode]
    ) -> dict[str, list[DTNode]]:
        """Extract all behavior types from multiple device tree roots using enhanced patterns.

        Args:
            roots: List of root nodes to search

        Returns:
            Dictionary mapping behavior types to node lists
        """
        results: dict[str, list[DTNode]] = {
            "hold_taps": [],
            "macros": [],
            "combos": [],
            "tap_dances": [],
            "caps_word": [],
            "sticky_keys": [],
            "layers": [],
            "mods": [],
            "other_behaviors": [],
        }

        # Use DTMultiWalker for multi-root behavior extraction
        multi_walker = DTMultiWalker(roots)

        # First, extract combos from combos sections (special case)
        results["combos"] = self._extract_combos_enhanced(roots)

        # Find all nodes with compatible properties that might be behaviors
        all_nodes_with_compatible = multi_walker.find_properties(
            lambda prop: prop.name == "compatible" and prop.value is not None
        )

        # Process each compatible node
        for node, compatible_prop in all_nodes_with_compatible:
            compatible_value = compatible_prop.value.value
            if not isinstance(compatible_value, str):
                continue

            # Check if this is a behavior type
            if not self._is_behavior_compatible(compatible_value):
                continue

            # Categorize behavior using enhanced pattern matching
            behavior_type = self._categorize_behavior(compatible_value)

            if behavior_type in results:
                # Avoid duplicates
                if node not in results[behavior_type]:
                    results[behavior_type].append(node)
            else:
                # Unknown behavior type
                if node not in results["other_behaviors"]:
                    results["other_behaviors"].append(node)

        # Log extraction summary
        total_behaviors = sum(len(behaviors) for behaviors in results.values())
        self.logger.debug(
            "Extracted %d behaviors: %s",
            total_behaviors,
            {k: len(v) for k, v in results.items() if v},
        )

        return results

    def _is_behavior_compatible(self, compatible_value: str) -> bool:
        """Check if compatible string indicates a ZMK behavior.

        Args:
            compatible_value: Compatible property value

        Returns:
            True if this is a behavior compatible string
        """
        behavior_indicators = [
            "zmk,behavior",
            "zmk,combo",  # Some combos use this
        ]

        return any(indicator in compatible_value for indicator in behavior_indicators)

    def _categorize_behavior(self, compatible_value: str) -> str:
        """Categorize behavior type based on compatible string.

        Args:
            compatible_value: Compatible property value

        Returns:
            Behavior category name or "other_behaviors"
        """
        # Check each behavior type pattern
        for behavior_type, patterns in self.behavior_patterns.items():
            for pattern in patterns:
                if pattern in compatible_value:
                    return behavior_type

        return "other_behaviors"

    def _extract_combos_enhanced(self, roots: list[DTNode]) -> list[DTNode]:
        """Enhanced combo extraction that looks in multiple locations.

        Args:
            roots: List of root nodes to search

        Returns:
            List of combo nodes
        """
        combos = []
        multi_walker = DTMultiWalker(roots)

        # Method 1: Find combos sections
        combos_sections = multi_walker.find_nodes_by_name("combos")
        for section in combos_sections:
            for child in section.children.values():
                if self._is_valid_combo(child):
                    combos.append(child)

        # Method 2: Find nodes with combo-like properties
        combo_nodes = multi_walker.find_properties(
            lambda prop: prop.name == "key-positions" and prop.value is not None
        )

        for node, _ in combo_nodes:
            # Verify this has bindings property too
            if node.get_property("bindings") and node not in combos:
                combos.append(node)

        # Method 3: Find nodes with combo compatible strings
        combo_compatible_nodes = multi_walker.find_properties(
            lambda prop: (
                prop.name == "compatible"
                and prop.value
                and isinstance(prop.value.value, str)
                and any(
                    pattern in prop.value.value
                    for pattern in self.behavior_patterns["combos"]
                )
            )
        )

        for node, _ in combo_compatible_nodes:
            if node not in combos:
                combos.append(node)

        return combos

    def _is_valid_combo(self, node: DTNode) -> bool:
        """Check if node is a valid combo definition.

        Args:
            node: Node to check

        Returns:
            True if node appears to be a valid combo
        """
        has_key_positions = node.get_property("key-positions") is not None
        has_bindings = node.get_property("bindings") is not None

        return has_key_positions and has_bindings

    def detect_advanced_patterns(self, roots: list[DTNode]) -> dict[str, Any]:
        """Detect advanced ZMK patterns and custom implementations.

        Args:
            roots: List of root nodes to analyze

        Returns:
            Dictionary with detected patterns and metadata
        """
        patterns = {
            "custom_behaviors": [],
            "input_listeners": [],
            "conditional_layers": [],
            "sensor_configs": [],
            "underglow_configs": [],
            "mouse_configs": [],
        }

        multi_walker = DTMultiWalker(roots)

        # Detect input listeners (like mouse movement processors)
        input_listeners = multi_walker.find_nodes_by_name("mmv_input_listener")
        input_listeners.extend(multi_walker.find_nodes_by_name("input_listener"))
        patterns["input_listeners"] = input_listeners

        # Detect sensor configurations
        sensor_nodes = multi_walker.find_nodes_by_compatible(
            "zmk,behavior-sensor-rotate"
        )
        patterns["sensor_configs"] = sensor_nodes

        # Detect underglow/RGB configurations
        rgb_nodes = multi_walker.find_nodes_by_compatible("worldsemi,ws2812")
        rgb_nodes.extend(multi_walker.find_nodes_by_name("rgb_ug"))
        patterns["underglow_configs"] = rgb_nodes

        # Detect mouse/pointing device configurations
        mouse_nodes = multi_walker.find_nodes_by_name("mmv")
        mouse_nodes.extend(multi_walker.find_nodes_by_name("mouse"))
        patterns["mouse_configs"] = mouse_nodes

        # Detect conditional layers (layers with specific activation conditions)
        conditional_nodes = multi_walker.find_properties(
            lambda prop: prop.name == "layers" and prop.value is not None
        )
        patterns["conditional_layers"] = [node for node, _ in conditional_nodes]

        # Detect custom behavior implementations
        custom_behaviors = multi_walker.find_properties(
            lambda prop: (
                prop.name == "compatible"
                and prop.value
                and isinstance(prop.value.value, str)
                and "zmk,behavior" in prop.value.value
                and not any(
                    known_pattern in prop.value.value
                    for patterns_list in self.behavior_patterns.values()
                    for known_pattern in patterns_list
                )
            )
        )
        patterns["custom_behaviors"] = [node for node, _ in custom_behaviors]

        return patterns


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


def create_universal_behavior_extractor_with_converter() -> UniversalBehaviorExtractor:
    """Create universal behavior extractor with AST converter for comment support.

    Returns:
        Configured UniversalBehaviorExtractor with AST converter
    """
    extractor = UniversalBehaviorExtractor()

    # Initialize the AST converter for comment-aware behavior extraction
    from .ast_behavior_converter import create_ast_behavior_converter

    extractor.ast_converter = create_ast_behavior_converter()

    return extractor
