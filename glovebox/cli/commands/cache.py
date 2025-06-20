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
from glovebox.compilation.cache import inject_base_dependencies_cache_from_workspace


logger = logging.getLogger(__name__)
console = Console()

cache_app = typer.Typer(help="Cache management commands")


def _get_workspace_cache_dir() -> Path:
    """Get workspace cache directory."""
    return Path.home() / ".cache" / "glovebox" / "workspaces"


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


@cache_app.command(name="inject-base-deps")
def inject_base_deps_command(
    workspace_path: Annotated[
        Path,
        typer.Argument(help="Path to existing workspace with ZMK dependencies"),
    ],
    zmk_repo_url: Annotated[
        str,
        typer.Option("--zmk-repo", help="ZMK repository URL"),
    ] = "zmkfirmware/zmk",
    zmk_revision: Annotated[
        str,
        typer.Option("--zmk-revision", help="ZMK revision/branch"),
    ] = "main",
    cache_root: Annotated[
        Path | None,
        typer.Option("--cache-root", help="Cache root directory"),
    ] = None,
) -> None:
    """Inject base dependencies cache from existing workspace.

    This command creates a new base dependencies cache entry from an existing
    workspace that already contains ZMK dependencies (zephyr, zmk, modules).

    Args:
        workspace_path: Path to existing workspace with ZMK dependencies
        zmk_repo_url: ZMK repository URL for cache key generation
        zmk_revision: ZMK revision for cache key generation
        cache_root: Root directory for cache storage
    """
    try:
        workspace_path = workspace_path.resolve()

        typer.echo(
            f"Injecting base dependencies cache from workspace: {workspace_path}"
        )
        typer.echo(f"ZMK repository: {zmk_repo_url}@{zmk_revision}")

        if cache_root:
            typer.echo(f"Cache root: {cache_root}")

        cache_key = inject_base_dependencies_cache_from_workspace(
            source_workspace=workspace_path,
            zmk_repo_url=zmk_repo_url,
            zmk_revision=zmk_revision,
            cache_root=cache_root,
        )

        # Note: This function doesn't have ctx parameter, using default icon mode
        icon_mode = "emoji"
        typer.echo(
            Icons.format_with_icon(
                "SUCCESS", "Base dependencies cache injected successfully!", icon_mode
            )
        )
        typer.echo(f"Cache key: {cache_key}")

    except Exception as e:
        logger.error("Failed to inject base dependencies cache: %s", e)
        typer.echo(Icons.format_with_icon("ERROR", f"Error: {e}", icon_mode), err=True)
        raise typer.Exit(1) from e


@cache_app.command(name="list-base-deps")
def list_base_deps_command(
    cache_root: Annotated[
        Path | None,
        typer.Option("--cache-root", help="Cache root directory"),
    ] = None,
) -> None:
    """List base dependencies cache entries."""
    try:
        from glovebox.compilation.cache.base_dependencies_cache import (
            create_base_dependencies_cache,
        )

        base_cache = create_base_dependencies_cache(cache_root=cache_root)

        if not base_cache.cache_root.exists():
            typer.echo("No base dependencies cache found.")
            return

        typer.echo(f"Base dependencies cache location: {base_cache.cache_root}")
        typer.echo()

        cache_entries = list(base_cache.cache_root.iterdir())
        if not cache_entries:
            typer.echo("No cache entries found.")
            return

        typer.echo("Available cache entries:")
        for entry in sorted(cache_entries):
            if entry.is_dir():
                metadata_file = entry / ".glovebox_cache_metadata.json"
                if metadata_file.exists():
                    try:
                        import json

                        metadata = json.loads(metadata_file.read_text())
                        created_at = metadata.get("created_at", "unknown")
                        zmk_repo = metadata.get("zmk_repo_url", "unknown")
                        zmk_revision = metadata.get("zmk_revision", "unknown")

                        from glovebox.cli.helpers.theme import Icons

                        # Note: This function doesn't have ctx parameter, using default icon mode
                        icon_mode = "emoji"
                        typer.echo(
                            f"  {Icons.get_icon('BUILD', icon_mode)} {entry.name}"
                        )
                        typer.echo(f"     ZMK: {zmk_repo}@{zmk_revision}")
                        typer.echo(f"     Created: {created_at}")
                        typer.echo()
                    except Exception:
                        typer.echo(
                            f"  {Icons.get_icon('BUILD', icon_mode)} {entry.name} (metadata unavailable)"
                        )
                        typer.echo()
                else:
                    typer.echo(
                        f"  {Icons.get_icon('BUILD', icon_mode)} {entry.name} (no metadata)"
                    )
                    typer.echo()

    except Exception as e:
        logger.error("Failed to list base dependencies cache: %s", e)
        typer.echo(Icons.format_with_icon("ERROR", f"Error: {e}", icon_mode), err=True)
        raise typer.Exit(1) from e


