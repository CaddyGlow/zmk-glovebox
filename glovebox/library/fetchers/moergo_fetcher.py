"""MoErgo fetcher for downloading layouts from MoErgo API."""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from glovebox.library.models import FetchResult, LibraryEntry, LibrarySource
from glovebox.moergo.client import MoErgoClient
from glovebox.moergo.client.models import AuthenticationError, NetworkError


logger = logging.getLogger(__name__)


class MoErgoFetcher:
    """Fetcher for MoErgo layouts via UUID or URL."""

    def __init__(self, client: MoErgoClient) -> None:
        """Initialize with MoErgo client.

        Args:
            client: Configured MoErgo client
        """
        self.client = client

        # UUID pattern for validation
        self.uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )

        # MoErgo URL patterns
        self.url_patterns = [
            re.compile(
                r"https?://(?:www\.)?moergo\.com/.*?/([0-9a-f-]{36})", re.IGNORECASE
            ),
            re.compile(
                r"https?://(?:www\.)?glove80\.com/.*?/([0-9a-f-]{36})", re.IGNORECASE
            ),
        ]

    def can_fetch(self, source: str) -> bool:
        """Check if source is a MoErgo UUID or URL.

        Args:
            source: Source identifier

        Returns:
            True if source is a UUID or MoErgo URL
        """
        # Check if it's a UUID
        if self.uuid_pattern.match(source.strip()):
            return True

        # Check if it's a MoErgo URL
        return any(pattern.search(source) for pattern in self.url_patterns)

    def _extract_uuid_from_url(self, url: str) -> str | None:
        """Extract UUID from MoErgo URL.

        Args:
            url: MoErgo URL

        Returns:
            Extracted UUID or None
        """
        for pattern in self.url_patterns:
            match = pattern.search(url)
            if match:
                return match.group(1)
        return None

    def _get_source_uuid(self, source: str) -> str:
        """Get UUID from source (either direct UUID or extract from URL).

        Args:
            source: Source identifier

        Returns:
            UUID string

        Raises:
            ValueError: If UUID cannot be extracted
        """
        # Check if it's already a UUID
        if self.uuid_pattern.match(source.strip()):
            return source.strip()

        # Try to extract from URL
        uuid = self._extract_uuid_from_url(source)
        if uuid:
            return uuid

        raise ValueError(f"Cannot extract UUID from source: {source}")

    def get_metadata(self, source: str) -> dict[str, Any] | None:
        """Get layout metadata without downloading full content.

        Args:
            source: MoErgo UUID or URL

        Returns:
            Metadata dictionary or None if error
        """
        try:
            uuid = self._get_source_uuid(source)

            # Use existing client method for metadata
            meta_response = self.client.get_layout_meta(uuid, use_cache=True)
            return meta_response.get("layout_meta")

        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error(
                "Failed to get metadata for %s: %s", source, e, exc_info=exc_info
            )
            return None

    def fetch(self, source: str, target_path: Path) -> FetchResult:
        """Fetch layout from MoErgo and save to target path.

        Args:
            source: MoErgo UUID or URL
            target_path: Local path to save layout

        Returns:
            FetchResult with success status and entry
        """
        errors: list[str] = []
        warnings: list[str] = []

        try:
            # Extract UUID from source
            uuid = self._get_source_uuid(source)

            # Check authentication
            if not self.client.validate_authentication():
                errors.append(
                    "MoErgo authentication failed. Please run 'glovebox moergo login' first."
                )
                return FetchResult(success=False, errors=errors)

            # Download layout
            logger.info("Downloading layout %s from MoErgo", uuid)
            layout = self.client.get_layout(uuid)

            # Prepare layout data for saving
            layout_data = layout.config.model_dump(mode="json", by_alias=True)

            # Add MoErgo metadata
            layout_data["_moergo_meta"] = {
                "uuid": layout.layout_meta.uuid,
                "title": layout.layout_meta.title,
                "creator": layout.layout_meta.creator,
                "date": layout.layout_meta.date,
                "notes": layout.layout_meta.notes,
                "tags": layout.layout_meta.tags,
            }

            # Save to file
            target_path.parent.mkdir(parents=True, exist_ok=True)
            layout_json = json.dumps(layout_data, indent=2)
            target_path.write_text(layout_json, encoding="utf-8")

            # Determine source type
            source_type = (
                LibrarySource.MOERGO_URL
                if any(pattern.search(source) for pattern in self.url_patterns)
                else LibrarySource.MOERGO_UUID
            )

            # Create library entry
            entry = LibraryEntry(
                uuid=uuid,
                name=layout.layout_meta.title.lower().replace(" ", "-")
                if layout.layout_meta.title
                else uuid,
                title=layout.layout_meta.title,
                creator=layout.layout_meta.creator,
                source=source_type,
                source_reference=source,
                file_path=target_path,
                downloaded_at=datetime.now(),
                tags=layout.layout_meta.tags or [],
                notes=layout.layout_meta.notes,
            )

            logger.info(
                "Successfully downloaded layout '%s' to %s",
                entry.title or entry.name,
                target_path,
            )
            return FetchResult(
                success=True, entry=entry, file_path=target_path, warnings=warnings
            )

        except AuthenticationError as e:
            error_msg = f"MoErgo authentication error: {e}"
            errors.append(error_msg)
            logger.error(error_msg)
            return FetchResult(success=False, errors=errors)

        except NetworkError as e:
            error_msg = f"Network error accessing MoErgo: {e}"
            errors.append(error_msg)
            logger.error(error_msg)
            return FetchResult(success=False, errors=errors)

        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            error_msg = f"Failed to fetch layout from MoErgo: {e}"
            errors.append(error_msg)
            logger.error(error_msg, exc_info=exc_info)
            return FetchResult(success=False, errors=errors)


def create_moergo_fetcher(client: MoErgoClient) -> MoErgoFetcher:
    """Factory function to create MoErgo fetcher.

    Args:
        client: Configured MoErgo client

    Returns:
        MoErgo fetcher instance
    """
    return MoErgoFetcher(client)
