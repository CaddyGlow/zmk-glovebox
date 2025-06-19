"""Unit tests for bookmark models."""

import pytest

from glovebox.layout.models.bookmarks import (
    BookmarkCollection,
    BookmarkSource,
    LayoutBookmark,
)


class TestLayoutBookmark:
    """Test LayoutBookmark model."""

    def test_create_user_bookmark(self):
        """Test creating a user bookmark."""
        bookmark = LayoutBookmark(
            uuid="12345678-1234-1234-1234-123456789012",
            name="my-layout",
            title="My Custom Layout",
            description="A custom layout for programming",
            tags=["programming", "vim"],
            source=BookmarkSource.USER,
        )

        assert bookmark.uuid == "12345678-1234-1234-1234-123456789012"
        assert bookmark.name == "my-layout"
        assert bookmark.title == "My Custom Layout"
        assert bookmark.description == "A custom layout for programming"
        assert bookmark.tags == ["programming", "vim"]
        assert bookmark.source == BookmarkSource.USER

    def test_create_factory_bookmark(self):
        """Test creating a factory bookmark."""
        bookmark = LayoutBookmark(
            uuid="87654321-4321-4321-4321-210987654321",
            name="factory-default",
            title="Factory Default Layout",
            source=BookmarkSource.FACTORY,
        )

        assert bookmark.uuid == "87654321-4321-4321-4321-210987654321"
        assert bookmark.name == "factory-default"
        assert bookmark.title == "Factory Default Layout"
        assert bookmark.description is None
        assert bookmark.tags == []
        assert bookmark.source == BookmarkSource.FACTORY

    def test_bookmark_defaults(self):
        """Test bookmark default values."""
        bookmark = LayoutBookmark(
            uuid="12345678-1234-1234-1234-123456789012",
            name="minimal",
        )

        assert bookmark.title is None
        assert bookmark.description is None
        assert bookmark.tags == []
        assert bookmark.source == BookmarkSource.USER

    def test_bookmark_string_representation(self):
        """Test bookmark string representation."""
        user_bookmark = LayoutBookmark(
            uuid="12345678-1234-1234-1234-123456789012",
            name="user-layout",
            source=BookmarkSource.USER,
        )

        factory_bookmark = LayoutBookmark(
            uuid="87654321-4321-4321-4321-210987654321",
            name="factory-layout",
            source=BookmarkSource.FACTORY,
        )

        user_str = str(user_bookmark)
        factory_str = str(factory_bookmark)

        assert "👤" in user_str
        assert "user-layout" in user_str
        assert "12345678" in user_str

        assert "📦" in factory_str
        assert "factory-layout" in factory_str
        assert "87654321" in factory_str


