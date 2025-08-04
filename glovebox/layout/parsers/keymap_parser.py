"""ZMK keymap parser for reverse engineering keymaps to JSON layouts."""

import logging
import re
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Protocol

from glovebox.layout.models import LayoutBinding, LayoutData
from glovebox.models.base import GloveboxBaseModel

from .ast_nodes import DTNode, DTValue
from .keymap_converters import ModelFactory
from .keymap_processors import (
    create_full_keymap_processor,
    create_template_aware_processor,
)
from .parsing_models import ParsingContext, get_default_extraction_config


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile
    from glovebox.layout.models import ConfigDirective, KeymapComment, KeymapInclude

    from .parsing_models import ExtractionConfig

    class ProcessorProtocol(Protocol):
        def process(self, context: "ParsingContext") -> LayoutData | None: ...


class ParsingMode(str, Enum):
    """Keymap parsing modes."""

    FULL = "full"
    TEMPLATE_AWARE = "template"


class ParsingMethod(str, Enum):
    """Keymap parsing method."""

    AST = "ast"  # AST-based parsing
    REGEX = "regex"  # Legacy regex-based parsing


class KeymapParseResult(GloveboxBaseModel):
    """Result of keymap parsing operation."""

    success: bool
    layout_data: LayoutData | None = None
    errors: list[str] = []
    warnings: list[str] = []
    parsing_mode: ParsingMode
    parsing_method: ParsingMethod = ParsingMethod.AST
    extracted_sections: dict[str, object] = {}


