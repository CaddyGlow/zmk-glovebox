"""CLI command for syncing layouts with Glove80 cloud service."""

import uuid as uuid_lib
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import typer

from glovebox.layout.utils.json_operations import load_layout_file
from glovebox.moergo.client import create_moergo_client
from glovebox.moergo.versioning import create_layout_versioning


# Create a typer app for glove80 commands
glove80_group = typer.Typer(
    name="glove80",
    help="Sync layouts with Glove80 cloud service",
    no_args_is_help=True,
)


@glove80_group.command()
def upload(
    layout_file: Annotated[
        Path, typer.Argument(help="Layout file to upload", exists=True)
    ],
    uuid: Annotated[
        str | None,
        typer.Option(
            help="Specify UUID for the layout (generates one if not provided)"
        ),
    ] = None,
    title: Annotated[str | None, typer.Option(help="Override the layout title")] = None,
    notes: Annotated[str | None, typer.Option(help="Add notes to the layout")] = None,
    tags: Annotated[
        list[str] | None, typer.Option(help="Add tags to the layout")
    ] = None,
    unlisted: Annotated[bool, typer.Option(help="Make the layout unlisted")] = False,
) -> None:
    """Upload a layout file to Glove80 cloud service."""

    client = create_moergo_client()

    if not client.validate_authentication():
        typer.echo(
            "❌ Authentication failed. Please run 'glovebox moergo login' first."
        )
        raise typer.Exit(1) from None

    # Load the layout file
    try:
        layout_data = load_layout_file(layout_file)
    except Exception as e:
        typer.echo(f"❌ Error loading layout file: {e}")
        raise typer.Exit(1) from None

    # Generate UUID if not provided
    layout_uuid = uuid or str(uuid_lib.uuid4())

    # Create layout metadata
    layout_meta = {
        "uuid": layout_uuid,
        "date": int(datetime.now().timestamp()),
        "creator": "glovebox-user",  # Could be made configurable
        "parent_uuid": None,
        "firmware_api_version": "v25.05",  # Could be made configurable
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

    typer.echo(f"📤 Uploading layout '{layout_meta['title']}' with UUID: {layout_uuid}")

    try:
        response = client.save_layout(layout_uuid, complete_layout)
        typer.echo("✅ Layout uploaded successfully!")
        typer.echo(f"🔗 UUID: {layout_uuid}")
        typer.echo(f"📝 Title: {layout_meta['title']}")
        if response.get("status") == "no_content":
            typer.echo("📊 Status: Upload completed")
    except Exception as e:
        typer.echo(f"❌ Error uploading layout: {e}")
        raise typer.Exit(1) from None


@glove80_group.command()
def update(
    layout_uuid: Annotated[str, typer.Argument(help="UUID of the layout to update")],
    layout_file: Annotated[
        Path, typer.Argument(help="Layout file with new content", exists=True)
    ],
    title: Annotated[str | None, typer.Option(help="Update the layout title")] = None,
    notes: Annotated[str | None, typer.Option(help="Update the layout notes")] = None,
    add_tag: Annotated[
        list[str] | None, typer.Option(help="Add tags to the layout")
    ] = None,
    unlisted: Annotated[
        bool | None, typer.Option(help="Update unlisted status")
    ] = None,
) -> None:
    """Update an existing layout in Glove80 cloud service."""

    client = create_moergo_client()

    if not client.validate_authentication():
        typer.echo(
            "❌ Authentication failed. Please run 'glovebox moergo login' first."
        )
        raise typer.Exit(1) from None

    # Get existing layout first
    try:
        existing_layout = client.get_layout(layout_uuid)
        typer.echo(f"📥 Found existing layout: {existing_layout.layout_meta.title}")
    except Exception as e:
        typer.echo(f"❌ Error fetching existing layout: {e}")
        raise typer.Exit(1) from None

    # Load the new layout file
    try:
        layout_data = load_layout_file(layout_file)
    except Exception as e:
        typer.echo(f"❌ Error loading layout file: {e}")
        raise typer.Exit(1) from None

    # Update metadata
    updated_meta = existing_layout.layout_meta.model_dump()
    updated_meta["date"] = int(datetime.now().timestamp())

    if title:
        updated_meta["title"] = title
    if notes is not None:
        updated_meta["notes"] = notes
    if add_tag:
        existing_tags = set(updated_meta.get("tags", []))
        existing_tags.update(add_tag)
        updated_meta["tags"] = list(existing_tags)
    if unlisted is not None:
        updated_meta["unlisted"] = unlisted
        updated_meta["searchable"] = not unlisted

    # Create the complete updated layout structure
    updated_layout = {
        "layout_meta": updated_meta,
        "config": layout_data.model_dump(mode="json", by_alias=True),
    }

    typer.echo(f"📤 Updating layout '{updated_meta['title']}' with UUID: {layout_uuid}")

    try:
        response = client.save_layout(layout_uuid, updated_layout)
        typer.echo("✅ Layout updated successfully!")
        typer.echo(f"🔗 UUID: {layout_uuid}")
        typer.echo(f"📝 Title: {updated_meta['title']}")
        if response.get("status") == "no_content":
            typer.echo("📊 Status: Update completed")
    except Exception as e:
        typer.echo(f"❌ Error updating layout: {e}")
        raise typer.Exit(1) from None


@glove80_group.command()
def download(
    layout_uuid: Annotated[str, typer.Argument(help="UUID of the layout to download")],
    output: Annotated[
        Path | None, typer.Option("-o", "--output", help="Save to file")
    ] = None,
    write_uuid: Annotated[
        bool,
        typer.Option("-w", "--write-uuid", help="Save to file using UUID as filename"),
    ] = False,
) -> None:
    """Download a layout from Glove80 cloud service."""

    client = create_moergo_client()

    if not client.validate_authentication():
        typer.echo(
            "❌ Authentication failed. Please run 'glovebox moergo login' first.",
            err=True,
        )
        raise typer.Exit(1) from None

    try:
        layout = client.get_layout(layout_uuid)

        # Determine output file path
        output_file = None
        if write_uuid:
            output_file = Path(f"{layout_uuid}.json")
        elif output:
            output_file = output

        if output_file:
            # Save the config part (the actual layout data)
            output_file.write_text(
                layout.config.model_dump_json(by_alias=True, indent=2)
            )
            typer.echo(f"💾 Saved to: {output_file}", err=True)
        else:
            # Print only JSON to stdout (no meta information)
            typer.echo(layout.config.model_dump_json(by_alias=True, indent=2))

    except Exception as e:
        typer.echo(f"❌ Error downloading layout: {e}", err=True)
        raise typer.Exit(1) from None


@glove80_group.command()
def delete(
    layout_uuid: Annotated[str, typer.Argument(help="UUID of the layout to delete")],
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Skip confirmation prompt")
    ] = False,
) -> None:
    """Delete a layout from Glove80 cloud service."""

    client = create_moergo_client()

    if not client.validate_authentication():
        typer.echo(
            "❌ Authentication failed. Please run 'glovebox moergo login' first."
        )
        raise typer.Exit(1) from None

    # Get layout info first
    try:
        layout = client.get_layout(layout_uuid)
        typer.echo(f"📄 Layout to delete: {layout.layout_meta.title}")
        typer.echo(f"👤 Creator: {layout.layout_meta.creator}")
        typer.echo(f"📅 Created: {layout.layout_meta.created_datetime}")
    except Exception as e:
        typer.echo(f"❌ Error fetching layout: {e}")
        raise typer.Exit(1) from None

    # Confirmation
    if not force:
        delete_confirm = typer.confirm(
            f"⚠️  Are you sure you want to delete '{layout.layout_meta.title}'?"
        )
        if not delete_confirm:
            typer.echo("❌ Deletion cancelled")
            raise typer.Exit(0)

    # Delete the layout
    try:
        success = client.delete_layout(layout_uuid)
        if success:
            typer.echo("✅ Layout deleted successfully!")
        else:
            typer.echo("❌ Failed to delete layout")
            raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"❌ Error deleting layout: {e}")
        raise typer.Exit(1) from None


