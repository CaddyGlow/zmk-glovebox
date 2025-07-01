"""Workspace cache management CLI commands."""

import logging
import shutil
import time
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console

from glovebox.cli.decorators import with_metrics
from glovebox.cli.helpers.theme import (
    Colors,
    Icons,
    format_file_operation,
    format_operation_status,
    format_status_message,
    get_icon_mode_from_context,
)
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
                console.print(format_status_message("No cached workspaces found", "warning"))
            else:
                console.print(
                    format_status_message("No cache entries match the specified filters", "warning")
                )
            console.print(f"[{Colors.MUTED}]Cache directory: {cache_dir}[/{Colors.MUTED}]")
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

            console.print(f"[{Colors.HEADER}]All Cached Workspace Entries[/{Colors.HEADER}]")
            console.print("=" * 80)

            table = Table(show_header=True, header_style=Colors.SUCCESS)
            table.add_column("Cache Key", style=Colors.MUTED)
            table.add_column("Repository", style=Colors.PRIMARY)
            table.add_column("Branch", style=Colors.WARNING)
            table.add_column("Level", style=Colors.ACCENT)
            table.add_column("Age", style=Colors.INFO)
            table.add_column("TTL Remaining", style=Colors.SUCCESS)
            table.add_column("Size", style=Colors.NORMAL)
            table.add_column("Notes", style=Colors.MUTED)

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
            console.print(f"\n[{Colors.FIELD_NAME}]Total entries:[/{Colors.FIELD_NAME}] {len(filtered_entries)}")
            console.print(f"[{Colors.MUTED}]Cache directory: {cache_dir}[/{Colors.MUTED}]")

    except Exception as e:
        log_error_with_debug_stack(logger, "Error in workspace_show: %s", e)
        console.print(format_status_message(f"Error displaying workspace cache: {e}", "error"))
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
                    format_status_message(f"No cached workspace found for {repository}", "warning")
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
                    console.print(format_status_message("Cancelled", "warning"))
                    return

            # Use the workspace cache service for deletion
            success = workspace_cache_service.delete_cached_workspace(repository)

            if success:
                icon_mode = "emoji"
                console.print(
                    f"[{Colors.SUCCESS}]{format_icon_with_message('SUCCESS', f'Deleted cached workspace for {repository}', icon_mode)}[/{Colors.SUCCESS}]"
                )
            else:
                console.print(
                    format_status_message(f"Failed to delete cached workspace for {repository}", "error")
                )
                raise typer.Exit(1)
        else:
            # Delete all workspaces
            cached_workspaces = workspace_cache_service.list_cached_workspaces()

            if not cached_workspaces:
                console.print(format_status_message("No cached workspaces found", "warning"))
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
                    console.print(format_status_message("Cancelled", "warning"))
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
                    f"[{Colors.SUCCESS}]{format_icon_with_message('SUCCESS', f'Deleted {deleted_count} cached workspaces ({format_size_display(total_size)})', icon_mode)}[/{Colors.SUCCESS}]"
                )
            else:
                console.print(format_status_message("Failed to delete any cached workspaces", "error"))
                raise typer.Exit(1)

    except Exception as e:
        logger.error("Failed to delete workspace cache: %s", e)
        console.print(format_status_message(f"Error: {e}", "error"))
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
                format_status_message(f"No workspaces older than {max_age_days} days found", "success")
            )
            return

        total_stale_size = sum(
            (workspace.size_bytes or get_directory_size_bytes(workspace.workspace_path))
            for workspace in stale_workspaces
        )

        console.print(
            format_status_message(f"Found {len(stale_workspaces)} stale workspaces ({format_size_display(total_stale_size)})", "warning")
        )

        if not force:
            console.print(f"\n[{Colors.FIELD_NAME}]Workspaces to be cleaned up:[/{Colors.FIELD_NAME}]")
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
                console.print(format_status_message("Cancelled", "warning"))
                return

        # Perform cleanup using the service
        cleaned_count = workspace_cache_service.cleanup_stale_entries(max_age_hours)

        if cleaned_count > 0:
            icon_mode = "emoji"
            console.print(
                f"[{Colors.SUCCESS}]{format_icon_with_message('SUCCESS', f'Cleaned up {cleaned_count} stale workspaces ({format_size_display(total_stale_size)})', icon_mode)}[/{Colors.SUCCESS}]"
            )
        else:
            console.print(format_status_message("No workspaces were cleaned up", "warning"))

    except Exception as e:
        logger.error("Failed to cleanup workspace cache: %s", e)
        console.print(format_status_message(f"Error: {e}", "error"))
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

        # Setup progress tracking using the new scrollable logs display
        start_time = time.time()
        progress_callback = None
        temp_cleanup_dirs = []  # Initialize to avoid undefined variable

        # Progress is enabled by default unless explicitly disabled
        display = None
        progress_coordinator = None

        if progress:
            # Use simple progress display for cache operations
            from glovebox.compilation.simple_progress import (
                ProgressConfig,
                create_simple_compilation_display,
                create_simple_progress_coordinator,
            )

            # Create workspace-specific configuration
            workspace_config = ProgressConfig(
                title_processing="→ Processing Workspace",
                title_complete="✓ Workspace Ready",
                title_failed="✗ Workspace Failed",
                operation_name="Workspace",
                tasks=[
                    "Cache Setup",
                    "Workspace Setup",
                    "Processing Files",
                    "Workspace Injection",
                    "Finalizing",
                ],
            )

            display = create_simple_compilation_display(console, workspace_config)
            progress_coordinator = create_simple_progress_coordinator(display)

            # Start display immediately to show all operations
            display.start()

            # Set initial phase for workspace processing
            progress_coordinator.transition_to_phase(
                "workspace_setup", "Processing workspace source"
            )

        try:
            # Determine source type and process accordingly
            # Disable visual progress in process_workspace_source to avoid competing displays
            workspace_path, temp_cleanup_dirs = process_workspace_source(
                workspace_source,
                progress=False,
                console=console,
                progress_coordinator=progress_coordinator,
            )

            # Use the new workspace cache service for adding external workspace
            if not repository:
                typer.echo(
                    "Error: Repository must be specified when injecting workspace",
                    err=True,
                )
                raise typer.Exit(1)

            # Set phase for workspace injection
            if progress_coordinator:
                progress_coordinator.transition_to_phase(
                    "workspace_setup", "Adding workspace to cache"
                )

            logger.info(f"Adding workspace cache for {repository}")
            logger.info(f"Source: {workspace_source}")

            result = workspace_cache_service.inject_existing_workspace(
                workspace_path=workspace_path,
                repository=repository,
                progress_callback=progress_callback,
                progress_coordinator=progress_coordinator,
            )

            # Mark as completed
            if progress_coordinator:
                progress_coordinator.transition_to_phase(
                    "complete", "Workspace successfully added to cache"
                )

        finally:
            # Stop display if it was started
            if display is not None:
                display.stop()

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
                transfer_icon = Icons.get_icon("STATS", "emoji")
                console.print(
                    f"[{Colors.INFO}]{transfer_icon} Transfer Summary:[/{Colors.INFO}] "
                    f"{format_size_display(metadata.size_bytes)} copied in "
                    f"{total_time:.1f}s at {avg_speed_mbps:.1f} MB/s"
                )
                console.print()  # Extra spacing

            console.print(
                f"[{Colors.SUCCESS}]{format_icon_with_message('SUCCESS', 'Successfully added workspace cache', icon_mode)}[/{Colors.SUCCESS}]"
            )
            console.print(
                f"[{Colors.FIELD_NAME}]Repository:[/{Colors.FIELD_NAME}] {metadata.repository}@{metadata.branch}"
            )
            console.print(f"[{Colors.FIELD_NAME}]Cache location:[/{Colors.FIELD_NAME}] {metadata.workspace_path}")

            if metadata.size_bytes:
                console.print(
                    f"[{Colors.FIELD_NAME}]Total size:[/{Colors.FIELD_NAME}] {format_size_display(metadata.size_bytes)}"
                )

            if metadata.cached_components:
                console.print(
                    f"[{Colors.FIELD_NAME}]Components cached:[/{Colors.FIELD_NAME}] {', '.join(metadata.cached_components)}"
                )

            # Handle cache_level safely
            cache_level_str = (
                metadata.cache_level.value
                if hasattr(metadata.cache_level, "value")
                else str(metadata.cache_level)
            )
            console.print(f"[{Colors.FIELD_NAME}]Cache level:[/{Colors.FIELD_NAME}] {cache_level_str}")

            if metadata.auto_detected:
                console.print(
                    f"[{Colors.FIELD_NAME}]Auto-detected from:[/{Colors.FIELD_NAME}] {metadata.auto_detected_source}"
                )

            console.print(
                f"\n[{Colors.MUTED}]Future builds using '{metadata.repository}' will now use this cache![/{Colors.MUTED}]"
            )
        elif result.success:
            # Success but no metadata (shouldn't happen, but handle gracefully)
            console.print(
                f"\n[{Colors.SUCCESS}]{format_icon_with_message('SUCCESS', 'Successfully added workspace cache', icon_mode)}[/{Colors.SUCCESS}]"
            )
        else:
            console.print(
                f"[{Colors.ERROR}]Failed to add workspace to cache: {result.error_message}[/{Colors.ERROR}]"
            )
            raise typer.Exit(1)

    except Exception as e:
        logger.error("Failed to add workspace to cache: %s", e)
        console.print(f"[{Colors.ERROR}]Error: {e}[/{Colors.ERROR}]")
        raise typer.Exit(1) from e


