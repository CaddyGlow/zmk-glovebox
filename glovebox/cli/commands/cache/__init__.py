"""Cache CLI commands following CLAUDE.md modular design patterns."""

import typer

from .workspace import register_workspace_commands


# Main cache app that combines all cache-related commands
cache_app = typer.Typer(help="Cache management commands")


def register_cache_commands(app: typer.Typer) -> None:
    """Register all cache commands with the main app following CLAUDE.md patterns.
    
    This function follows the clean registration pattern described in CLAUDE.md:
    - Modular CLI structure with focused command modules  
    - Single responsibility per module
    - Consistent registration patterns
    - All modules under 500 lines
    """

    # Register workspace commands as subcommand
    register_workspace_commands(cache_app)

    # Import individual command functions from modules
    from .debug import cache_debug
    from .delete import cache_delete
    from .clear import cache_clear
    from .keys import cache_keys
    from .show import cache_show

    # Register operations commands directly to cache app
    cache_app.command("keys")(cache_keys)
    cache_app.command("delete")(cache_delete)
    cache_app.command("clear")(cache_clear)

    # Register management commands directly to cache app
    cache_app.command("show")(cache_show)
    cache_app.command("debug")(cache_debug)

    # Add the complete cache app to the main CLI
    app.add_typer(cache_app, name="cache")


# Export the main registration function for use in CLI
__all__ = ["register_cache_commands"]
