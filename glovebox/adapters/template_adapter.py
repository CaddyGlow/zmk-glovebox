"""Template adapter for abstracting template rendering operations."""

import logging
from pathlib import Path
from typing import Any, assert_never

from glovebox.core.errors import TemplateError
from glovebox.protocols.template_adapter_protocol import TemplateAdapterProtocol
from glovebox.utils.error_utils import create_template_error


logger = logging.getLogger(__name__)


class TemplateAdapter:
    """Jinja2 template adapter implementation."""

    def __init__(self, trim_blocks: bool = True, lstrip_blocks: bool = True):
        """Initialize the Jinja2 template adapter.

        Args:
            trim_blocks: Remove newlines after block tags
            lstrip_blocks: Strip leading whitespace from block tags
        """
        self.trim_blocks = trim_blocks
        self.lstrip_blocks = lstrip_blocks
        # Create a basic environment for the tests that expect it
        from jinja2 import Environment, StrictUndefined

        self.env = Environment(
            trim_blocks=self.trim_blocks,
            lstrip_blocks=self.lstrip_blocks,
            undefined=StrictUndefined,  # Raise errors for undefined variables
        )

    def render_template(
        self,
        template_path: Path,
        context: dict[str, Any],
        output_path: Path | None = None,
    ) -> str:
        """Render a Jinja2 template with the given context."""
        try:
            from jinja2 import Environment, FileSystemLoader, TemplateNotFound


            # Create Jinja2 environment
            env = Environment(
                loader=FileSystemLoader(template_path.parent),
                trim_blocks=self.trim_blocks,
                lstrip_blocks=self.lstrip_blocks,
            )

            # Load and render template
            template = env.get_template(template_path.name)
            rendered_content = template.render(context)

            # Write to file if output path specified
            if output_path:
                self._write_output(output_path, rendered_content)

            return rendered_content

        except TemplateNotFound as e:
            error = create_template_error(
                template_path,
                "render_template",
                e,
                {"context_keys": list(context.keys())},
            )
            logger.error("Template not found: %s", template_path)
            raise error from e
        except Exception as e:
            error = create_template_error(
                template_path,
                "render_template",
                e,
                {
                    "context_keys": list(context.keys()),
                    "output_path": str(output_path) if output_path else None,
                },
            )
            logger.error("Error rendering template %s: %s", template_path, e)
            raise error from e

    def render_string(self, template_string: str, context: dict[str, Any]) -> str:
        """Render a Jinja2 template string with the given context."""
        try:
            from jinja2 import Environment


            # Create Jinja2 environment
            from jinja2 import StrictUndefined

            env = Environment(
                trim_blocks=self.trim_blocks,
                lstrip_blocks=self.lstrip_blocks,
                undefined=StrictUndefined,  # Raise errors for undefined variables
            )

            # Create and render template
            template = env.from_string(template_string)
            rendered_content = template.render(context)

            return rendered_content

        except Exception as e:
            error = create_template_error(
                template_string,
                "render_string",
                e,
                {
                    "context_keys": list(context.keys()),
                    "template_length": len(template_string),
                },
            )
            logger.error("Error rendering template string: %s", e)
            raise error from e

    def validate_template(self, template_path: Path) -> bool:
        """Validate that a Jinja2 template file is syntactically correct."""
        try:
            from jinja2 import Environment, FileSystemLoader

            logger.debug("Validating template: %s", template_path)

            if not template_path.exists():
                logger.warning("Template file does not exist: %s", template_path)
                return False

            # Create Jinja2 environment
            env = Environment(
                loader=FileSystemLoader(template_path.parent),
                trim_blocks=self.trim_blocks,
                lstrip_blocks=self.lstrip_blocks,
            )

            # Try to parse the template
            env.get_template(template_path.name)

            logger.debug("Template validation successful: %s", template_path)
            return True

        except Exception as e:
            logger.warning("Template validation failed for %s: %s", template_path, e)
            return False

    def get_template_variables(self, template_input: str | Path) -> list[str]:
        """Extract variable names used in a Jinja2 template.

        Args:
            template_input: Either a Path to template file or template content string

        Returns:
            List of variable names found in template

        Raises:
            GloveboxError: If template cannot be parsed
        """
        # Handle Path objects directly
        # Function accepts only Path or str as input types
        if isinstance(template_input, Path):
            return self._get_template_variables_from_path(template_input)
        elif isinstance(template_input, str):
            # If it looks like template content (contains template syntax)
            if "{{" in template_input or "{%" in template_input:
                return self.get_template_variables_from_string(template_input)
            # If it looks like a file path, convert to Path and process
            elif "/" in template_input or "\\" in template_input:
                try:
                    template_path = Path(template_input)
                    return self._get_template_variables_from_path(template_path)
                except Exception as e:
                    # If conversion to Path failed, treat as template content
                    return self.get_template_variables_from_string(template_input)
            else:
                # Treat as template content string by default
                return self.get_template_variables_from_string(template_input)
        else:
            # This else clause is needed for static type checking
            # even though this point should be unreachable with proper typing
            assert_never(template_input)  # Assertion for exhaustiveness checking

    def _get_template_variables_from_path(self, template_path: Path) -> list[str]:
        """Extract variable names from a template file.

        Args:
            template_path: Path to the template file

        Returns:
            List of variable names found in template

        Raises:
            GloveboxError: If template cannot be parsed
        """
        try:
            from jinja2 import Environment, FileSystemLoader, meta

            logger.debug("Extracting variables from template file: %s", template_path)

            if not template_path.exists():
                error = create_template_error(
                    template_path,
                    "get_template_variables",
                    FileNotFoundError("Template file not found"),
                    {},
                )
                logger.error("Template file does not exist: %s", template_path)
                raise error

            # Create Jinja2 environment
            env = Environment(
                loader=FileSystemLoader(template_path.parent),
                trim_blocks=self.trim_blocks,
                lstrip_blocks=self.lstrip_blocks,
            )

            # Parse template and extract variables
            if env.loader:
                template_source = env.loader.get_source(env, template_path.name)[0]
                ast = env.parse(template_source)
                variables = list(meta.find_undeclared_variables(ast))
            else:
                # Fallback if loader is None
                with template_path.open("r", encoding="utf-8") as f:
                    template_source = f.read()
                ast = env.parse(template_source)
                variables = list(meta.find_undeclared_variables(ast))

            logger.debug(
                "Found %d variables in template: %s", len(variables), variables
            )
            return sorted(variables)

        except Exception as e:
            error = create_template_error(
                template_path, "get_template_variables", e, {}
            )
            logger.error(
                "Error extracting variables from template %s: %s",
                template_path,
                e,
            )
            raise error from e

    def render_template_from_file(
        self, template_path: Path, context: dict[str, Any], encoding: str = "utf-8"
    ) -> str:
        """Render a template file with the given context.

        Args:
            template_path: Path to the template file
            context: Template context variables
            encoding: File encoding to use

        Returns:
            Rendered template content as string

        Raises:
            TemplateError: If template rendering fails
        """
        try:
            logger.debug("Reading template file: %s", template_path)

            with template_path.open(mode="r", encoding=encoding) as f:
                template_content = f.read()

            return self.render_string(template_content, context)

        except FileNotFoundError as e:
            error = create_template_error(
                template_path,
                "render_template_from_file",
                e,
                {"context_keys": list(context.keys()), "encoding": encoding},
            )
            logger.error("Template file not found: %s", template_path)
            raise error from e
        except PermissionError as e:
            error = create_template_error(
                template_path,
                "render_template_from_file",
                e,
                {"context_keys": list(context.keys()), "encoding": encoding},
            )
            logger.error("Permission denied reading template: %s", template_path)
            raise error from e
        except TemplateError:
            # Let TemplateError from render_string pass through
            raise
        except Exception as e:
            error = create_template_error(
                template_path,
                "render_template_from_file",
                e,
                {"context_keys": list(context.keys()), "encoding": encoding},
            )
            logger.error("Error rendering template file %s: %s", template_path, e)
            raise error from e

    def validate_template_syntax(self, template_content: str) -> bool:
        """Validate that a template string is syntactically correct.

        Args:
            template_content: Template content as string

        Returns:
            True if template is valid, False otherwise
        """
        try:
            from jinja2 import Environment

            logger.debug("Validating template syntax")

            # Create Jinja2 environment
            env = Environment(
                trim_blocks=self.trim_blocks,
                lstrip_blocks=self.lstrip_blocks,
            )

            # Try to parse the template
            env.from_string(template_content)

            logger.debug("Template syntax validation successful")
            return True

        except Exception as e:
            logger.warning("Template syntax validation failed: %s", e)
            return False

    def get_template_variables_from_string(self, template_content: str) -> list[str]:
        """Extract variable names used in a template string.

        Args:
            template_content: Template content as string

        Returns:
            List of variable names found in template

        Raises:
            TemplateError: If template cannot be parsed
        """
        try:
            from jinja2 import Environment, meta

            logger.debug("Extracting variables from template string")

            # Create Jinja2 environment
            env = Environment(
                trim_blocks=self.trim_blocks,
                lstrip_blocks=self.lstrip_blocks,
            )

            # Parse template and extract variables
            ast = env.parse(template_content)
            variables = list(meta.find_undeclared_variables(ast))

            logger.debug(
                "Found %d variables in template: %s", len(variables), variables
            )
            return sorted(variables)

        except Exception as e:
            error = create_template_error(
                template_content,
                "get_template_variables_from_string",
                e,
                {"template_length": len(template_content)},
            )
            logger.error("Failed to parse template string: %s", e)
            raise error from e

    def _write_output(self, output_path: Path, content: str) -> None:
        """Write rendered content to output file."""
        try:
            # Ensure parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            logger.debug("Writing rendered content to: %s", output_path)
            with output_path.open(mode="w", encoding="utf-8") as f:
                f.write(content)
            logger.debug("Successfully wrote rendered content to: %s", output_path)

        except Exception as e:
            error = create_template_error(
                output_path, "write_output", e, {"content_length": len(content)}
            )
            logger.error("Error writing rendered content to %s: %s", output_path, e)
            raise error from e


def create_template_adapter() -> TemplateAdapterProtocol:
    """Create a template adapter with default implementation."""
    return TemplateAdapter()
