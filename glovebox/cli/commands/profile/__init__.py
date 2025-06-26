"""Profile management CLI commands."""

import typer

from .edit import edit_profile
from .firmwares import list_firmwares, show_firmware
from .info import list_profiles, show_profile


# Create a typer app for profile commands
profile_app = typer.Typer(
    name="profile",
    help="Profile configuration and firmware management commands",
    no_args_is_help=True,
)

# Register profile information commands
profile_app.command(name="list")(list_profiles)
profile_app.command(name="show")(show_profile)
profile_app.command(name="edit")(edit_profile)

# Register firmware commands
profile_app.command(name="firmwares")(list_firmwares)
profile_app.command(name="firmware")(show_firmware)


def register_commands(app: typer.Typer) -> None:
    """Register profile commands with the main app.

    Args:
        app: The main Typer app
    """
    app.add_typer(profile_app, name="profile")