@cache_app.command(name="list-workspaces")
def list_workspaces() -> None:
    """List all cached workspaces."""
    cache_dir = _get_workspace_cache_dir()

    if not cache_dir.exists():
        console.print("[yellow]No workspace cache directory found[/yellow]")
        return

    cached_workspaces = list(cache_dir.iterdir())

    if not cached_workspaces:
        console.print("[yellow]No cached workspaces found[/yellow]")
        return

    from glovebox.cli.helpers.theme import Icons

    # Note: We can't get app context here since this function doesn't have ctx parameter
    # Using emoji icon mode as fallback for this case
    table = Table(
        title=f"{Icons.get_icon('BUILD', 'emoji')} Cached ZMK Workspaces",
        show_header=True,
        header_style="bold green",
    )
    table.add_column("Repository", style="cyan")
    table.add_column("Size", style="white")
    table.add_column("Components", style="yellow")

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

            table.add_row(
                repo_name,
                _format_size(size),
                ", ".join(components) if components else "empty",
            )

    console.print(table)
    console.print(f"\n[bold]Total cache size:[/bold] {_format_size(total_size)}")


@cache_app.command(name="clear-workspaces")
def clear_workspace(
    repository: Annotated[
        str | None,
        typer.Argument(
            help="Repository to clear (e.g., 'zmkfirmware/zmk'). Leave empty to clear all."
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force deletion without confirmation"),
    ] = False,
) -> None:
    """Clear cached workspace(s)."""
    cache_dir = _get_workspace_cache_dir()

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
                f"Clear cached workspace for {repository} ({_format_size(size)})?"
            )
            if not confirm:
                console.print("[yellow]Cancelled[/yellow]")
                return

        try:
            shutil.rmtree(workspace_dir)
            from glovebox.cli.helpers.theme import Icons

            # Note: This function doesn't have ctx parameter, using default icon mode
            icon_mode = "emoji"
            console.print(
                f"[green]{Icons.get_icon('SUCCESS', icon_mode)} Cleared cached workspace for {repository}[/green]"
            )
        except Exception as e:
            console.print(f"[red]Failed to clear cache: {e}[/red]")
            raise typer.Exit(1) from e
    else:
        # Clear all workspaces
        cached_workspaces = list(cache_dir.iterdir())

        if not cached_workspaces:
            console.print("[yellow]No cached workspaces found[/yellow]")
            return

        total_size = sum(
            _get_directory_size(d) for d in cached_workspaces if d.is_dir()
        )

        if not force:
            confirm = typer.confirm(
                f"Clear ALL cached workspaces ({len(cached_workspaces)} workspaces, {_format_size(total_size)})?"
            )
            if not confirm:
                console.print("[yellow]Cancelled[/yellow]")
                return

        try:
            shutil.rmtree(cache_dir)
            console.print(
                f"[green]{Icons.get_icon('SUCCESS', icon_mode)} Cleared all cached workspaces ({_format_size(total_size)})[/green]"
            )
        except Exception as e:
            console.print(f"[red]Failed to clear cache: {e}[/red]")
            raise typer.Exit(1) from e


