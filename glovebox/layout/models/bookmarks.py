"""Layout bookmark models for managing saved layout references."""

from enum import Enum

from pydantic import BaseModel, Field


class BookmarkSource(str, Enum):
    """Source of a layout bookmark."""

    FACTORY = "factory"
    USER = "user"


class LayoutBookmark(BaseModel):
    """A bookmark reference to a layout by UUID."""

    uuid: str = Field(..., description="Layout UUID from MoErgo API")
    name: str = Field(..., description="User-friendly name for the bookmark")
    title: str | None = Field(
        default=None, description="Original layout title from MoErgo"
    )
    description: str | None = Field(
        default=None, description="User description of the layout"
    )
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")
    source: BookmarkSource = Field(
        default=BookmarkSource.USER, description="Source of the bookmark"
    )

    def __str__(self) -> str:
        """String representation of bookmark."""
        source_indicator = "📦" if self.source == BookmarkSource.FACTORY else "👤"
        return f"{source_indicator} {self.name} ({self.uuid[:8]}...)"


class BookmarkCollection(BaseModel):
    """Collection of layout bookmarks."""

    bookmarks: list[LayoutBookmark] = Field(
        default_factory=list, description="List of layout bookmarks"
    )

    def add_bookmark(self, bookmark: LayoutBookmark) -> None:
        """Add a bookmark to the collection."""
        # Remove existing bookmark with same name if it exists
        self.bookmarks = [b for b in self.bookmarks if b.name != bookmark.name]
        self.bookmarks.append(bookmark)

    def remove_bookmark(self, name: str) -> bool:
        """Remove a bookmark by name. Returns True if removed, False if not found."""
        original_count = len(self.bookmarks)
        self.bookmarks = [b for b in self.bookmarks if b.name != name]
        return len(self.bookmarks) < original_count

    def get_bookmark(self, name: str) -> LayoutBookmark | None:
        """Get a bookmark by name."""
        for bookmark in self.bookmarks:
            if bookmark.name == name:
                return bookmark
        return None

    def list_bookmarks(
        self, source: BookmarkSource | None = None
    ) -> list[LayoutBookmark]:
        """List all bookmarks, optionally filtered by source."""
        if source is None:
            return self.bookmarks.copy()
        return [b for b in self.bookmarks if b.source == source]

    def get_factory_bookmarks(self) -> list[LayoutBookmark]:
        """Get all factory bookmarks."""
        return self.list_bookmarks(BookmarkSource.FACTORY)

    def get_user_bookmarks(self) -> list[LayoutBookmark]:
        """Get all user bookmarks."""
        return self.list_bookmarks(BookmarkSource.USER)

    def has_bookmark(self, name: str) -> bool:
        """Check if a bookmark with the given name exists."""
        return self.get_bookmark(name) is not None
