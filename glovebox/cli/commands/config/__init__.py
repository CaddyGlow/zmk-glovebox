"""Configuration CLI commands - refactored into focused modules."""

import typer

from .edit import edit
from .management import show_config
from .updates import check_updates


# Create a typer app for configuration commands
config_app = typer.Typer(
    name="config",
    help="Configuration management commands",
    no_args_is_help=True,
)

# Register new unified edit command
config_app.command()(edit)

# Register management commands
config_app.command(name="show")(show_config)

# Register update commands
config_app.command(name="check-updates")(check_updates)

# Note: profile-related commands are now in the dedicated profile module


def register_commands(app: typer.Typer) -> None:
    """Register config commands with the main app.

    Args:
        app: The main Typer app
    """
    app.add_typer(config_app, name="config")
