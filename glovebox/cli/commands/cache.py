"""Cache management CLI commands."""

import contextlib
import logging
import shutil
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from glovebox.cli.helpers.theme import Icons
from glovebox.compilation.cache.workspace_cache_service import (
    ZmkWorkspaceCacheService,
    create_zmk_workspace_cache_service,
)
from glovebox.config.user_config import UserConfig, create_user_config
from glovebox.core.cache_v2 import create_cache_from_user_config
from glovebox.core.cache_v2.cache_manager import CacheManager
from glovebox.core.workspace_cache_utils import (
    detect_git_info,
    generate_workspace_cache_key,
)


logger = logging.getLogger(__name__)
console = Console()

cache_app = typer.Typer(help="Cache management commands")
workspace_app = typer.Typer(help="Workspace cache management")
cache_app.add_typer(workspace_app, name="workspace")


def _format_size(size_bytes: float) -> str:
    """Format size in human readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def _get_directory_size(path: Path) -> int:
    """Get total size of directory in bytes."""
    total = 0
    try:
        for file_path in path.rglob("*"):
            if file_path.is_file():
                total += file_path.stat().st_size
    except (OSError, PermissionError):
        pass
    return total


def _get_cache_manager_and_service() -> tuple[
    CacheManager, ZmkWorkspaceCacheService, UserConfig
]:
    """Get cache manager and workspace cache service using user config.

    Returns:
        Tuple of (cache_manager, workspace_cache_service, user_config)
    """
    try:
        user_config = create_user_config()
        cache_manager = create_cache_from_user_config(user_config, tag="compilation")
        workspace_cache_service = create_zmk_workspace_cache_service(
            user_config, cache_manager
        )
        return cache_manager, workspace_cache_service, user_config
    except Exception:
        # Fallback to default cache if user config fails
        from glovebox.core.cache_v2 import create_default_cache

        cache_manager = create_default_cache(tag="compilation")
        # Create a minimal user config for fallback
        user_config = create_user_config()
        workspace_cache_service = create_zmk_workspace_cache_service(
            user_config, cache_manager
        )
        return cache_manager, workspace_cache_service, user_config


def _get_cache_manager() -> CacheManager:
    """Get cache manager using user config (backward compatibility)."""
    cache_manager, _, _ = _get_cache_manager_and_service()
    return cache_manager


@workspace_app.command(name="show")
def workspace_show() -> None:
    """Show all cached ZMK workspaces with enhanced metadata."""
    try:
        cache_manager, workspace_cache_service, user_config = (
            _get_cache_manager_and_service()
        )

        # Get cached workspaces using the new service
        cached_workspaces = workspace_cache_service.list_cached_workspaces()

        if not cached_workspaces:
            console.print("[yellow]No cached workspaces found[/yellow]")
            cache_dir = workspace_cache_service.get_cache_directory()
            console.print(f"[dim]Cache directory: {cache_dir}[/dim]")
            return

        # Create table with enhanced metadata
        table = Table(
            title=f"{Icons.get_icon('BUILD', 'emoji')} Cached ZMK Workspaces (Enhanced)",
            show_header=True,
            header_style="bold green",
        )
        table.add_column("Repository", style="cyan")
        table.add_column("Branch", style="yellow")
        table.add_column("Cache Level", style="magenta")
        table.add_column("Size", style="white")
        table.add_column("Age", style="blue")
        table.add_column("Components", style="green")
        table.add_column("Auto-Detected", style="dim")

        total_size = 0

        for metadata in sorted(cached_workspaces, key=lambda x: x.repository):
            size_bytes = metadata.size_bytes or _get_directory_size(
                metadata.workspace_path
            )
            total_size += size_bytes

            # Format age
            age_str = f"{metadata.age_hours:.1f}h"
            if metadata.age_hours > 24:
                age_str = f"{metadata.age_hours / 24:.1f}d"

            # Handle cache_level safely - could be string or enum
            cache_level_str = (
                metadata.cache_level.value
                if hasattr(metadata.cache_level, "value")
                else str(metadata.cache_level)
            )

            table.add_row(
                metadata.repository,
                metadata.branch,
                cache_level_str,
                _format_size(size_bytes),
                age_str,
                ", ".join(metadata.cached_components)
                if metadata.cached_components
                else "unknown",
                "✓" if metadata.auto_detected else "",
            )

        console.print(table)
        console.print(f"\n[bold]Total cache size:[/bold] {_format_size(total_size)}")
        console.print(f"[bold]Total workspaces:[/bold] {len(cached_workspaces)}")
        console.print("[dim]Cache managed by:[/dim] ZmkWorkspaceCacheService")

    except Exception as e:
        logger.error("Failed to show workspace cache: %s", e)
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e


@workspace_app.command(name="delete")
def workspace_delete(
    repository: Annotated[
        str | None,
        typer.Argument(
            help="Repository to delete (e.g., 'zmkfirmware/zmk'). Leave empty to delete all."
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force deletion without confirmation"),
    ] = False,
    all_workspaces: Annotated[
        bool,
        typer.Option("--all", help="Delete all cached workspaces"),
    ] = False,
) -> None:
    """Delete cached workspace(s) using ZmkWorkspaceCacheService."""
    try:
        cache_manager, workspace_cache_service, user_config = (
            _get_cache_manager_and_service()
        )

        if repository:
            # Get workspace metadata to show size before deletion
            cached_workspaces = workspace_cache_service.list_cached_workspaces()
            target_workspace = None

            for workspace in cached_workspaces:
                if workspace.repository == repository:
                    target_workspace = workspace
                    break

            if not target_workspace:
                console.print(
                    f"[yellow]No cached workspace found for {repository}[/yellow]"
                )
                return

            if not force:
                size_bytes = target_workspace.size_bytes or _get_directory_size(
                    target_workspace.workspace_path
                )
                confirm = typer.confirm(
                    f"Delete cached workspace for {repository} ({_format_size(size_bytes)})?"
                )
                if not confirm:
                    console.print("[yellow]Cancelled[/yellow]")
                    return

            # Use the workspace cache service for deletion
            success = workspace_cache_service.delete_cached_workspace(repository)

            if success:
                icon_mode = "emoji"
                console.print(
                    f"[green]{Icons.get_icon('SUCCESS', icon_mode)} Deleted cached workspace for {repository}[/green]"
                )
            else:
                console.print(
                    f"[red]Failed to delete cached workspace for {repository}[/red]"
                )
                raise typer.Exit(1)
        else:
            # Delete all workspaces
            cached_workspaces = workspace_cache_service.list_cached_workspaces()

            if not cached_workspaces:
                console.print("[yellow]No cached workspaces found[/yellow]")
                return

            total_size = sum(
                (workspace.size_bytes or _get_directory_size(workspace.workspace_path))
                for workspace in cached_workspaces
            )

            if not force:
                confirm = typer.confirm(
                    f"Delete ALL cached workspaces ({len(cached_workspaces)} workspaces, {_format_size(total_size)})?"
                )
                if not confirm:
                    console.print("[yellow]Cancelled[/yellow]")
                    return

            # Delete each workspace using the service
            deleted_count = 0
            for workspace in cached_workspaces:
                if workspace_cache_service.delete_cached_workspace(
                    workspace.repository
                ):
                    deleted_count += 1

            if deleted_count > 0:
                icon_mode = "emoji"
                console.print(
                    f"[green]{Icons.get_icon('SUCCESS', icon_mode)} Deleted {deleted_count} cached workspaces ({_format_size(total_size)})[/green]"
                )
            else:
                console.print("[red]Failed to delete any cached workspaces[/red]")
                raise typer.Exit(1)

    except Exception as e:
        logger.error("Failed to delete workspace cache: %s", e)
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e


@workspace_app.command(name="cleanup")
def workspace_cleanup(
    max_age_days: Annotated[
        float,
        typer.Option(
            "--max-age",
            help="Clean up workspaces older than specified days (default: 7 days)",
        ),
    ] = 7.0,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force cleanup without confirmation"),
    ] = False,
) -> None:
    """Clean up stale cached workspaces using ZmkWorkspaceCacheService."""
    try:
        cache_manager, workspace_cache_service, user_config = (
            _get_cache_manager_and_service()
        )

        max_age_hours = max_age_days * 24

        # List workspaces that would be cleaned up
        cached_workspaces = workspace_cache_service.list_cached_workspaces()
        stale_workspaces = [
            workspace
            for workspace in cached_workspaces
            if workspace.age_hours > max_age_hours
        ]

        if not stale_workspaces:
            console.print(
                f"[green]No workspaces older than {max_age_days} days found[/green]"
            )
            return

        total_stale_size = sum(
            (workspace.size_bytes or _get_directory_size(workspace.workspace_path))
            for workspace in stale_workspaces
        )

        console.print(
            f"[yellow]Found {len(stale_workspaces)} stale workspaces ({_format_size(total_stale_size)})[/yellow]"
        )

        if not force:
            console.print("\n[bold]Workspaces to be cleaned up:[/bold]")
            for workspace in stale_workspaces:
                age_days = workspace.age_hours / 24
                size_bytes = workspace.size_bytes or _get_directory_size(
                    workspace.workspace_path
                )
                console.print(
                    f"  • {workspace.repository}@{workspace.branch}: {_format_size(size_bytes)} (age: {age_days:.1f}d)"
                )

            confirm = typer.confirm(
                f"\nClean up these {len(stale_workspaces)} workspaces?"
            )
            if not confirm:
                console.print("[yellow]Cancelled[/yellow]")
                return

        # Perform cleanup using the service
        cleaned_count = workspace_cache_service.cleanup_stale_entries(max_age_hours)

        if cleaned_count > 0:
            icon_mode = "emoji"
            console.print(
                f"[green]{Icons.get_icon('SUCCESS', icon_mode)} Cleaned up {cleaned_count} stale workspaces ({_format_size(total_stale_size)})[/green]"
            )
        else:
            console.print("[yellow]No workspaces were cleaned up[/yellow]")

    except Exception as e:
        logger.error("Failed to cleanup workspace cache: %s", e)
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e


@cache_app.command(name="show")
def cache_show(
    module: Annotated[
        str | None,
        typer.Option("-m", "--module", help="Show detailed info for specific module"),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option("-l", "--limit", help="Limit number of entries shown"),
    ] = None,
    offset: Annotated[
        int | None,
        typer.Option("-o", "--offset", help="Offset for pagination"),
    ] = None,
) -> None:
    """Show unified cache information and statistics from both workspace and DiskCache systems."""
    try:
        cache_manager = _get_cache_manager()

        console.print("[bold]Glovebox Cache System Overview[/bold]")
        console.print("=" * 50)

        # Show workspace cache information using the service
        console.print("\n[bold cyan]1. Workspace Cache (ZMK Workspaces)[/bold cyan]")
        cache_manager, workspace_cache_service, user_config = (
            _get_cache_manager_and_service()
        )

        cache_dir = workspace_cache_service.get_cache_directory()
        cached_workspaces = workspace_cache_service.list_cached_workspaces()

        if cached_workspaces:
            total_workspace_size = sum(
                (workspace.size_bytes or _get_directory_size(workspace.workspace_path))
                for workspace in cached_workspaces
            )

            console.print(f"[bold]Location:[/bold] {cache_dir}")
            console.print(f"[bold]Cached Workspaces:[/bold] {len(cached_workspaces)}")
            console.print(
                f"[bold]Total Size:[/bold] {_format_size(total_workspace_size)}"
            )
            console.print("[bold]Managed by:[/bold] ZmkWorkspaceCacheService")

            if not module:
                console.print("\n[bold]Workspace Details:[/bold]")
                start_idx = offset or 0
                end_idx = start_idx + (limit or len(cached_workspaces))

                for workspace in sorted(cached_workspaces, key=lambda x: x.repository)[
                    start_idx:end_idx
                ]:
                    size_bytes = workspace.size_bytes or _get_directory_size(
                        workspace.workspace_path
                    )

                    # Format age
                    age_str = f"{workspace.age_hours:.1f}h"
                    if workspace.age_hours > 24:
                        age_str = f"{workspace.age_hours / 24:.1f}d"

                    auto_detected_marker = " [auto]" if workspace.auto_detected else ""
                    components_str = (
                        f" [{'/'.join(workspace.cached_components)}]"
                        if workspace.cached_components
                        else ""
                    )

                    # Handle cache_level safely
                    cache_level_str = (
                        workspace.cache_level.value
                        if hasattr(workspace.cache_level, "value")
                        else str(workspace.cache_level)
                    )

                    console.print(
                        f"  • {workspace.repository}@{workspace.branch}: {_format_size(size_bytes)} "
                        f"(level: {cache_level_str}, age: {age_str}){auto_detected_marker}{components_str}"
                    )
        else:
            console.print("[yellow]No cached workspaces found[/yellow]")
            console.print(f"[dim]Cache directory: {cache_dir}[/dim]")

        # Show DiskCache information
        console.print("\n[bold cyan]2. DiskCache System (Modules)[/bold cyan]")
        try:
            user_config = create_user_config()
            diskcache_root = user_config._config.cache_path

            if diskcache_root.exists():
                cache_subdirs = [d for d in diskcache_root.iterdir() if d.is_dir()]
                total_diskcache_size = sum(
                    _get_directory_size(d) for d in cache_subdirs
                )

                console.print(f"[bold]Location:[/bold] {diskcache_root}")
                console.print(
                    f"[bold]Cache Strategy:[/bold] {user_config._config.cache_strategy}"
                )
                console.print(f"[bold]Cached Modules:[/bold] {len(cache_subdirs)}")
                console.print(
                    f"[bold]Total Size:[/bold] {_format_size(total_diskcache_size)}"
                )

                if cache_subdirs:
                    if module:
                        # Show detailed info for specific module
                        module_dir = diskcache_root / module
                        if module_dir.exists():
                            module_size = _get_directory_size(module_dir)
                            console.print(f"\n[bold]Module '{module}' Details:[/bold]")
                            console.print(f"  • Location: {module_dir}")
                            console.print(f"  • Size: {_format_size(module_size)}")
                            console.print(
                                f"  • Files: {len(list(module_dir.rglob('*')))}"
                            )
                        else:
                            console.print(
                                f"[yellow]Module '{module}' not found in cache[/yellow]"
                            )
                    else:
                        console.print("\n[bold]Module Caches:[/bold]")
                        start_idx = offset or 0
                        end_idx = start_idx + (limit or len(cache_subdirs))

                        for cache_dir in sorted(cache_subdirs)[start_idx:end_idx]:
                            module_name = cache_dir.name
                            size = _get_directory_size(cache_dir)
                            console.print(f"  • {module_name}: {_format_size(size)}")
            else:
                console.print("[yellow]No DiskCache directory found[/yellow]")
                console.print(f"[dim]Would be located at: {diskcache_root}[/dim]")
        except Exception as e:
            console.print(f"[red]Error accessing DiskCache info: {e}[/red]")

        # Show usage instructions
        console.print("\n[bold cyan]3. Cache Management Commands[/bold cyan]")
        console.print("[dim]Workspace cache:[/dim]")
        console.print("  • glovebox cache workspace show")
        console.print("  • glovebox cache workspace add <path>")
        console.print("  • glovebox cache workspace delete [repository]")
        console.print("  • glovebox cache workspace cleanup [--max-age <days>]")
        console.print("[dim]Module cache:[/dim]")
        console.print("  • glovebox cache clear -m <module>")
        console.print("  • glovebox cache clear --max-age <days>")
        console.print("  • glovebox cache show -m <module>")

    except Exception as e:
        logger.error("Failed to show cache info: %s", e)
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e


@workspace_app.command(name="add")
def workspace_add(
    workspace_path: Annotated[
        Path,
        typer.Argument(help="Path to existing ZMK workspace directory"),
    ],
    repository: Annotated[
        str | None,
        typer.Option(
            "--repository",
            "-r",
            help="Repository name (e.g., 'zmkfirmware/zmk'). Auto-detected if not provided.",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing cache"),
    ] = False,
) -> None:
    """Add an existing ZMK workspace to cache with auto-detection support.

    This allows you to cache a workspace you've already built locally,
    with enhanced auto-detection of git repository info and workspace structure.

    Your workspace should contain directories like: zmk/, zephyr/, modules/
    """
    try:
        cache_manager, workspace_cache_service, user_config = (
            _get_cache_manager_and_service()
        )
        workspace_path = workspace_path.resolve()
        icon_mode = "emoji"  # Default icon mode

        # Use the new workspace cache service for adding external workspace
        result = workspace_cache_service.add_external_workspace(
            source_path=workspace_path, repository=repository, force=force
        )

        if result.success and result.metadata:
            # Display success information with enhanced metadata
            metadata = result.metadata

            console.print(
                f"\n[green]{Icons.format_with_icon('SUCCESS', 'Successfully added workspace cache', icon_mode)}[/green]"
            )
            console.print(
                f"[bold]Repository:[/bold] {metadata.repository}@{metadata.branch}"
            )
            console.print(f"[bold]Cache location:[/bold] {metadata.workspace_path}")

            if metadata.size_bytes:
                console.print(
                    f"[bold]Total size:[/bold] {_format_size(metadata.size_bytes)}"
                )

            if metadata.cached_components:
                console.print(
                    f"[bold]Components cached:[/bold] {', '.join(metadata.cached_components)}"
                )

            # Handle cache_level safely
            cache_level_str = (
                metadata.cache_level.value
                if hasattr(metadata.cache_level, "value")
                else str(metadata.cache_level)
            )
            console.print(f"[bold]Cache level:[/bold] {cache_level_str}")

            if metadata.auto_detected:
                console.print(
                    f"[bold]Auto-detected from:[/bold] {metadata.auto_detected_source}"
                )

            console.print(
                f"\n[dim]Future builds using '{metadata.repository}' will now use this cache![/dim]"
            )
        elif result.success:
            # Success but no metadata (shouldn't happen, but handle gracefully)
            console.print(
                f"\n[green]{Icons.format_with_icon('SUCCESS', 'Successfully added workspace cache', icon_mode)}[/green]"
            )
        else:
            console.print(
                f"[red]Failed to add workspace to cache: {result.error_message}[/red]"
            )
            raise typer.Exit(1)

    except Exception as e:
        logger.error("Failed to add workspace to cache: %s", e)
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e


@cache_app.command(name="clear")
def cache_clear(
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
    and age-based cleanup using the cache_v2 system.
    """
    try:
        user_config = create_user_config()
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
                size = _get_directory_size(module_cache_dir)
                confirm = typer.confirm(
                    f"Clear cache for module '{module}' ({_format_size(size)})?"
                )
                if not confirm:
                    console.print("[yellow]Cancelled[/yellow]")
                    return

            try:
                shutil.rmtree(module_cache_dir)

                icon_mode = "emoji"
                console.print(
                    f"[green]{Icons.get_icon('SUCCESS', icon_mode)} Cleared cache for module '{module}'[/green]"
                )
            except Exception as e:
                console.print(f"[red]Failed to clear module cache: {e}[/red]")
                raise typer.Exit(1) from e

        elif max_age_days is not None:
            # Age-based cleanup using cache_v2 system
            try:
                cache_manager = _get_cache_manager()
                cache_stats = cache_manager.get_stats()

                console.print(
                    f"[blue]Cleaning up cache entries older than {max_age_days} days...[/blue]"
                )

                # Use cache_v2's built-in cleanup if available
                if hasattr(cache_manager, "cleanup"):
                    cache_manager.cleanup()

                icon_mode = "emoji"
                console.print(
                    Icons.format_with_icon(
                        "SUCCESS",
                        "Cache cleanup completed using cache_v2 system.",
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

            total_size = sum(_get_directory_size(d) for d in cache_subdirs)

            if not force:
                confirm = typer.confirm(
                    f"Clear ALL cache directories ({len(cache_subdirs)} modules, {_format_size(total_size)})?"
                )
                if not confirm:
                    console.print("[yellow]Cancelled[/yellow]")
                    return

            try:
                # Clear cache_v2 system
                cache_manager = _get_cache_manager()
                cache_manager.clear()

                # Clear filesystem directories
                for cache_dir in cache_subdirs:
                    shutil.rmtree(cache_dir)

                icon_mode = "emoji"
                console.print(
                    f"[green]{Icons.get_icon('SUCCESS', icon_mode)} Cleared all cache directories ({_format_size(total_size)})[/green]"
                )
                console.print("[green]Cleared cache_v2 system entries[/green]")
            except Exception as e:
                console.print(f"[red]Failed to clear cache: {e}[/red]")
                raise typer.Exit(1) from e

    except Exception as e:
        logger.error("Failed to clear cache: %s", e)

        icon_mode = "emoji"
        typer.echo(Icons.format_with_icon("ERROR", f"Error: {e}", icon_mode), err=True)
        raise typer.Exit(1) from e