class ZmkKeymapParser:
    """Parser for converting ZMK keymap files back to glovebox JSON layouts.

    Supports two parsing modes:
    1. FULL: Parse complete standalone keymap files
    2. TEMPLATE_AWARE: Use keyboard profile templates to extract only user data
    """

    def __init__(
        self,
        processors: dict[ParsingMode, "ProcessorProtocol"] | None = None,
    ) -> None:
        """Initialize the keymap parser with explicit dependencies.

        Args:
            template_adapter: Template adapter for processing template files
            processors: Dictionary of parsing mode to processor instances
        """
        self.logger = logging.getLogger(__name__)
        self.model_factory = ModelFactory()
        self.defines: dict[str, str] = {}

        # Initialize processors for different parsing modes
        self.processors = processors or {
            ParsingMode.FULL: create_full_keymap_processor(),
            ParsingMode.TEMPLATE_AWARE: create_template_aware_processor(),
        }

    def _resolve_binding_string(self, binding_str: str) -> str:
        """Resolve defines in a binding string.

        Args:
            binding_str: Binding string that may contain defines

        Returns:
            Binding string with defines resolved
        """
        if not self.defines:
            return binding_str

        # Split the binding string into tokens
        tokens = binding_str.split()
        resolved_tokens = []

        for token in tokens:
            # Check if token is a define (but not a behavior reference starting with &)
            if not token.startswith("&") and token in self.defines:
                resolved = self.defines[token]
                self.logger.debug("Resolved define %s -> %s", token, resolved)
                resolved_tokens.append(resolved)
            else:
                resolved_tokens.append(token)

        return " ".join(resolved_tokens)

    def parse_keymap(
        self,
        keymap_file: Path,
        mode: ParsingMode = ParsingMode.TEMPLATE_AWARE,
        profile: Optional["KeyboardProfile"] = None,
        method: ParsingMethod = ParsingMethod.AST,
    ) -> KeymapParseResult:
        """Parse ZMK keymap file to JSON layout.

        Args:
            keymap_file: Path to .keymap file
            mode: Parsing mode (full or template-aware)
            keyboard_profile: Keyboard profile name (required for template-aware mode)
            method: Parsing method (always AST now)

        Returns:
            KeymapParseResult with layout data or errors
        """
        result = KeymapParseResult(
            success=False,
            parsing_mode=mode,
            parsing_method=method,
        )

        try:
            # Read keymap file content
            if not keymap_file.exists():
                result.errors.append(f"Keymap file not found: {keymap_file}")
                return result

            keymap_content = keymap_file.read_text(encoding="utf-8")

            # Get extraction configuration
            # TODO: currently not implemented in profile parser will used a default
            extraction_config = self._get_extraction_config(profile)

            # Create parsing context
            keyboard_name = profile.keyboard_name if profile else "unknown"
            title = f"{keymap_file.stem}"  # file name without extension

            context = ParsingContext(
                keymap_content=keymap_content,
                title=title,
                keyboard_name=keyboard_name,
                extraction_config=extraction_config,
            )

            # Use appropriate processor
            processor = self.processors[mode]
            layout_data = processor.process(context)

            # Add metedata
            if layout_data:
                layout_data.date = datetime.now()
                layout_data.creator = "glovebox"
                layout_data.notes = (
                    f"Automatically generated from keymap file {keymap_file.name}"
                )

                result.layout_data = layout_data
                result.success = True
                result.extracted_sections = getattr(context, "extracted_sections", {})

            # Transfer context errors and warnings to result
            result.errors.extend(context.errors)
            result.warnings.extend(context.warnings)

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Failed to parse keymap: %s", e, exc_info=exc_info)
            result.errors.append(f"Parsing failed: {e}")

        return result

    def _get_extraction_config(
        self,
        profile: Optional["KeyboardProfile"] = None,
    ) -> list["ExtractionConfig"]:
        """Get extraction configuration from profile or use default.

        Args:
            keyboard_profile: Keyboard profile

        Returns:
            List of extraction configurations
        """
        if profile:
            try:
                # Check if profile has custom extraction config
                # TODO: currently not implemented in profile
                if hasattr(profile, "keymap_extraction") and profile.keymap_extraction:
                    extraction_sections = profile.keymap_extraction.sections
                    # Ensure we return the proper typed list
                    return list(extraction_sections)
            except Exception as e:
                exc_info = self.logger.isEnabledFor(logging.DEBUG)
                self.logger.warning(
                    "Failed to load extraction config from profile %s: %s",
                    profile.keyboard_name if profile else "unknown",
                    e,
                    exc_info=exc_info,
                )

        # Return default configuration
        return get_default_extraction_config()

    def _get_template_path(self, profile: "KeyboardProfile") -> Path | None:
        """Get template file path from keyboard profile.

        Args:
            profile: Keyboard profile object

        Returns:
            Path to template file or None if not found
        """
        try:
            # Check if profile has keymap template configuration
            if (
                hasattr(profile, "keymap")
                and profile.keymap
                and hasattr(profile.keymap, "keymap_dtsi_file")
            ):
                # External template file
                template_file = profile.keymap.keymap_dtsi_file
                if template_file:
                    # Resolve relative to profile config directory if available
                    if hasattr(profile, "config_path") and profile.config_path:
                        config_dir = Path(profile.config_path).parent
                        return Path(config_dir / template_file)
                    else:
                        # Fallback to treating template_file as relative to built-in keyboards
                        package_path = Path(__file__).parent.parent.parent.parent
                        return Path(package_path / "keyboards" / template_file)

            # Fallback to default template location in the project
            project_root = Path(__file__).parent.parent.parent.parent
            return Path(
                project_root / "keyboards" / "config" / "templates" / "keymap.dtsi.j2"
            )

        except Exception as e:
            self.logger.warning("Could not determine template path: %s", e)
            return None

    def _extract_balanced_node(self, content: str, node_name: str) -> str | None:
        """Extract a device tree node with balanced brace matching.

        Args:
            content: Full content to search
            node_name: Name of node to extract

        Returns:
            Node content including braces, or None if not found
        """
        # Find the start of the node
        pattern = rf"{node_name}\s*\{{"
        match = re.search(pattern, content)

        if not match:
            return None

        start_pos = match.start()
        brace_start = match.end() - 1  # Position of opening brace

        # Count braces to find the matching closing brace
        brace_count = 1
        pos = brace_start + 1

        while pos < len(content) and brace_count > 0:
            char = content[pos]
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
            pos += 1

        if brace_count == 0:
            # Found matching brace
            return content[start_pos:pos]
        else:
            return None

    def _extract_layers_from_ast(self, root: DTNode) -> dict[str, object] | None:
        """Extract layer definitions from AST."""
        try:
            keymap_node = None

            # Log the root node structure for debugging
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(
                    "Searching for keymap node in root: name='%s', children=%s",
                    root.name,
                    list(root.children.keys()),
                )

            # Method 1: Direct check if root is keymap
            if root.name == "keymap":
                keymap_node = root
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug("Found keymap node as root node")

            # Method 2: Try direct path lookup
            if not keymap_node:
                keymap_node = root.find_node_by_path("/keymap")
                if keymap_node and self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug("Found keymap node via path /keymap")

            # Method 3: For main root nodes (name=""), look for keymap child directly
            if not keymap_node and root.name == "":
                keymap_node = root.get_child("keymap")
                if keymap_node and self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug("Found keymap node as direct child of main root")

            # Method 4: Recursive search through all child nodes
            if not keymap_node:
                keymap_node = self._find_keymap_node_recursive(root)
                if keymap_node and self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug("Found keymap node via recursive search")

            if not keymap_node:
                if self.logger.isEnabledFor(logging.DEBUG):
                    # Log the full tree structure for debugging
                    self._log_ast_structure(root, level=0, max_level=2)
                self.logger.warning("No keymap node found in AST")
                return None

            layer_names = []
            layers = []

            for child_name, child_node in keymap_node.children.items():
                if child_name.startswith("layer_"):
                    layer_name = child_name[6:]
                    layer_names.append(layer_name)

                    bindings_prop = child_node.get_property("bindings")
                    if bindings_prop and bindings_prop.value:
                        bindings = self._convert_ast_bindings(bindings_prop.value)
                        layers.append(bindings)
                    else:
                        layers.append([])

            if not layer_names:
                self.logger.warning("No layer definitions found in keymap node")
                return None

            return {"layer_names": layer_names, "layers": layers}

        except Exception as e:
            self.logger.warning("Failed to extract layers from AST: %s", e)
            return None

    def _find_keymap_node_recursive(self, node: DTNode) -> DTNode | None:
        """Recursively search for keymap node in the AST.

        Args:
            node: Node to search from

        Returns:
            Keymap DTNode if found, None otherwise
        """
        # Check all children of current node
        for child_name, child_node in node.children.items():
            if child_name == "keymap":
                return child_node

            # Recursively search in child nodes
            found = self._find_keymap_node_recursive(child_node)
            if found:
                return found

        return None

    def _log_ast_structure(
        self, node: DTNode, level: int = 0, max_level: int = 2
    ) -> None:
        """Log AST structure for debugging.

        Args:
            node: Node to log
            level: Current depth level
            max_level: Maximum depth to log
        """
        if level > max_level:
            return

        indent = "  " * level
        self.logger.debug(
            "%sNode: name='%s', children=%s, properties=%s",
            indent,
            node.name,
            list(node.children.keys()),
            list(node.properties.keys()),
        )

        # Log children recursively
        for _child_name, child_node in node.children.items():
            self._log_ast_structure(child_node, level + 1, max_level)

    def _convert_ast_bindings(self, bindings_value: DTValue) -> list[LayoutBinding]:
        """Convert AST bindings value to LayoutBinding objects.

        Args:
            bindings_value: DTValue containing bindings

        Returns:
            List of LayoutBinding objects
        """
        bindings: list[LayoutBinding] = []

        if not bindings_value or not bindings_value.value:
            return bindings

        # Handle array of bindings
        if isinstance(bindings_value.value, list):
            # Group behavior references with their parameters
            # In device tree syntax, <&kp Q &hm LCTRL A> means two bindings: "&kp Q" and "&hm LCTRL A"
            i = 0
            values = bindings_value.value
            while i < len(values):
                item = str(values[i]).strip()

                # Check if this is a behavior reference
                if item.startswith("&"):
                    # Look for parameters following this behavior
                    binding_parts = [item]
                    i += 1

                    # Collect parameters until we hit another behavior reference or end of array
                    while i < len(values):
                        next_item = str(values[i]).strip()
                        # Stop if we hit another behavior reference
                        if next_item.startswith("&"):
                            break
                        # Collect this parameter
                        binding_parts.append(next_item)
                        i += 1

                    # Join the parts to form the complete binding
                    binding_str = " ".join(binding_parts)

                    # Log the binding string for debugging parameter issues
                    if self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug(
                            "Converting binding: '%s' from parts: %s",
                            binding_str,
                            binding_parts,
                        )

                    try:
                        # Preprocess for MoErgo edge cases
                        preprocessed_binding_str = (
                            self._preprocess_moergo_binding_edge_cases(binding_str)
                        )

                        # Resolve defines in the binding string
                        resolved_binding_str = self._resolve_binding_string(
                            preprocessed_binding_str
                        )

                        # Use the existing LayoutBinding.from_str method
                        binding = LayoutBinding.from_str(resolved_binding_str)
                        bindings.append(binding)

                        # Debug log the parsed parameters
                        if self.logger.isEnabledFor(logging.DEBUG):
                            param_strs = [str(p.value) for p in binding.params]
                            self.logger.debug(
                                "Parsed binding '%s' with %d params: %s",
                                binding.value,
                                len(binding.params),
                                param_strs,
                            )
                    except Exception as e:
                        exc_info = self.logger.isEnabledFor(logging.DEBUG)
                        self.logger.error(
                            "Failed to parse binding '%s': %s",
                            binding_str,
                            e,
                            exc_info=exc_info,
                        )
                        # Create fallback binding with empty params
                        bindings.append(
                            LayoutBinding(value=binding_parts[0], params=[])
                        )
                else:
                    # Standalone parameter without behavior - this shouldn't happen in well-formed keymap
                    self.logger.warning(
                        "Found standalone parameter '%s' without behavior reference",
                        item,
                    )
                    i += 1
        else:
            # Single binding
            binding_str = str(bindings_value.value).strip()
            if binding_str:
                try:
                    # Preprocess for MoErgo edge cases
                    preprocessed_binding_str = (
                        self._preprocess_moergo_binding_edge_cases(binding_str)
                    )

                    # Resolve defines in the binding string
                    resolved_binding_str = self._resolve_binding_string(
                        preprocessed_binding_str
                    )

                    binding = LayoutBinding.from_str(resolved_binding_str)
                    bindings.append(binding)
                except Exception as e:
                    exc_info = self.logger.isEnabledFor(logging.DEBUG)
                    self.logger.error(
                        "Failed to parse single binding '%s': %s",
                        binding_str,
                        e,
                        exc_info=exc_info,
                    )
                    bindings.append(LayoutBinding(value=binding_str, params=[]))

        return bindings

    def _convert_comment_to_model(
        self, comment_dict: dict[str, object]
    ) -> "KeymapComment":
        """Convert comment dictionary to KeymapComment model instance.

        Args:
            comment_dict: Dictionary with comment data

        Returns:
            KeymapComment model instance
        """
        return self.model_factory.create_comment(comment_dict)

    def _convert_include_to_model(
        self, include_dict: dict[str, object]
    ) -> "KeymapInclude":
        """Convert include dictionary to KeymapInclude model instance.

        Args:
            include_dict: Dictionary with include data

        Returns:
            KeymapInclude model instance
        """
        return self.model_factory.create_include(include_dict)

    def _convert_directive_to_model(
        self, directive_dict: dict[str, object]
    ) -> "ConfigDirective":
        """Convert config directive dictionary to ConfigDirective model instance.

        Args:
            directive_dict: Dictionary with directive data

        Returns:
            ConfigDirective model instance
        """
        return self.model_factory.create_directive(directive_dict)

    def _preprocess_moergo_binding_edge_cases(self, binding_str: str) -> str:
        """Preprocess binding string to handle MoErgo JSON edge cases.

        Args:
            binding_str: Original binding string

        Returns:
            Preprocessed binding string with edge cases handled
        """
        # Edge case 1: Transform &sys_reset to &reset
        if binding_str == "&sys_reset":
            self.logger.debug(
                "Transforming &sys_reset to &reset for MoErgo compatibility"
            )
            return "&reset"

        # Edge case 2: Handle &magic parameter cleanup
        # Convert "&magic LAYER_Magic 0" to "&magic" (remove nested params)
        if binding_str.startswith("&magic "):
            parts = binding_str.split()
            if len(parts) >= 3 and parts[1].startswith("LAYER_") and parts[2] == "0":
                self.logger.debug(
                    "Cleaning up &magic parameters for MoErgo compatibility: %s -> &magic",
                    binding_str,
                )
                return "&magic"

        return binding_str