@workspace_app.command(name="export")
@with_metrics("workspace_export")
def workspace_export(
    ctx: typer.Context,
    repository: Annotated[
        str,
        typer.Argument(help="Repository name (e.g., 'zmkfirmware/zmk')"),
    ],
    branch: Annotated[
        str | None,
        typer.Argument(help="Branch name (optional, for repo+branch cache level)"),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output archive path (auto-generated if not specified)",
        ),
    ] = None,
    format: Annotated[
        str,
        typer.Option(
            "--format",
            help="Archive format (zip, tar, tar.gz, tar.bz2, tar.xz)",
        ),
    ] = "zip",
    compression_level: Annotated[
        int | None,
        typer.Option(
            "--compression-level",
            "-c",
            help="Compression level (1-9, default varies by format)",
            min=1,
            max=9,
        ),
    ] = None,
    include_git: Annotated[
        bool,
        typer.Option(
            "--include-git/--no-include-git",
            help="Include .git folders in export (if available in cached workspace)",
        ),
    ] = True,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing output file"),
    ] = False,
    progress: Annotated[
        bool,
        typer.Option(
            "--progress/--no-progress", help="Show progress bar during export"
        ),
    ] = True,
) -> None:
    """Export cached workspace to compressed archive.

    This command exports a cached ZMK workspace to various archive formats:
    - ZIP with configurable compression levels
    - TAR with optional compression (gzip, bzip2, xz)

    Examples:
        glovebox cache workspace export zmkfirmware/zmk main
        glovebox cache workspace export zmkfirmware/zmk --format tar.gz
        glovebox cache workspace export zmkfirmware/zmk main -o my_workspace.zip
    """
    try:
        # Import here to avoid circular dependencies
        from glovebox.compilation.cache.models import ArchiveFormat

        # Get session_metrics from context
        session_metrics = getattr(ctx.obj, "session_metrics", None)

        cache_manager, workspace_cache_service, user_config = (
            get_cache_manager_and_service(session_metrics=session_metrics)
        )
        icon_mode = "emoji"

        # Validate archive format
        try:
            archive_format = ArchiveFormat(format.lower())
        except ValueError:
            console.print(f"[{Colors.ERROR}]Invalid archive format: {format}[/{Colors.ERROR}]")
            console.print(
                f"[{Colors.MUTED}]Supported formats: zip, tar, tar.gz, tar.bz2, tar.xz[/{Colors.MUTED}]"
            )
            raise typer.Exit(1) from None

        # Check if workspace exists in cache
        cache_result = workspace_cache_service.get_cached_workspace(repository, branch)
        if not cache_result.success or not cache_result.metadata:
            cache_type = "repo+branch" if branch else "repo-only"
            console.print(
                f"[{Colors.ERROR}]No cached workspace found for {repository} ({cache_type})[/{Colors.ERROR}]"
            )
            console.print(
                f"[{Colors.MUTED}]Use 'glovebox cache workspace show' to see available workspaces[/{Colors.MUTED}]"
            )
            raise typer.Exit(1)

        metadata = cache_result.metadata

        # Generate output path if not provided
        if output is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            repo_name = repository.replace("/", "_")
            branch_part = f"_{branch}" if branch else ""
            filename = f"{repo_name}{branch_part}_workspace_{timestamp}{archive_format.file_extension}"
            output = Path.cwd() / filename

        # Check if output file exists and handle force flag
        if output.exists() and not force:
            confirm = typer.confirm(f"Output file {output} already exists. Overwrite?")
            if not confirm:
                console.print(f"[{Colors.WARNING}]Cancelled[/{Colors.WARNING}]")
                return

        # Setup progress tracking
        start_time = time.time()
        display = None
        progress_coordinator = None

        if progress:
            from glovebox.compilation.simple_progress import (
                ProgressConfig,
                create_simple_compilation_display,
                create_simple_progress_coordinator,
            )

            # Create workspace export configuration
            export_config = ProgressConfig(
                title_processing="↑ Exporting Workspace",
                title_complete="✓ Export Complete",
                title_failed="✗ Export Failed",
                operation_name="Workspace Export",
                tasks=[
                    "Cache Setup",
                    "Preparing Export",
                    "Scanning Files",
                    "Creating Archive",
                    "Finalizing Export",
                ],
            )

            display = create_simple_compilation_display(console, export_config)
            progress_coordinator = create_simple_progress_coordinator(display)
            display.start()

            # Set initial phase for export
            cache_type = "repo+branch" if branch else "repo-only"
            progress_coordinator.transition_to_phase(
                "initialization", f"Preparing export for {repository} ({cache_type})"
            )

            # Set workspace export task as active
            if hasattr(progress_coordinator, "set_enhanced_task_status"):
                progress_coordinator.set_enhanced_task_status(
                    "workspace_export", "active", f"Exporting to {archive_format.value}"
                )

        try:
            # Perform the export
            export_result = workspace_cache_service.export_cached_workspace(
                repository=repository,
                branch=branch,
                output_path=output,
                archive_format=archive_format,
                compression_level=compression_level,
                include_git=include_git,
                progress_coordinator=progress_coordinator,
            )

            # Mark as completed
            if progress_coordinator:
                if export_result.success:
                    progress_coordinator.transition_to_phase(
                        "complete", "Export completed successfully"
                    )
                else:
                    progress_coordinator.transition_to_phase(
                        "error", f"Export failed: {export_result.error_message}"
                    )

        finally:
            # Stop display if it was started
            if display is not None:
                display.stop()

        if export_result.success:
            # Display success information
            end_time = time.time()
            total_time = end_time - start_time

            console.print(
                f"[{Colors.SUCCESS}]{format_icon_with_message('SUCCESS', 'Workspace exported successfully', icon_mode)}[/{Colors.SUCCESS}]"
            )
            console.print(f"[{Colors.FIELD_NAME}]Repository:[/{Colors.FIELD_NAME}] {repository}")
            if branch:
                console.print(f"[{Colors.FIELD_NAME}]Branch:[/{Colors.FIELD_NAME}] {branch}")
            console.print(f"[{Colors.FIELD_NAME}]Output file:[/{Colors.FIELD_NAME}] {export_result.export_path}")
            console.print(f"[{Colors.FIELD_NAME}]Archive format:[/{Colors.FIELD_NAME}] {archive_format.value}")

            if export_result.original_size_bytes and export_result.archive_size_bytes:
                console.print(
                    f"[{Colors.FIELD_NAME}]Original size:[/{Colors.FIELD_NAME}] {format_size_display(export_result.original_size_bytes)}"
                )
                console.print(
                    f"[{Colors.FIELD_NAME}]Compressed size:[/{Colors.FIELD_NAME}] {format_size_display(export_result.archive_size_bytes)}"
                )

                if export_result.compression_percentage:
                    console.print(
                        f"[{Colors.FIELD_NAME}]Compression:[/{Colors.FIELD_NAME}] {export_result.compression_percentage:.1f}% reduction"
                    )

            if export_result.files_count:
                console.print(
                    f"[{Colors.FIELD_NAME}]Files exported:[/{Colors.FIELD_NAME}] {export_result.files_count:,}"
                )

            if export_result.export_speed_mb_s and export_result.export_speed_mb_s > 0:
                console.print(
                    f"[{Colors.FIELD_NAME}]Export speed:[/{Colors.FIELD_NAME}] {export_result.export_speed_mb_s:.1f} MB/s"
                )

            console.print(f"[{Colors.FIELD_NAME}]Export time:[/{Colors.FIELD_NAME}] {total_time:.1f}s")

            # Show workspace metadata info
            if metadata.cached_components:
                console.print(
                    f"[{Colors.FIELD_NAME}]Components exported:[/{Colors.FIELD_NAME}] {', '.join(metadata.cached_components)}"
                )

            git_status = "included" if include_git else "excluded"
            console.print(f"[{Colors.FIELD_NAME}]Git folders:[/{Colors.FIELD_NAME}] {git_status}")

        else:
            console.print(
                f"[{Colors.ERROR}]Failed to export workspace: {export_result.error_message}[/{Colors.ERROR}]"
            )
            raise typer.Exit(1)

    except Exception as e:
        logger.error("Failed to export workspace: %s", e)
        console.print(f"[{Colors.ERROR}]Error: {e}[/{Colors.ERROR}]")
        raise typer.Exit(1) from e


