"""Workspace processing utilities for cache commands."""

import contextlib
import json
import logging
import shutil
import tarfile
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import typer
from rich.console import Console

from glovebox.cli.components.noop_progress_context import get_noop_progress_context


if TYPE_CHECKING:
    from glovebox.compilation.cache.models import (
        ArchiveFormat,
        WorkspaceCacheMetadata,
    )
    from glovebox.core.file_operations import CopyProgressCallback
    from glovebox.protocols.progress_context_protocol import (
        ProgressContextProtocol,
    )


logger = logging.getLogger(__name__)


def process_workspace_source(
    source: str,
    progress: bool = True,
    console: Console | None = None,
    progress_context: "ProgressContextProtocol | None" = None,
) -> tuple[Path, list[Path]]:
    """Process workspace source (directory, zip file, or URL) and return workspace path.

    Args:
        source: Source path, zip file, or URL
        progress: Whether to show progress bars
        console: Rich console for output
        progress_context: Optional progress context for tracking

    Returns:
        Tuple of (workspace_path, temp_dirs_to_cleanup)

    Raises:
        typer.Exit: If processing fails
    """
    if console is None:
        console = Console()

    if progress_context is None:
        progress_context = get_noop_progress_context()

    # Check if it's a URL
    parsed_url = urlparse(source)
    if parsed_url.scheme in ["http", "https"]:
        workspace_path, temp_dir = download_and_extract_zip(
            source, progress, console, progress_context
        )
        # For downloads, we don't track extracted bytes yet, use 0
        return workspace_path, [temp_dir]

    # Convert to Path for local processing
    source_path = Path(source).resolve()

    # Check if source exists
    if not source_path.exists():
        console.print(f"[red]Source does not exist: {source_path}[/red]")
        raise typer.Exit(1)

    # If it's a directory, validate and return
    if source_path.is_dir():
        progress_context.log(f"Validating workspace directory: {source_path}", "info")
        workspace_path = validate_workspace_directory(source_path, console)
        return workspace_path, []

    # If it's a zip file, extract it
    if source_path.suffix.lower() == ".zip":
        workspace_path, temp_dir = extract_local_zip(
            source_path, progress, console, progress_context
        )
        return workspace_path, [temp_dir]

    # Unknown file type
    console.print(f"[red]Unsupported source type: {source_path}[/red]")
    console.print(
        "[dim]Supported sources: directory, .zip file, or URL to .zip file[/dim]"
    )
    raise typer.Exit(1)


