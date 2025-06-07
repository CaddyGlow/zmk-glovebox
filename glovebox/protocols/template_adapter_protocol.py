"""Protocol definition for template rendering operations."""

from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class TemplateAdapterProtocol(Protocol):
    """Protocol for template rendering operations."""

    def render_template(
        self,
        template_path: Path,
        context: dict[str, Any],
        output_path: Path | None = None,
    ) -> str:
        """Render a template with the given context.

        Args:
            template_path: Path to the template file
            context: Template context variables
            output_path: Optional path to write rendered content

        Returns:
            Rendered template content as string

        Raises:
            GloveboxError: If template rendering fails
        """
        ...

    def render_string(self, template_string: str, context: dict[str, Any]) -> str:
        """Render a template string with the given context.

        Args:
            template_string: Template content as string
            context: Template context variables

        Returns:
            Rendered template content as string

        Raises:
            GloveboxError: If template rendering fails
        """
        ...

    def validate_template(self, template_path: Path) -> bool:
        """Validate that a template file is syntactically correct.

        Args:
            template_path: Path to the template file

        Returns:
            True if template is valid, False otherwise
        """
        ...

    def get_template_variables(self, template_input: str | Path) -> list[str]:
        """Extract variable names used in a template.

        Args:
            template_input: Path to the template file or template content string

        Returns:
            List of variable names found in template

        Raises:
            GloveboxError: If template cannot be parsed
        """
        ...
