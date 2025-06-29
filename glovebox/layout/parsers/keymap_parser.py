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

                self.logger.debug(
                    "Set %d global comments on all model converters for description extraction",
                    len(global_comments),
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
                self.logger.debug("=== COMMENT EXTRACTION DEBUG ===")
                self.logger.debug(
                    "Raw comments from metadata_dict: %d", len(comments_raw)
                )

                for i, comment in enumerate(comments_raw[:5]):  # Show first 5
                    self.logger.debug("  Comment %d: %s", i + 1, comment)

                layout_data.keymap_metadata.comments = [
                    self._convert_comment_to_model(comment) for comment in comments_raw
                ]

                self.logger.debug(
                    "Converted to KeymapComment models: %d",
                    len(layout_data.keymap_metadata.comments),
                )

                # Show a sample of the final comments
                for i, comment in enumerate(layout_data.keymap_metadata.comments[:3]):
                    self.logger.debug(
                        "  Final comment %d: Line %d [%s]: %s",
                        i + 1,
                        comment.line,
                        comment.context,
                        comment.text[:50],
                    )

                self.logger.debug("=== END COMMENT DEBUG ===")
                self.logger.debug("")
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

                if "custom" in extracted_data:
                    custom = extracted_data["custom"]
                    layout_data.custom_defined_behaviors = custom.get("behaviors", "")
                    layout_data.custom_devicetree = custom.get("devicetree", "")

                    # Handle input listeners if present
                    if "input_listeners" in custom:
                        # Store input listeners in variables section for template usage
                        if (
                            not hasattr(layout_data, "variables")
                            or layout_data.variables is None
                        ):
                            layout_data.variables = {}
                        layout_data.variables["input_listeners_dtsi"] = custom[
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
            # Always try to extract all possible sections, not just those in template_vars
            all_possible_vars = [
                "custom_devicetree",
                "input_listeners_dtsi",
                "user_behaviors_dtsi",
                "user_behaviors_dtsi_alt",
                "custom_defined_behaviors",
                "user_macros_dtsi",
                "combos_dtsi",
            ]
            comment_sections = self._extract_sections_by_comment_delimiters(
                keymap_content, all_possible_vars
            )

            # Then extract remaining sections using regex approach for fallback
            regex_sections = self._extract_sections_by_regex(
                keymap_content, template_vars
            )

            # Always extract layers - use regex first, then AST if needed
            if "keymap" in regex_sections:
                layers_data = self._extract_layers_from_regex_section(
                    regex_sections["keymap"]
                )
                if layers_data:
                    extracted["layers"] = layers_data

            # Extract behaviors - prefer comment delimited content, parse it to structured data
            if (
                "user_behaviors_dtsi" in template_vars
                or "user_behaviors_dtsi" in comment_sections
            ):
                if "user_behaviors_dtsi" in comment_sections:
                    # Store raw content for template usage
                    extracted["behaviors_raw"] = comment_sections["user_behaviors_dtsi"]

                    # Parse raw content to structured data for LayoutData
                    parsed_behaviors = self._parse_behaviors_section_ast(
                        comment_sections["user_behaviors_dtsi"]
                    )
                    if parsed_behaviors:
                        extracted["behaviors"] = parsed_behaviors
                        self.logger.debug(
                            "HYBRID: Successfully parsed behaviors from comment-delimited content: %s",
                            parsed_behaviors,
                        )
                    else:
                        # Fallback to regex parser if AST parsing fails
                        behaviors = self.behavior_parser.parse_behaviors_section(
                            comment_sections["user_behaviors_dtsi"]
                        )
                        if behaviors:
                            extracted["behaviors"] = behaviors
                            self.logger.debug(
                                "HYBRID: Used regex parser for behaviors: %s", behaviors
                            )
                elif "behaviors" in regex_sections:
                    # Parse AST from regex-extracted section
                    behaviors = self._parse_behaviors_section_ast(
                        regex_sections["behaviors"]
                    )
                    if behaviors:
                        extracted["behaviors"] = behaviors

            # Also check alternative behaviors section for additional hold-taps/behaviors
            if "user_behaviors_dtsi_alt" in comment_sections:
                self.logger.debug(
                    "HYBRID: Found alternative behaviors section, processing..."
                )

                # Parse alternative content
                alt_parsed_behaviors = self._parse_behaviors_section_ast(
                    comment_sections["user_behaviors_dtsi_alt"]
                )
                if alt_parsed_behaviors:
                    self.logger.debug(
                        "HYBRID: Successfully parsed alternative behaviors: %s",
                        alt_parsed_behaviors,
                    )

                    # Merge with existing behaviors or create new
                    if "behaviors" in extracted and extracted["behaviors"]:
                        # Merge hold_taps if both sections have them
                        if "hold_taps" in alt_parsed_behaviors:
                            if "hold_taps" not in extracted["behaviors"]:
                                extracted["behaviors"]["hold_taps"] = []
                            extracted["behaviors"]["hold_taps"].extend(
                                alt_parsed_behaviors["hold_taps"]
                            )
                            self.logger.debug(
                                "HYBRID: Merged %d hold_taps from alternative section",
                                len(alt_parsed_behaviors["hold_taps"]),
                            )
                    else:
                        # Use alternative behaviors as primary
                        extracted["behaviors"] = alt_parsed_behaviors
                        self.logger.debug(
                            "HYBRID: Using alternative behaviors as primary behaviors"
                        )

                # Store alternative raw content too
                if not extracted.get("behaviors_raw"):
                    extracted["behaviors_raw"] = comment_sections[
                        "user_behaviors_dtsi_alt"
                    ]
                    self.logger.debug(
                        "HYBRID: Using alternative section for behaviors_raw"
                    )

            # Extract macros - prefer comment delimited content, parse it to structured data
            if (
                "user_macros_dtsi" in template_vars
                or "user_macros_dtsi" in comment_sections
            ):
                if "user_macros_dtsi" in comment_sections:
                    # Store raw content for template usage
                    extracted["macros_raw"] = comment_sections["user_macros_dtsi"]

                    # Parse raw content to structured data for LayoutData
                    parsed_macros = self._parse_macros_section_ast(
                        comment_sections["user_macros_dtsi"]
                    )
                    if parsed_macros:
                        extracted["macros"] = parsed_macros
                        self.logger.debug(
                            "HYBRID: Successfully parsed macros from comment-delimited content: %d macros",
                            len(parsed_macros),
                        )
                    else:
                        # Fallback to regex parser if AST parsing fails
                        macros = self.behavior_parser.parse_macros_section(
                            comment_sections["user_macros_dtsi"]
                        )
                        if macros:
                            extracted["macros"] = macros  # type: ignore[assignment]
                            self.logger.debug(
                                "HYBRID: Used regex parser for macros: %d macros",
                                len(macros),
                            )
                elif "macros" in regex_sections:
                    macros = self._parse_macros_section_ast(regex_sections["macros"])
                    if macros:
                        extracted["macros"] = macros  # type: ignore[assignment]

            # Extract combos - prefer comment delimited content, parse it to structured data
            if "combos_dtsi" in template_vars or "combos_dtsi" in comment_sections:
                if "combos_dtsi" in comment_sections:
                    # Store raw content for template usage
                    extracted["combos_raw"] = comment_sections["combos_dtsi"]

                    # Parse raw content to structured data for LayoutData
                    parsed_combos = self._parse_combos_section_ast(
                        comment_sections["combos_dtsi"]
                    )
                    if parsed_combos:
                        extracted["combos"] = parsed_combos
                        self.logger.debug(
                            "HYBRID: Successfully parsed combos from comment-delimited content: %d combos",
                            len(parsed_combos),
                        )
                    else:
                        # Fallback to regex parser if AST parsing fails
                        combos = self.behavior_parser.parse_combos_section(
                            comment_sections["combos_dtsi"]
                        )
                        if combos:
                            extracted["combos"] = combos  # type: ignore[assignment]
                            self.logger.debug(
                                "HYBRID: Used regex parser for combos: %d combos",
                                len(combos),
                            )
                elif "combos" in regex_sections:
                    combos = self._parse_combos_section_ast(regex_sections["combos"])
                    if combos:
                        extracted["combos"] = combos  # type: ignore[assignment]

            # Extract custom sections - prefer comment delimited content
            custom_sections = {}

            # Custom behaviors
            if "custom_defined_behaviors" in template_vars:
                if "custom_defined_behaviors" in comment_sections:
                    custom_sections["behaviors"] = comment_sections[
                        "custom_defined_behaviors"
                    ]
                elif "custom_behaviors" in regex_sections:
                    custom_sections["behaviors"] = regex_sections["custom_behaviors"]

            # Custom devicetree
            if "custom_devicetree" in template_vars:
                if "custom_devicetree" in comment_sections:
                    custom_sections["devicetree"] = comment_sections[
                        "custom_devicetree"
                    ]
                elif "custom_devicetree" in regex_sections:
                    custom_sections["devicetree"] = regex_sections["custom_devicetree"]

            # Input listeners
            if "input_listeners_dtsi" in template_vars:
                if "input_listeners_dtsi" in comment_sections:
                    custom_sections["input_listeners"] = comment_sections[
                        "input_listeners_dtsi"
                    ]

            if custom_sections:
                extracted["custom"] = custom_sections

            # Store raw comment sections for template variable usage
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

    def _extract_layers_from_regex_section(
        self, keymap_section: str
    ) -> dict[str, Any] | None:
        """Extract layer data from a regex-extracted keymap section.

        Args:
            keymap_section: Keymap section content from regex extraction

        Returns:
            Dictionary with layer_names and layers lists
        """
        # Use existing regex-based layer extraction
        return self._extract_layers_from_keymap(keymap_section)

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
        self, keymap_content: str, template_vars: list[str]
    ) -> dict[str, str]:
        """Extract sections from keymap content using comment-based delimiters.

        This method extracts content between comment delimiters like:
        /* Custom Device-tree */
        [actual device tree content]

        /* Input Listeners */

        Args:
            keymap_content: Full keymap file content
            template_vars: List of template variable names to guide extraction

        Returns:
            Dictionary mapping template variable names to their extracted content
        """
        sections = {}

        # Debug: Log that method is being called
        self.logger.debug(
            "_extract_sections_by_comment_delimiters called with template_vars: %s",
            template_vars,
        )

        # Define comment delimiter patterns - these match actual generated content
        delimiter_patterns = {
            "custom_devicetree": {
                "start": r"/\*\s*Custom\s+Device-tree\s*\*/",
                "end": r"/\*\s*Input\s+Listeners\s*\*/",
            },
            "input_listeners_dtsi": {
                "start": r"/\*\s*Input\s+Listeners\s*\*/",
                "end": r"/\*\s*System\s+behavior\s+and\s+Macros\s*\*/",
            },
            "system_behaviors_dts": {
                "start": r"/\*\s*System\s+behavior\s+and\s+Macros\s*\*/",
                "end": r"/\*\s*(?:#define\s+for\s+key\s+positions|Custom\s+Defined\s+Behaviors|Automatically\s+generated\s+macro|$)",
            },
            "custom_defined_behaviors_dtsi": {
                "start": r"/\*\s*Custom\s+Defined\s+Behaviors\s*\*/",
                "end": r"/\*\s*(?:Automatically\s+generated\s+macro|Automatically\s+generated\s+behavior|Automatically\s+generated\s+combos|Automatically\s+generated\s+keymap|$)",
            },
            "user_macros_dtsi": {
                "start": r"/\*\s*Automatically\s+generated\s+macro\s+definitions\s*\*/",
                "end": r"/\*\s*(?:Automatically\s+generated\s+behavior|Automatically\s+generated\s+combos|Automatically\s+generated\s+keymap|$)",
            },
            "user_behaviors_dtsi": {
                "start": r"/\*\s*Automatically\s+generated\s+behavior\s+definitions\s*\*/",
                "end": r"/\*\s*(?:Automatically\s+generated\s+combos|Automatically\s+generated\s+keymap|$)",
            },
            "combos_dtsi": {
                "start": r"/\*\s*Automatically\s+generated\s+combos\s+definitions\s*\*/",
                "end": r"/\*\s*(?:Automatically\s+generated\s+keymap|$)",
            },
        }

        # Only extract sections that are needed by the template
        for var_name, pattern in delimiter_patterns.items():
            if var_name not in template_vars:
                self.logger.debug("Skipping %s - not in template_vars", var_name)
                continue

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
