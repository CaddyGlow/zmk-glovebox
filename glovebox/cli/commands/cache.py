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
from glovebox.config.user_config import create_user_config
from glovebox.core.cache_v2 import create_cache_from_user_config
from glovebox.core.cache_v2.cache_manager import CacheManager
from glovebox.core.workspace_cache_utils import (
    detect_git_info,
    generate_workspace_cache_key,
    get_workspace_cache_dir,
    get_workspace_cache_ttls,
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


def _get_cache_manager() -> CacheManager:
    """Get cache manager using user config."""
    try:
        user_config = create_user_config()
        return create_cache_from_user_config(user_config, tag="workspace")
    except Exception:
        # Fallback to default cache if user config fails
        from glovebox.core.cache_v2 import create_default_cache

        return create_default_cache(tag="workspace")


@workspace_app.command(name="show")
def workspace_show() -> None:
    """Show all cached ZMK workspaces with metadata from cache_v2."""
    try:
        cache_manager = _get_cache_manager()
        cache_dir = get_workspace_cache_dir()

        if not cache_dir.exists():
            console.print("[yellow]No workspace cache directory found[/yellow]")
            return

        cached_workspaces = list(cache_dir.iterdir())

        if not cached_workspaces:
            console.print("[yellow]No cached workspaces found[/yellow]")
            return

        # Note: We can't get app context here since this function doesn't have ctx parameter
        # Using emoji icon mode as fallback for this case
        table = Table(
            title=f"{Icons.get_icon('BUILD', 'emoji')} Cached ZMK Workspaces (cache_v2)",
            show_header=True,
            header_style="bold green",
        )
        table.add_column("Repository", style="cyan")
        table.add_column("Branch", style="yellow")
        table.add_column("Cache Level", style="magenta")
        table.add_column("Size", style="white")
        table.add_column("Components", style="green")

        total_size = 0

        for workspace_dir in sorted(cached_workspaces):
            if workspace_dir.is_dir():
                repo_name = workspace_dir.name.replace("_", "/")
                size = _get_directory_size(workspace_dir)
                total_size += size

                # Check what components are cached
                components = []
                for component in ["zmk", "zephyr", "modules"]:
                    if (workspace_dir / component).exists():
                        components.append(component)

                # Try to detect git info and cache level from cache_v2
                git_info = detect_git_info(workspace_dir)
                branch = git_info.get("branch", "unknown")

                # Check cache levels using cache_v2
                cache_levels = []
                for level in ["base", "branch", "full"]:
                    cache_key = generate_workspace_cache_key(repo_name, branch, level)
                    if cache_manager.exists(cache_key):
                        cache_levels.append(level)

                level_str = "/".join(cache_levels) if cache_levels else "legacy"

                table.add_row(
                    repo_name,
                    branch,
                    level_str,
                    _format_size(size),
                    ", ".join(components) if components else "empty",
                )

        console.print(table)
        console.print(f"\n[bold]Total cache size:[/bold] {_format_size(total_size)}")
        console.print("[dim]Cache managed by:[/dim] glovebox/core/cache_v2")

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
    """Delete cached workspace(s) using cache_v2 system."""
    try:
        cache_manager = _get_cache_manager()
        cache_dir = get_workspace_cache_dir()

        if not cache_dir.exists():
            console.print("[yellow]No workspace cache directory found[/yellow]")
            return

        if repository:
            # Clear specific repository
            repo_cache_name = repository.replace("/", "_").replace("-", "_")
            workspace_dir = cache_dir / repo_cache_name

            if not workspace_dir.exists():
                console.print(
                    f"[yellow]No cached workspace found for {repository}[/yellow]"
                )
                return

            if not force:
                size = _get_directory_size(workspace_dir)
                confirm = typer.confirm(
                    f"Delete cached workspace for {repository} ({_format_size(size)})?"
                )
                if not confirm:
                    console.print("[yellow]Cancelled[/yellow]")
                    return

            try:
                # Remove from cache_v2 system first
                git_info = detect_git_info(workspace_dir)
                branch = git_info.get("branch", "main")

                for level in ["base", "branch", "full"]:
                    cache_key = generate_workspace_cache_key(repository, branch, level)
                    if cache_manager.exists(cache_key):
                        cache_manager.delete(cache_key)
                        logger.debug("Deleted cache_v2 entry: %s", cache_key)

                # Remove filesystem directory
                shutil.rmtree(workspace_dir)

                icon_mode = "emoji"
                console.print(
                    f"[green]{Icons.get_icon('SUCCESS', icon_mode)} Deleted cached workspace for {repository}[/green]"
                )
            except Exception as e:
                console.print(f"[red]Failed to delete cache: {e}[/red]")
                raise typer.Exit(1) from e
        else:
            # Clear all workspaces (or if --all flag is used)
            cached_workspaces = list(cache_dir.iterdir())

            if not cached_workspaces:
                console.print("[yellow]No cached workspaces found[/yellow]")
                return

            total_size = sum(
                _get_directory_size(d) for d in cached_workspaces if d.is_dir()
            )

            if not force:
                confirm = typer.confirm(
                    f"Delete ALL cached workspaces ({len(cached_workspaces)} workspaces, {_format_size(total_size)})?"
                )
                if not confirm:
                    console.print("[yellow]Cancelled[/yellow]")
                    return

            try:
                # Clear all cache_v2 entries
                for workspace_dir in cached_workspaces:
                    if workspace_dir.is_dir():
                        repo_name = workspace_dir.name.replace("_", "/")
                        git_info = detect_git_info(workspace_dir)
                        branch = git_info.get("branch", "main")

                        for level in ["base", "branch", "full"]:
                            cache_key = generate_workspace_cache_key(
                                repo_name, branch, level
                            )
                            if cache_manager.exists(cache_key):
                                cache_manager.delete(cache_key)

                # Remove filesystem directory
                shutil.rmtree(cache_dir)

                icon_mode = "emoji"
                console.print(
                    f"[green]{Icons.get_icon('SUCCESS', icon_mode)} Deleted all cached workspaces ({_format_size(total_size)})[/green]"
                )
            except Exception as e:
                console.print(f"[red]Failed to delete cache: {e}[/red]")
                raise typer.Exit(1) from e

    except Exception as e:
        logger.error("Failed to delete workspace cache: %s", e)
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

        # Show workspace cache information
        console.print("\n[bold cyan]1. Workspace Cache (ZMK Workspaces)[/bold cyan]")
        cache_dir = get_workspace_cache_dir()

        if cache_dir.exists():
            cached_workspaces = [d for d in cache_dir.iterdir() if d.is_dir()]
            total_workspace_size = sum(
                _get_directory_size(d) for d in cached_workspaces
            )

            console.print(f"[bold]Location:[/bold] {cache_dir}")
            console.print(f"[bold]Cached Workspaces:[/bold] {len(cached_workspaces)}")
            console.print(
                f"[bold]Total Size:[/bold] {_format_size(total_workspace_size)}"
            )
            console.print("[bold]Managed by:[/bold] glovebox/core/cache_v2")

            if cached_workspaces and not module:
                console.print("\n[bold]Workspace Details:[/bold]")
                start_idx = offset or 0
                end_idx = start_idx + (limit or len(cached_workspaces))

                for workspace_dir in sorted(cached_workspaces)[start_idx:end_idx]:
                    repo_name = workspace_dir.name.replace("_", "/")
                    size = _get_directory_size(workspace_dir)

                    # Check cache levels
                    git_info = detect_git_info(workspace_dir)
                    branch = git_info.get("branch", "main")
                    cache_levels = []
                    for level in ["base", "branch", "full"]:
                        cache_key = generate_workspace_cache_key(
                            repo_name, branch, level
                        )
                        if cache_manager.exists(cache_key):
                            cache_levels.append(level)

                    level_str = "/".join(cache_levels) if cache_levels else "legacy"
                    console.print(
                        f"  • {repo_name}@{branch}: {_format_size(size)} [{level_str}]"
                    )
        else:
            console.print("[yellow]No workspace cache directory found[/yellow]")
            console.print(f"[dim]Would be located at: {cache_dir}[/dim]")

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
    """Add an existing ZMK workspace to cache using cache_v2 system.

    This allows you to cache a workspace you've already built locally,
    with auto-detection of git repository info and ZMK workspace structure.

    Your workspace should contain directories like: zmk/, zephyr/, modules/
    """
    try:
        cache_manager = _get_cache_manager()
        workspace_path = workspace_path.resolve()
        icon_mode = "emoji"  # Default icon mode
        target_cache_dir: Path | None = None  # Initialize for cleanup

        if not workspace_path.exists():
            console.print(
                f"[red]Error: Workspace directory does not exist: {workspace_path}[/red]"
            )
            raise typer.Exit(1)

        if not workspace_path.is_dir():
            console.print(
                f"[red]Error: Path is not a directory: {workspace_path}[/red]"
            )
            raise typer.Exit(1)

        # Auto-detect git repository info if not provided
        if not repository:
            git_info = detect_git_info(workspace_path)
            repository = git_info["repository"]
            branch = git_info["branch"]
            console.print(
                f"[blue]Auto-detected repository: {repository}@{branch}[/blue]"
            )
        else:
            git_info = detect_git_info(workspace_path)
            branch = git_info.get("branch", "main")

        # Check for required ZMK workspace components
        required_dirs = ["zmk", "zephyr", "modules"]
        missing_dirs = []
        existing_dirs = []

        for dir_name in required_dirs:
            dir_path = workspace_path / dir_name
            if dir_path.exists() and dir_path.is_dir():
                existing_dirs.append(dir_name)
            else:
                missing_dirs.append(dir_name)

        if not existing_dirs:
            console.print(
                f"[red]Error: No ZMK workspace components found in {workspace_path}[/red]"
            )
            console.print(
                f"[yellow]Expected directories: {', '.join(required_dirs)}[/yellow]"
            )
            raise typer.Exit(1)

        if missing_dirs:
            console.print(
                f"[yellow]Warning: Missing components: {', '.join(missing_dirs)}[/yellow]"
            )
            console.print(
                f"[green]Found components: {', '.join(existing_dirs)}[/green]"
            )

            if not typer.confirm("Continue with partial workspace?"):
                console.print("[yellow]Cancelled[/yellow]")
                return

        # Set up cache directory
        cache_dir = get_workspace_cache_dir()
        repo_cache_name = repository.replace("/", "_").replace("-", "_")
        target_cache_dir = cache_dir / repo_cache_name

        # Check if already cached in cache_v2
        base_key = generate_workspace_cache_key(repository, branch, "base")
        if cache_manager.exists(base_key) and not force:
            console.print(f"[yellow]Workspace already cached for {repository}[/yellow]")
            if not typer.confirm("Overwrite existing cache?"):
                console.print("[yellow]Cancelled[/yellow]")
                return

        if target_cache_dir.exists() and not force:
            console.print(
                f"[yellow]Cache directory already exists for {repository}[/yellow]"
            )
            if not typer.confirm("Overwrite existing cache?"):
                console.print("[yellow]Cancelled[/yellow]")
                return

        # Create cache directory
        target_cache_dir.mkdir(parents=True, exist_ok=True)

        # Copy workspace components
        console.print(
            f"[blue]Adding workspace to cache: {workspace_path} -> {repository}[/blue]"
        )

        total_size = 0
        for dir_name in existing_dirs:
            src_dir = workspace_path / dir_name
            dest_dir = target_cache_dir / dir_name

            console.print(f"  • Copying {dir_name}...")

            # Remove existing if it exists
            if dest_dir.exists():
                shutil.rmtree(dest_dir)

            # Copy directory
            shutil.copytree(src_dir, dest_dir)

            # Calculate size
            dir_size = _get_directory_size(dest_dir)
            total_size += dir_size

            console.print(
                f"    {Icons.get_icon('SUCCESS', icon_mode)} {dir_name}: {_format_size(dir_size)}"
            )

        # Store in cache_v2 with tiered TTLs (following ZmkWestService pattern)
        ttls = get_workspace_cache_ttls()
        base_key = generate_workspace_cache_key(repository, branch, "base")
        branch_key = generate_workspace_cache_key(repository, branch, "branch")
        full_key = generate_workspace_cache_key(repository, branch, "full")

        cache_manager.set(base_key, str(target_cache_dir), ttl=ttls["base"])
        cache_manager.set(branch_key, str(target_cache_dir), ttl=ttls["branch"])
        cache_manager.set(full_key, str(target_cache_dir), ttl=ttls["full"])

        console.print(
            f"\n[green]{Icons.format_with_icon('SUCCESS', f'Successfully added workspace cache for {repository}', icon_mode)}[/green]"
        )
        console.print(f"[bold]Repository:[/bold] {repository}@{branch}")
        console.print(f"[bold]Cache location:[/bold] {target_cache_dir}")
        console.print(f"[bold]Total size:[/bold] {_format_size(total_size)}")
        console.print(f"[bold]Components cached:[/bold] {', '.join(existing_dirs)}")
        console.print("[bold]Cache levels:[/bold] base/branch/full (cache_v2)")

        console.print(
            f"\n[dim]Future builds using '{repository}' will now use this cache![/dim]"
        )

    except Exception as e:
        logger.error("Failed to add workspace to cache: %s", e)
        console.print(f"[red]Error: {e}[/red]")
        # Clean up partial cache on failure
        if target_cache_dir is not None and target_cache_dir.exists():
            with contextlib.suppress(Exception):
                shutil.rmtree(target_cache_dir)
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
