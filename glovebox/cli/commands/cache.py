"""Cache management CLI commands."""

import contextlib
import logging
import shutil
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from glovebox.cli.helpers.theme import Icons
from glovebox.compilation.cache import create_compilation_cache_service
from glovebox.compilation.cache.workspace_cache_service import (
    ZmkWorkspaceCacheService,
)
from glovebox.config.user_config import UserConfig, create_user_config
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
    """Get cache manager and workspace cache service using shared coordination.

    Returns:
        Tuple of (cache_manager, workspace_cache_service, user_config)
    """
    try:
        user_config = create_user_config()
        # Use domain-specific factory with shared cache coordination
        cache_manager, workspace_cache_service = create_compilation_cache_service(
            user_config
        )
        return cache_manager, workspace_cache_service, user_config
    except Exception:
        # Fallback to default cache if user config fails
        from glovebox.core.cache_v2 import create_default_cache

        cache_manager = create_default_cache(tag="compilation")
        # Create a minimal user config for fallback
        user_config = create_user_config()
        from glovebox.compilation.cache.workspace_cache_service import (
            create_zmk_workspace_cache_service,
        )

        workspace_cache_service = create_zmk_workspace_cache_service(
            user_config, cache_manager
        )
        return cache_manager, workspace_cache_service, user_config


def _get_cache_manager() -> CacheManager:
    """Get cache manager using user config (backward compatibility)."""
    cache_manager, _, _ = _get_cache_manager_and_service()
    return cache_manager


