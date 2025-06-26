"""Essential cloud operations for syncing layouts with Glove80 cloud service."""

from __future__ import annotations

import builtins
import uuid as uuid_lib
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import typer

from glovebox.adapters import create_file_adapter
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
    layout_file: Annotated[
        Path, typer.Argument(help="Layout file to upload", exists=True)
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
    from glovebox.cli.helpers.theme import Icons, get_icon_mode_from_context

    client = create_moergo_client()

    if not client.validate_authentication():
        typer.echo(
            Icons.format_with_icon(
                "ERROR",
                "Authentication failed. Please run 'glovebox moergo login' first.",
                "emoji",
            )
        )
        raise typer.Exit(1)

    # Load the layout file
    try:
        file_adapter = create_file_adapter()
        layout_data = load_layout_file(layout_file, file_adapter)
    except Exception as e:
        typer.echo(
            Icons.format_with_icon("ERROR", f"Error loading layout file: {e}", "emoji")
        )
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

    typer.echo(
        Icons.format_with_icon(
            "UPLOAD",
            f"Uploading layout '{layout_meta['title']}' with UUID: {layout_uuid}",
            "emoji",
        )
    )

    try:
        response = client.save_layout(layout_uuid, complete_layout)
        typer.echo(
            Icons.format_with_icon("SUCCESS", "Layout uploaded successfully!", "emoji")
        )
        typer.echo(Icons.format_with_icon("LINK", f"UUID: {layout_uuid}", "emoji"))
        typer.echo(
            Icons.format_with_icon(
                "DOCUMENT", f"Title: {layout_meta['title']}", "emoji"
            )
        )
    except Exception as e:
        typer.echo(
            Icons.format_with_icon("ERROR", f"Error uploading layout: {e}", "emoji")
        )
        raise typer.Exit(1) from e


@cloud_app.command()
def download(
    layout_uuid: Annotated[str, typer.Argument(help="UUID of the layout to download")],
    output_file: Annotated[
        Path, typer.Argument(help="Output file path for the downloaded layout")
    ],
) -> None:
    """Download a layout from Glove80 cloud service."""
    from glovebox.cli.helpers.theme import Icons, get_icon_mode_from_context

    client = create_moergo_client()

    if not client.validate_authentication():
        typer.echo(
            Icons.format_with_icon(
                "ERROR",
                "Authentication failed. Please run 'glovebox moergo login' first.",
                "emoji",
            )
        )
        raise typer.Exit(1)

    try:
        layout = client.get_layout(layout_uuid)

        # Save the config part (the actual layout data)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(layout.config.model_dump_json(by_alias=True, indent=2))
        typer.echo(
            Icons.format_with_icon("SAVE", f"Downloaded to: {output_file}", "emoji")
        )

    except Exception as e:
        typer.echo(
            Icons.format_with_icon("ERROR", f"Error downloading layout: {e}", "emoji")
        )
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
    from glovebox.cli.app import AppContext
    from glovebox.cli.helpers.theme import Icons, get_icon_mode_from_context

    icon_mode = get_icon_mode_from_context(ctx)

    client = create_moergo_client()

    if not client.validate_authentication():
        typer.echo(
            Icons.format_with_icon(
                "ERROR",
                "Authentication failed. Please run 'glovebox moergo login' first.",
                icon_mode,
            )
        )
        raise typer.Exit(1)

    try:
        layouts = client.list_user_layouts()

        if not layouts:
            typer.echo(
                Icons.format_with_icon("MAILBOX", "No layouts found.", icon_mode)
            )
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

        typer.echo(
            Icons.format_with_icon(
                "DOCUMENT", f"Found {len(layouts)} layouts:", icon_mode
            )
        )
        typer.echo()

        for layout in layouts:
            typer.echo(f"   {Icons.get_icon('LINK', icon_mode)} {layout['uuid']}")

        typer.echo()
        typer.echo(
            Icons.format_with_icon(
                "INFO",
                "Use 'glovebox cloud download <uuid> <output.json>' to download a layout",
                icon_mode,
            )
        )

    except Exception as e:
        typer.echo(
            Icons.format_with_icon("ERROR", f"Error listing layouts: {e}", icon_mode)
        )
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
    from glovebox.cli.app import AppContext
    from glovebox.cli.helpers.theme import Icons, get_icon_mode_from_context

    icon_mode = get_icon_mode_from_context(ctx)

    client = create_moergo_client()

    if not client.validate_authentication():
        typer.echo(
            Icons.format_with_icon(
                "ERROR",
                "Authentication failed. Please run 'glovebox moergo login' first.",
                icon_mode,
            )
        )
        raise typer.Exit(1)

    try:
        if tags:
            typer.echo(
                Icons.format_with_icon(
                    "GLOBE",
                    f"Browsing public layouts with tags: {', '.join(tags)}",
                    icon_mode,
                )
            )
        else:
            typer.echo(
                Icons.format_with_icon(
                    "GLOBE",
                    "Browsing public layouts from Glove80 community...",
                    icon_mode,
                )
            )

        public_uuids = client.list_public_layouts(tags=tags)

        typer.echo(
            Icons.format_with_icon(
                "DOCUMENT",
                f"Found {len(public_uuids)} public layouts (showing {min(limit, len(public_uuids))}):",
                icon_mode,
            )
        )
        typer.echo()

        # Show list with basic info
        for i, uuid in enumerate(public_uuids[:limit]):
            try:
                meta_response = client.get_layout_meta(uuid)
                layout_meta = meta_response["layout_meta"]

                status_icon = (
                    Icons.get_icon("SUCCESS", icon_mode)
                    if layout_meta["compiled"]
                    else Icons.get_icon("DOCUMENT", icon_mode)
                )
                typer.echo(f"{i + 1:3d}. {status_icon} {layout_meta['title']}")
                typer.echo(f"     {Icons.get_icon('LINK', icon_mode)} UUID: {uuid}")
                if layout_meta["tags"]:
                    typer.echo(
                        f"     {Icons.get_icon('TAG', icon_mode)} Tags: {', '.join(layout_meta['tags'][:3])}"
                    )
                typer.echo()
            except Exception:
                typer.echo(f"{i + 1:3d}. {Icons.get_icon('LINK', icon_mode)} {uuid}")
                typer.echo()

        typer.echo(
            Icons.format_with_icon(
                "INFO",
                "Use 'glovebox cloud download <uuid> <output.json>' to download a layout",
                icon_mode,
            )
        )

    except Exception as e:
        typer.echo(
            Icons.format_with_icon(
                "ERROR", f"Error browsing public layouts: {e}", icon_mode
            )
        )
        raise typer.Exit(1) from e


@cloud_app.command()
def delete(
    layout_uuid: Annotated[str, typer.Argument(help="UUID of the layout to delete")],
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Skip confirmation prompt")
    ] = False,
) -> None:
    """Delete a layout from Glove80 cloud service."""
    from glovebox.cli.helpers.theme import Icons, get_icon_mode_from_context

    client = create_moergo_client()

    if not client.validate_authentication():
        typer.echo(
            Icons.format_with_icon(
                "ERROR",
                "Authentication failed. Please run 'glovebox moergo login' first.",
                "emoji",
            )
        )
        raise typer.Exit(1)

    # Get layout info first
    try:
        layout = client.get_layout(layout_uuid)
        typer.echo(
            Icons.format_with_icon(
                "DOCUMENT", f"Layout to delete: {layout.layout_meta.title}", "emoji"
            )
        )
        typer.echo(
            Icons.format_with_icon(
                "USER", f"Creator: {layout.layout_meta.creator}", "emoji"
            )
        )
        typer.echo(
            Icons.format_with_icon(
                "CALENDAR", f"Created: {layout.layout_meta.created_datetime}", "emoji"
            )
        )
    except Exception as e:
        typer.echo(
            Icons.format_with_icon("ERROR", f"Error fetching layout: {e}", "emoji")
        )
        raise typer.Exit(1) from e

    # Confirmation
    if not force:
        delete_confirm = typer.confirm(
            f"{Icons.get_icon('WARNING', 'emoji')} Are you sure you want to delete '{layout.layout_meta.title}'?"
        )
        if not delete_confirm:
            typer.echo(Icons.format_with_icon("ERROR", "Deletion cancelled", "emoji"))
            return

    # Delete the layout
    try:
        success = client.delete_layout(layout_uuid)
        if success:
            typer.echo(
                Icons.format_with_icon(
                    "SUCCESS", "Layout deleted successfully!", "emoji"
                )
            )
        else:
            typer.echo(
                Icons.format_with_icon("ERROR", "Failed to delete layout", "emoji")
            )
            raise typer.Exit(1)
    except Exception as e:
        typer.echo(
            Icons.format_with_icon("ERROR", f"Error deleting layout: {e}", "emoji")
        )
        raise typer.Exit(1) from e


def register_commands(app: typer.Typer) -> None:
    """Register cloud commands with the main app."""
    app.add_typer(cloud_app, name="cloud")
