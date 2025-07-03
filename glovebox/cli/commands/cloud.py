"""Essential cloud operations for syncing layouts with Glove80 cloud service."""

from __future__ import annotations

import builtins
import logging
import uuid as uuid_lib
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

import typer

from glovebox.adapters import create_file_adapter
from glovebox.cli.core.command_base import IOCommand
from glovebox.cli.decorators.error_handling import handle_errors
from glovebox.cli.helpers.library_resolver import resolve_parameter_value
from glovebox.cli.helpers.parameters import complete_json_files
from glovebox.layout.utils.json_operations import load_layout_file
from glovebox.moergo.client import create_moergo_client


logger = logging.getLogger(__name__)

# Create a typer app for cloud commands
cloud_app = typer.Typer(
    name="cloud",
    help="Essential cloud operations for Glove80 layouts",
    no_args_is_help=True,
)


class UploadLayoutCommand(IOCommand):
    """Command to upload a layout file to Glove80 cloud service."""

    def execute(
        self,
        ctx: typer.Context,
        layout_file: str,
        title: str | None,
        uuid: str | None,
        notes: str | None,
        tags: builtins.list[str] | None,
        unlisted: bool,
    ) -> None:
        """Execute the upload layout command."""
        try:
            # Validate authentication
            client = create_moergo_client()
            if not client.validate_authentication():
                self.console.print_error(
                    "Authentication failed. Please run 'glovebox moergo login' first."
                )
                raise typer.Exit(1)

            # Load JSON input using IOCommand method
            layout_data = self.load_json_input(layout_file)

            # Generate UUID if not provided
            layout_uuid = uuid or str(uuid_lib.uuid4())

            # Create layout metadata
            layout_meta = {
                "uuid": layout_uuid,
                "date": int(datetime.now().timestamp()),
                "creator": "glovebox-user",
                "parent_uuid": None,
                "firmware_api_version": "v25.05",
                "title": title or layout_data.get("title", "Untitled Layout"),
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
                "config": layout_data,
            }

            # Upload the layout
            from glovebox.cli.helpers.theme import Icons

            icon = Icons.get_icon("UPLOAD", self.console.icon_mode)
            self.console.console.print(
                f"{icon} Uploading layout '{layout_meta['title']}' with UUID: {layout_uuid}",
                style="info",
            )

            response = client.save_layout(layout_uuid, complete_layout)
            self.console.print_success("Layout uploaded successfully!")

            # Print details
            link_icon = Icons.get_icon("LINK", self.console.icon_mode)
            self.console.console.print(f"{link_icon} UUID: {layout_uuid}")
            doc_icon = Icons.get_icon("DOCUMENT", self.console.icon_mode)
            self.console.console.print(f"{doc_icon} Title: {layout_meta['title']}")

        except Exception as e:
            self.handle_service_error(e, "upload layout")


class DownloadLayoutCommand(IOCommand):
    """Command to download a layout from Glove80 cloud service."""

    def execute(
        self,
        ctx: typer.Context,
        layout_uuid: str,
        output: str | None,
    ) -> None:
        """Execute the download layout command."""
        try:
            # Validate authentication
            client = create_moergo_client()
            if not client.validate_authentication():
                self.console.print_error(
                    "Authentication failed. Please run 'glovebox moergo login' first."
                )
                raise typer.Exit(1)

            # Download the layout
            layout = client.get_layout(layout_uuid)
            layout_data = layout.config.model_dump(by_alias=True, mode="json")

            # Write output using IOCommand method
            if output == "-":
                # Output to stdout
                self.format_and_print(layout_data, "json")
            else:
                # Determine output path
                if output is None:
                    # Generate smart default filename
                    from glovebox.config import create_user_config
                    from glovebox.utils.filename_generator import (
                        FileType,
                        generate_default_filename,
                    )
                    from glovebox.utils.filename_helpers import extract_layout_dict_data

                    user_config = create_user_config()
                    layout_template_data = extract_layout_dict_data(layout_data)

                    default_filename = generate_default_filename(
                        FileType.LAYOUT_JSON,
                        user_config._config.filename_templates,
                        layout_data=layout_template_data,
                        original_filename=f"{layout_uuid}.json",
                    )
                    output = default_filename

                # Write to file
                self.write_output(layout_data, output, "json")

                from glovebox.cli.helpers.theme import Icons

                save_icon = Icons.get_icon("SAVE", self.console.icon_mode)
                self.console.console.print(f"{save_icon} Downloaded to: {output}")

        except Exception as e:
            self.handle_service_error(e, "download layout")

    def handle_service_error(self, error: Exception, operation: str) -> None:
        """Handle service layer errors with consistent messaging."""
        exc_info = logger.isEnabledFor(logging.DEBUG)
        logger.error("Failed to %s: %s", operation, error, exc_info=exc_info)
        self.console.print_error(f"Failed to {operation}: {error}")
        raise typer.Exit(1) from error


