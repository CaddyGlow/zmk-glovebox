"""Cache management CLI commands."""

import contextlib
import logging
import shutil
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlparse

import typer
from rich.console import Console
from rich.table import Table

from glovebox.cli.helpers.theme import Icons
from glovebox.cli.workspace_display_utils import (
    filter_workspaces,
    format_size,
    format_workspace_entry,
    generate_workspace_cache_key,
    get_directory_size,
    get_workspace_summary,
)
from glovebox.compilation.cache import (
    ZmkWorkspaceCacheService,
    create_compilation_cache_service,
)
from glovebox.config.user_config import UserConfig, create_user_config
from glovebox.core.cache.cache_manager import CacheManager


logger = logging.getLogger(__name__)
console = Console()

cache_app = typer.Typer(help="Cache management commands")
workspace_app = typer.Typer(help="Workspace cache management")
cache_app.add_typer(workspace_app, name="workspace")


# Utility functions are now imported from workspace_display_utils
# Keeping backward compatibility aliases
def _format_size(size_bytes: float) -> str:
    """Format size in human readable format (backward compatibility alias)."""
    return format_size(size_bytes)


def _get_directory_size(path: Path) -> int:
    """Get total size of directory in bytes (backward compatibility alias)."""
    return get_directory_size(path)


def _get_cache_manager_and_service(
    session_metrics: Any = None,
) -> tuple[CacheManager, ZmkWorkspaceCacheService, UserConfig]:
    """Get cache manager and workspace cache service using factory functions."""
    user_config = create_user_config()
    cache_manager, workspace_cache_service, _ = create_compilation_cache_service(
        user_config, session_metrics=session_metrics
    )
    return cache_manager, workspace_cache_service, user_config


def _get_cache_manager() -> CacheManager:
    """Get cache manager using user config (backward compatibility)."""
    cache_manager, _, _ = _get_cache_manager_and_service()
    return cache_manager


def _process_workspace_source(
    source: str, progress: bool = True, console: Console | None = None
) -> tuple[Path, list[Path]]:
    """Process workspace source (directory, zip file, or URL) and return workspace path.

    Args:
        source: Source path, zip file, or URL
        progress: Whether to show progress bars
        console: Rich console for output

    Returns:
        Tuple of (workspace_path, temp_dirs_to_cleanup)

    Raises:
        typer.Exit: If processing fails
    """
    if console is None:
        console = Console()

    # Check if it's a URL
    parsed_url = urlparse(source)
    if parsed_url.scheme in ['http', 'https']:
        workspace_path, temp_dir = _download_and_extract_zip(source, progress, console)
        return workspace_path, [temp_dir]

    # Convert to Path for local processing
    source_path = Path(source).resolve()

    # Check if source exists
    if not source_path.exists():
        console.print(f"[red]Source does not exist: {source_path}[/red]")
        raise typer.Exit(1)

    # If it's a directory, validate and return
    if source_path.is_dir():
        return _validate_workspace_directory(source_path, console), []

    # If it's a zip file, extract it
    if source_path.suffix.lower() == '.zip':
        workspace_path, temp_dir = _extract_local_zip(source_path, progress, console)
        return workspace_path, [temp_dir]

    # Unknown file type
    console.print(f"[red]Unsupported source type: {source_path}[/red]")
    console.print("[dim]Supported sources: directory, .zip file, or URL to .zip file[/dim]")
    raise typer.Exit(1)


