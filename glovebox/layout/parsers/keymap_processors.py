"""Keymap processing strategies for different parsing modes."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from glovebox.layout.models import LayoutData
from glovebox.layout.parsers.ast_nodes import DTNode

from .dt_parser import parse_dt_lark_safe
from .parsing_models import ParsingContext, get_default_extraction_config
from .section_extractor import create_section_extractor


if TYPE_CHECKING:
    from .section_extractor import BehaviorExtractorProtocol

    class SectionExtractorProtocol(Protocol):
        def extract_sections(
            self, content: str, configs: list[Any]
        ) -> dict[str, Any]: ...
        def process_extracted_sections(
            self, sections: dict[str, Any], context: Any
        ) -> dict[str, Any]: ...
        @property
        def behavior_extractor(self) -> "BehaviorExtractorProtocol": ...


class BaseKeymapProcessor:
    """Base class for keymap processors with common functionality."""

    def __init__(
        self,
        section_extractor: "SectionExtractorProtocol | None" = None,
    ) -> None:
        """Initialize base processor."""
        self.logger = logging.getLogger(__name__)
        self.section_extractor = section_extractor or create_section_extractor()

    def process(self, context: ParsingContext) -> LayoutData | None:
        """Process keymap content according to parsing strategy."""
        raise NotImplementedError("Subclasses must implement process method")

    def _create_base_layout_data(self, context: ParsingContext) -> LayoutData:
        """Create base layout data with default values."""
        keyboard_name = context.keyboard_name
        # Handle cases where keyboard_name includes path like "glove80/main"
        if "/" in keyboard_name:
            keyboard_name = keyboard_name.split("/")[0]
        return LayoutData(keyboard=keyboard_name, title=context.title)

    def _transform_behavior_references_to_definitions(self, dtsi_content: str) -> str:
        """Transform behavior references (&name) to proper node definitions (name).

        Handles any behavior reference pattern, not just input listeners.

        Args:
            dtsi_content: Raw DTSI content with behavior references

        Returns:
            Transformed content with proper node definitions
        """
        import re

        # Transform behavior references (&name) to proper node definitions (name)
        # This handles any behavior reference, not just input listeners

        def transform_behavior_reference(match: Any) -> str:
            behavior_name = match.group(1)
            body = match.group(2)

            # Determine compatible string based on behavior name pattern
            if behavior_name.endswith("_input_listener"):
                compatible_line = '    compatible = "zmk,input-listener";\n'
            else:
                # For other behavior references, we'll let the AST converter determine the type
                compatible_line = '    compatible = "zmk,behavior";\n'

            # Insert compatible property at the beginning of the body
            lines = body.split("\n")
            if len(lines) > 1:
                # Insert after the opening brace
                transformed_body = (
                    lines[0] + "\n" + compatible_line + "\n".join(lines[1:])
                )
            else:
                transformed_body = compatible_line + body

            return f"{behavior_name} {{{transformed_body}}};"

        # Generic pattern to match any behavior references: &name { ... };
        pattern = r"&(\w+)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\};"

        transformed = re.sub(
            pattern, transform_behavior_reference, dtsi_content, flags=re.DOTALL
        )

        # Count transformations
        import re as regex_module

        self.logger.debug(
            "Transformed %d behavior references to definitions",
            len(regex_module.findall(r"&\w+", dtsi_content)),
        )

        return transformed

    def _extract_layers_from_roots(self, roots: list[DTNode]) -> dict[str, Any] | None:
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
        self, roots: list[DTNode], content: str
    ) -> dict[str, Any]:
        """Extract behaviors from AST roots.

        Args:
            roots: List of parsed device tree root nodes
            content: Original keymap content

        Returns:
            Dictionary of behavior models
        """
        # Extract behaviors using AST converter with comment support
        behavior_models = (
            self.section_extractor.behavior_extractor.extract_behaviors_as_models(
                roots, content
            )
        )
        return behavior_models

    def _populate_behaviors_in_layout(
        self, layout_data: LayoutData, converted_behaviors: dict[str, Any]
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
            # Transform behavior references (&name) to proper definitions before parsing
            # This handles input listeners and other behavior references in full mode
            transformed_content = self._transform_behavior_references_to_definitions(
                context.keymap_content
            )

            # Parse content into AST using enhanced parser for comment support
            try:
                from .dt_parser import parse_dt_multiple_safe

                roots, parse_errors = parse_dt_multiple_safe(transformed_content)
                # Convert DTParseError objects to strings
                if parse_errors:
                    context.warnings.extend([str(error) for error in parse_errors])
            except ImportError:
                # Fallback to Lark parser if enhanced parser not available
                roots, parse_error_strings = parse_dt_lark_safe(transformed_content)
                # These are already strings
                if parse_error_strings:
                    context.warnings.extend(parse_error_strings)

            if not roots:
                context.errors.append("Failed to parse device tree AST")
                return None

            # Create base layout data with enhanced metadata
            layout_data = self._create_base_layout_data(context)

            # Extract layers using AST from all roots
            layers_data = self._extract_layers_from_roots(roots)
            if layers_data:
                layout_data.layer_names = layers_data["layer_names"]
                layout_data.layers = layers_data["layers"]

            # Extract behaviors (use transformed content for metadata extraction too)
            behaviors_dict = self._extract_behaviors_and_metadata(
                roots, transformed_content
            )

            # Populate behaviors directly (already converted by AST converter)
            self._populate_behaviors_in_layout(layout_data, behaviors_dict)

            layout_data.custom_defined_behaviors = ""
            layout_data.custom_devicetree = ""

            return layout_data

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Full keymap parsing failed: %s", e, exc_info=exc_info)
            context.errors.append(f"Full parsing failed: {e}")
            return None


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
            layout_data = self._create_base_layout_data(context)

            # Use configured extraction or default
            extraction_config = (
                context.extraction_config or get_default_extraction_config()
            )

            # Extract sections using template-aware approach (only user content)
            extracted_sections = self.section_extractor.extract_sections(
                context.keymap_content, extraction_config
            )

            # Apply transformation to extracted sections BEFORE processing
            transformed_sections = {}
            for section_name, section in extracted_sections.items():
                if section.type in ("input_listener", "behavior", "macro", "combo"):
                    # Apply transformation to section content before processing
                    # Ensure content is a string before transformation
                    if isinstance(section.content, str):
                        transformed_content: str | dict[str, object] | list[object] = (
                            self._transform_behavior_references_to_definitions(
                                section.content
                            )
                        )
                    else:
                        # Skip transformation for non-string content
                        transformed_content = section.content
                    # Create new section with transformed content
                    from .parsing_models import ExtractedSection

                    transformed_sections[section_name] = ExtractedSection(
                        name=section.name,
                        content=transformed_content,
                        raw_content=section.raw_content,
                        type=section.type,
                    )
                else:
                    # Keep other sections as-is
                    transformed_sections[section_name] = section

            # Process extracted sections with transformations applied
            processed_data = self.section_extractor.process_extracted_sections(
                transformed_sections, context
            )

            # Populate layout data with processed sections
            self._populate_layout_from_processed_data(layout_data, processed_data)

            return layout_data

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Template-aware parsing failed: %s", e, exc_info=exc_info)
            context.errors.append(f"Template-aware parsing failed: {e}")
            return None

    def _populate_layout_from_processed_data(
        self, layout_data: LayoutData, processed_data: dict[str, Any]
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
            custom_behaviors = processed_data["custom_defined_behaviors"]
            # Convert empty device tree structure to empty string
            if custom_behaviors and custom_behaviors.strip() in (
                "/ {\n};",
                "/ { };",
                "/{\n};",
                "/{};",
            ):
                layout_data.custom_defined_behaviors = ""
            else:
                layout_data.custom_defined_behaviors = custom_behaviors

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
            if (not roots or parse_errors) and not dtsi_content.startswith("/"):
                self.logger.debug(
                    "Initial parse failed, attempting to transform behavior references to definitions"
                )

                # Transform behavior references (&name) to proper definitions (name)
                # Also add compatible strings for input listeners
                transformed_content = (
                    self._transform_behavior_references_to_definitions(dtsi_content)
                )

                # Wrap transformed behavior definitions in device tree structure
                wrapped_content = f"/ {{\n{transformed_content}\n}};"
                roots, parse_errors = parse_dt_lark_safe(wrapped_content)

                if parse_errors:
                    self.logger.warning(
                        "Parse errors while converting wrapped input listeners: %s",
                        parse_errors,
                    )

            if not roots:
                self.logger.warning(
                    "No AST roots found in input listeners DTSI content after wrapping attempt"
                )
                return

            # Use the behavior extractor to convert input listener nodes
            behavior_models = (
                self.section_extractor.behavior_extractor.extract_behaviors_as_models(
                    roots, dtsi_content
                )
            )

            # Extract input listeners from behavior models
            if behavior_models.get("input_listeners"):
                if layout_data.input_listeners is None:
                    layout_data.input_listeners = []
                input_listeners = behavior_models["input_listeners"]
                if isinstance(input_listeners, list):
                    layout_data.input_listeners.extend(input_listeners)
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
                            len(listener.input_processors)
                            if listener.input_processors
                            else 0,
                        )
            else:
                self.logger.debug("No input listeners found in DTSI content")

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to convert input listeners from DTSI: %s", e, exc_info=exc_info
            )

    def _store_raw_content_for_templates(
        self, layout_data: LayoutData, processed_data: dict[str, Any]
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
) -> FullKeymapProcessor:
    """Create full keymap processor with AST.

    Args:
        section_extractor: Optional section extractor
        template_adapter: Optional template adapter

    Returns:
        Configured FullKeymapProcessor instance
    """
    if section_extractor is None:
        from typing import cast

        from .section_extractor import create_section_extractor

        section_extractor = cast("SectionExtractorProtocol", create_section_extractor())

    return FullKeymapProcessor()


def create_template_aware_processor(
    section_extractor: "SectionExtractorProtocol | None" = None,
) -> TemplateAwareProcessor:
    """Create template-aware processor with AST converter for each section

    Args:
        section_extractor: Optional section extractor

    Returns:
        Configured TemplateAwareProcessor instance
    """
    if section_extractor is None:
        from typing import cast

        from .section_extractor import create_section_extractor

        section_extractor = cast("SectionExtractorProtocol", create_section_extractor())

    return TemplateAwareProcessor(
        section_extractor=section_extractor,
    )
