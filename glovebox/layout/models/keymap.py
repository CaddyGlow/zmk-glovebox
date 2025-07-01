"""Keymap parsing models for ZMK keymap preservation."""

from datetime import datetime

from pydantic import Field, field_serializer

from glovebox.models.base import GloveboxBaseModel


class KeymapComment(GloveboxBaseModel):
    """Model for preserved comments from ZMK keymap files."""

    text: str
    line: int = Field(default=0)
    context: str = Field(default="")  # "header", "behavior", "layer", "footer", etc.
    is_block: bool = Field(default=False)  # True for /* */, False for //


class KeymapInclude(GloveboxBaseModel):
    """Model for include directives in ZMK keymap files."""

    path: str
    line: int = Field(default=0)
    resolved_path: str = Field(default="")  # Actual resolved file path if available


class ConfigDirective(GloveboxBaseModel):
    """Model for configuration directives in ZMK keymap files."""

    directive: str  # "ifdef", "ifndef", "define", etc.
    condition: str = Field(default="")
    value: str = Field(default="")
    line: int = Field(default=0)


class DependencyInfo(GloveboxBaseModel):
    """Dependency tracking information for behaviors and includes."""

    include_dependencies: list[str] = Field(
        default_factory=list, description="List of include files this keymap depends on"
    )
    behavior_sources: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of behavior names to their source files",
    )
    unresolved_includes: list[str] = Field(
        default_factory=list,
        description="Include paths that could not be resolved to actual files",
    )


class KeymapMetadata(GloveboxBaseModel):
    """Enhanced metadata extracted from ZMK keymap parsing."""

    # File structure metadata
    comments: list[KeymapComment] = Field(default_factory=list)
    includes: list[KeymapInclude] = Field(default_factory=list)
    config_directives: list[ConfigDirective] = Field(
        default_factory=list, alias="configDirectives"
    )

    # Parsing metadata
    parsing_method: str = Field(default="ast")  # "ast" or "regex"
    parsing_mode: str = Field(default="full")  # "full", "template", "auto"
    parse_timestamp: datetime = Field(default_factory=datetime.now)
    source_file: str = Field(default="")

    # Original structure preservation
    original_header: str = Field(default="")  # Comments and includes before first node
    original_footer: str = Field(default="")  # Comments after last node
    custom_sections: dict[str, str] = Field(
        default_factory=dict,
        description="Custom sections with their content for round-trip preservation",
    )

    # Dependency tracking (Phase 4.3)
    dependencies: DependencyInfo = Field(
        default_factory=DependencyInfo,
        description="Dependency tracking for include files and behaviors",
    )

    @field_serializer("parse_timestamp", when_used="json")
    def serialize_parse_timestamp(self, dt: datetime) -> int:
        """Serialize parse timestamp to Unix timestamp for JSON."""
        return int(dt.timestamp())
