"""Unit tests for bookmark CLI commands."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pytest
import typer
from typer.testing import CliRunner

from glovebox.cli.commands.layout.glove80_sync import glove80_group
from glovebox.layout.models.bookmarks import BookmarkSource, LayoutBookmark
from glovebox.moergo.client.models import LayoutMeta, MoErgoLayout


class TestBookmarkCommands:
    """Test bookmark CLI commands."""

    @pytest.fixture
    def runner(self):
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_app_context(self):
        """Create a mock app context."""
        context = Mock()
        context.use_emoji = True
        return context

    @pytest.fixture
    def mock_bookmark_service(self):
        """Create a mock bookmark service."""
        service = Mock()
        service.list_bookmarks.return_value = []
        service.get_bookmark.return_value = None
        service.add_bookmark.return_value = Mock()
        service.remove_bookmark.return_value = True
        service.refresh_factory_defaults.return_value = 5
        return service

    @pytest.fixture
    def mock_layout_data(self):
        """Create mock layout data."""
        layout_data = Mock()
        layout_data.title = "Test Layout"
        layout_data.model_dump.return_value = {"title": "Test Layout"}
        return layout_data

    @pytest.fixture
    def mock_moergo_layout(self):
        """Create mock MoErgo layout."""
        layout_meta = LayoutMeta(
            uuid="12345678-1234-1234-1234-123456789012",
            title="Test Layout",
            creator="test-user",
            date=1234567890,
            firmware_api_version="v25.05",
            compiled=False,
        )
        from glovebox.layout.models import LayoutBinding, LayoutData

        mock_binding = LayoutBinding(value="&kp A", params=[])
        config = LayoutData(
            title="Test Layout",
            keyboard="glove80",
            layer_names=["Base"],
            layers=[[mock_binding]],
        )
        return MoErgoLayout(layout_meta=layout_meta, config=config)

    @patch("glovebox.cli.commands.layout.glove80_sync.create_bookmark_service")
    def test_bookmark_list_empty(
        self, mock_create_service, runner, mock_bookmark_service, mock_app_context
    ):
        """Test listing bookmarks when none exist."""
        mock_create_service.return_value = mock_bookmark_service
        mock_bookmark_service.list_bookmarks.return_value = []

        # Invoke with mock context
        result = runner.invoke(
            glove80_group, ["bookmark", "list"], obj=mock_app_context
        )

        assert result.exit_code == 0
        assert "No bookmarks found" in result.stdout
        mock_bookmark_service.list_bookmarks.assert_called_once_with(None)

    @patch("glovebox.cli.commands.layout.glove80_sync.create_bookmark_service")
    def test_bookmark_list_with_bookmarks(
        self, mock_create_service, runner, mock_bookmark_service, mock_app_context
    ):
        """Test listing bookmarks when some exist."""
        mock_create_service.return_value = mock_bookmark_service

        # Mock bookmarks
        user_bookmark = LayoutBookmark(
            uuid="12345678-1234-1234-1234-123456789012",
            name="user-layout",
            title="User Layout",
            source=BookmarkSource.USER,
        )
        factory_bookmark = LayoutBookmark(
            uuid="87654321-4321-4321-4321-210987654321",
            name="factory-layout",
            title="Factory Layout",
            source=BookmarkSource.FACTORY,
        )
        mock_bookmark_service.list_bookmarks.return_value = [
            user_bookmark,
            factory_bookmark,
        ]

        result = runner.invoke(
            glove80_group, ["bookmark", "list"], obj=mock_app_context
        )

        assert result.exit_code == 0
        assert "user-layout" in result.stdout
        assert "factory-layout" in result.stdout
        assert "User Layout" in result.stdout
        assert "Factory Layout" in result.stdout

    @patch("glovebox.cli.commands.layout.glove80_sync.create_bookmark_service")
    def test_bookmark_list_factory_only(
        self, mock_create_service, runner, mock_bookmark_service, mock_app_context
    ):
        """Test listing only factory bookmarks."""
        mock_create_service.return_value = mock_bookmark_service

        factory_bookmark = LayoutBookmark(
            uuid="87654321-4321-4321-4321-210987654321",
            name="factory-layout",
            title="Factory Layout",
            source=BookmarkSource.FACTORY,
        )
        mock_bookmark_service.list_bookmarks.return_value = [factory_bookmark]

        result = runner.invoke(
            glove80_group, ["bookmark", "list", "--factory"], obj=mock_app_context
        )

        assert result.exit_code == 0
        assert "factory-layout" in result.stdout
        mock_bookmark_service.list_bookmarks.assert_called_once_with(
            BookmarkSource.FACTORY
        )

    @patch("glovebox.cli.commands.layout.glove80_sync.create_bookmark_service")
    def test_bookmark_list_user_only(
        self, mock_create_service, runner, mock_bookmark_service, mock_app_context
    ):
        """Test listing only user bookmarks."""
        mock_create_service.return_value = mock_bookmark_service

        user_bookmark = LayoutBookmark(
            uuid="12345678-1234-1234-1234-123456789012",
            name="user-layout",
            title="User Layout",
            source=BookmarkSource.USER,
        )
        mock_bookmark_service.list_bookmarks.return_value = [user_bookmark]

        result = runner.invoke(
            glove80_group, ["bookmark", "list", "--user"], obj=mock_app_context
        )

        assert result.exit_code == 0
        assert "user-layout" in result.stdout
        mock_bookmark_service.list_bookmarks.assert_called_once_with(
            BookmarkSource.USER
        )

    @patch("glovebox.cli.commands.layout.glove80_sync.create_bookmark_service")
    def test_bookmark_add_success(
        self, mock_create_service, runner, mock_bookmark_service, mock_app_context
    ):
        """Test adding a bookmark successfully."""
        mock_create_service.return_value = mock_bookmark_service

        added_bookmark = LayoutBookmark(
            uuid="12345678-1234-1234-1234-123456789012",
            name="test-layout",
            title="Test Layout",
            source=BookmarkSource.USER,
        )
        mock_bookmark_service.add_bookmark.return_value = added_bookmark

        result = runner.invoke(
            glove80_group,
            [
                "bookmark",
                "add",
                "12345678-1234-1234-1234-123456789012",
                "test-layout",
                "--description",
                "Test description",
            ],
            obj=mock_app_context,
        )

        assert result.exit_code == 0
        assert "Added bookmark" in result.stdout
        assert "test-layout" in result.stdout
        mock_bookmark_service.add_bookmark.assert_called_once_with(
            "12345678-1234-1234-1234-123456789012",
            "test-layout",
            "Test description",
            True,
        )

    @patch("glovebox.cli.commands.layout.glove80_sync.create_bookmark_service")
    def test_bookmark_add_no_metadata(
        self, mock_create_service, runner, mock_bookmark_service, mock_app_context
    ):
        """Test adding a bookmark without fetching metadata."""
        mock_create_service.return_value = mock_bookmark_service

        added_bookmark = LayoutBookmark(
            uuid="12345678-1234-1234-1234-123456789012",
            name="test-layout",
            source=BookmarkSource.USER,
        )
        mock_bookmark_service.add_bookmark.return_value = added_bookmark

        result = runner.invoke(
            glove80_group,
            [
                "bookmark",
                "add",
                "12345678-1234-1234-1234-123456789012",
                "test-layout",
                "--no-metadata",
            ],
            obj=mock_app_context,
        )

        assert result.exit_code == 0
        mock_bookmark_service.add_bookmark.assert_called_once_with(
            "12345678-1234-1234-1234-123456789012", "test-layout", None, False
        )

    @patch("glovebox.cli.commands.layout.glove80_sync.create_bookmark_service")
    def test_bookmark_add_exception(
        self, mock_create_service, runner, mock_bookmark_service, mock_app_context
    ):
        """Test adding a bookmark with exception."""
        mock_create_service.return_value = mock_bookmark_service
        mock_bookmark_service.add_bookmark.side_effect = Exception("API Error")

        result = runner.invoke(
            glove80_group,
            ["bookmark", "add", "12345678-1234-1234-1234-123456789012", "test-layout"],
            obj=mock_app_context,
        )

        assert result.exit_code == 1
        assert "Error adding bookmark" in result.stdout

    @patch("glovebox.cli.commands.layout.glove80_sync.create_bookmark_service")
    def test_bookmark_remove_success(
        self, mock_create_service, runner, mock_bookmark_service, mock_app_context
    ):
        """Test removing a bookmark successfully."""
        mock_create_service.return_value = mock_bookmark_service
        mock_bookmark_service.remove_bookmark.return_value = True

        result = runner.invoke(
            glove80_group, ["bookmark", "remove", "test-layout"], obj=mock_app_context
        )

        assert result.exit_code == 0
        assert "Removed bookmark" in result.stdout
        assert "test-layout" in result.stdout
        mock_bookmark_service.remove_bookmark.assert_called_once_with("test-layout")

    @patch("glovebox.cli.commands.layout.glove80_sync.create_bookmark_service")
    def test_bookmark_remove_not_found(
        self, mock_create_service, runner, mock_bookmark_service, mock_app_context
    ):
        """Test removing a bookmark that doesn't exist."""
        mock_create_service.return_value = mock_bookmark_service
        mock_bookmark_service.remove_bookmark.return_value = False

        result = runner.invoke(
            glove80_group, ["bookmark", "remove", "nonexistent"], obj=mock_app_context
        )

        assert result.exit_code == 1
        assert "Bookmark not found" in result.stdout
        assert "nonexistent" in result.stdout

    @patch("glovebox.cli.commands.layout.glove80_sync.create_bookmark_service")
    def test_bookmark_info_exists(
        self, mock_create_service, runner, mock_bookmark_service, mock_app_context
    ):
        """Test getting info for an existing bookmark."""
        mock_create_service.return_value = mock_bookmark_service

        bookmark = LayoutBookmark(
            uuid="12345678-1234-1234-1234-123456789012",
            name="test-layout",
            title="Test Layout",
            description="Test description",
            tags=["test", "layout"],
            source=BookmarkSource.USER,
        )
        mock_bookmark_service.get_bookmark.return_value = bookmark

        result = runner.invoke(
            glove80_group, ["bookmark", "info", "test-layout"], obj=mock_app_context
        )

        assert result.exit_code == 0
        assert "test-layout" in result.stdout
        assert "Test Layout" in result.stdout
        assert "Test description" in result.stdout
        assert "test, layout" in result.stdout
        mock_bookmark_service.get_bookmark.assert_called_once_with("test-layout")

    @patch("glovebox.cli.commands.layout.glove80_sync.create_bookmark_service")
    def test_bookmark_info_not_found(
        self, mock_create_service, runner, mock_bookmark_service, mock_app_context
    ):
        """Test getting info for a non-existent bookmark."""
        mock_create_service.return_value = mock_bookmark_service
        mock_bookmark_service.get_bookmark.return_value = None

        result = runner.invoke(
            glove80_group, ["bookmark", "info", "nonexistent"], obj=mock_app_context
        )

        assert result.exit_code == 1
        assert "Bookmark not found" in result.stdout
        assert "nonexistent" in result.stdout

    @patch("glovebox.cli.commands.layout.glove80_sync.load_layout_file")
    @patch("glovebox.cli.commands.layout.glove80_sync.create_bookmark_service")
    def test_bookmark_clone_success(
        self,
        mock_create_service,
        mock_load_layout,
        runner,
        mock_bookmark_service,
        mock_moergo_layout,
        mock_layout_data,
        mock_app_context,
    ):
        """Test cloning a bookmark to a file successfully."""
        mock_create_service.return_value = mock_bookmark_service
        mock_bookmark_service.get_layout_by_bookmark.return_value = mock_moergo_layout
        mock_load_layout.return_value = mock_layout_data

        output_file = Path("/tmp/test_output.json")

        result = runner.invoke(
            glove80_group,
            ["bookmark", "clone", "test-layout", str(output_file)],
            obj=mock_app_context,
        )

        assert result.exit_code == 0
        assert "Cloned bookmark" in result.stdout
        assert "test-layout" in result.stdout
        mock_bookmark_service.get_layout_by_bookmark.assert_called_once_with(
            "test-layout", True
        )

    @patch("glovebox.cli.commands.layout.glove80_sync.create_bookmark_service")
    def test_bookmark_clone_not_found(
        self, mock_create_service, runner, mock_bookmark_service, mock_app_context
    ):
        """Test cloning a non-existent bookmark."""
        mock_create_service.return_value = mock_bookmark_service
        mock_bookmark_service.get_layout_by_bookmark.side_effect = ValueError(
            "Bookmark not found"
        )

        result = runner.invoke(
            glove80_group,
            ["bookmark", "clone", "nonexistent", "/tmp/output.json"],
            obj=mock_app_context,
        )

        assert result.exit_code == 1
        assert "Error cloning bookmark" in result.stdout

    @patch("glovebox.cli.commands.layout.glove80_sync.create_bookmark_service")
    def test_bookmark_refresh_success(
        self, mock_create_service, runner, mock_bookmark_service, mock_app_context
    ):
        """Test refreshing factory bookmarks successfully."""
        mock_create_service.return_value = mock_bookmark_service
        mock_bookmark_service.refresh_factory_defaults.return_value = 5

        result = runner.invoke(
            glove80_group, ["bookmark", "refresh"], obj=mock_app_context
        )

        assert result.exit_code == 0
        assert "Refreshed 5 factory bookmarks" in result.stdout
        mock_bookmark_service.refresh_factory_defaults.assert_called_once()

    @patch("glovebox.cli.commands.layout.glove80_sync.create_bookmark_service")
    def test_bookmark_refresh_exception(
        self, mock_create_service, runner, mock_bookmark_service, mock_app_context
    ):
        """Test refreshing factory bookmarks with exception."""
        mock_create_service.return_value = mock_bookmark_service
        mock_bookmark_service.refresh_factory_defaults.side_effect = Exception(
            "API Error"
        )

        result = runner.invoke(
            glove80_group, ["bookmark", "refresh"], obj=mock_app_context
        )

        assert result.exit_code == 1
        assert "Error refreshing factory bookmarks" in result.stdout

    def test_bookmark_commands_registered(self):
        """Test that bookmark commands are properly registered."""
        # Check that the bookmark command group is added to glove80_group
        # This is a basic smoke test - detailed functionality is tested in integration tests
        assert hasattr(glove80_group, "registered_groups")
        # The bookmark group should be registered
        assert len(glove80_group.registered_groups) > 0
