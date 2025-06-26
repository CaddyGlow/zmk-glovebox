"""Workspace processing utilities for cache commands."""

import contextlib
import logging
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import typer
from rich.console import Console


logger = logging.getLogger(__name__)


def process_workspace_source(
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
    if parsed_url.scheme in ["http", "https"]:
        workspace_path, temp_dir = download_and_extract_zip(source, progress, console)
        return workspace_path, [temp_dir]

    # Convert to Path for local processing
    source_path = Path(source).resolve()

    # Check if source exists
    if not source_path.exists():
        console.print(f"[red]Source does not exist: {source_path}[/red]")
        raise typer.Exit(1)

    # If it's a directory, validate and return
    if source_path.is_dir():
        return validate_workspace_directory(source_path, console), []

    # If it's a zip file, extract it
    if source_path.suffix.lower() == ".zip":
        workspace_path, temp_dir = extract_local_zip(source_path, progress, console)
        return workspace_path, [temp_dir]

    # Unknown file type
    console.print(f"[red]Unsupported source type: {source_path}[/red]")
    console.print(
        "[dim]Supported sources: directory, .zip file, or URL to .zip file[/dim]"
    )
    raise typer.Exit(1)


def download_and_extract_zip(
    url: str, progress: bool, console: Console
) -> tuple[Path, Path]:
    """Download zip file from URL and extract workspace.

    Args:
        url: URL to zip file
        progress: Whether to show progress bar
        console: Rich console for output

    Returns:
        Path to extracted workspace directory
    """
    from rich.progress import (
        BarColumn,
        DownloadColumn,
        Progress,
        SpinnerColumn,
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
                        # Cloudflare R2 storage is blocking the default User-Agent
                        headers = {"User-Agent": "curl/8.13.0"}
                        request = urllib.request.Request(url=url, headers=headers)
                        with urllib.request.urlopen(request) as response:
                            total_size = int(response.headers.get("content-length", 0))
                            if total_size > 0:
                                progress_bar.update(task_id, total=total_size)

                            downloaded = 0
                            with zip_path.open("wb") as f:
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
        workspace_path = extract_zip_file(zip_path, progress, console)

        # Return both workspace path and temp directory for cleanup
        return workspace_path, temp_dir

    except Exception as e:
        # Cleanup temp directory on error
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def extract_local_zip(
    zip_path: Path, progress: bool, console: Console
) -> tuple[Path, Path]:
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

        workspace_path = extract_zip_file(temp_zip, progress, console)

        # Return both workspace path and temp directory for cleanup
        return workspace_path, temp_dir

    except Exception as e:
        # Cleanup temp directory on error
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def extract_zip_file(zip_path: Path, progress: bool, console: Console) -> Path:
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
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
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
                    task_id = progress_bar.add_task(
                        "Extracting...", total=len(file_list)
                    )

                    for i, file_info in enumerate(zip_ref.infolist()):
                        zip_ref.extract(file_info, extract_dir)
                        progress_bar.update(task_id, completed=i + 1)
            else:
                console.print("[blue]Extracting zip file...[/blue]")
                zip_ref.extractall(extract_dir)

        # Find workspace directory in extracted content
        workspace_path = find_workspace_in_directory(extract_dir, console)
        return workspace_path

    except Exception as e:
        console.print(f"[red]Extraction failed: {e}[/red]")
        shutil.rmtree(extract_dir, ignore_errors=True)
        raise typer.Exit(1) from e


def find_workspace_in_directory(base_dir: Path, console: Console) -> Path:
    """Find workspace directory by checking for ZMK workspace structure.

    Args:
        base_dir: Base directory to search in
        console: Rich console for output

    Returns:
        Path to workspace directory
    """

    def is_workspace_directory(path: Path) -> bool:
        """Check if directory contains ZMK workspace structure."""
        required_dirs = ["zmk", "zephyr", "modules"]
        return all((path / dir_name).is_dir() for dir_name in required_dirs)

    # Check root directory first
    if is_workspace_directory(base_dir):
        return base_dir

    # Check each subdirectory
    for item in base_dir.iterdir():
        if item.is_dir() and is_workspace_directory(item):
            console.print(
                f"[green]Found workspace in subdirectory: {item.name}[/green]"
            )
            return item

    # No workspace found
    console.print("[red]No valid ZMK workspace found in zip file[/red]")
    console.print("[dim]Expected directories: zmk/, zephyr/, modules/[/dim]")
    raise typer.Exit(1)


def validate_workspace_directory(workspace_path: Path, console: Console) -> Path:
    """Validate that directory contains ZMK workspace structure.

    Args:
        workspace_path: Path to workspace directory
        console: Rich console for output

    Returns:
        Validated workspace path
    """
    required_dirs = ["zmk", "zephyr", "modules"]
    missing_dirs = [d for d in required_dirs if not (workspace_path / d).is_dir()]

    if missing_dirs:
        console.print(f"[red]Invalid workspace directory: {workspace_path}[/red]")
        console.print(f"[red]Missing directories: {', '.join(missing_dirs)}[/red]")
        console.print(
            "[dim]Expected ZMK workspace structure: zmk/, zephyr/, modules/[/dim]"
        )
        raise typer.Exit(1)

    return workspace_path


def cleanup_temp_directories(temp_dirs: list[Path]) -> None:
    """Clean up temporary directories with error handling."""
    for temp_dir in temp_dirs:
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.debug("Cleaned up temp directory: %s", temp_dir)
        except Exception as e:
            logger.debug("Failed to cleanup temp directory %s: %s", temp_dir, e)
