"""Layout service protocols for type-safe interfaces."""

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable


if TYPE_CHECKING:
    from glovebox.layout.models import LayoutData


@runtime_checkable
class TemplateServiceProtocol(Protocol):
    """Protocol for layout template processing services.

    This protocol defines the interface for services that handle Jinja2 template
    processing in layout data, including multi-pass resolution to handle complex
    nested template dependencies.
    """

    def process_layout_data(self, layout_data: "LayoutData") -> "LayoutData":
        """Process layout data with multi-pass template resolution.

        Args:
            layout_data: The layout data containing template expressions

        Returns:
            Processed layout data with all templates resolved

        Raises:
            TemplateError: If template processing fails
            CircularReferenceError: If circular dependencies are detected
        """
        ...

    def create_template_context(
        self, layout_data: "LayoutData", stage: str
    ) -> dict[str, Any]:
        """Create template context for given resolution stage.

        Args:
            layout_data: The layout data to create context from
            stage: Resolution stage ('basic', 'behaviors', 'layers', 'custom')

        Returns:
            Template context dictionary for Jinja2 rendering
        """
        ...

    def validate_template_syntax(self, layout_data: "LayoutData") -> list[str]:
        """Validate all template syntax in layout data.

        Args:
            layout_data: The layout data to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        ...

    def process_raw_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Process templates directly on raw dictionary data.

        This method is used when we need to process templates before model validation.

        Args:
            data: Raw dictionary data containing templates

        Returns:
            Dictionary with resolved templates

        Raises:
            TemplateError: If template processing fails
        """
        ...
