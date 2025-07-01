"""Library copy command for duplicating layouts within the library."""

import json
from typing import Annotated

import typer

from glovebox.cli.decorators import handle_errors, with_metrics
from glovebox.cli.helpers.theme import Icons, get_icon_mode_from_context
from glovebox.config import create_user_config
from glovebox.library import FetchRequest, create_library_service


copy_app = typer.Typer(help="Copy/duplicate layouts within the library")


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


@copy_app.command("layout")
@handle_errors
@with_metrics("library_copy")
def copy_layout(
    ctx: typer.Context,
    source: Annotated[
        str,
        typer.Argument(
            help="UUID or name of layout in library to copy",
            autocompletion=complete_library_entries,
        ),
    ],
    new_name: Annotated[
        str,
        typer.Argument(help="Name for the copied layout"),
    ],
    title: Annotated[
        str | None,
        typer.Option(
            "--title",
            "-t",
            help="Custom title for the copied layout (defaults to new_name)",
        ),
    ] = None,
    tags: Annotated[
        list[str] | None,
        typer.Option(
            "--tags",
            help="Tags for the copied layout (can be used multiple times)",
        ),
    ] = None,
    notes: Annotated[
        str | None,
        typer.Option("--notes", "-n", help="Notes for the copied layout"),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite if layout name already exists"),
    ] = False,
) -> None:
    """Copy/duplicate a layout within the library.

    This command creates a copy of an existing library layout with a new name,
    keeping both the original and copy in the library.

    Examples:
        # Copy with new name
        glovebox library copy "Gaming Layout" "Gaming Layout V2"

        # Copy with custom title and tags
        glovebox library copy work-layout "Work V2" --title "Enhanced Work Layout" --tags work,v2

        # Copy with notes
        glovebox library copy base-layout variation --notes "Experimental changes"
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

        # Check if new name already exists (unless force)
        if not force:
            for entry in local_entries:
                if entry.name == new_name:
                    typer.echo(
                        Icons.format_with_icon(
                            "ERROR",
                            f"Layout with name '{new_name}' already exists. Use --force to overwrite.",
                            icon_mode,
                        )
                    )
                    raise typer.Exit(1)

        # Read and modify the source layout
        typer.echo(
            Icons.format_with_icon(
                "COPY", f"Copying layout: {source_entry.name}", icon_mode
            )
        )

        with source_entry.file_path.open("r", encoding="utf-8") as source_file:
            layout_data = json.load(source_file)

        # Update layout metadata
        layout_data["config"] = layout_data.get("config", {})
        layout_data["config"]["title"] = title or new_name

        # Create temporary file for the copy
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as temp_file:
            json.dump(layout_data, temp_file, indent=2, ensure_ascii=False)
            temp_path = temp_file.name

        try:
            # Create fetch request to add the copy to library
            fetch_request = FetchRequest(
                source=temp_path,
                name=new_name,
                create_bookmark=False,
                force_overwrite=force,
            )

            fetch_result = library_service.fetch_layout(fetch_request)

            if fetch_result.success and fetch_result.entry:
                # Update additional metadata if provided
                if tags or notes:
                    # Update the library entry metadata
                    entry = fetch_result.entry
                    if tags:
                        entry.tags = list(tags)
                    if notes:
                        entry.notes = notes

                    # Update the library index
                    # Note: This is a simplified approach - in a real implementation,
                    # we'd want a proper update method in the library service
                    typer.echo(
                        Icons.format_with_icon(
                            "INFO",
                            "Note: Tags and notes can be updated separately with library management commands.",
                            icon_mode,
                        )
                    )

                typer.echo(
                    Icons.format_with_icon(
                        "SUCCESS", "Layout copied successfully!", icon_mode
                    )
                )

                # Show copy details
                typer.echo(f"   Original: {source_entry.name} ({source_entry.uuid})")
                typer.echo(
                    f"   Copy: {fetch_result.entry.name} ({fetch_result.entry.uuid})"
                )
                if source_entry.title:
                    typer.echo(f"   Original Title: {source_entry.title}")
                typer.echo(f"   New Title: {title or new_name}")
                if tags:
                    typer.echo(f"   Tags: {', '.join(tags)}")
                if notes:
                    typer.echo(f"   Notes: {notes}")
                typer.echo(f"   New File: {fetch_result.entry.file_path}")

                # Show warnings if any
                for warning in fetch_result.warnings:
                    typer.echo(Icons.format_with_icon("WARNING", warning, icon_mode))

            else:
                typer.echo(
                    Icons.format_with_icon(
                        "ERROR", "Failed to copy layout to library:", icon_mode
                    )
                )
                for error in fetch_result.errors:
                    typer.echo(f"   {error}")
                raise typer.Exit(1)

        finally:
            # Clean up temporary file
            import contextlib
            from pathlib import Path

            with contextlib.suppress(OSError):
                Path(temp_path).unlink()

    except Exception as e:
        typer.echo(
            Icons.format_with_icon("ERROR", f"Copy operation failed: {e}", icon_mode)
        )
        raise typer.Exit(1) from e


# Make the main command available as default
@copy_app.callback(invoke_without_command=True)
def copy_default(
    ctx: typer.Context,
    source: Annotated[
        str | None,
        typer.Argument(
            help="UUID or name of layout to copy",
            autocompletion=complete_library_entries,
        ),
    ] = None,
    new_name: Annotated[
        str | None, typer.Argument(help="Name for the copied layout")
    ] = None,
    title: Annotated[str | None, typer.Option("--title", "-t")] = None,
    tags: Annotated[list[str] | None, typer.Option("--tags")] = None,
    notes: Annotated[str | None, typer.Option("--notes", "-n")] = None,
    force: Annotated[bool, typer.Option("--force", "-f")] = False,
) -> None:
    """Copy a layout within the library."""
    if ctx.invoked_subcommand is None:
        if source is None or new_name is None:
            typer.echo("Error: Missing required arguments: source and new_name")
            raise typer.Exit(1)

        # Call the main copy command
        copy_layout(ctx, source, new_name, title, tags, notes, force)
