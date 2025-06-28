"""Filename generation utility with template support."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from jinja2 import Environment, Template

from glovebox.config.models.filename_templates import FilenameTemplateConfig


logger = logging.getLogger(__name__)


class FileType(Enum):
    """Supported file types for filename generation."""

    LAYOUT_JSON = "layout_json"
    KEYMAP = "keymap"
    CONF = "conf"
    FIRMWARE_UF2 = "firmware_uf2"
    ARTIFACTS_ZIP = "artifacts_zip"


class FilenameGenerator:
    """Generate filenames using configurable templates with Jinja2 support."""

    def __init__(self, templates: FilenameTemplateConfig):
        """Initialize the filename generator with template configuration.

        Args:
            templates: Filename template configuration
        """
        self.templates = templates
        self._env = self._create_jinja_environment()

    def _create_jinja_environment(self) -> Environment:
        """Create Jinja2 environment with custom filters."""
        env = Environment()

        if self.templates.enable_custom_filters:
            # Add custom filters for filename safety
            env.filters["sanitize"] = self._sanitize_filename
            env.filters["default"] = self._default_filter
            env.filters["truncate"] = self._truncate_filter

        return env

    def _sanitize_filename(self, value: str) -> str:
        """Sanitize a string for use in filenames.

        Removes or replaces characters that are problematic in filenames.
        """
        if not value:
            return "unnamed"

        # Replace problematic characters with underscores
        sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(value))

        # Replace multiple underscores with single underscore
        sanitized = re.sub(r"_+", "_", sanitized)

        # Remove leading/trailing underscores and dots
        sanitized = sanitized.strip("_.")

        # Ensure we have something left
        if not sanitized:
            return "unnamed"

        return sanitized

    def _default_filter(self, value: Any, default_value: str = "") -> str:
        """Return default value if the input is None, empty, or falsy."""
        if not value:
            return default_value
        return str(value)

    def _truncate_filter(self, value: str, max_length: int = 50) -> str:
        """Truncate a string to maximum length."""
        if len(value) <= max_length:
            return value
        return value[:max_length].rstrip("_.")

    def _get_template_context(
        self,
        layout_data: dict[str, Any] | None = None,
        profile_data: dict[str, Any] | None = None,
        original_filename: str | None = None,
        build_data: dict[str, Any] | None = None,
        board: str | None = None,
    ) -> dict[str, Any]:
        """Create template context with all available variables.

        Args:
            layout_data: Layout data including title, keyboard, etc.
            profile_data: Profile data including keyboard_name, firmware_version
            original_filename: Original filename if available
            build_data: Build metadata like build_id, build_date
            board: Board name for firmware files

        Returns:
            Dictionary of template variables
        """
        context: dict[str, Any] = {
            "now": datetime.now(),
        }

        # Add layout data
        if layout_data:
            # Handle date field that might be an integer timestamp or datetime
            date_value = layout_data.get("date")
            if isinstance(date_value, int):
                # Convert timestamp to datetime
                date_value = datetime.fromtimestamp(date_value)
            elif not isinstance(date_value, datetime) and date_value is not None:
                # If it's a string or other type, try to parse or use current time
                try:
                    # Try parsing as ISO format first
                    date_value = datetime.fromisoformat(str(date_value))
                except (ValueError, TypeError):
                    # Fall back to current time
                    date_value = datetime.now()

            context.update(
                {
                    "title": layout_data.get("title", ""),
                    "keyboard": layout_data.get("keyboard", ""),
                    "version": layout_data.get("version", ""),
                    "creator": layout_data.get("creator", ""),
                    "date": date_value,
                    "uuid": layout_data.get("uuid", ""),
                }
            )

        # Add profile data
        if profile_data:
            context.update(
                {
                    "keyboard_name": profile_data.get("keyboard_name", ""),
                    "firmware_version": profile_data.get("firmware_version", ""),
                }
            )

        # Add original filename data
        if original_filename:
            original_path = Path(original_filename)
            context.update(
                {
                    "original_name": original_path.stem,
                    "original_stem": original_path.stem,
                    "original_suffix": original_path.suffix,
                }
            )

        # Add build data
        if build_data:
            # Handle build_date field that might be an integer timestamp or datetime
            build_date_value = build_data.get("build_date")
            if isinstance(build_date_value, int):
                # Convert timestamp to datetime
                build_date_value = datetime.fromtimestamp(build_date_value)
            elif (
                not isinstance(build_date_value, datetime)
                and build_date_value is not None
            ):
                # If it's a string or other type, try to parse or use current time
                try:
                    # Try parsing as ISO format first
                    build_date_value = datetime.fromisoformat(str(build_date_value))
                except (ValueError, TypeError):
                    # Fall back to current time
                    build_date_value = datetime.now()

            context.update(
                {
                    "build_id": build_data.get("build_id", ""),
                    "build_date": build_date_value,
                }
            )

        # Add board for firmware files
        if board:
            context["board"] = board

        return context

    def _render_template(self, template_str: str, context: dict[str, Any]) -> str:
        """Render a Jinja2 template with the given context.

        Args:
            template_str: Template string
            context: Template context variables

        Returns:
            Rendered filename
        """
        try:
            template = self._env.from_string(template_str)
            result = template.render(context)

            # Apply max length constraint
            if len(result) > self.templates.max_filename_length:
                # Try to truncate before the extension
                path = Path(result)
                max_stem_length = self.templates.max_filename_length - len(path.suffix)
                truncated_stem = path.stem[:max_stem_length].rstrip("_.")
                result = f"{truncated_stem}{path.suffix}"

            return result

        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.warning("Template rendering failed: %s", e, exc_info=exc_info)
            return ""

    def generate_filename(
        self,
        file_type: FileType,
        layout_data: dict[str, Any] | None = None,
        profile_data: dict[str, Any] | None = None,
        original_filename: str | None = None,
        build_data: dict[str, Any] | None = None,
        board: str | None = None,
    ) -> str:
        """Generate a filename using the configured templates.

        Args:
            file_type: Type of file to generate filename for
            layout_data: Layout data for template variables
            profile_data: Profile data for template variables
            original_filename: Original filename for fallback
            build_data: Build metadata for template variables
            board: Board name for firmware files

        Returns:
            Generated filename
        """
        context = self._get_template_context(
            layout_data=layout_data,
            profile_data=profile_data,
            original_filename=original_filename,
            build_data=build_data,
            board=board,
        )

        # Get primary template
        template_map = {
            FileType.LAYOUT_JSON: self.templates.layout_json,
            FileType.KEYMAP: self.templates.keymap,
            FileType.CONF: self.templates.conf,
            FileType.FIRMWARE_UF2: self.templates.firmware_uf2,
            FileType.ARTIFACTS_ZIP: self.templates.artifacts_zip,
        }

        # Get fallback template
        fallback_map = {
            FileType.LAYOUT_JSON: self.templates.fallback_layout_json,
            FileType.KEYMAP: self.templates.fallback_keymap,
            FileType.CONF: self.templates.fallback_conf,
            FileType.FIRMWARE_UF2: self.templates.fallback_firmware_uf2,
            FileType.ARTIFACTS_ZIP: self.templates.fallback_artifacts_zip,
        }

        primary_template = template_map[file_type]
        fallback_template = fallback_map[file_type]

        # Try primary template first
        result = self._render_template(primary_template, context)

        # Fall back if primary template failed or produced empty result
        if not result or result.strip() == "":
            logger.debug(
                "Primary template failed, using fallback for %s", file_type.value
            )
            result = self._render_template(fallback_template, context)

        # Final fallback with timestamp
        if not result or result.strip() == "":
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            extension_map = {
                FileType.LAYOUT_JSON: ".json",
                FileType.KEYMAP: ".keymap",
                FileType.CONF: ".conf",
                FileType.FIRMWARE_UF2: ".uf2",
                FileType.ARTIFACTS_ZIP: ".zip",
            }
            result = f"{file_type.value}_{timestamp}{extension_map[file_type]}"

        return result


def create_filename_generator(templates: FilenameTemplateConfig) -> FilenameGenerator:
    """Create a filename generator with the given template configuration.

    Args:
        templates: Filename template configuration

    Returns:
        Configured FilenameGenerator instance
    """
    return FilenameGenerator(templates)


def generate_default_filename(
    file_type: FileType,
    templates: FilenameTemplateConfig,
    layout_data: dict[str, Any] | None = None,
    profile_data: dict[str, Any] | None = None,
    original_filename: str | None = None,
    build_data: dict[str, Any] | None = None,
    board: str | None = None,
) -> str:
    """Generate a default filename using templates - convenience function.

    Args:
        file_type: Type of file to generate filename for
        templates: Filename template configuration
        layout_data: Layout data for template variables
        profile_data: Profile data for template variables
        original_filename: Original filename for fallback
        build_data: Build metadata for template variables
        board: Board name for firmware files

    Returns:
        Generated filename
    """
    generator = create_filename_generator(templates)
    return generator.generate_filename(
        file_type=file_type,
        layout_data=layout_data,
        profile_data=profile_data,
        original_filename=original_filename,
        build_data=build_data,
        board=board,
    )