@glove80_group.command()
def list_layouts(
    ctx: typer.Context,
    detailed: Annotated[
        bool,
        typer.Option("--detailed", "-d", help="Show detailed info for recent layouts"),
    ] = False,
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", help="Limit number of detailed layouts to show"),
    ] = 5,
) -> None:
    """List all user's layouts from Glove80 cloud service."""
    from glovebox.cli.app import AppContext
    from glovebox.cli.helpers.theme import Icons

    app_ctx: AppContext = ctx.obj
    use_emoji = app_ctx.use_emoji

    client = create_moergo_client()

    if not client.validate_authentication():
        typer.echo(
            Icons.format_with_icon(
                "ERROR",
                "Authentication failed. Please run 'glovebox moergo login' first.",
                use_emoji,
            )
        )
        raise typer.Exit(1) from None

    try:
        layouts = client.list_user_layouts()

        if not layouts:
            typer.echo(
                Icons.format_with_icon("MAILBOX", "No layouts found.", use_emoji)
            )
            return

        # Group by status for better display
        draft_layouts = [layout for layout in layouts if layout["status"] == "draft"]
        compiled_layouts = [
            layout for layout in layouts if layout["status"] == "compiled"
        ]

        typer.echo(
            Icons.format_with_icon(
                "DOCUMENT", f"Found {len(layouts)} layouts:", use_emoji
            )
        )
        typer.echo()

        if compiled_layouts:
            typer.echo(
                Icons.format_with_icon(
                    "SUCCESS", f"Compiled layouts ({len(compiled_layouts)}):", use_emoji
                )
            )
            for layout in compiled_layouts[:10]:  # Show first 10
                typer.echo(f"   {Icons.get_icon('LINK', use_emoji)} {layout['uuid']}")
            if len(compiled_layouts) > 10:
                typer.echo(f"   ... and {len(compiled_layouts) - 10} more")
            typer.echo()

        if draft_layouts:
            typer.echo(
                Icons.format_with_icon(
                    "DOCUMENT", f"Draft layouts ({len(draft_layouts)}):", use_emoji
                )
            )
            for layout in draft_layouts[:10]:  # Show first 10
                typer.echo(f"   {Icons.get_icon('LINK', use_emoji)} {layout['uuid']}")
            if len(draft_layouts) > 10:
                typer.echo(f"   ... and {len(draft_layouts) - 10} more")
            typer.echo()

        typer.echo(
            Icons.format_with_icon(
                "INFO",
                "Use 'glovebox layout glove80 info <uuid>' to get details about a specific layout",
                use_emoji,
            )
        )

        # Show detailed info for recent layouts if requested
        if detailed and layouts:
            typer.echo()
            typer.echo(
                f"📋 Detailed info for {min(limit, len(layouts))} recent layouts:"
            )
            typer.echo()

            for layout in layouts[:limit]:
                try:
                    # Use the more efficient meta endpoint instead of full layout
                    meta_response = client.get_layout_meta(layout["uuid"])
                    layout_meta = meta_response["layout_meta"]

                    status_icon = "✅" if layout["status"] == "compiled" else "📝"
                    typer.echo(f"{status_icon} {layout_meta['title']}")
                    typer.echo(f"   🔗 UUID: {layout['uuid']}")
                    typer.echo(f"   👤 Creator: {layout_meta['creator']}")
                    typer.echo(
                        f"   📅 Modified: {datetime.fromtimestamp(layout_meta['date'])}"
                    )
                    if layout_meta["tags"]:
                        typer.echo(
                            f"   🏷️  Tags: {', '.join(layout_meta['tags'][:3])}{'...' if len(layout_meta['tags']) > 3 else ''}"
                        )
                    if layout_meta.get("notes"):
                        # Show first line of notes
                        first_line = layout_meta["notes"].split("\n")[0]
                        if len(first_line) > 60:
                            first_line = first_line[:57] + "..."
                        typer.echo(f"   📝 Notes: {first_line}")
                    typer.echo()
                except Exception:
                    typer.echo(f"⚠️  Could not fetch details for {layout['uuid']}")
                    typer.echo()

    except Exception as e:
        typer.echo(f"❌ Error listing layouts: {e}")
        raise typer.Exit(1) from None


