"""Library domain for layout fetching and management."""

from .fetchers import (
    BaseFetcher,
    FetcherRegistry,
    FileFetcher,
    HTTPFetcher,
    MoErgoFetcher,
    create_fetcher_registry,
    create_file_fetcher,
    create_http_fetcher,
    create_moergo_fetcher,
)
from .models import (
    FetchRequest,
    FetchResult,
    LayoutMetadata,
    LibraryEntry,
    LibrarySource,
    SearchQuery,
    SearchResult,
)
from .repository import LibraryRepository, create_library_repository
from .services import LibraryService, create_library_service


__all__ = [
    # Models
    "FetchRequest",
    "FetchResult",
    "LayoutMetadata",
    "LibraryEntry",
    "LibrarySource",
    "SearchQuery",
    "SearchResult",
    # Fetchers
    "BaseFetcher",
    "FetcherRegistry",
    "FileFetcher",
    "HTTPFetcher",
    "MoErgoFetcher",
    # Repository
    "LibraryRepository",
    # Services
    "LibraryService",
    # Factory functions
    "create_fetcher_registry",
    "create_file_fetcher",
    "create_http_fetcher",
    "create_moergo_fetcher",
    "create_library_repository",
    "create_library_service",
]
