"""Tests for MoErgo API client."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

from glovebox.moergo.client import (
    APIError,
    AuthenticationError,
    AuthTokens,
    CredentialManager,
    MoErgoClient,
    MoErgoLayout,
    NetworkError,
    UserCredentials,
)


class TestCredentialManager:
    """Test credential management functionality."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary config directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def credential_manager(self, temp_config_dir):
        """Create credential manager with temp directory."""
        return CredentialManager(config_dir=temp_config_dir)

    def test_store_and_load_credentials_file_fallback(self, credential_manager):
        """Test storing and loading credentials with file fallback."""
        credentials = UserCredentials(
            username="test@example.com", password="testpass123"
        )

        # Mock keyring to not be available
        with patch.object(credential_manager, "_try_keyring_import", return_value=None):
            credential_manager.store_credentials(credentials)

        loaded = credential_manager.load_credentials()
        assert loaded is not None
        assert loaded.username == credentials.username
        assert loaded.password == credentials.password

    def test_store_and_load_tokens(self, credential_manager):
        """Test storing and loading auth tokens."""
        tokens = AuthTokens(
            access_token="access123",
            refresh_token="refresh123",
            id_token="id123",
            expires_in=3600,
        )

        credential_manager.store_tokens(tokens)
        loaded = credential_manager.load_tokens()

        assert loaded is not None
        assert loaded.access_token == tokens.access_token
        assert loaded.refresh_token == tokens.refresh_token
        assert loaded.id_token == tokens.id_token

    def test_clear_credentials(self, credential_manager):
        """Test clearing stored credentials."""
        credentials = UserCredentials(
            username="test@example.com", password="testpass123"
        )
        tokens = AuthTokens(
            access_token="access123",
            refresh_token="refresh123",
            id_token="id123",
            expires_in=3600,
        )

        with patch.object(credential_manager, "_try_keyring_import", return_value=None):
            credential_manager.store_credentials(credentials)
        credential_manager.store_tokens(tokens)

        assert credential_manager.has_credentials()

        credential_manager.clear_credentials()

        assert not credential_manager.has_credentials()
        assert credential_manager.load_tokens() is None

    def test_has_credentials(self, credential_manager):
        """Test checking if credentials exist."""
        assert not credential_manager.has_credentials()

        credentials = UserCredentials(
            username="test@example.com", password="testpass123"
        )
        with patch.object(credential_manager, "_try_keyring_import", return_value=None):
            credential_manager.store_credentials(credentials)

        assert credential_manager.has_credentials()

    def test_keyring_storage_success(self, credential_manager):
        """Test successful keyring storage."""
        mock_keyring_module = Mock()
        mock_keyring_module.set_password = Mock()
        mock_keyring_module.get_password = Mock(return_value="testpass123")

        with patch.object(
            credential_manager, "_try_keyring_import", return_value=mock_keyring_module
        ):
            credentials = UserCredentials(
                username="test@example.com", password="testpass123"
            )
            credential_manager.store_credentials(credentials)

            mock_keyring_module.set_password.assert_called_once_with(
                "glovebox-moergo", "test@example.com", "testpass123"
            )

            loaded = credential_manager.load_credentials()
            assert loaded is not None
            assert loaded.username == "test@example.com"
            assert loaded.password == "testpass123"


