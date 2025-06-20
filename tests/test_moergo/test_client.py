"""Tests for MoErgo API client."""

import json
import tempfile
import zlib
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

from glovebox.moergo.client import (
    APIError,
    AuthenticationError,
    AuthTokens,
    CompilationError,
    CredentialManager,
    FirmwareCompileRequest,
    FirmwareCompileResponse,
    MoErgoClient,
    MoErgoLayout,
    NetworkError,
    TimeoutError,
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
            client.get_layout("test-uuid-123", use_cache=False)

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
                client.get_layout("test-uuid-123", use_cache=False)

    @patch("requests.Session.get")
    def test_handle_empty_response(self, mock_get, client, mock_auth_response):
        """Test handling of empty server response."""
        # Setup authentication
        with patch.object(
            client.auth_client, "simple_login_attempt", return_value=mock_auth_response
        ):
            client.login("test@example.com", "testpass123")

        # Mock empty response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b""
        mock_response.text = ""
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This should handle empty response gracefully
        result = client._handle_response(mock_response)
        assert result == {"success": True, "status": "empty_response"}

    @patch("requests.Session.get")
    def test_handle_invalid_json_response(self, mock_get, client, mock_auth_response):
        """Test handling of invalid JSON response with proper error message."""
        # Setup authentication
        with patch.object(
            client.auth_client, "simple_login_attempt", return_value=mock_auth_response
        ):
            client.login("test@example.com", "testpass123")

        # Mock invalid JSON response (non-empty content that isn't valid JSON)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = Mock()
        mock_response.content.strip.return_value = b"invalid json content"
        mock_response.text = "invalid json content"
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status = Mock()
        # Mock json() to raise ValueError
        mock_response.json.side_effect = ValueError(
            "Expecting value: line 1 column 1 (char 0)"
        )
        mock_get.return_value = mock_response

        with pytest.raises(APIError) as exc_info:
            client._handle_response(mock_response)

        error_message = str(exc_info.value)
        assert "Server returned invalid JSON response" in error_message
        assert "Status: 200" in error_message
        assert "Content-Type: text/html" in error_message
        assert "invalid json content" in error_message

    @patch("requests.Session.get")
    def test_handle_empty_content_json_parsing_error(
        self, mock_get, client, mock_auth_response
    ):
        """Test handling of whitespace-only response that fails JSON parsing."""
        # Setup authentication
        with patch.object(
            client.auth_client, "simple_login_attempt", return_value=mock_auth_response
        ):
            client.login("test@example.com", "testpass123")

        # Mock response with only whitespace
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"   \n  "
        mock_response.text = "   \n  "
        mock_response.headers = {"content-type": "application/json"}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # This should handle whitespace-only response as empty
        result = client._handle_response(mock_response)
        assert result == {"success": True, "status": "empty_response"}

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

    def test_refresh_token_success(self, client, mock_auth_response):
        """Test successful token refresh."""
        # Setup initial authentication
        with patch.object(
            client.auth_client, "simple_login_attempt", return_value=mock_auth_response
        ):
            client.login("test@example.com", "testpass123")

        # Mock refresh token response
        refresh_response = {
            "AuthenticationResult": {
                "AccessToken": "new-access-token",
                "IdToken": "new-id-token",
                "TokenType": "Bearer",
                "ExpiresIn": 3600,
                # Note: RefreshToken might not be returned in real AWS responses
            }
        }

        # Simulate token near expiry and test refresh
        with (
            patch.object(client, "_is_token_expired", return_value=True),
            patch.object(
                client.auth_client, "refresh_token", return_value=refresh_response
            ),
        ):
            client._ensure_authenticated()

            # Verify tokens were updated
            assert client._tokens.access_token == "new-access-token"
            assert client._tokens.id_token == "new-id-token"

    def test_refresh_token_fallback_to_full_auth(self, client, mock_auth_response):
        """Test falling back to full authentication when refresh fails."""
        # Setup initial authentication
        with patch.object(
            client.auth_client, "simple_login_attempt", return_value=mock_auth_response
        ):
            client.login("test@example.com", "testpass123")

        # Mock refresh token failure and successful full auth
        with (
            patch.object(client, "_is_token_expired", return_value=True),
            patch.object(client.auth_client, "refresh_token", return_value=None),
            patch.object(
                client.auth_client,
                "simple_login_attempt",
                return_value=mock_auth_response,
            ),
        ):
            client._ensure_authenticated()

            # Should have fallen back to full auth and updated tokens
            assert client._tokens.access_token == "access_token_123"

    def test_proactive_token_renewal_needed(self, client, mock_auth_response):
        """Test proactive token renewal when token is close to expiry."""
        # Setup initial authentication
        with patch.object(
            client.auth_client, "simple_login_attempt", return_value=mock_auth_response
        ):
            client.login("test@example.com", "testpass123")

        # Mock datetime to make token appear expired within buffer
        with patch("glovebox.moergo.client.base_client.datetime") as mock_datetime:
            # Set current time to make token expire within buffer
            mock_datetime.now.return_value.timestamp.return_value = (
                client._tokens.expires_at + 1  # Past expiry time
            )

            with patch.object(client, "_authenticate") as mock_auth:
                result = client.renew_token_if_needed(buffer_minutes=1)

                assert result is True
                mock_auth.assert_called_once()

    def test_proactive_token_renewal_not_needed(self, client, mock_auth_response):
        """Test proactive token renewal when token is still valid."""
        # Setup initial authentication
        with patch.object(
            client.auth_client, "simple_login_attempt", return_value=mock_auth_response
        ):
            client.login("test@example.com", "testpass123")

        # Mock datetime to make token appear valid (far from expiry)
        with patch("glovebox.moergo.client.base_client.datetime") as mock_datetime:
            # Set current time well before token expiry
            mock_datetime.now.return_value.timestamp.return_value = (
                client._tokens.expires_at - 3600  # 1 hour before expiry
            )

            result = client.renew_token_if_needed(buffer_minutes=10)

            assert result is False

    def test_get_token_info_authenticated(self, client, mock_auth_response):
        """Test getting token info when authenticated."""
        # Setup initial authentication
        with patch.object(
            client.auth_client, "simple_login_attempt", return_value=mock_auth_response
        ):
            client.login("test@example.com", "testpass123")

        # Get the actual expires_at time from the token
        expires_at = client._tokens.expires_at

        with patch("glovebox.moergo.client.base_client.datetime") as mock_datetime:
            # Set current time to 10 minutes before expiry
            current_time = expires_at - 600  # 10 minutes before
            mock_datetime.now.return_value.timestamp.return_value = current_time
            mock_datetime.fromtimestamp.return_value.isoformat.return_value = (
                "2025-01-01T00:00:00"
            )

            info = client.get_token_info()

            assert info["authenticated"] is True
            assert "expires_at" in info
            assert info["expires_in_minutes"] == 10.0
            assert info["needs_renewal"] is False

    def test_get_token_info_not_authenticated(self, client):
        """Test getting token info when not authenticated."""
        info = client.get_token_info()

        assert info["authenticated"] is False
        assert info["expires_at"] is None
        assert info["expires_in_minutes"] is None
        assert info["needs_renewal"] is True


class TestFirmwareCompilation:
    """Test firmware compilation and download functionality."""

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

    @pytest.fixture
    def authenticated_client(self, client, mock_auth_response):
        """Create authenticated client."""
        with patch.object(
            client.auth_client, "simple_login_attempt", return_value=mock_auth_response
        ):
            client.login("test@example.com", "testpass123")
        return client

    def test_compile_firmware_success(self, authenticated_client):
        """Test successful firmware compilation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"location": "/firmware/test.uf2.gz"}
        mock_response.raise_for_status = Mock()

        with patch.object(
            authenticated_client.session, "post", return_value=mock_response
        ):
            result = authenticated_client.compile_firmware(
                layout_uuid="test-uuid",
                keymap="test keymap content",
                kconfig="CONFIG_ZMK_SLEEP=y",
                board="glove80",
            )

            assert isinstance(result, FirmwareCompileResponse)
            assert result.location == "/firmware/test.uf2.gz"

    def test_compile_firmware_timeout(self, authenticated_client):
        """Test firmware compilation timeout."""
        with patch.object(authenticated_client.session, "post") as mock_post:
            mock_post.side_effect = requests.exceptions.Timeout("Request timed out")

            with pytest.raises(TimeoutError):
                authenticated_client.compile_firmware(
                    layout_uuid="test-uuid",
                    keymap="test keymap",
                    timeout=1,
                    max_retries=1,
                )

    def test_compile_firmware_compilation_error(self, authenticated_client):
        """Test firmware compilation error handling."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "message": "Compilation failed",
            "detail": ["Error on line 1", "Syntax error"],
        }
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError()

        with patch.object(
            authenticated_client.session, "post", return_value=mock_response
        ):
            with pytest.raises(CompilationError) as exc_info:
                authenticated_client.compile_firmware(
                    layout_uuid="test-uuid",
                    keymap="invalid keymap",
                )

            assert "Compilation failed" in str(exc_info.value)
            assert exc_info.value.detail == ["Error on line 1", "Syntax error"]

    def test_compile_firmware_retry_logic(self, authenticated_client):
        """Test retry logic on timeout."""
        # First two calls timeout, third succeeds
        timeout_response = requests.exceptions.Timeout("Request timed out")
        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {"location": "/firmware/test.uf2.gz"}
        success_response.raise_for_status = Mock()

        with patch.object(authenticated_client.session, "post") as mock_post:
            mock_post.side_effect = [
                timeout_response,
                timeout_response,
                success_response,
            ]

            with patch("time.sleep"):  # Speed up test by mocking sleep
                result = authenticated_client.compile_firmware(
                    layout_uuid="test-uuid",
                    keymap="test keymap",
                    max_retries=3,
                    initial_retry_delay=0.1,
                )

                assert result.location == "/firmware/test.uf2.gz"
                assert mock_post.call_count == 3

    def test_download_firmware_compressed(self, authenticated_client):
        """Test downloading compressed firmware (.gz file)."""
        # Create test firmware data and compress it
        test_firmware = b"test firmware content"
        compressed_firmware = zlib.compress(test_firmware)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = compressed_firmware
        mock_response.raise_for_status = Mock()

        with patch.object(
            authenticated_client.session, "get", return_value=mock_response
        ):
            result = authenticated_client.download_firmware("/firmware/test.uf2.gz")

            assert result == test_firmware

    def test_download_firmware_uncompressed(self, authenticated_client):
        """Test downloading uncompressed firmware (non-.gz file)."""
        test_firmware = b"test firmware content"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = test_firmware
        mock_response.raise_for_status = Mock()

        with patch.object(
            authenticated_client.session, "get", return_value=mock_response
        ):
            result = authenticated_client.download_firmware("/firmware/test.uf2")

            assert result == test_firmware

    def test_download_firmware_decompression_error(self, authenticated_client):
        """Test handling decompression error for .gz files."""
        # Invalid compressed data
        invalid_compressed_data = b"invalid compressed data"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = invalid_compressed_data
        mock_response.raise_for_status = Mock()

        with patch.object(
            authenticated_client.session, "get", return_value=mock_response
        ):
            with pytest.raises(APIError) as exc_info:
                authenticated_client.download_firmware(
                    "/firmware/test.uf2.gz", use_cache=False
                )

            assert "Failed to decompress firmware data" in str(exc_info.value)

    def test_download_firmware_with_output_path(
        self, authenticated_client, temp_config_dir
    ):
        """Test downloading firmware and saving to file."""
        test_firmware = b"test firmware content"
        compressed_firmware = zlib.compress(test_firmware)
        output_path = temp_config_dir / "downloaded_firmware.uf2"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = compressed_firmware
        mock_response.raise_for_status = Mock()

        with patch.object(
            authenticated_client.session, "get", return_value=mock_response
        ):
            result = authenticated_client.download_firmware(
                "/firmware/test.uf2.gz", str(output_path)
            )

            assert result == test_firmware
            assert output_path.exists()
            assert output_path.read_bytes() == test_firmware

    def test_download_firmware_network_error(self, authenticated_client):
        """Test download firmware with network error."""
        with patch.object(authenticated_client.session, "get") as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError("Network error")

            with pytest.raises(NetworkError):
                authenticated_client.download_firmware(
                    "/firmware/test.uf2.gz", use_cache=False
                )
