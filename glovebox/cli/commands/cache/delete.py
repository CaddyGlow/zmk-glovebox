"""Cache delete CLI command."""

import json
import logging
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from .utils import get_icon, log_error_with_debug_stack


logger = logging.getLogger(__name__)
console = Console()


def cache_delete(
    module: Annotated[
        str,
        typer.Option("-m", "--module", help="Module to delete keys from"),
    ],
    keys: Annotated[
        str | None,
        typer.Option("--keys", help="Comma-separated cache keys to delete"),
    ] = None,
    json_file: Annotated[
        Path | None,
        typer.Option("--json-file", help="JSON file with keys to delete"),
    ] = None,
    pattern: Annotated[
        str | None,
        typer.Option("--pattern", help="Delete all keys matching pattern"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Show what would be deleted without actually deleting"
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force deletion without confirmation"),
    ] = False,
) -> None:
    """Delete specific cache keys from a module."""
    try:
        from glovebox.core.cache import create_default_cache

        module_cache = create_default_cache(tag=module)

        keys_to_delete: list[str] = []

        if keys:
            # Parse comma-separated keys
            keys_to_delete = [k.strip() for k in keys.split(",") if k.strip()]
        elif json_file:
            # Load keys from JSON file
            try:
                with json_file.open() as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "keys" in data:
                        # Handle format from cache keys --json command
                        if isinstance(data["keys"], list):
                            keys_to_delete = [
                                item["key"] if isinstance(item, dict) else str(item)
                                for item in data["keys"]
                            ]
                    elif isinstance(data, list):
                        # Handle simple list of keys
                        keys_to_delete = [str(key) for key in data]
                    else:
                        console.print(f"[red]Invalid JSON format in {json_file}[/red]")
                        raise typer.Exit(1)
            except Exception as e:
                console.print(f"[red]Error reading JSON file: {e}[/red]")
                raise typer.Exit(1) from e
        elif pattern:
            # Find keys matching pattern
            all_keys = module_cache.keys()
            keys_to_delete = [k for k in all_keys if pattern.lower() in k.lower()]

            # For compilation module, ALWAYS provide safety check to prevent workspace deletion
            if module == "compilation":
                # Check if any workspace keys would be matched
                workspace_prefixes = ["workspace_repo_", "workspace_repo_branch_"]
                workspace_keys = [
                    k
                    for k in keys_to_delete
                    if any(k.startswith(prefix) for prefix in workspace_prefixes)
                ]

                if workspace_keys:
                    # Show warning about workspace keys that would be deleted
                    console.print(
                        f"[red]WARNING: Pattern '{pattern}' matches {len(workspace_keys)} workspace cache keys![/red]"
                    )
                    console.print("[red]Workspace keys contain git repositories and build data.[/red]")
                    console.print("[yellow]Matched workspace keys:[/yellow]")
                    for i, key in enumerate(workspace_keys[:5], 1):  # Show first 5
                        console.print(f"  {i}. {key}")
                    if len(workspace_keys) > 5:
                        console.print(f"  ... and {len(workspace_keys) - 5} more")

                    # Require explicit confirmation for workspace deletion
                    if not force:
                        console.print(
                            "\n[red]Deleting workspace keys will permanently remove git repositories and build data![/red]"
                        )
                        workspace_confirm = typer.confirm(
                            "Are you SURE you want to delete workspace cache keys?"
                        )
                        if not workspace_confirm:
                            # Filter out workspace keys for safety
                            original_count = len(keys_to_delete)
                            keys_to_delete = [
                                k
                                for k in keys_to_delete
                                if not any(k.startswith(prefix) for prefix in workspace_prefixes)
                            ]
                            filtered_count = original_count - len(keys_to_delete)
                            console.print(
                                f"[green]Filtered out {filtered_count} workspace cache keys for safety[/green]"
                            )
        else:
            console.print("[red]Must specify --keys, --json-file, or --pattern[/red]")
            console.print("[dim]Examples:[/dim]")
            console.print('  glovebox cache delete -m compilation --keys "key1,key2"')
            console.print(
                '  glovebox cache delete -m compilation --pattern "build" --dry-run'
            )
            console.print(
                "  glovebox cache delete -m compilation --json-file cache_dump.json"
            )
            console.print(
                '  glovebox cache delete -m compilation --keys "key1,key2" --dry-run'
            )
            raise typer.Exit(1)

        if not keys_to_delete:
            console.print("[yellow]No keys found to delete[/yellow]")
            return

        # Show what will be deleted
        console.print(f"[yellow]Keys to delete from '{module}' module:[/yellow]")
        for i, key in enumerate(keys_to_delete, 1):
            console.print(f"  {i:3d}. {key}")

        if dry_run:
            # Dry run mode - show what would be deleted without actually deleting
            console.print(
                f"\n[cyan]DRY RUN: Would delete {len(keys_to_delete)} cache keys from '{module}' module[/cyan]"
            )

            # Check which keys actually exist
            existing_keys = []
            missing_keys = []
            for key in keys_to_delete:
                if module_cache.exists(key):
                    existing_keys.append(key)
                else:
                    missing_keys.append(key)

            if existing_keys:
                console.print(
                    f"[green]Would delete {len(existing_keys)} existing keys[/green]"
                )
            if missing_keys:
                console.print(
                    f"[yellow]Would skip {len(missing_keys)} missing keys[/yellow]"
                )

            return

        if not force:
            confirm = typer.confirm(f"Delete {len(keys_to_delete)} cache keys?")
            if not confirm:
                console.print("[yellow]Cancelled[/yellow]")
                return

        # Delete the keys
        deleted_count = module_cache.delete_many(keys_to_delete)

        icon_mode = "emoji"
        if deleted_count == len(keys_to_delete):
            console.print(
                f"[green]{get_icon('SUCCESS', icon_mode)} Deleted all {deleted_count} cache keys from '{module}'[/green]"
            )
        elif deleted_count > 0:
            console.print(
                f"[green]{get_icon('SUCCESS', icon_mode)} Deleted {deleted_count}/{len(keys_to_delete)} cache keys from '{module}'[/green]"
            )
            console.print(
                f"[yellow]{len(keys_to_delete) - deleted_count} keys were not found[/yellow]"
            )
        else:
            console.print(
                f"[yellow]No keys were deleted (all {len(keys_to_delete)} keys not found)[/yellow]"
            )

    except Exception as e:
        log_error_with_debug_stack(logger, "Failed to delete cache keys: %s", e)
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e
