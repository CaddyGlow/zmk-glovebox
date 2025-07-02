"""Essential cloud operations for syncing layouts with Glove80 cloud service."""

from __future__ import annotations

import builtins
import uuid as uuid_lib
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import typer

from glovebox.adapters import create_file_adapter
from glovebox.cli.helpers.library_resolver import resolve_parameter_value
from glovebox.cli.helpers.parameters import complete_json_files
from glovebox.layout.utils.json_operations import load_layout_file
from glovebox.moergo.client import create_moergo_client


# Create a typer app for cloud commands
cloud_app = typer.Typer(
    name="cloud",
    help="Essential cloud operations for Glove80 layouts",
    no_args_is_help=True,
)


@cloud_app.command()
def upload(
    ctx: typer.Context,
    layout_file: Annotated[
        str,
        typer.Argument(
            help="Layout file to upload or @library-name/uuid",
            autocompletion=complete_json_files,
        ),
    ],
    title: Annotated[str | None, typer.Option(help="Title for the layout")] = None,
    uuid: Annotated[
        str | None,
        typer.Option(
            help="Specify UUID for the layout (generates one if not provided)"
        ),
    ] = None,
    notes: Annotated[str | None, typer.Option(help="Add notes to the layout")] = None,
    tags: Annotated[
        builtins.list[str] | None, typer.Option(help="Add tags to the layout")
    ] = None,
    unlisted: Annotated[bool, typer.Option(help="Make the layout unlisted")] = False,
) -> None:
    """Upload a layout file to Glove80 cloud service."""
    from glovebox.cli.helpers.theme import get_themed_console

    console = get_themed_console(ctx=ctx)
    client = create_moergo_client()

    if not client.validate_authentication():
        console.print_error(
            "Authentication failed. Please run 'glovebox moergo login' first."
        )
        raise typer.Exit(1)

    # Resolve library reference if needed
    try:
        resolved_file = resolve_parameter_value(layout_file)
        if isinstance(resolved_file, Path):
            resolved_layout_file: Path | None = resolved_file
        else:
            resolved_layout_file = Path(resolved_file) if resolved_file else None

        if resolved_layout_file is None or not resolved_layout_file.exists():
            console.print_error(f"Layout file not found: {layout_file}")
            raise typer.Exit(1)
    except Exception as e:
        console.print_error(f"Error resolving layout file: {e}")
        raise typer.Exit(1) from e

    # Load the layout file
    try:
        file_adapter = create_file_adapter()
        layout_data = load_layout_file(resolved_layout_file, file_adapter)
    except Exception as e:
        console.print_error(f"Error loading layout file: {e}")
        raise typer.Exit(1) from e

    # Generate UUID if not provided
    layout_uuid = uuid or str(uuid_lib.uuid4())

    # Create layout metadata
    layout_meta = {
        "uuid": layout_uuid,
        "date": int(datetime.now().timestamp()),
        "creator": "glovebox-user",
        "parent_uuid": None,
        "firmware_api_version": "v25.05",
        "title": title or layout_data.title,
        "notes": notes or "",
        "tags": tags or [],
        "unlisted": unlisted,
        "deleted": False,
        "compiled": False,
        "searchable": not unlisted,
    }

    # Create the complete layout structure
    complete_layout = {
        "layout_meta": layout_meta,
        "config": layout_data.model_dump(mode="json", by_alias=True),
    }

    from glovebox.cli.helpers.theme import Icons

    icon = Icons.get_icon("UPLOAD", console.icon_mode)
    console.console.print(
        f"{icon} Uploading layout '{layout_meta['title']}' with UUID: {layout_uuid}",
        style="info",
    )

    try:
        response = client.save_layout(layout_uuid, complete_layout)
        console.print_success("Layout uploaded successfully!")
        link_icon = Icons.get_icon("LINK", console.icon_mode)
        console.console.print(f"{link_icon} UUID: {layout_uuid}")
        doc_icon = Icons.get_icon("DOCUMENT", console.icon_mode)
        console.console.print(f"{doc_icon} Title: {layout_meta['title']}")
    except Exception as e:
        console.print_error(f"Error uploading layout: {e}")
        raise typer.Exit(1) from e


