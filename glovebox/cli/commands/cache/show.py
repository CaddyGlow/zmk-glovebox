"""Cache show CLI command."""

import logging
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.table import Table

from glovebox.cli.core.command_base import IOCommand
from glovebox.cli.decorators.error_handling import handle_errors
from glovebox.cli.helpers.parameters import OutputFormatOption
from glovebox.cli.helpers.theme import Colors, Icons, get_themed_console
from glovebox.config.user_config import create_user_config

from .utils import (
    format_size_display,
    get_cache_manager,
    get_cache_manager_and_service,
    get_directory_size_bytes,
)


logger = logging.getLogger(__name__)
themed_console = get_themed_console("text")
console = themed_console.console


class CacheShowCommand(IOCommand):
    """Command to show detailed cache information and statistics."""

    def execute(
        self,
        module: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        verbose: bool = False,
        keys: bool = False,
        stats: bool = False,
        output_format: str = "text",
    ) -> None:
        """Execute the cache show command."""
        try:
            cache_manager = get_cache_manager()

            # For JSON output, collect all data first
            if output_format == "json":
                cache_data = self._collect_cache_data(
                    cache_manager, module, limit, offset, verbose, keys, stats
                )
                self.write_output(cache_data, None, "json")
                return

            # Text output mode
            self._display_text_output(
                cache_manager, module, limit, offset, verbose, keys, stats
            )

        except Exception as e:
            self.handle_service_error(e, "show cache information")

    def _collect_cache_data(
        self,
        cache_manager: Any,
        module: str | None,
        limit: int | None,
        offset: int | None,
        verbose: bool,
        keys: bool,
        stats: bool,
    ) -> dict[str, Any]:
        """Collect all cache data for JSON output."""
        cache_data: dict[str, Any] = {}

        # Collect cache statistics
        cache_stats = cache_manager.get_stats()
        cache_data["cache_stats"] = {
            "total_entries": cache_stats.total_entries,
            "total_size_bytes": cache_stats.total_size_bytes,
            "hit_count": cache_stats.hit_count,
            "miss_count": cache_stats.miss_count,
            "hit_rate": cache_stats.hit_rate,
            "miss_rate": cache_stats.miss_rate,
            "eviction_count": cache_stats.eviction_count,
            "error_count": cache_stats.error_count,
        }

        # Collect workspace cache information
        try:
            cache_manager, workspace_cache_service, user_config = (
                get_cache_manager_and_service()
            )
            cached_workspaces = workspace_cache_service.list_cached_workspaces()

            workspace_data: dict[str, Any] = {
                "cache_directory": str(workspace_cache_service.get_cache_directory()),
                "cached_workspaces_count": len(cached_workspaces),
                "total_size_bytes": sum(
                    (
                        workspace.size_bytes
                        or get_directory_size_bytes(workspace.workspace_path)
                    )
                    for workspace in cached_workspaces
                ),
                "workspaces": [],
            }

            for workspace in cached_workspaces:
                workspace_info = {
                    "repository": workspace.repository,
                    "branch": workspace.branch,
                    "cache_level": workspace.cache_level.value
                    if hasattr(workspace.cache_level, "value")
                    else str(workspace.cache_level),
                    "size_bytes": workspace.size_bytes
                    or get_directory_size_bytes(workspace.workspace_path),
                    "age_hours": workspace.age_hours,
                    "auto_detected": workspace.auto_detected,
                    "cached_components": workspace.cached_components,
                    "workspace_path": str(workspace.workspace_path),
                }
                workspace_data["workspaces"].append(workspace_info)

            cache_data["workspace_cache"] = workspace_data
        except Exception as e:
            cache_data["workspace_cache"] = {"error": str(e)}

        # Collect DiskCache information
        try:
            user_config = create_user_config()
            diskcache_root = user_config._config.cache_path

            if diskcache_root.exists():
                cache_subdirs = [d for d in diskcache_root.iterdir() if d.is_dir()]
                diskcache_data: dict[str, Any] = {
                    "location": str(diskcache_root),
                    "cache_strategy": user_config._config.cache_strategy,
                    "cached_modules_count": len(cache_subdirs),
                    "total_size_bytes": sum(
                        get_directory_size_bytes(d) for d in cache_subdirs
                    ),
                    "modules": [],
                }

                for cache_dir_item in cache_subdirs:
                    module_name = cache_dir_item.name
                    size = get_directory_size_bytes(cache_dir_item)
                    file_count = len(list(cache_dir_item.rglob("*")))

                    module_info = {
                        "name": module_name,
                        "size_bytes": size,
                        "file_count": file_count,
                        "path": str(cache_dir_item),
                    }

                    # Try to get cache stats
                    try:
                        from glovebox.core.cache import create_default_cache

                        module_cache = create_default_cache(tag=module_name)
                        module_stats = module_cache.get_stats()
                        module_info.update(
                            {
                                "cache_entries": module_stats.total_entries,
                                "hit_rate": module_stats.hit_rate,
                            }
                        )
                    except Exception:
                        module_info.update(
                            {
                                "cache_entries": None,
                                "hit_rate": None,
                            }
                        )

                    diskcache_data["modules"].append(module_info)

                cache_data["diskcache"] = diskcache_data
            else:
                cache_data["diskcache"] = {"error": "No cache directory found"}
        except Exception as e:
            cache_data["diskcache"] = {"error": str(e)}

        return cache_data

    def _display_text_output(
        self,
        cache_manager: Any,
        module: str | None,
        limit: int | None,
        offset: int | None,
        verbose: bool,
        keys: bool,
        stats: bool,
    ) -> None:
        """Display cache information in text format."""
        # Implementation would be the existing text display logic
        # For brevity, keeping the existing console.print statements
        console.print("[bold cyan]Glovebox Cache System Overview[/bold cyan]")
        console.print("=" * 60)

        # Show performance statistics if requested or in verbose mode
        if stats or verbose:
            self._display_cache_stats(cache_manager)

        # Show workspace cache information
        self._display_workspace_cache(limit, offset, verbose)

        # Show DiskCache information
        self._display_diskcache_info(module, limit, offset, verbose, keys)

        # Show cache coordination information if verbose
        if verbose:
            self._display_coordination_info()

        # Show usage instructions
        self._display_usage_instructions()

    def _display_cache_stats(self, cache_manager: Any) -> None:
        """Display cache performance statistics."""

        stats_icon = Icons.get_icon("INFO", "text")
        console.print(
            f"\n[bold {Colors.INFO}]{stats_icon} Cache Performance Statistics[/bold {Colors.INFO}]"
        )
        cache_stats = cache_manager.get_stats()

        table = Table(show_header=True, header_style=f"bold {Colors.INFO}")
        table.add_column("Metric", style=Colors.PRIMARY)
        table.add_column("Value", style=Colors.SUCCESS)
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
        table.add_row("Hit Rate", f"{cache_stats.hit_rate:.1f}%", "Cache effectiveness")
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

    def _display_workspace_cache(
        self, limit: int | None, offset: int | None, verbose: bool
    ) -> None:
        """Display workspace cache information."""

        workspace_icon = Icons.get_icon("FOLDER", "text")
        console.print(
            f"\n[bold {Colors.INFO}]{workspace_icon} Workspace Cache (ZMK Compilation)[/bold {Colors.INFO}]"
        )
        cache_manager, workspace_cache_service, user_config = (
            get_cache_manager_and_service()
        )

        cache_dir = workspace_cache_service.get_cache_directory()
        cached_workspaces = workspace_cache_service.list_cached_workspaces()

        if cached_workspaces:
            total_workspace_size = sum(
                (
                    workspace.size_bytes
                    or get_directory_size_bytes(workspace.workspace_path)
                )
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

            console.print("\n[bold]Workspace Details:[/bold]")
            start_idx = offset or 0
            end_idx = start_idx + (limit or len(cached_workspaces))

            # Display workspace details based on verbose mode
            if verbose:
                self._display_workspace_table(cached_workspaces[start_idx:end_idx])
            else:
                self._display_workspace_list(cached_workspaces[start_idx:end_idx])
        else:
            console.print(
                f"[{Colors.WARNING}]No cached workspaces found[/{Colors.WARNING}]"
            )
            console.print(f"[dim]Cache directory: {cache_dir}[/dim]")

    def _display_workspace_table(self, workspaces: Any) -> None:
        """Display workspaces in table format."""

        table = Table(show_header=True, header_style=f"bold {Colors.SUCCESS}")
        table.add_column("Repository", style=Colors.PRIMARY)
        table.add_column("Branch", style=Colors.WARNING)
        table.add_column("Level", style=Colors.INFO)
        table.add_column("Size", style=Colors.SUCCESS)
        table.add_column("Age", style=Colors.INFO)
        table.add_column("Components", style=Colors.SUCCESS)
        table.add_column("Path", style="dim")
        table.add_column("Status", style=Colors.SUCCESS)

        for workspace in sorted(workspaces, key=lambda x: x.repository):
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

    def _display_workspace_list(self, workspaces: Any) -> None:
        """Display workspaces in simple list format."""
        for workspace in sorted(workspaces, key=lambda x: x.repository):
            size_bytes = workspace.size_bytes or get_directory_size_bytes(
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
                f"  • {workspace.repository}@{workspace.branch}: {format_size_display(size_bytes)} "
                f"(level: {cache_level_str}, age: {age_str}){auto_detected_marker}{components_str}"
            )

    def _display_diskcache_info(
        self,
        module: str | None,
        limit: int | None,
        offset: int | None,
        verbose: bool,
        keys: bool,
    ) -> None:
        """Display DiskCache system information."""

        disk_icon = Icons.get_icon("FILE", "text")
        console.print(
            f"\n[bold {Colors.INFO}]{disk_icon} DiskCache System (Domain Modules)[/bold {Colors.INFO}]"
        )

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
                        self._display_module_details(
                            module, diskcache_root, keys, verbose
                        )
                    else:
                        self._display_all_modules(cache_subdirs, limit, offset, verbose)
            else:
                console.print(
                    f"[{Colors.WARNING}]No DiskCache directory found[/{Colors.WARNING}]"
                )
                console.print(f"[dim]Would be located at: {diskcache_root}[/dim]")
        except Exception as e:
            console.print(
                f"[{Colors.ERROR}]Error accessing DiskCache info: {e}[/{Colors.ERROR}]"
            )

    def _display_module_details(
        self, module: str, diskcache_root: Path, keys: bool, verbose: bool
    ) -> None:
        """Display detailed info for specific module."""

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

                console.print(f"  • Cache Entries: {module_stats.total_entries}")
                console.print(f"  • Hit Rate: {module_stats.hit_rate:.1f}%")

                # Show individual cache keys if requested
                if keys and verbose:
                    console.print(f"\n[bold]Cache Keys in '{module}':[/bold]")
                    try:
                        cache_keys = module_cache.keys()
                        if cache_keys:
                            for cache_key in sorted(cache_keys):
                                # Get metadata for each key
                                metadata = module_cache.get_metadata(cache_key)
                                if metadata:
                                    size_str = format_size_display(metadata.size_bytes)
                                    console.print(f"  • {cache_key} ({size_str})")
                                else:
                                    console.print(
                                        f"  • {cache_key} (metadata unavailable)"
                                    )
                        else:
                            console.print("[dim]  No cache keys found[/dim]")
                    except Exception as e:
                        console.print(f"[dim]  Error listing keys: {e}[/dim]")

            except Exception as e:
                console.print(
                    f"  • [{Colors.WARNING}]Could not access cache stats: {e}[/{Colors.WARNING}]"
                )
        else:
            console.print(
                f"[{Colors.WARNING}]Module '{module}' not found in cache[/{Colors.WARNING}]"
            )

    def _display_all_modules(
        self,
        cache_subdirs: list[Path],
        limit: int | None,
        offset: int | None,
        verbose: bool,
    ) -> None:
        """Display all module caches."""

        console.print("\n[bold]Module Caches:[/bold]")
        start_idx = offset or 0
        end_idx = start_idx + (limit or len(cache_subdirs))

        if verbose:
            # Detailed table view
            table = Table(show_header=True, header_style=f"bold {Colors.INFO}")
            table.add_column("Module", style=Colors.PRIMARY)
            table.add_column("Size", style=Colors.SUCCESS)
            table.add_column("Files", style=Colors.INFO)
            table.add_column("Entries", style=Colors.SUCCESS)
            table.add_column("Hit Rate", style=Colors.WARNING)
            table.add_column("Path", style="dim")

            for cache_dir_item in sorted(cache_subdirs)[start_idx:end_idx]:
                module_name = cache_dir_item.name
                size = get_directory_size_bytes(cache_dir_item)
                file_count = len(list(cache_dir_item.rglob("*")))

                # Try to get cache stats for this module
                try:
                    from glovebox.core.cache import create_default_cache

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
                console.print(f"  • {module_name}: {format_size_display(size)}")

    def _display_coordination_info(self) -> None:
        """Display cache coordination information."""

        coordination_icon = Icons.get_icon("INFO", "text")
        console.print(
            f"\n[bold {Colors.INFO}]{coordination_icon} Cache Coordination System[/bold {Colors.INFO}]"
        )
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
                f"[{Colors.WARNING}]Could not access coordination info: {e}[/{Colors.WARNING}]"
            )

    def _display_usage_instructions(self) -> None:
        """Display cache management command instructions."""

        tools_icon = Icons.get_icon("INFO", "text")
        console.print(
            f"\n[bold {Colors.INFO}]{tools_icon} Cache Management Commands[/bold {Colors.INFO}]"
        )
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


@handle_errors
def cache_show(
    module: Annotated[
        str | None,
        typer.Option(
            "-m", "--module", help="Show detailed information for specific module"
        ),
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
    output_format: OutputFormatOption = "text",
) -> None:
    """Show detailed cache information and statistics."""
    command = CacheShowCommand()
    command.execute(
        module=module,
        limit=limit,
        offset=offset,
        verbose=verbose,
        keys=keys,
        stats=stats,
        output_format=output_format,
    )