def download_and_extract_zip(
    url: str,
    progress: bool,
    console: Console,
    progress_context: "ProgressContextProtocol | None" = None,
) -> tuple[Path, Path]:
    """Download zip file from URL and extract workspace.

    Args:
        url: URL to zip file
        progress: Whether to show progress bar
        console: Rich console for output
        progress_context: Optional progress context for tracking

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
        # Update progress: Completed workspace setup, starting file processing
        # TODO: Enable after refactoring
        # if progress_coordinator and hasattr(
        #     progress_coordinator, "set_enhanced_task_status"
        # ):
        #     progress_coordinator.set_enhanced_task_status(
        #         "Workspace Setup", "completed"
        #     )
        #     progress_coordinator.set_enhanced_task_status(
        #         "Processing Files", "active", f"Downloading from {url}"
        #     )

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

        # Mark download as completed
        # TODO: Enable after refactoring
        # if progress_coordinator and hasattr(
        #     progress_coordinator, "set_enhanced_task_status"
        # ):
        #     progress_coordinator.set_enhanced_task_status("download", "completed")

        # Extract the downloaded zip
        workspace_path = extract_zip_file(
            zip_path, progress, console, progress_context
        )

        # Return both workspace path and temp directory for cleanup
        return workspace_path, temp_dir

    except Exception as e:
        # Mark download as failed
        # TODO: Enable after refactoring
        # if progress_coordinator and hasattr(
        #     progress_coordinator, "set_enhanced_task_status"
        # ):
        #     progress_coordinator.set_enhanced_task_status("download", "failed")
        # Cleanup temp directory on error
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def extract_local_zip(
    zip_path: Path,
    progress: bool,
    console: Console,
    progress_context: "ProgressContextProtocol | None" = None,
) -> tuple[Path, Path]:
    """Extract local zip file to temporary directory.

    Args:
        zip_path: Path to local zip file
        progress: Whether to show progress bar
        console: Rich console for output
        progress_context: Optional progress context for enhanced tracking

    Returns:
        Path to extracted workspace directory
    """
    if not zipfile.is_zipfile(zip_path):
        console.print(f"[red]Invalid zip file: {zip_path}[/red]")
        raise typer.Exit(1)

    temp_dir = Path(tempfile.mkdtemp(prefix="glovebox_local_zip_"))

    try:
        # Update progress: Completed workspace setup, starting file processing
        # TODO: Enable after refactoring
        # if progress_coordinator and hasattr(
        #     progress_coordinator, "set_enhanced_task_status"
        # ):
        #     progress_coordinator.set_enhanced_task_status(
        #         "Workspace Setup", "completed"
        #     )
        #     progress_coordinator.set_enhanced_task_status(
        #         "Processing Files", "active", f"Extracting zip file {zip_path.name}"
        #     )

        # Copy zip to temp directory for extraction
        temp_zip = temp_dir / zip_path.name
        shutil.copy2(zip_path, temp_zip)

        workspace_path = extract_zip_file(temp_zip, progress, console, progress_context)

        # Return both workspace path and temp directory for cleanup
        return workspace_path, temp_dir

    except Exception as e:
        # Cleanup temp directory on error
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def extract_zip_file(
    zip_path: Path,
    progress: bool,
    console: Console,
    progress_context: "ProgressContextProtocol | None" = None,
) -> Path:
    """Extract zip file and find workspace directory with enhanced progress tracking.

    Args:
        zip_path: Path to zip file
        progress: Whether to show progress bar
        console: Rich console for output
        progress_context: Optional progress context for tracking

    Returns:
        Path to workspace directory
    """
    import time

    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
    )

    if progress_context is None:
        progress_context = get_noop_progress_context()

    extract_dir = zip_path.parent / "extracted"
    extract_dir.mkdir(exist_ok=True)

    try:
        progress_context.start_checkpoint("Extracting Files")
        progress_context.log(f"Extracting {zip_path.name}...", "info")
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            file_list = zip_ref.namelist()

            # Calculate total uncompressed size for byte-level progress
            total_uncompressed_size = sum(info.file_size for info in zip_ref.infolist())
            archive_name = zip_path.name

            # Set ZIP extraction task as active if coordinator available
            # TODO: Enable after refactoring
            # if progress_coordinator and hasattr(
            #     progress_coordinator, "set_enhanced_task_status"
            # ):
            #     progress_coordinator.set_enhanced_task_status(
            #         "Extracting Files", "active", "Extracting ZIP archive"
            #     )

            # Enhanced extraction with byte-level tracking - only use coordinator, no separate progress bar
            extracted_bytes = 0
            start_time = time.time()

            for i, file_info in enumerate(zip_ref.infolist()):
                # Extract file
                zip_ref.extract(file_info, extract_dir)
                extracted_bytes += file_info.file_size

                # Calculate extraction speed
                elapsed_time = time.time() - start_time
                extraction_speed_mb_s = 0.0
                eta_seconds = 0.0

                if elapsed_time > 0 and extracted_bytes > 0:
                    extraction_speed_mb_s = (
                        extracted_bytes / (1024 * 1024)
                    ) / elapsed_time

                    if extraction_speed_mb_s > 0:
                        remaining_bytes = total_uncompressed_size - extracted_bytes
                        eta_seconds = remaining_bytes / (
                            extraction_speed_mb_s * 1024 * 1024
                        )

                # Update progress every 10 files or for last file to avoid too many updates
                if (i + 1) % 10 == 0 or (i + 1) == len(file_list):
                    progress_context.update_progress(
                        current=extracted_bytes,
                        total=total_uncompressed_size,
                        status=f"Extracting {file_info.filename}",
                    )

                    # Update status info with extraction details
                    progress_context.set_status_info(
                        {
                            "current_file": file_info.filename,
                            "transfer_speed": extraction_speed_mb_s,
                            "eta_seconds": eta_seconds,
                            "files_remaining": len(file_list) - (i + 1),
                        }
                    )

        # Complete extraction checkpoint
        progress_context.complete_checkpoint("Extracting Files")
        progress_context.log(
            f"Extracted {len(file_list)} files from {archive_name}", "info"
        )

        # Find workspace directory in extracted content
        workspace_path = find_workspace_in_directory(extract_dir, console)

        return workspace_path

    except Exception as e:
        # Mark ZIP extraction as failed
        # TODO: Enable after refactoring
        # if progress_coordinator and hasattr(
        #     progress_coordinator, "set_enhanced_task_status"
        # ):
        #     progress_coordinator.set_enhanced_task_status("Extracting Files", "failed")
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


def create_zip_archive(
    workspace_path: Path,
    output_path: Path,
    compression_level: int,
    include_git: bool,
    metadata: "WorkspaceCacheMetadata",
    progress_callback: "CopyProgressCallback | None" = None,
    progress_context: "ProgressContextProtocol | None" = None,
) -> None:
    """Create ZIP archive from workspace directory.

    Args:
        workspace_path: Path to workspace directory to archive
        output_path: Path for output archive file
        compression_level: Compression level (0-9)
        include_git: Whether to include .git folders
        metadata: Workspace metadata to include in archive
        progress_callback: Optional progress callback
        progress_context: Optional progress context
    """
    # Calculate total files for progress tracking
    total_files = sum(
        1
        for file_path in workspace_path.rglob("*")
        if file_path.is_file() and (include_git or ".git" not in file_path.parts)
    )

    processed_files = 0
    start_time = time.time()

    with zipfile.ZipFile(
        output_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=compression_level,
    ) as zipf:
        # Add workspace metadata as JSON
        metadata_json = json.dumps(metadata.model_dump(mode="json"), indent=2)
        zipf.writestr(".glovebox_export_metadata.json", metadata_json)

        # Add all workspace files
        for file_path in workspace_path.rglob("*"):
            if file_path.is_file():
                # Skip .git files if not included
                if not include_git and ".git" in file_path.parts:
                    continue

                # Calculate relative path for archive
                rel_path = file_path.relative_to(workspace_path)
                archive_path = f"workspace/{rel_path}"

                # Add file to zip
                zipf.write(file_path, archive_path)
                processed_files += 1

                # Update progress
                # TODO: Enable after refactoring
                # if progress_coordinator and hasattr(
                #     progress_coordinator, "update_export_progress"
                # ):
                #     elapsed = time.time() - start_time
                #     speed_mb_s = 0.0
                #     eta_seconds = 0.0
                #
                #     if elapsed > 0 and processed_files > 0:
                #         files_per_second = processed_files / elapsed
                #         if files_per_second > 0:
                #             eta_seconds = (
                #                 total_files - processed_files
                #             ) / files_per_second
                #
                #     progress_coordinator.update_export_progress(
                #         files_processed=processed_files,
                #         total_files=total_files,
                #         current_file=str(rel_path),
                #         archive_format="zip",
                #         compression_level=compression_level,
                #         speed_mb_s=speed_mb_s,
                #         eta_seconds=eta_seconds,
                #     )


def create_tar_archive(
    workspace_path: Path,
    output_path: Path,
    archive_format: "ArchiveFormat",
    compression_level: int,
    include_git: bool,
    metadata: "WorkspaceCacheMetadata",
    progress_callback: "CopyProgressCallback | None" = None,
    progress_context: "ProgressContextProtocol | None" = None,
) -> None:
    """Create TAR archive from workspace directory.

    Args:
        workspace_path: Path to workspace directory to archive
        output_path: Path for output archive file
        archive_format: Archive format (TAR, TAR_GZ, TAR_BZ2, TAR_XZ)
        compression_level: Compression level (0-9)
        include_git: Whether to include .git folders
        metadata: Workspace metadata to include in archive
        progress_callback: Optional progress callback
        progress_context: Optional progress context
    """
    # Map archive format to tarfile mode
    mode_map = {
        "tar": "w",
        "tar.gz": "w:gz",
        "tar.bz2": "w:bz2",
        "tar.xz": "w:xz",
    }

    mode: str = mode_map.get(archive_format.value, "w")

    # Calculate total files for progress tracking
    total_files = sum(
        1
        for file_path in workspace_path.rglob("*")
        if file_path.is_file() and (include_git or ".git" not in file_path.parts)
    )

    processed_files = 0
    start_time = time.time()

    with tarfile.open(output_path, mode=mode) as tar:  # type: ignore[call-overload]
        # Add workspace metadata as JSON
        metadata_json = json.dumps(metadata.model_dump(mode="json"), indent=2)
        metadata_bytes = metadata_json.encode("utf-8")

        # Create tarinfo for metadata file
        metadata_info = tarfile.TarInfo(name=".glovebox_export_metadata.json")
        metadata_info.size = len(metadata_bytes)
        metadata_info.mtime = int(time.time())

        import io

        tar.addfile(metadata_info, io.BytesIO(metadata_bytes))

        # Add all workspace files
        for file_path in workspace_path.rglob("*"):
            if file_path.is_file():
                # Skip .git files if not included
                if not include_git and ".git" in file_path.parts:
                    continue

                # Calculate relative path for archive
                rel_path = file_path.relative_to(workspace_path)
                archive_path = f"workspace/{rel_path}"

                # Add file to tar with custom arcname
                tar.add(file_path, arcname=archive_path)
                processed_files += 1

                # Update progress
                # TODO: Enable after refactoring
                # if progress_coordinator and hasattr(
                #     progress_coordinator, "update_export_progress"
                # ):
                #     elapsed = time.time() - start_time
                #     speed_mb_s = 0.0
                #     eta_seconds = 0.0
                #
                #     if elapsed > 0 and processed_files > 0:
                #         files_per_second = processed_files / elapsed
                #         if files_per_second > 0:
                #             eta_seconds = (
                #                 total_files - processed_files
                #             ) / files_per_second
                #
                #     progress_coordinator.update_export_progress(
                #         files_processed=processed_files,
                #         total_files=total_files,
                #         current_file=str(rel_path),
                #         archive_format=archive_format.value,
                #         compression_level=compression_level,
                #         speed_mb_s=speed_mb_s,
                #         eta_seconds=eta_seconds,
                #     )
