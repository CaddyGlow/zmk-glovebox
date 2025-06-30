"""Workspace cache management CLI commands."""

import logging
import shutil
import time
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console

from glovebox.cli.workspace_display_utils import (
    filter_workspaces,
    format_workspace_entry,
)

from .utils import (
    format_icon_with_message,
    format_size_display,
    get_cache_manager_and_service,
    get_directory_size_bytes,
    get_icon,
    log_error_with_debug_stack,
)
from .workspace_processing import (
    cleanup_temp_directories,
    process_workspace_source,
)


logger = logging.getLogger(__name__)
console = Console()

workspace_app = typer.Typer(help="Workspace cache management")


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
    entries: Annotated[
        bool,
        typer.Option("--entries", help="Show entries grouped by cache level"),
    ] = False,
) -> None:
    """Show all cached ZMK workspace entries including orphaned directories."""
    try:
        cache_manager, workspace_cache_service, user_config = (
            get_cache_manager_and_service()
        )

        # Get cache directory and TTL configuration
        cache_dir = workspace_cache_service.get_cache_directory()
        ttl_config = workspace_cache_service.get_ttls_for_cache_levels()

        # Use the workspace cache service to list all workspaces (handles orphaned dirs)
        cached_workspaces = workspace_cache_service.list_cached_workspaces()

        # Convert workspace metadata to entry format using utility function
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

            # Use the utility function to format the workspace entry
            entry = format_workspace_entry(workspace_metadata, ttl_config)
            all_entries.append(entry)

        # Apply filters using utility function
        filtered_entries = filter_workspaces(
            all_entries,
            filter_repository=filter_repository,
            filter_branch=filter_branch,
            filter_level=filter_level,
        )

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
            from rich.table import Table

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
        log_error_with_debug_stack(logger, "Error in workspace_show: %s", e)
        console.print(f"[red]Error displaying workspace cache: {e}[/red]")
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
            get_cache_manager_and_service()
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
                size_bytes = target_workspace.size_bytes or get_directory_size_bytes(
                    target_workspace.workspace_path
                )
                confirm = typer.confirm(
                    f"Delete cached workspace for {repository} ({format_size_display(size_bytes)})?"
                )
                if not confirm:
                    console.print("[yellow]Cancelled[/yellow]")
                    return

            # Use the workspace cache service for deletion
            success = workspace_cache_service.delete_cached_workspace(repository)

            if success:
                icon_mode = "emoji"
                console.print(
                    f"[green]{format_icon_with_message('SUCCESS', f'Deleted cached workspace for {repository}', icon_mode)}[/green]"
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
                (
                    workspace.size_bytes
                    or get_directory_size_bytes(workspace.workspace_path)
                )
                for workspace in cached_workspaces
            )

            if not force:
                confirm = typer.confirm(
                    f"Delete ALL cached workspaces ({len(cached_workspaces)} workspaces, {format_size_display(total_size)})?"
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
                    f"[green]{format_icon_with_message('SUCCESS', f'Deleted {deleted_count} cached workspaces ({format_size_display(total_size)})', icon_mode)}[/green]"
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
            get_cache_manager_and_service()
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
            (workspace.size_bytes or get_directory_size_bytes(workspace.workspace_path))
            for workspace in stale_workspaces
        )

        console.print(
            f"[yellow]Found {len(stale_workspaces)} stale workspaces ({format_size_display(total_stale_size)})[/yellow]"
        )

        if not force:
            console.print("\n[bold]Workspaces to be cleaned up:[/bold]")
            for workspace in stale_workspaces:
                age_days = workspace.age_hours / 24
                size_bytes = workspace.size_bytes or get_directory_size_bytes(
                    workspace.workspace_path
                )
                console.print(
                    f"  • {workspace.repository}@{workspace.branch}: {format_size_display(size_bytes)} (age: {age_days:.1f}d)"
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
                f"[green]{format_icon_with_message('SUCCESS', f'Cleaned up {cleaned_count} stale workspaces ({format_size_display(total_stale_size)})', icon_mode)}[/green]"
            )
        else:
            console.print("[yellow]No workspaces were cleaned up[/yellow]")

    except Exception as e:
        logger.error("Failed to cleanup workspace cache: %s", e)
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e


