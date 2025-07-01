"""Library management CLI commands."""

import typer

from .compile import compile_app
from .copy import copy_app
from .diff import diff_app
from .edit import edit_app
from .export import export_app
from .fetch import fetch_app
from .info import info_app
from .list_cmd import list_app
from .remove import remove_app
from .search import search_app
from .show import show_app
from .validate import validate_app


# Create main library app
library_app = typer.Typer(
    name="library",
    help="Manage layout library for fetching and organizing layouts",
    no_args_is_help=True,
)

# Add sub-commands
library_app.add_typer(fetch_app, name="fetch")
library_app.add_typer(search_app, name="search")
library_app.add_typer(list_app, name="list")
library_app.add_typer(info_app, name="info")
library_app.add_typer(remove_app, name="remove")
library_app.add_typer(export_app, name="export")

# Add proxy commands
library_app.add_typer(compile_app, name="compile")
library_app.add_typer(copy_app, name="copy")
library_app.add_typer(edit_app, name="edit")
library_app.add_typer(show_app, name="show")
library_app.add_typer(validate_app, name="validate")
library_app.add_typer(diff_app, name="diff")


def register_commands(app: typer.Typer) -> None:
    """Register library commands with the main app."""
    app.add_typer(library_app, name="library")