@glove80_group.command()
def meta(
    layout_uuid: Annotated[
        str, typer.Argument(help="UUID of the layout to get metadata for")
    ],
) -> None:
    """Get just the metadata for a layout (faster than full info)."""

    client = create_moergo_client()

    if not client.validate_authentication():
        typer.echo(
            "❌ Authentication failed. Please run 'glovebox moergo login' first."
        )
        raise typer.Exit(1) from None

    try:
        meta_response = client.get_layout_meta(layout_uuid)
        layout_meta = meta_response["layout_meta"]

        typer.echo(f"🔗 UUID: {layout_meta['uuid']}")
        typer.echo(f"📝 Title: {layout_meta['title']}")
        typer.echo(f"👤 Creator: {layout_meta['creator']}")
        typer.echo(f"📅 Created: {datetime.fromtimestamp(layout_meta['date'])}")
        typer.echo(f"🏷️  Tags: {', '.join(layout_meta['tags'])}")
        typer.echo(
            f"👁️  Visibility: {'Unlisted' if layout_meta['unlisted'] else 'Public'}"
        )
        typer.echo(f"🔍 Searchable: {layout_meta['searchable']}")
        typer.echo(f"✅ Compiled: {layout_meta['compiled']}")
        typer.echo(f"⚙️  Firmware API: {layout_meta['firmware_api_version']}")

        if layout_meta.get("parent_uuid"):
            typer.echo(f"👨‍👩‍👧‍👦 Parent UUID: {layout_meta['parent_uuid']}")

        if layout_meta.get("notes"):
            typer.echo("📝 Notes:")
            typer.echo(f"   {layout_meta['notes']}")

    except Exception as e:
        typer.echo(f"❌ Error getting layout metadata: {e}")
        raise typer.Exit(1) from None


