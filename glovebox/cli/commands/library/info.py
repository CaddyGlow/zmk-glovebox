"""Library info command for showing detailed layout information."""

from typing import Annotated

import typer

from glovebox.cli.decorators import handle_errors, with_metrics
from glovebox.cli.helpers.theme import Icons, get_icon_mode_from_context
from glovebox.config import create_user_config
from glovebox.library import create_library_service


info_app = typer.Typer(help="Show detailed information about a layout")


def complete_layout_name(incomplete: str) -> list[str]:
    """Tab completion for layout names and UUIDs."""
    try:
        user_config = create_user_config()
        library_service = create_library_service(user_config._config)
        entries = library_service.list_local_layouts()

        # Return both names and UUIDs that match
        matches = []
        for entry in entries:
            if entry.name.startswith(incomplete):
                matches.append(entry.name)
            if entry.uuid.startswith(incomplete):
                matches.append(entry.uuid)

        return matches[:10]  # Limit to 10 matches
    except Exception:
        return []


@info_app.command()
@handle_errors
@with_metrics("library_info")
def info(
    ctx: typer.Context,
    identifier: Annotated[
        str,
        typer.Argument(help="Layout UUID or name", autocompletion=complete_layout_name),
    ],
    show_content: Annotated[
        bool, typer.Option("--content", "-c", help="Show layout content preview")
    ] = False,
    format_type: Annotated[
        str, typer.Option("--format", "-f", help="Output format")
    ] = "table",
) -> None:
    """Show detailed information about a layout in the library.

    The identifier can be either a UUID or a layout name.

    Examples:
        glovebox library info my-layout
        glovebox library info 12345678-1234-1234-1234-123456789abc
        glovebox library info my-layout --content
        glovebox library info my-layout --format json
    """
    icon_mode = get_icon_mode_from_context(ctx)

    try:
        # Create user config and library service
        user_config = create_user_config()
        library_service = create_library_service(user_config._config)

        # Try to find entry by UUID first, then by name
        entry = library_service.get_layout_entry(identifier)
        if entry is None:
            entry = library_service.get_layout_entry_by_name(identifier)

        if entry is None:
            typer.echo(
                Icons.format_with_icon(
                    "ERROR", f"Layout not found: {identifier}", icon_mode
                )
            )
            typer.echo(
                Icons.format_with_icon(
                    "INFO",
                    "Use 'glovebox library list' to see available layouts",
                    icon_mode,
                )
            )
            raise typer.Exit(1)

        if format_type == "json":
            import json

            data = entry.model_dump(mode="json")
            if show_content:
                content = library_service.get_layout_content(entry.uuid)
                if content:
                    data["content"] = content
            typer.echo(json.dumps(data, indent=2, default=str))
            return

        # Table format
        typer.echo(
            Icons.format_with_icon(
                "LAYOUT", f"Layout Information: {entry.name}", icon_mode
            )
        )
        typer.echo()

        # Basic information
        typer.echo(f"   Name: {entry.name}")
        if entry.title and entry.title != entry.name:
            typer.echo(f"   Title: {entry.title}")
        typer.echo(f"   UUID: {entry.uuid}")

        if entry.creator:
            typer.echo(f"   Creator: {entry.creator}")

        typer.echo(f"   Source Type: {entry.source.value}")
        typer.echo(f"   Source Reference: {entry.source_reference}")
        typer.echo(
            f"   Downloaded: {entry.downloaded_at.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        if entry.tags:
            typer.echo(f"   Tags: {', '.join(entry.tags)}")

        if entry.notes:
            typer.echo(f"   Notes: {entry.notes}")

        typer.echo(f"   File Path: {entry.file_path}")

        # File information
        if entry.file_path.exists():
            file_stat = entry.file_path.stat()
            file_size_kb = file_stat.st_size / 1024
            typer.echo(f"   File Size: {file_size_kb:.1f} KB")
            typer.echo(
                Icons.format_with_icon(
                    "SUCCESS", "File exists and is accessible", icon_mode
                )
            )
        else:
            typer.echo(
                Icons.format_with_icon("ERROR", "File not found on disk", icon_mode)
            )

        # Show content preview if requested
        if show_content:
            content = library_service.get_layout_content(entry.uuid)
            if content:
                typer.echo()
                typer.echo(
                    Icons.format_with_icon(
                        "DOCUMENT", "Layout Content Preview:", icon_mode
                    )
                )

                # Show key fields from content
                if isinstance(content, dict):
                    if "title" in content:
                        typer.echo(f"   Content Title: {content['title']}")
                    if "layers" in content and isinstance(content["layers"], list):
                        typer.echo(f"   Layers: {len(content['layers'])}")
                        for i, layer in enumerate(
                            content["layers"][:5]
                        ):  # Show first 5 layers
                            if isinstance(layer, dict) and "name" in layer:
                                typer.echo(f"      {i}: {layer['name']}")
                    if "_moergo_meta" in content:
                        meta = content["_moergo_meta"]
                        typer.echo(f"   MoErgo Metadata: {meta.get('title', 'N/A')}")

                # Show file size info
                import json

                content_json = json.dumps(content, indent=2)
                content_size_kb = len(content_json.encode("utf-8")) / 1024
                typer.echo(f"   Content Size: {content_size_kb:.1f} KB")
            else:
                typer.echo(
                    Icons.format_with_icon(
                        "WARNING", "Could not read layout content", icon_mode
                    )
                )

        typer.echo()
        typer.echo(
            Icons.format_with_icon(
                "INFO",
                "Use 'glovebox library remove <uuid>' to remove this layout",
                icon_mode,
            )
        )

    except Exception as e:
        typer.echo(Icons.format_with_icon("ERROR", f"Unexpected error: {e}", icon_mode))
        raise typer.Exit(1) from e


# Make info the default command
@info_app.callback(invoke_without_command=True)
def info_default(
    ctx: typer.Context,
    identifier: Annotated[
        str | None, typer.Argument(autocompletion=complete_layout_name)
    ] = None,
    show_content: Annotated[bool, typer.Option("--content", "-c")] = False,
    format_type: Annotated[str, typer.Option("--format", "-f")] = "table",
) -> None:
    """Show detailed information about a layout."""
    if ctx.invoked_subcommand is None:
        if identifier is None:
            typer.echo("Error: Missing layout identifier")
            raise typer.Exit(1)

        info(ctx, identifier, show_content, format_type)
