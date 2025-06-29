"""ZMK keymap parser for reverse engineering keymaps to JSON layouts."""

import logging
import re
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from glovebox.adapters import create_template_adapter
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
    from glovebox.protocols import TemplateAdapterProtocol

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
        template_adapter: "TemplateAdapterProtocol | None" = None,
        processors: dict[ParsingMode, "ProcessorProtocol"] | None = None,
    ) -> None:
        """Initialize the keymap parser with explicit dependencies.

        Args:
            template_adapter: Template adapter for processing template files
            processors: Dictionary of parsing mode to processor instances
        """
        self.logger = logging.getLogger(__name__)
        self.template_adapter = template_adapter or create_template_adapter()
        self.model_factory = ModelFactory()

        # Initialize processors for different parsing modes
        self.processors = processors or {
            ParsingMode.FULL: create_full_keymap_processor(
                template_adapter=self.template_adapter
            ),
            ParsingMode.TEMPLATE_AWARE: create_template_aware_processor(
                template_adapter=self.template_adapter
            ),
        }

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

            # Validate required parameters
            if mode == ParsingMode.TEMPLATE_AWARE and not keyboard_profile:
                result.errors.append(
                    "Keyboard profile is required for template-aware parsing"
                )
                return result

            # Get extraction configuration
            extraction_config = self._get_extraction_config(keyboard_profile)

            # Create parsing context
            context = ParsingContext(
                keymap_content=keymap_content,
                keyboard_profile_name=keyboard_profile,
                extraction_config=extraction_config,
            )

            # Use appropriate processor
            processor = self.processors[mode]
            layout_data = processor.process(context)

            if layout_data:
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
        self, keyboard_profile: str | None
    ) -> list["ExtractionConfig"]:
        """Get extraction configuration from profile or use default.

        Args:
            keyboard_profile: Keyboard profile name

        Returns:
            List of extraction configurations
        """
        if keyboard_profile:
            try:
                from glovebox.config import create_keyboard_profile

                profile = create_keyboard_profile(keyboard_profile)

                # Check if profile has custom extraction config
                if hasattr(profile, "keymap_extraction") and profile.keymap_extraction:
                    return profile.keymap_extraction.sections
            except Exception as e:
                exc_info = self.logger.isEnabledFor(logging.DEBUG)
                self.logger.warning(
                    "Failed to load extraction config from profile %s: %s",
                    keyboard_profile,
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

    def _extract_layers_from_ast(self, root: DTNode) -> dict[str, object] | None:
        """Extract layer definitions from AST."""
        try:
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


def create_zmk_keymap_parser(
    template_adapter: "TemplateAdapterProtocol | None" = None,
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
        template_adapter=template_adapter,
        processors=processors,
    )


def create_zmk_keymap_parser_from_profile(
    profile: "KeyboardProfile",
    template_adapter: "TemplateAdapterProtocol | None" = None,
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
    parser = create_zmk_keymap_parser(
        template_adapter=template_adapter,
    )

    # Configure parser based on profile settings
    # This could include profile-specific parsing preferences, template paths, etc.
    # For now, we return the standard parser, but this provides the extension point
    # for profile-based configuration

    return parser