@glove80_group.command()
def info(
    layout_uuid: Annotated[
        str, typer.Argument(help="UUID of the layout to get info for")
    ],
) -> None:
    """Get information about a layout from Glove80 cloud service."""

    client = create_moergo_client()

    if not client.validate_authentication():
        typer.echo(
            "❌ Authentication failed. Please run 'glovebox moergo login' first."
        )
        raise typer.Exit(1) from None

    try:
        layout = client.get_layout(layout_uuid)

        typer.echo(f"🔗 UUID: {layout.layout_meta.uuid}")
        typer.echo(f"📝 Title: {layout.layout_meta.title}")
        typer.echo(f"👤 Creator: {layout.layout_meta.creator}")
        typer.echo(f"📅 Created: {layout.layout_meta.created_datetime}")
        typer.echo(
            f"🔄 Last Modified: {datetime.fromtimestamp(layout.layout_meta.date)}"
        )
        typer.echo(f"🏷️  Tags: {', '.join(layout.layout_meta.tags)}")
        typer.echo(
            f"👁️  Visibility: {'Unlisted' if layout.layout_meta.unlisted else 'Public'}"
        )
        typer.echo(f"🔍 Searchable: {layout.layout_meta.searchable}")
        typer.echo(f"⚙️  Firmware API: {layout.layout_meta.firmware_api_version}")

        if layout.layout_meta.parent_uuid:
            typer.echo(f"👨‍👩‍👧‍👦 Parent UUID: {layout.layout_meta.parent_uuid}")

        if layout.layout_meta.notes:
            typer.echo("📝 Notes:")
            typer.echo(f"   {layout.layout_meta.notes}")

        # Layout stats
        config = layout.config
        typer.echo("📊 Layout Stats:")
        typer.echo(f"   Layers: {len(config.layer_names)}")
        typer.echo(f"   Hold-taps: {len(config.hold_taps)}")
        typer.echo(f"   Combos: {len(config.combos)}")
        typer.echo(f"   Macros: {len(config.macros)}")

    except Exception as e:
        typer.echo(f"❌ Error getting layout info: {e}")
        raise typer.Exit(1) from None


