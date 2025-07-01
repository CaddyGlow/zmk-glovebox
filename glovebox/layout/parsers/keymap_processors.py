"""Keymap processing strategies for different parsing modes."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from glovebox.layout.models import LayoutData

from .dt_parser import parse_dt_lark_safe
from .parsing_models import ParsingContext, get_default_extraction_config
from .section_extractor import create_section_extractor


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile
    from glovebox.protocols import TemplateAdapterProtocol

    class SectionExtractorProtocol(Protocol):
        def extract_sections(self, content: str, configs: list) -> dict: ...
        def process_extracted_sections(self, sections: dict, context) -> dict: ...
        @property
        def behavior_extractor(self) -> object: ...


class BaseKeymapProcessor:
    """Base class for keymap processors with common functionality."""

    def __init__(
        self,
        section_extractor: "SectionExtractorProtocol | None" = None,
        template_adapter: "TemplateAdapterProtocol | None" = None,
    ) -> None:
        """Initialize base processor."""
        self.logger = logging.getLogger(__name__)
        self.section_extractor = section_extractor or create_section_extractor()

        if template_adapter is None:
            from glovebox.adapters import create_template_adapter

            self.template_adapter = create_template_adapter()
        else:
            self.template_adapter = template_adapter

    def process(self, context: ParsingContext) -> LayoutData | None:
        """Process keymap content according to parsing strategy."""
        raise NotImplementedError("Subclasses must implement process method")

    def _create_base_layout_data(self, context: ParsingContext) -> LayoutData:
        """Create base layout data with default values."""
        keyboard_name = "unknown"
        if context.keyboard_profile_name:
            keyboard_name = context.keyboard_profile_name

        return LayoutData(keyboard=keyboard_name, title="Imported Keymap")


class FullKeymapProcessor(BaseKeymapProcessor):
    """Processor for full keymap parsing mode.

    This mode parses complete standalone keymap files without template awareness.
    """

    def process(self, context: ParsingContext) -> LayoutData | None:
        """Process complete keymap file using AST approach.

        Args:
            context: Parsing context with keymap content

        Returns:
            Parsed LayoutData or None if parsing fails
        """
        try:
            # Parse content into AST using enhanced parser for comment support
            try:
                from .dt_parser import parse_dt_multiple_safe

                roots, parse_errors = parse_dt_multiple_safe(context.keymap_content)
            except ImportError:
                # Fallback to Lark parser if enhanced parser not available
                roots, parse_errors = parse_dt_lark_safe(context.keymap_content)

            if parse_errors:
                context.warnings.extend([str(error) for error in parse_errors])

            if not roots:
                context.errors.append("Failed to parse device tree AST")
                return None

            # Create base layout data with enhanced metadata
            layout_data = self._create_enhanced_layout_data(context)

            # Extract layers using AST from all roots
            layers_data = self._extract_layers_from_roots(roots)
            if layers_data:
                layout_data.layer_names = layers_data["layer_names"]
                layout_data.layers = layers_data["layers"]

            # Extract behaviors and metadata
            behaviors_dict, metadata_dict = self._extract_behaviors_and_metadata(
                roots, context.keymap_content
            )

            # Populate behaviors directly (already converted by AST converter)
            self._populate_behaviors_in_layout(layout_data, behaviors_dict)

            # Populate keymap metadata for round-trip preservation
            if metadata_dict:
                self._populate_keymap_metadata(layout_data, metadata_dict)

            # Extract custom device tree code
            custom_code = self._extract_custom_sections(roots)
            if custom_code:
                layout_data.custom_defined_behaviors = custom_code.get("behaviors", "")
                layout_data.custom_devicetree = custom_code.get("devicetree", "")

            return layout_data

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Full keymap parsing failed: %s", e, exc_info=exc_info)
            context.errors.append(f"Full parsing failed: {e}")
            return None

    def _extract_layers_from_roots(
        self, roots: list[object]
    ) -> dict[str, object] | None:
        """Extract layer definitions from AST roots.

        Args:
            roots: List of parsed device tree root nodes

        Returns:
            Dictionary with layer_names and layers lists
        """
        # Import here to avoid circular dependency
        from .keymap_parser import ZmkKeymapParser

        temp_parser = ZmkKeymapParser()

        for root in roots:
            layers_data = temp_parser._extract_layers_from_ast(root)
            if layers_data:
                return layers_data

        return None

    def _extract_behaviors_and_metadata(
        self, roots: list[object], content: str
    ) -> tuple[dict[str, object], dict[str, object]]:
        """Extract behaviors and metadata from AST roots.

        Args:
            roots: List of parsed device tree root nodes
            content: Original keymap content

        Returns:
            Tuple of (behaviors_dict, metadata_dict)
        """
        # Extract behaviors using AST converter with comment support
        behavior_models, metadata = (
            self.section_extractor.behavior_extractor.extract_behaviors_as_models(
                roots, content
            )
        )
        return behavior_models, metadata

    def _populate_behaviors_in_layout(
        self, layout_data: LayoutData, converted_behaviors: dict[str, object]
    ) -> None:
        """Populate layout data with converted behaviors.

        Args:
            layout_data: Layout data to populate
            converted_behaviors: Converted behavior data
        """
        if converted_behaviors.get("hold_taps"):
            layout_data.hold_taps = converted_behaviors["hold_taps"]

        if converted_behaviors.get("macros"):
            layout_data.macros = converted_behaviors["macros"]

        if converted_behaviors.get("combos"):
            layout_data.combos = converted_behaviors["combos"]

        if converted_behaviors.get("input_listeners"):
            if layout_data.input_listeners is None:
                layout_data.input_listeners = []
            layout_data.input_listeners.extend(converted_behaviors["input_listeners"])

    def _populate_keymap_metadata(
        self, layout_data: LayoutData, metadata_dict: dict[str, object]
    ) -> None:
        """Populate keymap metadata in layout data.

        Args:
            layout_data: Layout data to populate
            metadata_dict: Metadata dictionary from extraction
        """
        # Import here to avoid circular dependency
        from .keymap_parser import ZmkKeymapParser

        temp_parser = ZmkKeymapParser()

        # Convert metadata to proper model instances
        comments_raw = metadata_dict.get("comments", [])
        layout_data.keymap_metadata.comments = [
            temp_parser._convert_comment_to_model(comment) for comment in comments_raw
        ]

        layout_data.keymap_metadata.includes = [
            temp_parser._convert_include_to_model(include)
            for include in metadata_dict.get("includes", [])
        ]

        layout_data.keymap_metadata.config_directives = [
            temp_parser._convert_directive_to_model(directive)
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

        # Set dependency information
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
        layout_data.keymap_metadata.source_file = ""

    def _extract_custom_sections(self, roots: list[object]) -> dict[str, str]:
        """Extract custom device tree sections from AST roots.

        Args:
            roots: List of parsed device tree root nodes

        Returns:
            Dictionary with custom sections (placeholder implementation)
        """
        # Placeholder implementation - would extract custom sections
        # not covered by standard behaviors
        return {"behaviors": "", "devicetree": ""}

    def _create_enhanced_layout_data(self, context: ParsingContext) -> LayoutData:
        """Create enhanced layout data with better metadata extraction.

        Args:
            context: Parsing context with keymap content

        Returns:
            LayoutData with enhanced metadata
        """
        # Extract keyboard name and clean it up
        keyboard_name = "unknown"
        if context.keyboard_profile_name:
            keyboard_name = context.keyboard_profile_name
            # Handle cases where keyboard_name includes path like "glove80/main"
            if "/" in keyboard_name:
                keyboard_name = keyboard_name.split("/")[0]

        # Extract title from file content if available
        title = self._extract_title_from_content(context.keymap_content)

        # Create layout data with enhanced metadata
        layout_data = LayoutData(
            keyboard=keyboard_name, title=title or "Imported Keymap"
        )

        # Extract and set additional metadata from comments
        self._extract_metadata_from_comments(layout_data, context.keymap_content)

        return layout_data

    def _extract_title_from_content(self, content: str) -> str | None:
        """Extract title from keymap file comments.

        Args:
            content: Keymap file content

        Returns:
            Extracted title or None if not found
        """
        # Look for common title patterns in comments
        import re

        # Pattern 1: Look for layout name in comments
        title_patterns = [
            r"(?:^|\n)\s*(?://|\*)\s*(.+?)(?:\s+layout|\s+keymap|$)",
            r"(?:^|\n)\s*/\*\s*(.+?)\s*\*/",
            r"(?:^|\n)\s*//\s*(.+?)(?:\n|$)",
        ]

        for pattern in title_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                cleaned = match.strip()
                # Skip copyright, include statements, and generic comments
                if (
                    cleaned
                    and not cleaned.lower().startswith(
                        ("copyright", "include", "spdx", "this file", "zmk")
                    )
                    and len(cleaned) > 5
                    and len(cleaned) < 100
                ):
                    return cleaned

        return None

    def _extract_metadata_from_comments(
        self, layout_data: LayoutData, content: str
    ) -> None:
        """Extract additional metadata from file comments.

        Args:
            layout_data: Layout data to populate
            content: Keymap file content
        """
        # For now, set basic values that would typically be in a parsed keymap
        # In a real reverse-engineering scenario, these would be unknown
        if (
            not hasattr(layout_data, "firmware_api_version")
            or layout_data.firmware_api_version is None
        ):
            layout_data.firmware_api_version = "1"

        if not hasattr(layout_data, "locale") or layout_data.locale is None:
            layout_data.locale = "en-US"


class TemplateAwareProcessor(BaseKeymapProcessor):
    """Processor for template-aware parsing mode.

    This mode uses keyboard profile templates to extract only user-defined data.
    """

    def process(self, context: ParsingContext) -> LayoutData | None:
        """Process keymap using template awareness.

        Args:
            context: Parsing context with keymap content and profile

        Returns:
            Parsed LayoutData or None if parsing fails
        """
        try:
            # Load keyboard profile and template information
            profile = self._get_keyboard_profile(context.keyboard_profile_name)
            if not profile:
                context.errors.append(
                    f"Failed to load profile: {context.keyboard_profile_name}"
                )
                return None

            template_path = self._get_template_path(profile)
            if not template_path or not template_path.exists():
                context.errors.append(
                    f"Template not found for profile: {context.keyboard_profile_name}"
                )
                return None

            # Get template variables
            template_content = template_path.read_text(encoding="utf-8")
            template_vars = self.template_adapter.get_template_variables(
                template_content
            )

            # Create base layout data
            # Use the base keyboard name from config rather than profile path
            keyboard_name = profile.keyboard_name
            # Handle cases where keyboard_name includes path like "glove80/main"
            if "/" in keyboard_name:
                keyboard_name = keyboard_name.split("/")[0]

            layout_data = LayoutData(keyboard=keyboard_name, title="Imported Layout")

            # Use configured extraction or default
            extraction_config = (
                context.extraction_config or get_default_extraction_config()
            )

            # Extract global comments for model converters BEFORE section processing
            # Parse content into AST to get global comments (similar to FullKeymapProcessor)
            try:
                from .dt_parser import parse_dt_lark_safe

                roots, parse_errors = parse_dt_lark_safe(context.keymap_content)
                if parse_errors:
                    context.warnings.extend([str(error) for error in parse_errors])

                if roots:
                    # Extract global comments metadata
                    _, metadata_dict = (
                        self.section_extractor.behavior_extractor.extract_behaviors_with_metadata(
                            roots, context.keymap_content
                        )
                    )

                    # Global comments are now handled directly by the AST converter
                    self.logger.debug("Global comments handled by AST converter")
            except Exception as e:
                exc_info = self.logger.isEnabledFor(logging.DEBUG)
                self.logger.warning(
                    "Failed to extract global comments for template mode: %s",
                    e,
                    exc_info=exc_info,
                )

            # Extract sections using hybrid approach
            extracted_sections = self.section_extractor.extract_sections(
                context.keymap_content, extraction_config
            )

            # Process extracted sections
            processed_data = self.section_extractor.process_extracted_sections(
                extracted_sections, context
            )

            # Populate layout data with processed sections
            self._populate_layout_from_processed_data(layout_data, processed_data)

            return layout_data

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Template-aware parsing failed: %s", e, exc_info=exc_info)
            context.errors.append(f"Template-aware parsing failed: {e}")
            return None

    def _get_keyboard_profile(
        self, profile_name: str | None
    ) -> "KeyboardProfile | None":
        """Get keyboard profile instance.

        Args:
            profile_name: Name of the profile to load

        Returns:
            KeyboardProfile instance or None if not found
        """
        if not profile_name:
            return None

        try:
            from glovebox.config import create_keyboard_profile

            return create_keyboard_profile(profile_name)
        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to load profile %s: %s", profile_name, e, exc_info=exc_info
            )
            return None

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
                template_file = profile.keymap.keymap_dtsi_file
                if template_file:
                    # Resolve relative to profile config directory
                    config_dir = Path(profile.config_path).parent
                    return Path(config_dir / template_file)

            # Fallback to default template location
            project_root = Path(__file__).parent.parent.parent.parent
            return Path(
                project_root / "keyboards" / "config" / "templates" / "keymap.dtsi.j2"
            )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.warning(
                "Could not determine template path: %s", e, exc_info=exc_info
            )
            return None

    def _populate_layout_from_processed_data(
        self, layout_data: LayoutData, processed_data: dict[str, object]
    ) -> None:
        """Populate layout data from processed section data.

        Args:
            layout_data: Layout data to populate
            processed_data: Processed data from sections
        """
        # Populate layers
        if "layers" in processed_data:
            layers = processed_data["layers"]
            layout_data.layer_names = layers["layer_names"]
            layout_data.layers = layers["layers"]

        # Populate behaviors
        if "behaviors" in processed_data:
            behaviors = processed_data["behaviors"]
            layout_data.hold_taps = behaviors.get("hold_taps", [])

        # Populate macros and combos
        if "macros" in processed_data:
            layout_data.macros = processed_data["macros"]

        if "combos" in processed_data:
            layout_data.combos = processed_data["combos"]

        # Handle custom devicetree content
        if "custom_devicetree" in processed_data:
            layout_data.custom_devicetree = processed_data["custom_devicetree"]

        if "custom_defined_behaviors" in processed_data:
            layout_data.custom_defined_behaviors = processed_data[
                "custom_defined_behaviors"
            ]

        # Handle input listeners - convert to JSON models instead of storing as raw DTSI
        if "input_listeners" in processed_data:
            input_listeners_data = processed_data["input_listeners"]
            self.logger.debug(
                "Processing input listeners data: type=%s, content preview=%s",
                type(input_listeners_data).__name__,
                str(input_listeners_data)[:100] if input_listeners_data else "None",
            )
            if isinstance(input_listeners_data, str):
                # This is raw DTSI content, need to parse and convert to models
                self._convert_input_listeners_from_dtsi(
                    layout_data, input_listeners_data
                )
            elif isinstance(input_listeners_data, list):
                # Already converted to models
                if layout_data.input_listeners is None:
                    layout_data.input_listeners = []
                layout_data.input_listeners.extend(input_listeners_data)
            else:
                self.logger.warning(
                    "Unexpected input listeners data type: %s",
                    type(input_listeners_data).__name__,
                )

            # Also store raw DTSI for template variables
            if not hasattr(layout_data, "variables") or layout_data.variables is None:
                layout_data.variables = {}
            if isinstance(input_listeners_data, str):
                layout_data.variables["input_listeners_dtsi"] = input_listeners_data

        # Store raw content for template variables
        self._store_raw_content_for_templates(layout_data, processed_data)

    def _convert_input_listeners_from_dtsi(
        self, layout_data: LayoutData, input_listeners_dtsi: str
    ) -> None:
        """Convert raw input listeners DTSI content to JSON models.

        Args:
            layout_data: Layout data to populate with converted input listeners
            input_listeners_dtsi: Raw DTSI content containing input listener definitions
        """
        try:
            # Parse the DTSI content into AST nodes
            from .dt_parser import parse_dt_lark_safe

            # The section extractor provides behavior references (starting with &) rather than definitions
            # Convert references to definitions for proper AST parsing
            dtsi_content = input_listeners_dtsi.strip()

            # First attempt: try parsing as-is (for complete device tree structures)
            roots, parse_errors = parse_dt_lark_safe(dtsi_content)

            # If parsing failed and content doesn't start with '/', try transforming and wrapping it
            if (not roots or parse_errors) and not dtsi_content.startswith('/'):
                self.logger.debug(
                    "Initial parse failed, attempting to transform behavior references to definitions"
                )

                # Transform behavior references (&name) to proper definitions (name)
                # Also add compatible strings for input listeners
                transformed_content = self._transform_behavior_references_to_definitions(dtsi_content)

                # Wrap transformed behavior definitions in device tree structure
                wrapped_content = f"/ {{\n{transformed_content}\n}};"
                roots, parse_errors = parse_dt_lark_safe(wrapped_content)

                if parse_errors:
                    self.logger.warning(
                        "Parse errors while converting wrapped input listeners: %s",
                        parse_errors
                    )

            if not roots:
                self.logger.warning(
                    "No AST roots found in input listeners DTSI content after wrapping attempt"
                )
                return

            # Use the behavior extractor to convert input listener nodes
            behavior_models, _ = (
                self.section_extractor.behavior_extractor.extract_behaviors_as_models(
                    roots, dtsi_content
                )
            )

            # Extract input listeners from behavior models
            if behavior_models.get("input_listeners"):
                if layout_data.input_listeners is None:
                    layout_data.input_listeners = []
                layout_data.input_listeners.extend(behavior_models["input_listeners"])
                self.logger.debug(
                    "Converted %d input listeners from DTSI to JSON models",
                    len(layout_data.input_listeners),
                )
                # Debug the structure of converted input listeners
                if layout_data.input_listeners:
                    for i, listener in enumerate(layout_data.input_listeners):
                        self.logger.debug(
                            "Input listener %d: code=%s, nodes=%d, inputProcessors=%d",
                            i,
                            listener.code,
                            len(listener.nodes) if listener.nodes else 0,
                            len(listener.input_processors) if listener.input_processors else 0,
                        )
            else:
                self.logger.debug("No input listeners found in DTSI content")

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to convert input listeners from DTSI: %s", e, exc_info=exc_info
            )

    def _transform_behavior_references_to_definitions(self, dtsi_content: str) -> str:
        """Transform behavior references (&name) to proper node definitions (name).

        Args:
            dtsi_content: Raw DTSI content with behavior references

        Returns:
            Transformed content with proper node definitions
        """
        import re

        # Transform &mmv_input_listener and &msc_input_listener references to definitions
        # Pattern: &(listener_name) { ... };
        # Replace with: listener_name { compatible = "zmk,input-listener"; ... };

        def transform_listener_reference(match):
            listener_name = match.group(1)
            body = match.group(2)

            # Add compatible property for input listeners
            compatible_line = '    compatible = "zmk,input-listener";\n'

            # Insert compatible property at the beginning of the body
            lines = body.split('\n')
            if len(lines) > 1:
                # Insert after the opening brace
                transformed_body = lines[0] + '\n' + compatible_line + '\n'.join(lines[1:])
            else:
                transformed_body = compatible_line + body

            return f"{listener_name} {{{transformed_body}}};"

        # Pattern to match behavior references: &name { ... };
        pattern = r'&((?:mmv_input_listener|msc_input_listener))\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\};'

        transformed = re.sub(pattern, transform_listener_reference, dtsi_content, flags=re.DOTALL)

        import re as regex_module
        self.logger.debug("Transformed behavior references for %d listeners",
                         len(regex_module.findall(r'&(?:mmv_input_listener|msc_input_listener)', dtsi_content)))

        return transformed

    def _store_raw_content_for_templates(
        self, layout_data: LayoutData, processed_data: dict[str, object]
    ) -> None:
        """Store raw section content for template rendering.

        Args:
            layout_data: Layout data to populate
            processed_data: Processed data containing raw content
        """
        if not hasattr(layout_data, "variables") or layout_data.variables is None:
            layout_data.variables = {}

        # Map raw content to template variable names
        raw_mappings = {
            "behaviors_raw": "user_behaviors_dtsi",
            "macros_raw": "user_macros_dtsi",
            "combos_raw": "combos_dtsi",
        }

        for data_key, template_var in raw_mappings.items():
            if data_key in processed_data:
                layout_data.variables[template_var] = processed_data[data_key]


def create_full_keymap_processor(
    section_extractor: "SectionExtractorProtocol | None" = None,
    template_adapter: "TemplateAdapterProtocol | None" = None,
) -> FullKeymapProcessor:
    """Create full keymap processor with AST converter for comment support.

    Args:
        section_extractor: Optional section extractor (creates default with comment support if None)
        template_adapter: Optional template adapter

    Returns:
        Configured FullKeymapProcessor instance with comment support
    """
    if section_extractor is None:
        from .section_extractor import create_section_extractor

        section_extractor = create_section_extractor()

    return FullKeymapProcessor(
        section_extractor=section_extractor,
        template_adapter=template_adapter,
    )


def create_template_aware_processor(
    section_extractor: "SectionExtractorProtocol | None" = None,
    template_adapter: "TemplateAdapterProtocol | None" = None,
) -> TemplateAwareProcessor:
    """Create template-aware processor with AST converter for comment support.

    Args:
        section_extractor: Optional section extractor (creates default with comment support if None)
        template_adapter: Optional template adapter

    Returns:
        Configured TemplateAwareProcessor instance with comment support
    """
    if section_extractor is None:
        from .section_extractor import create_section_extractor

        section_extractor = create_section_extractor()

    return TemplateAwareProcessor(
        section_extractor=section_extractor,
        template_adapter=template_adapter,
    )
