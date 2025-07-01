"""Library repository for managing layout storage and indexing."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from glovebox.library.models import LibraryEntry, LibrarySource


logger = logging.getLogger(__name__)


class LibraryRepository:
    """Repository for managing layout library storage and indexing."""

    def __init__(self, library_path: Path) -> None:
        """Initialize repository with library path.

        Args:
            library_path: Base path for library storage
        """
        self.library_path = library_path
        self.layouts_path = library_path / "layouts"
        self.metadata_path = library_path / "metadata"
        self.index_path = library_path / "index.yaml"

        # Ensure directories exist
        self.layouts_path.mkdir(parents=True, exist_ok=True)
        self.metadata_path.mkdir(parents=True, exist_ok=True)

        # Load or create index
        self._index: dict[str, dict[str, Any]] = self._load_index()

    def _load_index(self) -> dict[str, dict[str, Any]]:
        """Load library index from file.

        Returns:
            Index dictionary mapping UUIDs to entry metadata
        """
        if not self.index_path.exists():
            logger.debug("No index file found, creating new index")
            return {}

        try:
            with self.index_path.open("r", encoding="utf-8") as f:
                index_data = yaml.safe_load(f) or {}
                logger.debug("Loaded index with %d entries", len(index_data))
                return index_data
        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error(
                "Failed to load index file, creating new index: %s",
                e,
                exc_info=exc_info,
            )
            return {}

    def _save_index(self) -> None:
        """Save library index to file."""
        try:
            with self.index_path.open("w", encoding="utf-8") as f:
                yaml.safe_dump(self._index, f, default_flow_style=False, sort_keys=True)
            logger.debug("Saved index with %d entries", len(self._index))
        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error("Failed to save index file: %s", e, exc_info=exc_info)

    def _generate_layout_filename(self, entry: LibraryEntry) -> str:
        """Generate filename for layout file.

        Args:
            entry: Library entry

        Returns:
            Filename for the layout file
        """
        # Use UUID as base filename for uniqueness
        safe_name = entry.name.replace("/", "_").replace("\\", "_")
        return f"{entry.uuid}_{safe_name}.json"

    def _entry_to_index_data(self, entry: LibraryEntry) -> dict[str, Any]:
        """Convert library entry to index data.

        Args:
            entry: Library entry

        Returns:
            Index data dictionary
        """
        return {
            "uuid": entry.uuid,
            "name": entry.name,
            "title": entry.title,
            "creator": entry.creator,
            "source": entry.source.value,
            "source_reference": entry.source_reference,
            "file_path": str(entry.file_path),
            "downloaded_at": entry.downloaded_at.isoformat(),
            "tags": entry.tags,
            "notes": entry.notes,
        }

    def _index_data_to_entry(self, data: dict[str, Any]) -> LibraryEntry:
        """Convert index data to library entry.

        Args:
            data: Index data dictionary

        Returns:
            Library entry
        """
        return LibraryEntry(
            uuid=data["uuid"],
            name=data["name"],
            title=data.get("title"),
            creator=data.get("creator"),
            source=LibrarySource(data["source"]),
            source_reference=data["source_reference"],
            file_path=Path(data["file_path"]),
            downloaded_at=datetime.fromisoformat(data["downloaded_at"]),
            tags=data.get("tags", []),
            notes=data.get("notes"),
        )

    def store_layout(
        self, content: dict[str, Any], entry: LibraryEntry
    ) -> LibraryEntry:
        """Store layout content and create index entry.

        Args:
            content: Layout content dictionary
            entry: Library entry metadata

        Returns:
            Updated library entry with actual file path

        Raises:
            OSError: If storage operation fails
        """
        try:
            # Generate filename and path
            filename = self._generate_layout_filename(entry)
            layout_file_path = self.layouts_path / filename

            # Update entry with actual file path
            updated_entry = entry.model_copy(update={"file_path": layout_file_path})

            # Write layout content
            layout_json = json.dumps(content, indent=2, ensure_ascii=False)
            layout_file_path.write_text(layout_json, encoding="utf-8")

            # Update index
            self._index[entry.uuid] = self._entry_to_index_data(updated_entry)
            self._save_index()

            logger.info(
                "Stored layout '%s' (UUID: %s) to %s",
                entry.title or entry.name,
                entry.uuid,
                layout_file_path,
            )
            return updated_entry

        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error(
                "Failed to store layout %s: %s", entry.uuid, e, exc_info=exc_info
            )
            raise

    def get_entry(self, uuid: str) -> LibraryEntry | None:
        """Get library entry by UUID.

        Args:
            uuid: Layout UUID

        Returns:
            Library entry or None if not found
        """
        index_data = self._index.get(uuid)
        if index_data is None:
            return None

        try:
            return self._index_data_to_entry(index_data)
        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error(
                "Failed to reconstruct entry for %s: %s", uuid, e, exc_info=exc_info
            )
            return None

    def get_entry_by_name(self, name: str) -> LibraryEntry | None:
        """Get library entry by name.

        Args:
            name: Layout name

        Returns:
            Library entry or None if not found
        """
        for index_data in self._index.values():
            if index_data.get("name") == name:
                try:
                    return self._index_data_to_entry(index_data)
                except Exception as e:
                    exc_info = logger.isEnabledFor(logging.DEBUG)
                    logger.error(
                        "Failed to reconstruct entry for name %s: %s",
                        name,
                        e,
                        exc_info=exc_info,
                    )
                    continue
        return None

    def list_entries(
        self,
        source_filter: LibrarySource | None = None,
        tag_filter: list[str] | None = None,
    ) -> list[LibraryEntry]:
        """List all library entries with optional filtering.

        Args:
            source_filter: Filter by source type
            tag_filter: Filter by tags (entry must have all specified tags)

        Returns:
            List of library entries
        """
        entries = []

        for index_data in self._index.values():
            try:
                # Apply source filter
                if (
                    source_filter is not None
                    and index_data.get("source") != source_filter.value
                ):
                    continue

                # Apply tag filter
                if tag_filter is not None:
                    entry_tags = set(index_data.get("tags", []))
                    required_tags = set(tag_filter)
                    if not required_tags.issubset(entry_tags):
                        continue

                entry = self._index_data_to_entry(index_data)
                entries.append(entry)

            except Exception as e:
                exc_info = logger.isEnabledFor(logging.DEBUG)
                logger.error("Failed to reconstruct entry: %s", e, exc_info=exc_info)
                continue

        # Sort by downloaded date (newest first)
        entries.sort(key=lambda e: e.downloaded_at, reverse=True)
        return entries

    def remove_entry(self, uuid: str) -> bool:
        """Remove library entry and associated files.

        Args:
            uuid: Layout UUID

        Returns:
            True if entry was removed, False if not found
        """
        index_data = self._index.get(uuid)
        if index_data is None:
            logger.warning("Entry not found for removal: %s", uuid)
            return False

        try:
            # Remove layout file
            file_path = Path(index_data["file_path"])
            if file_path.exists():
                file_path.unlink()
                logger.debug("Removed layout file: %s", file_path)

            # Remove from index
            del self._index[uuid]
            self._save_index()

            logger.info("Removed library entry: %s", uuid)
            return True

        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error("Failed to remove entry %s: %s", uuid, e, exc_info=exc_info)
            return False

    def get_layout_content(self, uuid: str) -> dict[str, Any] | None:
        """Get layout content by UUID.

        Args:
            uuid: Layout UUID

        Returns:
            Layout content dictionary or None if not found
        """
        entry = self.get_entry(uuid)
        if entry is None:
            return None

        try:
            if not entry.file_path.exists():
                logger.error("Layout file not found: %s", entry.file_path)
                return None

            content = entry.file_path.read_text(encoding="utf-8")
            return json.loads(content)  # type: ignore[no-any-return]

        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error(
                "Failed to read layout content for %s: %s", uuid, e, exc_info=exc_info
            )
            return None

    def get_layout_path(self, uuid: str) -> Path | None:
        """Get file path for layout by UUID.

        Args:
            uuid: Layout UUID

        Returns:
            Path to layout file or None if not found
        """
        entry = self.get_entry(uuid)
        return entry.file_path if entry else None

    def entry_exists(self, uuid: str) -> bool:
        """Check if entry exists in library.

        Args:
            uuid: Layout UUID

        Returns:
            True if entry exists
        """
        return uuid in self._index

    def get_statistics(self) -> dict[str, Any]:
        """Get library statistics.

        Returns:
            Statistics dictionary
        """
        total_count = len(self._index)
        source_counts: dict[str, int] = {}
        tag_counts: dict[str, int] = {}

        for index_data in self._index.values():
            # Count by source
            source = index_data.get("source", "unknown")
            source_counts[source] = source_counts.get(source, 0) + 1

            # Count by tags
            for tag in index_data.get("tags", []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        return {
            "total_layouts": total_count,
            "source_breakdown": source_counts,
            "popular_tags": dict(
                sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            ),
            "library_path": str(self.library_path),
            "layouts_path": str(self.layouts_path),
            "index_path": str(self.index_path),
        }


def create_library_repository(library_path: Path) -> LibraryRepository:
    """Factory function to create library repository.

    Args:
        library_path: Base path for library storage

    Returns:
        Library repository instance
    """
    return LibraryRepository(library_path)
