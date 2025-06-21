"""New workspace_show function using workspace cache service."""

import logging
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

logger = logging.getLogger(__name__)
console = Console()


def _format_size(size_bytes: float) -> str:
    """Format size in human readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def _get_directory_size(path) -> int:
    """Get total size of directory in bytes."""
    total = 0
    try:
        for file_path in path.rglob("*"):
            if file_path.is_file():
                total += file_path.stat().st_size
    except (OSError, PermissionError):
        pass
    return total


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
    entries: Annotated[
        bool,
        typer.Option("--entries", help="Show entries grouped by cache level"),
    ] = False,
) -> None:
    """Show all cached ZMK workspace entries including orphaned directories."""
    try:
        from glovebox.cli.commands.cache import _get_cache_manager_and_service
        
        cache_manager, workspace_cache_service, user_config = (
            _get_cache_manager_and_service()
        )

        # Get cache directory and TTL configuration
        cache_dir = workspace_cache_service.get_cache_directory()
        ttl_config = workspace_cache_service.get_ttls_for_cache_levels()

        # Use the workspace cache service to list all workspaces (handles orphaned dirs)
        cached_workspaces = workspace_cache_service.list_cached_workspaces()

        # Convert workspace metadata to entry format
        all_entries: list[dict[str, Any]] = []

        for workspace_metadata in cached_workspaces:
            # Extract cache level
            cache_level_value = (
                workspace_metadata.cache_level.value
                if hasattr(workspace_metadata.cache_level, "value")
                else str(workspace_metadata.cache_level)
            )

            # Skip build-level caches as they represent compiled artifacts, not workspaces
            if cache_level_value == "build":
                continue

            # Format age and TTL
            age_hours = workspace_metadata.age_hours
            if age_hours >= 24:  # >= 1 day
                age_str = f"{age_hours / 24:.1f}d"
            elif age_hours >= 1:  # >= 1 hour
                age_str = f"{age_hours:.1f}h"
            else:  # < 1 hour
                age_str = f"{age_hours * 60:.1f}m"

            # Calculate TTL remaining
            ttl_seconds = ttl_config.get(cache_level_value, 3600)
            age_seconds = age_hours * 3600
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

            # Generate cache key for display (matches the directory name)
            from glovebox.core.workspace_cache_utils import generate_workspace_cache_key
            cache_key = generate_workspace_cache_key(
                workspace_metadata.repository, 
                workspace_metadata.branch, 
                cache_level_value
            )

            # Calculate size
            try:
                if workspace_metadata.workspace_path.exists():
                    size_bytes = _get_directory_size(workspace_metadata.workspace_path)
                    size_display = _format_size(size_bytes)
                else:
                    size_display = "N/A"
            except Exception:
                size_display = "N/A"

            # Check for symlinks
            path_display = str(workspace_metadata.workspace_path)
            if workspace_metadata.workspace_path.is_symlink():
                try:
                    actual_path = workspace_metadata.workspace_path.resolve()
                    path_display = f"{workspace_metadata.workspace_path} → {actual_path}"
                except (OSError, RuntimeError):
                    path_display = f"{workspace_metadata.workspace_path} → [BROKEN]"

            entry = {
                "cache_key": cache_key,
                "repository": workspace_metadata.repository,
                "branch": workspace_metadata.branch,
                "cache_level": cache_level_value,
                "age": age_str,
                "ttl_remaining": ttl_str,
                "size": size_display,
                "workspace_path": path_display,
                "notes": workspace_metadata.notes or "",
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

            cache_levels = ["base", "branch", "full", "build"]
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
            table.add_column("Notes", style="dim")

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
                    entry["notes"],
                )

            console.print(table)
            console.print(f"\n[bold]Total entries:[/bold] {len(filtered_entries)}")
            console.print(f"[dim]Cache directory: {cache_dir}[/dim]")

    except Exception as e:
        exc_info = logger.isEnabledFor(logging.DEBUG)
        logger.error("Error in workspace_show: %s", e, exc_info=exc_info)
        console.print(f"[red]Error displaying workspace cache: {e}[/red]")
        raise typer.Exit(1) from e