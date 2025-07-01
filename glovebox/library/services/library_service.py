"""Main library service for layout fetching and management."""

import logging
import uuid as uuid_module
from pathlib import Path
from typing import Any

from glovebox.config.models.user import UserConfigData
from glovebox.core.cache import get_shared_cache_instance
from glovebox.core.cache.cache_manager import CacheManager
from glovebox.library.fetchers import FetcherRegistry
from glovebox.library.models import (
    FetchRequest,
    FetchResult,
    LayoutMetadata,
    LibraryEntry,
    LibrarySource,
    SearchQuery,
    SearchResult,
)
from glovebox.library.repository import LibraryRepository
from glovebox.moergo.client import MoErgoClient


logger = logging.getLogger(__name__)


class LibraryService:
    """Main service for library operations."""

    def __init__(
        self,
        repository: LibraryRepository,
        fetcher_registry: FetcherRegistry,
        user_config: UserConfigData,
        cache: CacheManager | None = None,
    ) -> None:
        """Initialize library service.

        Args:
            repository: Library repository for storage
            fetcher_registry: Registry of fetchers for different sources
            user_config: User configuration
            cache: Cache manager (optional)
        """
        self.repository = repository
        self.fetcher_registry = fetcher_registry
        self.user_config = user_config
        self.cache = cache or get_shared_cache_instance(
            cache_root=user_config.cache_path,
            tag="library",
            enabled=user_config.cache_strategy == "shared",
        )

    def fetch_layout(self, request: FetchRequest) -> FetchResult:
        """Fetch layout from any supported source.

        Args:
            request: Fetch request with source and options

        Returns:
            Fetch result with success status and entry
        """
        try:
            # Get appropriate fetcher
            fetcher = self.fetcher_registry.get_fetcher(request.source)
            if fetcher is None:
                return FetchResult(
                    success=False,
                    errors=[
                        f"No fetcher available for source: {request.source}",
                        f"Supported sources: {', '.join(self.fetcher_registry.list_supported_sources())}",
                    ],
                )

            # Check if layout already exists
            if hasattr(fetcher, "_get_source_uuid"):
                try:
                    source_uuid = fetcher._get_source_uuid(request.source)
                    if self.repository.entry_exists(source_uuid):
                        existing_entry = self.repository.get_entry(source_uuid)
                        if existing_entry and not request.force_overwrite:
                            return FetchResult(
                                success=False,
                                errors=[
                                    f"Layout already exists in library: {existing_entry.name}",
                                    "Use --force to overwrite existing layout",
                                ],
                            )
                except Exception:
                    # Not a MoErgo source or other issue, continue with fetch
                    pass

            # Determine output path
            if request.output_path:
                target_path = request.output_path
            else:
                # Generate temporary path - repository will determine final path
                temp_filename = f"temp_{uuid_module.uuid4().hex[:8]}.json"
                target_path = self.repository.layouts_path / temp_filename

            # Fetch the layout
            fetch_result = fetcher.fetch(request.source, target_path)
            if not fetch_result.success or not fetch_result.entry:
                return fetch_result

            # Apply custom name if provided
            if request.name:
                fetch_result.entry = fetch_result.entry.model_copy(
                    update={"name": request.name}
                )

            # Read layout content for storage
            if not fetch_result.file_path or not fetch_result.file_path.exists():
                return FetchResult(
                    success=False,
                    errors=["Fetched file not found or inaccessible"],
                )

            try:
                import json

                content = fetch_result.file_path.read_text(encoding="utf-8")
                layout_data = json.loads(content)
            except Exception as e:
                return FetchResult(
                    success=False,
                    errors=[f"Failed to read fetched layout content: {e}"],
                )

            # Store in repository
            try:
                stored_entry = self.repository.store_layout(
                    layout_data, fetch_result.entry
                )

                # Clean up temporary file if it's different from final path
                if (
                    fetch_result.file_path != stored_entry.file_path
                    and fetch_result.file_path.exists()
                ):
                    fetch_result.file_path.unlink()

                return FetchResult(
                    success=True,
                    entry=stored_entry,
                    file_path=stored_entry.file_path,
                    warnings=fetch_result.warnings,
                )

            except Exception as e:
                exc_info = logger.isEnabledFor(logging.DEBUG)
                logger.error(
                    "Failed to store layout in repository: %s", e, exc_info=exc_info
                )
                return FetchResult(
                    success=False,
                    errors=[f"Failed to store layout in library: {e}"],
                )

        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error("Unexpected error in fetch_layout: %s", e, exc_info=exc_info)
            return FetchResult(
                success=False,
                errors=[f"Unexpected error during fetch: {e}"],
            )

    def search_layouts(self, query: SearchQuery) -> SearchResult:
        """Search for layouts using MoErgo API.

        Args:
            query: Search query parameters

        Returns:
            Search result with layouts found
        """
        try:
            # Get MoErgo client from fetcher registry
            moergo_fetcher = None
            for fetcher in self.fetcher_registry._fetchers:
                if hasattr(fetcher, "client"):
                    moergo_fetcher = fetcher
                    break

            if moergo_fetcher is None:
                return SearchResult(
                    success=False,
                    errors=["MoErgo client not available for search"],
                )

            client: MoErgoClient = moergo_fetcher.client

            # Use existing client to list public layouts
            # For now, we'll use the existing list_public_layouts method
            # A full search implementation would require additional MoErgo API endpoints
            try:
                public_uuids = client.list_public_layouts(
                    tags=query.tags, use_cache=True
                )

                # Get metadata for each UUID
                layouts = []
                processed = 0

                for layout_uuid in public_uuids:
                    if query.limit and processed >= query.limit:
                        break

                    if processed < query.offset:
                        processed += 1
                        continue

                    try:
                        meta_response = client.get_layout_meta(
                            layout_uuid, use_cache=True
                        )
                        layout_meta = meta_response["layout_meta"]

                        # Apply filters
                        if (
                            query.creator
                            and query.creator.lower()
                            not in layout_meta.get("creator", "").lower()
                        ):
                            continue

                        if (
                            query.title_contains
                            and query.title_contains.lower()
                            not in layout_meta.get("title", "").lower()
                        ):
                            continue

                        metadata = LayoutMetadata(
                            uuid=layout_uuid,
                            title=layout_meta["title"],
                            creator=layout_meta["creator"],
                            created_at=None,  # Not available in current API
                            tags=layout_meta.get("tags", []),
                            notes=layout_meta.get("notes"),
                            compiled=layout_meta.get("compiled", False),
                        )
                        layouts.append(metadata)
                        processed += 1

                    except Exception as e:
                        exc_info = logger.isEnabledFor(logging.DEBUG)
                        logger.warning(
                            "Failed to get metadata for layout %s: %s",
                            layout_uuid,
                            e,
                            exc_info=exc_info,
                        )
                        continue

                has_more = len(public_uuids) > (query.offset + len(layouts))

                return SearchResult(
                    success=True,
                    layouts=layouts,
                    total_count=len(public_uuids),
                    has_more=has_more,
                )

            except Exception as e:
                exc_info = logger.isEnabledFor(logging.DEBUG)
                logger.error("Search operation failed: %s", e, exc_info=exc_info)
                return SearchResult(
                    success=False,
                    errors=[f"Search failed: {e}"],
                )

        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error("Unexpected error in search_layouts: %s", e, exc_info=exc_info)
            return SearchResult(
                success=False,
                errors=[f"Unexpected error during search: {e}"],
            )

    def list_local_layouts(
        self,
        source_filter: LibrarySource | None = None,
        tag_filter: list[str] | None = None,
    ) -> list[LibraryEntry]:
        """List layouts in local library.

        Args:
            source_filter: Filter by source type
            tag_filter: Filter by tags

        Returns:
            List of library entries
        """
        return self.repository.list_entries(source_filter, tag_filter)

    def get_layout_content(self, uuid: str) -> dict[str, Any] | None:
        """Get layout content by UUID.

        Args:
            uuid: Layout UUID

        Returns:
            Layout content dictionary or None if not found
        """
        return self.repository.get_layout_content(uuid)

    def get_layout_entry(self, uuid: str) -> LibraryEntry | None:
        """Get library entry by UUID.

        Args:
            uuid: Layout UUID

        Returns:
            Library entry or None if not found
        """
        return self.repository.get_entry(uuid)

    def get_layout_entry_by_name(self, name: str) -> LibraryEntry | None:
        """Get library entry by name.

        Args:
            name: Layout name

        Returns:
            Library entry or None if not found
        """
        return self.repository.get_entry_by_name(name)

    def remove_layout(self, uuid: str) -> bool:
        """Remove layout from library.

        Args:
            uuid: Layout UUID

        Returns:
            True if layout was removed
        """
        return self.repository.remove_entry(uuid)

    def get_library_statistics(self) -> dict[str, Any]:
        """Get library statistics.

        Returns:
            Statistics dictionary
        """
        return self.repository.get_statistics()


def create_library_service(
    user_config: UserConfigData,
    repository: LibraryRepository | None = None,
    fetcher_registry: FetcherRegistry | None = None,
    cache: CacheManager | None = None,
) -> LibraryService:
    """Factory function to create library service.

    Args:
        user_config: User configuration
        repository: Library repository (optional, creates default if None)
        fetcher_registry: Fetcher registry (optional, creates default if None)
        cache: Cache manager (optional, creates default if None)

    Returns:
        Library service instance
    """
    from glovebox.library.fetchers.moergo_fetcher import create_moergo_fetcher
    from glovebox.library.fetchers.registry import create_fetcher_registry
    from glovebox.library.repository.library_repository import create_library_repository
    from glovebox.moergo.client import create_moergo_client

    # Create repository if not provided
    if repository is None:
        repository = create_library_repository(user_config.library_path)

    # Create fetcher registry if not provided
    if fetcher_registry is None:
        moergo_client = create_moergo_client(user_config=user_config)
        moergo_fetcher = create_moergo_fetcher(moergo_client)
        fetcher_registry = create_fetcher_registry(moergo_fetcher)

    return LibraryService(
        repository=repository,
        fetcher_registry=fetcher_registry,
        user_config=user_config,
        cache=cache,
    )
