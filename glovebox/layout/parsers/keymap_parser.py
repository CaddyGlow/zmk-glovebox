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
    from glovebox.protocols import TemplateAdapterProtocol


class ParsingMode(str, Enum):
    """Keymap parsing modes."""

    FULL = "full"
    TEMPLATE_AWARE = "template"


class ParsingMethod(str, Enum):
    """Keymap parsing method."""

    AST = "ast"  # AST-based parsing


class KeymapParseResult(GloveboxBaseModel):
    """Result of keymap parsing operation."""

    success: bool
    layout_data: LayoutData | None = None
    errors: list[str] = []
    warnings: list[str] = []
    parsing_mode: ParsingMode
    parsing_method: ParsingMethod = ParsingMethod.AST
    extracted_sections: dict[str, Any] = {}


class ZmkKeymapParser:
    """Parser for converting ZMK keymap files back to glovebox JSON layouts.

    Supports two parsing modes:
    1. FULL: Parse complete standalone keymap files
    2. TEMPLATE_AWARE: Use keyboard profile templates to extract only user data
    """

    def __init__(
        self,
        template_adapter: "TemplateAdapterProtocol | None" = None,
        behavior_parser: Any | None = None,
        behavior_extractor: Any | None = None,
        model_converter: Any | None = None,
    ) -> None:
        """Initialize the keymap parser with explicit dependencies.

        Args:
            template_adapter: Template adapter for processing template files
            behavior_parser: Parser for behavior sections
            behavior_extractor: AST-based behavior extractor
            model_converter: Model converter for behaviors
        """
        self.logger = logging.getLogger(__name__)

        # Initialize dependencies with factory functions if not provided
        self.template_adapter = template_adapter or create_template_adapter()
        self.behavior_parser = behavior_parser or create_behavior_parser()
        self.behavior_extractor = (
            behavior_extractor or create_universal_behavior_extractor()
        )
        self.model_converter = model_converter or create_universal_model_converter()

    def parse_keymap(
        self,
        keymap_file: Path,
        mode: ParsingMode = ParsingMode.TEMPLATE_AWARE,
        keyboard_profile: str | None = None,
        method: ParsingMethod = ParsingMethod.AST,
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

            # Parse based on mode using AST method
            if mode == ParsingMode.FULL:
                layout_data = self._parse_full_keymap_ast(keymap_content, result)
            else:
                # Ensure keyboard_profile is not None for template-aware parsing
                if not keyboard_profile:
                    result.errors.append(
                        "Keyboard profile is required for template-aware parsing"
                    )
                    return result

                layout_data = self._parse_template_aware_ast(
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

            # Pass global comments to model converter for description extraction
            if metadata_dict and "comments" in metadata_dict:
                # Set global comments on all individual converter instances
                global_comments = metadata_dict["comments"]
                self.model_converter.hold_tap_converter._global_comments = (
                    global_comments
                )
                self.model_converter.macro_converter._global_comments = global_comments
                self.model_converter.combo_converter._global_comments = global_comments
                self.model_converter.tap_dance_converter._global_comments = (
                    global_comments
                )
                self.model_converter.sticky_key_converter._global_comments = (
                    global_comments
                )
                self.model_converter.caps_word_converter._global_comments = (
                    global_comments
                )
                self.model_converter.mod_morph_converter._global_comments = (
                    global_comments
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
                comments_raw = metadata_dict.get("comments", [])

                layout_data.keymap_metadata.comments = [
                    self._convert_comment_to_model(comment) for comment in comments_raw
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

            if extracted_data and "behaviors" in extracted_data:
                behaviors = extracted_data["behaviors"]
                self.logger.debug("BEHAVIORS DEBUG: %s", behaviors)
                if isinstance(behaviors, dict) and "hold_taps" in behaviors:
                    self.logger.debug(
                        "HOLD_TAPS DEBUG: Found %d hold_taps",
                        len(behaviors["hold_taps"]),
                    )
                else:
                    self.logger.debug(
                        "HOLD_TAPS DEBUG: No hold_taps found - behaviors type: %s",
                        type(behaviors),
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

                # Handle custom devicetree content using actual field names from extraction
                if "custom_devicetree" in extracted_data:
                    layout_data.custom_devicetree = extracted_data["custom_devicetree"]

                if "custom_defined_behaviors" in extracted_data:
                    layout_data.custom_defined_behaviors = extracted_data[
                        "custom_defined_behaviors"
                    ]

                # Handle input listeners using actual field name from extraction
                if "input_listeners" in extracted_data:
                    # Store input listeners in variables section for template usage
                    if (
                        not hasattr(layout_data, "variables")
                        or layout_data.variables is None
                    ):
                        layout_data.variables = {}
                    layout_data.variables["input_listeners_dtsi"] = extracted_data[
                        "input_listeners"
                    ]

                if "variables" in extracted_data:
                    layout_data.variables = extracted_data["variables"]

                # Store raw sections in variables for template rendering if not already present
                if "behaviors_raw" in extracted_data:
                    if (
                        not hasattr(layout_data, "variables")
                        or layout_data.variables is None
                    ):
                        layout_data.variables = {}
                    layout_data.variables["user_behaviors_dtsi"] = extracted_data[
                        "behaviors_raw"
                    ]

                if "macros_raw" in extracted_data:
                    if (
                        not hasattr(layout_data, "variables")
                        or layout_data.variables is None
                    ):
                        layout_data.variables = {}
                    layout_data.variables["user_macros_dtsi"] = extracted_data[
                        "macros_raw"
                    ]

                if "combos_raw" in extracted_data:
                    if (
                        not hasattr(layout_data, "variables")
                        or layout_data.variables is None
                    ):
                        layout_data.variables = {}
                    layout_data.variables["combos_dtsi"] = extracted_data["combos_raw"]

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

        This method first tries comment delimiter extraction, then falls back to
        regex+AST for sections not found with delimiters.

        Args:
            keymap_content: Original keymap content
            template_vars: List of template variable names from the template
            result: Result object for warnings/errors

        Returns:
            Dictionary with extracted user data sections
        """
        extracted = {}

        try:
            # First, try to extract sections using comment delimiters
            # Define extraction configuration for all possible template sections
            extraction_config = [
                {
                    "tpl_ctx_name": "custom_devicetree",
                    "type": "dtsi",
                    "layer_data_name": "custom_devicetree",
                    "delimiter": [
                        r"/\*\s*Custom\s+Device-tree\s*\*/",
                        r"/\*\s*Input\s+Listeners\s*\*/",
                    ],
                },
                {
                    "tpl_ctx_name": "input_listeners_dtsi",
                    "type": "input_listener",
                    "layer_data_name": "input_listeners",
                    "delimiter": [
                        r"/\*\s*Input\s+Listeners\s*\*/",
                        r"/\*\s*System\s+behavior\s+and\s+Macros\s*\*/",
                    ],
                },
                # Note in LayoutData: this is coming from moergo injected during keymap generation
                {
                    "tpl_ctx_name": "system_behaviors_dts",
                    "type": "dtsi",
                    "layer_data_name": "system_behaviors_raw",
                    "delimiter": [
                        r"/\*\s*System\s+behavior\s+and\s+Macros\s*\*/",
                        r"/\*\s*(?:#define\s+for\s+key\s+positions|Custom\s+Defined\s+Behaviors|Automatically\s+generated\s+macro|$)",
                    ],
                },
                {
                    "tpl_ctx_name": "custom_defined_behaviors",
                    "type": "dtsi",
                    "layer_data_name": "custom_defined_behaviors",
                    "delimiter": [
                        r"/\*\s*Custom\s+Defined\s+Behaviors\s*\*/",
                        r"/\*\s*(?:Automatically\s+generated\s+macro|Automatically\s+generated\s+behavior|Automatically\s+generated\s+combos|Automatically\s+generated\s+keymap|$)",
                    ],
                },
                {
                    "tpl_ctx_name": "user_macros_dtsi",
                    "type": "macro",
                    "layer_data_name": "macros",
                    "delimiter": [
                        r"/\*\s*Automatically\s+generated\s+macro\s+definitions\s*\*/",
                        r"/\*\s*(?:Automatically\s+generated\s+behavior|Automatically\s+generated\s+combos|Automatically\s+generated\s+keymap|$)",
                    ],
                },
                {
                    "tpl_ctx_name": "user_behaviors_dtsi",
                    "type": "behavior",
                    "layer_data_name": "behaviors",
                    "delimiter": [
                        r"/\*\s*Automatically\s+generated\s+behavior\s+definitions\s*\*/",
                        r"/\*\s*(?:Automatically\s+generated\s+combos|Automatically\s+generated\s+keymap|$)",
                    ],
                },
                {
                    "tpl_ctx_name": "combos_dtsi",
                    "type": "combo",
                    "layer_data_name": "combos",
                    "delimiter": [
                        r"/\*\s*Automatically\s+generated\s+combos\s+definitions\s*\*/",
                        r"/\*\s*(?:Automatically\s+generated\s+keymap|$)",
                    ],
                },
                {
                    "tpl_ctx_name": "keymap_node",
                    "type": "keymap",
                    "layer_data_name": "layers",
                    "delimiter": [
                        r"/\*\s*Automatically\s+generated\s+keymap\s*\*/",
                        r"\Z",  # End of string
                    ],
                },
            ]

            # Extract sections using the new config format
            comment_sections = self._extract_sections_by_comment_delimiters(
                keymap_content, extraction_config
            )

            # Process all configured sections based on extraction config
            for config in extraction_config:
                tpl_ctx_name: str = str(config["tpl_ctx_name"])
                extraction_type: str = str(config["type"])
                layer_data_name: str = str(config["layer_data_name"])

                # Skip if section not found in comment extraction
                if tpl_ctx_name not in comment_sections:
                    continue

                content = comment_sections[tpl_ctx_name]
                self.logger.debug(
                    "HYBRID: Processing %s section (type: %s, output: %s)",
                    tpl_ctx_name,
                    extraction_type,
                    layer_data_name,
                )

                if extraction_type == "dtsi":
                    # Store raw DTSI content directly
                    extracted[layer_data_name] = content  # type: ignore[assignment]
                    self.logger.debug(
                        "HYBRID: Stored raw DTSI content for %s (%d chars)",
                        layer_data_name,
                        len(content),
                    )

                elif extraction_type == "behavior":
                    # Parse behaviors using AST
                    parsed_content = self._parse_behaviors_section_ast(content)
                    if parsed_content:
                        if layer_data_name == "behaviors" and "behaviors" in extracted:
                            # Merge with existing behaviors
                            self._merge_behavior_sections(
                                extracted["behaviors"], parsed_content
                            )
                        else:
                            extracted[layer_data_name] = parsed_content
                        self.logger.debug(
                            "HYBRID: Successfully parsed behaviors for %s: %s",
                            layer_data_name,
                            parsed_content,
                        )

                elif extraction_type == "macro":
                    # Parse macros using AST
                    parsed_content = self._parse_macros_section_ast(content)
                    if parsed_content:
                        extracted[layer_data_name] = parsed_content
                        self.logger.debug(
                            "HYBRID: Successfully parsed macros for %s: %s",
                            layer_data_name,
                            parsed_content,
                        )

                elif extraction_type == "combo":
                    # Parse combos using AST
                    parsed_content = self._parse_combos_section_ast(content)
                    if parsed_content:
                        extracted[layer_data_name] = parsed_content
                        self.logger.debug(
                            "HYBRID: Successfully parsed combos for %s: %s",
                            layer_data_name,
                            parsed_content,
                        )

                elif extraction_type == "input_listener":
                    # Store input listeners as raw content for now
                    extracted[layer_data_name] = content  # type: ignore[assignment]
                    self.logger.debug(
                        "HYBRID: Stored input listeners as raw for %s (%d chars)",
                        layer_data_name,
                        len(content),
                    )

                elif extraction_type == "keymap":
                    # Parse keymap using AST to extract layers
                    parsed_content = self._parse_keymap_section_ast(content)
                    if parsed_content:
                        extracted[layer_data_name] = parsed_content
                        self.logger.debug(
                            "HYBRID: Successfully parsed keymap for %s: %s",
                            layer_data_name,
                            parsed_content,
                        )
                else:
                    # Default to raw storage for unknown types
                    self.logger.warning(
                        "HYBRID: Unknown type %s for %s, storing as raw",
                        extraction_type,
                        tpl_ctx_name,
                    )
                    extracted[layer_data_name] = content  # type: ignore[assignment]

            # Store extracted comment sections for template variable usage
            if comment_sections:
                extracted["comment_sections"] = comment_sections

            return extracted if extracted else None

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Template sections extraction failed: %s", e, exc_info=exc_info
            )
            result.errors.append(f"Template sections extraction failed: {e}")
            return None

    def _merge_behavior_sections(
        self, existing_behaviors: dict[str, Any], new_behaviors: dict[str, Any]
    ) -> None:
        """Merge new behavior sections into existing behavior data.

        Args:
            existing_behaviors: Existing behavior data to merge into
            new_behaviors: New behavior data to merge from
        """
        for behavior_type, behaviors in new_behaviors.items():
            if behavior_type in existing_behaviors:
                # Extend existing list
                if isinstance(existing_behaviors[behavior_type], list) and isinstance(
                    behaviors, list
                ):
                    existing_behaviors[behavior_type].extend(behaviors)
                    self.logger.debug(
                        "HYBRID: Merged %d %s behaviors", len(behaviors), behavior_type
                    )
            else:
                # Add new behavior type
                existing_behaviors[behavior_type] = behaviors
                self.logger.debug(
                    "HYBRID: Added %d %s behaviors",
                    len(behaviors) if isinstance(behaviors, list) else 1,
                    behavior_type,
                )

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

    def _parse_behaviors_section_ast(
        self, behaviors_section: str
    ) -> dict[str, Any] | None:
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

    def _parse_keymap_section_ast(self, keymap_section: str) -> dict[str, Any] | None:
        """Parse keymap section using targeted AST parsing to extract layers.

        Args:
            keymap_section: Keymap section content

        Returns:
            Dictionary with layer_names and layers lists
        """
        try:
            # Parse just this section as AST
            root, _ = parse_dt_safe(keymap_section)
            if not root:
                return None

            # Use existing layer extraction method
            return self._extract_layers_from_ast(root)

        except Exception as e:
            self.logger.warning("Failed to parse keymap section as AST: %s", e)
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
            if all(
                prop in combo for prop in ["timeout-ms", "key-positions", "bindings"]
            ):
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

    def _extract_sections_by_comment_delimiters(
        self, keymap_content: str, extraction_config: list[dict[str, Any]]
    ) -> dict[str, str]:
        """Extract sections from keymap content using comment-based delimiters.

        This method extracts content between comment delimiters using the provided
        extraction configuration.

        Args:
            keymap_content: Full keymap file content
            extraction_config: List of extraction configuration dictionaries with
                tpl_ctx_name, type, layer_data_name, and delimiter fields

        Returns:
            Dictionary mapping template variable names to their extracted content
        """
        sections = {}

        # Debug: Log that method is being called
        self.logger.debug(
            "_extract_sections_by_comment_delimiters called with %d configs",
            len(extraction_config),
        )

        # Convert delimiter patterns from extraction config
        delimiter_patterns = {}
        for config in extraction_config:
            tpl_name = config["tpl_ctx_name"]
            delimiters = config["delimiter"]

            # Use the regex patterns directly from config
            if len(delimiters) >= 2:
                delimiter_patterns[tpl_name] = {
                    "start": delimiters[0],  # Already regex patterns
                    "end": delimiters[1] if len(delimiters) > 1 else "$",
                    "config": config,  # Store full config for later use
                }
            else:
                self.logger.warning(
                    "Invalid delimiter config for %s: expected 2 delimiters, got %d",
                    tpl_name,
                    len(delimiters),
                )

        # Extract all configured sections
        for var_name, pattern in delimiter_patterns.items():
            self.logger.debug("Processing section: %s", var_name)

            try:
                # Create regex pattern to capture content between delimiters
                start_pattern = pattern["start"]
                end_pattern = pattern["end"]

                # Find the start delimiter
                start_match = re.search(
                    start_pattern, keymap_content, re.IGNORECASE | re.MULTILINE
                )
                if not start_match:
                    self.logger.debug("No start delimiter found for %s", var_name)
                    continue

                self.logger.debug(
                    "Found start delimiter for %s at position %d",
                    var_name,
                    start_match.start(),
                )

                # Find the end delimiter after the start position
                search_start = start_match.end()
                end_match = re.search(
                    end_pattern,
                    keymap_content[search_start:],
                    re.IGNORECASE | re.MULTILINE,
                )

                if end_match:
                    # Extract content between delimiters
                    content_start = search_start
                    content_end = search_start + end_match.start()
                    section_content = keymap_content[content_start:content_end].strip()
                else:
                    # If no end delimiter found, extract to end of file
                    section_content = keymap_content[search_start:].strip()

                if section_content:
                    self.logger.debug(
                        "Found content for %s: %d chars", var_name, len(section_content)
                    )
                    # Clean up the content - remove template variables and empty content
                    cleaned_content = self._clean_extracted_section_content(
                        section_content, var_name
                    )
                    if cleaned_content:
                        sections[var_name] = cleaned_content
                        self.logger.debug(
                            "Added %s to sections after cleaning: %d chars",
                            var_name,
                            len(cleaned_content),
                        )
                    else:
                        self.logger.debug(
                            "Content for %s was empty after cleaning", var_name
                        )
                else:
                    self.logger.debug("No content found for %s", var_name)

            except re.error as e:
                self.logger.warning(
                    "Regex error extracting section %s: %s", var_name, e
                )
                continue

        return sections

    def _clean_extracted_section_content(self, content: str, section_type: str) -> str:
        """Clean extracted section content by removing empty lines and comments.

        Args:
            content: Raw extracted content
            section_type: Type of section being cleaned

        Returns:
            Cleaned content or empty string if nothing meaningful found
        """
        # Split into lines and process
        lines = []
        for line in content.split("\n"):
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                continue

            # Skip pure comment lines (but keep lines with code + comments)
            if stripped.startswith("//") or (
                stripped.startswith("/*") and stripped.endswith("*/")
            ):
                continue

            # Skip lines that look like template comments
            if "{#" in stripped and "#}" in stripped:
                continue

            lines.append(line)

        return "\n".join(lines) if lines else ""

    def _extract_layers_from_regex_section(
        self, keymap_section: str
    ) -> dict[str, Any] | None:
        """Extract layer data from a regex-extracted keymap section.

        This method is deprecated and now uses AST parsing internally.
        """
        # Use AST parsing instead of regex
        roots, _ = parse_dt_multiple_safe(keymap_section)
        if roots:
            for root in roots:
                layers_data = self._extract_layers_from_ast(root)
                if layers_data:
                    return layers_data
        return None


def create_zmk_keymap_parser(
    template_adapter: "TemplateAdapterProtocol | None" = None,
    behavior_parser: Any | None = None,
    behavior_extractor: Any | None = None,
    model_converter: Any | None = None,
) -> ZmkKeymapParser:
    """Create ZMK keymap parser instance with explicit dependencies.

    Args:
        template_adapter: Optional template adapter (uses create_template_adapter() if None)
        behavior_parser: Optional behavior parser (uses create_behavior_parser() if None)
        behavior_extractor: Optional behavior extractor (uses create_universal_behavior_extractor() if None)
        model_converter: Optional model converter (uses create_universal_model_converter() if None)

    Returns:
        Configured ZmkKeymapParser instance with all dependencies injected
    """
    return ZmkKeymapParser(
        template_adapter=template_adapter,
        behavior_parser=behavior_parser,
        behavior_extractor=behavior_extractor,
        model_converter=model_converter,
    )


def create_zmk_keymap_parser_from_profile(
    profile: "KeyboardProfile",
    template_adapter: "TemplateAdapterProtocol | None" = None,
    behavior_parser: Any | None = None,
    behavior_extractor: Any | None = None,
    model_converter: Any | None = None,
) -> ZmkKeymapParser:
    """Create ZMK keymap parser instance configured for a specific keyboard profile.

    This factory function follows the CLAUDE.md pattern of profile-based configuration
    loading, similar to other domains in the codebase.

    Args:
        profile: Keyboard profile containing configuration for the parser
        template_adapter: Optional template adapter (uses create_template_adapter() if None)
        behavior_parser: Optional behavior parser (uses create_behavior_parser() if None)
        behavior_extractor: Optional behavior extractor (uses create_universal_behavior_extractor() if None)
        model_converter: Optional model converter (uses create_universal_model_converter() if None)

    Returns:
        Configured ZmkKeymapParser instance with profile-specific settings
    """
    # Create parser with dependencies
    parser = create_zmk_keymap_parser(
        template_adapter=template_adapter,
        behavior_parser=behavior_parser,
        behavior_extractor=behavior_extractor,
        model_converter=model_converter,
    )

    # Configure parser based on profile settings
    # This could include profile-specific parsing preferences, template paths, etc.
    # For now, we return the standard parser, but this provides the extension point
    # for profile-based configuration

    return parser