@cache_app.command(name="info")
def cache_info() -> None:
    """Show cache information and statistics."""
    cache_dir = _get_workspace_cache_dir()

    if not cache_dir.exists():
        console.print("[yellow]No workspace cache directory found[/yellow]")
        console.print(f"[dim]Cache directory would be: {cache_dir}[/dim]")
        return

    cached_workspaces = [d for d in cache_dir.iterdir() if d.is_dir()]
    total_size = sum(_get_directory_size(d) for d in cached_workspaces)

    console.print(f"[bold]Cache Directory:[/bold] {cache_dir}")
    console.print(f"[bold]Cached Workspaces:[/bold] {len(cached_workspaces)}")
    console.print(f"[bold]Total Size:[/bold] {_format_size(total_size)}")

    if cached_workspaces:
        console.print("\n[bold]Cached Repositories:[/bold]")
        for workspace_dir in sorted(cached_workspaces):
            repo_name = workspace_dir.name.replace("_", "/")
            size = _get_directory_size(workspace_dir)
            console.print(f"  • {repo_name}: {_format_size(size)}")

    console.print("\n[dim]To clear cache: glovebox cache clear-workspaces[/dim]")
    console.print("[dim]To list details: glovebox cache list-workspaces[/dim]")


@cache_app.command(name="import-workspace")
def import_workspace(
    workspace_path: Annotated[
        Path,
        typer.Argument(help="Path to existing ZMK workspace directory"),
    ],
    repository: Annotated[
        str,
        typer.Option(
            "--repository", "-r", help="Repository name (e.g., 'zmkfirmware/zmk')"
        ),
    ] = "zmkfirmware/zmk",
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing cache"),
    ] = False,
) -> None:
    """Import an existing ZMK workspace into the cache.

    This allows you to cache a workspace you've already built locally,
    so future compilations can use it instead of downloading everything again.

    Your workspace should contain directories like: zmk/, zephyr/, modules/
    """
    workspace_path = workspace_path.resolve()

    if not workspace_path.exists():
        console.print(
            f"[red]Error: Workspace directory does not exist: {workspace_path}[/red]"
        )
        raise typer.Exit(1)

    if not workspace_path.is_dir():
        console.print(f"[red]Error: Path is not a directory: {workspace_path}[/red]")
        raise typer.Exit(1)

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
        console.print(f"[green]Found components: {', '.join(existing_dirs)}[/green]")

        if not typer.confirm("Continue with partial workspace?"):
            console.print("[yellow]Cancelled[/yellow]")
            return

    # Set up cache directory
    cache_dir = _get_workspace_cache_dir()
    repo_cache_name = repository.replace("/", "_").replace("-", "_")
    target_cache_dir = cache_dir / repo_cache_name

    if target_cache_dir.exists() and not force:
        console.print(f"[yellow]Cache already exists for {repository}[/yellow]")
        if not typer.confirm("Overwrite existing cache?"):
            console.print("[yellow]Cancelled[/yellow]")
            return

    try:
        # Create cache directory
        target_cache_dir.mkdir(parents=True, exist_ok=True)

        # Copy workspace components
        console.print(f"[blue]Importing workspace from {workspace_path}...[/blue]")

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
            from glovebox.cli.helpers.theme import Icons

            # Note: This function doesn't have ctx parameter, using default icon mode
            icon_mode = "emoji"
            console.print(
                f"    {Icons.get_icon('SUCCESS', icon_mode)} {dir_name}: {_format_size(dir_size)}"
            )

        console.print(
            f"\n[green]{Icons.format_with_icon('SUCCESS', f'Successfully imported workspace cache for {repository}', icon_mode)}[/green]"
        )
        console.print(f"[bold]Cache location:[/bold] {target_cache_dir}")
        console.print(f"[bold]Total size:[/bold] {_format_size(total_size)}")
        console.print(f"[bold]Components cached:[/bold] {', '.join(existing_dirs)}")

        console.print(
            f"\n[dim]Future builds using '{repository}' will now use this cache![/dim]"
        )

    except Exception as e:
        console.print(f"[red]Failed to import workspace: {e}[/red]")
        # Clean up partial cache on failure
        if target_cache_dir.exists():
            with contextlib.suppress(Exception):
                shutil.rmtree(target_cache_dir)
        raise typer.Exit(1) from e


