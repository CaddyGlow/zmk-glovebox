"""Cache clear CLI command."""

import logging
import shutil
from typing import Annotated

import typer
from rich.console import Console

from glovebox.cli.decorators import (
    handle_errors,
    with_cache,
    with_metrics,
    with_user_config,
)
from glovebox.cli.decorators.profile import (
    get_cache_manager_from_context,
    get_user_config_from_context_decorator,
)
from glovebox.config.user_config import create_user_config

from .utils import (
    format_icon_with_message,
    format_size_display,
    get_cache_manager,
    get_directory_size_bytes,
    get_icon,
)


logger = logging.getLogger(__name__)
console = Console()


@handle_errors
@with_metrics("cache_clear")
@with_cache("cache", required=False)
@with_user_config(required=True)
def cache_clear(
    ctx: typer.Context,
    module: Annotated[
        str | None,
        typer.Option(
            "-m",
            "--module",
            help="Specific module cache to clear (e.g., 'layout', 'compilation', 'moergo')",
        ),
    ] = None,
    max_age_days: Annotated[
        int | None,
        typer.Option("--max-age", help="Clear entries older than specified days"),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force deletion without confirmation"),
    ] = False,
) -> None:
    """Clear cache entries from both workspace and DiskCache systems.

    This unified command handles clearing of workspace caches, module caches,
    and age-based cleanup using the cache system.
    """
    try:
        user_config = get_user_config_from_context_decorator(ctx)
        diskcache_root = user_config._config.cache_path

        if module:
            # Clear specific module cache
            if not diskcache_root.exists():
                console.print("[yellow]No cache directory found[/yellow]")
                return

            module_cache_dir = diskcache_root / module

            if not module_cache_dir.exists():
                console.print(f"[yellow]No cache found for module '{module}'[/yellow]")
                return

            if not force:
                size = get_directory_size_bytes(module_cache_dir)
                confirm = typer.confirm(
                    f"Clear cache for module '{module}' ({format_size_display(size)})?"
                )
                if not confirm:
                    console.print("[yellow]Cancelled[/yellow]")
                    return

            try:
                # Clear the specific module's cache instance
                from glovebox.core.cache import create_default_cache

                module_cache = create_default_cache(tag=module)
                module_cache.clear()

                # Also remove the filesystem directory to ensure complete cleanup
                shutil.rmtree(module_cache_dir)

                icon_mode = "emoji"
                console.print(
                    f"[green]{get_icon('SUCCESS', icon_mode)} Cleared cache for module '{module}'[/green]"
                )
            except Exception as e:
                console.print(f"[red]Failed to clear module cache: {e}[/red]")
                raise typer.Exit(1) from e

        elif max_age_days is not None:
            # Age-based cleanup using cache system
            try:
                cache_manager = get_cache_manager()
                cache_stats = cache_manager.get_stats()

                console.print(
                    f"[blue]Cleaning up cache entries older than {max_age_days} days...[/blue]"
                )

                # Use cache's built-in cleanup if available
                if hasattr(cache_manager, "cleanup"):
                    cache_manager.cleanup()

                icon_mode = "emoji"
                console.print(
                    format_icon_with_message(
                        "SUCCESS",
                        "Cache cleanup completed using cache system.",
                        icon_mode,
                    )
                )

                # Show updated stats
                new_stats = cache_manager.get_stats()
                if new_stats.total_entries < cache_stats.total_entries:
                    removed = cache_stats.total_entries - new_stats.total_entries
                    console.print(
                        f"[green]Removed {removed} expired cache entries[/green]"
                    )
                else:
                    console.print("[yellow]No expired entries found to remove[/yellow]")

            except Exception as e:
                logger.error("Failed to cleanup cache: %s", e)
                console.print(f"[red]Error during cleanup: {e}[/red]")
                raise typer.Exit(1) from e
        else:
            # Clear all cache types
            if not diskcache_root.exists():
                console.print("[yellow]No cache directories found[/yellow]")
                return

            cache_subdirs = [d for d in diskcache_root.iterdir() if d.is_dir()]

            if not cache_subdirs:
                console.print("[yellow]No cache directories found[/yellow]")
                return

            total_size = sum(get_directory_size_bytes(d) for d in cache_subdirs)

            if not force:
                confirm = typer.confirm(
                    f"Clear ALL cache directories ({len(cache_subdirs)} modules, {format_size_display(total_size)})?"
                )
                if not confirm:
                    console.print("[yellow]Cancelled[/yellow]")
                    return

            try:
                # Clear all module-specific cache instances
                from glovebox.core.cache import (
                    create_default_cache,
                    reset_shared_cache_instances,
                )

                cleared_modules = []
                for cache_dir in cache_subdirs:
                    module_name = cache_dir.name
                    try:
                        # Clear the cache instance for this module
                        module_cache = create_default_cache(tag=module_name)
                        module_cache.clear()
                        cleared_modules.append(module_name)
                    except Exception as e:
                        logger.warning(
                            "Failed to clear cache instance for module '%s': %s",
                            module_name,
                            e,
                        )

                # Reset shared cache coordination to clean up instance registry
                reset_shared_cache_instances()

                # Clear filesystem directories
                for cache_dir in cache_subdirs:
                    shutil.rmtree(cache_dir)

                icon_mode = "emoji"
                console.print(
                    f"[green]{get_icon('SUCCESS', icon_mode)} Cleared all cache directories ({format_size_display(total_size)})[/green]"
                )
                if cleared_modules:
                    console.print(
                        f"[green]Cleared cache instances for modules: {', '.join(cleared_modules)}[/green]"
                    )
                console.print("[green]Reset shared cache coordination[/green]")
            except Exception as e:
                console.print(f"[red]Failed to clear cache: {e}[/red]")
                raise typer.Exit(1) from e

    except Exception as e:
        logger.error("Failed to clear cache: %s", e)

        icon_mode = "emoji"
        typer.echo(
            format_icon_with_message("ERROR", f"Error: {e}", icon_mode), err=True
        )
        raise typer.Exit(1) from e
