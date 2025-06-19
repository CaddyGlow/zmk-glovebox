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

        from glovebox.cli.helpers.theme import Icons

        # Note: This function doesn't have ctx parameter, so we'll use default emoji mode
        use_emoji = True  # Default behavior for this command

        if keyring_available:
            storage_method = "OS keyring"
            typer.echo(
                Icons.format_with_icon(
                    "SUCCESS",
                    f"Successfully logged in and stored credentials using {storage_method}",
                    use_emoji,
                )
            )
            typer.echo(
                Icons.format_with_icon(
                    "INFO",
                    "Your credentials are securely stored in your system keyring",
                    use_emoji,
                )
            )
        else:
            storage_method = "file with basic obfuscation"
            typer.echo(
                Icons.format_with_icon(
                    "SUCCESS",
                    f"Successfully logged in and stored credentials using {storage_method}",
                    use_emoji,
                )
            )
            typer.echo(
                Icons.format_with_icon(
                    "WARNING",
                    "For better security, consider installing the keyring package:",
                    use_emoji,
                )
            )
            typer.echo("   pip install keyring")
            typer.echo("   Then login again to use secure keyring storage")

    except AuthenticationError as e:
        typer.echo(Icons.format_with_icon("ERROR", f"Login failed: {e}", use_emoji))
        raise typer.Exit(1) from None
    except Exception as e:
        typer.echo(Icons.format_with_icon("ERROR", f"Unexpected error: {e}", use_emoji))
        raise typer.Exit(1) from None