@cloud_app.command()
def download(
    ctx: typer.Context,
    layout_uuid: Annotated[str, typer.Argument(help="UUID of the layout to download")],
    output: Annotated[
        str | None,
        typer.Option(
            "--output",
            "-o",
            help="Output file path for the downloaded layout. Use '-' for stdout. If not specified, generates a smart default filename.",
        ),
    ] = None,
) -> None:
    """Download a layout from Glove80 cloud service."""
    import sys

    from glovebox.cli.helpers.theme import Icons, get_themed_console
    from glovebox.utils.filename_generator import FileType, generate_default_filename
    from glovebox.utils.filename_helpers import extract_layout_dict_data

    console = get_themed_console(ctx=ctx)
    client = create_moergo_client()

    if not client.validate_authentication():
        console.print_error(
            "Authentication failed. Please run 'glovebox moergo login' first."
        )
        raise typer.Exit(1)

    try:
        layout = client.get_layout(layout_uuid)

        # Prepare the layout JSON content
        layout_json = layout.config.model_dump_json(by_alias=True, indent=2)

        # Handle output destination
        if output == "-":
            # Output to stdout
            sys.stdout.write(layout_json)
            sys.stdout.write("\n")
        else:
            # Determine output path
            if output is None:
                # Generate smart default filename using templates
                from glovebox.config import create_user_config

                user_config = create_user_config()
                layout_dict = layout.config.model_dump(by_alias=True)
                layout_template_data = extract_layout_dict_data(layout_dict)

                default_filename = generate_default_filename(
                    FileType.LAYOUT_JSON,
                    user_config._config.filename_templates,
                    layout_data=layout_template_data,
                    original_filename=f"{layout_uuid}.json",
                )
                output_file = Path(default_filename)
            else:
                output_file = Path(output)

            # Save the config part (the actual layout data)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(layout_json)
            save_icon = Icons.get_icon("SAVE", console.icon_mode)
            console.console.print(f"{save_icon} Downloaded to: {output_file}")

    except Exception as e:
        console.print_error(f"Error downloading layout: {e}")
        raise typer.Exit(1) from e


@cloud_app.command()
def list(
    ctx: typer.Context,
    tags: Annotated[
        builtins.list[str] | None,
        typer.Option("--tags", help="Filter by tags (can use multiple times)"),
    ] = None,
) -> None:
    """List all user's layouts from Glove80 cloud service."""
    from glovebox.cli.helpers.theme import Icons, get_themed_console

    console = get_themed_console(ctx=ctx)
    client = create_moergo_client()

    if not client.validate_authentication():
        console.print_error(
            "Authentication failed. Please run 'glovebox moergo login' first."
        )
        raise typer.Exit(1)

    try:
        layouts = client.list_user_layouts()

        if not layouts:
            mailbox_icon = Icons.get_icon("MAILBOX", console.icon_mode)
            console.console.print(f"{mailbox_icon} No layouts found.")
            return

        # Filter by tags if provided
        if tags:
            filtered_layouts = []
            for layout in layouts:
                try:
                    meta_response = client.get_layout_meta(layout["uuid"])
                    layout_meta = meta_response["layout_meta"]
                    layout_tags = set(layout_meta.get("tags", []))
                    if any(tag in layout_tags for tag in tags):
                        filtered_layouts.append(layout)
                except Exception:
                    continue
            layouts = filtered_layouts

        doc_icon = Icons.get_icon("DOCUMENT", console.icon_mode)
        console.console.print(f"{doc_icon} Found {len(layouts)} layouts:")
        console.console.print()

        for layout in layouts:
            link_icon = Icons.get_icon("LINK", console.icon_mode)
            console.console.print(f"   {link_icon} {layout['uuid']}")

        console.console.print()
        console.print_info(
            "Use 'glovebox cloud download <uuid> [--output <file>]' to download a layout"
        )

    except Exception as e:
        console.print_error(f"Error listing layouts: {e}")
        raise typer.Exit(1) from e


