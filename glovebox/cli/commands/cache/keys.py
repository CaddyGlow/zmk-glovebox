"""Cache keys CLI command."""

import time
from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Any

from glovebox.core.structlog_logger import get_struct_logger


if TYPE_CHECKING:
    from glovebox.core.cache.cache_manager import CacheManager

import typer
from rich.console import Console
from rich.table import Table

from glovebox.cli.core.command_base import IOCommand
from glovebox.cli.decorators.error_handling import handle_errors
from glovebox.cli.helpers.parameters import OutputFormatOption
from glovebox.cli.helpers.theme import Colors
from glovebox.config.user_config import create_user_config

from .utils import format_size_display


logger = get_struct_logger(__name__)
console = Console()


class CacheKeysCommand(IOCommand):
    """Command to list cache keys with optional filtering, metadata, and cached values."""

    def execute(
        self,
        module: str | None = None,
        pattern: str | None = None,
        limit: int | None = None,
        output_format: str = "text",
        metadata: bool = False,
        values: bool = False,
    ) -> None:
        """Execute the cache keys command."""
        try:
            if module:
                self._show_module_keys(
                    module, pattern, limit, output_format, metadata, values
                )
            else:
                self._show_all_module_keys(pattern, limit, output_format)

        except Exception as e:
            self.handle_service_error(e, "list cache keys")

    def _show_module_keys(
        self,
        module: str,
        pattern: str | None,
        limit: int | None,
        output_format: str,
        metadata: bool,
        values: bool,
    ) -> None:
        """Show keys for specific module."""
        from glovebox.core.cache import create_default_cache

        try:
            module_cache = create_default_cache(tag=module)
            cache_keys = module_cache.keys()

            # Apply pattern filtering
            if pattern:
                cache_keys = [
                    key for key in cache_keys if pattern.lower() in key.lower()
                ]

            # Apply limit
            if limit:
                cache_keys = cache_keys[:limit]

            if output_format == "json":
                keys_data = self._collect_keys_data(
                    module, cache_keys, module_cache, metadata, values, pattern, limit
                )
                self.write_output(keys_data, None, "json")
            else:
                self._display_module_keys_text(
                    module, cache_keys, module_cache, metadata, values, pattern, limit
                )

        except Exception as e:
            console.print(
                f"[red]Error accessing cache for module '{module}': {e}[/red]"
            )
            raise typer.Exit(1) from e

    def _show_all_module_keys(
        self, pattern: str | None, limit: int | None, output_format: str
    ) -> None:
        """Show keys for all modules."""
        user_config = create_user_config()
        diskcache_root = user_config._config.cache_path

        if not diskcache_root.exists():
            console.print("[yellow]No cache directory found[/yellow]")
            return

        cache_subdirs = [d.name for d in diskcache_root.iterdir() if d.is_dir()]

        if not cache_subdirs:
            console.print("[yellow]No cache modules found[/yellow]")
            return

        if output_format == "json":
            all_modules_data = self._collect_all_modules_data(cache_subdirs, pattern)
            self.write_output(all_modules_data, None, "json")
        else:
            self._display_all_modules_text(cache_subdirs, pattern, limit)

    def _collect_keys_data(
        self,
        module: str,
        cache_keys: list[str],
        module_cache: "CacheManager",
        metadata: bool,
        values: bool,
        pattern: str | None,
        limit: int | None,
    ) -> dict[str, Any]:
        """Collect keys data for JSON output."""
        output_data: dict[str, Any] = {
            "module": module,
            "total_keys": len(cache_keys),
            "pattern_filter": pattern,
            "limit_applied": limit,
            "timestamp": datetime.now().isoformat(),
            "keys": [],
        }

        for key in sorted(cache_keys):
            key_data: dict[str, Any] = {"key": key}

            if metadata:
                key_metadata = module_cache.get_metadata(key)
                if key_metadata:
                    key_data.update(
                        {
                            "size_bytes": key_metadata.size_bytes,
                            "created_at": key_metadata.created_at,
                            "last_accessed": key_metadata.last_accessed,
                            "access_count": key_metadata.access_count,
                            "ttl_seconds": key_metadata.ttl_seconds,
                        }
                    )

            if values:
                try:
                    cached_value = module_cache.get(key)
                    # Handle different types of cached values safely
                    if cached_value is not None:
                        if isinstance(
                            cached_value,
                            dict | list | str | int | float | bool,
                        ):
                            key_data["value"] = cached_value
                        else:
                            # For complex objects, show string representation
                            key_data["value"] = str(cached_value)
                            key_data["value_type"] = type(cached_value).__name__
                    else:
                        key_data["value"] = None
                except Exception as e:
                    key_data["value_error"] = str(e)

            output_data["keys"].append(key_data)

        return output_data

    def _collect_all_modules_data(
        self, cache_subdirs: list[str], pattern: str | None
    ) -> dict[str, Any]:
        """Collect data for all modules for JSON output."""
        all_modules_data: dict[str, Any] = {
            "total_modules": len(cache_subdirs),
            "pattern_filter": pattern,
            "timestamp": datetime.now().isoformat(),
            "modules": {},
        }

        for module_name in sorted(cache_subdirs):
            try:
                from glovebox.core.cache import create_default_cache

                module_cache = create_default_cache(tag=module_name)
                cache_keys_all = module_cache.keys()

                # Apply pattern filtering
                if pattern:
                    cache_keys_all = [
                        key for key in cache_keys_all if pattern.lower() in key.lower()
                    ]

                all_modules_data["modules"][module_name] = {
                    "total_keys": len(cache_keys_all),
                    "keys": sorted(cache_keys_all),
                }
            except Exception:
                all_modules_data["modules"][module_name] = {
                    "total_keys": 0,
                    "keys": [],
                    "error": "Unable to access cache",
                }

        return all_modules_data

    def _display_module_keys_text(
        self,
        module: str,
        cache_keys: list[str],
        module_cache: "CacheManager",
        metadata: bool,
        values: bool,
        pattern: str | None,
        limit: int | None,
    ) -> None:
        """Display module keys in text format."""
        if cache_keys:
            console.print(f"[bold]Cache Keys in '{module}' Module[/bold]")
            if pattern:
                console.print(f"[dim]Filtered by pattern: '{pattern}'[/dim]")
            console.print("=" * 60)

            if metadata or values:
                self._display_keys_table(cache_keys, module_cache, metadata, values)
            else:
                self._display_keys_list(cache_keys, module_cache, values)

            console.print(f"\n[bold]Total keys:[/bold] {len(cache_keys)}")
            if limit and len(cache_keys) == limit:
                console.print(f"[dim]Limited to first {limit} keys[/dim]")
        else:
            if pattern:
                console.print(
                    f"[yellow]No cache keys found in '{module}' matching pattern '{pattern}'[/yellow]"
                )
            else:
                console.print(
                    f"[yellow]No cache keys found in '{module}' module[/yellow]"
                )

    def _display_keys_table(
        self,
        cache_keys: list[str],
        module_cache: "CacheManager",
        metadata: bool,
        values: bool,
    ) -> None:
        """Display cache keys in table format."""
        table = Table(show_header=True, header_style=Colors.HEADER)
        table.add_column("Cache Key", style=Colors.PRIMARY)

        if metadata:
            table.add_column("Size", style=Colors.FIELD_VALUE)
            table.add_column("Age", style=Colors.SECONDARY)
            table.add_column("Accesses", style=Colors.WARNING)
            table.add_column("TTL", style=Colors.ACCENT)

        if values:
            table.add_column("Cached Value", style=Colors.SUCCESS)

        for key in sorted(cache_keys):
            row_data = [key]

            if metadata:
                key_metadata = module_cache.get_metadata(key)
                if key_metadata:
                    # Calculate age
                    age_seconds = time.time() - key_metadata.created_at
                    if age_seconds >= 86400:
                        age_str = f"{age_seconds / 86400:.1f}d"
                    elif age_seconds >= 3600:
                        age_str = f"{age_seconds / 3600:.1f}h"
                    elif age_seconds >= 60:
                        age_str = f"{age_seconds / 60:.1f}m"
                    else:
                        age_str = f"{age_seconds:.0f}s"

                    # Format TTL
                    ttl_str = (
                        f"{key_metadata.ttl_seconds}s"
                        if key_metadata.ttl_seconds
                        else "None"
                    )

                    row_data.extend(
                        [
                            format_size_display(key_metadata.size_bytes),
                            age_str,
                            str(key_metadata.access_count),
                            ttl_str,
                        ]
                    )
                else:
                    row_data.extend(["N/A", "N/A", "N/A", "N/A"])

            if values:
                try:
                    cached_value = module_cache.get(key)
                    if cached_value is not None:
                        # Truncate very long values for display
                        value_str = str(cached_value)
                        if len(value_str) > 100:
                            value_display = value_str[:97] + "..."
                        else:
                            value_display = value_str
                        row_data.append(value_display)
                    else:
                        row_data.append("[dim]None[/dim]")
                except Exception as e:
                    row_data.append(f"[red]Error: {e}[/red]")

            table.add_row(*row_data)

        console.print(table)

    def _display_keys_list(
        self, cache_keys: list[str], module_cache: "CacheManager", values: bool
    ) -> None:
        """Display cache keys in simple list format."""
        for i, key in enumerate(sorted(cache_keys), 1):
            if values:
                try:
                    cached_value = module_cache.get(key)
                    if cached_value is not None:
                        # For simple format, show a brief preview of the value
                        value_str = str(cached_value)
                        if len(value_str) > 50:
                            value_preview = value_str[:47] + "..."
                        else:
                            value_preview = value_str
                        console.print(f"{i:3d}. {key}")
                        console.print(f"     [green]Value:[/green] {value_preview}")
                    else:
                        console.print(f"{i:3d}. {key}")
                        console.print("     [dim]Value: None[/dim]")
                except Exception as e:
                    console.print(f"{i:3d}. {key}")
                    console.print(f"     [red]Value Error: {e}[/red]")
            else:
                console.print(f"{i:3d}. {key}")

    def _display_all_modules_text(
        self, cache_subdirs: list[str], pattern: str | None, limit: int | None
    ) -> None:
        """Display all modules in text format."""
        console.print("[bold]Cache Keys by Module[/bold]")
        if pattern:
            console.print(f"[dim]Filtered by pattern: '{pattern}'[/dim]")
        console.print("=" * 60)

        total_keys = 0
        for module_name in sorted(cache_subdirs):
            try:
                from glovebox.core.cache import create_default_cache

                module_cache = create_default_cache(tag=module_name)
                cache_keys_all = module_cache.keys()

                # Apply pattern filtering
                if pattern:
                    cache_keys_all = [
                        key for key in cache_keys_all if pattern.lower() in key.lower()
                    ]

                console.print(
                    f"\n[bold cyan]📦 {module_name}[/bold cyan] ({len(cache_keys_all)} keys)"
                )

                if cache_keys_all:
                    if limit:
                        display_keys = cache_keys_all[:limit]
                    else:
                        display_keys = cache_keys_all

                    for key in sorted(display_keys):
                        console.print(f"  • {key}")

                    if limit and len(cache_keys_all) > limit:
                        console.print(
                            f"  [dim]... and {len(cache_keys_all) - limit} more keys[/dim]"
                        )
                else:
                    if pattern:
                        console.print(
                            f"  [dim]No keys matching pattern '{pattern}'[/dim]"
                        )
                    else:
                        console.print("  [dim]No keys found[/dim]")

                total_keys += len(cache_keys_all)

            except Exception as e:
                console.print(
                    f"\n[bold cyan]📦 {module_name}[/bold cyan] [red](Error: {e})[/red]"
                )

        console.print(f"\n[bold]Total keys across all modules:[/bold] {total_keys}")


@handle_errors
def cache_keys(
    module: Annotated[
        str | None,
        typer.Option(
            "-m",
            "--module",
            help="Show keys for specific module (layout, compilation, metrics)",
        ),
    ] = None,
    pattern: Annotated[
        str | None,
        typer.Option(
            "--pattern",
            help="Filter keys by pattern (case-insensitive substring match)",
        ),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option("--limit", help="Limit number of keys displayed"),
    ] = None,
    output_format: OutputFormatOption = "text",
    metadata: Annotated[
        bool,
        typer.Option("--metadata", help="Include metadata for each key"),
    ] = False,
    values: Annotated[
        bool,
        typer.Option("--values", help="Include actual cached values for each key"),
    ] = False,
) -> None:
    """List cache keys with optional filtering, metadata, and cached values."""
    command = CacheKeysCommand()
    command.execute(
        module=module,
        pattern=pattern,
        limit=limit,
        output_format=output_format,
        metadata=metadata,
        values=values,
    )