def _download_and_extract_zip(url: str, progress: bool, console: Console) -> tuple[Path, Path]:
    """Download zip file from URL and extract workspace.

    Args:
        url: URL to zip file
        progress: Whether to show progress bar
        console: Rich console for output

    Returns:
        Path to extracted workspace directory
    """
    import queue
    import threading

    from rich.progress import (
        BarColumn,
        DownloadColumn,
        Progress,
        SpinnerColumn,
        TaskID,
        TimeRemainingColumn,
        TransferSpeedColumn,
    )

    temp_dir = Path(tempfile.mkdtemp(prefix="glovebox_workspace_"))
    zip_path = temp_dir / "workspace.zip"

    try:
        if progress:
            # Create progress bar for download
            progress_bar = Progress(
                SpinnerColumn(),
                "[progress.description]{task.description}",
                BarColumn(),
                DownloadColumn(),
                "•",
                TransferSpeedColumn(),
                "•",
                TimeRemainingColumn(),
                console=console,
                transient=True,
            )

            with progress_bar:
                task_id = progress_bar.add_task("Downloading...", total=None)

                def download_with_progress() -> None:
                    """Download file with progress updates."""
                    try:
                        with urllib.request.urlopen(url) as response:
                            total_size = int(response.headers.get('content-length', 0))
                            if total_size > 0:
                                progress_bar.update(task_id, total=total_size)

                            downloaded = 0
                            with zip_path.open('wb') as f:
                                while True:
                                    chunk = response.read(8192)
                                    if not chunk:
                                        break
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    progress_bar.update(task_id, completed=downloaded)
                    except Exception as e:
                        console.print(f"[red]Download failed: {e}[/red]")
                        raise typer.Exit(1) from e

                download_with_progress()
        else:
            # Simple download without progress
            console.print(f"[blue]Downloading: {url}[/blue]")
            try:
                urllib.request.urlretrieve(url, zip_path)
            except Exception as e:
                console.print(f"[red]Download failed: {e}[/red]")
                raise typer.Exit(1) from e

        # Extract the downloaded zip
        workspace_path = _extract_zip_file(zip_path, progress, console)

        # Return both workspace path and temp directory for cleanup
        return workspace_path, temp_dir

    except Exception as e:
        # Cleanup temp directory on error
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def _extract_local_zip(zip_path: Path, progress: bool, console: Console) -> tuple[Path, Path]:
    """Extract local zip file to temporary directory.

    Args:
        zip_path: Path to local zip file
        progress: Whether to show progress bar
        console: Rich console for output

    Returns:
        Path to extracted workspace directory
    """
    if not zipfile.is_zipfile(zip_path):
        console.print(f"[red]Invalid zip file: {zip_path}[/red]")
        raise typer.Exit(1)

    temp_dir = Path(tempfile.mkdtemp(prefix="glovebox_local_zip_"))

    try:
        # Copy zip to temp directory for extraction
        temp_zip = temp_dir / zip_path.name
        shutil.copy2(zip_path, temp_zip)

        workspace_path = _extract_zip_file(temp_zip, progress, console)

        # Return both workspace path and temp directory for cleanup
        return workspace_path, temp_dir

    except Exception as e:
        # Cleanup temp directory on error
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def _extract_zip_file(zip_path: Path, progress: bool, console: Console) -> Path:
    """Extract zip file and find workspace directory.

    Args:
        zip_path: Path to zip file
        progress: Whether to show progress bar
        console: Rich console for output

    Returns:
        Path to workspace directory
    """
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
    )

    extract_dir = zip_path.parent / "extracted"
    extract_dir.mkdir(exist_ok=True)

    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            file_list = zip_ref.namelist()

            if progress:
                progress_bar = Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    console=console,
                    transient=True,
                )

                with progress_bar:
                    task_id = progress_bar.add_task("Extracting...", total=len(file_list))

                    for i, file_info in enumerate(zip_ref.infolist()):
                        zip_ref.extract(file_info, extract_dir)
                        progress_bar.update(task_id, completed=i + 1)
            else:
                console.print("[blue]Extracting zip file...[/blue]")
                zip_ref.extractall(extract_dir)

        # Find workspace directory in extracted content
        workspace_path = _find_workspace_in_directory(extract_dir, console)
        return workspace_path

    except Exception as e:
        console.print(f"[red]Extraction failed: {e}[/red]")
        shutil.rmtree(extract_dir, ignore_errors=True)
        raise typer.Exit(1) from e