@glove80_group.command()
def version_history(
    layout_uuid: Annotated[
        str, typer.Argument(help="UUID of the layout to show history for")
    ],
    show_tree: Annotated[
        bool,
        typer.Option("--tree", help="Show full family tree instead of linear lineage"),
    ] = False,
) -> None:
    """Show version history of a layout using parent_uuid relationships."""

    client = create_moergo_client()

    if not client.validate_authentication():
        typer.echo(
            "❌ Authentication failed. Please run 'glovebox moergo login' first."
        )
        raise typer.Exit(1) from None

    versioning = create_layout_versioning(client)

    try:
        if show_tree:
            typer.echo("🌳 Building complete version tree...")
            # For now, show family members as this is synchronous
            family_members = versioning.get_all_versions_in_family(layout_uuid)

            if not family_members:
                typer.echo("No version family found.")
                return

            typer.echo(f"📊 Version Family ({len(family_members)} versions):")
            typer.echo("=" * 60)

            for i, version in enumerate(family_members):
                typer.echo(f"v{i + 1}: {version.title}")
                typer.echo(f"   🔗 UUID: {version.uuid}")
                typer.echo(f"   👤 Creator: {version.creator}")
                typer.echo(f"   📅 Created: {version.created_datetime}")

                if version.parent_uuid:
                    typer.echo(f"   👪 Parent: {version.parent_uuid}")
                else:
                    typer.echo("   👑 Root version")

                if version.notes:
                    # Truncate notes to first 160 characters
                    truncated_notes = version.notes[:160]
                    if len(version.notes) > 160:
                        truncated_notes += "..."
                    typer.echo(f"   📝 Notes: {truncated_notes}")

                if version.tags:
                    typer.echo(f"   🏷️  Tags: {', '.join(version.tags)}")

                typer.echo()
        else:
            # Show linear lineage
            lineage = versioning.get_version_lineage(layout_uuid)

            if not lineage:
                typer.echo("No version lineage found.")
                return

            versioning.print_version_lineage(lineage)

    except Exception as e:
        typer.echo(f"❌ Error getting version history: {e}")
        raise typer.Exit(1) from None


@glove80_group.command()
def create_version(
    parent_uuid: Annotated[str, typer.Argument(help="UUID of the parent layout")],
    layout_file: Annotated[
        Path, typer.Argument(help="Layout file for the new version", exists=True)
    ],
    title: Annotated[str, typer.Option("--title", help="Title for the new version")],
    notes: Annotated[str, typer.Option("--notes", help="Notes for this version")] = "",
    tags: Annotated[
        list[str] | None, typer.Option("--tag", help="Tags for the new version")
    ] = None,
) -> None:
    """Create a new version of a layout with parent_uuid link."""

    client = create_moergo_client()

    if not client.validate_authentication():
        typer.echo(
            "❌ Authentication failed. Please run 'glovebox moergo login' first."
        )
        raise typer.Exit(1) from None

    versioning = create_layout_versioning(client)

    try:
        # Get parent layout
        parent_layout = client.get_layout(parent_uuid)
        typer.echo(f"📥 Found parent layout: {parent_layout.layout_meta.title}")

        # Load new layout content
        new_layout_data = load_layout_file(layout_file)

        # Create version with parent link
        import uuid

        new_uuid = str(uuid.uuid4())

        # Create new layout metadata with parent reference
        new_meta = {
            "uuid": new_uuid,
            "title": title,
            "notes": notes,
            "tags": tags or parent_layout.layout_meta.tags,
            "parent_uuid": parent_layout.layout_meta.uuid,  # Key: set parent reference
            "creator": parent_layout.layout_meta.creator,
            "firmware_api_version": parent_layout.layout_meta.firmware_api_version,
            "date": int(datetime.now().timestamp()),
            "unlisted": parent_layout.layout_meta.unlisted,
            "deleted": False,
            "compiled": False,
            "searchable": True,
        }

        # Create complete layout with new content
        complete_layout = {
            "layout_meta": new_meta,
            "config": new_layout_data.model_dump(mode="json", by_alias=True),
        }

        typer.echo(f"📤 Creating new version '{title}' with parent link...")

        # Upload the new version
        response = client.save_layout(new_uuid, complete_layout)

        typer.echo("✅ New version created successfully!")
        typer.echo(f"🔗 New UUID: {new_uuid}")
        typer.echo(f"👪 Parent UUID: {parent_uuid}")
        typer.echo(f"📝 Title: {title}")

        if notes:
            typer.echo(f"📖 Notes: {notes}")

        # Show lineage
        typer.echo("\n📜 Updated lineage:")
        lineage = versioning.get_version_lineage(new_uuid)
        for i, version in enumerate(lineage):
            if version.uuid == new_uuid:
                typer.echo(f"  v{i + 1}: {version.title} ⭐ (NEW)")
            else:
                typer.echo(f"  v{i + 1}: {version.title}")

    except Exception as e:
        typer.echo(f"❌ Error creating version: {e}")
        raise typer.Exit(1) from None


