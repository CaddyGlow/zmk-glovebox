"""CLI command modules."""

import typer

from glovebox.cli.commands.cache import cache_app
from glovebox.cli.commands.config import register_commands as register_config_commands
from glovebox.cli.commands.firmware import (
    register_commands as register_firmware_commands,
)
from glovebox.cli.commands.keyboard import (
    register_commands as register_keyboard_commands,
)
from glovebox.cli.commands.layout import register_commands as register_layout_commands
from glovebox.cli.commands.layout.cloud import register_commands as register_cloud_commands
from glovebox.cli.commands.layout.bookmarks import register_commands as register_bookmarks_commands
from glovebox.cli.commands.moergo import register_commands as register_moergo_commands
from glovebox.cli.commands.status import register_commands as register_status_commands


def register_all_commands(app: typer.Typer) -> None:
    """Register all CLI commands with the main app.

    Args:
        app: The main Typer app
    """
    register_layout_commands(app)
    register_firmware_commands(app)
    register_config_commands(app)
    register_keyboard_commands(app)
    register_status_commands(app)
    register_moergo_commands(app)
    register_cloud_commands(app)
    register_bookmarks_commands(app)
    app.add_typer(cache_app, name="cache")
