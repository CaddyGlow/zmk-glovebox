"""Unit tests for bookmark service."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from glovebox.config.models.user import UserConfigData
from glovebox.core.cache import CacheManager
from glovebox.layout.models.bookmarks import (
    BookmarkCollection,
    BookmarkSource,
    LayoutBookmark,
)
from glovebox.moergo.bookmark_service import BookmarkService
from glovebox.moergo.client import MoErgoClient
from glovebox.moergo.client.models import LayoutMeta, MoErgoLayout


class TestBookmarkService:
    """Test BookmarkService functionality."""

    @pytest.fixture
    def mock_moergo_client(self):
        """Create a mock MoErgo client."""
        client = Mock(spec=MoErgoClient)
        return client

    @pytest.fixture
    def mock_user_config(self):
        """Create a mock user config."""
        config = Mock(spec=UserConfigData)
        config.layout_bookmarks = None
        return config

    @pytest.fixture
    def mock_cache(self):
        """Create a mock cache manager."""
        cache = Mock(spec=CacheManager)
        return cache

    @pytest.fixture
    def bookmark_service(self, mock_moergo_client, mock_user_config, mock_cache):
        """Create a bookmark service with mocked dependencies."""
        return BookmarkService(mock_moergo_client, mock_user_config, mock_cache)

    def test_init_bookmark_service(
        self, mock_moergo_client, mock_user_config, mock_cache
    ):
        """Test initializing bookmark service."""
        service = BookmarkService(mock_moergo_client, mock_user_config, mock_cache)

        assert service._client == mock_moergo_client
        assert service._user_config == mock_user_config
        assert service._cache == mock_cache
        assert service._bookmarks is None

    def test_get_bookmarks_initializes_empty_collection(
        self, bookmark_service, mock_moergo_client
    ):
        """Test getting bookmarks initializes empty collection when none exists."""
        # Mock the client to return empty public layouts for factory defaults
        mock_moergo_client.list_public_layouts.return_value = []

        bookmarks = bookmark_service.get_bookmarks()

        assert isinstance(bookmarks, BookmarkCollection)
        assert len(bookmarks.bookmarks) == 0

    def test_get_bookmarks_loads_existing_collection(self, bookmark_service):
        """Test getting bookmarks when collection already exists in config."""
        existing_collection = BookmarkCollection()
        existing_bookmark = LayoutBookmark(
            uuid="12345678-1234-1234-1234-123456789012",
            name="existing-layout",
            source=BookmarkSource.USER,
        )
        existing_collection.add_bookmark(existing_bookmark)

        bookmark_service._user_config.layout_bookmarks = existing_collection

        bookmarks = bookmark_service.get_bookmarks()

        assert bookmarks == existing_collection
        assert len(bookmarks.bookmarks) == 1
        assert bookmarks.has_bookmark("existing-layout")

    def test_load_factory_defaults(self, bookmark_service, mock_moergo_client):
        """Test loading factory default bookmarks."""
        # Mock the API responses
        mock_moergo_client.list_public_layouts.return_value = [
            "factory-uuid-1",
            "factory-uuid-2",
        ]

        mock_moergo_client.get_layout_meta.side_effect = [
            {
                "layout_meta": {
                    "title": "Factory Layout 1",
                    "tags": ["glove80-standard", "default"],
                }
            },
            {
                "layout_meta": {
                    "title": "Factory Layout 2",
                    "tags": ["glove80-standard"],
                }
            },
        ]

        # Trigger loading by getting bookmarks
        bookmarks = bookmark_service.get_bookmarks()

        # Verify factory defaults were loaded
        mock_moergo_client.list_public_layouts.assert_called_once_with(
            tags=["glove80-standard"], use_cache=True
        )
        assert mock_moergo_client.get_layout_meta.call_count == 2

        factory_bookmarks = bookmarks.get_factory_bookmarks()
        assert len(factory_bookmarks) == 2

        names = [b.name for b in factory_bookmarks]
        assert "factory-factory-layout-1" in names
        assert "factory-factory-layout-2" in names

    def test_add_bookmark_with_metadata(self, bookmark_service, mock_moergo_client):
        """Test adding a bookmark with metadata fetching."""
        # Mock the get_bookmarks to return empty collection
        mock_moergo_client.list_public_layouts.return_value = []

        # Mock metadata response
        mock_moergo_client.get_layout_meta.return_value = {
            "layout_meta": {
                "title": "Test Layout",
                "tags": ["programming", "vim"],
            }
        }

        bookmark = bookmark_service.add_bookmark(
            uuid="12345678-1234-1234-1234-123456789012",
            name="test-layout",
            description=None,  # Should use auto-generated description
            fetch_metadata=True,
        )

        assert bookmark.uuid == "12345678-1234-1234-1234-123456789012"
        assert bookmark.name == "test-layout"
        assert bookmark.title == "Test Layout"
        assert bookmark.description == "Layout: Test Layout"
        assert bookmark.tags == ["programming", "vim"]
        assert bookmark.source == BookmarkSource.USER

        # Verify metadata was fetched
        mock_moergo_client.get_layout_meta.assert_called_once_with(
            "12345678-1234-1234-1234-123456789012", use_cache=True
        )

    def test_add_bookmark_without_metadata(self, bookmark_service, mock_moergo_client):
        """Test adding a bookmark without metadata fetching."""
        # Mock the get_bookmarks to return empty collection
        mock_moergo_client.list_public_layouts.return_value = []

        bookmark = bookmark_service.add_bookmark(
            uuid="12345678-1234-1234-1234-123456789012",
            name="test-layout",
            description="Custom description",
            fetch_metadata=False,
        )

        assert bookmark.uuid == "12345678-1234-1234-1234-123456789012"
        assert bookmark.name == "test-layout"
        assert bookmark.title is None
        assert bookmark.description == "Custom description"
        assert bookmark.tags == []
        assert bookmark.source == BookmarkSource.USER

        # Verify metadata was not fetched
        mock_moergo_client.get_layout_meta.assert_not_called()

    def test_add_bookmark_metadata_failure(
        self, bookmark_service, mock_moergo_client, caplog
    ):
        """Test adding a bookmark when metadata fetching fails."""
        # Mock the get_bookmarks to return empty collection
        mock_moergo_client.list_public_layouts.return_value = []

        # Mock metadata failure
        mock_moergo_client.get_layout_meta.side_effect = Exception("API Error")

        bookmark = bookmark_service.add_bookmark(
            uuid="12345678-1234-1234-1234-123456789012",
            name="test-layout",
            fetch_metadata=True,
        )

        # Should still create bookmark without metadata
        assert bookmark.uuid == "12345678-1234-1234-1234-123456789012"
        assert bookmark.name == "test-layout"
        assert bookmark.title is None
        assert bookmark.description is None
        assert bookmark.tags == []

        # Should log the warning
        assert "Failed to fetch metadata" in caplog.text

    def test_remove_bookmark_exists(self, bookmark_service, mock_moergo_client):
        """Test removing an existing bookmark."""
        # Mock the get_bookmarks to return empty collection
        mock_moergo_client.list_public_layouts.return_value = []

        # Add a bookmark first
        bookmark_service.add_bookmark(
            uuid="12345678-1234-1234-1234-123456789012",
            name="test-layout",
            fetch_metadata=False,
        )

        # Remove the bookmark
        success = bookmark_service.remove_bookmark("test-layout")

        assert success
        assert not bookmark_service.get_bookmarks().has_bookmark("test-layout")

    def test_remove_bookmark_not_exists(
        self, bookmark_service, mock_moergo_client, caplog
    ):
        """Test removing a non-existent bookmark."""
        # Mock the get_bookmarks to return empty collection
        mock_moergo_client.list_public_layouts.return_value = []

        # Try to remove non-existent bookmark
        success = bookmark_service.remove_bookmark("nonexistent")

        assert not success
        assert "Bookmark not found: nonexistent" in caplog.text

    def test_get_bookmark_exists(self, bookmark_service, mock_moergo_client):
        """Test getting an existing bookmark."""
        # Mock the get_bookmarks to return empty collection
        mock_moergo_client.list_public_layouts.return_value = []

        # Add a bookmark first
        added = bookmark_service.add_bookmark(
            uuid="12345678-1234-1234-1234-123456789012",
            name="test-layout",
            fetch_metadata=False,
        )

        # Get the bookmark
        retrieved = bookmark_service.get_bookmark("test-layout")

        assert retrieved is not None
        assert retrieved.uuid == added.uuid
        assert retrieved.name == added.name

    def test_get_bookmark_not_exists(self, bookmark_service, mock_moergo_client):
        """Test getting a non-existent bookmark."""
        # Mock the get_bookmarks to return empty collection
        mock_moergo_client.list_public_layouts.return_value = []

        retrieved = bookmark_service.get_bookmark("nonexistent")

        assert retrieved is None

    def test_list_bookmarks_no_filter(self, bookmark_service, mock_moergo_client):
        """Test listing all bookmarks without filter."""
        # Mock the get_bookmarks to return empty collection
        mock_moergo_client.list_public_layouts.return_value = []

        # Add bookmarks of different sources
        bookmark_service.add_bookmark(
            uuid="12345678-1234-1234-1234-123456789012",
            name="user-layout",
            fetch_metadata=False,
        )

        # Manually add a factory bookmark
        bookmarks = bookmark_service.get_bookmarks()
        factory_bookmark = LayoutBookmark(
            uuid="87654321-4321-4321-4321-210987654321",
            name="factory-layout",
            source=BookmarkSource.FACTORY,
        )
        bookmarks.add_bookmark(factory_bookmark)

        all_bookmarks = bookmark_service.list_bookmarks()

        assert len(all_bookmarks) == 2
        names = [b.name for b in all_bookmarks]
        assert "user-layout" in names
        assert "factory-layout" in names

    def test_list_bookmarks_filter_by_source(
        self, bookmark_service, mock_moergo_client
    ):
        """Test listing bookmarks filtered by source."""
        # Mock the get_bookmarks to return empty collection
        mock_moergo_client.list_public_layouts.return_value = []

        # Add user bookmark
        bookmark_service.add_bookmark(
            uuid="12345678-1234-1234-1234-123456789012",
            name="user-layout",
            fetch_metadata=False,
        )

        # Manually add factory bookmark
        bookmarks = bookmark_service.get_bookmarks()
        factory_bookmark = LayoutBookmark(
            uuid="87654321-4321-4321-4321-210987654321",
            name="factory-layout",
            source=BookmarkSource.FACTORY,
        )
        bookmarks.add_bookmark(factory_bookmark)

        # Test filtering
        user_bookmarks = bookmark_service.list_bookmarks(BookmarkSource.USER)
        factory_bookmarks = bookmark_service.list_bookmarks(BookmarkSource.FACTORY)

        assert len(user_bookmarks) == 1
        assert user_bookmarks[0].name == "user-layout"

        assert len(factory_bookmarks) == 1
        assert factory_bookmarks[0].name == "factory-layout"

    def test_get_layout_by_bookmark_with_cache(
        self, bookmark_service, mock_moergo_client, mock_cache
    ):
        """Test getting layout data by bookmark with cache hit."""
        # Mock the get_bookmarks to return empty collection
        mock_moergo_client.list_public_layouts.return_value = []

        # Add a bookmark
        bookmark_service.add_bookmark(
            uuid="12345678-1234-1234-1234-123456789012",
            name="test-layout",
            fetch_metadata=False,
        )

        # Mock cached layout data
        cached_layout_data = {
            "layout_meta": {
                "uuid": "12345678-1234-1234-1234-123456789012",
                "title": "Test Layout",
                "creator": "test-user",
                "date": 1234567890,
                "firmware_api_version": "v25.05",
                "notes": "",
                "tags": [],
                "unlisted": False,
                "deleted": False,
                "compiled": False,
                "searchable": True,
            },
            "config": {
                "title": "Test Layout",
                "keyboard": "glove80",
                "layer_names": ["Base"],
                "layers": [[{"value": "&kp A", "params": []}]],
            },
        }
        mock_cache.get.return_value = cached_layout_data

        layout = bookmark_service.get_layout_by_bookmark("test-layout", use_cache=True)

        assert isinstance(layout, MoErgoLayout)
        assert layout.layout_meta.title == "Test Layout"

        # Verify cache was checked
        mock_cache.get.assert_called_once()
        mock_moergo_client.get_layout.assert_not_called()

    def test_get_layout_by_bookmark_cache_miss(
        self, bookmark_service, mock_moergo_client, mock_cache
    ):
        """Test getting layout data by bookmark with cache miss."""
        # Mock the get_bookmarks to return empty collection
        mock_moergo_client.list_public_layouts.return_value = []

        # Add a bookmark
        bookmark_service.add_bookmark(
            uuid="12345678-1234-1234-1234-123456789012",
            name="test-layout",
            fetch_metadata=False,
        )

        # Mock cache miss
        mock_cache.get.return_value = None

        # Mock layout from API
        mock_layout_meta = LayoutMeta(
            uuid="12345678-1234-1234-1234-123456789012",
            date=1234567890,
            creator="test-user",
            firmware_api_version="v25.05",
            title="Test Layout",
        )
        from glovebox.layout.models import LayoutBinding, LayoutData

        mock_binding = LayoutBinding(value="&kp A", params=[])
        mock_layout_config = LayoutData(
            title="Test Layout",
            keyboard="glove80",
            layer_names=["Base"],
            layers=[[mock_binding]],
        )
        mock_layout = MoErgoLayout(
            layout_meta=mock_layout_meta, config=mock_layout_config
        )
        mock_moergo_client.get_layout.return_value = mock_layout

        layout = bookmark_service.get_layout_by_bookmark("test-layout", use_cache=True)

        assert layout == mock_layout

        # Verify API was called and result was cached
        mock_moergo_client.get_layout.assert_called_once_with(
            "12345678-1234-1234-1234-123456789012"
        )
        mock_cache.set.assert_called_once()

    def test_get_layout_by_bookmark_not_found(
        self, bookmark_service, mock_moergo_client
    ):
        """Test getting layout data for non-existent bookmark."""
        # Mock the get_bookmarks to return empty collection
        mock_moergo_client.list_public_layouts.return_value = []

        with pytest.raises(ValueError, match="Bookmark not found: nonexistent"):
            bookmark_service.get_layout_by_bookmark("nonexistent")

    def test_refresh_factory_defaults(self, bookmark_service, mock_moergo_client):
        """Test refreshing factory default bookmarks."""
        # Mock initial factory defaults
        mock_moergo_client.list_public_layouts.return_value = ["old-factory-uuid"]
        mock_moergo_client.get_layout_meta.return_value = {
            "layout_meta": {
                "title": "Old Factory Layout",
                "tags": ["glove80-standard"],
            }
        }

        # Get initial bookmarks (loads factory defaults)
        bookmarks = bookmark_service.get_bookmarks()
        initial_factory_count = len(bookmarks.get_factory_bookmarks())
        assert initial_factory_count == 1

        # Add a user bookmark
        bookmark_service.add_bookmark(
            uuid="12345678-1234-1234-1234-123456789012",
            name="user-layout",
            fetch_metadata=False,
        )

        # Mock new factory defaults for refresh
        mock_moergo_client.list_public_layouts.return_value = [
            "new-factory-uuid-1",
            "new-factory-uuid-2",
        ]
        mock_moergo_client.get_layout_meta.side_effect = [
            {
                "layout_meta": {
                    "title": "New Factory Layout 1",
                    "tags": ["glove80-standard"],
                }
            },
            {
                "layout_meta": {
                    "title": "New Factory Layout 2",
                    "tags": ["glove80-standard"],
                }
            },
        ]

        # Refresh factory defaults
        count = bookmark_service.refresh_factory_defaults()

        assert count == 2

        # Verify old factory bookmarks were removed and new ones added
        updated_bookmarks = bookmark_service.get_bookmarks()
        factory_bookmarks = updated_bookmarks.get_factory_bookmarks()
        user_bookmarks = updated_bookmarks.get_user_bookmarks()

        assert len(factory_bookmarks) == 2
        assert len(user_bookmarks) == 1  # User bookmark should remain

        factory_names = [b.name for b in factory_bookmarks]
        assert "factory-new-factory-layout-1" in factory_names
        assert "factory-new-factory-layout-2" in factory_names

        # Old factory bookmark should be gone
        assert "factory-old-factory-layout" not in factory_names

    def test_save_bookmarks_called(self, bookmark_service, mock_moergo_client):
        """Test that save_bookmarks is called when modifying bookmarks."""
        # Mock the get_bookmarks to return empty collection
        mock_moergo_client.list_public_layouts.return_value = []

        # Add a bookmark
        bookmark_service.add_bookmark(
            uuid="12345678-1234-1234-1234-123456789012",
            name="test-layout",
            fetch_metadata=False,
        )

        # Verify the bookmark was saved to user config
        assert bookmark_service._user_config.layout_bookmarks is not None
        assert bookmark_service._user_config.layout_bookmarks.has_bookmark(
            "test-layout"
        )


@patch("glovebox.moergo.bookmark_service.create_moergo_client")
@patch("glovebox.config.user_config.create_user_config")
def test_create_bookmark_service_defaults(
    mock_create_user_config, mock_create_moergo_client
):
    """Test creating bookmark service with default dependencies."""
    from glovebox.moergo.bookmark_service import create_bookmark_service

    mock_moergo_client = Mock()
    mock_create_moergo_client.return_value = mock_moergo_client

    mock_user_config_manager = Mock()
    mock_user_config = Mock()
    mock_user_config_manager._config = mock_user_config
    mock_create_user_config.return_value = mock_user_config_manager

    service = create_bookmark_service()

    assert service._client == mock_moergo_client
    assert service._user_config == mock_user_config

    mock_create_moergo_client.assert_called_once()
    mock_create_user_config.assert_called_once()


def test_create_bookmark_service_with_args():
    """Test creating bookmark service with provided dependencies."""
    from glovebox.moergo.bookmark_service import create_bookmark_service

    mock_client = Mock()
    mock_config = Mock()
    mock_cache = Mock()

    service = create_bookmark_service(
        moergo_client=mock_client,
        user_config=mock_config,
        cache=mock_cache,
    )

    assert service._client == mock_client
    assert service._user_config == mock_config
    assert service._cache == mock_cache
