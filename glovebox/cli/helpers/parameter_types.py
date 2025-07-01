"""Standardized parameter type definitions for CLI commands.

This module provides reusable parameter types that eliminate duplication across
CLI commands while ensuring consistent behavior and validation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from glovebox.cli.helpers.parameters import (
    complete_json_files,
    complete_output_formats,
    complete_profile_names,
)


# =============================================================================
# Output Parameter Types
# =============================================================================

OutputFileOption = Annotated[
    Path | None,
    typer.Option(
        "--output",
        "-o",
        help="Output file path. If not specified, generates a smart default filename.",
        dir_okay=False,
        writable=True,
    ),
]

OutputFileWithStdoutOption = Annotated[
    str | None,
    typer.Option(
        "--output",
        "-o",
        help="Output file path or '-' for stdout. If not specified, generates a smart default filename.",
    ),
]

OutputDirOption = Annotated[
    Path,
    typer.Option(
        "--output",
        "-o",
        help="Output directory path.",
        file_okay=False,
        dir_okay=True,
        writable=True,
    ),
]

OutputDirOptionalOption = Annotated[
    Path | None,
    typer.Option(
        "--output",
        "-o",
        help="Output directory path. If not specified, uses current directory.",
        file_okay=False,
        dir_okay=True,
        writable=True,
    ),
]

OutputPathOption = Annotated[
    str | None,
    typer.Option(
        "--output",
        "-o",
        help="Output path (file or directory). Supports template variables and smart defaults.",
    ),
]


# =============================================================================
# Input Parameter Types
# =============================================================================

InputFileArgument = Annotated[
    Path,
    typer.Argument(
        help="Input file path.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
]

InputFileOptionalArgument = Annotated[
    Path | None,
    typer.Argument(
        help="Input file path. Uses GLOVEBOX_JSON_FILE environment variable if not provided.",
        exists=False,  # Will be validated in processing
        file_okay=True,
        dir_okay=False,
    ),
]

InputFileWithStdinArgument = Annotated[
    str,
    typer.Argument(
        help="Input file path or '-' for stdin.",
    ),
]

InputFileWithStdinOptionalArgument = Annotated[
    str | None,
    typer.Argument(
        help="Input file path or '-' for stdin. Uses GLOVEBOX_JSON_FILE environment variable if not provided.",
    ),
]

InputDirArgument = Annotated[
    Path,
    typer.Argument(
        help="Input directory path.",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
    ),
]

InputMultipleFileArgument = Annotated[
    list[Path],
    typer.Argument(
        help="One or more input file paths.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
]

JsonFileArgument = Annotated[
    str | None,
    typer.Argument(
        help="JSON layout file path or '-' for stdin. Uses GLOVEBOX_JSON_FILE environment variable if not provided.",
        autocompletion=complete_json_files,
    ),
]


# =============================================================================
# Format Parameter Types
# =============================================================================

StandardFormatOption = Annotated[
    str,
    typer.Option(
        "--output-format",
        "-t",
        help="Output format: rich-table|text|json|markdown",
        autocompletion=complete_output_formats,
    ),
]

LegacyFormatOption = Annotated[
    str,
    typer.Option(
        "--format",
        "-f",
        help="Output format: table|text|json|markdown",
        autocompletion=complete_output_formats,
    ),
]

BooleanJsonOption = Annotated[
    bool,
    typer.Option(
        "--json",
        help="Output in JSON format.",
    ),
]

FormatWithJsonBooleanOption = Annotated[
    str,
    typer.Option(
        "--format",
        "-f",
        help="Output format: table|text|json|markdown (use --json for JSON format)",
        autocompletion=complete_output_formats,
    ),
]


# =============================================================================
# Common Control Parameter Types
# =============================================================================

ForceOverwriteOption = Annotated[
    bool,
    typer.Option(
        "--force",
        help="Overwrite existing files without prompting.",
    ),
]

VerboseOption = Annotated[
    bool,
    typer.Option(
        "--verbose",
        "-v",
        help="Enable verbose output.",
    ),
]

QuietOption = Annotated[
    bool,
    typer.Option(
        "--quiet",
        "-q",
        help="Suppress non-error output.",
    ),
]

DryRunOption = Annotated[
    bool,
    typer.Option(
        "--dry-run",
        help="Show what would be done without making changes.",
    ),
]


# =============================================================================
# Profile and Configuration Parameter Types
# =============================================================================

ProfileOption = Annotated[
    str | None,
    typer.Option(
        "--profile",
        "-p",
        help="Keyboard profile in format 'keyboard' or 'keyboard/firmware'.",
        autocompletion=complete_profile_names,
    ),
]

ProfileRequiredOption = Annotated[
    str,
    typer.Option(
        "--profile",
        "-p",
        help="Keyboard profile in format 'keyboard' or 'keyboard/firmware' (required).",
        autocompletion=complete_profile_names,
    ),
]


# =============================================================================
# Validation and Processing Parameter Types
# =============================================================================

ValidateOnlyOption = Annotated[
    bool,
    typer.Option(
        "--validate-only",
        help="Only validate input without processing.",
    ),
]

SkipValidationOption = Annotated[
    bool,
    typer.Option(
        "--skip-validation",
        help="Skip input validation (use with caution).",
    ),
]

BackupOption = Annotated[
    bool,
    typer.Option(
        "--backup",
        help="Create backup of existing files before overwriting.",
    ),
]

NoBackupOption = Annotated[
    bool,
    typer.Option(
        "--no-backup",
        help="Do not create backup of existing files.",
    ),
]


# =============================================================================
# Parameter Type Result Classes
# =============================================================================


class InputResult:
    """Result of input parameter processing."""

    def __init__(
        self,
        raw_value: str | Path | None,
        resolved_path: Path | None = None,
        is_stdin: bool = False,
        env_fallback_used: bool = False,
        data: str | bytes | None = None,
    ):
        self.raw_value = raw_value
        self.resolved_path = resolved_path
        self.is_stdin = is_stdin
        self.env_fallback_used = env_fallback_used
        self.data = data


class OutputResult:
    """Result of output parameter processing."""

    def __init__(
        self,
        raw_value: str | Path | None,
        resolved_path: Path | None = None,
        is_stdout: bool = False,
        smart_default_used: bool = False,
        template_vars: dict[str, str] | None = None,
    ):
        self.raw_value = raw_value
        self.resolved_path = resolved_path
        self.is_stdout = is_stdout
        self.smart_default_used = smart_default_used
        self.template_vars = template_vars or {}


class FormatResult:
    """Result of format parameter processing."""

    def __init__(
        self,
        format_type: str,
        is_json: bool = False,
        supports_rich: bool = True,
        legacy_format: bool = False,
    ):
        self.format_type = format_type
        self.is_json = is_json
        self.supports_rich = supports_rich
        self.legacy_format = legacy_format


class ValidationResult:
    """Result of parameter validation."""

    def __init__(
        self,
        is_valid: bool,
        error_message: str | None = None,
        warnings: list[str] | None = None,
        suggestions: list[str] | None = None,
    ):
        self.is_valid = is_valid
        self.error_message = error_message
        self.warnings = warnings or []
        self.suggestions = suggestions or []