@glove80_group.command()
def batch_delete(
    layout_uuids: Annotated[
        list[str], typer.Argument(help="UUIDs of layouts to delete")
    ],
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Skip confirmation prompt")
    ] = False,
) -> None:
    """Delete multiple layouts from Glove80 cloud service."""

    client = create_moergo_client()

    if not client.validate_authentication():
        typer.echo(
            "❌ Authentication failed. Please run 'glovebox moergo login' first."
        )
        raise typer.Exit(1) from None

    typer.echo(f"🗑️  About to delete {len(layout_uuids)} layouts:")

    # Show info for each layout
    layout_infos = {}
    for uuid in layout_uuids:
        try:
            meta_response = client.get_layout_meta(uuid)
            layout_meta = meta_response["layout_meta"]
            layout_infos[uuid] = layout_meta
            typer.echo(f"   📝 {layout_meta['title']} ({uuid})")
        except Exception:
            typer.echo(f"   ❓ Unknown layout ({uuid})")

    # Confirmation prompt
    if not force:
        confirm = typer.confirm(
            f"⚠️  Are you sure you want to delete these {len(layout_uuids)} layouts? This cannot be undone."
        )
        if not confirm:
            typer.echo("❌ Deletion cancelled.")
            return

    try:
        results = client.batch_delete_layouts(layout_uuids)

        successful = []
        failed = []

        for uuid, success in results.items():
            if success:
                successful.append(uuid)
            else:
                failed.append(uuid)

        if successful:
            typer.echo(f"✅ Successfully deleted {len(successful)} layouts:")
            for uuid in successful:
                title = layout_infos.get(uuid, {}).get("title", "Unknown")
                typer.echo(f"   ✅ {title} ({uuid})")

        if failed:
            typer.echo(f"❌ Failed to delete {len(failed)} layouts:")
            for uuid in failed:
                title = layout_infos.get(uuid, {}).get("title", "Unknown")
                typer.echo(f"   ❌ {title} ({uuid})")
            raise typer.Exit(1) from None

    except Exception as e:
        typer.echo(f"❌ Error deleting layouts: {e}")
        raise typer.Exit(1) from None


