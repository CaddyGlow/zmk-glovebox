"""Layout CLI commands - refactored into focused modules."""

import typer

from .comparison import create_patch, diff, patch
from .core import compile_layout, compose, decompose, show, validate
from .editing import get_field, set_field
from .glove80_sync import glove80_group
from .layers import add_layer, export_layer, list_layers, move_layer, remove_layer
from .version import import_master, list_masters, upgrade


# Create a typer app for layout commands
layout_app = typer.Typer(
    name="layout",
    help="""Layout management commands.

Convert JSON layouts to ZMK files, extract/merge layers, validate layouts,
and display visual representations of keyboard layouts.""",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Register core commands
layout_app.command(name="compile")(compile_layout)
layout_app.command()(decompose)
layout_app.command()(compose)
layout_app.command()(validate)
layout_app.command()(show)

# Register version management commands
layout_app.command(name="import-master")(import_master)
layout_app.command()(upgrade)
layout_app.command(name="list-masters")(list_masters)

# Register comparison commands
layout_app.command()(diff)
layout_app.command()(patch)
layout_app.command(name="create-patch")(create_patch)

# Register field editing commands
layout_app.command(name="get-field")(get_field)
layout_app.command(name="set-field")(set_field)

# Register layer management commands
layout_app.command(name="add-layer")(add_layer)
layout_app.command(name="remove-layer")(remove_layer)
layout_app.command(name="move-layer")(move_layer)
layout_app.command(name="list-layers")(list_layers)
layout_app.command(name="export-layer")(export_layer)

# Register Glove80 cloud sync commands
layout_app.add_typer(glove80_group, name="glove80")


def register_commands(app: typer.Typer) -> None:
    """Register layout commands with the main app.

    Args:
        app: The main Typer app
    """
    app.add_typer(layout_app, name="layout")