@workspace_app.command(name="add")
def workspace_add(
    workspace_source: Annotated[
        str,
        typer.Argument(
            help="Path to ZMK workspace directory, zip file, or URL to zip file"
        ),
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
    progress: Annotated[
        bool,
        typer.Option(
            "--progress/--no-progress", help="Show progress bar during copy operations"
        ),
    ] = True,
    show_logs: Annotated[
        bool,
        typer.Option(
            "--show-logs/--no-show-logs",
            help="Show detailed operation logs in progress display (default: enabled when progress is shown)",
        ),
    ] = True,
) -> None:
    """Add an existing ZMK workspace to cache from directory, zip file, or URL.

    This allows you to cache a workspace from various sources:
    - Local directory: /path/to/workspace
    - Local zip file: /path/to/workspace.zip
    - Remote zip URL: https://example.com/workspace.zip

    The workspace should contain directories like: zmk/, zephyr/, modules/
    """
    try:
        cache_manager, workspace_cache_service, user_config = (
            get_cache_manager_and_service()
        )
        icon_mode = "emoji"  # Default icon mode

        # Determine source type and process accordingly
        workspace_path, temp_cleanup_dirs = process_workspace_source(
            workspace_source, progress=progress, console=console
        )

        # Use the new workspace cache service for adding external workspace
        if not repository:
            typer.echo(
                "Error: Repository must be specified when injecting workspace", err=True
            )
            raise typer.Exit(1)

        # Setup progress tracking using the new scrollable logs display
        start_time = time.time()
        progress_callback = None

        if progress:
            from glovebox.cli.progress.workspace import create_workspace_cache_progress

            # Create display and callback using the factory function with show_logs parameter
            display, progress_callback = create_workspace_cache_progress(
                operation_type="workspace_add",
                repository=repository,
                show_logs=show_logs
            )

        try:
            if progress and "display" in locals():
                # Use the display context manager for clean lifecycle
                with display:
                    logger.info(f"Adding workspace cache for {repository}")
                    logger.info(f"Source: {workspace_source}")

                    result = workspace_cache_service.inject_existing_workspace(
                        workspace_path=workspace_path,
                        repository=repository,
                        progress_callback=progress_callback,
                    )
            else:
                result = workspace_cache_service.inject_existing_workspace(
                    workspace_path=workspace_path,
                    repository=repository,
                    progress_callback=progress_callback,
                )
        finally:
            # Cleanup temporary directories from zip extraction
            cleanup_temp_directories(temp_cleanup_dirs)

        if result.success and result.metadata:
            # Display success information with enhanced metadata
            metadata = result.metadata

            # Calculate and display transfer summary
            end_time = time.time()
            total_time = end_time - start_time

            # Display transfer summary using metadata
            if metadata.size_bytes and metadata.size_bytes > 0 and total_time > 0:
                avg_speed_mbps = (metadata.size_bytes / (1024 * 1024)) / total_time
                console.print(
                    f"[bold cyan]📊 Transfer Summary:[/bold cyan] "
                    f"{format_size_display(metadata.size_bytes)} copied in "
                    f"{total_time:.1f}s at {avg_speed_mbps:.1f} MB/s"
                )
                console.print()  # Extra spacing

            console.print(
                f"[green]{format_icon_with_message('SUCCESS', 'Successfully added workspace cache', icon_mode)}[/green]"
            )
            console.print(
                f"[bold]Repository:[/bold] {metadata.repository}@{metadata.branch}"
            )
            console.print(f"[bold]Cache location:[/bold] {metadata.workspace_path}")

            if metadata.size_bytes:
                console.print(
                    f"[bold]Total size:[/bold] {format_size_display(metadata.size_bytes)}"
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
                f"\n[green]{format_icon_with_message('SUCCESS', 'Successfully added workspace cache', icon_mode)}[/green]"
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


def register_workspace_commands(app: typer.Typer) -> None:
    """Register workspace commands with the main cache app."""
    app.add_typer(workspace_app, name="workspace")
