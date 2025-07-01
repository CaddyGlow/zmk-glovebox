"""Library fetcher implementations for different source types."""

from .base import BaseFetcher
from .file_fetcher import FileFetcher, create_file_fetcher
from .http_fetcher import HTTPFetcher, create_http_fetcher
from .moergo_fetcher import MoErgoFetcher, create_moergo_fetcher
from .registry import FetcherRegistry, create_fetcher_registry


__all__ = [
    "BaseFetcher",
    "FileFetcher",
    "HTTPFetcher",
    "MoErgoFetcher",
    "FetcherRegistry",
    "create_file_fetcher",
    "create_http_fetcher",
    "create_moergo_fetcher",
    "create_fetcher_registry",
]
