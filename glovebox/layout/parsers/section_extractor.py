"""Section extraction utilities for keymap parsing."""

import logging
import re
from typing import TYPE_CHECKING, Protocol


if TYPE_CHECKING:

    class BehaviorParserProtocol(Protocol):
        pass

    class BehaviorExtractorProtocol(Protocol):
        def extract_behaviors_with_metadata(
            self, roots: list, content: str
        ) -> tuple[dict, dict]: ...

    class ModelConverterProtocol(Protocol):
        def convert_behaviors(self, behaviors_dict: dict) -> dict: ...


from .ast_walker import create_universal_behavior_extractor
from .behavior_parser import create_behavior_parser
from .dt_parser import parse_dt_safe
from .model_converters import create_universal_model_converter
from .parsing_models import (
    ExtractedSection,
    ExtractionConfig,
    ParsingContext,
    SectionProcessingResult,
)


class SectionExtractor:
    """Extracts and processes sections from keymap content using configurable delimiters."""

    def __init__(
        self,
        behavior_parser: "BehaviorParserProtocol | None" = None,
        behavior_extractor: "BehaviorExtractorProtocol | None" = None,
        model_converter: "ModelConverterProtocol | None" = None,
    ) -> None:
        """Initialize section extractor with dependencies."""
        self.logger = logging.getLogger(__name__)
        self.behavior_parser = behavior_parser or create_behavior_parser()
        self.behavior_extractor = (
            behavior_extractor or create_universal_behavior_extractor()
        )
        self.model_converter = model_converter or create_universal_model_converter()

    def extract_sections(
        self, content: str, configs: list[ExtractionConfig]
    ) -> dict[str, ExtractedSection]:
        """Extract all configured sections from keymap content."""
        sections = {}

        self.logger.debug("Extracting sections with %d configurations", len(configs))

        for config in configs:
            try:
                section = self._extract_single_section(content, config)
                if section:
                    sections[config.tpl_ctx_name] = section
                    self.logger.debug(
                        "Extracted section %s: %d chars",
                        config.tpl_ctx_name,
                        len(section.raw_content),
                    )
            except Exception as e:
                exc_info = self.logger.isEnabledFor(logging.DEBUG)
                self.logger.warning(
                    "Failed to extract section %s: %s",
                    config.tpl_ctx_name,
                    e,
                    exc_info=exc_info,
                )

        return sections

    def process_extracted_sections(
        self, sections: dict[str, ExtractedSection], context: ParsingContext
    ) -> dict[str, object]:
        """Process extracted sections based on their types.

        Args:
            sections: Extracted sections to process
            context: Parsing context with additional information

        Returns:
            Dictionary with processed section data
        """
        processed = {}

        for section_name, section in sections.items():
            try:
                result = self._process_section_by_type(section)

                if result.success and result.data is not None:
                    processed[section.name] = result.data

                    # Store raw content for template variables if needed
                    if section.type in ("behavior", "macro", "combo"):
                        raw_key = (
                            f"{section_name}_raw"
                            if not section_name.endswith("_raw")
                            else section_name
                        )
                        processed[raw_key] = section.raw_content

                context.warnings.extend(result.warnings)

                if not result.success and result.error_message:
                    context.errors.append(
                        f"Processing {section_name}: {result.error_message}"
                    )

            except Exception as e:
                exc_info = self.logger.isEnabledFor(logging.DEBUG)
                self.logger.error(
                    "Failed to process section %s: %s",
                    section_name,
                    e,
                    exc_info=exc_info,
                )
                context.errors.append(f"Processing {section_name}: {e}")

        return processed

    def _extract_single_section(
        self, content: str, config: ExtractionConfig
    ) -> ExtractedSection | None:
        """Extract a single section using comment delimiters.

        Args:
            content: Full keymap content
            config: Section extraction configuration

        Returns:
            Extracted section or None if not found
        """
        try:
            # Find start delimiter
            start_pattern = config.delimiter[0]
            start_match = re.search(
                start_pattern, content, re.IGNORECASE | re.MULTILINE
            )

            if not start_match:
                self.logger.debug(
                    "No start delimiter found for %s", config.tpl_ctx_name
                )
                return None

            # Find end delimiter
            search_start = start_match.end()
            end_pattern = config.delimiter[1] if len(config.delimiter) > 1 else r"\Z"
            end_match = re.search(
                end_pattern, content[search_start:], re.IGNORECASE | re.MULTILINE
            )

            if end_match:
                content_end = search_start + end_match.start()
            else:
                content_end = len(content)

            # Extract and clean content
            raw_content = content[search_start:content_end].strip()
            cleaned_content = self._clean_section_content(raw_content)

            if not cleaned_content:
                return None

            return ExtractedSection(
                name=config.layer_data_name,
                content=cleaned_content,
                raw_content=raw_content,
                type=config.type,
            )

        except re.error as e:
            self.logger.warning("Regex error extracting %s: %s", config.tpl_ctx_name, e)
            return None

    def _clean_section_content(self, content: str) -> str:
        """Clean extracted section content by removing empty lines and pure comments.

        Args:
            content: Raw extracted content

        Returns:
            Cleaned content or empty string if nothing meaningful found
        """
        lines = []

        for line in content.split("\n"):
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                continue

            # Skip pure comment lines
            if stripped.startswith("//") or (
                stripped.startswith("/*") and stripped.endswith("*/")
            ):
                continue

            # Skip template comment lines
            if "{#" in stripped and "#}" in stripped:
                continue

            lines.append(line)

        return "\n".join(lines) if lines else ""

    def _process_section_by_type(
        self, section: ExtractedSection
    ) -> SectionProcessingResult:
        """Process a section based on its type.

        Args:
            section: Section to process

        Returns:
            Processing result with data or error information
        """
        try:
            if section.type == "dtsi":
                return SectionProcessingResult(
                    success=True,
                    data=section.content,
                    raw_content=section.raw_content,
                )

            elif section.type in ("behavior", "macro", "combo"):
                return self._process_ast_section(section)

            elif section.type == "keymap":
                return self._process_keymap_section(section)

            elif section.type == "input_listener":
                return SectionProcessingResult(
                    success=True,
                    data=section.content,
                    raw_content=section.raw_content,
                )

            else:
                return SectionProcessingResult(
                    success=False,
                    error_message=f"Unknown section type: {section.type}",
                    raw_content=section.raw_content,
                )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to process %s section: %s", section.type, e, exc_info=exc_info
            )
            return SectionProcessingResult(
                success=False,
                error_message=str(e),
                raw_content=section.raw_content,
            )

    def _process_ast_section(
        self, section: ExtractedSection
    ) -> SectionProcessingResult:
        """Process a section using AST parsing for behaviors, macros, or combos.

        Args:
            section: Section to parse with AST

        Returns:
            Processing result with parsed data
        """
        try:
            # Use raw content for AST parsing to preserve comments
            # Fall back to cleaned content if raw content is not available
            content_to_parse = (
                section.raw_content if section.raw_content else section.content
            )

            # Parse section content as AST
            root, parse_errors = parse_dt_safe(content_to_parse)

            if not root:
                return SectionProcessingResult(
                    success=False,
                    error_message="Failed to parse as device tree AST",
                    raw_content=section.raw_content,
                    warnings=[str(e) for e in parse_errors] if parse_errors else [],
                )

            # Extract behaviors using enhanced infrastructure with comment support
            if hasattr(self.behavior_extractor, "extract_behaviors_as_models"):
                # Use new AST converter method for comment-aware behavior extraction
                behavior_models, _ = (
                    self.behavior_extractor.extract_behaviors_as_models(
                        [root], content_to_parse
                    )
                )
                # Behavior models are already converted, no need for model converter
                converted_behaviors = behavior_models
            else:
                # Fallback to legacy method for compatibility
                behaviors_dict, _ = (
                    self.behavior_extractor.extract_behaviors_with_metadata(
                        [root], content_to_parse
                    )
                )
                converted_behaviors = self.model_converter.convert_behaviors(
                    behaviors_dict
                )

            # Return appropriate data based on section type
            if section.type == "behavior":
                data = converted_behaviors if converted_behaviors else {}
            elif section.type == "macro":
                data = converted_behaviors.get("macros", [])
            elif section.type == "combo":
                data = converted_behaviors.get("combos", [])
            else:
                data = converted_behaviors

            return SectionProcessingResult(
                success=True,
                data=data,
                raw_content=section.raw_content,
                warnings=[str(e) for e in parse_errors] if parse_errors else [],
            )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "AST processing failed for %s: %s", section.type, e, exc_info=exc_info
            )
            return SectionProcessingResult(
                success=False,
                error_message=f"AST processing failed: {e}",
                raw_content=section.raw_content,
            )

    def _process_keymap_section(
        self, section: ExtractedSection
    ) -> SectionProcessingResult:
        """Process a keymap section to extract layer information.

        Args:
            section: Keymap section to process

        Returns:
            Processing result with layer data
        """
        try:
            # Import here to avoid circular imports
            from .keymap_parser import ZmkKeymapParser

            # Create a temporary parser instance for layer extraction
            temp_parser = ZmkKeymapParser()

            # Parse section content as AST
            root, parse_errors = parse_dt_safe(section.content)

            if not root:
                return SectionProcessingResult(
                    success=False,
                    error_message="Failed to parse keymap section as AST",
                    raw_content=section.raw_content,
                    warnings=[str(e) for e in parse_errors] if parse_errors else [],
                )

            # Extract layers using existing method
            layers_data = temp_parser._extract_layers_from_ast(root)

            if not layers_data:
                return SectionProcessingResult(
                    success=False,
                    error_message="No layer data found in keymap section",
                    raw_content=section.raw_content,
                    warnings=[str(e) for e in parse_errors] if parse_errors else [],
                )

            return SectionProcessingResult(
                success=True,
                data=layers_data,
                raw_content=section.raw_content,
                warnings=[str(e) for e in parse_errors] if parse_errors else [],
            )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Keymap section processing failed: %s", e, exc_info=exc_info
            )
            return SectionProcessingResult(
                success=False,
                error_message=f"Keymap processing failed: {e}",
                raw_content=section.raw_content,
            )