class ListLayoutsCommand(IOCommand):
    """Command to list user's layouts from Glove80 cloud service."""

    def execute(
        self,
        ctx: typer.Context,
        tags: builtins.list[str] | None,
    ) -> None:
        """Execute the list layouts command."""
        try:
            # Validate authentication
            client = create_moergo_client()
            if not client.validate_authentication():
                self.console.print_error(
                    "Authentication failed. Please run 'glovebox moergo login' first."
                )
                raise typer.Exit(1)

            # List layouts
            layouts = client.list_user_layouts()

            if not layouts:
                from glovebox.cli.helpers.theme import Icons

                mailbox_icon = Icons.get_icon("MAILBOX", self.console.icon_mode)
                self.console.console.print(f"{mailbox_icon} No layouts found.")
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

            # Display results
            from glovebox.cli.helpers.theme import Icons

            doc_icon = Icons.get_icon("DOCUMENT", self.console.icon_mode)
            self.console.console.print(f"{doc_icon} Found {len(layouts)} layouts:")
            self.console.console.print()

            for layout in layouts:
                link_icon = Icons.get_icon("LINK", self.console.icon_mode)
                self.console.console.print(f"   {link_icon} {layout['uuid']}")

            self.console.console.print()
            self.console.print_info(
                "Use 'glovebox cloud download <uuid> [--output <file>]' to download a layout"
            )

        except Exception as e:
            self.handle_service_error(e, "list layouts")

    def handle_service_error(self, error: Exception, operation: str) -> None:
        """Handle service layer errors with consistent messaging."""
        exc_info = logger.isEnabledFor(logging.DEBUG)
        logger.error("Failed to %s: %s", operation, error, exc_info=exc_info)
        self.console.print_error(f"Failed to {operation}: {error}")
        raise typer.Exit(1) from error


class BrowseLayoutsCommand(IOCommand):
    """Command to browse public layouts from Glove80 community."""

    def execute(self, ctx: typer.Context) -> None:
        """Execute the browse layouts command."""
        try:
            self.console.print_info("Opening Glove80 cloud service in browser...")

            import webbrowser

            webbrowser.open("https://my.glove80.com")
            self.console.print_success("Browser opened successfully")

        except Exception as e:
            self.handle_service_error(e, "browse layouts")

    def handle_service_error(self, error: Exception, operation: str) -> None:
        """Handle service layer errors with consistent messaging."""
        exc_info = logger.isEnabledFor(logging.DEBUG)
        logger.error("Failed to %s: %s", operation, error, exc_info=exc_info)
        self.console.print_error(f"Failed to {operation}: {error}")
        raise typer.Exit(1) from error


class DeleteLayoutCommand(IOCommand):
    """Command to delete a layout from Glove80 cloud service."""

    def execute(
        self,
        ctx: typer.Context,
        layout_uuid: str,
    ) -> None:
        """Execute the delete layout command."""
        try:
            # Validate authentication
            client = create_moergo_client()
            if not client.validate_authentication():
                self.console.print_error(
                    "Authentication failed. Please run 'glovebox moergo login' first."
                )
                raise typer.Exit(1)

            # Confirm deletion
            self.console.print_warning(
                f"This will permanently delete layout: {layout_uuid}"
            )
            if not typer.confirm("Are you sure?"):
                self.console.print_info("Operation cancelled")
                return

            # Delete the layout
            client.delete_layout(layout_uuid)
            self.console.print_success(f"Layout {layout_uuid} deleted successfully")

        except Exception as e:
            self.handle_service_error(e, "delete layout")

    def handle_service_error(self, error: Exception, operation: str) -> None:
        """Handle service layer errors with consistent messaging."""
        exc_info = logger.isEnabledFor(logging.DEBUG)
        logger.error("Failed to %s: %s", operation, error, exc_info=exc_info)
        self.console.print_error(f"Failed to {operation}: {error}")
        raise typer.Exit(1) from error


@cloud_app.command()
@handle_errors
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
    command = UploadLayoutCommand()
    command.execute(ctx, layout_file, title, uuid, notes, tags, unlisted)


@cloud_app.command()
@handle_errors
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
    command = DownloadLayoutCommand()
    command.execute(ctx, layout_uuid, output)


@cloud_app.command()
@handle_errors
def list(
    ctx: typer.Context,
    tags: Annotated[
        builtins.list[str] | None,
        typer.Option("--tags", help="Filter by tags (can use multiple times)"),
    ] = None,
) -> None:
    """List all user's layouts from Glove80 cloud service."""
    command = ListLayoutsCommand()
    command.execute(ctx, tags)


@cloud_app.command()
@handle_errors
def browse(ctx: typer.Context) -> None:
    """Browse layouts in the Glove80 cloud service."""
    command = BrowseLayoutsCommand()
    command.execute(ctx)


@cloud_app.command()
@handle_errors
def delete(
    ctx: typer.Context,
    layout_uuid: Annotated[str, typer.Argument(help="UUID of the layout to delete")],
) -> None:
    """Delete a layout from Glove80 cloud service."""
    command = DeleteLayoutCommand()
    command.execute(ctx, layout_uuid)


def register_commands(app: typer.Typer) -> None:
    """Register cloud commands with the main app."""
    app.add_typer(cloud_app)
