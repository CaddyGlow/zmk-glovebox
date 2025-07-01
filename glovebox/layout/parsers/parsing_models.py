"""Data models for keymap parsing operations."""

from typing import TYPE_CHECKING, Literal, Optional

from glovebox.models.base import GloveboxBaseModel


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile


class ExtractionConfig(GloveboxBaseModel):
    """Configuration for extracting a section from keymap content."""

    tpl_ctx_name: str
    type: Literal["dtsi", "behavior", "macro", "combo", "keymap", "input_listener"]
    layer_data_name: str
    delimiter: list[str]


class ExtractedSection(GloveboxBaseModel):
    """Result of extracting a section from keymap content."""

    name: str
    content: str | dict[str, object] | list[object]
    raw_content: str
    type: str


class KeymapExtractionProfile(GloveboxBaseModel):
    """Profile-specific extraction configuration for keyboards."""

    sections: list[ExtractionConfig]
    version: str = "1.0"


class ParsingContext(GloveboxBaseModel):
    """Context information for keymap parsing operations."""

    keymap_content: str
    title: str = "Glovebox Generated Keymap"
    keyboard_name: str = "unknown"
    extraction_config: list[ExtractionConfig] = []
    errors: list[str] = []
    warnings: list[str] = []


class SectionProcessingResult(GloveboxBaseModel):
    """Result of processing an extracted section."""

    success: bool
    data: object | None = None
    raw_content: str = ""
    error_message: str = ""
    warnings: list[str] = []


def get_default_extraction_config() -> list[ExtractionConfig]:
    """Get default extraction configuration for backward compatibility."""
    return [
        ExtractionConfig(
            tpl_ctx_name="custom_devicetree",
            type="dtsi",
            layer_data_name="custom_devicetree",
            delimiter=[
                r"/\*\s*Custom\s+Device-tree\s*\*/",
                r"/\*\s*Input\s+Listeners\s*\*/",
            ],
        ),
        ExtractionConfig(
            tpl_ctx_name="input_listeners_dtsi",
            type="input_listener",
            layer_data_name="input_listeners",
            delimiter=[
                r"/\*\s*Input\s+Listeners\s*\*/",
                r"/\*\s*System\s+behavior\s+and\s+Macros\s*\*/",
            ],
        ),
        ExtractionConfig(
            tpl_ctx_name="system_behaviors_dts",
            type="dtsi",
            layer_data_name="system_behaviors_raw",
            delimiter=[
                r"/\*\s*System\s+behavior\s+and\s+Macros\s*\*/",
                r"/\*\s*(?:#define\s+for\s+key\s+positions|Custom\s+Defined\s+Behaviors|Automatically\s+generated\s+macro|$)",
            ],
        ),
        ExtractionConfig(
            tpl_ctx_name="custom_defined_behaviors",
            type="dtsi",
            layer_data_name="custom_defined_behaviors",
            delimiter=[
                r"/\*\s*Custom\s+Defined\s+Behaviors\s*\*/",
                r"/\*\s*(?:Automatically\s+generated\s+macro|Automatically\s+generated\s+behavior|Automatically\s+generated\s+combos|Automatically\s+generated\s+keymap|$)",
            ],
        ),
        ExtractionConfig(
            tpl_ctx_name="user_macros_dtsi",
            type="macro",
            layer_data_name="macros",
            delimiter=[
                r"/\*\s*Automatically\s+generated\s+macro\s+definitions\s*\*/",
                r"/\*\s*(?:Automatically\s+generated\s+behavior|Automatically\s+generated\s+combos|Automatically\s+generated\s+keymap|$)",
            ],
        ),
        ExtractionConfig(
            tpl_ctx_name="user_behaviors_dtsi",
            type="behavior",
            layer_data_name="behaviors",
            delimiter=[
                r"/\*\s*Automatically\s+generated\s+behavior\s+definitions\s*\*/",
                r"/\*\s*(?:Automatically\s+generated\s+combos|Automatically\s+generated\s+keymap|$)",
            ],
        ),
        ExtractionConfig(
            tpl_ctx_name="combos_dtsi",
            type="combo",
            layer_data_name="combos",
            delimiter=[
                r"/\*\s*Automatically\s+generated\s+combos\s+definitions\s*\*/",
                r"/\*\s*(?:Automatically\s+generated\s+keymap|$)",
            ],
        ),
        ExtractionConfig(
            tpl_ctx_name="keymap_node",
            type="keymap",
            layer_data_name="layers",
            delimiter=[
                r"/\*\s*Automatically\s+generated\s+keymap\s*\*/",
                r"\Z",  # End of string
            ],
        ),
    ]