@cache_app.command(name="cleanup")
def cleanup_command(
    max_age_days: Annotated[
        int,
        typer.Option("--max-age", help="Maximum age in days for cache entries"),
    ] = 30,
    cache_root: Annotated[
        Path | None,
        typer.Option("--cache-root", help="Cache root directory"),
    ] = None,
) -> None:
    """Clean up old cache entries."""
    try:
        from glovebox.compilation.cache.base_dependencies_cache import (
            create_base_dependencies_cache,
        )

        base_cache = create_base_dependencies_cache(cache_root=cache_root)

        typer.echo(f"Cleaning up cache entries older than {max_age_days} days...")
        base_cache.cleanup_cache(max_age_days=max_age_days)
        from glovebox.cli.helpers.theme import Icons

        # Note: This function doesn't have ctx parameter, using default icon mode
        icon_mode = "emoji"
        typer.echo(
            Icons.format_with_icon("SUCCESS", "Cache cleanup completed.", icon_mode)
        )

    except Exception as e:
        logger.error("Failed to cleanup cache: %s", e)
        typer.echo(Icons.format_with_icon("ERROR", f"Error: {e}", icon_mode), err=True)
        raise typer.Exit(1) from e


@cache_app.command(name="clear-diskcache")
def clear_diskcache_command(
    module: Annotated[
        str | None,
        typer.Option(
            "--module",
            help="Specific module cache to clear (e.g., 'layout', 'compilation', 'moergo')",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force deletion without confirmation"),
    ] = False,
) -> None:
    """Clear DiskCache directories.

    This clears the new DiskCache-based cache system used for layout compilation,
    MoErgo API responses, and other cached data.
    """
    try:
        from glovebox.config.user_config import create_user_config

        user_config = create_user_config()
        cache_root = user_config._config.cache_path

        if not cache_root.exists():
            console.print("[yellow]No cache directory found[/yellow]")
            console.print(f"[dim]Cache directory would be: {cache_root}[/dim]")
            return

        if module:
            # Clear specific module cache
            module_cache_dir = cache_root / module

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
        else:
            # Clear all DiskCache directories
            cache_subdirs = [d for d in cache_root.iterdir() if d.is_dir()]

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
                for cache_dir in cache_subdirs:
                    shutil.rmtree(cache_dir)

                icon_mode = "emoji"
                console.print(
                    f"[green]{Icons.get_icon('SUCCESS', icon_mode)} Cleared all cache directories ({_format_size(total_size)})[/green]"
                )
            except Exception as e:
                console.print(f"[red]Failed to clear cache: {e}[/red]")
                raise typer.Exit(1) from e

    except Exception as e:
        logger.error("Failed to clear diskcache: %s", e)
        icon_mode = "emoji"
        typer.echo(Icons.format_with_icon("ERROR", f"Error: {e}", icon_mode), err=True)
        raise typer.Exit(1) from e


@cache_app.command(name="info-diskcache")
def info_diskcache_command() -> None:
    """Show DiskCache information and statistics."""
    try:
        from glovebox.config.user_config import create_user_config

        user_config = create_user_config()
        cache_root = user_config._config.cache_path

        if not cache_root.exists():
            console.print("[yellow]No cache directory found[/yellow]")
            console.print(f"[dim]Cache directory would be: {cache_root}[/dim]")
            return

        cache_subdirs = [d for d in cache_root.iterdir() if d.is_dir()]
        total_size = sum(_get_directory_size(d) for d in cache_subdirs)

        console.print(f"[bold]Cache Directory:[/bold] {cache_root}")
        console.print(
            f"[bold]Cache Strategy:[/bold] {user_config._config.cache_strategy}"
        )
        console.print(f"[bold]Cached Modules:[/bold] {len(cache_subdirs)}")
        console.print(f"[bold]Total Size:[/bold] {_format_size(total_size)}")

        if cache_subdirs:
            console.print("\n[bold]Module Caches:[/bold]")
            for cache_dir in sorted(cache_subdirs):
                module_name = cache_dir.name
                size = _get_directory_size(cache_dir)
                console.print(f"  • {module_name}: {_format_size(size)}")

        console.print("\n[dim]To clear cache: glovebox cache clear-diskcache[/dim]")
        console.print(
            "[dim]To clear specific module: glovebox cache clear-diskcache --module <name>[/dim]"
        )

    except Exception as e:
        logger.error("Failed to get diskcache info: %s", e)
        icon_mode = "emoji"
        typer.echo(Icons.format_with_icon("ERROR", f"Error: {e}", icon_mode), err=True)
        raise typer.Exit(1) from e
