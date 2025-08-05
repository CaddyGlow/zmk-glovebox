"""Template adapter for abstracting template rendering operations."""

import logging
from pathlib import Path
from typing import Any, assert_never

from glovebox.core.errors import TemplateError
from glovebox.core.structlog_logger import get_struct_logger
from glovebox.protocols.template_adapter_protocol import TemplateAdapterProtocol
from glovebox.utils.error_utils import create_template_error


logger = get_struct_logger(__name__)


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
            logger.error("template_not_found", template_path=str(template_path))
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
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error(
                "template_render_error",
                template_path=str(template_path),
                error=str(e),
                exc_info=exc_info,
            )
            raise error from e

    def render_string(self, template_string: str, context: dict[str, Any]) -> str:
        """Render a Jinja2 template string with the given context."""
        try:
            # Create Jinja2 environment
            from jinja2 import Environment, StrictUndefined

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
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error(
                "template_string_render_error", error=str(e), exc_info=exc_info
            )
            raise error from e

    def validate_template(self, template_path: Path) -> bool:
        """Validate that a Jinja2 template file is syntactically correct."""
        try:
            from jinja2 import Environment, FileSystemLoader

            logger.debug("validating_template", template_path=str(template_path))

            if not template_path.exists():
                logger.warning(
                    "template_file_not_exist", template_path=str(template_path)
                )
                return False

            # Create Jinja2 environment
            env = Environment(
                loader=FileSystemLoader(template_path.parent),
                trim_blocks=self.trim_blocks,
                lstrip_blocks=self.lstrip_blocks,
            )

            # Try to parse the template
            env.get_template(template_path.name)

            logger.debug(
                "template_validation_successful", template_path=str(template_path)
            )
            return True

        except Exception as e:
            logger.warning(
                "template_validation_failed",
                template_path=str(template_path),
                error=str(e),
            )
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

            logger.debug(
                "extracting_template_variables", template_path=str(template_path)
            )

            if not template_path.exists():
                error = create_template_error(
                    template_path,
                    "get_template_variables",
                    FileNotFoundError("Template file not found"),
                    {},
                )
                logger.error(
                    "template_file_does_not_exist", template_path=str(template_path)
                )
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
                "template_variables_found",
                variable_count=len(variables),
                variables=variables,
            )
            return sorted(variables)

        except Exception as e:
            error = create_template_error(
                template_path, "get_template_variables", e, {}
            )
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error(
                "template_variable_extraction_error",
                template_path=str(template_path),
                error=str(e),
                exc_info=exc_info,
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
            logger.debug("reading_template_file", template_path=str(template_path))

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
            logger.error("template_file_not_found", template_path=str(template_path))
            raise error from e
        except PermissionError as e:
            error = create_template_error(
                template_path,
                "render_template_from_file",
                e,
                {"context_keys": list(context.keys()), "encoding": encoding},
            )
            logger.error(
                "template_read_permission_denied", template_path=str(template_path)
            )
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
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error(
                "template_file_render_error",
                template_path=str(template_path),
                error=str(e),
                exc_info=exc_info,
            )
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

            logger.debug("validating_template_syntax")

            # Create Jinja2 environment
            env = Environment(
                trim_blocks=self.trim_blocks,
                lstrip_blocks=self.lstrip_blocks,
            )

            # Try to parse the template
            env.from_string(template_content)

            logger.debug("template_syntax_validation_successful")
            return True

        except Exception as e:
            logger.warning("template_syntax_validation_failed", error=str(e))
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

            logger.debug("extracting_variables_from_template_string")

            # Create Jinja2 environment
            env = Environment(
                trim_blocks=self.trim_blocks,
                lstrip_blocks=self.lstrip_blocks,
            )

            # Parse template and extract variables
            ast = env.parse(template_content)
            variables = list(meta.find_undeclared_variables(ast))

            logger.debug(
                "template_variables_found",
                variable_count=len(variables),
                variables=variables,
            )
            return sorted(variables)

        except Exception as e:
            error = create_template_error(
                template_content,
                "get_template_variables_from_string",
                e,
                {"template_length": len(template_content)},
            )
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error("template_string_parse_error", error=str(e), exc_info=exc_info)
            raise error from e

    def _write_output(self, output_path: Path, content: str) -> None:
        """Write rendered content to output file."""
        try:
            # Ensure parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            logger.debug("writing_rendered_content", output_path=str(output_path))
            with output_path.open(mode="w", encoding="utf-8") as f:
                f.write(content)
            logger.debug(
                "rendered_content_written_successfully", output_path=str(output_path)
            )

        except Exception as e:
            error = create_template_error(
                output_path, "write_output", e, {"content_length": len(content)}
            )
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error(
                "rendered_content_write_error",
                output_path=str(output_path),
                error=str(e),
                exc_info=exc_info,
            )
            raise error from e


def create_template_adapter() -> TemplateAdapterProtocol:
    """Create a template adapter with default implementation."""
    return TemplateAdapter()
