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
        from glovebox.config import create_user_config

        user_config = create_user_config()
        bookmark_service = create_bookmark_service(user_config._config)
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
    from glovebox.cli.helpers.theme import Icons, get_icon_mode_from_context

    icon_mode = get_icon_mode_from_context(ctx)

    try:
        from glovebox.cli.helpers.profile import get_user_config_from_context
        from glovebox.config import create_user_config

        user_config = get_user_config_from_context(ctx) or create_user_config()
        bookmark_service = create_bookmark_service(user_config._config)

        # Check if bookmark already exists
        existing = bookmark_service.get_bookmark(name)
        if existing:
            typer.echo(
                Icons.format_with_icon(
                    "WARNING",
                    f"Bookmark '{name}' already exists (UUID: {existing.uuid})",
                    icon_mode,
                )
            )
            if not typer.confirm("Do you want to replace it?"):
                typer.echo(
                    Icons.format_with_icon(
                        "ERROR", "Bookmark creation cancelled.", icon_mode
                    )
                )
                return

        # Add the bookmark
        bookmark = bookmark_service.add_bookmark(
            uuid=layout_uuid,
            name=name,
            description=description,
            fetch_metadata=True,
        )

        typer.echo(
            Icons.format_with_icon("SUCCESS", "Bookmark added successfully!", icon_mode)
        )
        typer.echo(Icons.format_with_icon("TAG", f"Name: {bookmark.name}", icon_mode))
        typer.echo(Icons.format_with_icon("LINK", f"UUID: {bookmark.uuid}", icon_mode))
        if bookmark.title:
            typer.echo(
                Icons.format_with_icon(
                    "DOCUMENT", f"Title: {bookmark.title}", icon_mode
                )
            )
        if bookmark.description:
            typer.echo(
                Icons.format_with_icon(
                    "INFO", f"Description: {bookmark.description}", icon_mode
                )
            )

    except Exception as e:
        typer.echo(
            Icons.format_with_icon("ERROR", f"Error adding bookmark: {e}", icon_mode)
        )
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
    from glovebox.cli.helpers.theme import Icons, get_icon_mode_from_context

    icon_mode = get_icon_mode_from_context(ctx)

    try:
        from glovebox.cli.helpers.profile import get_user_config_from_context
        from glovebox.config import create_user_config

        user_config = get_user_config_from_context(ctx) or create_user_config()
        bookmark_service = create_bookmark_service(user_config._config)

        # Determine source filter
        source_filter = None
        if factory_only:
            source_filter = BookmarkSource.FACTORY
        elif user_only:
            source_filter = BookmarkSource.USER

        bookmarks = bookmark_service.list_bookmarks(source_filter)

        if not bookmarks:
            typer.echo(
                Icons.format_with_icon("MAILBOX", "No bookmarks found.", icon_mode)
            )
            return

        # Group bookmarks by source
        factory_bookmarks = [b for b in bookmarks if b.source == BookmarkSource.FACTORY]
        user_bookmarks = [b for b in bookmarks if b.source == BookmarkSource.USER]

        typer.echo(
            Icons.format_with_icon(
                "DOCUMENT", f"Found {len(bookmarks)} bookmarks:", icon_mode
            )
        )
        typer.echo()

        if factory_bookmarks and not user_only:
            typer.echo(
                Icons.format_with_icon(
                    "FACTORY",
                    f"Factory defaults ({len(factory_bookmarks)}):",
                    icon_mode,
                )
            )
            for bookmark in factory_bookmarks:
                typer.echo(
                    f"   {Icons.get_icon('BOOKMARK', icon_mode)} {bookmark.name}"
                )
                if bookmark.title:
                    typer.echo(
                        f"      {Icons.get_icon('DOCUMENT', icon_mode)} {bookmark.title}"
                    )
                typer.echo()

        if user_bookmarks and not factory_only:
            typer.echo(
                Icons.format_with_icon(
                    "USER", f"User bookmarks ({len(user_bookmarks)}):", icon_mode
                )
            )
            for bookmark in user_bookmarks:
                typer.echo(f"   {Icons.get_icon('TAG', icon_mode)} {bookmark.name}")
                if bookmark.title:
                    typer.echo(
                        f"      {Icons.get_icon('DOCUMENT', icon_mode)} {bookmark.title}"
                    )
                typer.echo()

        typer.echo(
            Icons.format_with_icon(
                "INFO",
                "Use 'glovebox bookmarks clone <name> [--output <file>]' to clone",
                icon_mode,
            )
        )
        typer.echo(
            Icons.format_with_icon(
                "INFO",
                "Use 'glovebox bookmarks flash <name> --profile <profile>' to flash",
                icon_mode,
            )
        )

    except Exception as e:
        typer.echo(
            Icons.format_with_icon("ERROR", f"Error listing bookmarks: {e}", icon_mode)
        )
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
        str | None,
        typer.Option(
            "--output",
            "-o",
            help="Output file path for the cloned layout. Use '-' for stdout. If not specified, generates a smart default filename.",
        ),
    ] = None,
) -> None:
    """Clone a bookmarked layout to a local file."""
    import sys

    from glovebox.cli.helpers.theme import Icons
    from glovebox.utils.filename_generator import FileType, generate_default_filename
    from glovebox.utils.filename_helpers import (
        extract_bookmark_data,
        extract_layout_dict_data,
    )

    try:
        from glovebox.cli.helpers.profile import get_user_config_from_context
        from glovebox.config import create_user_config

        user_config = get_user_config_from_context(ctx) or create_user_config()
        bookmark_service = create_bookmark_service(user_config._config)

        # Get bookmark
        bookmark = bookmark_service.get_bookmark(name)
        from glovebox.cli.app import AppContext

        app_ctx: AppContext = ctx.obj
        icon_mode = app_ctx.icon_mode

        if not bookmark:
            typer.echo(
                Icons.format_with_icon(
                    "ERROR", f"Bookmark '{name}' not found.", icon_mode
                )
            )
            raise typer.Exit(1)

        # Get full layout data
        layout = bookmark_service.get_layout_by_bookmark(name)

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
                layout_dict = layout.config.model_dump(by_alias=True)
                layout_data = extract_layout_dict_data(layout_dict)
                bookmark_data = extract_bookmark_data(
                    name, layout_dict.get("title", "")
                )

                # Combine layout and bookmark data for better templating
                combined_data = {**layout_data, **bookmark_data}

                default_filename = generate_default_filename(
                    FileType.LAYOUT_JSON,
                    user_config._config.filename_templates,
                    layout_data=combined_data,
                    original_filename=f"{name}.json",
                )
                output_path = Path(default_filename)
            else:
                output_path = Path(output)

            # Save the config part (the actual layout data)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(layout_json)

            typer.echo(
                Icons.format_with_icon(
                    "SUCCESS", "Layout cloned successfully!", icon_mode
                )
            )
            typer.echo(
                Icons.format_with_icon("TAG", f"Bookmark: {bookmark.name}", icon_mode)
            )
            typer.echo(
                Icons.format_with_icon(
                    "DOCUMENT", f"Title: {layout.layout_meta.title}", icon_mode
                )
            )
            typer.echo(
                Icons.format_with_icon("SAVE", f"Saved to: {output_path}", icon_mode)
            )

    except Exception as e:
        from glovebox.cli.helpers.theme import get_icon_mode_from_context

        error_icon_mode = get_icon_mode_from_context(ctx)
        typer.echo(
            Icons.format_with_icon(
                "ERROR", f"Error cloning bookmark: {e}", error_icon_mode
            )
        )
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
    from glovebox.cli.helpers.theme import Icons, get_icon_mode_from_context

    icon_mode = get_icon_mode_from_context(ctx)

    try:
        from glovebox.cli.helpers.profile import get_user_config_from_context
        from glovebox.config import create_user_config

        user_config = get_user_config_from_context(ctx) or create_user_config()
        bookmark_service = create_bookmark_service(user_config._config)

        # Get bookmark
        bookmark = bookmark_service.get_bookmark(name)
        if not bookmark:
            typer.echo(
                Icons.format_with_icon(
                    "ERROR", f"Bookmark '{name}' not found.", icon_mode
                )
            )
            raise typer.Exit(1)

        # Parse profile
        try:
            from glovebox.cli.helpers.profile import create_profile_from_context

            keyboard_profile = create_profile_from_context(ctx, profile)
        except Exception as e:
            typer.echo(
                Icons.format_with_icon(
                    "ERROR", f"Invalid profile '{profile}': {e}", icon_mode
                )
            )
            raise typer.Exit(1) from e

        # Get app context for session metrics
        from glovebox.cli.app import AppContext

        app_ctx: AppContext = ctx.obj

        # Get layout metadata to check compilation status
        layout_meta = bookmark_service._client.get_layout_meta(
            bookmark.uuid, use_cache=True
        )

        typer.echo(
            Icons.format_with_icon(
                "FLASH", f"Flashing bookmark '{bookmark.name}'...", icon_mode
            )
        )

        # Check if we can use MoErgo's compiled firmware
        if layout_meta["layout_meta"]["compiled"]:
            typer.echo(
                Icons.format_with_icon(
                    "BUILD",
                    "Using pre-compiled firmware from MoErgo servers",
                    icon_mode,
                )
            )

            # Use MoErgo's compile and download workflow
            layout = bookmark_service.get_layout_by_bookmark(name)

            # Import layout service to convert to ZMK format
            from glovebox.adapters import create_file_adapter, create_template_adapter
            from glovebox.layout import (
                create_behavior_registry,
                create_grid_layout_formatter,
                create_layout_component_service,
                create_layout_display_service,
                create_layout_service,
            )
            from glovebox.layout.behavior.formatter import BehaviorFormatterImpl
            from glovebox.layout.zmk_generator import ZmkFileContentGenerator

            # Create all dependencies for layout service
            file_adapter = create_file_adapter()
            template_adapter = create_template_adapter()
            behavior_registry = create_behavior_registry()
            behavior_formatter = BehaviorFormatterImpl(behavior_registry)
            dtsi_generator = ZmkFileContentGenerator(behavior_formatter)
            layout_generator = create_grid_layout_formatter()
            component_service = create_layout_component_service(file_adapter)
            layout_display_service = create_layout_display_service(layout_generator)

            layout_service = create_layout_service(
                file_adapter=file_adapter,
                template_adapter=template_adapter,
                behavior_registry=behavior_registry,
                component_service=component_service,
                layout_service=layout_display_service,
                behavior_formatter=behavior_formatter,
                dtsi_generator=dtsi_generator,
            )

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
                    session_metrics=app_ctx.session_metrics,
                    force=True,
                )

                if not result.success:
                    typer.echo(
                        Icons.format_with_icon(
                            "ERROR",
                            f"Failed to generate ZMK files: {'; '.join(result.errors)}",
                            icon_mode,
                        )
                    )
                    raise typer.Exit(1)

                # Read the generated files
                keymap_file = temp_output.with_suffix(".keymap")
                config_file = temp_output.with_suffix(".conf")

                keymap_content = keymap_file.read_text()
                config_content = config_file.read_text() if config_file.exists() else ""

                # Compile firmware using MoErgo API
                typer.echo(
                    Icons.format_with_icon(
                        "BUILD", "Compiling firmware on MoErgo servers...", icon_mode
                    )
                )
                compile_response = bookmark_service._client.compile_firmware(
                    layout_uuid=bookmark.uuid,
                    keymap=keymap_content,
                    kconfig=config_content,
                    board=keyboard_profile.keyboard_name or "glove80",
                    firmware_version=keyboard_profile.firmware_version or "v25.05",
                )

                # Download firmware
                typer.echo(
                    Icons.format_with_icon(
                        "DOWNLOAD", "Downloading compiled firmware...", icon_mode
                    )
                )
                firmware_path = Path(f"{bookmark.name}.uf2")
                firmware_data = bookmark_service._client.download_firmware(
                    firmware_location=compile_response.location,
                    output_path=str(firmware_path),
                )

                # Flash the firmware
                from glovebox.adapters import create_file_adapter
                from glovebox.firmware.flash import create_flash_service
                from glovebox.firmware.flash.device_wait_service import (
                    create_device_wait_service,
                )

                file_adapter = create_file_adapter()
                device_wait_service = create_device_wait_service()
                flash_service = create_flash_service(file_adapter, device_wait_service)

                typer.echo("⚡ Flashing firmware to keyboard...")
                flash_result = flash_service.flash_from_file(
                    firmware_file_path=firmware_path, profile=keyboard_profile
                )

                if flash_result.success:
                    typer.echo(
                        Icons.format_with_icon(
                            "SUCCESS", "Firmware flashed successfully!", icon_mode
                        )
                    )
                else:
                    typer.echo(
                        Icons.format_with_icon(
                            "ERROR",
                            f"Flash failed: {'; '.join(flash_result.errors)}",
                            icon_mode,
                        )
                    )
                    raise typer.Exit(1)
        else:
            typer.echo(
                Icons.format_with_icon(
                    "WARNING",
                    "Layout not compiled on MoErgo servers. Compile locally first.",
                    icon_mode,
                )
            )
            typer.echo(
                Icons.format_with_icon(
                    "INFO",
                    "Use 'glovebox layout compile' to build firmware locally",
                    icon_mode,
                )
            )

    except Exception as e:
        typer.echo(
            Icons.format_with_icon("ERROR", f"Error flashing bookmark: {e}", icon_mode)
        )
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
    from glovebox.cli.helpers.theme import Icons, get_icon_mode_from_context

    icon_mode = get_icon_mode_from_context(ctx)

    try:
        from glovebox.cli.helpers.profile import get_user_config_from_context
        from glovebox.config import create_user_config

        user_config = get_user_config_from_context(ctx) or create_user_config()
        bookmark_service = create_bookmark_service(user_config._config)

        # Check if bookmark exists
        bookmark = bookmark_service.get_bookmark(name)
        if not bookmark:
            typer.echo(
                Icons.format_with_icon(
                    "ERROR", f"Bookmark '{name}' not found", icon_mode
                )
            )
            raise typer.Exit(1)

        # Ask for confirmation unless --force is used
        if not force:
            confirm = typer.confirm(f"Remove bookmark '{name}'?")
            if not confirm:
                typer.echo(
                    Icons.format_with_icon("ERROR", "Operation cancelled", icon_mode)
                )
                return

        # Remove the bookmark
        success = bookmark_service.remove_bookmark(name)
        if success:
            typer.echo(
                Icons.format_with_icon(
                    "SUCCESS", f"Bookmark '{name}' removed successfully!", icon_mode
                )
            )
        else:
            typer.echo(
                Icons.format_with_icon(
                    "ERROR", f"Failed to remove bookmark '{name}'", icon_mode
                )
            )
            raise typer.Exit(1)

    except Exception as e:
        typer.echo(
            Icons.format_with_icon("ERROR", f"Error removing bookmark: {e}", icon_mode)
        )
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
    from glovebox.cli.helpers.theme import Icons, get_icon_mode_from_context

    icon_mode = get_icon_mode_from_context(ctx)

    try:
        from glovebox.cli.helpers.profile import get_user_config_from_context
        from glovebox.config import create_user_config

        user_config = get_user_config_from_context(ctx) or create_user_config()
        bookmark_service = create_bookmark_service(user_config._config)

        # Get bookmark info
        bookmark = bookmark_service.get_bookmark(name)
        if not bookmark:
            typer.echo(
                Icons.format_with_icon(
                    "ERROR", f"Bookmark '{name}' not found", icon_mode
                )
            )
            raise typer.Exit(1)

        # Display bookmark information
        typer.echo(Icons.format_with_icon("TAG", f"Name: {bookmark.name}", icon_mode))
        typer.echo(Icons.format_with_icon("LINK", f"UUID: {bookmark.uuid}", icon_mode))
        if bookmark.title:
            typer.echo(
                Icons.format_with_icon(
                    "DOCUMENT", f"Title: {bookmark.title}", icon_mode
                )
            )
        if bookmark.description:
            typer.echo(
                Icons.format_with_icon(
                    "INFO", f"Description: {bookmark.description}", icon_mode
                )
            )
        if bookmark.tags:
            typer.echo(
                Icons.format_with_icon(
                    "TAG", f"Tags: {', '.join(bookmark.tags)}", icon_mode
                )
            )
        typer.echo(
            Icons.format_with_icon(
                "FOLDER",
                f"Source: {bookmark.source.value if hasattr(bookmark.source, 'value') else bookmark.source}",
                icon_mode,
            )
        )

    except Exception as e:
        typer.echo(
            Icons.format_with_icon(
                "ERROR", f"Error getting bookmark info: {e}", icon_mode
            )
        )
        raise typer.Exit(1) from e


