"""Simplified parameter factory for creating standardized CLI parameters.

This module provides factory methods for creating consistent parameter definitions
across CLI commands, eliminating duplication and ensuring standard behavior.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

import typer


if TYPE_CHECKING:
    pass

from glovebox.cli.helpers.parameters import (
    complete_json_files,
    complete_output_formats,
    complete_profile_names,
)


class ParameterFactory:
    """Simplified factory for creating standardized parameter definitions."""

    @staticmethod
    def create_input_parameter(
        help_text: str = "Input source (file, '-' for stdin, '@name' for library)",
        default: str | None = None,
        required: bool = True,
    ) -> Any:
        """Create a standardized input parameter.

        Args:
            help_text: Help text for the parameter
            default: Default value if not provided
            required: Whether the parameter is required

        Returns:
            Annotated type with Typer Argument configured for input
        """
        return Annotated[
            str if required and default is None else str | None,
            typer.Argument(
                help=help_text,
                show_default=bool(default),
                autocompletion=complete_json_files
                if "json" in help_text.lower()
                else None,
            ),
        ]

    @staticmethod
    def create_output_parameter(
        help_text: str = "Output destination (file, directory, '-' for stdout)",
        default: str | None = None,
        is_option: bool = True,
    ) -> Any:
        """Create a standardized output parameter.

        Args:
            help_text: Help text for the parameter
            default: Default value if not provided
            is_option: Whether to create as Option (True) or Argument (False)

        Returns:
            Annotated type with Typer Option or Argument configured for output
        """
        if is_option:
            # Create option with proper param_decls
            opt = typer.Option(help=help_text, show_default=bool(default))
            opt.param_decls = ("--output", "-o")
            return Annotated[str | None, opt]
        else:
            return Annotated[
                str if default is None else str | None,
                typer.Argument(
                    help=help_text,
                    show_default=bool(default),
                ),
            ]

    @staticmethod
    def create_profile_parameter(
        help_text: str = "Keyboard profile in format 'keyboard' or 'keyboard/firmware'",
        default: str | None = None,
        required: bool = False,
    ) -> Any:
        """Create a standardized profile parameter.

        Args:
            help_text: Help text for the parameter
            default: Default value if not provided
            required: Whether the parameter is required

        Returns:
            Annotated type with Typer Option configured for profile selection
        """
        if required and not default:
            help_text += " (required)"

        opt = _create_option_with_decls(
            ("--profile", "-p"),
            help=help_text,
            show_default=bool(default),
            autocompletion=complete_profile_names,
        )
        return Annotated[
            str if required and default is None else str | None,
            opt,
        ]


def _create_option_with_decls(
    param_decls: tuple[str, ...], **kwargs: Any
) -> Any:  # Returns typer's internal option type
    """Helper to create Option with explicit param declarations."""
    opt = typer.Option(**kwargs)
    opt.param_decls = param_decls
    return opt


# Legacy compatibility - map old method names to new ones
# This allows existing code to work without immediate changes
def _create_legacy_wrapper(factory_class: type[ParameterFactory]) -> None:
    """Create legacy method wrappers for backward compatibility."""
    # Type: ignore comments are needed because we're dynamically adding attributes

    # Define all legacy methods
    legacy_methods: dict[str, Callable[..., Any]] = {
        # Input parameter legacy methods
        "input_file": lambda **kwargs: Annotated[
            Path,
            typer.Argument(
                help=kwargs.get(
                    "help_text",
                    "Input file path"
                    + (
                        f". Supported formats: {', '.join(kwargs.get('file_extensions', []))}"
                        if kwargs.get("file_extensions")
                        else ""
                    )
                    + kwargs.get("default_help_suffix", ""),
                ),
                exists=True,
                file_okay=True,
                dir_okay=False,
                readable=True,
            ),
        ],
        "input_file_optional": lambda **kwargs: Annotated[
            Path | None,
            typer.Argument(
                help=kwargs.get(
                    "help_text",
                    f"Input file path. Uses {kwargs.get('env_var', 'GLOVEBOX_JSON_FILE')} environment variable if not provided.{kwargs.get('default_help_suffix', '')}",
                ),
                exists=False,  # Will be validated in processing
                file_okay=True,
                dir_okay=False,
            ),
        ],
        "input_file_with_stdin": lambda **kwargs: Annotated[
            str,
            typer.Argument(
                help=kwargs.get("help_text")
                or (
                    "Input file path or '-' for stdin"
                    + (
                        " or @library-name/uuid"
                        if kwargs.get("library_resolvable")
                        else ""
                    )
                    + f".{kwargs.get('default_help_suffix', '')}"
                ),
            ),
        ],
        "input_file_with_stdin_optional": lambda **kwargs: Annotated[
            str | None,
            typer.Argument(
                help=kwargs.get(
                    "help_text",
                    "Input file path or '-' for stdin"
                    + (
                        " or @library-name/uuid"
                        if kwargs.get("library_resolvable", False)
                        else ""
                    )
                    + f". Uses {kwargs.get('env_var', 'GLOVEBOX_JSON_FILE')} environment variable if not provided.{kwargs.get('default_help_suffix', '')}",
                ),
                callback=kwargs.get("callback")
                if kwargs.get("library_resolvable")
                else None,
            ),
        ],
        "json_file_argument": lambda **kwargs: Annotated[
            str | None,
            typer.Argument(
                help=kwargs.get("help_text")
                or "JSON layout file path or '-' for stdin"
                + (
                    " or @library-name/uuid"
                    if kwargs.get("library_resolvable", True)
                    else ""
                )
                + f". Uses {kwargs.get('env_var', 'GLOVEBOX_JSON_FILE')} environment variable if not provided.{kwargs.get('default_help_suffix', '')}",
                autocompletion=complete_json_files,
            ),
        ],
        "json_file_argument_optional": lambda **kwargs: Annotated[
            str | None,
            typer.Argument(
                help=kwargs.get("help_text")
                or "JSON layout file path or '-' for stdin"
                + (
                    " or @library-name/uuid"
                    if kwargs.get("library_resolvable", True)
                    else ""
                )
                + f". Uses {kwargs.get('env_var', 'GLOVEBOX_JSON_FILE')} environment variable if not provided.{kwargs.get('default_help_suffix', '')}",
                autocompletion=complete_json_files,
            ),
        ],
        "input_directory": lambda **kwargs: Annotated[
            Path,
            typer.Argument(
                help=kwargs.get(
                    "help_text",
                    f"Input directory path.{kwargs.get('default_help_suffix', '')}",
                ),
                exists=True,
                file_okay=False,
                dir_okay=True,
                readable=True,
            ),
        ],
        "input_multiple_files": lambda **kwargs: Annotated[
            list[Path],
            typer.Argument(
                help=kwargs.get(
                    "help_text",
                    "One or more input file paths."
                    + (
                        f" Supported formats: {', '.join(kwargs.get('file_extensions', []))}"
                        if kwargs.get("file_extensions")
                        else ""
                    )
                    + kwargs.get("default_help_suffix", ""),
                ),
                exists=True,
                file_okay=True,
                dir_okay=False,
                readable=True,
            ),
        ],
        # Output parameter legacy methods
        "output_file": lambda **kwargs: Annotated[
            str | None,
            _create_option_with_decls(
                ("--output", "-o"),
                help=kwargs.get("help_text")
                or (
                    "Output file path."
                    + (" Use '-' for stdout." if kwargs.get("supports_stdout") else "")
                    + " If not specified, generates a smart default filename."
                    + kwargs.get("default_help_suffix", "")
                ),
            ),
        ],
        "output_file_path_only": lambda **kwargs: Annotated[
            Path | None,
            _create_option_with_decls(
                ("--output", "-o"),
                help=kwargs.get(
                    "help_text",
                    f"Output file path.{kwargs.get('default_help_suffix', '')}",
                ),
                dir_okay=False,
                writable=True,
            ),
        ],
        "output_directory": lambda **kwargs: Annotated[
            Path,
            _create_option_with_decls(
                ("--output", "-o"),
                help=kwargs.get(
                    "help_text",
                    f"Output directory path.{kwargs.get('default_help_suffix', '')}",
                ),
                file_okay=False,
                dir_okay=True,
                writable=True,
            ),
        ],
        "output_directory_optional": lambda **kwargs: Annotated[
            Path | None,
            _create_option_with_decls(
                ("--output", "-o"),
                help=kwargs.get("help_text")
                or f"Output directory path. If not specified, uses current directory.{kwargs.get('default_help_suffix', '')}",
                file_okay=False,
                dir_okay=True,
                writable=True,
            ),
        ],
        # Profile parameter legacy method
        "profile_option": lambda **kwargs: factory_class.create_profile_parameter(
            help_text=kwargs.get(
                "help_text",
                "Keyboard profile in format 'keyboard' or 'keyboard/firmware'",
            )
            + kwargs.get("default_help_suffix", ""),
            required=kwargs.get("required", False),
        ),
        # Format parameters
        "output_format": lambda **kwargs: Annotated[
            str,
            _create_option_with_decls(
                ("--output-format", "-t"),
                help=kwargs.get("help_text")
                or f"Output format: {('|'.join(kwargs.get('supported_formats') or ['rich-table', 'text', 'json', 'markdown']))}{kwargs.get('default_help_suffix', '')}",
                autocompletion=complete_output_formats,
            ),
        ],
        "legacy_format": lambda **kwargs: Annotated[
            str,
            _create_option_with_decls(
                ("--format", "-f"),
                help=kwargs.get("help_text")
                or f"Output format: {('|'.join(kwargs.get('supported_formats') or ['table', 'text', 'json', 'markdown']))}{kwargs.get('default_help_suffix', '')}",
                autocompletion=complete_output_formats,
            ),
        ],
        "json_boolean_flag": lambda **kwargs: Annotated[
            bool,
            _create_option_with_decls(
                ("--json",),
                help=kwargs.get(
                    "help_text",
                    f"Output in JSON format.{kwargs.get('default_help_suffix', '')}",
                ),
            ),
        ],
        "format_with_json_flag": lambda **kwargs: Annotated[
            str,
            _create_option_with_decls(
                ("--format", "-f"),
                help=kwargs.get("help_text")
                or f"Output format: {('|'.join(kwargs.get('supported_formats') or ['table', 'text', 'markdown']))} (use --json for JSON format){kwargs.get('default_help_suffix', '')}",
                autocompletion=complete_output_formats,
            ),
        ],
        # Control flags
        "force_overwrite": lambda **kwargs: Annotated[
            bool,
            _create_option_with_decls(
                ("--force",),
                help=kwargs.get(
                    "help_text",
                    f"Overwrite existing files without prompting.{kwargs.get('default_help_suffix', '')}",
                ),
            ),
        ],
        "verbose_flag": lambda **kwargs: Annotated[
            bool,
            _create_option_with_decls(
                ("--verbose", "-v"),
                help=kwargs.get(
                    "help_text",
                    f"Enable verbose output.{kwargs.get('default_help_suffix', '')}",
                ),
            ),
        ],
        "quiet_flag": lambda **kwargs: Annotated[
            bool,
            _create_option_with_decls(
                ("--quiet", "-q"),
                help=kwargs.get(
                    "help_text",
                    f"Suppress non-error output.{kwargs.get('default_help_suffix', '')}",
                ),
            ),
        ],
        "dry_run_flag": lambda **kwargs: Annotated[
            bool,
            _create_option_with_decls(
                ("--dry-run",),
                help=kwargs.get(
                    "help_text",
                    f"Show what would be done without making changes.{kwargs.get('default_help_suffix', '')}",
                ),
            ),
        ],
        "backup_flag": lambda **kwargs: Annotated[
            bool,
            _create_option_with_decls(
                ("--backup",),
                help=kwargs.get(
                    "help_text",
                    f"Create backup of existing files before overwriting.{kwargs.get('default_help_suffix', '')}",
                ),
            ),
        ],
        "no_backup_flag": lambda **kwargs: Annotated[
            bool,
            _create_option_with_decls(
                ("--no-backup",),
                help=kwargs.get(
                    "help_text",
                    f"Do not create backup of existing files.{kwargs.get('default_help_suffix', '')}",
                ),
            ),
        ],
        # Validation flags
        "validate_only_flag": lambda **kwargs: Annotated[
            bool,
            _create_option_with_decls(
                ("--validate-only",),
                help=kwargs.get(
                    "help_text",
                    f"Only validate input without processing.{kwargs.get('default_help_suffix', '')}",
                ),
            ),
        ],
        "skip_validation_flag": lambda **kwargs: Annotated[
            bool,
            _create_option_with_decls(
                ("--skip-validation",),
                help=kwargs.get(
                    "help_text",
                    f"Skip input validation (use with caution).{kwargs.get('default_help_suffix', '')}",
                ),
            ),
        ],
    }

    # Add all legacy methods to the factory class
    for method_name, method_func in legacy_methods.items():
        setattr(factory_class, method_name, method_func)


# Apply legacy wrappers to maintain backward compatibility
_create_legacy_wrapper(ParameterFactory)


# Legacy CommonParameterSets for backward compatibility
class CommonParameterSets:
    """Legacy parameter sets for backward compatibility."""

    @staticmethod
    def input_output_format(**kwargs: Any) -> dict[str, Any]:
        """Create a standard input/output/format parameter set."""
        return {
            "input_file": ParameterFactory.input_file_with_stdin(  # type: ignore[attr-defined]
                help_text=kwargs.get("input_help"),
                file_extensions=kwargs.get("input_extensions"),
            )
            if kwargs.get("supports_stdin", True)
            else ParameterFactory.input_file(  # type: ignore[attr-defined]
                help_text=kwargs.get("input_help"),
                file_extensions=kwargs.get("input_extensions"),
            ),
            "output": ParameterFactory.output_file(  # type: ignore[attr-defined]
                help_text=kwargs.get("output_help"),
                supports_stdout=kwargs.get("supports_stdout", False),
            ),
            "output_format": ParameterFactory.output_format(  # type: ignore[attr-defined]
                help_text=kwargs.get("format_help"),
                supported_formats=kwargs.get("format_types"),
            ),
            "force": ParameterFactory.force_overwrite(),  # type: ignore[attr-defined]
        }

    @staticmethod
    def compilation_parameters(**kwargs: Any) -> dict[str, Any]:
        """Create parameters for compilation commands."""
        return {
            "json_file": ParameterFactory.json_file_argument(  # type: ignore[attr-defined]
                help_text=kwargs.get("input_help")
            ),
            "output_dir": ParameterFactory.output_directory_optional(  # type: ignore[attr-defined]
                help_text=kwargs.get("output_help")
            ),
            "profile": ParameterFactory.profile_option(),  # type: ignore[attr-defined]
            "force": ParameterFactory.force_overwrite(),  # type: ignore[attr-defined]
            "verbose": ParameterFactory.verbose_flag(),  # type: ignore[attr-defined]
        }

    @staticmethod
    def display_parameters(**kwargs: Any) -> dict[str, Any]:
        """Create parameters for display/show commands."""
        return {
            "json_file": ParameterFactory.json_file_argument(  # type: ignore[attr-defined]
                help_text=kwargs.get("input_help")
            ),
            "output_format": ParameterFactory.output_format(  # type: ignore[attr-defined]
                help_text=kwargs.get("format_help"),
                supported_formats=kwargs.get("format_types"),
            ),
            "verbose": ParameterFactory.verbose_flag(),  # type: ignore[attr-defined]
        }

    @staticmethod
    def file_transformation_parameters(**kwargs: Any) -> dict[str, Any]:
        """Create parameters for file transformation commands."""
        return {
            "input_file": ParameterFactory.input_file_with_stdin(  # type: ignore[attr-defined]
                help_text=kwargs.get("input_help")
            ),
            "output": ParameterFactory.output_file(  # type: ignore[attr-defined]
                help_text=kwargs.get("output_help"),
                supports_stdout=kwargs.get("supports_stdout", True),
            ),
            "force": ParameterFactory.force_overwrite(),  # type: ignore[attr-defined]
            "backup": ParameterFactory.backup_flag(),  # type: ignore[attr-defined]
            "dry_run": ParameterFactory.dry_run_flag(),  # type: ignore[attr-defined]
        }
