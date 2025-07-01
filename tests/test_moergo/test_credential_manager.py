"""Comprehensive tests for MoErgo credential manager with encryption."""

import base64
import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from cryptography.fernet import Fernet

from glovebox.moergo.client.credentials import (
    CredentialManager,
    create_credential_manager,
)
from glovebox.moergo.client.models import AuthTokens, UserCredentials
from glovebox.moergo.config import (
    MoErgoCredentialConfig,
    create_moergo_credential_config,
)


class TestCredentialManager:
    """Test credential management functionality with encryption."""

    @pytest.fixture
    def credential_config(self, tmp_path):
        """Create MoErgo credential configuration with temporary directory."""
        return create_moergo_credential_config(
            config_dir=tmp_path,
            username="test@example.com",
            prefer_keyring=True,
        )

    @pytest.fixture
    def credential_manager(self, credential_config):
        """Create credential manager with test configuration."""
        return create_credential_manager(credential_config)

    @pytest.fixture
    def mock_keyring_with_key(self):
        """Mock keyring module with existing encryption key."""
        mock_keyring = Mock()
        # Generate a valid Fernet key
        test_key = Fernet.generate_key()
        encoded_key = base64.b64encode(test_key).decode()
        mock_keyring.get_password.return_value = encoded_key
        mock_keyring.set_password = Mock()
        mock_keyring.delete_password = Mock()
        return mock_keyring

    @pytest.fixture
    def mock_keyring_without_key(self):
        """Mock keyring module without existing encryption key."""
        mock_keyring = Mock()
        mock_keyring.get_password.return_value = None
        mock_keyring.set_password = Mock()
        mock_keyring.delete_password = Mock()
        return mock_keyring

    def test_create_credential_manager_factory(self, credential_config):
        """Test factory function creates proper instance."""
        manager = create_credential_manager(credential_config)
        assert isinstance(manager, CredentialManager)
        assert manager.config == credential_config

    def test_store_and_load_credentials_with_encryption(
        self, credential_manager, mock_keyring_with_key
    ):
        """Test storing and loading credentials with encryption."""
        credentials = UserCredentials(
            username="test@example.com", password="testpass123"
        )

        with patch.object(
            credential_manager,
            "_try_keyring_import",
            return_value=mock_keyring_with_key,
        ):
            # Store credentials
            credential_manager.store_credentials(credentials)

            # Verify file was created with correct permissions
            assert credential_manager.credentials_file.exists()
            assert (
                oct(credential_manager.credentials_file.stat().st_mode)[-3:]
                == oct(credential_manager.config.get_file_permissions_octal())[-3:]
            )

            # Verify file contains encrypted data
            with credential_manager.credentials_file.open() as f:
                data = json.load(f)
            assert "username" in data
            assert "password_encrypted" in data
            assert "storage_method" in data
            assert data["storage_method"] == "encrypted"
            # Password should be encrypted, not plain text
            assert data["password_encrypted"] != "testpass123"

            # Load credentials
            loaded = credential_manager.load_credentials()
            assert loaded is not None
            assert loaded.username == credentials.username
            assert loaded.password == credentials.password

    def test_store_credentials_generates_new_key(
        self, credential_manager, mock_keyring_without_key
    ):
        """Test that storing credentials generates new encryption key if none exists."""
        credentials = UserCredentials(
            username="test@example.com", password="testpass123"
        )

        with patch.object(
            credential_manager,
            "_try_keyring_import",
            return_value=mock_keyring_without_key,
        ):
            credential_manager.store_credentials(credentials)

            # Verify keyring.set_password was called to store new key
            mock_keyring_without_key.set_password.assert_called_once()
            call_args = mock_keyring_without_key.set_password.call_args[0]
            assert call_args[0] == credential_manager.config.keyring_service
            assert call_args[1] == "encryption_key"
            # Verify the stored key is a valid base64-encoded Fernet key
            stored_key_b64 = call_args[2]
            stored_key = base64.b64decode(stored_key_b64)
            # This should not raise an error if it's a valid key
            Fernet(stored_key)

    def test_store_credentials_no_keyring_raises_error(self, credential_manager):
        """Test that storing credentials without keyring availability raises error."""
        credentials = UserCredentials(
            username="test@example.com", password="testpass123"
        )

        with patch.object(credential_manager, "_try_keyring_import", return_value=None):
            with pytest.raises(RuntimeError) as exc_info:
                credential_manager.store_credentials(credentials)
            assert "Cannot store credentials without encryption key" in str(
                exc_info.value
            )

    def test_load_credentials_no_file_returns_none(self, credential_manager):
        """Test loading credentials when no file exists returns None."""
        assert not credential_manager.credentials_file.exists()
        result = credential_manager.load_credentials()
        assert result is None

    def test_load_credentials_no_keyring_returns_none(
        self, credential_manager, mock_keyring_with_key
    ):
        """Test loading credentials without keyring returns None."""
        credentials = UserCredentials(
            username="test@example.com", password="testpass123"
        )

        # First store with keyring available
        with patch.object(
            credential_manager,
            "_try_keyring_import",
            return_value=mock_keyring_with_key,
        ):
            credential_manager.store_credentials(credentials)

        # Then try to load without keyring
        with patch.object(credential_manager, "_try_keyring_import", return_value=None):
            result = credential_manager.load_credentials()
            assert result is None

    def test_load_credentials_invalid_file_returns_none(
        self, credential_manager, mock_keyring_with_key
    ):
        """Test loading credentials with invalid file returns None."""
        # Create invalid credentials file
        credential_manager.credentials_file.write_text("invalid json")

        with patch.object(
            credential_manager,
            "_try_keyring_import",
            return_value=mock_keyring_with_key,
        ):
            # Should return None for invalid JSON without raising exception
            result = credential_manager.load_credentials()
            assert result is None

    def test_store_and_load_tokens_with_encryption(
        self, credential_manager, mock_keyring_with_key
    ):
        """Test storing and loading auth tokens with encryption."""
        tokens = AuthTokens(
            access_token="access123",
            refresh_token="refresh123",
            id_token="id123",
            expires_in=3600,
        )

        with patch.object(
            credential_manager,
            "_try_keyring_import",
            return_value=mock_keyring_with_key,
        ):
            # Store tokens
            credential_manager.store_tokens(tokens)

            # Verify file was created with correct permissions
            assert credential_manager.tokens_file.exists()
            assert (
                oct(credential_manager.tokens_file.stat().st_mode)[-3:]
                == oct(credential_manager.config.get_file_permissions_octal())[-3:]
            )

            # Verify file contains encrypted data
            with credential_manager.tokens_file.open() as f:
                data = json.load(f)
            assert "tokens_encrypted" in data
            # Tokens should be encrypted
            assert "access123" not in data["tokens_encrypted"]

            # Load tokens
            loaded = credential_manager.load_tokens()
            assert loaded is not None
            assert loaded.access_token == tokens.access_token
            assert loaded.refresh_token == tokens.refresh_token
            assert loaded.id_token == tokens.id_token

    def test_store_tokens_no_keyring_raises_error(self, credential_manager):
        """Test that storing tokens without keyring availability raises error."""
        tokens = AuthTokens(
            access_token="access123",
            refresh_token="refresh123",
            id_token="id123",
            expires_in=3600,
        )

        with patch.object(credential_manager, "_try_keyring_import", return_value=None):
            with pytest.raises(RuntimeError) as exc_info:
                credential_manager.store_tokens(tokens)
            assert "Cannot store tokens without encryption key" in str(exc_info.value)

    def test_load_tokens_no_file_returns_none(self, credential_manager):
        """Test loading tokens when no file exists returns None."""
        assert not credential_manager.tokens_file.exists()
        result = credential_manager.load_tokens()
        assert result is None

    def test_load_tokens_invalid_file_returns_none(
        self, credential_manager, mock_keyring_with_key
    ):
        """Test loading tokens with invalid file returns None."""
        # Create invalid tokens file
        credential_manager.tokens_file.write_text("invalid json")

        with patch.object(
            credential_manager,
            "_try_keyring_import",
            return_value=mock_keyring_with_key,
        ):
            # Should return None for invalid JSON without raising exception
            result = credential_manager.load_tokens()
            assert result is None

    def test_clear_credentials(self, credential_manager, mock_keyring_with_key):
        """Test clearing stored credentials and encryption key."""
        credentials = UserCredentials(
            username="test@example.com", password="testpass123"
        )
        tokens = AuthTokens(
            access_token="access123",
            refresh_token="refresh123",
            id_token="id123",
            expires_in=3600,
        )

        with patch.object(
            credential_manager,
            "_try_keyring_import",
            return_value=mock_keyring_with_key,
        ):
            # Store credentials and tokens
            credential_manager.store_credentials(credentials)
            credential_manager.store_tokens(tokens)

            assert credential_manager.has_credentials()
            assert credential_manager.credentials_file.exists()
            assert credential_manager.tokens_file.exists()

            # Clear everything
            credential_manager.clear_credentials()

            # Verify keyring.delete_password was called
            mock_keyring_with_key.delete_password.assert_called_once_with(
                credential_manager.config.keyring_service, "encryption_key"
            )

            # Verify files were deleted
            assert not credential_manager.credentials_file.exists()
            assert not credential_manager.tokens_file.exists()
            assert not credential_manager.has_credentials()

    def test_clear_credentials_keyring_error_continues(
        self, credential_manager, mock_keyring_with_key
    ):
        """Test that clear_credentials continues even if keyring deletion fails."""
        credentials = UserCredentials(
            username="test@example.com", password="testpass123"
        )

        # Setup keyring to fail on delete
        mock_keyring_with_key.delete_password.side_effect = Exception("Keyring error")

        with patch.object(
            credential_manager,
            "_try_keyring_import",
            return_value=mock_keyring_with_key,
        ):
            credential_manager.store_credentials(credentials)
            assert credential_manager.credentials_file.exists()

            # Clear should continue despite keyring error
            credential_manager.clear_credentials()

            # Files should still be deleted even if keyring fails
            assert not credential_manager.credentials_file.exists()
            assert not credential_manager.tokens_file.exists()

    def test_has_credentials(self, credential_manager, mock_keyring_with_key):
        """Test checking if credentials exist."""
        assert not credential_manager.has_credentials()

        credentials = UserCredentials(
            username="test@example.com", password="testpass123"
        )
        with patch.object(
            credential_manager,
            "_try_keyring_import",
            return_value=mock_keyring_with_key,
        ):
            credential_manager.store_credentials(credentials)
            assert credential_manager.has_credentials()

    def test_get_storage_info(self, credential_manager, mock_keyring_with_key):
        """Test getting storage information."""
        # Mock keyring backend
        mock_backend = Mock()
        mock_backend.__class__.__name__ = "TestKeyringBackend"
        mock_keyring_with_key.get_keyring.return_value = mock_backend

        with patch.object(
            credential_manager,
            "_try_keyring_import",
            return_value=mock_keyring_with_key,
        ):
            info = credential_manager.get_storage_info()

        assert info["keyring_available"] is True
        assert info["keyring_preferred"] == credential_manager.config.prefer_keyring
        assert info["keyring_service"] == credential_manager.config.keyring_service
        assert info["platform"] is not None
        assert info["config_dir"] == str(credential_manager.config.config_dir)
        assert info["credentials_file"] == str(credential_manager.credentials_file)
        assert info["tokens_file"] == str(credential_manager.tokens_file)
        assert info["file_permissions"] == credential_manager.config.file_permissions
        assert "has_credentials" in info
        assert info["encryption_enabled"] is True
        assert info["encryption_method"] == "Fernet (AES-128-CBC + HMAC)"
        assert info["keyring_backend"] == "TestKeyringBackend"

    def test_get_storage_info_no_keyring(self, credential_manager):
        """Test getting storage info when keyring is not available."""
        with patch.object(credential_manager, "_try_keyring_import", return_value=None):
            info = credential_manager.get_storage_info()

        assert info["keyring_available"] is False
        assert "keyring_backend" not in info

    def test_get_storage_info_keyring_backend_error(
        self, credential_manager, mock_keyring_with_key
    ):
        """Test getting storage info when keyring backend retrieval fails."""
        mock_keyring_with_key.get_keyring.side_effect = Exception("Backend error")

        with patch.object(
            credential_manager,
            "_try_keyring_import",
            return_value=mock_keyring_with_key,
        ):
            info = credential_manager.get_storage_info()

        assert info["keyring_backend"] == "unknown"

    def test_encryption_decryption_roundtrip(self, credential_manager):
        """Test encryption and decryption work correctly."""
        test_data = "sensitive password data"
        key = Fernet.generate_key()

        encrypted = credential_manager._encrypt_data(test_data, key)
        assert encrypted != test_data
        assert isinstance(encrypted, str)

        decrypted = credential_manager._decrypt_data(encrypted, key)
        assert decrypted == test_data

    def test_encryption_with_different_keys_fails(self, credential_manager):
        """Test that decryption with wrong key fails."""
        test_data = "sensitive data"
        key1 = Fernet.generate_key()
        key2 = Fernet.generate_key()

        encrypted = credential_manager._encrypt_data(test_data, key1)

        from cryptography.fernet import InvalidToken

        with pytest.raises(InvalidToken):
            credential_manager._decrypt_data(encrypted, key2)

    def test_keyring_import_error_returns_none(self, credential_manager):
        """Test that keyring import error is handled gracefully."""
        with patch("builtins.__import__", side_effect=ImportError("No module")):
            result = credential_manager._try_keyring_import()
            assert result is None

    def test_generate_encryption_key_creates_valid_key(self, credential_manager):
        """Test that generated encryption keys are valid Fernet keys."""
        key = credential_manager._generate_encryption_key()
        assert isinstance(key, bytes)
        # This should not raise an error if it's a valid key
        Fernet(key)

    def test_get_or_create_encryption_key_error_handling(self, credential_manager):
        """Test error handling in get_or_create_encryption_key."""
        mock_keyring = Mock()
        mock_keyring.get_password.side_effect = Exception("Keyring access error")

        with patch.object(
            credential_manager, "_try_keyring_import", return_value=mock_keyring
        ):
            # Should return None when keyring operations fail
            result = credential_manager._get_or_create_encryption_key()
            assert result is None