def _show_cache_entries_by_level(
    cache_manager: CacheManager,
    workspace_cache_service: ZmkWorkspaceCacheService,
    user_config: UserConfig,
    json_output: bool = False,
) -> None:
    """Show all cache entries grouped by cache level with TTL information."""
    import json
    from datetime import datetime

    from glovebox.core.workspace_cache_utils import generate_workspace_cache_key

    if not json_output:
        console.print("[bold]ZMK Workspace Cache Entries by Level[/bold]")
        console.print("=" * 60)

    # Get TTL configuration
    ttl_config = workspace_cache_service.get_ttls_for_cache_levels()
    cache_dir = workspace_cache_service.get_cache_directory()

    # Define cache levels in hierarchy order
    cache_levels = ["base", "branch", "full", "build"]

    # Collect all cache entries by scanning the cache
    all_entries: dict[str, list[dict[str, Any]]] = {level: [] for level in cache_levels}

    try:
        # Get all known repositories and branches from filesystem scan
        repositories_branches = set()

        if cache_dir.exists():
            for cache_item in cache_dir.iterdir():
                if cache_item.is_file():
                    continue

                # Try to get metadata from cache
                cache_key = cache_item.name
                cached_data = cache_manager.get(cache_key)

                if cached_data and isinstance(cached_data, dict):
                    repo = cached_data.get("repository", "unknown")
                    branch = cached_data.get("branch", "main")
                    repositories_branches.add((repo, branch))
                else:
                    # Try to auto-detect from directory structure
                    actual_path = cache_item
                    if cache_item.is_symlink():
                        try:
                            actual_path = cache_item.resolve()
                        except (OSError, RuntimeError):
                            continue

                    if actual_path.is_dir():
                        from glovebox.core.workspace_cache_utils import detect_git_info

                        git_info = detect_git_info(actual_path)
                        repo = git_info.get("repository", "unknown")
                        branch = git_info.get("branch", "main")
                        repositories_branches.add((repo, branch))

        # Now check each level for each repository/branch combination
        for repo, branch in sorted(repositories_branches):
            for level in cache_levels:
                cache_key = generate_workspace_cache_key(repo, branch, level)
                cached_data = cache_manager.get(cache_key)

                if cached_data:
                    # Calculate remaining TTL
                    metadata = cache_manager.get_metadata(cache_key)
                    ttl_seconds = ttl_config.get(level, 3600)

                    if metadata:
                        # Calculate remaining TTL from creation time
                        import time

                        current_time = time.time()
                        age_seconds = current_time - metadata.created_at
                        remaining_ttl = max(0, ttl_seconds - age_seconds)
                    else:
                        # Fallback if metadata not available
                        remaining_ttl = ttl_seconds

                    # Format remaining TTL
                    if remaining_ttl > 0:
                        if remaining_ttl >= 86400:  # >= 1 day
                            ttl_str = f"{remaining_ttl / 86400:.1f}d"
                        elif remaining_ttl >= 3600:  # >= 1 hour
                            ttl_str = f"{remaining_ttl / 3600:.1f}h"
                        elif remaining_ttl >= 60:  # >= 1 minute
                            ttl_str = f"{remaining_ttl / 60:.1f}m"
                        else:
                            ttl_str = f"{remaining_ttl:.0f}s"
                    else:
                        ttl_str = "EXPIRED"

                    # Get workspace path from cache directory
                    workspace_path = cache_dir / cache_key
                    if workspace_path.is_symlink():
                        try:
                            actual_path = workspace_path.resolve()
                            path_display = f"{workspace_path} → {actual_path}"
                        except (OSError, RuntimeError):
                            path_display = f"{workspace_path} → [BROKEN]"
                    else:
                        path_display = str(workspace_path)

                    # Calculate size
                    try:
                        if workspace_path.exists():
                            size_bytes = _get_directory_size(workspace_path)
                            size_display = _format_size(size_bytes)
                        else:
                            size_display = "N/A"
                    except Exception:
                        size_display = "N/A"

                    entry = {
                        "repository": repo,
                        "branch": branch,
                        "cache_key": cache_key,
                        "ttl_remaining": ttl_str,
                        "size": size_display,
                        "path": path_display,
                    }

                    all_entries[level].append(entry)

        # Output results
        if json_output:
            # Create structured JSON output
            output_data: dict[str, Any] = {
                "cache_directory": str(cache_dir),
                "ttl_configuration": {
                    level: {
                        "seconds": ttl_config.get(level, 3600),
                        "human_readable": f"{ttl_config.get(level, 3600) / 86400:.1f} days"
                        if ttl_config.get(level, 3600) >= 86400
                        else f"{ttl_config.get(level, 3600) / 3600:.1f} hours",
                    }
                    for level in cache_levels
                },
                "cache_levels": {},
                "summary": {
                    "total_entries": sum(
                        len(entries) for entries in all_entries.values()
                    ),
                    "levels_with_entries": [
                        level for level, entries in all_entries.items() if entries
                    ],
                    "timestamp": datetime.now().isoformat(),
                },
            }

            # Add entries for each level
            for level in cache_levels:
                level_entries = all_entries[level]
                ttl_total_seconds = ttl_config.get(level, 3600)

                output_data["cache_levels"][level] = {
                    "ttl_seconds": ttl_total_seconds,
                    "ttl_human_readable": f"{ttl_total_seconds / 86400:.1f} days"
                    if ttl_total_seconds >= 86400
                    else f"{ttl_total_seconds / 3600:.1f} hours",
                    "entry_count": len(level_entries),
                    "entries": sorted(
                        level_entries, key=lambda x: (x["repository"], x["branch"])
                    ),
                }

            # Output JSON to stdout
            print(json.dumps(output_data, indent=2, ensure_ascii=False))

        else:
            # Display entries grouped by level (original format)
            for level in cache_levels:
                level_entries = all_entries[level]
                ttl_total_hours = ttl_config.get(level, 3600) / 3600

                if ttl_total_hours >= 24:
                    ttl_display = f"{ttl_total_hours / 24:.1f} days"
                else:
                    ttl_display = f"{ttl_total_hours:.1f} hours"

                console.print(
                    f"\n[bold cyan]📦 Cache Level: {level.upper()}[/bold cyan]"
                )
                console.print(
                    f"[dim]TTL: {ttl_display} | Entries: {len(level_entries)}[/dim]"
                )

                if level_entries:
                    table = Table(show_header=True, header_style="bold green")
                    table.add_column("Repository", style="cyan")
                    table.add_column("Branch", style="yellow")
                    table.add_column("TTL Remaining", style="magenta")
                    table.add_column("Size", style="white")
                    table.add_column("Cache Key", style="dim")
                    table.add_column("Workspace Path", style="blue")

                    for entry in sorted(
                        level_entries, key=lambda x: (x["repository"], x["branch"])
                    ):
                        table.add_row(
                            entry["repository"],
                            entry["branch"],
                            entry["ttl_remaining"],
                            entry["size"],
                            entry["cache_key"],
                            entry["path"],
                        )

                    console.print(table)
                else:
                    console.print("[dim]  No entries at this level[/dim]")

            console.print(f"\n[bold]Cache Directory:[/bold] {cache_dir}")
            console.print(
                "[dim]Use 'glovebox cache workspace show' for workspace-focused view[/dim]"
            )

    except Exception as e:
        if json_output:
            error_output = {
                "error": str(e),
                "cache_directory": str(cache_dir) if "cache_dir" in locals() else None,
                "timestamp": datetime.now().isoformat(),
            }
            print(json.dumps(error_output, indent=2))
        else:
            logger.error("Failed to list cache entries by level: %s", e)
            console.print(f"[red]Error listing cache entries: {e}[/red]")


