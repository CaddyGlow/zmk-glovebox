"""ZMK keymap parser for reverse engineering keymaps to JSON layouts."""

import logging
import re
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from glovebox.adapters import create_template_adapter
from glovebox.layout.models import LayoutBinding, LayoutData
from glovebox.models.base import GloveboxBaseModel

from .ast_nodes import DTNode, DTValue
from .ast_walker import create_universal_behavior_extractor
from .behavior_parser import create_behavior_parser
from .dt_parser import parse_dt_lark_safe, parse_dt_multiple_safe, parse_dt_safe
from .model_converters import create_universal_model_converter


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile


class ParsingMode(str, Enum):
    """Keymap parsing modes."""

    FULL = "full"
    TEMPLATE_AWARE = "template"


class ParsingMethod(str, Enum):
    """Keymap parsing method."""

    REGEX = "regex"  # Legacy regex-based parsing
    AST = "ast"  # New AST-based parsing


class KeymapParseResult(GloveboxBaseModel):
    """Result of keymap parsing operation."""

    success: bool
    layout_data: LayoutData | None = None
    errors: list[str] = []
    warnings: list[str] = []
    parsing_mode: ParsingMode
    parsing_method: ParsingMethod = ParsingMethod.REGEX
    extracted_sections: dict[str, Any] = {}


