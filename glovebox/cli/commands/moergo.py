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
• Environment: MOERGO_USERNAME=user@email.com MOERGO_PASSWORD=*** glovebox moergo login

Credential Storage:
• Automatically uses OS keyring (macOS Keychain, Windows Credential Manager, Linux keyring)
• Falls back to encrypted file storage if keyring unavailable
• Use 'glovebox moergo keystore' to see detailed storage information
• Install 'keyring' package for enhanced security: pip install keyring""",
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
        keyring_available = info.get("keyring_available", False)

        if keyring_available:
            storage_method = "OS keyring"
            typer.echo(
                f"✅ Successfully logged in and stored credentials using {storage_method}"
            )
            typer.echo("🔒 Your credentials are securely stored in your system keyring")
        else:
            storage_method = "file with basic obfuscation"
            typer.echo(
                f"✅ Successfully logged in and stored credentials using {storage_method}"
            )
            typer.echo(
                "⚠️  For better security, consider installing the keyring package:"
            )
            typer.echo("   pip install keyring")
            typer.echo("   Then login again to use secure keyring storage")

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

        # Check if authenticated with server validation
        if not client.validate_authentication():
            typer.echo(
                "❌ Authentication failed. Please run 'glovebox moergo login' first."
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

        # Check authentication status
        is_auth = client.is_authenticated()
        typer.echo(f"  Authenticated: {'✅ Yes' if is_auth else '❌ No'}")

        # Show token info if authenticated
        if is_auth:
            try:
                token_info = client.get_token_info()
                if token_info.get("expires_in_minutes") is not None:
                    expires_in = token_info["expires_in_minutes"]
                    if expires_in > 60:
                        expires_str = f"{expires_in / 60:.1f} hours"
                    else:
                        expires_str = f"{expires_in:.1f} minutes"
                    typer.echo(f"  Token expires in: {expires_str}")

                    if token_info.get("needs_renewal", False):
                        typer.echo("  ⚠️  Token needs renewal soon")
            except Exception:
                pass  # Don't fail if we can't get token info

        # Credential storage info
        has_creds = info.get("has_credentials", False)
        storage_method = (
            "OS keyring" if info.get("keyring_available") else "file storage"
        )

        typer.echo(f"  Credentials stored: {'✅ Yes' if has_creds else '❌ No'}")
        if has_creds:
            typer.echo(f"  Storage method: {storage_method}")

        typer.echo(
            f"  Keyring available: {'✅ Yes' if info.get('keyring_available') else '❌ No'}"
        )
        typer.echo(f"  Platform: {info.get('platform', 'Unknown')}")

        if info.get("keyring_backend"):
            typer.echo(f"  Keyring backend: {info['keyring_backend']}")

        if not is_auth and not has_creds:
            typer.echo("\n💡 To authenticate:")
            typer.echo("   Interactive: glovebox moergo login")
            typer.echo(
                "   With env vars: MOERGO_USERNAME=user@email.com MOERGO_PASSWORD=*** glovebox moergo login"
            )

    except Exception as e:
        typer.echo(f"❌ Error checking status: {e}")
        raise typer.Exit(1) from None


@moergo_app.command("keystore")
def keystore_info() -> None:
    """Show detailed keystore and credential storage information."""
    try:
        client = create_moergo_client()
        info = client.get_credential_info()

        typer.echo("🔐 Keystore Information")
        typer.echo("=" * 40)

        # Platform info
        typer.echo(f"Platform: {info.get('platform', 'Unknown')}")
        typer.echo(f"Config directory: {info.get('config_dir', 'Unknown')}")

        # Keyring availability
        keyring_available = info.get("keyring_available", False)
        if keyring_available:
            typer.echo("✅ OS Keyring: Available")
            backend = info.get("keyring_backend", "Unknown")
            typer.echo(f"   Backend: {backend}")

            # Platform-specific keyring info
            platform_name = info.get("platform", "")
            if platform_name == "Darwin":
                typer.echo("   🍎 Using macOS Keychain")
            elif platform_name == "Windows":
                typer.echo("   🪟 Using Windows Credential Manager")
            elif platform_name == "Linux":
                typer.echo("   🐧 Using Linux keyring (secretstorage/keyctl)")
        else:
            typer.echo("❌ OS Keyring: Not available")
            typer.echo("   💡 Install keyring package for better security:")
            typer.echo("   pip install keyring")

        # Current storage method
        has_creds = info.get("has_credentials", False)
        if has_creds:
            storage_method = (
                "OS keyring" if keyring_available else "file with obfuscation"
            )
            typer.echo(f"\n📁 Current storage method: {storage_method}")

            if not keyring_available:
                typer.echo("   ⚠️  File storage provides basic obfuscation only")
                typer.echo("   🔒 For better security, install keyring package")
        else:
            typer.echo("\n📭 No credentials currently stored")

        # Security recommendations
        typer.echo("\n🛡️  Security Recommendations:")
        if keyring_available:
            typer.echo("   ✅ Your credentials are stored securely in OS keyring")
        else:
            typer.echo("   🔸 Install 'keyring' package for secure credential storage")
            typer.echo("   🔸 File storage uses basic obfuscation (not encryption)")

        typer.echo("   🔸 Use 'glovebox moergo logout' to clear stored credentials")
        typer.echo("   🔸 Credentials are stored per-user with restricted permissions")

    except Exception as e:
        typer.echo(f"❌ Error getting keystore info: {e}")
        raise typer.Exit(1) from None


@moergo_app.command("history")
def show_history(
    limit: Annotated[
        int, typer.Option("--limit", "-l", help="Number of entries to show")
    ] = 20,
    layout_uuid: Annotated[
        str | None,
        typer.Option("--layout", help="Show history for specific layout UUID"),
    ] = None,
    stats: Annotated[
        bool, typer.Option("--stats", help="Show usage statistics")
    ] = False,
) -> None:
    """Show MoErgo API interaction history."""
    try:
        client = create_moergo_client()

        if stats:
            # Show statistics
            statistics = client.get_history_statistics()
            typer.echo("📊 MoErgo API Usage Statistics")
            typer.echo("=" * 35)

            if statistics["total_operations"] == 0:
                typer.echo("No API interactions recorded yet.")
                return

            typer.echo(f"Total operations: {statistics['total_operations']}")
            typer.echo(f"Successful: {statistics['successful_operations']}")
            typer.echo(f"Failed: {statistics['failed_operations']}")

            success_rate = (
                statistics["successful_operations"] / statistics["total_operations"]
            ) * 100
            typer.echo(f"Success rate: {success_rate:.1f}%")

            typer.echo("\nOperations by type:")
            typer.echo(f"  📤 Uploads: {statistics['uploads']}")
            typer.echo(f"  📥 Downloads: {statistics['downloads']}")
            typer.echo(f"  🗑️  Deletes: {statistics['deletes']}")
            typer.echo(f"  ⚠️  Update attempts: {statistics['update_attempts']}")

            typer.echo(f"\nUnique layouts: {statistics['unique_layouts']}")

            if statistics["date_range"]:
                typer.echo(f"First operation: {statistics['date_range']['earliest']}")
                typer.echo(f"Latest operation: {statistics['date_range']['latest']}")

        elif layout_uuid:
            # Show history for specific layout
            history = client.get_layout_history(layout_uuid)
            if not history:
                typer.echo(f"No history found for layout {layout_uuid}")
                return

            typer.echo(f"📄 History for Layout {layout_uuid}")
            typer.echo("=" * 50)

            for entry in reversed(history):  # Show oldest first
                timestamp = entry["timestamp"]
                action = entry["action"]
                success = "✅" if entry["success"] else "❌"

                action_icons = {
                    "upload": "📤",
                    "download": "📥",
                    "delete": "🗑️",
                    "update_attempt": "⚠️",
                }
                icon = action_icons.get(action, "🔄")

                typer.echo(f"{success} {icon} {action.upper()} - {timestamp}")

                if entry.get("layout_title"):
                    typer.echo(f"   Title: {entry['layout_title']}")

                if not entry["success"] and entry.get("error_message"):
                    typer.echo(f"   Error: {entry['error_message']}")

                typer.echo()
        else:
            # Show recent history
            history = client.get_history(limit)
            if not history:
                typer.echo("No API interactions recorded yet.")
                return

            typer.echo(f"📚 Recent MoErgo API History (last {len(history)} operations)")
            typer.echo("=" * 60)

            for entry in history:
                timestamp = entry["timestamp"]
                action = entry["action"]
                layout_uuid = entry["layout_uuid"][:8] + "..."  # Short UUID
                success = "✅" if entry["success"] else "❌"

                action_icons = {
                    "upload": "📤",
                    "download": "📥",
                    "delete": "🗑️",
                    "update_attempt": "⚠️",
                }
                icon = action_icons.get(action, "🔄")

                title = entry.get("layout_title", "Unknown")
                typer.echo(
                    f"{success} {icon} {action.upper()} {layout_uuid} '{title}' - {timestamp}"
                )

                if not entry["success"] and entry.get("error_message"):
                    error = (
                        entry["error_message"][:80] + "..."
                        if len(entry["error_message"]) > 80
                        else entry["error_message"]
                    )
                    typer.echo(f"   Error: {error}")

    except Exception as e:
        typer.echo(f"❌ Error getting history: {e}")
        raise typer.Exit(1) from None


def register_commands(app: typer.Typer) -> None:
    """Register MoErgo commands with the main app."""
    app.add_typer(moergo_app, name="moergo")