@cache_app.command(name="debug")
def cache_debug() -> None:
    """Debug cache state - show filesystem vs cache database entries."""
    try:
        cache_manager, workspace_cache_service, user_config = (
            _get_cache_manager_and_service()
        )

        cache_dir = workspace_cache_service.get_cache_directory()
        console.print("[bold]Cache Debug Report[/bold]")
        console.print(f"Cache directory: {cache_dir}")
        console.print("=" * 60)

        if not cache_dir.exists():
            console.print("[red]Cache directory does not exist[/red]")
            return

        console.print("\n[bold cyan]1. Filesystem Items[/bold cyan]")
        filesystem_items = list(cache_dir.iterdir())
        for item in sorted(filesystem_items):
            item_type = (
                "symlink"
                if item.is_symlink()
                else "directory"
                if item.is_dir()
                else "file"
            )
            if item.is_symlink():
                try:
                    target = item.resolve()
                    console.print(f"  {item.name} ({item_type}) -> {target}")
                except (OSError, RuntimeError):
                    console.print(f"  {item.name} ({item_type}) -> [red]BROKEN[/red]")
            else:
                console.print(f"  {item.name} ({item_type})")

        console.print(f"\nTotal filesystem items: {len(filesystem_items)}")

        console.print("\n[bold cyan]2. Cache Database Entries[/bold cyan]")
        cache_entries = []
        for item in filesystem_items:
            if item.is_file():
                continue
            cache_key = item.name
            cached_data = cache_manager.get(cache_key)
            if cached_data:
                console.print(f"  {cache_key}: [green]HAS METADATA[/green]")
                if isinstance(cached_data, dict):
                    repo = cached_data.get("repository", "unknown")
                    branch = cached_data.get("branch", "unknown")
                    console.print(f"    -> {repo}@{branch}")
                cache_entries.append(cache_key)
            else:
                console.print(f"  {cache_key}: [red]NO METADATA[/red]")

                # Try to auto-detect git info for missing metadata
                actual_path = item
                if item.is_symlink():
                    try:
                        actual_path = item.resolve()
                    except (OSError, RuntimeError):
                        continue

                if actual_path.is_dir():
                    git_info = detect_git_info(actual_path)
                    repo = git_info.get("repository", "unknown")
                    branch = git_info.get("branch", "main")
                    console.print(f"    -> Detected: {repo}@{branch}")

        console.print(f"\nCache entries with metadata: {len(cache_entries)}")

        # Test specific cache key mentioned in logs
        test_keys = ["91005f829d37fa2b", "465b177522248c96"]
        console.print("\n[bold cyan]3. Test Specific Keys[/bold cyan]")
        for test_key in test_keys:
            cached_data = cache_manager.get(test_key)
            if cached_data:
                console.print(f"  {test_key}: [green]FOUND[/green]")
                if isinstance(cached_data, dict):
                    repo = cached_data.get("repository", "unknown")
                    branch = cached_data.get("branch", "unknown")
                    workspace_path = cached_data.get("workspace_path", "unknown")
                    console.print(f"    -> {repo}@{branch}")
                    console.print(f"    -> Path: {workspace_path}")
            else:
                console.print(f"  {test_key}: [red]NOT FOUND[/red]")

                # Check if it exists on filesystem
                cache_item = cache_dir / test_key
                if cache_item.exists():
                    item_type = "symlink" if cache_item.is_symlink() else "directory"
                    if cache_item.is_symlink():
                        try:
                            target = cache_item.resolve()
                            console.print(f"    -> Filesystem: {item_type} -> {target}")
                        except (OSError, RuntimeError):
                            console.print(
                                f"    -> Filesystem: {item_type} -> [red]BROKEN[/red]"
                            )
                    else:
                        console.print(f"    -> Filesystem: {item_type}")
                else:
                    console.print("    -> Filesystem: [red]NOT FOUND[/red]")

        console.print(
            "\n[bold cyan]4. Cache Keys Generated for Known Repos[/bold cyan]"
        )
        test_repos = [
            ("zmkfirmware/zmk", "main", "base"),
            ("zmkfirmware/zmk", "main", "branch"),
            ("moergo-sc/zmk", "v25.05", "base"),
            ("moergo-sc/zmk", "v25.01", "base"),
        ]

        for repo, branch, level in test_repos:
            cache_key = generate_workspace_cache_key(repo, branch, level)
            cached_data = cache_manager.get(cache_key)
            status = "[green]FOUND[/green]" if cached_data else "[red]NOT FOUND[/red]"
            console.print(f"  {repo}@{branch} ({level}): {cache_key} -> {status}")

    except Exception as e:
        exc_info = logger.isEnabledFor(logging.DEBUG)
        logger.error("Failed to debug cache: %s", e, exc_info=exc_info)
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e


