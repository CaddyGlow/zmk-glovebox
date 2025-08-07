"""Layout CLI commands - refactored into focused, logical command groups."""

import typer


def register_commands(app: typer.Typer) -> None:
    """Register layout commands with the main app using lazy loading.

    Args:
        app: The main Typer app
    """
    # Import commands only when this function is called
    from .comparison import diff, patch
    from .core import (
        compile_layout,
        show,
        validate,
        zmk_layout_compile,
        zmk_layout_info,
    )
    from .edit import edit
    from .file_operations import merge, split
    from .parsing import register_parsing_commands

    # Create a typer app for layout commands
    layout_app = typer.Typer(
        name="layout",
        help="""Layout management commands.

Transform JSON layouts to ZMK files, edit layouts with batch operations,
manage file operations, handle version upgrades, and compare layouts.

**NEW COMMAND STRUCTURE** (8 main commands instead of 19+):

Core Operations:
  compile     - Convert JSON layout to ZMK files
  validate    - Validate layout syntax and structure
  show        - Display layout in terminal

ZMK-Layout Integration:
  zmk-compile - Enhanced compilation using zmk-layout library
  zmk-info    - Show zmk-layout integration status and capabilities

Unified Editing:
  edit        - Get/set fields, add/remove/move layers, list variable usage (batch operations)

File Operations:
  split       - Split layout into component files (was decompose)
  merge       - Merge component files into layout (was compose)

Parsing:
  parse       - Parse ZMK keymap files to JSON layouts (keymap, import)

Comparison:
  diff        - Compare layouts with optional patch creation
  patch       - Apply JSON diff patch to layout

""",
        no_args_is_help=True,
        rich_markup_mode="rich",
    )

    # Register core operations
    layout_app.command(name="compile")(compile_layout)
    layout_app.command()(validate)
    layout_app.command()(show)

    # Register zmk-layout integration commands
    layout_app.command(name="zmk-compile")(zmk_layout_compile)
    layout_app.command(name="zmk-info")(zmk_layout_info)

    # Register unified edit command
    layout_app.command()(edit)

    # Register file operations
    layout_app.command()(split)
    layout_app.command()(merge)

    # Register parsing commands
    register_parsing_commands(layout_app)

    # Register comparison commands
    layout_app.command()(diff)
    layout_app.command()(patch)

    # Add to main app
    app.add_typer(layout_app, name="layout")
