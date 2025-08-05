"""MoErgo API commands for authentication and credential management."""

import logging
from typing import Annotated

import typer

from glovebox.cli.core.command_base import BaseCommand
from glovebox.cli.decorators import handle_errors, with_metrics
from glovebox.core.structlog_logger import get_struct_logger
from glovebox.moergo.client import (
    AuthenticationError,
    create_moergo_client,
)


logger = get_struct_logger(__name__)

moergo_app = typer.Typer(
    name="moergo",
    help="""MoErgo API operations for authentication and credential management.

Authentication can be done interactively, with command line options, or environment variables:
• Interactive: glovebox moergo login
• Environment: MOERGO_USERNAME=user@email.com MOERGO_PASSWORD=*** glovebox moergo login

Credential Storage:
• Automatically uses OS keyring (macOS Keychain, Windows Credential Manager, Linux keyring)
• Falls back to encrypted file storage if keyring unavailable
• Use 'glovebox moergo keystore' to see detailed storage information
• Install 'keyring' package for enhanced security: pip install keyring""",
)


class LoginCommand(BaseCommand):
    """Command to login to MoErgo and store credentials securely."""

    def execute(
        self,
        ctx: typer.Context,
        username: str | None,
        password: str | None,
    ) -> None:
        """Execute the login command."""
        import os

        from glovebox.cli.helpers.theme import get_themed_console

        console = get_themed_console(ctx=ctx)

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
                console.print_success(
                    f"Successfully logged in and stored credentials using {storage_method}"
                )
                console.print_info(
                    "Your credentials are securely stored in your system keyring"
                )
            else:
                storage_method = "file with basic obfuscation"
                console.print_success(
                    f"Successfully logged in and stored credentials using {storage_method}"
                )
                console.print_warning(
                    "For better security, consider installing the keyring package:"
                )
                console.console.print("   pip install keyring")
                console.console.print(
                    "   Then login again to use secure keyring storage"
                )

        except AuthenticationError as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("authentication_failed", error=str(e), exc_info=exc_info)
            console.print_error(f"Login failed: {e}")
            raise typer.Exit(1) from None
        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("login_operation_failed", error=str(e), exc_info=exc_info)
            console.print_error(f"Unexpected error: {e}")
            raise typer.Exit(1) from None


class LogoutCommand(BaseCommand):
    """Command to clear stored MoErgo credentials."""

    def execute(self, ctx: typer.Context) -> None:
        """Execute the logout command."""
        from glovebox.cli.helpers.theme import get_themed_console

        console = get_themed_console(ctx=ctx)

        try:
            client = create_moergo_client()
            client.logout()
            console.print_success("Successfully logged out and cleared credentials")

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "logout_operation_failed", error=str(e), exc_info=exc_info
            )
            console.print_error(f"Error during logout: {e}")
            raise typer.Exit(1) from None


class StatusCommand(BaseCommand):
    """Command to show MoErgo authentication status and credential information."""

    def execute(self, ctx: typer.Context) -> None:
        """Execute the status command."""
        from glovebox.cli.helpers.theme import Icons, get_themed_console

        console = get_themed_console(ctx=ctx)

        try:
            client = create_moergo_client()
            info = client.get_credential_info()

            console.console.print("MoErgo Authentication Status:")

            # Check authentication status
            is_auth = client.is_authenticated()
            if is_auth:
                success_icon = Icons.get_icon("SUCCESS", console.icon_mode)
                auth_status = f"{success_icon} Yes"
            else:
                error_icon = Icons.get_icon("ERROR", console.icon_mode)
                auth_status = f"{error_icon} No"
            console.console.print(f"  Authenticated: {auth_status}")

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
                        console.console.print(f"  Token expires in: {expires_str}")

                        if token_info.get("needs_renewal", False):
                            warning_icon = Icons.get_icon("WARNING", console.icon_mode)
                            console.console.print(
                                f"  {warning_icon} Token needs renewal soon"
                            )
                except Exception:
                    pass  # Don't fail if we can't get token info

            # Credential storage info
            has_creds = info.get("has_credentials", False)
            storage_method = (
                "OS keyring" if info.get("keyring_available") else "file storage"
            )

            if has_creds:
                success_icon = Icons.get_icon("SUCCESS", console.icon_mode)
                creds_status = f"{success_icon} Yes"
            else:
                error_icon = Icons.get_icon("ERROR", console.icon_mode)
                creds_status = f"{error_icon} No"
            console.console.print(f"  Credentials stored: {creds_status}")
            if has_creds:
                console.console.print(f"  Storage method: {storage_method}")

            keyring_available = info.get("keyring_available")
            if keyring_available:
                success_icon = Icons.get_icon("SUCCESS", console.icon_mode)
                keyring_status = f"{success_icon} Yes"
            else:
                error_icon = Icons.get_icon("ERROR", console.icon_mode)
                keyring_status = f"{error_icon} No"
            console.console.print(f"  Keyring available: {keyring_status}")
            console.console.print(f"  Platform: {info.get('platform', 'Unknown')}")

            if info.get("keyring_backend"):
                console.console.print(f"  Keyring backend: {info['keyring_backend']}")

            if not is_auth and not has_creds:
                console.console.print()
                console.print_info("To authenticate:")
                console.console.print("   Interactive: glovebox moergo login")
                console.console.print(
                    "   With env vars: MOERGO_USERNAME=user@email.com MOERGO_PASSWORD=*** glovebox moergo login"
                )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("status_check_failed", error=str(e), exc_info=exc_info)
            console.print_error(f"Error checking status: {e}")
            raise typer.Exit(1) from None