def _find_workspace_in_directory(base_dir: Path, console: Console) -> Path:
    """Find workspace directory by checking for ZMK workspace structure.

    Args:
        base_dir: Base directory to search in
        console: Rich console for output

    Returns:
        Path to workspace directory
    """
    def is_workspace_directory(path: Path) -> bool:
        """Check if directory contains ZMK workspace structure."""
        required_dirs = ['zmk', 'zephyr', 'modules']
        return all((path / dir_name).is_dir() for dir_name in required_dirs)

    # Check root directory first
    if is_workspace_directory(base_dir):
        return base_dir

    # Check each subdirectory
    for item in base_dir.iterdir():
        if item.is_dir() and is_workspace_directory(item):
            console.print(f"[green]Found workspace in subdirectory: {item.name}[/green]")
            return item

    # No workspace found
    console.print("[red]No valid ZMK workspace found in zip file[/red]")
    console.print("[dim]Expected directories: zmk/, zephyr/, modules/[/dim]")
    raise typer.Exit(1)


def _validate_workspace_directory(workspace_path: Path, console: Console) -> Path:
    """Validate that directory contains ZMK workspace structure.

    Args:
        workspace_path: Path to workspace directory
        console: Rich console for output

    Returns:
        Validated workspace path
    """
    required_dirs = ['zmk', 'zephyr', 'modules']
    missing_dirs = [d for d in required_dirs if not (workspace_path / d).is_dir()]

    if missing_dirs:
        console.print(f"[red]Invalid workspace directory: {workspace_path}[/red]")
        console.print(f"[red]Missing directories: {', '.join(missing_dirs)}[/red]")
        console.print("[dim]Expected ZMK workspace structure: zmk/, zephyr/, modules/[/dim]")
        raise typer.Exit(1)

    return workspace_path


