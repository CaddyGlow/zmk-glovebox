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
from .dt_parser import parse_dt_safe
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
                    return config_dir / template_file

            # Fallback to default template location in the project
            project_root = Path(__file__).parent.parent.parent.parent
            return (
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

        # Find all behavior patterns - behaviors start with & and may have parameters
        # This regex finds complete behaviors like &kp Q, &mt LSHIFT A, &trans, etc.
        behavior_pattern = r"&[a-zA-Z_][a-zA-Z0-9_]*(?:\s+[^\s&]+)*"
        behavior_matches = re.findall(behavior_pattern, cleaned_content)

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
                extracted["macros"] = macros

        # Extract combos if template supports them
        if "combos_dtsi" in template_vars:
            combos = self.behavior_parser.parse_combos_section(keymap_content)
            if combos:
                extracted["combos"] = combos

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
            # Parse content into AST
            root, parse_errors = parse_dt_safe(keymap_content)

            if parse_errors:
                for error in parse_errors:
                    result.warnings.append(str(error))

            if not root:
                result.errors.append("Failed to parse device tree AST")
                return None

            # Extract basic metadata
            layout_data = LayoutData(keyboard="unknown", title="Imported Keymap")

            # Extract layers using AST
            layers_data = self._extract_layers_from_ast(root)
            if layers_data:
                layout_data.layer_names = layers_data["layer_names"]
                layout_data.layers = layers_data["layers"]
                result.extracted_sections["layers"] = layers_data

            # Extract all behaviors using AST
            behaviors_dict = self.behavior_extractor.extract_all_behaviors(root)
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

            # Extract custom device tree code (remaining sections)
            custom_code = self._extract_custom_sections_ast(root)
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
            # Parse content into AST
            root, parse_errors = parse_dt_safe(keymap_content)

            if parse_errors:
                for error in parse_errors:
                    result.warnings.append(str(error))

            if not root:
                result.errors.append("Failed to parse device tree AST")
                return None

            # For now, use same logic as full parsing
            # TODO: Implement template-aware extraction that only gets user-defined sections
            return self._parse_full_keymap_ast(keymap_content, result)

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
            # Find keymap node
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
            for binding_item in bindings_value.value:
                binding_str = str(binding_item).strip()
                if binding_str:
                    try:
                        # Use the existing LayoutBinding.from_str method
                        binding = LayoutBinding.from_str(binding_str)
                        bindings.append(binding)
                    except Exception as e:
                        self.logger.warning(
                            "Failed to parse binding '%s': %s", binding_str, e
                        )
                        # Create fallback binding
                        bindings.append(LayoutBinding(value=binding_str, params=[]))
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


def create_zmk_keymap_parser() -> ZmkKeymapParser:
    """Create ZMK keymap parser instance.

    Returns:
        Configured ZmkKeymapParser instance
    """
    return ZmkKeymapParser()
