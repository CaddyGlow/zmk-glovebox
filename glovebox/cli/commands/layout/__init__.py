"""Layout CLI commands - refactored into focused, logical command groups."""

import typer

# Import comparison commands
from .comparison import diff, patch

# Import core operations
from .core import compile_layout, show, validate

# Import unified edit command
from .edit import edit

# Import file operations
from .file_operations import export, import_layout, merge, split

# Import new cloud and bookmark commands
from .cloud import register_commands as register_cloud_commands
from .bookmarks import register_commands as register_bookmarks_commands

# Import upgrade command
from .upgrade import upgrade

# Import version management subcommand group
from .versions import versions_app


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

Unified Editing:
  edit        - Get/set fields, add/remove/move layers (batch operations)

File Operations:
  split       - Split layout into component files (was decompose)
  merge       - Merge component files into layout (was compose)
  export      - Export layer to external file (was export-layer)
  import      - Import from other layouts (new unified import)

Version Management:
  versions    - Subcommand group for master version management
  upgrade     - Upgrade layout to new master version

Comparison:
  diff        - Compare layouts with optional patch creation
  patch       - Apply JSON diff patch to layout

Cloud Integration:
  cloud       - Essential cloud operations (upload, download, list, browse, delete)
  bookmarks   - Bookmark management for easy access to saved layouts
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
layout_app.command()(export)
layout_app.command(name="import")(import_layout)  # import is a Python keyword

# Register upgrade command
layout_app.command()(upgrade)

# Register comparison commands
layout_app.command()(diff)
layout_app.command()(patch)

# Register version management subcommand group
layout_app.add_typer(versions_app, name="versions")

# Register cloud and bookmark commands
register_cloud_commands(layout_app)
register_bookmarks_commands(layout_app)


def register_commands(app: typer.Typer) -> None:
    """Register layout commands with the main app.

    Args:
        app: The main Typer app
    """
    app.add_typer(layout_app, name="layout")