@workspace_app.command(name="create")
@with_metrics("workspace_create")
def workspace_create(
    ctx: typer.Context,
    repo_spec: Annotated[
        str,
        typer.Argument(
            help="Repository specification in format 'org/repo@branch' (e.g., 'moergo-sc/zmk@main')"
        ),
    ],
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            "-p",
            help="Keyboard profile for configuration (e.g., 'glove80/v25.05')",
        ),
    ] = None,
    docker_image: Annotated[
        str | None,
        typer.Option(
            "--docker-image",
            help="Docker image to use for workspace creation (overrides profile default)",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force", "-f", help="Force recreation of workspace if it already exists"
        ),
    ] = False,
    progress: Annotated[
        bool,
        typer.Option(
            "--progress/--no-progress", help="Show progress during workspace creation"
        ),
    ] = True,
) -> None:
    """Create a new ZMK workspace from repository specification.

    This command creates a fresh ZMK workspace by:
    1. Parsing the repository specification (org/repo@branch)
    2. Setting up Docker environment for workspace preparation
    3. Initializing west workspace and cloning repository
    4. Updating dependencies with west update
    5. Caching the prepared workspace for future use

    Examples:
        glovebox cache workspace create moergo-sc/zmk@main
        glovebox cache workspace create zmkfirmware/zmk@v3.5.0 --profile glove80
        glovebox cache workspace create moergo-sc/zmk@v26.01 --force
    """
    try:
        # Get session_metrics from context
        session_metrics = getattr(ctx.obj, "session_metrics", None)

        cache_manager, workspace_cache_service, user_config = (
            get_cache_manager_and_service(session_metrics=session_metrics)
        )
        icon_mode = "emoji"

        # Parse keyboard profile if provided
        keyboard_profile = None
        if profile:
            try:
                from glovebox.config import create_keyboard_profile

                # Parse profile (e.g., "glove80/v25.05" or "glove80")
                if "/" in profile:
                    keyboard_name, firmware_version = profile.split("/", 1)
                    keyboard_profile = create_keyboard_profile(
                        keyboard_name, firmware_version
                    )
                else:
                    keyboard_profile = create_keyboard_profile(profile)
            except Exception as e:
                console.print(f"[{Colors.ERROR}]Invalid keyboard profile '{profile}': {e}[/{Colors.ERROR}]")
                raise typer.Exit(1) from e

        # Setup progress tracking
        start_time = time.time()
        display = None
        progress_coordinator = None

        if progress:
            from glovebox.compilation.simple_progress import (
                ProgressConfig,
                create_simple_compilation_display,
                create_simple_progress_coordinator,
            )

            # Create workspace creation configuration
            create_config = ProgressConfig(
                title_processing="+ Creating Workspace",
                title_complete="✓ Workspace Created",
                title_failed="✗ Creation Failed",
                operation_name="Workspace Creation",
                tasks=[
                    "Cache Setup",
                    "Repository Clone",
                    "Processing Files",
                    "Workspace Setup",
                    "Finalizing",
                ],
            )

            display = create_simple_compilation_display(console, create_config)
            progress_coordinator = create_simple_progress_coordinator(display)
            display.start()

            # Set initial phase
            progress_coordinator.transition_to_phase(
                "initialization", f"Creating workspace for {repo_spec}"
            )

        try:
            # Create workspace using the cache service
            result = workspace_cache_service.create_workspace_from_spec(
                repo_spec=repo_spec,
                keyboard_profile=keyboard_profile,
                docker_image=docker_image,
                force_recreate=force,
                progress_coordinator=progress_coordinator,
            )

            # Mark as completed
            if progress_coordinator:
                if result.success:
                    progress_coordinator.transition_to_phase(
                        "complete", "Workspace created and cached successfully"
                    )
                else:
                    progress_coordinator.transition_to_phase(
                        "error", f"Workspace creation failed: {result.error_message}"
                    )

        finally:
            # Stop display if it was started
            if display is not None:
                display.stop()

        if result.success and result.metadata:
            # Display success information
            end_time = time.time()
            total_time = end_time - start_time
            metadata = result.metadata

            console.print(
                f"[{Colors.SUCCESS}]{format_icon_with_message('SUCCESS', 'Workspace created successfully', icon_mode)}[/{Colors.SUCCESS}]"
            )
            console.print(f"[{Colors.FIELD_NAME}]Repository:[/{Colors.FIELD_NAME}] {metadata.repository}")
            console.print(f"[{Colors.FIELD_NAME}]Branch:[/{Colors.FIELD_NAME}] {metadata.branch}")
            console.print(f"[{Colors.FIELD_NAME}]Cache location:[/{Colors.FIELD_NAME}] {metadata.workspace_path}")

            if metadata.size_bytes:
                console.print(
                    f"[{Colors.FIELD_NAME}]Total size:[/{Colors.FIELD_NAME}] {format_size_display(metadata.size_bytes)}"
                )

            if metadata.cached_components:
                console.print(
                    f"[{Colors.FIELD_NAME}]Components:[/{Colors.FIELD_NAME}] {', '.join(metadata.cached_components)}"
                )

            if metadata.docker_image:
                console.print(f"[{Colors.FIELD_NAME}]Docker image:[/{Colors.FIELD_NAME}] {metadata.docker_image}")

            if metadata.creation_profile:
                console.print(f"[{Colors.FIELD_NAME}]Profile used:[/{Colors.FIELD_NAME}] {metadata.creation_profile}")

            console.print(f"[{Colors.FIELD_NAME}]Creation time:[/{Colors.FIELD_NAME}] {total_time:.1f}s")

            console.print(
                f"\n[{Colors.MUTED}]Workspace is now cached and ready for compilation![/{Colors.MUTED}]"
            )

        elif result.success:
            # Success but no metadata (shouldn't happen, but handle gracefully)
            console.print(
                f"[{Colors.SUCCESS}]{format_icon_with_message('SUCCESS', 'Workspace created successfully', icon_mode)}[/{Colors.SUCCESS}]"
            )
        else:
            console.print(
                f"[{Colors.ERROR}]Failed to create workspace: {result.error_message}[/{Colors.ERROR}]"
            )
            raise typer.Exit(1)

    except Exception as e:
        logger.error("Failed to create workspace: %s", e)
        console.print(f"[{Colors.ERROR}]Error: {e}[/{Colors.ERROR}]")
        raise typer.Exit(1) from e


