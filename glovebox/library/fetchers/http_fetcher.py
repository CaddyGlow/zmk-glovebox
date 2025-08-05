"""HTTP fetcher for downloading layout JSON from arbitrary URLs."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from glovebox.library.models import FetchResult, LibraryEntry, LibrarySource


logger = logging.getLogger(__name__)


class HTTPFetcher:
    """Fetcher for HTTP/HTTPS URLs."""

    def __init__(self, timeout: int = 30) -> None:
        """Initialize HTTP fetcher.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout

    def can_fetch(self, source: str) -> bool:
        """Check if source is an HTTP/HTTPS URL.

        Args:
            source: Source identifier

        Returns:
            True if source is HTTP/HTTPS URL
        """
        try:
            parsed = urlparse(source.strip())
            return parsed.scheme in ("http", "https") and bool(parsed.netloc)
        except Exception:
            return False

    def get_metadata(self, source: str) -> dict[str, Any] | None:
        """Get metadata from HTTP source (limited to what we can extract).

        Args:
            source: HTTP URL

        Returns:
            Basic metadata or None
        """
        # For HTTP sources, we can only provide the URL itself as metadata
        if self.can_fetch(source):
            parsed = urlparse(source)
            return {
                "url": source,
                "domain": parsed.netloc,
                "path": parsed.path,
            }
        return None

    def fetch(self, source: str, target_path: Path) -> FetchResult:
        """Fetch layout JSON from HTTP URL.

        Args:
            source: HTTP/HTTPS URL
            target_path: Local path to save layout

        Returns:
            FetchResult with success status and entry
        """
        errors = []
        warnings = []

        try:
            logger.info("Downloading layout from %s", source)

            # Download content with browser user agent to avoid Cloudflare blocking
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            with httpx.Client(timeout=self.timeout, headers=headers) as client:
                response = client.get(source)
                response.raise_for_status()

                # Check content type
                content_type = response.headers.get("content-type", "").lower()
                if (
                    "application/json" not in content_type
                    and "text/json" not in content_type
                ):
                    warnings.append(f"Content-Type is '{content_type}', expected JSON")

                # Parse JSON to validate
                try:
                    layout_data = response.json()
                except json.JSONDecodeError as e:
                    errors.append(f"Invalid JSON content: {e}")
                    return FetchResult(success=False, errors=errors)

                # Save to file
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(response.text, encoding="utf-8")

                # Extract metadata from layout if available
                title = None
                creator = None
                tags = []
                notes = None

                # Try to extract from common layout fields
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

                # Generate name from URL if no title
                parsed = urlparse(source)
                if not title:
                    # Use filename from URL path
                    path_name = Path(parsed.path).stem
                    title = path_name if path_name else parsed.netloc

                name = title.lower().replace(" ", "-") if title else "http-layout"

                # Generate a pseudo-UUID from URL for consistency
                import hashlib

                url_hash = hashlib.sha256(source.encode()).hexdigest()
                pseudo_uuid = f"{url_hash[:8]}-{url_hash[8:12]}-{url_hash[12:16]}-{url_hash[16:20]}-{url_hash[20:32]}"

                # Create library entry
                entry = LibraryEntry(
                    uuid=pseudo_uuid,
                    name=name,
                    title=title,
                    creator=creator,
                    source=LibrarySource.HTTP_URL,
                    source_reference=source,
                    file_path=target_path,
                    downloaded_at=datetime.now(),
                    tags=tags if isinstance(tags, list) else [],
                    notes=notes,
                )

                logger.info(
                    "Successfully downloaded layout from %s to %s", source, target_path
                )
                return FetchResult(
                    success=True, entry=entry, file_path=target_path, warnings=warnings
                )

        except httpx.HTTPStatusError as e:
            error_msg = (
                f"HTTP error {e.response.status_code}: {e.response.reason_phrase}"
            )
            errors.append(error_msg)
            logger.error("HTTP error downloading from %s: %s", source, error_msg)
            return FetchResult(success=False, errors=errors)

        except httpx.TimeoutException:
            error_msg = f"Request timeout after {self.timeout} seconds"
            errors.append(error_msg)
            logger.error("Timeout downloading from %s", source)
            return FetchResult(success=False, errors=errors)

        except httpx.RequestError as e:
            error_msg = f"Request error: {e}"
            errors.append(error_msg)
            logger.error("Request error downloading from %s: %s", source, e)
            return FetchResult(success=False, errors=errors)

        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            error_msg = f"Failed to fetch layout from HTTP: {e}"
            errors.append(error_msg)
            logger.error(error_msg, exc_info=exc_info)
            return FetchResult(success=False, errors=errors)


def create_http_fetcher(timeout: int = 30) -> HTTPFetcher:
    """Factory function to create HTTP fetcher.

    Args:
        timeout: Request timeout in seconds

    Returns:
        HTTP fetcher instance
    """
    return HTTPFetcher(timeout)