class TestBookmarkCollection:
    """Test BookmarkCollection model."""

    def test_empty_collection(self):
        """Test empty bookmark collection."""
        collection = BookmarkCollection()

        assert len(collection.bookmarks) == 0
        assert collection.list_bookmarks() == []
        assert collection.get_bookmark("nonexistent") is None
        assert not collection.has_bookmark("nonexistent")

    def test_add_bookmark(self):
        """Test adding bookmarks to collection."""
        collection = BookmarkCollection()

        bookmark1 = LayoutBookmark(
            uuid="12345678-1234-1234-1234-123456789012",
            name="layout1",
            source=BookmarkSource.USER,
        )

        bookmark2 = LayoutBookmark(
            uuid="87654321-4321-4321-4321-210987654321",
            name="layout2",
            source=BookmarkSource.FACTORY,
        )

        collection.add_bookmark(bookmark1)
        collection.add_bookmark(bookmark2)

        assert len(collection.bookmarks) == 2
        assert collection.has_bookmark("layout1")
        assert collection.has_bookmark("layout2")

    def test_add_duplicate_bookmark_replaces(self):
        """Test that adding a bookmark with same name replaces the old one."""
        collection = BookmarkCollection()

        bookmark1 = LayoutBookmark(
            uuid="12345678-1234-1234-1234-123456789012",
            name="layout1",
            title="Original Title",
            source=BookmarkSource.USER,
        )

        bookmark2 = LayoutBookmark(
            uuid="87654321-4321-4321-4321-210987654321",
            name="layout1",  # Same name
            title="Updated Title",
            source=BookmarkSource.USER,
        )

        collection.add_bookmark(bookmark1)
        collection.add_bookmark(bookmark2)

        assert len(collection.bookmarks) == 1
        retrieved = collection.get_bookmark("layout1")
        assert retrieved is not None
        assert retrieved.uuid == "87654321-4321-4321-4321-210987654321"
        assert retrieved.title == "Updated Title"

    def test_remove_bookmark(self):
        """Test removing bookmarks from collection."""
        collection = BookmarkCollection()

        bookmark = LayoutBookmark(
            uuid="12345678-1234-1234-1234-123456789012",
            name="layout1",
            source=BookmarkSource.USER,
        )

        collection.add_bookmark(bookmark)
        assert collection.has_bookmark("layout1")

        # Remove existing bookmark
        success = collection.remove_bookmark("layout1")
        assert success
        assert not collection.has_bookmark("layout1")
        assert len(collection.bookmarks) == 0

        # Try to remove non-existent bookmark
        success = collection.remove_bookmark("nonexistent")
        assert not success

    def test_get_bookmark(self):
        """Test getting bookmarks by name."""
        collection = BookmarkCollection()

        bookmark = LayoutBookmark(
            uuid="12345678-1234-1234-1234-123456789012",
            name="layout1",
            title="Test Layout",
            source=BookmarkSource.USER,
        )

        collection.add_bookmark(bookmark)

        retrieved = collection.get_bookmark("layout1")
        assert retrieved is not None
        assert retrieved.uuid == bookmark.uuid
        assert retrieved.name == bookmark.name
        assert retrieved.title == bookmark.title

        assert collection.get_bookmark("nonexistent") is None

    def test_list_bookmarks_no_filter(self):
        """Test listing all bookmarks without filter."""
        collection = BookmarkCollection()

        user_bookmark = LayoutBookmark(
            uuid="12345678-1234-1234-1234-123456789012",
            name="user-layout",
            source=BookmarkSource.USER,
        )

        factory_bookmark = LayoutBookmark(
            uuid="87654321-4321-4321-4321-210987654321",
            name="factory-layout",
            source=BookmarkSource.FACTORY,
        )

        collection.add_bookmark(user_bookmark)
        collection.add_bookmark(factory_bookmark)

        all_bookmarks = collection.list_bookmarks()
        assert len(all_bookmarks) == 2

        names = [b.name for b in all_bookmarks]
        assert "user-layout" in names
        assert "factory-layout" in names

    def test_list_bookmarks_by_source(self):
        """Test listing bookmarks filtered by source."""
        collection = BookmarkCollection()

        user_bookmark1 = LayoutBookmark(
            uuid="12345678-1234-1234-1234-123456789012",
            name="user-layout1",
            source=BookmarkSource.USER,
        )

        user_bookmark2 = LayoutBookmark(
            uuid="11111111-1111-1111-1111-111111111111",
            name="user-layout2",
            source=BookmarkSource.USER,
        )

        factory_bookmark = LayoutBookmark(
            uuid="87654321-4321-4321-4321-210987654321",
            name="factory-layout",
            source=BookmarkSource.FACTORY,
        )

        collection.add_bookmark(user_bookmark1)
        collection.add_bookmark(user_bookmark2)
        collection.add_bookmark(factory_bookmark)

        # Test user bookmarks
        user_bookmarks = collection.list_bookmarks(BookmarkSource.USER)
        assert len(user_bookmarks) == 2
        names = [b.name for b in user_bookmarks]
        assert "user-layout1" in names
        assert "user-layout2" in names
        assert "factory-layout" not in names

        # Test factory bookmarks
        factory_bookmarks = collection.list_bookmarks(BookmarkSource.FACTORY)
        assert len(factory_bookmarks) == 1
        assert factory_bookmarks[0].name == "factory-layout"

    def test_get_factory_bookmarks(self):
        """Test getting only factory bookmarks."""
        collection = BookmarkCollection()

        user_bookmark = LayoutBookmark(
            uuid="12345678-1234-1234-1234-123456789012",
            name="user-layout",
            source=BookmarkSource.USER,
        )

        factory_bookmark = LayoutBookmark(
            uuid="87654321-4321-4321-4321-210987654321",
            name="factory-layout",
            source=BookmarkSource.FACTORY,
        )

        collection.add_bookmark(user_bookmark)
        collection.add_bookmark(factory_bookmark)

        factory_bookmarks = collection.get_factory_bookmarks()
        assert len(factory_bookmarks) == 1
        assert factory_bookmarks[0].name == "factory-layout"
        assert factory_bookmarks[0].source == BookmarkSource.FACTORY

    def test_get_user_bookmarks(self):
        """Test getting only user bookmarks."""
        collection = BookmarkCollection()

        user_bookmark = LayoutBookmark(
            uuid="12345678-1234-1234-1234-123456789012",
            name="user-layout",
            source=BookmarkSource.USER,
        )

        factory_bookmark = LayoutBookmark(
            uuid="87654321-4321-4321-4321-210987654321",
            name="factory-layout",
            source=BookmarkSource.FACTORY,
        )

        collection.add_bookmark(user_bookmark)
        collection.add_bookmark(factory_bookmark)

        user_bookmarks = collection.get_user_bookmarks()
        assert len(user_bookmarks) == 1
        assert user_bookmarks[0].name == "user-layout"
        assert user_bookmarks[0].source == BookmarkSource.USER

    def test_has_bookmark(self):
        """Test checking if bookmark exists."""
        collection = BookmarkCollection()

        bookmark = LayoutBookmark(
            uuid="12345678-1234-1234-1234-123456789012",
            name="test-layout",
            source=BookmarkSource.USER,
        )

        assert not collection.has_bookmark("test-layout")

        collection.add_bookmark(bookmark)
        assert collection.has_bookmark("test-layout")

        collection.remove_bookmark("test-layout")
        assert not collection.has_bookmark("test-layout")


class TestBookmarkSource:
    """Test BookmarkSource enum."""

    def test_bookmark_source_values(self):
        """Test bookmark source enum values."""
        assert BookmarkSource.FACTORY.value == "factory"
        assert BookmarkSource.USER.value == "user"

    def test_bookmark_source_string_conversion(self):
        """Test bookmark source string conversion."""
        assert BookmarkSource.FACTORY.value == "factory"
        assert BookmarkSource.USER.value == "user"