def create_section_extractor(
    behavior_parser: "BehaviorParserProtocol | None" = None,
    behavior_extractor: "BehaviorExtractorProtocol | None" = None,
    model_converter: "ModelConverterProtocol | None" = None,
) -> SectionExtractor:
    """Create a section extractor with dependency injection.

    Args:
        behavior_parser: Optional behavior parser (uses factory if None)
        behavior_extractor: Optional behavior extractor (uses factory if None)
        model_converter: Optional model converter (uses factory if None)

    Returns:
        Configured SectionExtractor instance
    """
    return SectionExtractor(
        behavior_parser=behavior_parser,
        behavior_extractor=behavior_extractor,
        model_converter=model_converter,
    )


def create_section_extractor_with_ast_converter(
    behavior_parser: "BehaviorParserProtocol | None" = None,
    model_converter: "ModelConverterProtocol | None" = None,
) -> SectionExtractor:
    """Create a section extractor with AST converter for comment support.

    Args:
        behavior_parser: Optional behavior parser (uses factory if None)
        model_converter: Optional model converter (uses factory if None)

    Returns:
        Configured SectionExtractor instance with AST converter support
    """
    from .ast_walker import create_universal_behavior_extractor_with_converter

    return SectionExtractor(
        behavior_parser=behavior_parser,
        behavior_extractor=create_universal_behavior_extractor_with_converter(),
        model_converter=model_converter,
    )
