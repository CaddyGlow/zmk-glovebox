"""Firmware management commands.

Build ZMK firmware from keymap files using Docker with multiple build strategies,
flash firmware to USB devices, and manage firmware-related operations.

Supports modern ZMK west workspace builds (recommended) as well as traditional
cmake, make, and ninja build systems for custom keyboards.
"""

import typer

from .compile import compile
from .devices import list_devices
from .flash import flash


# Create a typer app for firmware commands
firmware_app = typer.Typer(
    name="firmware",
    help=__doc__,
    no_args_is_help=True,
)

# Register commands
firmware_app.command(name="compile")(compile)
firmware_app.command(name="flash")(flash)
firmware_app.command(name="devices")(list_devices)


def register_commands(app: typer.Typer) -> None:
    """Register firmware commands with the main app.

    Args:
        app: The main Typer app
    """
    app.add_typer(firmware_app, name="firmware")
