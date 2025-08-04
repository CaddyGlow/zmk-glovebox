"""Filename template configuration models."""

from __future__ import annotations

from pydantic import Field

from glovebox.models.base import GloveboxBaseModel


class FilenameTemplateConfig(GloveboxBaseModel):
    """Configuration for filename templates with Jinja2 support.

    Templates can use the following variables:
    - Layout data: title, keyboard, version, creator, date, uuid
    - Profile data: keyboard_name, firmware_version
    - Original filename: original_name, original_stem, original_suffix
    - Current datetime: now (datetime object)
    - Build metadata: build_id, build_date (when available)
    """

    # Default filename templates for different file types
    layout_json: str = Field(
        default="{{title|sanitize}}_{{keyboard}}_{{date.strftime('%Y%m%d')}}.json",
        description="Template for layout JSON files. Default: '{{title|sanitize}}_{{keyboard}}_{{date.strftime('%Y%m%d')}}.json'",
    )

    keymap: str = Field(
        default="{{title|sanitize}}_{{keyboard}}_{{firmware_version}}.keymap",
        description="Template for keymap files. Default: '{{title|sanitize}}_{{keyboard}}_{{firmware_version}}.keymap'",
    )

    conf: str = Field(
        default="{{title|sanitize}}_{{keyboard}}_{{firmware_version}}.conf",
        description="Template for conf files. Default: '{{title|sanitize}}_{{keyboard}}_{{firmware_version}}.conf'",
    )

    firmware_uf2: str = Field(
        default="{{title|sanitize}}_{{keyboard}}_{{firmware_version}}_{{board}}.uf2",
        description="Template for UF2 firmware files. Default: '{{title|sanitize}}_{{keyboard}}_{{firmware_version}}_{{board}}.uf2'",
    )

    artifacts_zip: str = Field(
        default="{{title|sanitize}}_{{keyboard}}_{{firmware_version}}_artifacts.zip",
        description="Template for build artifacts ZIP files. Default: '{{title|sanitize}}_{{keyboard}}_{{firmware_version}}_artifacts.zip'",
    )

    # Fallback patterns when data is missing
    fallback_layout_json: str = Field(
        default="{{original_name|default('layout_' + now.strftime('%Y%m%d_%H%M%S'))}}.json",
        description="Fallback template when layout data is unavailable",
    )

    fallback_keymap: str = Field(
        default="{{original_name|default('keymap_' + now.strftime('%Y%m%d_%H%M%S'))}}.keymap",
        description="Fallback template when layout data is unavailable",
    )

    fallback_conf: str = Field(
        default="{{original_name|default('config_' + now.strftime('%Y%m%d_%H%M%S'))}}.conf",
        description="Fallback template when layout data is unavailable",
    )

    fallback_firmware_uf2: str = Field(
        default="{{original_name|default('firmware_' + now.strftime('%Y%m%d_%H%M%S'))}}.uf2",
        description="Fallback template when build data is unavailable",
    )

    fallback_artifacts_zip: str = Field(
        default="{{original_name|default('artifacts_' + now.strftime('%Y%m%d_%H%M%S'))}}.zip",
        description="Fallback template when build data is unavailable",
    )

    # Template engine settings
    enable_custom_filters: bool = Field(
        default=True,
        description="Enable custom Jinja2 filters like 'sanitize' for filename safety",
    )

    max_filename_length: int = Field(
        default=200,
        description="Maximum filename length (including extension). Long names will be truncated.",
    )


def create_default_filename_templates() -> FilenameTemplateConfig:
    """Create default filename template configuration."""
    return FilenameTemplateConfig()
