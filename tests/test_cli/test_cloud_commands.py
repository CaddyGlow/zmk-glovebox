"""Unit tests for cloud CLI commands."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pytest
import typer
from typer.testing import CliRunner

from glovebox.cli.commands.cloud import cloud_app
from glovebox.layout.models import LayoutData
from glovebox.moergo.client import LayoutMeta, MoErgoLayout


class TestCloudCommands:
    """Test cloud CLI commands."""

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
    def mock_moergo_client(self):
        """Create a mock MoErgo client."""
        client = Mock()
        client.validate_authentication.return_value = True
        return client

    @pytest.fixture
    def mock_layout_data(self):
        """Create mock layout data."""
        layout_data = Mock(spec=LayoutData)
        layout_data.title = "Test Layout"
        layout_data.model_dump_json.return_value = '{"title": "Test Layout"}'
        return layout_data

    @pytest.fixture
    def mock_moergo_layout(self):
        """Create a mock MoErgo layout."""
        layout_meta = LayoutMeta(
            uuid="12345678-1234-1234-1234-123456789012",
            date=1234567890,
            creator="test-user",
            title="Test Layout",
            notes="Test description",
            tags=["test"],
            firmware_api_version="v25.05",
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

    @patch("glovebox.cli.commands.cloud.create_moergo_client")
    @patch("glovebox.cli.commands.cloud.load_layout_file")
    def test_upload_success(
        self,
        mock_load_layout,
        mock_create_client,
        runner,
        mock_moergo_client,
        mock_layout_data,
        mock_app_context,
        tmp_path,
    ):
        """Test uploading a layout successfully."""
        mock_create_client.return_value = mock_moergo_client
        mock_load_layout.return_value = mock_layout_data

        # Create a temporary layout file
        layout_file = tmp_path / "test_layout.json"
        layout_file.write_text('{"title": "Test Layout"}')

        mock_moergo_client.save_layout.return_value = {}

        result = runner.invoke(
            cloud_app,
            ["upload", str(layout_file), "--title", "Test Layout"],
            obj=mock_app_context,
        )

        assert result.exit_code == 0
        assert "uploaded successfully" in result.stdout
        mock_moergo_client.save_layout.assert_called_once()

    @patch("glovebox.cli.commands.cloud.create_moergo_client")
    def test_upload_authentication_failed(
        self, mock_create_client, runner, mock_app_context, tmp_path
    ):
        """Test upload with authentication failure."""
        mock_client = Mock()
        mock_client.validate_authentication.return_value = False
        mock_create_client.return_value = mock_client

        # Create a temporary layout file
        layout_file = tmp_path / "test_layout.json"
        layout_file.write_text('{"title": "Test Layout"}')

        result = runner.invoke(
            cloud_app,
            ["upload", str(layout_file)],
            obj=mock_app_context,
        )

        assert result.exit_code == 1
        assert "Authentication failed" in result.stdout

    @patch("glovebox.cli.commands.cloud.create_moergo_client")
    def test_download_success(
        self,
        mock_create_client,
        runner,
        mock_moergo_client,
        mock_moergo_layout,
        mock_app_context,
        tmp_path,
    ):
        """Test downloading a layout successfully."""
        mock_create_client.return_value = mock_moergo_client
        mock_moergo_client.get_layout.return_value = mock_moergo_layout

        output_file = tmp_path / "downloaded_layout.json"

        result = runner.invoke(
            cloud_app,
            [
                "download",
                "12345678-1234-1234-1234-123456789012",
                str(output_file),
            ],
            obj=mock_app_context,
        )

        assert result.exit_code == 0
        assert "Downloaded to:" in result.stdout
        mock_moergo_client.get_layout.assert_called_once_with(
            "12345678-1234-1234-1234-123456789012"
        )

    @patch("glovebox.cli.commands.cloud.create_moergo_client")
    def test_list_layouts_success(
        self, mock_create_client, runner, mock_moergo_client, mock_app_context
    ):
        """Test listing user layouts successfully."""
        mock_create_client.return_value = mock_moergo_client

        mock_layouts = [
            {"uuid": "12345678-1234-1234-1234-123456789012", "title": "Layout 1"},
            {"uuid": "87654321-4321-4321-4321-210987654321", "title": "Layout 2"},
        ]
        mock_moergo_client.list_user_layouts.return_value = mock_layouts

        result = runner.invoke(
            cloud_app,
            ["list"],
            obj=mock_app_context,
        )

        assert result.exit_code == 0
        assert "12345678-1234-1234-1234-123456789012" in result.stdout
        assert "87654321-4321-4321-4321-210987654321" in result.stdout
        assert "Found 2 layouts" in result.stdout

    @patch("glovebox.cli.commands.cloud.create_moergo_client")
    def test_delete_success(
        self,
        mock_create_client,
        runner,
        mock_moergo_client,
        mock_moergo_layout,
        mock_app_context,
    ):
        """Test deleting a layout successfully."""
        mock_create_client.return_value = mock_moergo_client
        mock_moergo_client.get_layout.return_value = mock_moergo_layout
        mock_moergo_client.delete_layout.return_value = True

        result = runner.invoke(
            cloud_app,
            ["delete", "12345678-1234-1234-1234-123456789012", "--force"],
            obj=mock_app_context,
        )

        assert result.exit_code == 0
        assert "deleted successfully" in result.stdout
        mock_moergo_client.get_layout.assert_called_once_with(
            "12345678-1234-1234-1234-123456789012"
        )
        mock_moergo_client.delete_layout.assert_called_once_with(
            "12345678-1234-1234-1234-123456789012"
        )

    def test_cloud_commands_registered(self):
        """Test that cloud commands are properly registered."""
        # Check that the cloud_app has the expected commands
        # This is a basic smoke test - detailed functionality is tested in integration tests
        assert hasattr(cloud_app, "registered_commands")
        # The cloud commands should be registered
        assert len(cloud_app.registered_commands) > 0