class TestMoErgoClient:
    """Test MoErgo API client functionality."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary config directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def credential_manager(self, temp_config_dir):
        """Create credential manager with temp directory."""
        return CredentialManager(config_dir=temp_config_dir)

    @pytest.fixture
    def client(self, credential_manager):
        """Create MoErgo client with mocked credential manager."""
        return MoErgoClient(credential_manager=credential_manager)

    @pytest.fixture
    def mock_auth_response(self):
        """Mock successful authentication response."""
        return {
            "AuthenticationResult": {
                "AccessToken": "access_token_123",
                "RefreshToken": "refresh_token_123",
                "IdToken": "id_token_123",
                "TokenType": "Bearer",
                "ExpiresIn": 3600,
            }
        }

    def test_login_success(self, client, mock_auth_response):
        """Test successful login."""
        with patch.object(
            client.auth_client, "simple_login_attempt", return_value=mock_auth_response
        ):
            client.login("test@example.com", "testpass123")

            # Check that credentials were stored
            assert client.credential_manager.has_credentials()

            # Check that tokens were stored
            tokens = client.credential_manager.load_tokens()
            assert tokens is not None
            assert tokens.access_token == "access_token_123"

    def test_login_failure(self, client):
        """Test login failure."""
        with (
            patch.object(client.auth_client, "simple_login_attempt", return_value=None),
            pytest.raises(AuthenticationError),
        ):
            client.login("test@example.com", "wrongpass")

    def test_logout(self, client, mock_auth_response):
        """Test logout functionality."""
        # First login
        with patch.object(
            client.auth_client, "simple_login_attempt", return_value=mock_auth_response
        ):
            client.login("test@example.com", "testpass123")

        assert client.credential_manager.has_credentials()

        # Then logout
        client.logout()

        assert not client.credential_manager.has_credentials()
        assert client._tokens is None

    @patch("requests.Session.get")
    def test_get_layout_success(self, mock_get, client, mock_auth_response):
        """Test successful layout retrieval."""
        # Setup authentication
        with patch.object(
            client.auth_client, "simple_login_attempt", return_value=mock_auth_response
        ):
            client.login("test@example.com", "testpass123")

        # Mock API response
        layout_data = {
            "layout_meta": {
                "uuid": "test-uuid-123",
                "date": 1748441847,
                "creator": "test_user",
                "firmware_api_version": "1",
                "title": "Test Layout",
                "notes": "Test notes",
                "tags": ["test"],
                "unlisted": False,
                "deleted": False,
                "compiled": True,
                "searchable": True,
            },
            "config": {
                "keyboard": "glove80",
                "title": "Test Layout",
                "firmware_api_version": "1",
                "locale": "en-US",
                "uuid": "",
                "layers": [[]],  # At least one empty layer required
            },
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = layout_data
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        layout = client.get_layout("test-uuid-123")

        assert isinstance(layout, MoErgoLayout)
        assert layout.layout_meta.uuid == "test-uuid-123"
        assert layout.layout_meta.title == "Test Layout"
        assert layout.config.keyboard == "glove80"

    @patch("requests.Session.get")
    def test_get_layout_authentication_error(self, mock_get, client):
        """Test layout retrieval with authentication error."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Unauthorized"}
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError()
        mock_get.return_value = mock_response

        with pytest.raises(AuthenticationError):
            client.get_layout("test-uuid-123")

    def test_get_layout_network_error(self, client, mock_auth_response):
        """Test layout retrieval with network error."""
        # Setup authentication
        with patch.object(
            client.auth_client, "simple_login_attempt", return_value=mock_auth_response
        ):
            client.login("test@example.com", "testpass123")

        # Mock both _ensure_authenticated and session.get
        with (
            patch.object(client, "_ensure_authenticated"),
            patch.object(client.session, "get") as mock_get,
        ):
            mock_get.side_effect = requests.exceptions.ConnectionError("Network error")

            with pytest.raises(NetworkError):
                client.get_layout("test-uuid-123")

    def test_is_authenticated_true(self, client, mock_auth_response):
        """Test authentication check returns True when authenticated."""
        with patch.object(
            client.auth_client, "simple_login_attempt", return_value=mock_auth_response
        ):
            client.login("test@example.com", "testpass123")

        assert client.is_authenticated()

    def test_is_authenticated_false(self, client):
        """Test authentication check returns False when not authenticated."""
        assert not client.is_authenticated()

    def test_get_credential_info(self, client):
        """Test getting credential storage information."""
        info = client.get_credential_info()

        assert "keyring_available" in info
        assert "platform" in info
        assert "config_dir" in info
        assert "has_credentials" in info
