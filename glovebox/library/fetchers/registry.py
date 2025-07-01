"""Fetcher registry for managing different source types."""

import logging
from typing import Any

from .base import BaseFetcher
from .file_fetcher import FileFetcher
from .http_fetcher import HTTPFetcher
from .moergo_fetcher import MoErgoFetcher


logger = logging.getLogger(__name__)


class FetcherRegistry:
    """Registry for managing fetchers for different source types."""

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._fetchers: list[BaseFetcher] = []

    def register_fetcher(self, fetcher: BaseFetcher) -> None:
        """Register a fetcher.

        Args:
            fetcher: Fetcher to register
        """
        self._fetchers.append(fetcher)
        logger.debug("Registered fetcher: %s", type(fetcher).__name__)

    def get_fetcher(self, source: str) -> BaseFetcher | None:
        """Get appropriate fetcher for source.

        Args:
            source: Source identifier

        Returns:
            Matching fetcher or None if no match
        """
        for fetcher in self._fetchers:
            if fetcher.can_fetch(source):
                logger.debug(
                    "Selected fetcher %s for source: %s", type(fetcher).__name__, source
                )
                return fetcher

        logger.warning("No fetcher found for source: %s", source)
        return None

    def get_metadata(self, source: str) -> dict[str, Any] | None:
        """Get metadata for source using appropriate fetcher.

        Args:
            source: Source identifier

        Returns:
            Metadata dictionary or None
        """
        fetcher = self.get_fetcher(source)
        if fetcher:
            return fetcher.get_metadata(source)
        return None

    def list_supported_sources(self) -> list[str]:
        """Get list of registered fetcher types.

        Returns:
            List of fetcher type names
        """
        return [type(fetcher).__name__ for fetcher in self._fetchers]


def create_fetcher_registry(
    moergo_fetcher: MoErgoFetcher,
    http_fetcher: HTTPFetcher | None = None,
    file_fetcher: FileFetcher | None = None,
) -> FetcherRegistry:
    """Factory function to create fetcher registry with standard fetchers.

    Args:
        moergo_fetcher: MoErgo fetcher (required)
        http_fetcher: HTTP fetcher (optional, creates default if None)
        file_fetcher: File fetcher (optional, creates default if None)

    Returns:
        Configured fetcher registry
    """
    from .file_fetcher import create_file_fetcher
    from .http_fetcher import create_http_fetcher

    registry = FetcherRegistry()

    # Register fetchers in priority order
    # MoErgo first (most specific)
    registry.register_fetcher(moergo_fetcher)

    # HTTP fetcher
    if http_fetcher is None:
        http_fetcher = create_http_fetcher()
    registry.register_fetcher(http_fetcher)

    # File fetcher last (fallback)
    if file_fetcher is None:
        file_fetcher = create_file_fetcher()
    registry.register_fetcher(file_fetcher)

    return registry
