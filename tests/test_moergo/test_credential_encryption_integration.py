"""Integration tests for credential encryption functionality."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from cryptography.fernet import Fernet

from glovebox.moergo.client.credentials import create_credential_manager
from glovebox.moergo.client.models import AuthTokens, UserCredentials
from glovebox.moergo.config import create_moergo_credential_config


class TestCredentialEncryptionIntegration:
    """Integration tests for the complete encryption workflow."""

    @pytest.fixture
    def temp_config_dir(self, tmp_path):
        """Create temporary config directory."""
        config_dir = tmp_path / ".glovebox"
        config_dir.mkdir(exist_ok=True)
        return config_dir

    @pytest.fixture
    def credential_config(self, temp_config_dir):
        """Create credential config with temp directory."""
        return create_moergo_credential_config(
            config_dir=temp_config_dir,
            prefer_keyring=True,
        )

    def test_full_encryption_workflow(self, credential_config):
        """Test complete workflow: store, load, clear credentials with encryption."""
        # Create two credential managers to simulate different sessions
        manager1 = create_credential_manager(credential_config)
        manager2 = create_credential_manager(credential_config)

        # Mock keyring for both managers
        mock_keyring = Mock()
        encryption_key = None

        def mock_set_password(service, key, value):
            if key == "encryption_key":
                nonlocal encryption_key
                encryption_key = value

        def mock_get_password(service, key):
            if key == "encryption_key":
                return encryption_key
            return None

        mock_keyring.set_password = mock_set_password
        mock_keyring.get_password = mock_get_password
        mock_keyring.delete_password = Mock()

        # Test data
        test_credentials = UserCredentials(
            username="integration@test.com", password="super_secret_password_123"
        )
        test_tokens = AuthTokens(
            access_token="access_integration_token",
            refresh_token="refresh_integration_token",
            id_token="id_integration_token",
            expires_in=7200,
        )

        # Store credentials and tokens with first manager
        with patch.object(manager1, "_try_keyring_import", return_value=mock_keyring):
            manager1.store_credentials(test_credentials)
            manager1.store_tokens(test_tokens)

            # Verify files were created
            assert manager1.credentials_file.exists()
            assert manager1.tokens_file.exists()

            # Verify encryption key was stored
            assert encryption_key is not None

            # Verify files contain encrypted data
            with manager1.credentials_file.open() as f:
                cred_data = json.load(f)
            assert "password_encrypted" in cred_data
            assert cred_data["storage_method"] == "encrypted"
            # Ensure password is not plaintext
            assert test_credentials.password not in cred_data["password_encrypted"]

            with manager1.tokens_file.open() as f:
                token_data = json.load(f)
            assert "tokens_encrypted" in token_data
            # Ensure tokens are not plaintext
            assert test_tokens.access_token not in token_data["tokens_encrypted"]

        # Load credentials and tokens with second manager (different session)
        with patch.object(manager2, "_try_keyring_import", return_value=mock_keyring):
            loaded_credentials = manager2.load_credentials()
            loaded_tokens = manager2.load_tokens()

            # Verify loaded data matches original
            assert loaded_credentials is not None
            assert loaded_credentials.username == test_credentials.username
            assert loaded_credentials.password == test_credentials.password

            assert loaded_tokens is not None
            assert loaded_tokens.access_token == test_tokens.access_token
            assert loaded_tokens.refresh_token == test_tokens.refresh_token
            assert loaded_tokens.id_token == test_tokens.id_token

            # Clear credentials
            manager2.clear_credentials()

            # Verify everything was cleared
            assert not manager2.credentials_file.exists()
            assert not manager2.tokens_file.exists()
            assert mock_keyring.delete_password.called

    def test_encryption_key_isolation(self, credential_config):
        """Test that different encryption keys cannot decrypt each other's data."""
        manager = create_credential_manager(credential_config)

        # Create two different encryption keys
        key1 = Fernet.generate_key()
        key2 = Fernet.generate_key()

        test_data = "sensitive_information"

        # Encrypt with key1
        encrypted1 = manager._encrypt_data(test_data, key1)

        # Try to decrypt with key2 (should fail)
        from cryptography.fernet import InvalidToken

        with pytest.raises(InvalidToken):  # Fernet will raise InvalidToken
            manager._decrypt_data(encrypted1, key2)

        # Decrypt with correct key should work
        decrypted = manager._decrypt_data(encrypted1, key1)
        assert decrypted == test_data

    def test_no_keyring_fallback(self, credential_config):
        """Test behavior when keyring is not available."""
        manager = create_credential_manager(credential_config)

        # Mock no keyring available
        with patch.object(manager, "_try_keyring_import", return_value=None):
            # Should raise error when trying to store without keyring
            test_credentials = UserCredentials(
                username="test@example.com", password="testpass"
            )

            with pytest.raises(
                RuntimeError, match="Cannot store credentials without encryption key"
            ):
                manager.store_credentials(test_credentials)

    def test_file_permissions(self, credential_config):
        """Test that credential files have correct permissions."""
        manager = create_credential_manager(credential_config)

        mock_keyring = Mock()
        mock_keyring.get_password.return_value = None
        mock_keyring.set_password = Mock()

        test_credentials = UserCredentials(
            username="perm@test.com", password="permission_test"
        )

        with patch.object(manager, "_try_keyring_import", return_value=mock_keyring):
            manager.store_credentials(test_credentials)

            # Check file permissions (should be 0o600)
            cred_stat = manager.credentials_file.stat()
            assert oct(cred_stat.st_mode)[-3:] == "600"
