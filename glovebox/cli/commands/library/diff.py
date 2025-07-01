"""Library diff command for comparing layouts directly from the library."""

from typing import Annotated

import typer

from glovebox.cli.decorators import handle_errors, with_metrics
from glovebox.cli.helpers.theme import Icons, get_icon_mode_from_context
from glovebox.config import create_user_config
from glovebox.library import create_library_service


diff_app = typer.Typer(help="Compare layouts from the library")


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


@diff_app.command("layouts")
@handle_errors
@with_metrics("library_diff")
def diff_layouts(
    ctx: typer.Context,
    source1: Annotated[
        str,
        typer.Argument(
            help="UUID or name of first layout in library",
            autocompletion=complete_library_entries,
        ),
    ],
    source2: Annotated[
        str,
        typer.Argument(
            help="UUID or name of second layout in library",
            autocompletion=complete_library_entries,
        ),
    ],
    include_dtsi: Annotated[
        bool,
        typer.Option("--include-dtsi", help="Include DTSI content comparison"),
    ] = False,
    json: Annotated[
        bool,
        typer.Option("--json", help="Output in JSON format"),
    ] = False,
    unified: Annotated[
        int | None,
        typer.Option(
            "--unified",
            "-u",
            help="Number of unified context lines to show",
        ),
    ] = None,
    ignore_whitespace: Annotated[
        bool,
        typer.Option("--ignore-whitespace", "-w", help="Ignore whitespace differences"),
    ] = False,
    summary: Annotated[
        bool,
        typer.Option("--summary", "-s", help="Show only summary of differences"),
    ] = False,
) -> None:
    """Compare two layouts from the library.

    This command resolves both library entries to their file paths and compares
    them using the standard layout diff process, with additional library metadata.

    Examples:
        # Basic diff between two layouts
        glovebox library diff "Gaming Layout" "Work Layout"

        # Include DTSI comparison
        glovebox library diff layout1-uuid layout2-uuid --include-dtsi

        # JSON output for automation
        glovebox library diff "My Layout" "Other Layout" --json

        # Summary only
        glovebox library diff layout1 layout2 --summary
    """
    icon_mode = get_icon_mode_from_context(ctx)

    try:
        # Create user config and library service
        user_config = create_user_config()
        library_service = create_library_service(user_config._config)

        # Find both source layouts
        typer.echo(
            Icons.format_with_icon("SEARCH", "Finding layouts in library...", icon_mode)
        )

        # Get all local entries once
        local_entries = library_service.list_local_layouts()

        # Find source1
        source1_entry = None
        for entry in local_entries:
            if entry.uuid == source1 or entry.name == source1:
                source1_entry = entry
                break

        if not source1_entry:
            typer.echo(
                Icons.format_with_icon(
                    "ERROR", f"First layout not found in library: {source1}", icon_mode
                )
            )
            raise typer.Exit(1)

        # Find source2
        source2_entry = None
        for entry in local_entries:
            if entry.uuid == source2 or entry.name == source2:
                source2_entry = entry
                break

        if not source2_entry:
            typer.echo(
                Icons.format_with_icon(
                    "ERROR", f"Second layout not found in library: {source2}", icon_mode
                )
            )
            raise typer.Exit(1)

        # Check if source files exist
        if not source1_entry.file_path.exists():
            typer.echo(
                Icons.format_with_icon(
                    "ERROR",
                    f"First source file not found: {source1_entry.file_path}",
                    icon_mode,
                )
            )
            raise typer.Exit(1)

        if not source2_entry.file_path.exists():
            typer.echo(
                Icons.format_with_icon(
                    "ERROR",
                    f"Second source file not found: {source2_entry.file_path}",
                    icon_mode,
                )
            )
            raise typer.Exit(1)

        # Show library source info (unless JSON format)
        if not json:
            typer.echo(
                Icons.format_with_icon(
                    "INFO", "Comparing layouts from library:", icon_mode
                )
            )
            typer.echo("   First Layout:")
            typer.echo(f"     Name: {source1_entry.name}")
            if source1_entry.title:
                typer.echo(f"     Title: {source1_entry.title}")
            if source1_entry.creator:
                typer.echo(f"     Creator: {source1_entry.creator}")
            typer.echo(f"     UUID: {source1_entry.uuid}")
            typer.echo(f"     Source: {source1_entry.source.value}")
            if source1_entry.tags:
                typer.echo(f"     Tags: {', '.join(source1_entry.tags)}")

            typer.echo("   Second Layout:")
            typer.echo(f"     Name: {source2_entry.name}")
            if source2_entry.title:
                typer.echo(f"     Title: {source2_entry.title}")
            if source2_entry.creator:
                typer.echo(f"     Creator: {source2_entry.creator}")
            typer.echo(f"     UUID: {source2_entry.uuid}")
            typer.echo(f"     Source: {source2_entry.source.value}")
            if source2_entry.tags:
                typer.echo(f"     Tags: {', '.join(source2_entry.tags)}")
            typer.echo()  # Empty line separator

        # Import the layout diff command
        from glovebox.cli.commands.layout.comparison import diff as layout_diff

        # Call the layout diff command with resolved paths
        typer.echo(
            Icons.format_with_icon("DIFF", "Comparing layout content...", icon_mode)
        )

        # Create a new context for the layout command
        layout_ctx = typer.Context(layout_diff)
        layout_ctx.parent = ctx

        # Call the layout diff function directly
        # Note: layout diff has different parameter order (layout2, layout1)
        layout_diff(
            ctx=layout_ctx,
            layout2=source2_entry.file_path,  # Second layout
            layout1=source1_entry.file_path,  # First layout
            output_format="json" if json else "text",
            detailed=not summary,  # Invert summary for detailed
            include_dtsi=include_dtsi,
        )

    except Exception as e:
        typer.echo(
            Icons.format_with_icon("ERROR", f"Diff operation failed: {e}", icon_mode)
        )
        raise typer.Exit(1) from e


# Make the main command available as default
@diff_app.callback(invoke_without_command=True)
def diff_default(
    ctx: typer.Context,
    source1: Annotated[
        str | None,
        typer.Argument(
            help="UUID or name of first layout",
            autocompletion=complete_library_entries,
        ),
    ] = None,
    source2: Annotated[
        str | None,
        typer.Argument(
            help="UUID or name of second layout",
            autocompletion=complete_library_entries,
        ),
    ] = None,
    include_dtsi: Annotated[bool, typer.Option("--include-dtsi")] = False,
    json: Annotated[bool, typer.Option("--json")] = False,
    unified: Annotated[int | None, typer.Option("--unified", "-u")] = None,
    ignore_whitespace: Annotated[
        bool, typer.Option("--ignore-whitespace", "-w")
    ] = False,
    summary: Annotated[bool, typer.Option("--summary", "-s")] = False,
) -> None:
    """Compare two layouts from the library."""
    if ctx.invoked_subcommand is None:
        if source1 is None or source2 is None:
            typer.echo("Error: Missing required arguments: source1 and source2")
            raise typer.Exit(1)

        # Call the main diff command
        diff_layouts(
            ctx,
            source1,
            source2,
            include_dtsi,
            json,
            unified,
            ignore_whitespace,
            summary,
        )
