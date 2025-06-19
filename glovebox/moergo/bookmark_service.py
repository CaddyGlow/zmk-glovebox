"""Bookmark service for managing layout bookmarks with MoErgo integration."""

import logging
from typing import Any, Optional

from glovebox.config.models.user import UserConfigData
from glovebox.config.user_config import create_user_config
from glovebox.core.cache import CacheKey, CacheManager, create_default_cache
from glovebox.layout.models.bookmarks import (
    BookmarkCollection,
    BookmarkSource,
    LayoutBookmark,
)
from glovebox.moergo.client import MoErgoClient, create_moergo_client
from glovebox.moergo.client.models import MoErgoLayout


logger = logging.getLogger(__name__)


class BookmarkService:
    """Service for managing layout bookmarks with MoErgo integration."""

    def __init__(
        self,
        moergo_client: MoErgoClient,
        user_config: UserConfigData,
        cache: CacheManager | None = None,
    ):
        """Initialize bookmark service."""
        self._client = moergo_client
        self._user_config = user_config
        self._cache = cache or create_default_cache(cache_strategy="shared")
        self._bookmarks: BookmarkCollection | None = None

    def get_bookmarks(self) -> BookmarkCollection:
        """Get the current bookmark collection, initializing if needed."""
        if self._bookmarks is None:
            self._load_bookmarks()
        return self._bookmarks  # type: ignore[return-value]

    def _load_bookmarks(self) -> None:
        """Load bookmarks from user config."""
        if self._user_config.layout_bookmarks is not None:
            self._bookmarks = self._user_config.layout_bookmarks
        else:
            self._bookmarks = BookmarkCollection()
            # Initialize with factory defaults on first load
            self._load_factory_defaults()
            self._save_bookmarks()

    def _save_bookmarks(self) -> None:
        """Save bookmarks to user config."""
        if self._bookmarks is not None:
            self._user_config.layout_bookmarks = self._bookmarks

    def _load_factory_defaults(self) -> None:
        """Load factory default bookmarks from glove80-standard tagged layouts."""
        try:
            logger.info("Loading factory default bookmarks with 'glove80-standard' tag")
            public_uuids = self._client.list_public_layouts(
                tags=["glove80-standard"], use_cache=True
            )

            factory_bookmarks = []
            for uuid in public_uuids[:10]:  # Limit to first 10 factory defaults
                try:
                    # Get layout metadata efficiently
                    meta_response = self._client.get_layout_meta(uuid, use_cache=True)
                    layout_meta = meta_response["layout_meta"]

                    # Create factory bookmark
                    bookmark = LayoutBookmark(
                        uuid=uuid,
                        name=f"factory-{layout_meta['title'].lower().replace(' ', '-')}",
                        title=layout_meta["title"],
                        description=f"Factory default: {layout_meta['title']}",
                        tags=layout_meta.get("tags", []),
                        source=BookmarkSource.FACTORY,
                    )
                    factory_bookmarks.append(bookmark)
                    logger.debug("Added factory bookmark: %s", bookmark.name)

                except Exception as e:
                    logger.warning(
                        "Failed to load factory bookmark for %s: %s", uuid, e
                    )

            # Add all factory bookmarks to collection
            if self._bookmarks is not None:
                for bookmark in factory_bookmarks:
                    self._bookmarks.add_bookmark(bookmark)

            logger.info("Loaded %d factory default bookmarks", len(factory_bookmarks))

        except Exception as e:
            logger.warning("Failed to load factory defaults: %s", e)

    def add_bookmark(
        self,
        uuid: str,
        name: str,
        description: str | None = None,
        fetch_metadata: bool = True,
    ) -> LayoutBookmark:
        """Add a new user bookmark."""
        bookmarks = self.get_bookmarks()

        title = None
        tags = []

        # Fetch metadata from MoErgo if requested
        if fetch_metadata:
            try:
                meta_response = self._client.get_layout_meta(uuid, use_cache=True)
                layout_meta = meta_response["layout_meta"]
                title = layout_meta["title"]
                tags = layout_meta.get("tags", [])

                # Use original title as description if none provided
                if description is None:
                    description = f"Layout: {title}"

            except Exception as e:
                logger.warning("Failed to fetch metadata for %s: %s", uuid, e)

        bookmark = LayoutBookmark(
            uuid=uuid,
            name=name,
            title=title,
            description=description,
            tags=tags,
            source=BookmarkSource.USER,
        )

        bookmarks.add_bookmark(bookmark)
        self._save_bookmarks()

        logger.info("Added bookmark: %s -> %s", name, uuid)
        return bookmark

    def remove_bookmark(self, name: str) -> bool:
        """Remove a bookmark by name."""
        bookmarks = self.get_bookmarks()
        success = bookmarks.remove_bookmark(name)

        if success:
            self._save_bookmarks()
            logger.info("Removed bookmark: %s", name)
        else:
            logger.warning("Bookmark not found: %s", name)

        return success

    def get_bookmark(self, name: str) -> LayoutBookmark | None:
        """Get a bookmark by name."""
        bookmarks = self.get_bookmarks()
        return bookmarks.get_bookmark(name)

    def list_bookmarks(
        self, source: BookmarkSource | None = None
    ) -> list[LayoutBookmark]:
        """List all bookmarks, optionally filtered by source."""
        bookmarks = self.get_bookmarks()
        return bookmarks.list_bookmarks(source)

    def get_layout_by_bookmark(self, name: str, use_cache: bool = True) -> MoErgoLayout:
        """Get the full layout data for a bookmarked layout."""
        bookmark = self.get_bookmark(name)
        if bookmark is None:
            raise ValueError(f"Bookmark not found: {name}")

        # Check cache first if enabled
        if use_cache:
            cache_key = CacheKey.from_parts("bookmark_layout", bookmark.uuid)
            cached_layout = self._cache.get(cache_key)
            if cached_layout is not None:
                return MoErgoLayout(**cached_layout)

        # Fetch from MoErgo API
        layout = self._client.get_layout(bookmark.uuid)

        # Cache the result for long-term storage (UUIDs are immutable)
        if use_cache:
            cache_key = CacheKey.from_parts("bookmark_layout", bookmark.uuid)
            # Cache for 24 hours since layout content is immutable by UUID
            self._cache.set(cache_key, layout.model_dump(), ttl=86400)

        return layout

    def refresh_factory_defaults(self) -> int:
        """Refresh factory default bookmarks from MoErgo API."""
        bookmarks = self.get_bookmarks()

        # Remove existing factory bookmarks
        bookmarks.bookmarks = [
            b for b in bookmarks.bookmarks if b.source != BookmarkSource.FACTORY
        ]

        # Reload factory defaults
        self._load_factory_defaults()
        self._save_bookmarks()

        factory_count = len(bookmarks.get_factory_bookmarks())
        logger.info("Refreshed %d factory default bookmarks", factory_count)
        return factory_count


def create_bookmark_service(
    moergo_client: MoErgoClient | None = None,
    user_config: UserConfigData | None = None,
    cache: CacheManager | None = None,
) -> BookmarkService:
    """Factory function to create a bookmark service."""
    if moergo_client is None:
        moergo_client = create_moergo_client()

    if user_config is None:
        from glovebox.config.user_config import create_user_config

        user_config_manager = create_user_config()
        user_config = user_config_manager._config

    return BookmarkService(moergo_client, user_config, cache)