@workspace_app.command(name="show")
def workspace_show(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output all cache entries in JSON format"),
    ] = False,
    filter_repository: Annotated[
        str | None,
        typer.Option("--repo", help="Filter by repository name (partial match)"),
    ] = None,
    filter_branch: Annotated[
        str | None,
        typer.Option("--branch", help="Filter by branch name (partial match)"),
    ] = None,
    filter_level: Annotated[
        str | None,
        typer.Option(
            "--level", help="Filter by cache level (base, branch, full, build)"
        ),
    ] = None,
) -> None:
    """Show all cached ZMK workspace entries in a simple flat format."""
    try:
        cache_manager, workspace_cache_service, user_config = (
            _get_cache_manager_and_service()
        )

        # Get cache directory and TTL configuration
        cache_dir = workspace_cache_service.get_cache_directory()
        ttl_config = workspace_cache_service.get_ttls_for_cache_levels()

        # Define cache levels in hierarchy order
        cache_levels = ["base", "branch", "full", "build"]

        # Collect all cache entries by scanning the cache manager directly
        all_entries: list[dict[str, Any]] = []

        try:
            # Get all cache keys and iterate through them
            all_keys = cache_manager.keys()

            for cache_key in all_keys:
                # Get cached data for this key
                cached_data = cache_manager.get(cache_key)
                if not cached_data:
                    continue

                # Only process workspace-related cache entries
                # Skip entries that don't have workspace metadata
                if not isinstance(cached_data, dict):
                    continue
                
                # Skip non-workspace cache entries (e.g., build results, other compilation caches)
                if "workspace_path" not in cached_data and "repository" not in cached_data:
                    continue
                
                # Skip build-level caches as they represent compiled artifacts, not workspaces
                cache_level_value = cached_data.get("cache_level", "")
                if isinstance(cache_level_value, dict):
                    cache_level_value = cache_level_value.get("value", "")
                if cache_level_value == "build":
                    continue

                # Extract metadata if available
                repo = cached_data.get("repository", "unknown")
                branch = cached_data.get("branch", "unknown")
                level = cached_data.get("cache_level", "unknown")
                if isinstance(level, dict) and "value" in level:
                    level = level["value"]

                # Get cache metadata for timing information
                metadata = cache_manager.get_metadata(cache_key)
                age_seconds = 0.0
                ttl_remaining_seconds = 0.0

                if metadata:
                    import time

                    current_time = time.time()
                    age_seconds = current_time - metadata.created_at

                    # Determine TTL for this level
                    ttl_seconds = ttl_config.get(level, 3600)
                    ttl_remaining_seconds = max(0, ttl_seconds - age_seconds)

                # Format remaining TTL
                if ttl_remaining_seconds > 0:
                    if ttl_remaining_seconds >= 86400:  # >= 1 day
                        ttl_str = f"{ttl_remaining_seconds / 86400:.1f}d"
                    elif ttl_remaining_seconds >= 3600:  # >= 1 hour
                        ttl_str = f"{ttl_remaining_seconds / 3600:.1f}h"
                    elif ttl_remaining_seconds >= 60:  # >= 1 minute
                        ttl_str = f"{ttl_remaining_seconds / 60:.1f}m"
                    else:
                        ttl_str = f"{ttl_remaining_seconds:.0f}s"
                else:
                    ttl_str = "EXPIRED"

                # Get workspace path from cache directory
                workspace_path = cache_dir / cache_key
                path_display = str(workspace_path)
                if workspace_path.is_symlink():
                    try:
                        actual_path = workspace_path.resolve()
                        path_display = f"{workspace_path} → {actual_path}"
                    except (OSError, RuntimeError):
                        path_display = f"{workspace_path} → [BROKEN]"

                # Calculate size
                try:
                    if workspace_path.exists():
                        size_bytes = _get_directory_size(workspace_path)
                        size_display = _format_size(size_bytes)
                    else:
                        size_display = "N/A"
                except Exception:
                    size_display = "N/A"

                # Format age
                if age_seconds >= 86400:  # >= 1 day
                    age_str = f"{age_seconds / 86400:.1f}d"
                elif age_seconds >= 3600:  # >= 1 hour
                    age_str = f"{age_seconds / 3600:.1f}h"
                elif age_seconds >= 60:  # >= 1 minute
                    age_str = f"{age_seconds / 60:.1f}m"
                else:
                    age_str = f"{age_seconds:.0f}s"

                entry = {
                    "cache_key": cache_key,
                    "repository": repo,
                    "branch": branch,
                    "cache_level": level,
                    "age": age_str,
                    "ttl_remaining": ttl_str,
                    "size": size_display,
                    "workspace_path": path_display,
                }

                all_entries.append(entry)

            # Apply filters
            filtered_entries = all_entries

            if filter_repository:
                filtered_entries = [
                    entry
                    for entry in filtered_entries
                    if filter_repository.lower() in entry["repository"].lower()
                ]

            if filter_branch:
                filtered_entries = [
                    entry
                    for entry in filtered_entries
                    if filter_branch.lower() in entry["branch"].lower()
                ]

            if filter_level:
                filtered_entries = [
                    entry
                    for entry in filtered_entries
                    if entry["cache_level"].lower() == filter_level.lower()
                ]

            # Check if any entries found
            if not filtered_entries:
                if not all_entries:
                    console.print("[yellow]No cached workspaces found[/yellow]")
                else:
                    console.print(
                        "[yellow]No cache entries match the specified filters[/yellow]"
                    )
                console.print(f"[dim]Cache directory: {cache_dir}[/dim]")
                return

            # Output results
            if json_output:
                # Create structured JSON output
                import json
                from datetime import datetime

                output_data: dict[str, Any] = {
                    "cache_directory": str(cache_dir),
                    "ttl_configuration": {
                        level: {
                            "seconds": ttl_config.get(level, 3600),
                            "human_readable": f"{ttl_config.get(level, 3600) / 86400:.1f} days"
                            if ttl_config.get(level, 3600) >= 86400
                            else f"{ttl_config.get(level, 3600) / 3600:.1f} hours",
                        }
                        for level in cache_levels
                    },
                    "entries": sorted(
                        filtered_entries,
                        key=lambda x: (x["repository"], x["branch"], x["cache_level"]),
                    ),
                    "summary": {
                        "total_entries": len(filtered_entries),
                        "cache_levels_present": list(
                            {entry["cache_level"] for entry in filtered_entries}
                        ),
                        "repositories_present": list(
                            {entry["repository"] for entry in filtered_entries}
                        ),
                        "timestamp": datetime.now().isoformat(),
                    },
                }

                # Output JSON to stdout
                print(json.dumps(output_data, indent=2, ensure_ascii=False))

            else:
                # Display entries in a simple table format
                console.print("[bold]All Cached Workspace Entries[/bold]")
                console.print("=" * 80)

                table = Table(show_header=True, header_style="bold green")
                table.add_column("Cache Key", style="dim")
                table.add_column("Repository", style="cyan")
                table.add_column("Branch", style="yellow")
                table.add_column("Level", style="magenta")
                table.add_column("Age", style="blue")
                table.add_column("TTL Remaining", style="green")
                table.add_column("Size", style="white")
                table.add_column("Workspace Path", style="dim")

                # Sort entries by repository, branch, then cache level
                sorted_entries = sorted(
                    filtered_entries,
                    key=lambda x: (x["repository"], x["branch"], x["cache_level"]),
                )

                for entry in sorted_entries:
                    table.add_row(
                        entry["cache_key"],
                        entry["repository"],
                        entry["branch"],
                        entry["cache_level"],
                        entry["age"],
                        entry["ttl_remaining"],
                        entry["size"],
                        entry["workspace_path"],
                    )

                console.print(table)
                console.print(f"\n[bold]Total entries:[/bold] {len(filtered_entries)}")
                console.print(f"[bold]Cache directory:[/bold] {cache_dir}")

        except Exception as e:
            if json_output:
                import json

                error_output = {
                    "error": str(e),
                    "cache_directory": str(cache_dir),
                    "entries": [],
                }
                print(json.dumps(error_output, indent=2))
            else:
                console.print(f"[red]Error reading cache entries: {e}[/red]")
            raise

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
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show detailed cache entry information"),
    ] = False,
    keys: Annotated[
        bool,
        typer.Option("--keys", help="Show individual cache keys and metadata"),
    ] = False,
    stats: Annotated[
        bool,
        typer.Option("--stats", help="Show detailed performance statistics"),
    ] = False,
) -> None:
    """Show detailed cache information and statistics with enhanced details."""
    try:
        cache_manager = _get_cache_manager()

        console.print("[bold]Glovebox Cache System Overview[/bold]")
        console.print("=" * 60)

        # Show performance statistics if requested or in verbose mode
        if stats or verbose:
            console.print("\n[bold cyan]📊 Cache Performance Statistics[/bold cyan]")
            cache_stats = cache_manager.get_stats()

            table = Table(show_header=True, header_style="bold blue")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="white")
            table.add_column("Details", style="dim")

            table.add_row(
                "Total Entries",
                str(cache_stats.total_entries),
                "Number of cached items",
            )
            table.add_row(
                "Total Size",
                _format_size(cache_stats.total_size_bytes),
                "Disk space used",
            )
            table.add_row(
                "Hit Count", str(cache_stats.hit_count), "Successful cache retrievals"
            )
            table.add_row("Miss Count", str(cache_stats.miss_count), "Cache misses")
            table.add_row(
                "Hit Rate", f"{cache_stats.hit_rate:.1f}%", "Cache effectiveness"
            )
            table.add_row(
                "Miss Rate", f"{cache_stats.miss_rate:.1f}%", "Cache inefficiency"
            )
            table.add_row(
                "Evictions", str(cache_stats.eviction_count), "Entries removed by LRU"
            )
            table.add_row(
                "Errors", str(cache_stats.error_count), "Cache operation failures"
            )

            console.print(table)

        # Show workspace cache information using the service
        console.print("\n[bold cyan]🏗️  Workspace Cache (ZMK Compilation)[/bold cyan]")
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

            # Get TTL information
            ttl_config = workspace_cache_service.get_ttls_for_cache_levels()
            console.print("\n[bold]Cache Level TTLs:[/bold]")
            for level, ttl_seconds in ttl_config.items():
                ttl_hours = ttl_seconds / 3600
                if ttl_hours >= 24:
                    ttl_str = f"{ttl_hours / 24:.1f} days"
                else:
                    ttl_str = f"{ttl_hours:.1f} hours"
                console.print(f"  • {level}: {ttl_str}")

            if not module:
                console.print("\n[bold]Workspace Details:[/bold]")
                start_idx = offset or 0
                end_idx = start_idx + (limit or len(cached_workspaces))

                # Create detailed table for verbose mode
                if verbose:
                    table = Table(show_header=True, header_style="bold green")
                    table.add_column("Repository", style="cyan")
                    table.add_column("Branch", style="yellow")
                    table.add_column("Level", style="magenta")
                    table.add_column("Size", style="white")
                    table.add_column("Age", style="blue")
                    table.add_column("Components", style="green")
                    table.add_column("Path", style="dim")
                    table.add_column("Status", style="white")

                    for workspace in sorted(
                        cached_workspaces, key=lambda x: x.repository
                    )[start_idx:end_idx]:
                        size_bytes = workspace.size_bytes or _get_directory_size(
                            workspace.workspace_path
                        )

                        # Format age
                        age_str = f"{workspace.age_hours:.1f}h"
                        if workspace.age_hours > 24:
                            age_str = f"{workspace.age_hours / 24:.1f}d"

                        # Handle cache_level safely
                        cache_level_str = (
                            workspace.cache_level.value
                            if hasattr(workspace.cache_level, "value")
                            else str(workspace.cache_level)
                        )

                        # Status indicators
                        status_parts = []
                        if workspace.auto_detected:
                            status_parts.append("auto")
                        if workspace.workspace_path.is_symlink():
                            status_parts.append("symlink")
                        status = ", ".join(status_parts) if status_parts else "direct"

                        table.add_row(
                            workspace.repository,
                            workspace.branch,
                            cache_level_str,
                            _format_size(size_bytes),
                            age_str,
                            ", ".join(workspace.cached_components)
                            if workspace.cached_components
                            else "unknown",
                            str(workspace.workspace_path),
                            status,
                        )

                    console.print(table)
                else:
                    # Simple list format
                    for workspace in sorted(
                        cached_workspaces, key=lambda x: x.repository
                    )[start_idx:end_idx]:
                        size_bytes = workspace.size_bytes or _get_directory_size(
                            workspace.workspace_path
                        )

                        # Format age
                        age_str = f"{workspace.age_hours:.1f}h"
                        if workspace.age_hours > 24:
                            age_str = f"{workspace.age_hours / 24:.1f}d"

                        auto_detected_marker = (
                            " [auto]" if workspace.auto_detected else ""
                        )
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
        console.print("\n[bold cyan]💾 DiskCache System (Domain Modules)[/bold cyan]")
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
                            file_count = len(list(module_dir.rglob("*")))

                            console.print(f"\n[bold]Module '{module}' Details:[/bold]")
                            console.print(f"  • Location: {module_dir}")
                            console.print(f"  • Size: {_format_size(module_size)}")
                            console.print(f"  • Files: {file_count}")

                            # Try to get cache manager for this module
                            try:
                                from glovebox.core.cache_v2 import create_default_cache

                                module_cache = create_default_cache(tag=module)
                                module_stats = module_cache.get_stats()

                                console.print(
                                    f"  • Cache Entries: {module_stats.total_entries}"
                                )
                                console.print(
                                    f"  • Hit Rate: {module_stats.hit_rate:.1f}%"
                                )

                                # Show individual cache keys if requested
                                if keys and verbose:
                                    console.print(
                                        f"\n[bold]Cache Keys in '{module}':[/bold]"
                                    )
                                    # Note: DiskCache doesn't expose key iteration easily
                                    # This would require additional implementation
                                    console.print(
                                        "[dim]Key enumeration not yet implemented for DiskCache[/dim]"
                                    )

                            except Exception as e:
                                console.print(
                                    f"  • [yellow]Could not access cache stats: {e}[/yellow]"
                                )
                        else:
                            console.print(
                                f"[yellow]Module '{module}' not found in cache[/yellow]"
                            )
                    else:
                        console.print("\n[bold]Module Caches:[/bold]")
                        start_idx = offset or 0
                        end_idx = start_idx + (limit or len(cache_subdirs))

                        if verbose:
                            # Detailed table view
                            table = Table(show_header=True, header_style="bold blue")
                            table.add_column("Module", style="cyan")
                            table.add_column("Size", style="white")
                            table.add_column("Files", style="blue")
                            table.add_column("Entries", style="green")
                            table.add_column("Hit Rate", style="yellow")
                            table.add_column("Path", style="dim")

                            for cache_dir in sorted(cache_subdirs)[start_idx:end_idx]:
                                module_name = cache_dir.name
                                size = _get_directory_size(cache_dir)
                                file_count = len(list(cache_dir.rglob("*")))

                                # Try to get cache stats for this module
                                try:
                                    from glovebox.core.cache_v2 import (
                                        create_default_cache,
                                    )

                                    module_cache = create_default_cache(tag=module_name)
                                    module_stats = module_cache.get_stats()
                                    entries = str(module_stats.total_entries)
                                    hit_rate = f"{module_stats.hit_rate:.1f}%"
                                except Exception:
                                    entries = "N/A"
                                    hit_rate = "N/A"

                                table.add_row(
                                    module_name,
                                    _format_size(size),
                                    str(file_count),
                                    entries,
                                    hit_rate,
                                    str(cache_dir),
                                )

                            console.print(table)
                        else:
                            # Simple list view
                            for cache_dir in sorted(cache_subdirs)[start_idx:end_idx]:
                                module_name = cache_dir.name
                                size = _get_directory_size(cache_dir)
                                console.print(
                                    f"  • {module_name}: {_format_size(size)}"
                                )
            else:
                console.print("[yellow]No DiskCache directory found[/yellow]")
                console.print(f"[dim]Would be located at: {diskcache_root}[/dim]")
        except Exception as e:
            console.print(f"[red]Error accessing DiskCache info: {e}[/red]")

        # Show cache coordination information if verbose
        if verbose:
            console.print("\n[bold cyan]🔗 Cache Coordination System[/bold cyan]")
            try:
                from glovebox.core.cache_v2 import (
                    get_cache_instance_count,
                    get_cache_instance_keys,
                )

                instance_count = get_cache_instance_count()
                instance_keys = get_cache_instance_keys()

                console.print(f"[bold]Active Cache Instances:[/bold] {instance_count}")
                console.print("[bold]Instance Keys:[/bold]")
                for key in sorted(instance_keys):
                    console.print(f"  • {key}")

            except Exception as e:
                console.print(
                    f"[yellow]Could not access coordination info: {e}[/yellow]"
                )

        # Show usage instructions
        console.print("\n[bold cyan]🛠️  Cache Management Commands[/bold cyan]")
        console.print("[dim]Workspace cache:[/dim]")
        console.print("  • glovebox cache workspace show")
        console.print("  • glovebox cache workspace add <path>")
        console.print("  • glovebox cache workspace delete [repository]")
        console.print("  • glovebox cache workspace cleanup [--max-age <days>]")
        console.print("[dim]Module cache:[/dim]")
        console.print("  • glovebox cache clear -m <module>")
        console.print("  • glovebox cache clear --max-age <days>")
        console.print("  • glovebox cache show -m <module> --verbose")
        console.print("[dim]Advanced:[/dim]")
        console.print("  • glovebox cache show --stats --verbose --keys")
        console.print("  • glovebox cache debug")

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
