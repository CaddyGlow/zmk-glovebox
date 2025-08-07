"""ZMK Layout Library Integration CLI Commands.

Comprehensive CLI commands that expose all zmk-layout library features through
the glovebox interface.
"""

import typer


def register_zmk_layout_commands(app: typer.Typer) -> None:
    """Register zmk-layout integration commands with the main app.

    Args:
        app: The main Typer app
    """
    # Import commands only when this function is called (lazy loading)
    from .batch import batch_app
    from .behaviors import behaviors_app
    from .compile import compile_layout
    from .export import export_layout
    from .info import info_layout
    from .layers import layers_app
    from .parse import parse_keymap
    from .stats import stats_layout
    from .transform_typer import transform_app
    from .validate import validate_layout

    # Create a typer app for zmk-layout commands
    zmk_layout_app = typer.Typer(
        name="zmk-layout",
        help="""ZMK Layout Library Integration Commands.

Advanced layout processing using the zmk-layout library for enhanced
JSON to DTSI conversion, validation, and layout management.

**Main Commands:**

Core Operations:
  compile     - Compile layouts with full zmk-layout options
  validate    - Validate layout files with zmk-layout rules
  parse       - Parse ZMK keymap files to JSON using zmk-layout library
  export      - Export to multiple formats (keymap, config, JSON)
  info        - Show zmk-layout integration status and capabilities

Advanced Features:
  behaviors   - Manage behaviors (add, list, remove, validate)
  layers      - Manage layers (add, remove, modify, reorder)
  stats       - Show detailed layout statistics and analysis
  batch       - Execute batch operations on multiple layouts

Use 'glovebox zmk-layout <command> --help' for detailed command options.
""",
        no_args_is_help=True,
        rich_markup_mode="rich",
    )

    # Register individual commands
    zmk_layout_app.command(name="compile")(compile_layout)
    zmk_layout_app.command(name="validate")(validate_layout)
    zmk_layout_app.command(name="parse")(parse_keymap)
    zmk_layout_app.command(name="export")(export_layout)
    zmk_layout_app.command(name="stats")(stats_layout)
    zmk_layout_app.command(name="info")(info_layout)

    # Register sub-app commands
    zmk_layout_app.add_typer(behaviors_app, name="behaviors")
    zmk_layout_app.add_typer(layers_app, name="layers")
    zmk_layout_app.add_typer(batch_app, name="batch")
    zmk_layout_app.add_typer(transform_app, name="transform")

    # Add to main app
    app.add_typer(zmk_layout_app, name="zmk-layout")
