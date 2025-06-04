"""CLI command modules."""

import typer

from glovebox.cli.commands.config import register_commands as register_config_commands
from glovebox.cli.commands.firmware import (
    register_commands as register_firmware_commands,
)
from glovebox.cli.commands.keymap import register_commands as register_keymap_commands
from glovebox.cli.commands.status import register_commands as register_status_commands


def register_all_commands(app: typer.Typer) -> None:
    """Register all CLI commands with the main app.

    Args:
        app: The main Typer app
    """
    register_keymap_commands(app)
    register_firmware_commands(app)
    register_config_commands(app)
    register_status_commands(app)
