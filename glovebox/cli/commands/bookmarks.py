"""Bookmark management commands for easy access to saved layouts."""

from __future__ import annotations

import builtins
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

from glovebox.layout.models.bookmarks import BookmarkSource
from glovebox.moergo.bookmark_service import create_bookmark_service


# Create a typer app for bookmark commands
bookmarks_app = typer.Typer(
    name="bookmarks",
    help="Manage layout bookmarks for easy access",
    no_args_is_help=True,
)


def complete_bookmark_name(incomplete: str) -> builtins.list[str]:
    """Tab completion for bookmark names."""
    try:
        bookmark_service = create_bookmark_service()
        bookmarks = bookmark_service.list_bookmarks()
        return [
            bookmark.name
            for bookmark in bookmarks
            if bookmark.name.startswith(incomplete)
        ]
    except Exception:
        return []


@bookmarks_app.command()
def add(
    ctx: typer.Context,
    layout_uuid: Annotated[str, typer.Argument(help="UUID of the layout to bookmark")],
    name: Annotated[str, typer.Argument(help="Name for the bookmark")],
    description: Annotated[
        str | None,
        typer.Option("--description", "-d", help="Description for the bookmark"),
    ] = None,
) -> None:
    """Add a new layout bookmark."""
    from glovebox.cli.app import AppContext
    from glovebox.cli.helpers.theme import Icons

    app_ctx: AppContext = ctx.obj
    use_emoji = app_ctx.use_emoji

    try:
        bookmark_service = create_bookmark_service()

        # Check if bookmark already exists
        existing = bookmark_service.get_bookmark(name)
        if existing:
            typer.echo(
                Icons.format_with_icon(
                    "WARNING",
                    f"Bookmark '{name}' already exists (UUID: {existing.uuid})",
                    use_emoji,
                )
            )
            if not typer.confirm("Do you want to replace it?"):
                typer.echo("❌ Bookmark creation cancelled.")
                return

        # Add the bookmark
        bookmark = bookmark_service.add_bookmark(
            uuid=layout_uuid,
            name=name,
            description=description,
            fetch_metadata=True,
        )

        typer.echo("✅ Bookmark added successfully!")
        typer.echo(f"📛 Name: {bookmark.name}")
        typer.echo(f"🔗 UUID: {bookmark.uuid}")
        if bookmark.title:
            typer.echo(f"📝 Title: {bookmark.title}")
        if bookmark.description:
            typer.echo(f"💬 Description: {bookmark.description}")

    except Exception as e:
        typer.echo(f"❌ Error adding bookmark: {e}")
        raise typer.Exit(1) from e


@bookmarks_app.command()
def list(
    ctx: typer.Context,
    factory_only: Annotated[
        bool, typer.Option("--factory", help="Show only factory default bookmarks")
    ] = False,
    user_only: Annotated[
        bool, typer.Option("--user", help="Show only user bookmarks")
    ] = False,
) -> None:
    """List all saved layout bookmarks."""
    from glovebox.cli.app import AppContext
    from glovebox.cli.helpers.theme import Icons

    app_ctx: AppContext = ctx.obj
    use_emoji = app_ctx.use_emoji

    try:
        bookmark_service = create_bookmark_service()

        # Determine source filter
        source_filter = None
        if factory_only:
            source_filter = BookmarkSource.FACTORY
        elif user_only:
            source_filter = BookmarkSource.USER

        bookmarks = bookmark_service.list_bookmarks(source_filter)

        if not bookmarks:
            typer.echo("📭 No bookmarks found.")
            return

        # Group bookmarks by source
        factory_bookmarks = [b for b in bookmarks if b.source == BookmarkSource.FACTORY]
        user_bookmarks = [b for b in bookmarks if b.source == BookmarkSource.USER]

        typer.echo(f"📚 Found {len(bookmarks)} bookmarks:")
        typer.echo()

        if factory_bookmarks and not user_only:
            typer.echo(f"🏭 Factory defaults ({len(factory_bookmarks)}):")
            for bookmark in factory_bookmarks:
                typer.echo(f"   📦 {bookmark.name}")
                if bookmark.title:
                    typer.echo(f"      📝 {bookmark.title}")
                typer.echo()

        if user_bookmarks and not factory_only:
            typer.echo(f"👤 User bookmarks ({len(user_bookmarks)}):")
            for bookmark in user_bookmarks:
                typer.echo(f"   📛 {bookmark.name}")
                if bookmark.title:
                    typer.echo(f"      📝 {bookmark.title}")
                typer.echo()

        typer.echo("💡 Use 'glovebox bookmarks clone <name> <output.json>' to clone")
        typer.echo(
            "💡 Use 'glovebox bookmarks flash <name> --profile <profile>' to flash"
        )

    except Exception as e:
        typer.echo(f"❌ Error listing bookmarks: {e}")
        raise typer.Exit(1) from e


