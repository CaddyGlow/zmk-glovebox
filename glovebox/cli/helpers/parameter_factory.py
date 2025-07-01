"""Factory for creating standardized parameter definitions.

This module provides a factory class for creating consistent parameter definitions
across CLI commands, eliminating duplication and ensuring standard behavior.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer

from glovebox.cli.helpers.parameters import (
    complete_json_files,
    complete_output_formats,
    complete_profile_names,
)


class ParameterFactory:
    """Factory for creating standardized parameter definitions."""

    # =============================================================================
    # Output Parameter Factories
    # =============================================================================

    @staticmethod
    def output_file(
        help_text: str | None = None,
        supports_stdout: bool = False,
        default_help_suffix: str = "",
    ) -> Any:
        """Create a standardized output file parameter.

        Args:
            help_text: Custom help text (uses default if None)
            supports_stdout: Whether to support '-' for stdout output
            default_help_suffix: Additional text to append to default help
        """
        if help_text is None:
            base_help = "Output file path."
            if supports_stdout:
                base_help += " Use '-' for stdout."
            base_help += " If not specified, generates a smart default filename."
            help_text = f"{base_help}{default_help_suffix}"

        return Annotated[
            str | None,
            typer.Option(
                "--output",
                "-o",
                help=help_text,
            ),
        ]

    @staticmethod
    def output_file_path_only(
        help_text: str | None = None,
        default_help_suffix: str = "",
    ) -> Any:
        """Create an output file parameter that only accepts file paths (no stdout)."""
        if help_text is None:
            help_text = f"Output file path.{default_help_suffix}"

        return Annotated[
            Path | None,
            typer.Option(
                "--output",
                "-o",
                help=help_text,
                dir_okay=False,
                writable=True,
            ),
        ]

    @staticmethod
    def output_directory(
        help_text: str | None = None,
        default_help_suffix: str = "",
    ) -> Any:
        """Create a standardized output directory parameter."""
        if help_text is None:
            help_text = f"Output directory path.{default_help_suffix}"

        return Annotated[
            Path,
            typer.Option(
                "--output",
                "-o",
                help=help_text,
                file_okay=False,
                dir_okay=True,
                writable=True,
            ),
        ]

    @staticmethod
    def output_directory_optional(
        help_text: str | None = None,
        default_help_suffix: str = "",
    ) -> Any:
        """Create an optional output directory parameter."""
        if help_text is None:
            help_text = f"Output directory path. If not specified, uses current directory.{default_help_suffix}"

        return Annotated[
            Path | None,
            typer.Option(
                "--output",
                "-o",
                help=help_text,
                file_okay=False,
                dir_okay=True,
                writable=True,
            ),
        ]

    # =============================================================================
    # Input Parameter Factories
    # =============================================================================

    @staticmethod
    def input_file(
        help_text: str | None = None,
        file_extensions: list[str] | None = None,
        default_help_suffix: str = "",
    ) -> Any:
        """Create a standardized required input file parameter."""
        if help_text is None:
            help_text = "Input file path."
            if file_extensions:
                help_text += f" Supported formats: {', '.join(file_extensions)}"
            help_text += default_help_suffix

        return Annotated[
            Path,
            typer.Argument(
                help=help_text,
                exists=True,
                file_okay=True,
                dir_okay=False,
                readable=True,
            ),
        ]

    @staticmethod
    def input_file_optional(
        help_text: str | None = None,
        env_var: str = "GLOVEBOX_JSON_FILE",
        default_help_suffix: str = "",
    ) -> Any:
        """Create an optional input file parameter with environment variable fallback."""
        if help_text is None:
            help_text = f"Input file path. Uses {env_var} environment variable if not provided.{default_help_suffix}"

        return Annotated[
            Path | None,
            typer.Argument(
                help=help_text,
                exists=False,  # Will be validated in processing
                file_okay=True,
                dir_okay=False,
            ),
        ]

    @staticmethod
    def input_file_with_stdin(
        help_text: str | None = None,
        library_resolvable: bool = False,
        default_help_suffix: str = "",
    ) -> Any:
        """Create an input file parameter that supports stdin."""
        if help_text is None:
            base_help = "Input file path or '-' for stdin"
            if library_resolvable:
                base_help += " or @library-name/uuid"
            help_text = f"{base_help}.{default_help_suffix}"

        # Library resolution is handled at command level to avoid circular imports
        return Annotated[
            str,
            typer.Argument(help=help_text),
        ]

    @staticmethod
    def input_file_with_stdin_optional(
        help_text: str | None = None,
        env_var: str = "GLOVEBOX_JSON_FILE",
        library_resolvable: bool = False,
        default_help_suffix: str = "",
    ) -> Any:
        """Create an optional input file parameter with stdin and env var support."""
        if help_text is None:
            base_help = "Input file path or '-' for stdin"
            if library_resolvable:
                base_help += " or @library-name/uuid"
            base_help += f". Uses {env_var} environment variable if not provided"
            help_text = f"{base_help}.{default_help_suffix}"

        if library_resolvable:
            from glovebox.cli.decorators.library_params import (
                library_resolvable_callback,
            )

            return Annotated[
                str | None,
                typer.Argument(
                    help=help_text,
                    callback=library_resolvable_callback,
                ),
            ]
        else:
            return Annotated[
                str | None,
                typer.Argument(help=help_text),
            ]

    @staticmethod
    def input_directory(
        help_text: str | None = None,
        default_help_suffix: str = "",
    ) -> Any:
        """Create a standardized input directory parameter."""
        if help_text is None:
            help_text = f"Input directory path.{default_help_suffix}"

        return Annotated[
            Path,
            typer.Argument(
                help=help_text,
                exists=True,
                file_okay=False,
                dir_okay=True,
                readable=True,
            ),
        ]

    @staticmethod
    def input_multiple_files(
        help_text: str | None = None,
        file_extensions: list[str] | None = None,
        default_help_suffix: str = "",
    ) -> Any:
        """Create a parameter for multiple input files."""
        if help_text is None:
            help_text = "One or more input file paths."
            if file_extensions:
                help_text += f" Supported formats: {', '.join(file_extensions)}"
            help_text += default_help_suffix

        return Annotated[
            list[Path],
            typer.Argument(
                help=help_text,
                exists=True,
                file_okay=True,
                dir_okay=False,
                readable=True,
            ),
        ]

    @staticmethod
    def json_file_argument(
        help_text: str | None = None,
        env_var: str = "GLOVEBOX_JSON_FILE",
        library_resolvable: bool = True,
        default_help_suffix: str = "",
    ) -> Any:
        """Create a JSON file argument with completion and env var support.

        Args:
            help_text: Custom help text
            env_var: Environment variable name for fallback
            library_resolvable: Whether to support @library-name references
            default_help_suffix: Additional help text suffix
        """
        if help_text is None:
            base_help = "JSON layout file path or '-' for stdin"
            if library_resolvable:
                base_help += " or @library-name/uuid"
            base_help += f". Uses {env_var} environment variable if not provided"
            help_text = f"{base_help}.{default_help_suffix}"

        # Library resolution is handled at command level to avoid circular imports
        return Annotated[
            str | None,
            typer.Argument(
                help=help_text,
                autocompletion=complete_json_files,
            ),
        ]

    # =============================================================================
    # Format Parameter Factories
    # =============================================================================

    @staticmethod
    def output_format(
        help_text: str | None = None,
        supported_formats: list[str] | None = None,
        default_help_suffix: str = "",
    ) -> Any:
        """Create a standardized output format parameter."""
        if supported_formats is None:
            supported_formats = ["rich-table", "text", "json", "markdown"]

        if help_text is None:
            format_list = "|".join(supported_formats)
            help_text = f"Output format: {format_list}{default_help_suffix}"

        return Annotated[
            str,
            typer.Option(
                "--output-format",
                "-t",
                help=help_text,
                autocompletion=complete_output_formats,
            ),
        ]

    @staticmethod
    def legacy_format(
        help_text: str | None = None,
        supported_formats: list[str] | None = None,
        default_help_suffix: str = "",
    ) -> Any:
        """Create a legacy format parameter (--format instead of --output-format)."""
        if supported_formats is None:
            supported_formats = ["table", "text", "json", "markdown"]

        if help_text is None:
            format_list = "|".join(supported_formats)
            help_text = f"Output format: {format_list}{default_help_suffix}"

        return Annotated[
            str,
            typer.Option(
                "--format",
                "-f",
                help=help_text,
                autocompletion=complete_output_formats,
            ),
        ]

    @staticmethod
    def json_boolean_flag(
        help_text: str | None = None,
        default_help_suffix: str = "",
    ) -> Any:
        """Create a boolean JSON flag parameter."""
        if help_text is None:
            help_text = f"Output in JSON format.{default_help_suffix}"

        return Annotated[
            bool,
            typer.Option(
                "--json",
                help=help_text,
            ),
        ]

    @staticmethod
    def format_with_json_flag(
        help_text: str | None = None,
        supported_formats: list[str] | None = None,
        default_help_suffix: str = "",
    ) -> Any:
        """Create a format parameter with separate JSON boolean flag."""
        if supported_formats is None:
            supported_formats = ["table", "text", "markdown"]

        if help_text is None:
            format_list = "|".join(supported_formats)
            help_text = f"Output format: {format_list} (use --json for JSON format){default_help_suffix}"

        return Annotated[
            str,
            typer.Option(
                "--format",
                "-f",
                help=help_text,
                autocompletion=complete_output_formats,
            ),
        ]

    # =============================================================================
    # Control Parameter Factories
    # =============================================================================

    @staticmethod
    def force_overwrite(
        help_text: str | None = None,
        default_help_suffix: str = "",
    ) -> Any:
        """Create a force overwrite parameter."""
        if help_text is None:
            help_text = (
                f"Overwrite existing files without prompting.{default_help_suffix}"
            )

        return Annotated[
            bool,
            typer.Option(
                "--force",
                help=help_text,
            ),
        ]

    @staticmethod
    def verbose_flag(
        help_text: str | None = None,
        default_help_suffix: str = "",
    ) -> Any:
        """Create a verbose output parameter."""
        if help_text is None:
            help_text = f"Enable verbose output.{default_help_suffix}"

        return Annotated[
            bool,
            typer.Option(
                "--verbose",
                "-v",
                help=help_text,
            ),
        ]

    @staticmethod
    def quiet_flag(
        help_text: str | None = None,
        default_help_suffix: str = "",
    ) -> Any:
        """Create a quiet output parameter."""
        if help_text is None:
            help_text = f"Suppress non-error output.{default_help_suffix}"

        return Annotated[
            bool,
            typer.Option(
                "--quiet",
                "-q",
                help=help_text,
            ),
        ]

    @staticmethod
    def dry_run_flag(
        help_text: str | None = None,
        default_help_suffix: str = "",
    ) -> Any:
        """Create a dry run parameter."""
        if help_text is None:
            help_text = (
                f"Show what would be done without making changes.{default_help_suffix}"
            )

        return Annotated[
            bool,
            typer.Option(
                "--dry-run",
                help=help_text,
            ),
        ]

    @staticmethod
    def backup_flag(
        help_text: str | None = None,
        default_help_suffix: str = "",
    ) -> Any:
        """Create a backup parameter."""
        if help_text is None:
            help_text = f"Create backup of existing files before overwriting.{default_help_suffix}"

        return Annotated[
            bool,
            typer.Option(
                "--backup",
                help=help_text,
            ),
        ]

    @staticmethod
    def no_backup_flag(
        help_text: str | None = None,
        default_help_suffix: str = "",
    ) -> Any:
        """Create a no-backup parameter."""
        if help_text is None:
            help_text = f"Do not create backup of existing files.{default_help_suffix}"

        return Annotated[
            bool,
            typer.Option(
                "--no-backup",
                help=help_text,
            ),
        ]

    # =============================================================================
    # Profile and Configuration Parameter Factories
    # =============================================================================

    @staticmethod
    def profile_option(
        help_text: str | None = None,
        required: bool = False,
        default_help_suffix: str = "",
    ) -> Any:
        """Create a profile parameter."""
        if help_text is None:
            base_text = "Keyboard profile in format 'keyboard' or 'keyboard/firmware'"
            if required:
                base_text += " (required)"
            help_text = f"{base_text}.{default_help_suffix}"

        param_type = str if required else str | None

        return Annotated[
            param_type,
            typer.Option(
                "--profile",
                "-p",
                help=help_text,
                autocompletion=complete_profile_names,
            ),
        ]

    # =============================================================================
    # Validation Parameter Factories
    # =============================================================================

    @staticmethod
    def validate_only_flag(
        help_text: str | None = None,
        default_help_suffix: str = "",
    ) -> Any:
        """Create a validate-only parameter."""
        if help_text is None:
            help_text = f"Only validate input without processing.{default_help_suffix}"

        return Annotated[
            bool,
            typer.Option(
                "--validate-only",
                help=help_text,
            ),
        ]

    @staticmethod
    def skip_validation_flag(
        help_text: str | None = None,
        default_help_suffix: str = "",
    ) -> Any:
        """Create a skip-validation parameter."""
        if help_text is None:
            help_text = (
                f"Skip input validation (use with caution).{default_help_suffix}"
            )

        return Annotated[
            bool,
            typer.Option(
                "--skip-validation",
                help=help_text,
            ),
        ]


# =============================================================================
# Convenience Functions for Common Parameter Combinations
# =============================================================================


class CommonParameterSets:
    """Pre-defined parameter sets for common command patterns."""

    @staticmethod
    def input_output_format(
        input_help: str | None = None,
        output_help: str | None = None,
        format_help: str | None = None,
        supports_stdin: bool = True,
        supports_stdout: bool = True,
        input_extensions: list[str] | None = None,
        format_types: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a standard input/output/format parameter set."""
        params = {}

        # Input parameter
        if supports_stdin:
            params["input_file"] = ParameterFactory.input_file_with_stdin(
                help_text=input_help,
            )
        else:
            params["input_file"] = ParameterFactory.input_file(
                help_text=input_help,
                file_extensions=input_extensions,
            )

        # Output parameter
        params["output"] = ParameterFactory.output_file(
            help_text=output_help,
            supports_stdout=supports_stdout,
        )

        # Format parameter
        params["output_format"] = ParameterFactory.output_format(
            help_text=format_help,
            supported_formats=format_types,
        )

        # Force parameter
        params["force"] = ParameterFactory.force_overwrite()

        return params

    @staticmethod
    def compilation_parameters(
        input_help: str | None = None,
        output_help: str | None = None,
    ) -> dict[str, Any]:
        """Create parameters for compilation commands."""
        return {
            "json_file": ParameterFactory.json_file_argument(help_text=input_help),
            "output_dir": ParameterFactory.output_directory_optional(
                help_text=output_help
            ),
            "profile": ParameterFactory.profile_option(),
            "force": ParameterFactory.force_overwrite(),
            "verbose": ParameterFactory.verbose_flag(),
        }

    @staticmethod
    def display_parameters(
        input_help: str | None = None,
        format_help: str | None = None,
        format_types: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create parameters for display/show commands."""
        return {
            "json_file": ParameterFactory.json_file_argument(help_text=input_help),
            "output_format": ParameterFactory.output_format(
                help_text=format_help,
                supported_formats=format_types,
            ),
            "verbose": ParameterFactory.verbose_flag(),
        }

    @staticmethod
    def file_transformation_parameters(
        input_help: str | None = None,
        output_help: str | None = None,
        supports_stdout: bool = True,
    ) -> dict[str, Any]:
        """Create parameters for file transformation commands."""
        return {
            "input_file": ParameterFactory.input_file_with_stdin(help_text=input_help),
            "output": ParameterFactory.output_file(
                help_text=output_help,
                supports_stdout=supports_stdout,
            ),
            "force": ParameterFactory.force_overwrite(),
            "backup": ParameterFactory.backup_flag(),
            "dry_run": ParameterFactory.dry_run_flag(),
        }