@workspace_app.command(name="new")
@with_metrics("workspace_new")
def workspace_new(
    ctx: typer.Context,
    repo_spec: Annotated[
        str,
        typer.Argument(
            help="Repository specification in format 'org/repo@branch' (e.g., 'moergo-sc/zmk@main')"
        ),
    ],
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            "-p",
            help="Keyboard profile for configuration (e.g., 'glove80/v25.05')",
        ),
    ] = None,
    docker_image: Annotated[
        str | None,
        typer.Option(
            "--docker-image",
            help="Docker image to use for workspace creation (overrides profile default)",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force", "-f", help="Force recreation of workspace if it already exists"
        ),
    ] = False,
    progress: Annotated[
        bool,
        typer.Option(
            "--progress/--no-progress", help="Show progress during workspace creation"
        ),
    ] = True,
) -> None:
    """Alias for 'create' - Create a new ZMK workspace from repository specification.

    This is an alias for the 'create' command with identical functionality.
    See 'glovebox cache workspace create --help' for detailed usage.
    """
    # Call the create command with the same context and parameters
    workspace_create(
        ctx=ctx,
        repo_spec=repo_spec,
        profile=profile,
        docker_image=docker_image,
        force=force,
        progress=progress,
    )


@workspace_app.command(name="update")
@with_metrics("workspace_update")
def workspace_update(
    ctx: typer.Context,
    repository: Annotated[
        str,
        typer.Argument(help="Repository name (e.g., 'moergo-sc/zmk')"),
    ],
    branch: Annotated[
        str | None,
        typer.Argument(help="Branch name (required for specific branch updates)"),
    ] = None,
    new_branch: Annotated[
        str | None,
        typer.Option(
            "--new-branch",
            help="Switch to a different branch (updates branch and dependencies)",
        ),
    ] = None,
    dependencies_only: Annotated[
        bool,
        typer.Option(
            "--dependencies-only",
            help="Only update dependencies (west update) without changing branch",
        ),
    ] = False,
    progress: Annotated[
        bool,
        typer.Option(
            "--progress/--no-progress", help="Show progress during workspace update"
        ),
    ] = True,
) -> None:
    """Update existing cached workspace dependencies or switch branches.

    This command can:
    1. Update dependencies only (west update)
    2. Switch to a different branch and update dependencies
    3. Refresh workspace with latest changes

    Examples:
        # Update dependencies for workspace
        glovebox cache workspace update moergo-sc/zmk main --dependencies-only

        # Switch workspace from main to v26.01 branch
        glovebox cache workspace update moergo-sc/zmk main --new-branch v26.01

        # Update dependencies (default behavior)
        glovebox cache workspace update moergo-sc/zmk main
    """
    try:
        # Get session_metrics from context
        session_metrics = getattr(ctx.obj, "session_metrics", None)

        cache_manager, workspace_cache_service, user_config = (
            get_cache_manager_and_service(session_metrics=session_metrics)
        )
        icon_mode = "emoji"

        # Validate arguments
        if not branch and not new_branch:
            console.print(
                format_status_message("Error: Either branch argument or --new-branch option must be provided", "error")
            )
            raise typer.Exit(1)

        if dependencies_only and new_branch:
            console.print(
                format_status_message("Error: Cannot use --dependencies-only with --new-branch", "error")
            )
            raise typer.Exit(1)

        # Setup progress tracking
        start_time = time.time()
        display = None
        progress_coordinator = None

        if progress:
            from glovebox.compilation.simple_progress import (
                ProgressConfig,
                create_simple_compilation_display,
                create_simple_progress_coordinator,
            )

            # Create workspace update configuration
            update_config = ProgressConfig(
                title_processing="↻ Updating Workspace",
                title_complete="✓ Workspace Updated",
                title_failed="✗ Update Failed",
                operation_name="Workspace Update",
                tasks=[
                    "Cache Setup",
                    "Workspace Setup",
                    "Updating Dependencies",
                    "Branch Operations",
                    "Finalizing",
                ],
            )

            display = create_simple_compilation_display(console, update_config)
            progress_coordinator = create_simple_progress_coordinator(display)
            display.start()

        try:
            if new_branch:
                # Switch to new branch
                if not branch:
                    console.print(
                        format_status_message("Error: Branch argument is required when using --new-branch", "error")
                    )
                    raise typer.Exit(1)

                if progress_coordinator:
                    progress_coordinator.transition_to_phase(
                        "branch_update",
                        f"Switching {repository} from {branch} to {new_branch}",
                    )

                result = workspace_cache_service.update_workspace_branch(
                    repository=repository,
                    old_branch=branch,
                    new_branch=new_branch,
                    progress_coordinator=progress_coordinator,
                )

                operation = f"switched to branch {new_branch}"

            else:
                # Update dependencies only
                target_branch = branch

                if progress_coordinator:
                    progress_coordinator.transition_to_phase(
                        "dependencies_update",
                        f"Updating dependencies for {repository}@{target_branch}",
                    )

                result = workspace_cache_service.update_workspace_dependencies(
                    repository=repository,
                    branch=target_branch,
                    progress_coordinator=progress_coordinator,
                )

                operation = "updated dependencies"

            # Mark as completed
            if progress_coordinator:
                if result.success:
                    progress_coordinator.transition_to_phase(
                        "complete", f"Workspace {operation} successfully"
                    )
                else:
                    progress_coordinator.transition_to_phase(
                        "error", f"Workspace update failed: {result.error_message}"
                    )

        finally:
            # Stop display if it was started
            if display is not None:
                display.stop()

        if result.success and result.metadata:
            # Display success information
            end_time = time.time()
            total_time = end_time - start_time
            metadata = result.metadata

            console.print(
                f"[{Colors.SUCCESS}]{format_icon_with_message('SUCCESS', f'Workspace {operation}', icon_mode)}[/{Colors.SUCCESS}]"
            )
            console.print(f"[{Colors.FIELD_NAME}]Repository:[/{Colors.FIELD_NAME}] {metadata.repository}")
            console.print(f"[{Colors.FIELD_NAME}]Branch:[/{Colors.FIELD_NAME}] {metadata.branch}")
            console.print(f"[{Colors.FIELD_NAME}]Cache location:[/{Colors.FIELD_NAME}] {metadata.workspace_path}")

            if metadata.dependencies_updated:
                from datetime import datetime

                time_str = metadata.dependencies_updated.strftime("%Y-%m-%d %H:%M:%S")
                console.print(f"[{Colors.FIELD_NAME}]Dependencies updated:[/{Colors.FIELD_NAME}] {time_str}")

            if metadata.cached_components:
                console.print(
                    f"[{Colors.FIELD_NAME}]Components:[/{Colors.FIELD_NAME}] {', '.join(metadata.cached_components)}"
                )

            console.print(f"[{Colors.FIELD_NAME}]Update time:[/{Colors.FIELD_NAME}] {total_time:.1f}s")

            console.print(
                f"\n[{Colors.MUTED}]Workspace is now updated and ready for compilation![/{Colors.MUTED}]"
            )

        elif result.success:
            # Success but no metadata (shouldn't happen, but handle gracefully)
            console.print(
                f"[{Colors.SUCCESS}]{format_icon_with_message('SUCCESS', f'Workspace {operation}', icon_mode)}[/{Colors.SUCCESS}]"
            )
        else:
            console.print(
                format_status_message(f"Failed to update workspace: {result.error_message}", "error")
            )
            raise typer.Exit(1)

    except Exception as e:
        logger.error("Failed to update workspace: %s", e)
        console.print(format_status_message(f"Error: {e}", "error"))
        raise typer.Exit(1) from e


def register_workspace_commands(app: typer.Typer) -> None:
    """Register workspace commands with the main cache app."""
    app.add_typer(workspace_app, name="workspace")