@bookmarks_app.command()
def refresh(
    ctx: typer.Context,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Refresh factory default bookmarks from MoErgo API."""
    from glovebox.cli.helpers.theme import Icons, get_icon_mode_from_context

    icon_mode = get_icon_mode_from_context(ctx)

    try:
        from glovebox.cli.helpers.profile import get_user_config_from_context
        from glovebox.config import create_user_config

        user_config = get_user_config_from_context(ctx) or create_user_config()
        bookmark_service = create_bookmark_service(user_config._config)

        # Ask for confirmation unless --force is used
        if not force:
            confirm = typer.confirm("Refresh factory default bookmarks?")
            if not confirm:
                typer.echo(
                    Icons.format_with_icon("ERROR", "Operation cancelled", icon_mode)
                )
                return

        # Refresh factory defaults
        count = bookmark_service.refresh_factory_defaults()
        typer.echo(
            Icons.format_with_icon(
                "SUCCESS", f"Refreshed {count} factory default bookmarks!", icon_mode
            )
        )

    except Exception as e:
        typer.echo(
            Icons.format_with_icon(
                "ERROR", f"Error refreshing factory bookmarks: {e}", icon_mode
            )
        )
        raise typer.Exit(1) from e


def register_commands(app: typer.Typer) -> None:
    """Register bookmark commands with the main app."""
    app.add_typer(bookmarks_app, name="bookmarks")
