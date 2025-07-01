"""Library validate command for validating layouts directly from the library."""

from typing import Annotated

import typer

from glovebox.cli.decorators import handle_errors, with_metrics
from glovebox.cli.helpers.theme import Icons, get_icon_mode_from_context
from glovebox.config import create_user_config
from glovebox.library import create_library_service


validate_app = typer.Typer(help="Validate layouts from the library")


def complete_library_entries(incomplete: str) -> list[str]:
    """Tab completion for library entries (UUIDs and names)."""
    matches = []

    try:
        user_config = create_user_config()
        library_service = create_library_service(user_config._config)

        # Get local library entries
        local_entries = library_service.list_local_layouts()
        for entry in local_entries:
            if entry.uuid.startswith(incomplete):
                matches.append(entry.uuid)
            if entry.name.lower().startswith(incomplete.lower()):
                matches.append(entry.name)

        return matches[:20]  # Limit to 20 matches

    except Exception:
        return []


@validate_app.command("layout")
@handle_errors
@with_metrics("library_validate")
def validate_layout(
    ctx: typer.Context,
    source: Annotated[
        str,
        typer.Argument(
            help="UUID or name of layout in library to validate",
            autocompletion=complete_library_entries,
        ),
    ],
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            "-p",
            help="Keyboard profile for validation (e.g., 'glove80')",
        ),
    ] = None,
    strict: Annotated[
        bool,
        typer.Option("--strict", "-s", help="Enable strict validation mode"),
    ] = False,
    fix: Annotated[
        bool,
        typer.Option("--fix", "-f", help="Attempt to fix validation issues"),
    ] = False,
    format: Annotated[
        str,
        typer.Option(
            "--format",
            help="Output format for validation results",
        ),
    ] = "table",
) -> None:
    """Validate a layout from the library.

    This command resolves the library entry to its file path and validates
    it using the standard layout validation process, with additional library context.

    Examples:
        # Basic validation
        glovebox library validate "My Gaming Layout"

        # Validate with specific profile
        glovebox library validate work-layout --profile glove80

        # Strict validation with fix attempts
        glovebox library validate gaming-layout --strict --fix

        # JSON output for automation
        glovebox library validate work-layout --format json
    """
    icon_mode = get_icon_mode_from_context(ctx)

    try:
        # Create user config and library service
        user_config = create_user_config()
        library_service = create_library_service(user_config._config)

        # Find the source layout
        typer.echo(
            Icons.format_with_icon(
                "SEARCH", f"Finding layout in library: {source}", icon_mode
            )
        )

        # Try to find by UUID first, then by name
        source_entry = None
        local_entries = library_service.list_local_layouts()

        for entry in local_entries:
            if entry.uuid == source or entry.name == source:
                source_entry = entry
                break

        if not source_entry:
            typer.echo(
                Icons.format_with_icon(
                    "ERROR", f"Layout not found in library: {source}", icon_mode
                )
            )
            raise typer.Exit(1)

        # Check if source file exists
        if not source_entry.file_path.exists():
            typer.echo(
                Icons.format_with_icon(
                    "ERROR",
                    f"Source file not found: {source_entry.file_path}",
                    icon_mode,
                )
            )
            raise typer.Exit(1)

        # Show library source info (unless JSON format)
        if format.lower() != "json":
            typer.echo(
                Icons.format_with_icon(
                    "INFO", "Validating layout from library:", icon_mode
                )
            )
            typer.echo(f"   Name: {source_entry.name}")
            if source_entry.title:
                typer.echo(f"   Title: {source_entry.title}")
            if source_entry.creator:
                typer.echo(f"   Creator: {source_entry.creator}")
            typer.echo(f"   UUID: {source_entry.uuid}")
            typer.echo(f"   Source: {source_entry.source.value}")
            if source_entry.tags:
                typer.echo(f"   Tags: {', '.join(source_entry.tags)}")
            typer.echo(f"   File: {source_entry.file_path}")
            typer.echo()  # Empty line separator

        # Import the layout validate command
        from glovebox.cli.commands.layout.compilation import (
            validate_layout as layout_validate,
        )

        # Call the layout validate command with resolved path
        typer.echo(
            Icons.format_with_icon("VALIDATE", "Starting validation...", icon_mode)
        )

        # Create a new context for the layout command
        layout_ctx = typer.Context(layout_validate)
        layout_ctx.parent = ctx

        # Call the layout validate function directly
        layout_validate(
            ctx=layout_ctx,
            input_file=source_entry.file_path,
            profile=profile,
            strict=strict,
            fix=fix,
            format=format,
        )

    except Exception as e:
        typer.echo(
            Icons.format_with_icon("ERROR", f"Validation failed: {e}", icon_mode)
        )
        raise typer.Exit(1) from e


# Make the main command available as default
@validate_app.callback(invoke_without_command=True)
def validate_default(
    ctx: typer.Context,
    source: Annotated[
        str | None,
        typer.Argument(
            help="UUID or name of layout to validate",
            autocompletion=complete_library_entries,
        ),
    ] = None,
    profile: Annotated[str | None, typer.Option("--profile", "-p")] = None,
    strict: Annotated[bool, typer.Option("--strict", "-s")] = False,
    fix: Annotated[bool, typer.Option("--fix", "-f")] = False,
    format: Annotated[str, typer.Option("--format")] = "table",
) -> None:
    """Validate a layout from the library."""
    if ctx.invoked_subcommand is None:
        if source is None:
            typer.echo("Error: Missing required argument: source")
            raise typer.Exit(1)

        # Call the main validate command
        validate_layout(ctx, source, profile, strict, fix, format)
