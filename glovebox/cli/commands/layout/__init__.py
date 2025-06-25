"""Layout CLI commands - refactored into focused, logical command groups."""

import typer

# Note: cloud and bookmarks commands have been moved to main commands directory
# Import comparison commands
from .comparison import diff, patch

# Import core operations
from .core import compile_layout, show, validate

# Import unified edit command
from .edit import edit

# Import file operations
from .file_operations import merge, split


# Import variable management command


# Create a typer app for layout commands
layout_app = typer.Typer(
    name="layout",
    help="""Layout management commands.

Transform JSON layouts to ZMK files, edit layouts with batch operations,
manage file operations, handle version upgrades, and compare layouts.

**NEW COMMAND STRUCTURE** (6 main commands instead of 19+):

Core Operations:
  compile     - Convert JSON layout to ZMK files
  validate    - Validate layout syntax and structure
  show        - Display layout in terminal

Unified Editing:
  edit        - Get/set fields, add/remove/move layers, list variable usage (batch operations)

File Operations:
  split       - Split layout into component files (was decompose)
  merge       - Merge component files into layout (was compose)


Comparison:
  diff        - Compare layouts with optional patch creation
  patch       - Apply JSON diff patch to layout

Note: Cloud and bookmark operations have been moved to top-level commands:
  glovebox cloud       - Essential cloud operations (upload, download, list, browse, delete)
  glovebox bookmarks   - Bookmark management for easy access to saved layouts
""",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Register core operations
layout_app.command(name="compile")(compile_layout)
layout_app.command()(validate)
layout_app.command()(show)

# Register unified edit command
layout_app.command()(edit)


# Register file operations
layout_app.command()(split)
layout_app.command()(merge)


# Register comparison commands
layout_app.command()(diff)
layout_app.command()(patch)


# Note: cloud and bookmarks commands are now registered at the top level


def register_commands(app: typer.Typer) -> None:
    """Register layout commands with the main app.

    Args:
        app: The main Typer app
    """
    app.add_typer(layout_app, name="layout")
