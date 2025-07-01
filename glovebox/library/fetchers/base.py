"""Base fetcher protocol for library sources."""

from pathlib import Path
from typing import Any, Protocol

from glovebox.library.models import FetchResult


class BaseFetcher(Protocol):
    """Protocol for fetching layouts from different sources."""

    def can_fetch(self, source: str) -> bool:
        """Check if this fetcher can handle the given source.

        Args:
            source: Source identifier (UUID, URL, file path, etc.)

        Returns:
            True if this fetcher can handle the source
        """
        ...

    def fetch(self, source: str, target_path: Path) -> FetchResult:
        """Fetch layout content and save to target path.

        Args:
            source: Source identifier to fetch from
            target_path: Local path to save the layout

        Returns:
            FetchResult with success status and metadata
        """
        ...

    def get_metadata(self, source: str) -> dict[str, Any] | None:
        """Get metadata for a source without downloading content.

        Args:
            source: Source identifier

        Returns:
            Metadata dictionary or None if not available
        """
        ...
