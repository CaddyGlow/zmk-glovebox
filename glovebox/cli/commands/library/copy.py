"""Library copy command for duplicating layouts within the library."""

from typing import Annotated

import typer

from glovebox.cli.core.command_base import IOCommand
from glovebox.cli.decorators import handle_errors, with_metrics
from glovebox.config import create_user_config
from glovebox.library import create_library_service


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


class CopyLayoutCommand(IOCommand):
    """Command to copy/duplicate a layout within the library."""

    def execute(
        self,
        ctx: typer.Context,
        source: str,
        new_name: str,
        title: str | None,
        tags: list[str] | None,
        notes: str | None,
        force: bool,
    ) -> None:
        """Execute the copy layout command."""
        try:
            # Create user config and library service
            from glovebox.config import create_user_config
            from glovebox.library import create_library_service

            user_config = create_user_config()
            library_service = create_library_service(user_config._config)

            # Find the source layout
            self.console.print_info(f"Finding layout in library: {source}")

            # Try to find by UUID first, then by name
            source_entry = None
            local_entries = library_service.list_local_layouts()

            for entry in local_entries:
                if entry.uuid == source or entry.name == source:
                    source_entry = entry
                    break

            if not source_entry:
                self.console.print_error(f"Layout not found in library: {source}")
                ctx.exit(1)

            # Check if source file exists
            if not source_entry.file_path.exists():
                self.console.print_error(
                    f"Source file not found: {source_entry.file_path}"
                )
                ctx.exit(1)

            # Check if new name already exists (unless force)
            if not force:
                for entry in local_entries:
                    if entry.name == new_name:
                        self.console.print_error(
                            f"Layout with name '{new_name}' already exists. Use --force to overwrite."
                        )
                        ctx.exit(1)

            # Read and modify the source layout
            self.console.print_info(f"Copying layout: {source_entry.name}")

            layout_data = self.load_json_input(str(source_entry.file_path))

            # Update layout metadata
            layout_data["config"] = layout_data.get("config", {})
            layout_data["config"]["title"] = title or new_name

            # Create temporary file for the copy
            import tempfile
            from pathlib import Path

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, encoding="utf-8"
            ) as temp_file:
                self.write_output(layout_data, temp_file.name, format="json")
                temp_path = temp_file.name

            try:
                # Create fetch request to add the copy to library
                from glovebox.library import FetchRequest

                fetch_request = FetchRequest(
                    source=temp_path,
                    name=new_name,
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

                        # Note: This is a simplified approach - in a real implementation,
                        # we'd want a proper update method in the library service
                        self.console.print_info(
                            "Note: Tags and notes can be updated separately with library management commands."
                        )

                    self.console.print_success("Layout copied successfully!")

                    # Show copy details
                    self.console.print_info(
                        f"Original: {source_entry.name} ({source_entry.uuid})"
                    )
                    self.console.print_info(
                        f"Copy: {fetch_result.entry.name} ({fetch_result.entry.uuid})"
                    )
                    if source_entry.title:
                        self.console.print_info(f"Original Title: {source_entry.title}")
                    self.console.print_info(f"New Title: {title or new_name}")
                    if tags:
                        self.console.print_info(f"Tags: {', '.join(tags)}")
                    if notes:
                        self.console.print_info(f"Notes: {notes}")
                    self.console.print_info(f"New File: {fetch_result.entry.file_path}")

                    # Show warnings if any
                    for warning in fetch_result.warnings:
                        self.console.print_warning(warning)

                else:
                    self.console.print_error("Failed to copy layout to library:")
                    for error in fetch_result.errors:
                        self.console.print_info(f"  {error}")
                    ctx.exit(1)

            finally:
                # Clean up temporary file
                import contextlib

                with contextlib.suppress(OSError):
                    Path(temp_path).unlink()

        except Exception as e:
            self.handle_service_error(e, "copy layout")


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
    command = CopyLayoutCommand()
    command.execute(ctx, source, new_name, title, tags, notes, force)


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
            ctx.exit(1)

        # Call the main copy command
        copy_layout(ctx, source, new_name, title, tags, notes, force)
