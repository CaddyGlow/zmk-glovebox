"""Tests for library reference resolution in CLI parameters."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from glovebox.cli.helpers.library_resolver import (
    get_library_entries_for_completion,
    is_library_reference,
    is_valid_uuid,
    resolve_library_reference,
    resolve_parameter_value,
)
from glovebox.library.models import LibraryEntry, LibrarySource


class TestLibraryReferenceDetection:
    """Test library reference detection functions."""

    def test_is_library_reference_valid(self):
        """Test detection of valid library references."""
        assert is_library_reference("@my-layout") is True
        assert is_library_reference("@12345678-1234-1234-1234-123456789abc") is True
        assert is_library_reference("@") is True
        assert is_library_reference("@@double") is True

    def test_is_library_reference_invalid(self):
        """Test detection of non-library references."""
        assert is_library_reference("my-layout.json") is False
        assert is_library_reference("./path/to/file") is False
        assert is_library_reference("") is False
        assert is_library_reference(None) is False

    def test_is_valid_uuid(self):
        """Test UUID validation."""
        # Valid UUIDs
        assert is_valid_uuid("12345678-1234-1234-1234-123456789abc") is True
        assert is_valid_uuid(str(uuid4())) is True
        assert is_valid_uuid("12345678-1234-5678-9abc-def012345678") is True

        # Invalid UUIDs
        assert is_valid_uuid("not-a-uuid") is False
        assert is_valid_uuid("12345678-1234-1234-1234") is False
        assert is_valid_uuid("") is False
        assert is_valid_uuid("g2345678-1234-1234-1234-123456789abc") is False


class TestLibraryReferenceResolution:
    """Test library reference resolution."""

    @pytest.fixture
    def mock_library_service(self, tmp_path):
        """Create a mock library service with test entries."""
        layout_file = tmp_path / "test-layout.json"
        layout_file.write_text(json.dumps({"title": "Test Layout"}))

        entry = LibraryEntry(
            uuid="12345678-1234-1234-1234-123456789abc",
            name="test-layout",
            title="Test Layout",
            creator="Test User",
            source=LibrarySource.MOERGO_UUID,
            source_reference="moergo:12345678-1234-1234-1234-123456789abc",
            file_path=layout_file,
            downloaded_at=datetime.now(),
        )

        service = MagicMock()
        service.get_layout_entry.return_value = entry
        service.get_layout_entry_by_name.return_value = entry
        service.list_local_layouts.return_value = [entry]

        return service

    @pytest.fixture
    def mock_moergo_client(self):
        """Create a mock MoErgo client."""
        client = MagicMock()
        client.get_layout_meta.return_value = {
            "layout_meta": {
                "title": "Remote Layout",
                "creator": "Remote User",
                "tags": ["test"],
                "compiled": True,
            }
        }
        return client

    def test_resolve_by_name(self, mock_library_service):
        """Test resolving library reference by name."""
        with patch(
            "glovebox.cli.helpers.library_resolver.create_library_service",
            return_value=mock_library_service,
        ):
            result = resolve_library_reference("@test-layout")
            assert (
                result
                == mock_library_service.get_layout_entry_by_name.return_value.file_path
            )
            mock_library_service.get_layout_entry_by_name.assert_called_once_with(
                "test-layout"
            )

    def test_resolve_by_uuid(self, mock_library_service):
        """Test resolving library reference by UUID."""
        with patch(
            "glovebox.cli.helpers.library_resolver.create_library_service",
            return_value=mock_library_service,
        ):
            uuid = "12345678-1234-1234-1234-123456789abc"
            result = resolve_library_reference(f"@{uuid}")
            assert (
                result == mock_library_service.get_layout_entry.return_value.file_path
            )
            mock_library_service.get_layout_entry.assert_called_once_with(uuid)

    def test_resolve_not_found_locally(self, mock_library_service):
        """Test error when reference not found locally and MoErgo disabled."""
        mock_library_service.get_layout_entry.return_value = None
        mock_library_service.get_layout_entry_by_name.return_value = None

        with patch(
            "glovebox.cli.helpers.library_resolver.create_library_service",
            return_value=mock_library_service,
        ):
            with pytest.raises(ValueError) as exc_info:
                resolve_library_reference("@missing-layout", fetch_from_moergo=False)
            assert "Could not resolve library reference" in str(exc_info.value)

    def test_resolve_with_moergo_fallback(
        self, mock_library_service, mock_moergo_client, tmp_path
    ):
        """Test MoErgo API fallback when UUID not found locally."""
        # Setup: UUID not found locally
        mock_library_service.get_layout_entry.return_value = None

        # Setup: Successful MoErgo fetch
        fetched_file = tmp_path / "fetched-layout.json"
        fetched_file.write_text(json.dumps({"title": "Fetched Layout"}))

        fetched_entry = LibraryEntry(
            uuid="87654321-4321-4321-4321-210987654321",
            name="fetched-layout",
            title="Fetched Layout",
            creator="MoErgo User",
            source=LibrarySource.MOERGO_UUID,
            source_reference="moergo:87654321-4321-4321-4321-210987654321",
            file_path=fetched_file,
            downloaded_at=datetime.now(),
        )

        mock_library_service.fetch_layout.return_value = MagicMock(
            success=True,
            entry=fetched_entry,
        )

        # Mock user config with API key
        mock_user_config = MagicMock()
        mock_user_config._config.moergo_api_key = "test-api-key"

        with (
            patch(
                "glovebox.cli.helpers.library_resolver.create_library_service",
                return_value=mock_library_service,
            ),
            patch(
                "glovebox.cli.helpers.library_resolver.create_user_config",
                return_value=mock_user_config,
            ),
            patch(
                "glovebox.cli.helpers.library_resolver.create_moergo_client",
                return_value=mock_moergo_client,
            ),
        ):
            uuid = "87654321-4321-4321-4321-210987654321"
            result = resolve_library_reference(f"@{uuid}")
            assert result == fetched_file
            mock_moergo_client.get_layout_meta.assert_called_once_with(
                uuid, use_cache=False
            )

    def test_resolve_parameter_value_with_reference(self, mock_library_service):
        """Test resolve_parameter_value with library reference."""
        with patch(
            "glovebox.cli.helpers.library_resolver.create_library_service",
            return_value=mock_library_service,
        ):
            result = resolve_parameter_value("@test-layout")
            assert isinstance(result, Path)

    def test_resolve_parameter_value_without_reference(self):
        """Test resolve_parameter_value with regular path."""
        result = resolve_parameter_value("my-layout.json")
        assert result == "my-layout.json"

    def test_resolve_parameter_value_none(self):
        """Test resolve_parameter_value with None."""
        result = resolve_parameter_value(None)
        assert result is None


class TestLibraryCompletion:
    """Test library entry completion."""

    def test_get_library_entries_for_completion(self, tmp_path):
        """Test getting library entries for tab completion."""
        layout_file = tmp_path / "test-layout.json"
        layout_file.write_text(json.dumps({"title": "Test Layout"}))

        entries = [
            LibraryEntry(
                uuid="11111111-1111-1111-1111-111111111111",
                name="layout-one",
                title="Layout One",
                creator="User One",
                source=LibrarySource.MOERGO_UUID,
                source_reference="moergo:11111111-1111-1111-1111-111111111111",
                file_path=layout_file,
                downloaded_at=datetime.now(),
            ),
            LibraryEntry(
                uuid="22222222-2222-2222-2222-222222222222",
                name="layout-two",
                title="Layout Two",
                creator="User Two",
                source=LibrarySource.MOERGO_UUID,
                source_reference="moergo:22222222-2222-2222-2222-222222222222",
                file_path=layout_file,
                downloaded_at=datetime.now(),
            ),
        ]

        mock_service = MagicMock()
        mock_service.list_local_layouts.return_value = entries

        with patch(
            "glovebox.cli.helpers.library_resolver.create_library_service",
            return_value=mock_service,
        ):
            completions = get_library_entries_for_completion()

            # Should have 2 entries × 2 references (name + UUID) = 4 total
            assert len(completions) == 4

            # Check name references
            assert ("@layout-one", "Layout One (by User One)") in completions
            assert ("@layout-two", "Layout Two (by User Two)") in completions

            # Check UUID references
            assert (
                "@11111111-1111-1111-1111-111111111111",
                "Layout One (UUID)",
            ) in completions
            assert (
                "@22222222-2222-2222-2222-222222222222",
                "Layout Two (UUID)",
            ) in completions

    def test_get_library_entries_handles_errors(self):
        """Test completion handles errors gracefully."""
        with patch(
            "glovebox.cli.helpers.library_resolver.create_library_service",
            side_effect=Exception("Service error"),
        ):
            completions = get_library_entries_for_completion()
            assert completions == []
