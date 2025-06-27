"""Cache keys CLI command."""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from glovebox.config.user_config import create_user_config

from .utils import format_size_display


logger = logging.getLogger(__name__)
console = Console()


def cache_keys(
    module: Annotated[
        str | None,
        typer.Option(
            "-m",
            "--module",
            help="Show keys for specific module (e.g., 'layout', 'compilation', 'metrics')",
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
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output keys in JSON format"),
    ] = False,
    metadata: Annotated[
        bool,
        typer.Option("--metadata", help="Include metadata for each key"),
    ] = False,
    values: Annotated[
        bool,
        typer.Option("--values", help="Include actual cached values for each key"),
    ] = False,
) -> None:
    """List cache keys with optional filtering, metadata, and actual cached values."""
    try:
        if module:
            # Show keys for specific module
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

                if json_output:
                    # JSON output format
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
                                        key_data["value_type"] = type(
                                            cached_value
                                        ).__name__
                                else:
                                    key_data["value"] = None
                            except Exception as e:
                                key_data["value_error"] = str(e)

                        output_data["keys"].append(key_data)

                    print(json.dumps(output_data, indent=2, ensure_ascii=False))
                else:
                    # Human-readable output
                    if cache_keys:
                        console.print(f"[bold]Cache Keys in '{module}' Module[/bold]")
                        if pattern:
                            console.print(
                                f"[dim]Filtered by pattern: '{pattern}'[/dim]"
                            )
                        console.print("=" * 60)

                        if metadata or values:
                            # Table format with metadata and/or values
                            table = Table(show_header=True, header_style="bold green")
                            table.add_column("Cache Key", style="cyan")

                            if metadata:
                                table.add_column("Size", style="white")
                                table.add_column("Age", style="blue")
                                table.add_column("Accesses", style="yellow")
                                table.add_column("TTL", style="magenta")

                            if values:
                                table.add_column("Cached Value", style="green")

                            for key in sorted(cache_keys):
                                row_data = [key]

                                if metadata:
                                    key_metadata = module_cache.get_metadata(key)
                                    if key_metadata:
                                        # Calculate age
                                        age_seconds = (
                                            time.time() - key_metadata.created_at
                                        )
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
                                                format_size_display(
                                                    key_metadata.size_bytes
                                                ),
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
                        else:
                            # Simple list format
                            for i, key in enumerate(sorted(cache_keys), 1):
                                if values:
                                    try:  # type: ignore[unreachable]
                                        cached_value = module_cache.get(key)
                                        if cached_value is not None:
                                            # For simple format, show a brief preview of the value
                                            value_str = str(cached_value)
                                            if len(value_str) > 50:
                                                value_preview = value_str[:47] + "..."
                                            else:
                                                value_preview = value_str
                                            console.print(f"{i:3d}. {key}")
                                            console.print(
                                                f"     [green]Value:[/green] {value_preview}"
                                            )
                                        else:
                                            console.print(f"{i:3d}. {key}")
                                            console.print("     [dim]Value: None[/dim]")
                                    except Exception as e:
                                        console.print(f"{i:3d}. {key}")
                                        console.print(
                                            f"     [red]Value Error: {e}[/red]"
                                        )
                                else:
                                    console.print(f"{i:3d}. {key}")

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

            except Exception as e:
                console.print(
                    f"[red]Error accessing cache for module '{module}': {e}[/red]"
                )
                raise typer.Exit(1) from e
        else:
            # Show keys for all modules
            user_config = create_user_config()
            diskcache_root = user_config._config.cache_path

            if not diskcache_root.exists():
                console.print("[yellow]No cache directory found[/yellow]")
                return

            cache_subdirs = [d.name for d in diskcache_root.iterdir() if d.is_dir()]

            if not cache_subdirs:
                console.print("[yellow]No cache modules found[/yellow]")
                return

            if json_output:
                # JSON output for all modules
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
                                key
                                for key in cache_keys_all
                                if pattern.lower() in key.lower()
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

                print(json.dumps(all_modules_data, indent=2, ensure_ascii=False))
            else:
                # Human-readable output for all modules
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
                                key
                                for key in cache_keys_all
                                if pattern.lower() in key.lower()
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

                console.print(
                    f"\n[bold]Total keys across all modules:[/bold] {total_keys}"
                )

    except Exception as e:
        logger.error("Failed to list cache keys: %s", e)
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e