def create_zmk_keymap_parser(
    processors: dict[ParsingMode, "ProcessorProtocol"] | None = None,
) -> ZmkKeymapParser:
    """Create ZMK keymap parser instance with explicit dependencies.

    Args:
        template_adapter: Optional template adapter (uses create_template_adapter() if None)
        processors: Optional processors dictionary (uses default processors if None)

    Returns:
        Configured ZmkKeymapParser instance with all dependencies injected
    """
    return ZmkKeymapParser(
        processors=processors,
    )


def create_zmk_keymap_parser_from_profile(
    profile: "KeyboardProfile",
) -> ZmkKeymapParser:
    """Create ZMK keymap parser instance configured for a specific keyboard profile.

    This factory function follows the CLAUDE.md pattern of profile-based configuration
    loading, similar to other domains in the codebase.

    Args:
        profile: Keyboard profile containing configuration for the parser
        template_adapter: Optional template adapter (uses create_template_adapter() if None)

    Returns:
        Configured ZmkKeymapParser instance with profile-specific settings
    """
    # Create parser with dependencies
    parser = create_zmk_keymap_parser()

    # Configure parser based on profile settings
    # This could include profile-specific parsing preferences, template paths, etc.
    # For now, we return the standard parser, but this provides the extension point
    # for profile-based configuration

    return parser
