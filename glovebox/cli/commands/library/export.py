"""Library export command for copying layouts to external locations."""

import json
from pathlib import Path
from typing import Annotated

import typer

from glovebox.cli.core.command_base import IOCommand
from glovebox.cli.decorators import handle_errors, with_metrics
from glovebox.cli.helpers.theme import Icons, get_icon_mode_from_context
from glovebox.config import create_user_config
from glovebox.library import FetchRequest, create_library_service
from glovebox.library.models import LibraryEntry


export_app = typer.Typer(help="Export layouts from the library")


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


class ExportLayoutCommand(IOCommand):
    """Command to export a layout from the library to a new location."""

    def execute(
        self,
        ctx: typer.Context,
        source: str,
        destination: Path,
        name: str | None,
        add_to_library: bool,
        force: bool,
    ) -> None:
        """Execute the export layout command."""

        icon_mode = get_icon_mode_from_context(ctx)

        try:
            # Create user config and library service
            from glovebox.config import create_user_config
            from glovebox.library import create_library_service

            user_config = create_user_config()
            library_service = create_library_service(user_config._config)

            # Find the source layout
            self.console.print_info(f"Finding layout: {source}")

            # Try to find by UUID first, then by name
            source_entry = None
            local_entries = library_service.list_local_layouts()

            for entry in local_entries:
                if entry.uuid == source or entry.name == source:
                    source_entry = entry
                    break

            if not source_entry:
                self.console.print_error(f"Layout not found in library: {source}")
                raise typer.Exit(1)

            # Check if source file exists
            if not source_entry.file_path.exists():
                self.console.print_error(
                    f"Source file not found: {source_entry.file_path}"
                )
                raise typer.Exit(1)

            # Read source layout data
            layout_data = self.load_json_input(str(source_entry.file_path))

            # Modify metadata if name provided
            if name:
                layout_data["config"] = layout_data.get("config", {})
                layout_data["config"]["title"] = name

            # Write to destination using IOCommand
            destination = destination.expanduser().resolve()
            self.write_output(
                layout_data,
                str(destination),
                format="json",
                force_overwrite=force,
                create_dirs=True,
            )

            self.console.print_success(
                f"Layout exported successfully to: {destination}"
            )

            # Show export details
            self.console.print_info(
                f"Source: {source_entry.name} ({source_entry.uuid})"
            )
            if source_entry.title:
                self.console.print_info(f"Original Title: {source_entry.title}")
            if name:
                self.console.print_info(f"New Title: {name}")
            self.console.print_info(f"Size: {destination.stat().st_size} bytes")

            # Add to library if requested
            if add_to_library:
                self.console.print_info("Adding exported layout to library...")

                # Create fetch request for the exported file
                from glovebox.library import FetchRequest

                fetch_request = FetchRequest(
                    source=str(destination),
                    name=name or f"{source_entry.name} (Export)",
                    force_overwrite=True,  # We just created it, so safe to overwrite
                )

                fetch_result = library_service.fetch_layout(fetch_request)

                if fetch_result.success and fetch_result.entry:
                    self.console.print_success("Added to library successfully!")
                    self.console.print_info(f"New UUID: {fetch_result.entry.uuid}")
                    self.console.print_info(
                        f"Library Path: {fetch_result.entry.file_path}"
                    )

                    # Show warnings if any
                    for warning in fetch_result.warnings:
                        self.console.print_warning(warning)
                else:
                    self.console.print_warning("Failed to add to library:")
                    for error in fetch_result.errors:
                        self.console.print_info(f"  {error}")

        except Exception as e:
            self.handle_service_error(e, "export layout")


@export_app.command("layout")
@handle_errors
@with_metrics("library_export")
def export_layout(
    ctx: typer.Context,
    source: Annotated[
        str,
        typer.Argument(
            help="UUID or name of layout in library to export",
            autocompletion=complete_library_entries,
        ),
    ],
    destination: Annotated[
        Path,
        typer.Argument(help="Output path for the exported layout file"),
    ],
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="Custom name for the exported layout"),
    ] = None,
    add_to_library: Annotated[
        bool,
        typer.Option(
            "--add-to-library",
            "-l",
            help="Add the exported layout back to the library",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite destination if it exists"),
    ] = False,
) -> None:
    """Export a layout from the library to a new location.

    This command copies an existing layout from your library to a specified
    location, optionally modifying metadata and adding it back to the library.

    Examples:
        # Export a layout by UUID to a new file
        glovebox library export 12345678-1234-1234-1234-123456789abc my-layout.json

        # Export with custom name and add back to library
        glovebox library export "My Gaming Layout" variation.json --name "Gaming V2" --add-to-library

        # Export layout
        glovebox library export work-layout ~/layouts/work-backup.json
    """
    command = ExportLayoutCommand()
    command.execute(ctx, source, destination, name, add_to_library, force)


# Make the main command available as default
@export_app.callback(invoke_without_command=True)
def export_default(
    ctx: typer.Context,
    source: Annotated[
        str | None,
        typer.Argument(
            help="UUID or name of layout to export",
            autocompletion=complete_library_entries,
        ),
    ] = None,
    destination: Annotated[
        Path | None, typer.Argument(help="Output path for exported layout")
    ] = None,
    name: Annotated[str | None, typer.Option("--name", "-n")] = None,
    add_to_library: Annotated[bool, typer.Option("--add-to-library", "-l")] = False,
    force: Annotated[bool, typer.Option("--force", "-f")] = False,
) -> None:
    """Export a layout from the library."""
    if ctx.invoked_subcommand is None:
        if source is None or destination is None:
            typer.echo("Error: Missing required arguments: source and destination")
            raise typer.Exit(1)

        # Call the main export command
        export_layout(ctx, source, destination, name, add_to_library, force)
