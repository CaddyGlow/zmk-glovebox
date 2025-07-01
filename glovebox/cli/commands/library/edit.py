"""Library edit command for editing layouts directly from the library."""

from typing import Annotated

import typer

from glovebox.cli.decorators import handle_errors, with_metrics
from glovebox.cli.helpers.theme import Icons, get_icon_mode_from_context
from glovebox.config import create_user_config
from glovebox.library import create_library_service


edit_app = typer.Typer(help="Edit layouts from the library")


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


@edit_app.command("layout")
@handle_errors
@with_metrics("library_edit")
def edit_layout(
    ctx: typer.Context,
    source: Annotated[
        str,
        typer.Argument(
            help="UUID or name of layout in library to edit",
            autocompletion=complete_library_entries,
        ),
    ],
    get: Annotated[
        list[str] | None,
        typer.Option(
            "--get",
            "-g",
            help="Get field values (can be used multiple times)",
        ),
    ] = None,
    set: Annotated[
        list[str] | None,
        typer.Option(
            "--set",
            "-s",
            help="Set field values using field=value format (can be used multiple times)",
        ),
    ] = None,
    add: Annotated[
        list[str] | None,
        typer.Option(
            "--add",
            "-a",
            help="Add values to list fields using field=value format (can be used multiple times)",
        ),
    ] = None,
    remove: Annotated[
        list[str] | None,
        typer.Option(
            "--remove",
            "-r",
            help="Remove values from list fields using field=value format (can be used multiple times)",
        ),
    ] = None,
    save: Annotated[
        bool,
        typer.Option("--save", help="Save changes to the file"),
    ] = False,
    no_save: Annotated[
        bool,
        typer.Option("--no-save", help="Do not save changes (preview only)"),
    ] = False,
    backup: Annotated[
        bool,
        typer.Option("--backup", "-b", help="Create backup before editing"),
    ] = True,
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format for get operations",
        ),
    ] = "table",
) -> None:
    """Edit a layout from the library.

    This command resolves the library entry to its file path and edits
    it using the standard layout editing process.

    Examples:
        # Get field values
        glovebox library edit "My Gaming Layout" --get config.title --get layers[0].name

        # Set field values
        glovebox library edit work-layout --set config.title="Work Layout v2" --save

        # Multiple operations
        glovebox library edit gaming-layout --get config.title --set config.author="Me" --save
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

        # Show library source info
        typer.echo(
            Icons.format_with_icon("INFO", "Editing layout from library:", icon_mode)
        )
        typer.echo(f"   Name: {source_entry.name}")
        if source_entry.title:
            typer.echo(f"   Title: {source_entry.title}")
        typer.echo(f"   UUID: {source_entry.uuid}")
        typer.echo(f"   File: {source_entry.file_path}")

        # Import the layout edit command
        from glovebox.cli.commands.layout.editor import edit_layout as layout_edit

        # Call the layout edit command with resolved path
        typer.echo(
            Icons.format_with_icon("EDIT", "Starting edit operation...", icon_mode)
        )

        # Create a new context for the layout command
        layout_ctx = typer.Context(layout_edit)
        layout_ctx.parent = ctx

        # Call the layout edit function directly
        layout_edit(
            ctx=layout_ctx,
            input_file=source_entry.file_path,
            get=get,
            set=set,
            add=add,
            remove=remove,
            save=save,
            no_save=no_save,
            backup=backup,
            format=format,
        )

        # Check if the layout title was changed and offer to update library metadata
        if save and set:
            for set_expr in set:
                if "config.title" in set_expr or "title" in set_expr:
                    typer.echo(
                        Icons.format_with_icon(
                            "INFO",
                            "Layout title may have been updated. Library metadata will be refreshed on next access.",
                            icon_mode,
                        )
                    )
                    break

    except Exception as e:
        typer.echo(
            Icons.format_with_icon("ERROR", f"Edit operation failed: {e}", icon_mode)
        )
        raise typer.Exit(1) from e


# Make the main command available as default
@edit_app.callback(invoke_without_command=True)
def edit_default(
    ctx: typer.Context,
    source: Annotated[
        str | None,
        typer.Argument(
            help="UUID or name of layout to edit",
            autocompletion=complete_library_entries,
        ),
    ] = None,
    get: Annotated[list[str] | None, typer.Option("--get", "-g")] = None,
    set: Annotated[list[str] | None, typer.Option("--set", "-s")] = None,
    add: Annotated[list[str] | None, typer.Option("--add", "-a")] = None,
    remove: Annotated[list[str] | None, typer.Option("--remove", "-r")] = None,
    save: Annotated[bool, typer.Option("--save")] = False,
    no_save: Annotated[bool, typer.Option("--no-save")] = False,
    backup: Annotated[bool, typer.Option("--backup", "-b")] = True,
    format: Annotated[str, typer.Option("--format", "-f")] = "table",
) -> None:
    """Edit a layout from the library."""
    if ctx.invoked_subcommand is None:
        if source is None:
            typer.echo("Error: Missing required argument: source")
            raise typer.Exit(1)

        # Call the main edit command
        edit_layout(ctx, source, get, set, add, remove, save, no_save, backup, format)
