"""Cache show CLI command."""

import logging
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from glovebox.config.user_config import create_user_config

from .utils import (
    format_size_display,
    get_cache_manager,
    get_cache_manager_and_service,
    get_directory_size_bytes,
)


logger = logging.getLogger(__name__)
console = Console()


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
        cache_manager = get_cache_manager()

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
                format_size_display(cache_stats.total_size_bytes),
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
            get_cache_manager_and_service()
        )

        cache_dir = workspace_cache_service.get_cache_directory()
        cached_workspaces = workspace_cache_service.list_cached_workspaces()

        if cached_workspaces:
            total_workspace_size = sum(
                (workspace.size_bytes or get_directory_size_bytes(workspace.workspace_path))
                for workspace in cached_workspaces
            )

            console.print(f"[bold]Location:[/bold] {cache_dir}")
            console.print(f"[bold]Cached Workspaces:[/bold] {len(cached_workspaces)}")
            console.print(
                f"[bold]Total Size:[/bold] {format_size_display(total_workspace_size)}"
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
                        size_bytes = workspace.size_bytes or get_directory_size_bytes(
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
                            format_size_display(size_bytes),
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
                        size_bytes = workspace.size_bytes or get_directory_size_bytes(
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
                            f"  • {workspace.repository}@{workspace.branch}: {format_size_display(size_bytes)} "
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
                    get_directory_size_bytes(d) for d in cache_subdirs
                )

                console.print(f"[bold]Location:[/bold] {diskcache_root}")
                console.print(
                    f"[bold]Cache Strategy:[/bold] {user_config._config.cache_strategy}"
                )
                console.print(f"[bold]Cached Modules:[/bold] {len(cache_subdirs)}")
                console.print(
                    f"[bold]Total Size:[/bold] {format_size_display(total_diskcache_size)}"
                )

                if cache_subdirs:
                    if module:
                        # Show detailed info for specific module
                        module_dir = diskcache_root / module
                        if module_dir.exists():
                            module_size = get_directory_size_bytes(module_dir)
                            file_count = len(list(module_dir.rglob("*")))

                            console.print(f"\n[bold]Module '{module}' Details:[/bold]")
                            console.print(f"  • Location: {module_dir}")
                            console.print(f"  • Size: {format_size_display(module_size)}")
                            console.print(f"  • Files: {file_count}")

                            # Try to get cache manager for this module
                            try:
                                from glovebox.core.cache import create_default_cache

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
                                    try:
                                        cache_keys = module_cache.keys()
                                        if cache_keys:
                                            for cache_key in sorted(cache_keys):
                                                # Get metadata for each key
                                                metadata = module_cache.get_metadata(
                                                    cache_key
                                                )
                                                if metadata:
                                                    size_str = format_size_display(
                                                        metadata.size_bytes
                                                    )
                                                    console.print(
                                                        f"  • {cache_key} ({size_str})"
                                                    )
                                                else:
                                                    console.print(
                                                        f"  • {cache_key} (metadata unavailable)"
                                                    )
                                        else:
                                            console.print(
                                                "[dim]  No cache keys found[/dim]"
                                            )
                                    except Exception as e:
                                        console.print(
                                            f"[dim]  Error listing keys: {e}[/dim]"
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

                            for cache_dir_item in sorted(cache_subdirs)[start_idx:end_idx]:
                                module_name = cache_dir_item.name
                                size = get_directory_size_bytes(cache_dir_item)
                                file_count = len(list(cache_dir_item.rglob("*")))

                                # Try to get cache stats for this module
                                try:
                                    from glovebox.core.cache import (
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
                                    format_size_display(size),
                                    str(file_count),
                                    entries,
                                    hit_rate,
                                    str(cache_dir_item),
                                )

                            console.print(table)
                        else:
                            # Simple list view
                            for cache_dir_item in sorted(cache_subdirs)[start_idx:end_idx]:
                                module_name = cache_dir_item.name
                                size = get_directory_size_bytes(cache_dir_item)
                                console.print(
                                    f"  • {module_name}: {format_size_display(size)}"
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
                from glovebox.core.cache import (
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
        console.print("  • glovebox cache workspace add <path|zip|url>")
        console.print("  • glovebox cache workspace delete [repository]")
        console.print("  • glovebox cache workspace cleanup [--max-age <days>]")
        console.print("[dim]Module cache:[/dim]")
        console.print("  • glovebox cache clear -m <module>")
        console.print("  • glovebox cache clear --max-age <days>")
        console.print("  • glovebox cache show -m <module> --verbose")
        console.print('  • glovebox cache delete -m <module> --keys "key1,key2"')
        console.print('  • glovebox cache delete -m <module> --pattern "build"')
        console.print("[dim]Advanced:[/dim]")
        console.print("  • glovebox cache show --stats --verbose --keys")
        console.print("  • glovebox cache keys -m <module> --metadata")
        console.print("  • glovebox cache keys -m <module> --values")
        console.print("  • glovebox cache keys --pattern <substring> --json")
        console.print("  • glovebox cache delete -m <module> --json-file cache.json")
        console.print("  • glovebox cache debug")

    except Exception as e:
        logger.error("Failed to show cache info: %s", e)
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e
