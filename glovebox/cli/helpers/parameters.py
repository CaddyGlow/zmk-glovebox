"""Common CLI parameter definitions for reuse across commands."""

from typing import Annotated

import typer


# Standard profile parameter that can be reused across all commands
ProfileOption = Annotated[
    str | None,
    typer.Option(
        "--profile",
        "-p",
        help="Profile to use (e.g., 'glove80/v25.05'). Uses user config default if not specified.",
    ),
]


# Standard output format parameter for unified output formatting
OutputFormatOption = Annotated[
    str,
    typer.Option(
        "--output-format",
        help="Output format: text|json|markdown|table (default: text)",
    ),
]


# Note: For more complex parameter variations, create new Annotated types
# following the same pattern as ProfileOption above.