@bookmarks_app.command()
def clone(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Argument(
            help="Name of the bookmark to clone", autocompletion=complete_bookmark_name
        ),
    ],
    output: Annotated[
        Path, typer.Argument(help="Output file path for the cloned layout")
    ],
) -> None:
    """Clone a bookmarked layout to a local file."""
    try:
        bookmark_service = create_bookmark_service()

        # Get bookmark
        bookmark = bookmark_service.get_bookmark(name)
        if not bookmark:
            typer.echo(f"❌ Bookmark '{name}' not found.")
            raise typer.Exit(1)

        # Get full layout data
        layout = bookmark_service.get_layout_by_bookmark(name)

        # Save the config part (the actual layout data)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(layout.config.model_dump_json(by_alias=True, indent=2))

        typer.echo("✅ Layout cloned successfully!")
        typer.echo(f"📛 Bookmark: {bookmark.name}")
        typer.echo(f"📝 Title: {layout.layout_meta.title}")
        typer.echo(f"💾 Saved to: {output}")

    except Exception as e:
        typer.echo(f"❌ Error cloning bookmark: {e}")
        raise typer.Exit(1) from e


@bookmarks_app.command()
def flash(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Argument(
            help="Name of the bookmark to flash", autocompletion=complete_bookmark_name
        ),
    ],
    profile: Annotated[
        str, typer.Option("--profile", help="Keyboard profile (e.g., 'glove80/v25.05')")
    ],
) -> None:
    """Flash firmware for a bookmarked layout directly to keyboard."""
    from glovebox.cli.app import AppContext
    from glovebox.cli.helpers.theme import Icons

    app_ctx: AppContext = ctx.obj
    use_emoji = app_ctx.use_emoji

    try:
        bookmark_service = create_bookmark_service()

        # Get bookmark
        bookmark = bookmark_service.get_bookmark(name)
        if not bookmark:
            typer.echo(f"❌ Bookmark '{name}' not found.")
            raise typer.Exit(1)

        # Parse profile
        try:
            from glovebox.cli.helpers.profile import create_profile_from_context

            keyboard_profile = create_profile_from_context(ctx, profile)
        except Exception as e:
            typer.echo(f"❌ Invalid profile '{profile}': {e}")
            raise typer.Exit(1) from e

        # Get layout metadata to check compilation status
        layout_meta = bookmark_service._client.get_layout_meta(
            bookmark.uuid, use_cache=True
        )

        typer.echo(f"⚡ Flashing bookmark '{bookmark.name}'...")

        # Check if we can use MoErgo's compiled firmware
        if layout_meta["layout_meta"]["compiled"]:
            typer.echo("🏗️ Using pre-compiled firmware from MoErgo servers")

            # Use MoErgo's compile and download workflow
            layout = bookmark_service.get_layout_by_bookmark(name)

            # Import layout service to convert to ZMK format
            from glovebox.layout import create_layout_service

            layout_service = create_layout_service()

            # Generate ZMK files from layout
            import tempfile

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_output = Path(temp_dir) / "temp_keymap"

                # Clone layout to temporary file
                temp_layout_path = Path(temp_dir) / "layout.json"
                temp_layout_path.write_text(
                    layout.config.model_dump_json(by_alias=True, indent=2)
                )

                # Generate ZMK files
                result = layout_service.generate_from_file(
                    profile=keyboard_profile,
                    json_file_path=temp_layout_path,
                    output_file_prefix=temp_output,
                    force=True,
                )

                if not result.success:
                    typer.echo(
                        f"❌ Failed to generate ZMK files: {'; '.join(result.errors)}"
                    )
                    raise typer.Exit(1)

                # Read the generated files
                keymap_file = temp_output.with_suffix(".keymap")
                config_file = temp_output.with_suffix(".conf")

                keymap_content = keymap_file.read_text()
                config_content = config_file.read_text() if config_file.exists() else ""

                # Compile firmware using MoErgo API
                typer.echo("🏗️ Compiling firmware on MoErgo servers...")
                compile_response = bookmark_service._client.compile_firmware(
                    layout_uuid=bookmark.uuid,
                    keymap=keymap_content,
                    kconfig=config_content,
                    board=keyboard_profile.keyboard_name or "glove80",
                    firmware_version=keyboard_profile.firmware_version or "v25.05",
                )

                # Download firmware
                typer.echo("📥 Downloading compiled firmware...")
                firmware_path = Path(f"{bookmark.name}.uf2")
                firmware_data = bookmark_service._client.download_firmware(
                    firmware_location=compile_response.location,
                    output_path=str(firmware_path),
                )

                # Flash the firmware
                from glovebox.firmware.flash import create_flash_service

                flash_service = create_flash_service()

                typer.echo("⚡ Flashing firmware to keyboard...")
                flash_result = flash_service.flash_from_file(
                    firmware_file_path=firmware_path, profile=keyboard_profile
                )

                if flash_result.success:
                    typer.echo("✅ Firmware flashed successfully!")
                else:
                    typer.echo(f"❌ Flash failed: {'; '.join(flash_result.errors)}")
                    raise typer.Exit(1)
        else:
            typer.echo(
                "⚠️ Layout not compiled on MoErgo servers. Compile locally first."
            )
            typer.echo("💡 Use 'glovebox layout compile' to build firmware locally")

    except Exception as e:
        typer.echo(f"❌ Error flashing bookmark: {e}")
        raise typer.Exit(1) from e