@cloud_app.command()
def browse(
    ctx: typer.Context,
    tags: Annotated[
        builtins.list[str] | None,
        typer.Option("--tags", help="Filter by tags (can use multiple times)"),
    ] = None,
    limit: Annotated[
        int, typer.Option("--limit", help="Limit number of layouts to show")
    ] = 20,
) -> None:
    """Browse public layouts from Glove80 community."""
    from glovebox.cli.helpers.theme import Icons, get_themed_console

    console = get_themed_console(ctx=ctx)
    client = create_moergo_client()

    if not client.validate_authentication():
        console.print_error(
            "Authentication failed. Please run 'glovebox moergo login' first."
        )
        raise typer.Exit(1)

    try:
        globe_icon = Icons.get_icon("GLOBE", console.icon_mode)
        if tags:
            console.console.print(
                f"{globe_icon} Browsing public layouts with tags: {', '.join(tags)}"
            )
        else:
            console.console.print(
                f"{globe_icon} Browsing public layouts from Glove80 community..."
            )

        public_uuids = client.list_public_layouts(tags=tags)

        doc_icon = Icons.get_icon("DOCUMENT", console.icon_mode)
        console.console.print(
            f"{doc_icon} Found {len(public_uuids)} public layouts (showing {min(limit, len(public_uuids))}):"
        )
        console.console.print()

        # Show list with basic info
        for i, uuid in enumerate(public_uuids[:limit]):
            try:
                meta_response = client.get_layout_meta(uuid)
                layout_meta = meta_response["layout_meta"]

                status_icon = (
                    Icons.get_icon("SUCCESS", console.icon_mode)
                    if layout_meta["compiled"]
                    else Icons.get_icon("DOCUMENT", console.icon_mode)
                )
                console.console.print(
                    f"{i + 1:3d}. {status_icon} {layout_meta['title']}"
                )
                link_icon = Icons.get_icon("LINK", console.icon_mode)
                console.console.print(f"     {link_icon} UUID: {uuid}")
                if layout_meta["tags"]:
                    tag_icon = Icons.get_icon("TAG", console.icon_mode)
                    console.console.print(
                        f"     {tag_icon} Tags: {', '.join(layout_meta['tags'][:3])}"
                    )
                console.console.print()
            except Exception:
                link_icon = Icons.get_icon("LINK", console.icon_mode)
                console.console.print(f"{i + 1:3d}. {link_icon} {uuid}")
                console.console.print()

        console.print_info(
            "Use 'glovebox cloud download <uuid> [--output <file>]' to download a layout"
        )

    except Exception as e:
        console.print_error(f"Error browsing public layouts: {e}")
        raise typer.Exit(1) from e


@cloud_app.command()
def delete(
    ctx: typer.Context,
    layout_uuid: Annotated[str, typer.Argument(help="UUID of the layout to delete")],
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Skip confirmation prompt")
    ] = False,
) -> None:
    """Delete a layout from Glove80 cloud service."""
    from glovebox.cli.helpers.theme import Icons, get_themed_console

    console = get_themed_console(ctx=ctx)
    client = create_moergo_client()

    if not client.validate_authentication():
        console.print_error(
            "Authentication failed. Please run 'glovebox moergo login' first."
        )
        raise typer.Exit(1)

    # Get layout info first
    try:
        layout = client.get_layout(layout_uuid)
        doc_icon = Icons.get_icon("DOCUMENT", console.icon_mode)
        console.console.print(
            f"{doc_icon} Layout to delete: {layout.layout_meta.title}"
        )
        user_icon = Icons.get_icon("USER", console.icon_mode)
        console.console.print(f"{user_icon} Creator: {layout.layout_meta.creator}")
        calendar_icon = Icons.get_icon("CALENDAR", console.icon_mode)
        console.console.print(
            f"{calendar_icon} Created: {layout.layout_meta.created_datetime}"
        )
    except Exception as e:
        console.print_error(f"Error fetching layout: {e}")
        raise typer.Exit(1) from e

    # Confirmation
    if not force:
        warning_icon = Icons.get_icon("WARNING", console.icon_mode)
        delete_confirm = typer.confirm(
            f"{warning_icon} Are you sure you want to delete '{layout.layout_meta.title}'?"
        )
        if not delete_confirm:
            console.print_error("Deletion cancelled")
            return

    # Delete the layout
    try:
        success = client.delete_layout(layout_uuid)
        if success:
            console.print_success("Layout deleted successfully!")
        else:
            console.print_error("Failed to delete layout")
            raise typer.Exit(1)
    except Exception as e:
        console.print_error(f"Error deleting layout: {e}")
        raise typer.Exit(1) from e


def register_commands(app: typer.Typer) -> None:
    """Register cloud commands with the main app."""
    app.add_typer(cloud_app, name="cloud")
