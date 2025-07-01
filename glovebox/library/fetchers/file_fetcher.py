"""File fetcher for copying/importing local layout files."""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from glovebox.library.models import FetchResult, LibraryEntry, LibrarySource


logger = logging.getLogger(__name__)


class FileFetcher:
    """Fetcher for local file sources."""

    def can_fetch(self, source: str) -> bool:
        """Check if source is a local file path.

        Args:
            source: Source identifier

        Returns:
            True if source is an existing file
        """
        try:
            path = Path(source.strip()).expanduser()
            return path.is_file() and path.suffix.lower() == ".json"
        except Exception:
            return False

    def get_metadata(self, source: str) -> dict[str, Any] | None:
        """Get metadata from local file.

        Args:
            source: Local file path

        Returns:
            File metadata or None
        """
        try:
            path = Path(source.strip()).expanduser()
            if not path.is_file():
                return None

            stat = path.stat()
            return {
                "file_path": str(path),
                "file_size": stat.st_size,
                "modified_time": datetime.fromtimestamp(stat.st_mtime),
                "file_name": path.name,
            }
        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error(
                "Failed to get file metadata for %s: %s", source, e, exc_info=exc_info
            )
            return None

    def fetch(self, source: str, target_path: Path) -> FetchResult:
        """Copy local file to target path.

        Args:
            source: Local file path
            target_path: Target path to copy file to

        Returns:
            FetchResult with success status and entry
        """
        errors = []
        warnings = []

        try:
            source_path = Path(source.strip()).expanduser()

            # Validate source file
            if not source_path.is_file():
                errors.append(f"Source file does not exist: {source_path}")
                return FetchResult(success=False, errors=errors)

            if source_path.suffix.lower() != ".json":
                warnings.append(
                    f"Source file does not have .json extension: {source_path.suffix}"
                )

            logger.info("Importing layout from %s", source_path)

            # Read and validate JSON
            try:
                content = source_path.read_text(encoding="utf-8")
                layout_data = json.loads(content)
            except json.JSONDecodeError as e:
                errors.append(f"Invalid JSON in source file: {e}")
                return FetchResult(success=False, errors=errors)
            except UnicodeDecodeError as e:
                errors.append(f"Cannot read source file (encoding issue): {e}")
                return FetchResult(success=False, errors=errors)

            # Create target directory
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            shutil.copy2(source_path, target_path)

            # Extract metadata from layout
            title = None
            creator = None
            tags = []
            notes = None

            if isinstance(layout_data, dict):
                title = layout_data.get("title") or layout_data.get("name")
                creator = layout_data.get("creator") or layout_data.get("author")
                tags = layout_data.get("tags", [])
                notes = layout_data.get("notes") or layout_data.get("description")

                # Check for MoErgo metadata
                if "_moergo_meta" in layout_data:
                    meta = layout_data["_moergo_meta"]
                    title = meta.get("title") or title
                    creator = meta.get("creator") or creator
                    tags = meta.get("tags", tags)
                    notes = meta.get("notes") or notes

            # Use filename as fallback for title/name
            if not title:
                title = source_path.stem

            name = (
                title.lower().replace(" ", "-") if title else source_path.stem.lower()
            )

            # Generate a pseudo-UUID from file path and mtime for consistency
            import hashlib

            file_info = f"{source_path}:{source_path.stat().st_mtime}"
            file_hash = hashlib.sha256(file_info.encode()).hexdigest()
            pseudo_uuid = f"{file_hash[:8]}-{file_hash[8:12]}-{file_hash[12:16]}-{file_hash[16:20]}-{file_hash[20:32]}"

            # Create library entry
            entry = LibraryEntry(
                uuid=pseudo_uuid,
                name=name,
                title=title,
                creator=creator,
                source=LibrarySource.LOCAL_FILE,
                source_reference=str(source_path),
                file_path=target_path,
                downloaded_at=datetime.now(),
                tags=tags if isinstance(tags, list) else [],
                notes=notes,
            )

            logger.info(
                "Successfully imported layout '%s' from %s to %s",
                title or name,
                source_path,
                target_path,
            )
            return FetchResult(
                success=True, entry=entry, file_path=target_path, warnings=warnings
            )

        except PermissionError as e:
            error_msg = f"Permission denied accessing file: {e}"
            errors.append(error_msg)
            logger.error("Permission error importing from %s: %s", source, e)
            return FetchResult(success=False, errors=errors)

        except OSError as e:
            error_msg = f"File system error: {e}"
            errors.append(error_msg)
            logger.error("OS error importing from %s: %s", source, e)
            return FetchResult(success=False, errors=errors)

        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            error_msg = f"Failed to import layout from file: {e}"
            errors.append(error_msg)
            logger.error(error_msg, exc_info=exc_info)
            return FetchResult(success=False, errors=errors)


def create_file_fetcher() -> FileFetcher:
    """Factory function to create file fetcher.

    Returns:
        File fetcher instance
    """
    return FileFetcher()
