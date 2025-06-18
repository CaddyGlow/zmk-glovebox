"""MoErgo API commands for downloading layouts."""

import json
import logging
from pathlib import Path
from typing import Annotated

import typer

from glovebox.moergo.client import create_moergo_client
from glovebox.moergo.client.models import AuthenticationError, NetworkError


logger = logging.getLogger(__name__)

moergo_app = typer.Typer(
    name="moergo",
    help="""MoErgo API operations for downloading and managing layouts.

Authentication can be done interactively, with command line options, or environment variables:
• Interactive: glovebox moergo login
• Environment: MOERGO_USERNAME=user@email.com MOERGO_PASSWORD=*** glovebox moergo login""",
)


@moergo_app.command("login")
def login(
    username: Annotated[
        str | None, typer.Option("--username", "-u", help="MoErgo username/email")
    ] = None,
    password: Annotated[
        str | None,
        typer.Option(
            "--password",
            "-p",
            help="MoErgo password (not recommended, use prompt or env)",
            hide_input=True,
        ),
    ] = None,
) -> None:
    """Login to MoErgo and store credentials securely.

    Interactive mode: glovebox moergo login
    With username: glovebox moergo login --username user@email.com
    Environment variables: MOERGO_USERNAME and MOERGO_PASSWORD
    """
    import os

    try:
        # Get username from parameter, environment, or prompt
        if username is None:
            username = os.getenv("MOERGO_USERNAME")
        if username is None:
            username = typer.prompt("Username/Email")

        # Get password from parameter, environment, or prompt
        if password is None:
            password = os.getenv("MOERGO_PASSWORD")
        if password is None:
            password = typer.prompt("Password", hide_input=True)

        client = create_moergo_client()
        client.login(username, password)

        info = client.get_credential_info()
        storage_method = (
            "OS keyring" if info.get("keyring_available") else "encrypted file"
        )

        typer.echo(
            f"✅ Successfully logged in and stored credentials using {storage_method}"
        )

    except AuthenticationError as e:
        typer.echo(f"❌ Login failed: {e}")
        raise typer.Exit(1) from None
    except Exception as e:
        typer.echo(f"❌ Unexpected error: {e}")
        raise typer.Exit(1) from None


@moergo_app.command("logout")
def logout() -> None:
    """Clear stored MoErgo credentials."""
    try:
        client = create_moergo_client()
        client.logout()
        typer.echo("✅ Successfully logged out and cleared credentials")

    except Exception as e:
        typer.echo(f"❌ Error during logout: {e}")
        raise typer.Exit(1) from None


@moergo_app.command("download")
def download_layout(
    layout_id: Annotated[str, typer.Argument(help="Layout UUID to download")],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output", "-o", help="Output file path (defaults to <layout_id>.json)"
        ),
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Overwrite existing file")
    ] = False,
) -> None:
    """Download a layout by ID from MoErgo."""
    try:
        client = create_moergo_client()

        # Check if authenticated
        if not client.is_authenticated():
            typer.echo(
                "❌ Not authenticated. Please run 'glovebox moergo login' first."
            )
            raise typer.Exit(1)

        typer.echo(f"Downloading layout {layout_id}...")

        # Download the layout
        layout = client.get_layout(layout_id)

        # Determine output path
        if output is None:
            output = Path(f"{layout_id}.json")

        # Check if file exists
        if output.exists() and not force:
            typer.echo(f"❌ File {output} already exists. Use --force to overwrite.")
            raise typer.Exit(1)

        # Convert to layout data and save
        layout_data = layout.config.model_dump(mode="json")

        # Add metadata from layout_meta
        layout_data["_moergo_meta"] = {
            "uuid": layout.layout_meta.uuid,
            "title": layout.layout_meta.title,
            "creator": layout.layout_meta.creator,
            "date": layout.layout_meta.date,
            "notes": layout.layout_meta.notes,
            "tags": layout.layout_meta.tags,
        }

        # Write to file
        with output.open("w") as f:
            json.dump(layout_data, f, indent=2)

        typer.echo(f"✅ Layout '{layout.layout_meta.title}' saved to {output}")
        typer.echo(f"   Creator: {layout.layout_meta.creator}")
        typer.echo(f"   Created: {layout.layout_meta.created_datetime}")

        if layout.layout_meta.notes:
            typer.echo(f"   Notes: {layout.layout_meta.notes}")

        if layout.layout_meta.tags:
            typer.echo(f"   Tags: {', '.join(layout.layout_meta.tags)}")

    except AuthenticationError as e:
        typer.echo(f"❌ Authentication error: {e}")
        typer.echo("Try running 'glovebox moergo login' first.")
        raise typer.Exit(1) from None
    except NetworkError as e:
        typer.echo(f"❌ Network error: {e}")
        raise typer.Exit(1) from None
    except Exception as e:
        typer.echo(f"❌ Error downloading layout: {e}")
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception("Full error details")
        raise typer.Exit(1) from None


@moergo_app.command("status")
def status() -> None:
    """Show MoErgo authentication status and credential information."""
    try:
        client = create_moergo_client()
        info = client.get_credential_info()

        typer.echo("MoErgo Authentication Status:")
        typer.echo(
            f"  Authenticated: {'✅ Yes' if client.is_authenticated() else '❌ No'}"
        )
        typer.echo(
            f"  Keyring Available: {'✅ Yes' if info.get('keyring_available') else '❌ No'}"
        )
        typer.echo(f"  Platform: {info.get('platform', 'Unknown')}")
        typer.echo(f"  Config Directory: {info.get('config_dir', 'Unknown')}")

        if info.get("keyring_backend"):
            typer.echo(f"  Keyring Backend: {info['keyring_backend']}")

        if not client.is_authenticated():
            typer.echo("\n💡 To authenticate:")
            typer.echo("   Interactive: glovebox moergo login")
            typer.echo(
                "   With env vars: MOERGO_USERNAME=user@email.com MOERGO_PASSWORD=*** glovebox moergo login"
            )

    except Exception as e:
        typer.echo(f"❌ Error checking status: {e}")
        raise typer.Exit(1) from None


def register_commands(app: typer.Typer) -> None:
    """Register MoErgo commands with the main app."""
    app.add_typer(moergo_app, name="moergo")
