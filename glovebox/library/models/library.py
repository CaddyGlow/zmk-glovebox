"""Core library models for layout management."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import Field

from glovebox.models.base import GloveboxBaseModel


class LibrarySource(str, Enum):
    """Source types for layout fetching."""

    MOERGO_UUID = "moergo_uuid"
    MOERGO_URL = "moergo_url"
    HTTP_URL = "http_url"
    LOCAL_FILE = "local_file"


class LibraryEntry(GloveboxBaseModel):
    """A single layout entry in the library."""

    uuid: str = Field(description="Unique identifier for the layout")
    name: str = Field(description="User-friendly name for the layout")
    title: str | None = Field(
        default=None, description="Original title from layout metadata"
    )
    creator: str | None = Field(default=None, description="Creator of the layout")
    source: LibrarySource = Field(
        description="Source type where layout was fetched from"
    )
    source_reference: str = Field(
        description="Original source reference (UUID, URL, file path)"
    )
    file_path: Path = Field(description="Local file path where layout is stored")
    downloaded_at: datetime = Field(description="When the layout was added to library")
    tags: list[str] = Field(
        default_factory=list, description="Tags associated with the layout"
    )
    notes: str | None = Field(
        default=None, description="Additional notes from layout metadata"
    )


class FetchRequest(GloveboxBaseModel):
    """Request to fetch a layout from any source."""

    source: str = Field(description="Source identifier (UUID, URL, or file path)")
    name: str | None = Field(default=None, description="Custom name for the layout")
    output_path: Path | None = Field(default=None, description="Custom output path")
    create_bookmark: bool = Field(
        default=False, description="Whether to create a bookmark"
    )
    force_overwrite: bool = Field(
        default=False, description="Whether to overwrite existing files"
    )


class FetchResult(GloveboxBaseModel):
    """Result of a layout fetch operation."""

    success: bool = Field(description="Whether the fetch was successful")
    entry: LibraryEntry | None = Field(
        default=None, description="Created library entry if successful"
    )
    file_path: Path | None = Field(default=None, description="Path to the fetched file")
    errors: list[str] = Field(
        default_factory=list, description="Any errors encountered"
    )
    warnings: list[str] = Field(
        default_factory=list, description="Any warnings generated"
    )


class SearchQuery(GloveboxBaseModel):
    """Query parameters for searching layouts."""

    tags: list[str] | None = Field(default=None, description="Filter by tags")
    creator: str | None = Field(default=None, description="Filter by creator")
    title_contains: str | None = Field(
        default=None, description="Filter by title containing text"
    )
    limit: int | None = Field(default=None, description="Maximum number of results")
    offset: int = Field(default=0, description="Offset for pagination")


class LayoutMetadata(GloveboxBaseModel):
    """Metadata for a layout from search results."""

    uuid: str = Field(description="Layout UUID")
    title: str = Field(description="Layout title")
    creator: str = Field(description="Layout creator")
    created_at: datetime | None = Field(default=None, description="Creation date")
    tags: list[str] = Field(default_factory=list, description="Layout tags")
    notes: str | None = Field(default=None, description="Layout notes")
    compiled: bool = Field(
        default=False, description="Whether layout is compiled on MoErgo servers"
    )


class SearchResult(GloveboxBaseModel):
    """Result of a layout search operation."""

    success: bool = Field(description="Whether the search was successful")
    layouts: list[LayoutMetadata] = Field(
        default_factory=list, description="Found layouts"
    )
    total_count: int | None = Field(default=None, description="Total number of matches")
    has_more: bool = Field(default=False, description="Whether there are more results")
    errors: list[str] = Field(
        default_factory=list, description="Any errors encountered"
    )