class ZmkKeymapParser:
    """Parser for converting ZMK keymap files back to glovebox JSON layouts.

    Supports two parsing modes:
    1. FULL: Parse complete standalone keymap files
    2. TEMPLATE_AWARE: Use keyboard profile templates to extract only user data
    """

    def __init__(self) -> None:
        """Initialize the keymap parser."""
        self.logger = logging.getLogger(__name__)
        self.template_adapter = create_template_adapter()
        self.behavior_parser = create_behavior_parser()

        # AST-based parsing components
        self.behavior_extractor = create_universal_behavior_extractor()
        self.model_converter = create_universal_model_converter()

    def parse_keymap(
        self,
        keymap_file: Path,
        mode: ParsingMode = ParsingMode.TEMPLATE_AWARE,
        keyboard_profile: str | None = None,
        method: ParsingMethod = ParsingMethod.REGEX,
    ) -> KeymapParseResult:
        """Parse ZMK keymap file to JSON layout.

        Args:
            keymap_file: Path to .keymap file
            mode: Parsing mode (full or template-aware)
            keyboard_profile: Keyboard profile name (required for template-aware mode)
            method: Parsing method (regex or ast)

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

            # Validate required parameters
            if mode == ParsingMode.TEMPLATE_AWARE and not keyboard_profile:
                result.errors.append(
                    "Keyboard profile is required for template-aware parsing"
                )
                return result

            # Parse based on mode and method
            if mode == ParsingMode.FULL:
                if method == ParsingMethod.AST:
                    layout_data = self._parse_full_keymap_ast(keymap_content, result)
                else:
                    layout_data = self._parse_full_keymap(keymap_content, result)
            else:
                # Ensure keyboard_profile is not None for template-aware parsing
                if not keyboard_profile:
                    result.errors.append(
                        "Keyboard profile is required for template-aware parsing"
                    )
                    return result

                if method == ParsingMethod.AST:
                    layout_data = self._parse_template_aware_ast(
                        keymap_content, keyboard_profile, result
                    )
                else:
                    layout_data = self._parse_template_aware(
                        keymap_content, keyboard_profile, result
                    )

            if layout_data:
                result.layout_data = layout_data
                result.success = True

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Failed to parse keymap: %s", e, exc_info=exc_info)
            result.errors.append(f"Parsing failed: {e}")

        return result

    def _parse_full_keymap(
        self, keymap_content: str, result: KeymapParseResult
    ) -> LayoutData | None:
        """Parse complete keymap file extracting all structure.

        Args:
            keymap_content: Full keymap file content
            result: Result object to populate with warnings/errors

        Returns:
            Parsed LayoutData or None if parsing fails
        """
        try:
            # Extract basic metadata
            layout_data = LayoutData(keyboard="unknown", title="Imported Keymap")

            # Extract layers from keymap node
            layers_data = self._extract_layers_from_keymap(keymap_content)
            if layers_data:
                layout_data.layer_names = layers_data["layer_names"]
                layout_data.layers = layers_data["layers"]
                result.extracted_sections["layers"] = layers_data

            # Extract custom behaviors using behavior parser
            behaviors = self.behavior_parser.parse_behaviors_section(keymap_content)
            if behaviors:
                layout_data.hold_taps = behaviors.get("hold_taps", [])
                result.extracted_sections["behaviors"] = behaviors

            # Extract macros
            macros = self.behavior_parser.parse_macros_section(keymap_content)
            if macros:
                layout_data.macros = macros
                result.extracted_sections["macros"] = macros

            # Extract combos
            combos = self.behavior_parser.parse_combos_section(keymap_content)
            if combos:
                layout_data.combos = combos
                result.extracted_sections["combos"] = combos

            # Extract custom device tree code
            custom_code = self._extract_custom_sections(keymap_content)
            if custom_code:
                layout_data.custom_defined_behaviors = custom_code.get("behaviors", "")
                layout_data.custom_devicetree = custom_code.get("devicetree", "")
                result.extracted_sections["custom"] = custom_code

            # DEBUG: Log metadata extraction summary
            self.logger.debug("=== FULL MODE METADATA SUMMARY ===")
            self.logger.debug("Extracted sections: %s", list(result.extracted_sections.keys()))
            if 'macros' in result.extracted_sections:
                macros = result.extracted_sections['macros']
                self.logger.debug("Macros found: %d", len(macros))
                for i, macro in enumerate(macros[:3]):  # Show first 3
                    self.logger.debug("  %d. %s - %s", i+1, macro.name, macro.description)
            self.logger.debug("=== END METADATA SUMMARY ===")

            return layout_data

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Full keymap parsing failed: %s", e, exc_info=exc_info)
            result.errors.append(f"Full parsing failed: {e}")
            return None

    def _parse_template_aware(
        self, keymap_content: str, keyboard_profile: str, result: KeymapParseResult
    ) -> LayoutData | None:
        """Parse keymap using keyboard profile template for structure identification.

        Args:
            keymap_content: Keymap file content
            keyboard_profile: Keyboard profile identifier
            result: Result object to populate

        Returns:
            Parsed LayoutData or None if parsing fails
        """
        try:
            # Load keyboard profile and template
            from glovebox.config import create_keyboard_profile

            profile = create_keyboard_profile(keyboard_profile)
            template_path = self._get_template_path(profile)

            if not template_path or not template_path.exists():
                result.errors.append(
                    f"Template not found for profile: {keyboard_profile}"
                )
                return None

            # Load template and get variable structure
            template_content = template_path.read_text(encoding="utf-8")
            template_vars = self.template_adapter.get_template_variables(
                template_content
            )

            # Create base layout data with profile info
            layout_data = LayoutData(
                keyboard=profile.keyboard_name, title="Imported Layout"
            )

            # Extract user data sections using template knowledge
            extracted_data = self._extract_template_sections(
                keymap_content, template_vars, profile, result
            )

            if extracted_data:
                # Populate layout data with extracted sections
                if "layers" in extracted_data:
                    layers = extracted_data["layers"]
                    layout_data.layer_names = layers["layer_names"]
                    layout_data.layers = layers["layers"]

                if "behaviors" in extracted_data:
                    behaviors = extracted_data["behaviors"]
                    layout_data.hold_taps = behaviors.get("hold_taps", [])

                if "macros" in extracted_data:
                    layout_data.macros = extracted_data["macros"]

                if "combos" in extracted_data:
                    layout_data.combos = extracted_data["combos"]

                if "custom" in extracted_data:
                    custom = extracted_data["custom"]
                    layout_data.custom_defined_behaviors = custom.get("behaviors", "")
                    layout_data.custom_devicetree = custom.get("devicetree", "")

                if "variables" in extracted_data:
                    layout_data.variables = extracted_data["variables"]

                result.extracted_sections = extracted_data

            return layout_data

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Template-aware parsing failed: %s", e, exc_info=exc_info)
            result.errors.append(f"Template-aware parsing failed: {e}")
            return None

    def _get_template_path(self, profile: Any) -> Path | None:
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
                    # Resolve relative to profile config directory
                    config_dir = Path(profile.config_path).parent
                    return Path(config_dir / template_file)

            # Fallback to default template location in the project
            project_root = Path(__file__).parent.parent.parent.parent
            return Path(
                project_root / "keyboards" / "config" / "templates" / "keymap.dtsi.j2"
            )

        except Exception as e:
            self.logger.warning("Could not determine template path: %s", e)
            return None

    def _extract_layers_from_keymap(self, keymap_content: str) -> dict[str, Any] | None:
        """Extract layer definitions from keymap node.

        Args:
            keymap_content: Keymap file content

        Returns:
            Dictionary with layer_names and layers lists
        """
        try:
            # Find keymap node using balanced brace matching
            keymap_node = self._extract_balanced_node(keymap_content, "keymap")

            if not keymap_node:
                self.logger.warning("No keymap node found")
                return None

            # Extract individual layer definitions
            layer_pattern = r"layer_(\w+)\s*\{([^}]*)\}"
            layer_matches = re.findall(layer_pattern, keymap_node, re.DOTALL)

            if not layer_matches:
                self.logger.warning("No layer definitions found")
                return None

            layer_names = []
            layers = []

            for layer_name, layer_body in layer_matches:
                layer_names.append(layer_name)

                # Extract bindings from layer body
                bindings_pattern = r"bindings\s*=\s*<([^>]*)>"
                bindings_match = re.search(bindings_pattern, layer_body, re.DOTALL)

                if bindings_match:
                    bindings_content = bindings_match.group(1)
                    bindings = self._parse_bindings_content(bindings_content)
                    layers.append(bindings)
                else:
                    # Empty layer
                    layers.append([])

            return {"layer_names": layer_names, "layers": layers}

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Failed to extract layers: %s", e, exc_info=exc_info)
            return None

    def _parse_bindings_content(self, bindings_content: str) -> list[LayoutBinding]:
        """Parse bindings content string to LayoutBinding objects.

        Args:
            bindings_content: Raw bindings content from keymap

        Returns:
            List of LayoutBinding objects
        """
        bindings = []

        # Remove comments and clean up content
        cleaned_content = re.sub(r"//.*$", "", bindings_content, flags=re.MULTILINE)

        # Split by semicolons first to properly separate behaviors
        # Handle semicolons as primary separators in ZMK bindings
        semicolon_parts = [part.strip() for part in cleaned_content.split(';') if part.strip()]
        
        for part in semicolon_parts:
            # Find all behavior patterns within each semicolon-separated part
            # This regex finds complete behaviors like &kp Q, &mt LSHIFT A, &trans, etc.
            # Updated pattern to stop at semicolons and handle parameters properly
            behavior_pattern = r"&[a-zA-Z_][a-zA-Z0-9_]*(?:\s+[^\s&;]+)*"
            behavior_matches = re.findall(behavior_pattern, part)

            # Parse each complete behavior
            for behavior_str in behavior_matches:
                behavior_str = behavior_str.strip()
                if behavior_str:
                    try:
                        binding = LayoutBinding.from_str(behavior_str)
                        bindings.append(binding)
                    except Exception as e:
                        self.logger.warning(
                            "Failed to parse binding '%s': %s", behavior_str, e
                        )
                        # Create a fallback binding
                        bindings.append(
                            LayoutBinding(value=behavior_str.split()[0], params=[])
                        )

        return bindings

    def _extract_custom_sections(self, keymap_content: str) -> dict[str, Any] | None:
        """Extract custom device tree and behavior code.

        Args:
            keymap_content: Keymap file content

        Returns:
            Dictionary with custom code sections
        """
        custom = {}

        # Extract custom behaviors section (outside of standard nodes)
        # Look for behaviors not in behaviors/macros/combos nodes
        custom_behaviors = self._extract_custom_behavior_code(keymap_content)
        if custom_behaviors:
            custom["behaviors"] = custom_behaviors

        # Extract custom device tree code
        custom_dt = self._extract_custom_devicetree_code(keymap_content)
        if custom_dt:
            custom["devicetree"] = custom_dt

        return custom if custom else None

    def _extract_custom_behavior_code(self, keymap_content: str) -> str:
        """Extract custom behavior definitions outside standard nodes."""
        # This would identify custom behavior code that's not in
        # standard behaviors/macros/combos sections
        # For now, return empty string - this is complex parsing
        return ""

    def _extract_custom_devicetree_code(self, keymap_content: str) -> str:
        """Extract custom device tree code outside keymap structure."""
        # This would identify custom DT code outside standard template sections
        # For now, return empty string - this is complex parsing
        return ""

    def _extract_template_sections(
        self,
        keymap_content: str,
        template_vars: list[str],
        profile: Any,
        result: KeymapParseResult,
    ) -> dict[str, Any] | None:
        """Extract user data sections using template variable knowledge.

        Args:
            keymap_content: Keymap file content
            template_vars: List of template variable names
            profile: Keyboard profile object
            result: Result object for warnings/errors

        Returns:
            Dictionary with extracted user data sections
        """
        extracted = {}

        # Extract layers (always needed)
        layers_data = self._extract_layers_from_keymap(keymap_content)
        if layers_data:
            extracted["layers"] = layers_data

        # Extract behaviors using template knowledge
        if "user_behaviors_dtsi" in template_vars:
            behaviors = self.behavior_parser.parse_behaviors_section(keymap_content)
            if behaviors:
                extracted["behaviors"] = behaviors

        # Extract macros if template supports them
        if "user_macros_dtsi" in template_vars:
            macros = self.behavior_parser.parse_macros_section(keymap_content)
            if macros:
                extracted["macros"] = macros  # type: ignore[assignment]

        # Extract combos if template supports them
        if "combos_dtsi" in template_vars:
            combos = self.behavior_parser.parse_combos_section(keymap_content)
            if combos:
                extracted["combos"] = combos  # type: ignore[assignment]

        # Extract custom sections if template supports them
        if any(
            var in template_vars
            for var in ["custom_defined_behaviors", "custom_devicetree"]
        ):
            custom = self._extract_custom_sections(keymap_content)
            if custom:
                extracted["custom"] = custom

        # TODO: Extract template variables from keymap content
        # This would reverse-engineer variables section from usage patterns

        return extracted if extracted else None

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

    def _parse_full_keymap_ast(
        self, keymap_content: str, result: KeymapParseResult
    ) -> LayoutData | None:
        """Parse complete keymap file using AST approach.

        Args:
            keymap_content: Full keymap file content
            result: Result object to populate with warnings/errors

        Returns:
            Parsed LayoutData or None if parsing fails
        """
        try:
            # Parse content into AST using Lark parser
            roots, parse_errors = parse_dt_lark_safe(keymap_content)

            if parse_errors:
                for error in parse_errors:
                    result.warnings.append(str(error))

            if not roots:
                result.errors.append("Failed to parse device tree AST")
                return None

            # Extract basic metadata
            layout_data = LayoutData(keyboard="unknown", title="Imported Keymap")

            # Extract layers using AST from all roots
            layers_data = None
            for root in roots:
                layers_data = self._extract_layers_from_ast(root)
                if layers_data:
                    break  # Use first valid layer data found

            if layers_data:
                layout_data.layer_names = layers_data["layer_names"]
                layout_data.layers = layers_data["layers"]
                result.extracted_sections["layers"] = layers_data

            # Extract behaviors and metadata using enhanced extraction (Phase 4.1)
            behaviors_dict, metadata_dict = (
                self.behavior_extractor.extract_behaviors_with_metadata(
                    roots, keymap_content
                )
            )
            converted_behaviors = self.model_converter.convert_behaviors(behaviors_dict)

            # Populate layout data with converted behaviors
            if converted_behaviors.get("hold_taps"):
                layout_data.hold_taps = converted_behaviors["hold_taps"]
                result.extracted_sections["hold_taps"] = converted_behaviors[
                    "hold_taps"
                ]

            if converted_behaviors.get("macros"):
                layout_data.macros = converted_behaviors["macros"]
                result.extracted_sections["macros"] = converted_behaviors["macros"]

            if converted_behaviors.get("combos"):
                layout_data.combos = converted_behaviors["combos"]
                result.extracted_sections["combos"] = converted_behaviors["combos"]

            # Populate keymap metadata for round-trip preservation (Phase 4.1)
            if metadata_dict:
                # Convert metadata to proper model instances
                layout_data.keymap_metadata.comments = [
                    self._convert_comment_to_model(comment)
                    for comment in metadata_dict.get("comments", [])
                ]
                layout_data.keymap_metadata.includes = [
                    self._convert_include_to_model(include)
                    for include in metadata_dict.get("includes", [])
                ]
                layout_data.keymap_metadata.config_directives = [
                    self._convert_directive_to_model(directive)
                    for directive in metadata_dict.get("config_directives", [])
                ]
                layout_data.keymap_metadata.original_header = metadata_dict.get(
                    "original_header", ""
                )
                layout_data.keymap_metadata.original_footer = metadata_dict.get(
                    "original_footer", ""
                )
                layout_data.keymap_metadata.custom_sections = metadata_dict.get(
                    "custom_sections", {}
                )

                # Set dependency information (Phase 4.3)
                dependencies_dict = metadata_dict.get("dependencies", {})
                if dependencies_dict:
                    layout_data.keymap_metadata.dependencies.include_dependencies = (
                        dependencies_dict.get("include_dependencies", [])
                    )
                    layout_data.keymap_metadata.dependencies.behavior_sources = (
                        dependencies_dict.get("behavior_sources", {})
                    )
                    layout_data.keymap_metadata.dependencies.unresolved_includes = (
                        dependencies_dict.get("unresolved_includes", [])
                    )

                # Set parsing metadata
                layout_data.keymap_metadata.parsing_method = "ast"
                layout_data.keymap_metadata.parsing_mode = "full"
                layout_data.keymap_metadata.source_file = ""  # Could be set by caller

                result.extracted_sections["metadata"] = metadata_dict

            # Extract custom device tree code (remaining sections)
            custom_code = self._extract_custom_sections_ast_multiple(roots)
            if custom_code:
                layout_data.custom_defined_behaviors = custom_code.get("behaviors", "")
                layout_data.custom_devicetree = custom_code.get("devicetree", "")
                result.extracted_sections["custom"] = custom_code

            return layout_data

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("AST-based full parsing failed: %s", e, exc_info=exc_info)
            result.errors.append(f"AST parsing failed: {e}")
            return None

    def _parse_template_aware_ast(
        self, keymap_content: str, keyboard_profile: str, result: KeymapParseResult
    ) -> LayoutData | None:
        """Parse keymap using AST approach with template awareness.

        Args:
            keymap_content: Keymap file content
            keyboard_profile: Keyboard profile name
            result: Result object to populate

        Returns:
            Parsed LayoutData or None if parsing fails
        """
        try:
            # Load keyboard profile and template to understand structure
            from glovebox.config import create_keyboard_profile

            profile = create_keyboard_profile(keyboard_profile)
            template_path = self._get_template_path(profile)

            if not template_path or not template_path.exists():
                result.errors.append(
                    f"Template not found for profile: {keyboard_profile}"
                )
                return None

            # Load template and get variable structure
            template_content = template_path.read_text(encoding="utf-8")
            template_vars = self.template_adapter.get_template_variables(
                template_content
            )

            # Create base layout data with profile info
            layout_data = LayoutData(
                keyboard=profile.keyboard_name, title="Imported Layout"
            )

            # Extract only user-defined sections using hybrid regex+AST approach
            # This avoids parsing the entire keymap as AST, only parsing relevant sections
            extracted_data = self._extract_template_sections_hybrid(
                keymap_content, template_vars, result
            )

            self.logger.debug("Extracted template sections %s", extracted_data)
            if extracted_data:
                # Populate layout data with extracted sections
                if "layers" in extracted_data:
                    layers = extracted_data["layers"]
                    layout_data.layer_names = layers["layer_names"]
                    layout_data.layers = layers["layers"]

                if "behaviors" in extracted_data:
                    behaviors = extracted_data["behaviors"]
                    layout_data.hold_taps = behaviors.get("hold_taps", [])

                if "macros" in extracted_data:
                    layout_data.macros = extracted_data["macros"]

                if "combos" in extracted_data:
                    layout_data.combos = extracted_data["combos"]

                if "custom" in extracted_data:
                    custom = extracted_data["custom"]
                    layout_data.custom_defined_behaviors = custom.get("behaviors", "")
                    layout_data.custom_devicetree = custom.get("devicetree", "")

                result.extracted_sections = extracted_data

            return layout_data

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "AST-based template-aware parsing failed: %s", e, exc_info=exc_info
            )
            result.errors.append(f"AST template-aware parsing failed: {e}")
            return None

    def _extract_layers_from_ast(self, root: DTNode) -> dict[str, Any] | None:
        """Extract layer definitions from AST.

        Args:
            root: Parsed device tree root node

        Returns:
            Dictionary with layer_names and layers lists
        """
        try:
            # Find keymap node - it could be the root itself or a child
            keymap_node = None
            if root.name == "keymap":
                keymap_node = root
            else:
                keymap_node = root.find_node_by_path("/keymap")

            if not keymap_node:
                self.logger.warning("No keymap node found in AST")
                return None

            layer_names = []
            layers = []

            # Look for layer definitions (nodes starting with "layer_")
            for child_name, child_node in keymap_node.children.items():
                if child_name.startswith("layer_"):
                    layer_name = child_name[6:]  # Remove "layer_" prefix
                    layer_names.append(layer_name)

                    # Extract bindings from layer
                    bindings_prop = child_node.get_property("bindings")
                    if bindings_prop and bindings_prop.value:
                        # Convert bindings to LayoutBinding objects
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

                    # Collect parameters until we hit another behavior reference
                    while i < len(values) and not str(values[i]).startswith("&"):
                        binding_parts.append(str(values[i]).strip())
                        i += 1

                    # Join the parts to form the complete binding
                    binding_str = " ".join(binding_parts)
                    try:
                        # Use the existing LayoutBinding.from_str method
                        binding = LayoutBinding.from_str(binding_str)
                        bindings.append(binding)
                    except Exception as e:
                        self.logger.warning(
                            "Failed to parse binding '%s': %s", binding_str, e
                        )
                        # Create fallback binding
                        bindings.append(
                            LayoutBinding(value=binding_parts[0], params=[])
                        )
                else:
                    # Standalone parameter without behavior - skip it
                    i += 1
        else:
            # Single binding
            binding_str = str(bindings_value.value).strip()
            if binding_str:
                try:
                    binding = LayoutBinding.from_str(binding_str)
                    bindings.append(binding)
                except Exception as e:
                    self.logger.warning(
                        "Failed to parse binding '%s': %s", binding_str, e
                    )
                    bindings.append(LayoutBinding(value=binding_str, params=[]))

        return bindings

    def _extract_custom_sections_ast(self, root: DTNode) -> dict[str, str]:
        """Extract custom device tree sections from AST.

        Args:
            root: Parsed device tree root node

        Returns:
            Dictionary with custom sections
        """
        # TODO: Implement extraction of custom sections not covered by standard behaviors
        # This would include:
        # - Custom behavior definitions not in standard categories
        # - Custom device tree nodes
        # - Include statements
        # - etc.

        return {"behaviors": "", "devicetree": ""}

    def _extract_custom_sections_ast_multiple(
        self, roots: list[DTNode]
    ) -> dict[str, str]:
        """Extract custom device tree sections from multiple AST roots.

        Args:
            roots: List of parsed device tree root nodes

        Returns:
            Dictionary with custom sections
        """
        # Combine custom sections from all roots
        combined_behaviors = []
        combined_devicetree = []

        for root in roots:
            sections = self._extract_custom_sections_ast(root)
            if sections.get("behaviors"):
                combined_behaviors.append(sections["behaviors"])
            if sections.get("devicetree"):
                combined_devicetree.append(sections["devicetree"])

        return {
            "behaviors": "\n".join(combined_behaviors),
            "devicetree": "\n".join(combined_devicetree),
        }

    def _convert_comment_to_model(self, comment_dict: dict[str, Any]) -> Any:
        """Convert comment dictionary to KeymapComment model instance.

        Args:
            comment_dict: Dictionary with comment data

        Returns:
            KeymapComment model instance
        """
        from glovebox.layout.models import KeymapComment

        return KeymapComment(
            text=comment_dict.get("text", ""),
            line=comment_dict.get("line", 0),
            context=comment_dict.get("context", ""),
            is_block=comment_dict.get("is_block", False),
        )

    def _convert_include_to_model(self, include_dict: dict[str, Any]) -> Any:
        """Convert include dictionary to KeymapInclude model instance.

        Args:
            include_dict: Dictionary with include data

        Returns:
            KeymapInclude model instance
        """
        from glovebox.layout.models import KeymapInclude

        return KeymapInclude(
            path=include_dict.get("path", ""),
            line=include_dict.get("line", 0),
            resolved_path=include_dict.get("resolved_path", ""),
        )

    def _convert_directive_to_model(self, directive_dict: dict[str, Any]) -> Any:
        """Convert config directive dictionary to ConfigDirective model instance.

        Args:
            directive_dict: Dictionary with directive data

        Returns:
            ConfigDirective model instance
        """
        from glovebox.layout.models import ConfigDirective

        return ConfigDirective(
            directive=directive_dict.get("directive", ""),
            condition=directive_dict.get("condition", ""),
            value=directive_dict.get("value", ""),
            line=directive_dict.get("line", 0),
        )

    def _extract_template_sections_hybrid(
        self,
        keymap_content: str,
        template_vars: list[str],
        result: KeymapParseResult,
    ) -> dict[str, Any] | None:
        """Extract user-defined sections using hybrid regex+AST approach.

        This method first uses regex to identify and extract specific sections
        that correspond to template variables, then parses only those sections
        as AST for better performance.

        Args:
            keymap_content: Original keymap content
            template_vars: List of template variable names from the template
            result: Result object for warnings/errors

        Returns:
            Dictionary with extracted user data sections
        """
        extracted = {}

        try:
            # Extract sections using regex first, then parse specific ones as AST
            section_extracts = self._extract_sections_by_regex(keymap_content, template_vars)

            # Always extract layers - use regex first, then AST if needed
            if "keymap" in section_extracts:
                layers_data = self._extract_layers_from_regex_section(section_extracts["keymap"])
                if layers_data:
                    extracted["layers"] = layers_data

            # Extract behaviors if template supports them
            if "user_behaviors_dtsi" in template_vars and "behaviors" in section_extracts:
                behaviors = self._parse_behaviors_section_ast(section_extracts["behaviors"])
                if behaviors:
                    extracted["behaviors"] = behaviors

            # Extract macros if template supports them
            if "user_macros_dtsi" in template_vars and "macros" in section_extracts:
                macros = self._parse_macros_section_ast(section_extracts["macros"])
                if macros:
                    extracted["macros"] = macros  # type: ignore[assignment]

            # Extract combos if template supports them
            if "combos_dtsi" in template_vars and "combos" in section_extracts:
                combos = self._parse_combos_section_ast(section_extracts["combos"])
                if combos:
                    extracted["combos"] = combos  # type: ignore[assignment]

            # Extract custom sections if template supports them
            custom_sections = {}
            if "custom_defined_behaviors" in template_vars and "custom_behaviors" in section_extracts:
                custom_sections["behaviors"] = section_extracts["custom_behaviors"]

            if "custom_devicetree" in template_vars and "custom_devicetree" in section_extracts:
                custom_sections["devicetree"] = section_extracts["custom_devicetree"]

            if custom_sections:
                extracted["custom"] = custom_sections

            return extracted if extracted else None

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Template sections extraction failed: %s", e, exc_info=exc_info
            )
            result.errors.append(f"Template sections extraction failed: {e}")
            return None

    def _extract_user_custom_sections_ast(
        self, roots: list[DTNode], template_vars: list[str]
    ) -> dict[str, str] | None:
        """Extract user-defined custom sections from AST using template knowledge.

        Args:
            roots: List of parsed device tree root nodes
            template_vars: List of template variable names

        Returns:
            Dictionary with custom sections that match template variables
        """
        custom = {}

        try:
            # Look for custom behavior definitions if template supports them
            if "custom_defined_behaviors" in template_vars:
                custom_behaviors = self._extract_custom_behaviors_from_roots(roots)
                if custom_behaviors:
                    custom["behaviors"] = custom_behaviors

            # Look for custom device tree code if template supports it
            if "custom_devicetree" in template_vars:
                custom_dt = self._extract_custom_devicetree_from_roots(roots)
                if custom_dt:
                    custom["devicetree"] = custom_dt

            return custom if custom else None

        except Exception as e:
            self.logger.warning("Failed to extract user custom sections: %s", e)
            return None

    def _extract_custom_behaviors_from_roots(self, roots: list[DTNode]) -> str:
        """Extract custom behavior definitions that are user-defined.

        Args:
            roots: List of parsed device tree root nodes

        Returns:
            String containing custom behavior definitions
        """
        # Look for behavior definitions that are not in standard template sections
        # This would be behaviors defined outside of macros/combos/behaviors nodes
        # For now, return empty string as this requires more complex analysis
        return ""

    def _extract_custom_devicetree_from_roots(self, roots: list[DTNode]) -> str:
        """Extract custom device tree code that is user-defined.

        Args:
            roots: List of parsed device tree root nodes

        Returns:
            String containing custom device tree code
        """
        # Look for device tree nodes/properties that are not part of standard template
        # This would include custom nodes, includes, etc.
        # For now, return empty string as this requires more complex analysis
        return ""

    def _extract_sections_by_regex(
        self, keymap_content: str, template_vars: list[str]
    ) -> dict[str, str]:
        """Extract specific sections from keymap content using regex patterns.

        Args:
            keymap_content: Full keymap file content
            template_vars: List of template variable names to guide extraction

        Returns:
            Dictionary mapping section names to their content
        """
        sections = {}

        # Always extract keymap section for layers
        keymap_section = self._extract_balanced_node(keymap_content, "keymap")
        if keymap_section:
            sections["keymap"] = keymap_section

        # Extract behaviors section if template needs it
        if "user_behaviors_dtsi" in template_vars:
            behaviors_section = self._extract_balanced_node(keymap_content, "behaviors")
            if behaviors_section:
                sections["behaviors"] = behaviors_section

        # Extract macros section if template needs it
        if "user_macros_dtsi" in template_vars:
            macros_section = self._extract_balanced_node(keymap_content, "macros")
            if macros_section:
                sections["macros"] = macros_section

        # Extract combos if template needs them
        if "combos_dtsi" in template_vars:
            # Combos can be directly under root node
            combos_section = self._extract_combos_content(keymap_content)
            if combos_section:
                sections["combos"] = combos_section

        # Extract custom sections if template supports them
        if "custom_defined_behaviors" in template_vars:
            custom_behaviors = self._extract_custom_behavior_content(keymap_content)
            if custom_behaviors:
                sections["custom_behaviors"] = custom_behaviors

        if "custom_devicetree" in template_vars:
            custom_dt = self._extract_custom_devicetree_content(keymap_content)
            if custom_dt:
                sections["custom_devicetree"] = custom_dt

        return sections

    def _extract_layers_from_regex_section(self, keymap_section: str) -> dict[str, Any] | None:
        """Extract layer data from a regex-extracted keymap section.

        Args:
            keymap_section: Keymap section content from regex extraction

        Returns:
            Dictionary with layer_names and layers lists
        """
        # Use existing regex-based layer extraction
        return self._extract_layers_from_keymap(keymap_section)

    def _parse_behaviors_section_ast(self, behaviors_section: str) -> dict[str, Any] | None:
        """Parse behaviors section using targeted AST parsing.

        Args:
            behaviors_section: Behaviors section content

        Returns:
            Dictionary with parsed behaviors
        """
        try:
            # Parse just this section as AST
            root, _ = parse_dt_safe(behaviors_section)
            if not root:
                return None

            # Use existing behavior extraction
            behaviors_dict, _ = self.behavior_extractor.extract_behaviors_with_metadata(
                [root], behaviors_section
            )
            converted_behaviors = self.model_converter.convert_behaviors(behaviors_dict)

            if converted_behaviors.get("hold_taps"):
                return {"hold_taps": converted_behaviors["hold_taps"]}

            return None

        except Exception as e:
            self.logger.warning("Failed to parse behaviors section as AST: %s", e)
            return None

    def _parse_macros_section_ast(self, macros_section: str) -> list[Any] | None:
        """Parse macros section using targeted AST parsing.

        Args:
            macros_section: Macros section content

        Returns:
            List of parsed macros
        """
        try:
            # Parse just this section as AST
            root, _ = parse_dt_safe(macros_section)
            if not root:
                return None

            # Use existing behavior extraction for macros
            behaviors_dict, _ = self.behavior_extractor.extract_behaviors_with_metadata(
                [root], macros_section
            )
            converted_behaviors = self.model_converter.convert_behaviors(behaviors_dict)

            return converted_behaviors.get("macros")

        except Exception as e:
            self.logger.warning("Failed to parse macros section as AST: %s", e)
            return None

    def _parse_combos_section_ast(self, combos_section: str) -> list[Any] | None:
        """Parse combos section using targeted AST parsing.

        Args:
            combos_section: Combos section content

        Returns:
            List of parsed combos
        """
        try:
            # Parse just this section as AST
            root, _ = parse_dt_safe(combos_section)
            if not root:
                return None

            # Use existing behavior extraction for combos
            behaviors_dict, _ = self.behavior_extractor.extract_behaviors_with_metadata(
                [root], combos_section
            )
            converted_behaviors = self.model_converter.convert_behaviors(behaviors_dict)

            return converted_behaviors.get("combos")

        except Exception as e:
            self.logger.warning("Failed to parse combos section as AST: %s", e)
            return None

    def _extract_combos_content(self, keymap_content: str) -> str | None:
        """Extract combos content using regex patterns.

        Args:
            keymap_content: Full keymap content

        Returns:
            String containing combos content or None if not found
        """
        # First try to extract the entire combos container node
        combos_container = self._extract_balanced_node(keymap_content, "combos")
        if combos_container:
            return combos_container

        # Fallback: Look for individual combo definitions with any name pattern
        # Combos can have any name, not just "combo_" prefix
        # Look for patterns like: some_name { timeout-ms = ...; key-positions = ...; bindings = ...; }
        combo_pattern = r"\w+\s*\{\s*[^}]*(?:timeout-ms|key-positions|bindings)[^}]*\}"
        combos = re.findall(combo_pattern, keymap_content, re.DOTALL)

        # Filter to only include nodes that look like combo definitions
        # (contain combo-specific properties)
        actual_combos = []
        for combo in combos:
            if all(prop in combo for prop in ["timeout-ms", "key-positions", "bindings"]):
                actual_combos.append(combo)

        if actual_combos:
            return "\n".join(actual_combos)
        return None

    def _extract_custom_behavior_content(self, keymap_content: str) -> str | None:
        """Extract custom behavior definitions outside standard sections.

        Args:
            keymap_content: Full keymap content

        Returns:
            String containing custom behavior content or None if not found
        """
        # This would identify behavior definitions outside standard sections
        # For now, return None as this requires more sophisticated analysis
        return None

    def _extract_custom_devicetree_content(self, keymap_content: str) -> str | None:
        """Extract custom device tree content outside standard template sections.

        Args:
            keymap_content: Full keymap content

        Returns:
            String containing custom device tree content or None if not found
        """
        # This would identify custom DT code outside template sections
        # For now, return None as this requires more sophisticated analysis
        return None


def create_zmk_keymap_parser() -> ZmkKeymapParser:
    """Create ZMK keymap parser instance.

    Returns:
        Configured ZmkKeymapParser instance
    """
    return ZmkKeymapParser()