class KeystoreCommand(BaseCommand):
    """Command to show detailed keystore and credential storage information."""

    def execute(self, ctx: typer.Context) -> None:
        """Execute the keystore command."""
        from glovebox.cli.helpers.theme import Icons, get_themed_console

        console = get_themed_console(ctx=ctx)

        try:
            client = create_moergo_client()
            info = client.get_credential_info()
            keystore_icon = Icons.get_icon("KEYSTORE", console.icon_mode)
            console.console.print(f"{keystore_icon} Keystore Information")
            console.console.print("=" * 40)

            # Platform info
            console.console.print(f"Platform: {info.get('platform', 'Unknown')}")
            console.console.print(
                f"Config directory: {info.get('config_dir', 'Unknown')}"
            )

            # Keyring availability
            keyring_available = info.get("keyring_available", False)
            if keyring_available:
                console.print_success("OS Keyring: Available")
                backend = info.get("keyring_backend", "Unknown")
                console.console.print(f"   Backend: {backend}")

                # Platform-specific keyring info
                platform_name = info.get("platform", "")
                info_icon = Icons.get_icon("INFO", console.icon_mode)
                if platform_name == "Darwin":
                    console.console.print(f"   {info_icon} Using macOS Keychain")
                elif platform_name == "Windows":
                    console.console.print(
                        f"   {info_icon} Using Windows Credential Manager"
                    )
                elif platform_name == "Linux":
                    console.console.print(
                        f"   {info_icon} Using Linux keyring (secretstorage/keyctl)"
                    )
            else:
                console.print_error("OS Keyring: Not available")
                info_icon = Icons.get_icon("INFO", console.icon_mode)
                console.console.print(
                    f"   {info_icon} Install keyring package for better security:"
                )
                console.console.print("   pip install keyring")

            # Current storage method
            has_creds = info.get("has_credentials", False)
            if has_creds:
                storage_method = (
                    "OS keyring" if keyring_available else "file with obfuscation"
                )
                config_icon = Icons.get_icon("CONFIG", console.icon_mode)
                console.console.print(
                    f"\n{config_icon} Current storage method: {storage_method}"
                )

                if not keyring_available:
                    warning_icon = Icons.get_icon("WARNING", console.icon_mode)
                    console.console.print(
                        f"   {warning_icon} File storage provides basic obfuscation only"
                    )
                    info_icon = Icons.get_icon("INFO", console.icon_mode)
                    console.console.print(
                        f"   {info_icon} For better security, install keyring package"
                    )
            else:
                info_icon = Icons.get_icon("INFO", console.icon_mode)
                console.console.print(f"\n{info_icon} No credentials currently stored")

            # Security recommendations
            info_icon = Icons.get_icon("INFO", console.icon_mode)
            console.console.print(f"\n{info_icon} Security Recommendations:")
            if keyring_available:
                success_icon = Icons.get_icon("SUCCESS", console.icon_mode)
                console.console.print(
                    f"   {success_icon} Your credentials are stored securely in OS keyring"
                )
            else:
                bullet_icon = Icons.get_icon("BULLET", console.icon_mode)
                console.console.print(
                    f"   {bullet_icon} Install 'keyring' package for secure credential storage"
                )
                console.console.print(
                    f"   {bullet_icon} File storage uses basic obfuscation (not encryption)"
                )

            bullet_icon = Icons.get_icon("BULLET", console.icon_mode)
            console.console.print(
                f"   {bullet_icon} Use 'glovebox moergo logout' to clear stored credentials"
            )
            console.console.print(
                f"   {bullet_icon} Credentials are stored per-user with restricted permissions"
            )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Keystore info retrieval failed: %s", e, exc_info=exc_info
            )
            console.print_error(f"Error getting keystore info: {e}")
            raise typer.Exit(1) from None


@moergo_app.command("login")
@handle_errors
@with_metrics("moergo_login")
def login(
    ctx: typer.Context,
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
    command = LoginCommand()
    command.execute(ctx, username, password)


@moergo_app.command("logout")
@handle_errors
def logout(ctx: typer.Context) -> None:
    """Clear stored MoErgo credentials."""
    command = LogoutCommand()
    command.execute(ctx)


@moergo_app.command("status")
@handle_errors
def status(ctx: typer.Context) -> None:
    """Show MoErgo authentication status and credential information."""
    command = StatusCommand()
    command.execute(ctx)


@moergo_app.command("keystore")
@handle_errors
def keystore_info(ctx: typer.Context) -> None:
    """Show detailed keystore and credential storage information."""
    command = KeystoreCommand()
    command.execute(ctx)


def register_commands(app: typer.Typer) -> None:
    """Register MoErgo commands with the main app."""
    app.add_typer(moergo_app, name="moergo")