@bookmarks_app.command()
def remove(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Argument(
            help="Name of the bookmark to remove",
            autocompletion=complete_bookmark_name,
        ),
    ],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Remove a layout bookmark."""
    from glovebox.cli.app import AppContext
    from glovebox.cli.helpers.theme import Icons

    app_ctx: AppContext = ctx.obj
    use_emoji = app_ctx.use_emoji

    try:
        bookmark_service = create_bookmark_service()

        # Check if bookmark exists
        bookmark = bookmark_service.get_bookmark(name)
        if not bookmark:
            typer.echo(f"❌ Bookmark '{name}' not found")
            raise typer.Exit(1)

        # Ask for confirmation unless --force is used
        if not force:
            confirm = typer.confirm(f"Remove bookmark '{name}'?")
            if not confirm:
                typer.echo("❌ Operation cancelled")
                return

        # Remove the bookmark
        success = bookmark_service.remove_bookmark(name)
        if success:
            typer.echo(f"✅ Bookmark '{name}' removed successfully!")
        else:
            typer.echo(f"❌ Failed to remove bookmark '{name}'")
            raise typer.Exit(1)

    except Exception as e:
        typer.echo(f"❌ Error removing bookmark: {e}")
        raise typer.Exit(1) from e


@bookmarks_app.command()
def info(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Argument(
            help="Name of the bookmark to show info for",
            autocompletion=complete_bookmark_name,
        ),
    ],
) -> None:
    """Get detailed information about a bookmarked layout."""
    from glovebox.cli.app import AppContext
    from glovebox.cli.helpers.theme import Icons

    app_ctx: AppContext = ctx.obj
    use_emoji = app_ctx.use_emoji

    try:
        bookmark_service = create_bookmark_service()

        # Get bookmark info
        bookmark = bookmark_service.get_bookmark(name)
        if not bookmark:
            typer.echo(f"❌ Bookmark '{name}' not found")
            raise typer.Exit(1)

        # Display bookmark information
        typer.echo(f"📛 Name: {bookmark.name}")
        typer.echo(f"🔗 UUID: {bookmark.uuid}")
        if bookmark.title:
            typer.echo(f"📝 Title: {bookmark.title}")
        if bookmark.description:
            typer.echo(f"💬 Description: {bookmark.description}")
        if bookmark.tags:
            typer.echo(f"🏷️  Tags: {', '.join(bookmark.tags)}")
        typer.echo(
            f"📂 Source: {bookmark.source.value if hasattr(bookmark.source, 'value') else bookmark.source}"
        )

    except Exception as e:
        typer.echo(f"❌ Error getting bookmark info: {e}")
        raise typer.Exit(1) from e


@bookmarks_app.command()
def refresh(
    ctx: typer.Context,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Refresh factory default bookmarks from MoErgo API."""
    from glovebox.cli.app import AppContext
    from glovebox.cli.helpers.theme import Icons

    app_ctx: AppContext = ctx.obj
    use_emoji = app_ctx.use_emoji

    try:
        bookmark_service = create_bookmark_service()

        # Ask for confirmation unless --force is used
        if not force:
            confirm = typer.confirm("Refresh factory default bookmarks?")
            if not confirm:
                typer.echo("❌ Operation cancelled")
                return

        # Refresh factory defaults
        count = bookmark_service.refresh_factory_defaults()
        typer.echo(f"✅ Refreshed {count} factory default bookmarks!")

    except Exception as e:
        typer.echo(f"❌ Error refreshing factory bookmarks: {e}")
        raise typer.Exit(1) from e


def register_commands(app: typer.Typer) -> None:
    """Register bookmark commands with the main app."""
    app.add_typer(bookmarks_app, name="bookmarks")