@glove80_group.command()
def browse(
    ctx: typer.Context,
    limit: Annotated[
        int, typer.Option("--limit", "-l", help="Limit number of layouts to show")
    ] = 20,
    detailed: Annotated[
        bool, typer.Option("--detailed", "-d", help="Show detailed info for layouts")
    ] = False,
    tags: Annotated[
        list[str] | None,
        typer.Option("--tag", "-t", help="Filter by tags (can use multiple times)"),
    ] = None,
    no_cache: Annotated[
        bool, typer.Option("--no-cache", help="Skip cache and fetch fresh data")
    ] = False,
) -> None:
    """Browse public layouts from Glove80 community."""
    from glovebox.cli.app import AppContext
    from glovebox.cli.helpers.theme import Icons

    app_ctx: AppContext = ctx.obj
    use_emoji = app_ctx.use_emoji

    client = create_moergo_client()

    if not client.validate_authentication():
        typer.echo(
            Icons.format_with_icon(
                "ERROR",
                "Authentication failed. Please run 'glovebox moergo login' first.",
                use_emoji,
            )
        )
        raise typer.Exit(1) from None

    try:
        if tags:
            typer.echo(
                Icons.format_with_icon(
                    "GLOBE",
                    f"Fetching public layouts with tags: {', '.join(tags)}",
                    use_emoji,
                )
            )
        else:
            typer.echo(
                Icons.format_with_icon(
                    "GLOBE",
                    "Fetching public layouts from Glove80 community...",
                    use_emoji,
                )
            )

        # Show cache status
        if not no_cache:
            typer.echo(
                Icons.format_with_icon(
                    "SAVE", "Using cached data when available...", use_emoji
                )
            )

        public_uuids = client.list_public_layouts(tags=tags, use_cache=not no_cache)

        if tags:
            typer.echo(
                Icons.format_with_icon(
                    "DOCUMENT",
                    f"Found {len(public_uuids)} public layouts with tags '{', '.join(tags)}' (showing {min(limit, len(public_uuids))}):",
                    use_emoji,
                )
            )
        else:
            typer.echo(
                Icons.format_with_icon(
                    "DOCUMENT",
                    f"Found {len(public_uuids)} public layouts (showing {min(limit, len(public_uuids))}):",
                    use_emoji,
                )
            )
        typer.echo()

        # Show basic list first
        if not detailed:
            for i, uuid in enumerate(public_uuids[:limit]):
                typer.echo(f"   {i + 1:3d}. {Icons.get_icon('LINK', use_emoji)} {uuid}")
        else:
            # Show detailed info for each layout
            for i, uuid in enumerate(public_uuids[:limit]):
                try:
                    meta_response = client.get_layout_meta(uuid, use_cache=not no_cache)
                    layout_meta = meta_response["layout_meta"]

                    status_icon = (
                        Icons.get_icon("SUCCESS", use_emoji)
                        if layout_meta["compiled"]
                        else Icons.get_icon("DOCUMENT", use_emoji)
                    )
                    typer.echo(f"{i + 1:3d}. {status_icon} {layout_meta['title']}")
                    typer.echo(f"     {Icons.get_icon('LINK', use_emoji)} UUID: {uuid}")
                    typer.echo(
                        f"     {Icons.get_icon('USER', use_emoji)} Creator: {layout_meta['creator']}"
                    )
                    typer.echo(
                        f"     {Icons.get_icon('CALENDAR', use_emoji)} Modified: {datetime.fromtimestamp(layout_meta['date'])}"
                    )
                    if layout_meta["tags"]:
                        typer.echo(
                            f"     {Icons.get_icon('TAG', use_emoji)} Tags: {', '.join(layout_meta['tags'][:3])}{'...' if len(layout_meta['tags']) > 3 else ''}"
                        )
                    if layout_meta.get("notes"):
                        # Show first line of notes
                        first_line = layout_meta["notes"].split("\n")[0]
                        if len(first_line) > 60:
                            first_line = first_line[:57] + "..."
                        typer.echo(
                            f"     {Icons.get_icon('DOCUMENT', use_emoji)} Notes: {first_line}"
                        )
                    typer.echo()
                except Exception:
                    typer.echo(
                        f"{i + 1:3d}. {Icons.get_icon('QUESTION', use_emoji)} Layout {uuid} (unable to fetch details)"
                    )
                    typer.echo()

        if not detailed:
            typer.echo()
            typer.echo("💡 Use --detailed to see layout information")
            typer.echo(
                "💡 Use --tag <tag> to filter by tags (e.g., --tag linux --tag gaming)"
            )
            typer.echo("💡 Use --no-cache to fetch fresh data")
            typer.echo("💡 Use 'glovebox layout glove80 info <uuid>' for full details")
            typer.echo(
                "💡 Use 'glovebox layout glove80 download <uuid>' to download a layout"
            )

    except Exception as e:
        typer.echo(f"❌ Error browsing public layouts: {e}")
        raise typer.Exit(1) from None


@glove80_group.command()
def cache_stats() -> None:
    """Show cache statistics and performance metrics."""

    client = create_moergo_client()

    try:
        # Cache stats functionality not available in simplified client
        typer.echo("📊 Glove80 API Cache:")
        typer.echo()
        typer.echo("   💾 Cache is enabled for API responses")
        typer.echo("   ⚡ Speeds up repeated API calls")
        typer.echo("   🔄 Use 'cache-clear' to empty cache")

    except Exception as e:
        typer.echo(f"❌ Error accessing cache: {e}")
        raise typer.Exit(1) from None


@glove80_group.command()
def cache_clear(
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Skip confirmation prompt")
    ] = False,
) -> None:
    """Clear the API response cache."""

    client = create_moergo_client()

    # Confirmation prompt
    if not force:
        confirm = typer.confirm(
            "⚠️  Are you sure you want to clear the cache? This will slow down the next API calls."
        )
        if not confirm:
            typer.echo("❌ Cache clear cancelled.")
            return

    try:
        client.clear_cache()
        typer.echo("✅ Cache cleared successfully!")
        typer.echo("💡 Next API calls will be slower but will rebuild the cache")

    except Exception as e:
        typer.echo(f"❌ Error clearing cache: {e}")
        raise typer.Exit(1) from None
