"""CLI command modules."""

import typer

from glovebox.cli.commands.bookmarks import (
    register_commands as register_bookmarks_commands,
)
from glovebox.cli.commands.cache import register_cache_commands
from glovebox.cli.commands.cloud import (
    register_commands as register_cloud_commands,
)
from glovebox.cli.commands.config import register_commands as register_config_commands
from glovebox.cli.commands.firmware import (
    register_commands as register_firmware_commands,
)
from glovebox.cli.commands.layout import register_commands as register_layout_commands
from glovebox.cli.commands.library import register_commands as register_library_commands
from glovebox.cli.commands.metrics import register_commands as register_metrics_commands
from glovebox.cli.commands.moergo import register_commands as register_moergo_commands
from glovebox.cli.commands.profile import (
    register_commands as register_profile_commands,
)
from glovebox.cli.commands.status import register_commands as register_status_commands


def register_all_commands(app: typer.Typer) -> None:
    """Register all CLI commands with the main app.

    Args:
        app: The main Typer app
    """
    register_layout_commands(app)
    register_library_commands(app)
    register_firmware_commands(app)
    register_config_commands(app)
    register_profile_commands(app)
    register_status_commands(app)
    register_moergo_commands(app)
    register_cloud_commands(app)
    register_bookmarks_commands(app)
    register_metrics_commands(app)
    register_cache_commands(app)