def _show_cache_entries_by_level(
    cache_manager: CacheManager,
    workspace_cache_service: ZmkWorkspaceCacheService,
    user_config: UserConfig,
    json_output: bool = False,
) -> None:
    """Show all cache entries grouped by cache level with TTL information."""
    import json
    from datetime import datetime

    # Use utility functions from workspace display utils
    # These are now imported at the top of the file

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
                        # Try to auto-detect from git info (simplified fallback)
                        repo = "unknown"
                        branch = "main"
                        try:
                            if (actual_path / ".git").exists():
                                repo = "auto-detected"  # Simplified fallback
                        except Exception:
                            pass
                        git_info = {"repository": repo, "branch": branch}
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
                            size_bytes = get_directory_size(workspace_path)
                            size_display = format_size(size_bytes)
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
                    # Simple fallback for missing metadata (git info detection removed)
                    repo = "auto-detected"
                    branch = "main"
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
    entries: Annotated[
        bool,
        typer.Option("--entries", help="Show entries grouped by cache level"),
    ] = False,
) -> None:
    """Show all cached ZMK workspace entries including orphaned directories."""
    try:
        cache_manager, workspace_cache_service, user_config = (
            _get_cache_manager_and_service()
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
                                                    size_str = _format_size(
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

                            for cache_dir in sorted(cache_subdirs)[start_idx:end_idx]:
                                module_name = cache_dir.name
                                size = _get_directory_size(cache_dir)
                                file_count = len(list(cache_dir.rglob("*")))

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


@workspace_app.command(name="add")
def workspace_add(
    workspace_source: Annotated[
        str,
        typer.Argument(help="Path to ZMK workspace directory, zip file, or URL to zip file"),
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
            _get_cache_manager_and_service()
        )
        icon_mode = "emoji"  # Default icon mode

        # Determine source type and process accordingly
        workspace_path, temp_cleanup_dirs = _process_workspace_source(
            workspace_source, progress=progress, console=console
        )

        # Use the new workspace cache service for adding external workspace
        if not repository:
            typer.echo(
                "Error: Repository must be specified when injecting workspace", err=True
            )
            raise typer.Exit(1)

        # Setup progress tracking using the new reusable TUI component
        import time

        start_time = time.time()
        progress_callback = None

        if progress:
            from glovebox.cli.components.progress_display import (
                create_workspace_progress_display,
            )

            # Create workspace progress display using the reusable TUI component
            progress_callback = create_workspace_progress_display(show_logs=False)

        try:
            result = workspace_cache_service.inject_existing_workspace(
                workspace_path=workspace_path,
                repository=repository,
                progress_callback=progress_callback,
            )
        finally:
            # Clean up progress display if it was used
            if progress_callback and hasattr(progress_callback, "cleanup"):
                progress_callback.cleanup()

            # Cleanup temporary directories from zip extraction
            for temp_dir in temp_cleanup_dirs:
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    logger.debug("Cleaned up temp directory: %s", temp_dir)
                except Exception as e:
                    logger.debug("Failed to cleanup temp directory %s: %s", temp_dir, e)

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
                    f"{_format_size(metadata.size_bytes)} copied in "
                    f"{total_time:.1f}s at {avg_speed_mbps:.1f} MB/s"
                )
                console.print()  # Extra spacing

            console.print(
                f"[green]{Icons.format_with_icon('SUCCESS', 'Successfully added workspace cache', icon_mode)}[/green]"
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
        # Cleanup temporary directories on error
        if 'temp_cleanup_dirs' in locals():
            for temp_dir in temp_cleanup_dirs:
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    logger.debug("Cleaned up temp directory after error: %s", temp_dir)
                except Exception as cleanup_e:
                    logger.debug("Failed to cleanup temp directory %s: %s", temp_dir, cleanup_e)

        logger.error("Failed to add workspace to cache: %s", e)
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e


@cache_app.command(name="keys")
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
    import json
    from datetime import datetime

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
                                                _format_size(key_metadata.size_bytes),
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
                        cache_keys = module_cache.keys()

                        # Apply pattern filtering
                        if pattern:
                            cache_keys = [
                                key
                                for key in cache_keys
                                if pattern.lower() in key.lower()
                            ]

                        all_modules_data["modules"][module_name] = {
                            "total_keys": len(cache_keys),
                            "keys": sorted(cache_keys),
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
                        cache_keys = module_cache.keys()

                        # Apply pattern filtering
                        if pattern:
                            cache_keys = [
                                key
                                for key in cache_keys
                                if pattern.lower() in key.lower()
                            ]

                        console.print(
                            f"\n[bold cyan]📦 {module_name}[/bold cyan] ({len(cache_keys)} keys)"
                        )

                        if cache_keys:
                            if limit:
                                display_keys = cache_keys[:limit]
                            else:
                                display_keys = cache_keys

                            for key in sorted(display_keys):
                                console.print(f"  • {key}")

                            if limit and len(cache_keys) > limit:
                                console.print(
                                    f"  [dim]... and {len(cache_keys) - limit} more keys[/dim]"
                                )
                        else:
                            if pattern:
                                console.print(
                                    f"  [dim]No keys matching pattern '{pattern}'[/dim]"
                                )
                            else:
                                console.print("  [dim]No keys found[/dim]")

                        total_keys += len(cache_keys)

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


@cache_app.command(name="delete")
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
    import json

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

            # For compilation module, provide safety check to prevent workspace deletion
            if module == "compilation" and pattern.lower() in ["compilation_build", "build"]:
                # Filter out workspace keys to prevent accidental deletion
                workspace_prefixes = ["workspace_repo_", "workspace_repo_branch_"]
                original_count = len(keys_to_delete)
                keys_to_delete = [
                    k for k in keys_to_delete
                    if not any(k.startswith(prefix) for prefix in workspace_prefixes)
                ]
                filtered_count = original_count - len(keys_to_delete)
                if filtered_count > 0:
                    console.print(f"[yellow]Filtered out {filtered_count} workspace cache keys for safety[/yellow]")
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
                f"[green]{Icons.get_icon('SUCCESS', icon_mode)} Deleted all {deleted_count} cache keys from '{module}'[/green]"
            )
        elif deleted_count > 0:
            console.print(
                f"[green]{Icons.get_icon('SUCCESS', icon_mode)} Deleted {deleted_count}/{len(keys_to_delete)} cache keys from '{module}'[/green]"
            )
            console.print(
                f"[yellow]{len(keys_to_delete) - deleted_count} keys were not found[/yellow]"
            )
        else:
            console.print(
                f"[yellow]No keys were deleted (all {len(keys_to_delete)} keys not found)[/yellow]"
            )

    except Exception as e:
        exc_info = logger.isEnabledFor(logging.DEBUG)
        logger.error("Failed to delete cache keys: %s", e, exc_info=exc_info)
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
    and age-based cleanup using the cache system.
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
                # Clear the specific module's cache instance
                from glovebox.core.cache import create_default_cache

                module_cache = create_default_cache(tag=module)
                module_cache.clear()

                # Also remove the filesystem directory to ensure complete cleanup
                shutil.rmtree(module_cache_dir)

                icon_mode = "emoji"
                console.print(
                    f"[green]{Icons.get_icon('SUCCESS', icon_mode)} Cleared cache for module '{module}'[/green]"
                )
            except Exception as e:
                console.print(f"[red]Failed to clear module cache: {e}[/red]")
                raise typer.Exit(1) from e

        elif max_age_days is not None:
            # Age-based cleanup using cache system
            try:
                cache_manager = _get_cache_manager()
                cache_stats = cache_manager.get_stats()

                console.print(
                    f"[blue]Cleaning up cache entries older than {max_age_days} days...[/blue]"
                )

                # Use cache's built-in cleanup if available
                if hasattr(cache_manager, "cleanup"):
                    cache_manager.cleanup()

                icon_mode = "emoji"
                console.print(
                    Icons.format_with_icon(
                        "SUCCESS",
                        "Cache cleanup completed using cache system.",
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
                # Clear all module-specific cache instances
                from glovebox.core.cache import (
                    create_default_cache,
                    reset_shared_cache_instances,
                )

                cleared_modules = []
                for cache_dir in cache_subdirs:
                    module_name = cache_dir.name
                    try:
                        # Clear the cache instance for this module
                        module_cache = create_default_cache(tag=module_name)
                        module_cache.clear()
                        cleared_modules.append(module_name)
                    except Exception as e:
                        logger.warning(
                            "Failed to clear cache instance for module '%s': %s",
                            module_name,
                            e,
                        )

                # Reset shared cache coordination to clean up instance registry
                reset_shared_cache_instances()

                # Clear filesystem directories
                for cache_dir in cache_subdirs:
                    shutil.rmtree(cache_dir)

                icon_mode = "emoji"
                console.print(
                    f"[green]{Icons.get_icon('SUCCESS', icon_mode)} Cleared all cache directories ({_format_size(total_size)})[/green]"
                )
                if cleared_modules:
                    console.print(
                        f"[green]Cleared cache instances for modules: {', '.join(cleared_modules)}[/green]"
                    )
                console.print("[green]Reset shared cache coordination[/green]")
            except Exception as e:
                console.print(f"[red]Failed to clear cache: {e}[/red]")
                raise typer.Exit(1) from e

    except Exception as e:
        logger.error("Failed to clear cache: %s", e)

        icon_mode = "emoji"
        typer.echo(Icons.format_with_icon("ERROR", f"Error: {e}", icon_mode), err=True)
        raise typer.Exit(1) from e
