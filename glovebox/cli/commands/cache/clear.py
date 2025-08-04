"""Cache clear CLI command."""

import logging
import shutil
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from glovebox.cli.core.command_base import IOCommand
from glovebox.cli.decorators.error_handling import handle_errors
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


class CacheClearCommand(IOCommand):
    """Command to clear cache entries from both workspace and DiskCache systems."""

    def execute(
        self,
        ctx: typer.Context,
        module: str | None = None,
        max_age_days: int | None = None,
        force: bool = False,
    ) -> None:
        """Execute the cache clear command."""
        try:
            user_config = create_user_config()
            diskcache_root = user_config._config.cache_path

            if module:
                self._clear_module_cache(module, diskcache_root, force)
            elif max_age_days is not None:
                self._clear_by_age(max_age_days)
            else:
                self._clear_all_cache(diskcache_root, force)

        except Exception as e:
            self.handle_service_error(e, "clear cache")

    def _clear_module_cache(
        self, module: str, diskcache_root: Path, force: bool
    ) -> None:
        """Clear specific module cache."""
        module_cache_dir = diskcache_root / module

        # Check if filesystem directory exists
        has_filesystem_cache = module_cache_dir.exists()

        # Check if in-memory cache exists
        from glovebox.core.cache import create_default_cache

        module_cache = create_default_cache(tag=module)
        has_inmemory_cache = len(module_cache.keys()) > 0

        if not has_filesystem_cache and not has_inmemory_cache:
            console.print(f"[yellow]No cache found for module '{module}'[/yellow]")
            return

        if not force:
            if has_filesystem_cache:
                size = get_directory_size_bytes(module_cache_dir)
                confirm = typer.confirm(
                    f"Clear cache for module '{module}' ({format_size_display(size)})?"
                )
            else:
                confirm = typer.confirm(f"Clear in-memory cache for module '{module}'?")
            if not confirm:
                console.print("[yellow]Cancelled[/yellow]")
                return

        try:
            # Clear the specific module's cache instance
            module_cache.clear()

            # Also remove the filesystem directory if it exists
            if has_filesystem_cache:
                shutil.rmtree(module_cache_dir)

            icon_mode = "emoji"
            console.print(
                f"[green]{get_icon('SUCCESS', icon_mode)} Cleared cache for module '{module}'[/green]"
            )
        except Exception as e:
            console.print(f"[red]Failed to clear module cache: {e}[/red]")
            raise typer.Exit(1) from e

    def _clear_by_age(self, max_age_days: int) -> None:
        """Age-based cleanup using cache system."""
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
                console.print(f"[green]Removed {removed} expired cache entries[/green]")
            else:
                console.print("[yellow]No expired entries found to remove[/yellow]")

        except Exception as e:
            logger.error("Failed to cleanup cache: %s", e)
            console.print(f"[red]Error during cleanup: {e}[/red]")
            raise typer.Exit(1) from e

    def _clear_all_cache(self, diskcache_root: Path, force: bool) -> None:
        """Clear all cache types."""
        # Get filesystem directories
        cache_subdirs = []
        if diskcache_root.exists():
            cache_subdirs = [d for d in diskcache_root.iterdir() if d.is_dir()]

        # Get in-memory cache modules
        from glovebox.core.cache import (
            create_default_cache,
            reset_shared_cache_instances,
        )

        # Common cache module names to check
        common_modules = ["metrics", "layout", "compilation", "moergo", "firmware"]
        inmemory_modules = []

        for module in common_modules:
            try:
                module_cache = create_default_cache(tag=module)
                if len(module_cache.keys()) > 0:
                    inmemory_modules.append(module)
            except Exception:
                # Skip modules that can't be created
                continue

        # Combine filesystem and in-memory modules
        all_modules: set[str] = set()
        if cache_subdirs:
            all_modules.update(d.name for d in cache_subdirs)
        all_modules.update(inmemory_modules)

        if not all_modules:
            console.print("[yellow]No cache directories found[/yellow]")
            return

        total_size = sum(get_directory_size_bytes(d) for d in cache_subdirs)

        if not force:
            confirm = typer.confirm(
                f"Clear ALL cache directories ({len(all_modules)} modules, {format_size_display(total_size)})?"
            )
            if not confirm:
                console.print("[yellow]Cancelled[/yellow]")
                return

        try:
            # Clear all module-specific cache instances
            cleared_modules = []
            for module_name in all_modules:
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


@handle_errors
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
    """Clear cache entries from both workspace and DiskCache systems."""
    command = CacheClearCommand()
    command.execute(
        ctx=ctx,
        module=module,
        max_age_days=max_age_days,
        force=force,
    )
