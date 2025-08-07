"""Glovebox implementation of TemplateProvider for zmk-layout."""

import logging
from typing import Any

from glovebox.models.base import GloveboxBaseModel


class GloveboxTemplateProvider(GloveboxBaseModel):
    """Template provider that bridges glovebox template service to zmk-layout."""

    def __init__(self, template_service):
        super().__init__()
        self.template_service = template_service
        self.logger = logging.getLogger(__name__)

    def render_string(self, template: str, context: dict[str, Any]) -> str:
        """Render a template string with given context."""
        try:
            result = self.template_service.render_string(template, context)
            self.logger.debug(
                "Rendered template string",
                extra={
                    "template_length": len(template),
                    "context_keys": list(context.keys()),
                    "result_length": len(result),
                },
            )
            return result

        except Exception as e:
            # Convert glovebox template errors to standard format
            self.logger.error(
                "Template string rendering failed: %s",
                e,
                exc_info=self.logger.isEnabledFor(logging.DEBUG),
            )
            raise ValueError(f"Template rendering failed: {e}") from e

    def render_file(self, template_path: str, context: dict[str, Any]) -> str:
        """Render a template file with given context."""
        try:
            result = self.template_service.render_file(template_path, context)
            self.logger.debug(
                "Rendered template file",
                extra={
                    "template_path": template_path,
                    "context_keys": list(context.keys()),
                    "result_length": len(result),
                },
            )
            return result

        except Exception as e:
            self.logger.error(
                "Template file rendering failed: %s",
                e,
                extra={"template_path": template_path},
                exc_info=self.logger.isEnabledFor(logging.DEBUG),
            )
            raise ValueError(f"Template file rendering failed: {e}") from e

    def has_template_syntax(self, content: str) -> bool:
        """Check if content contains template syntax."""
        try:
            has_syntax = self.template_service.contains_template_syntax(content)
            self.logger.debug(
                "Template syntax check",
                extra={"content_length": len(content), "has_syntax": has_syntax},
            )
            return has_syntax

        except Exception as e:
            self.logger.error(
                "Template syntax detection failed: %s",
                e,
                exc_info=self.logger.isEnabledFor(logging.DEBUG),
            )
            # Conservative fallback - assume it might have syntax
            return True

    def validate_template(self, template: str) -> list[str]:
        """Validate template syntax."""
        try:
            self.template_service.validate_syntax(template)
            self.logger.debug(
                "Template validation passed", extra={"template_length": len(template)}
            )
            return []  # No errors

        except Exception as e:
            error_msg = str(e)
            self.logger.warning(
                "Template validation failed: %s",
                error_msg,
                extra={"template_length": len(template)},
            )
            return [error_msg]

    def escape_content(self, content: str) -> str:
        """Escape special characters in content."""
        try:
            escaped = self.template_service.escape_template_content(content)
            self.logger.debug(
                "Content escaped",
                extra={"original_length": len(content), "escaped_length": len(escaped)},
            )
            return escaped

        except Exception as e:
            self.logger.error(
                "Content escaping failed: %s",
                e,
                exc_info=self.logger.isEnabledFor(logging.DEBUG),
            )
            # Fallback to basic escaping
            return content.replace("{", "{{").replace("}", "}}")

    def get_template_engine_info(self) -> dict[str, Any]:
        """Get information about the template engine (glovebox extension)."""
        try:
            info = {
                "engine": self.template_service.get_engine_name(),
                "version": self.template_service.get_engine_version(),
                "features": self.template_service.get_supported_features(),
            }

            self.logger.debug(
                "Retrieved template engine info",
                extra={"engine": info.get("engine", "unknown")},
            )
            return info

        except Exception as e:
            self.logger.error(
                "Failed to get template engine info: %s",
                e,
                exc_info=self.logger.isEnabledFor(logging.DEBUG),
            )
            # Return fallback info
            return {
                "engine": "unknown",
                "version": "unknown",
                "features": [],
            }
