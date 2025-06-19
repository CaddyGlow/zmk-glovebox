"""Keyboard management CLI commands."""

import typer

from .firmwares import list_firmwares, show_firmware
from .info import list_keyboards, show_keyboard


# Create a typer app for keyboard commands
keyboard_app = typer.Typer(
    name="keyboard",
    help="Keyboard configuration and firmware management commands",
    no_args_is_help=True,
)

# Register keyboard information commands
keyboard_app.command(name="list")(list_keyboards)
keyboard_app.command(name="show")(show_keyboard)

# Register firmware commands
keyboard_app.command(name="firmwares")(list_firmwares)
keyboard_app.command(name="firmware")(show_firmware)


def register_commands(app: typer.Typer) -> None:
    """Register keyboard commands with the main app.

    Args:
        app: The main Typer app
    """
    app.add_typer(keyboard_app, name="keyboard")