@moergo_app.command("logout")
def logout() -> None:
    """Clear stored MoErgo credentials."""
    try:
        client = create_moergo_client()
        client.logout()
        from glovebox.cli.helpers.theme import Icons

        use_emoji = True  # Default behavior for this command
        typer.echo(
            Icons.format_with_icon(
                "SUCCESS", "Successfully logged out and cleared credentials", use_emoji
            )
        )

    except Exception as e:
        typer.echo(
            Icons.format_with_icon("ERROR", f"Error during logout: {e}", use_emoji)
        )
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
            from glovebox.cli.helpers.theme import Icons

            use_emoji = True  # Default behavior for this command
            typer.echo(
                Icons.format_with_icon(
                    "ERROR",
                    "Authentication failed. Please run 'glovebox moergo login' first.",
                    use_emoji,
                )
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
            typer.echo(
                Icons.format_with_icon(
                    "ERROR",
                    f"File {output} already exists. Use --force to overwrite.",
                    use_emoji,
                )
            )
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

        typer.echo(
            Icons.format_with_icon(
                "SUCCESS",
                f"Layout '{layout.layout_meta.title}' saved to {output}",
                use_emoji,
            )
        )
        typer.echo(f"   Creator: {layout.layout_meta.creator}")
        typer.echo(f"   Created: {layout.layout_meta.created_datetime}")

        if layout.layout_meta.notes:
            typer.echo(f"   Notes: {layout.layout_meta.notes}")

        if layout.layout_meta.tags:
            typer.echo(f"   Tags: {', '.join(layout.layout_meta.tags)}")

    except AuthenticationError as e:
        typer.echo(
            Icons.format_with_icon("ERROR", f"Authentication error: {e}", use_emoji)
        )
        typer.echo("Try running 'glovebox moergo login' first.")
        raise typer.Exit(1) from None
    except NetworkError as e:
        typer.echo(Icons.format_with_icon("ERROR", f"Network error: {e}", use_emoji))
        raise typer.Exit(1) from None
    except Exception as e:
        typer.echo(
            Icons.format_with_icon("ERROR", f"Error downloading layout: {e}", use_emoji)
        )
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception("Full error details")
        raise typer.Exit(1) from None


@moergo_app.command("status")
def status(ctx: typer.Context) -> None:
    """Show MoErgo authentication status and credential information."""
    from glovebox.cli.app import AppContext
    from glovebox.cli.helpers.theme import Icons

    # Get emoji mode from app context
    app_ctx: AppContext = ctx.obj
    use_emoji = app_ctx.use_emoji

    try:
        client = create_moergo_client()
        info = client.get_credential_info()

        typer.echo("MoErgo Authentication Status:")

        # Check authentication status
        is_auth = client.is_authenticated()
        auth_status = (
            Icons.format_with_icon("SUCCESS", "Yes", use_emoji)
            if is_auth
            else Icons.format_with_icon("ERROR", "No", use_emoji)
        )
        typer.echo(f"  Authenticated: {auth_status}")

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
                        warning_msg = Icons.format_with_icon(
                            "WARNING", "Token needs renewal soon", use_emoji
                        )
                        typer.echo(f"  {warning_msg}")
            except Exception:
                pass  # Don't fail if we can't get token info

        # Credential storage info
        has_creds = info.get("has_credentials", False)
        storage_method = (
            "OS keyring" if info.get("keyring_available") else "file storage"
        )

        creds_status = (
            Icons.format_with_icon("SUCCESS", "Yes", use_emoji)
            if has_creds
            else Icons.format_with_icon("ERROR", "No", use_emoji)
        )
        typer.echo(f"  Credentials stored: {creds_status}")
        if has_creds:
            typer.echo(f"  Storage method: {storage_method}")

        keyring_available = info.get("keyring_available")
        keyring_status = (
            Icons.format_with_icon("SUCCESS", "Yes", use_emoji)
            if keyring_available
            else Icons.format_with_icon("ERROR", "No", use_emoji)
        )
        typer.echo(f"  Keyring available: {keyring_status}")
        typer.echo(f"  Platform: {info.get('platform', 'Unknown')}")

        if info.get("keyring_backend"):
            typer.echo(f"  Keyring backend: {info['keyring_backend']}")

        if not is_auth and not has_creds:
            info_msg = Icons.format_with_icon("INFO", "To authenticate:", use_emoji)
            typer.echo(f"\n{info_msg}")
            typer.echo("   Interactive: glovebox moergo login")
            typer.echo(
                "   With env vars: MOERGO_USERNAME=user@email.com MOERGO_PASSWORD=*** glovebox moergo login"
            )

    except Exception as e:
        error_msg = Icons.format_with_icon(
            "ERROR", f"Error checking status: {e}", use_emoji
        )
        typer.echo(error_msg)
        raise typer.Exit(1) from None


@moergo_app.command("keystore")
def keystore_info() -> None:
    """Show detailed keystore and credential storage information."""
    try:
        client = create_moergo_client()
        info = client.get_credential_info()

        from glovebox.cli.helpers.theme import Icons

        use_emoji = True  # Default behavior for this command
        typer.echo(f"{Icons.get_icon('KEYSTORE', use_emoji)} Keystore Information")
        typer.echo("=" * 40)

        # Platform info
        typer.echo(f"Platform: {info.get('platform', 'Unknown')}")
        typer.echo(f"Config directory: {info.get('config_dir', 'Unknown')}")

        # Keyring availability
        keyring_available = info.get("keyring_available", False)
        if keyring_available:
            typer.echo(
                Icons.format_with_icon("SUCCESS", "OS Keyring: Available", use_emoji)
            )
            backend = info.get("keyring_backend", "Unknown")
            typer.echo(f"   Backend: {backend}")

            # Platform-specific keyring info
            platform_name = info.get("platform", "")
            if platform_name == "Darwin":
                typer.echo(
                    f"   {Icons.get_icon('INFO', use_emoji)} Using macOS Keychain"
                )
            elif platform_name == "Windows":
                typer.echo(
                    f"   {Icons.get_icon('INFO', use_emoji)} Using Windows Credential Manager"
                )
            elif platform_name == "Linux":
                typer.echo(
                    f"   {Icons.get_icon('INFO', use_emoji)} Using Linux keyring (secretstorage/keyctl)"
                )
        else:
            typer.echo(
                Icons.format_with_icon("ERROR", "OS Keyring: Not available", use_emoji)
            )
            typer.echo(
                f"   {Icons.get_icon('INFO', use_emoji)} Install keyring package for better security:"
            )
            typer.echo("   pip install keyring")

        # Current storage method
        has_creds = info.get("has_credentials", False)
        if has_creds:
            storage_method = (
                "OS keyring" if keyring_available else "file with obfuscation"
            )
            typer.echo(
                f"\n{Icons.get_icon('CONFIG', use_emoji)} Current storage method: {storage_method}"
            )

            if not keyring_available:
                typer.echo(
                    f"   {Icons.format_with_icon('WARNING', 'File storage provides basic obfuscation only', use_emoji)}"
                )
                typer.echo(
                    f"   {Icons.get_icon('INFO', use_emoji)} For better security, install keyring package"
                )
        else:
            typer.echo(
                f"\n{Icons.get_icon('INFO', use_emoji)} No credentials currently stored"
            )

        # Security recommendations
        typer.echo(f"\n{Icons.get_icon('INFO', use_emoji)} Security Recommendations:")
        if keyring_available:
            typer.echo(
                f"   {Icons.format_with_icon('SUCCESS', 'Your credentials are stored securely in OS keyring', use_emoji)}"
            )
        else:
            typer.echo(
                f"   {Icons.get_icon('BULLET', use_emoji)} Install 'keyring' package for secure credential storage"
            )
            typer.echo(
                f"   {Icons.get_icon('BULLET', use_emoji)} File storage uses basic obfuscation (not encryption)"
            )

        typer.echo(
            f"   {Icons.get_icon('BULLET', use_emoji)} Use 'glovebox moergo logout' to clear stored credentials"
        )
        typer.echo(
            f"   {Icons.get_icon('BULLET', use_emoji)} Credentials are stored per-user with restricted permissions"
        )

    except Exception as e:
        typer.echo(
            Icons.format_with_icon(
                "ERROR", f"Error getting keystore info: {e}", use_emoji
            )
        )
        raise typer.Exit(1) from None


def register_commands(app: typer.Typer) -> None:
    """Register MoErgo commands with the main app."""
    app.add_typer(moergo_app, name="moergo")
