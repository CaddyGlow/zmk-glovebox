"""Secure credential management for MoErgo API client."""

import base64
import json
import logging
import platform
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet

from glovebox.moergo.config import MoErgoCredentialConfig
from glovebox.services.base_service import BaseService

from .models import AuthTokens, UserCredentials


class CredentialManager(BaseService):
    """Manages secure storage of credentials using OS keyring or encrypted file."""

    def __init__(self, credential_config: MoErgoCredentialConfig | None = None):
        super().__init__("CredentialManager", "1.0.0")
        self.logger = logging.getLogger(__name__)
        self.config = credential_config or MoErgoCredentialConfig()

        # Ensure config directory exists
        self.config.config_dir.mkdir(parents=True, exist_ok=True)

        # Get file paths from configuration
        self.credentials_file = self.config.get_credentials_path()
        self.tokens_file = self.config.get_tokens_path()

    def _try_keyring_import(self) -> Any | None:
        """Try to import keyring, return None if not available."""
        try:
            import keyring

            return keyring
        except ImportError:
            return None

    def _generate_encryption_key(self) -> bytes:
        """Generate a new Fernet encryption key."""
        return Fernet.generate_key()

    def _get_or_create_encryption_key(self) -> bytes | None:
        """Get encryption key from keyring or create new one."""
        keyring = self._try_keyring_import()
        if not keyring:
            self.logger.warning("No keyring available for encryption key storage")
            return None

        try:
            # Try to get existing key
            key_b64 = keyring.get_password(
                self.config.keyring_service, "encryption_key"
            )
            if key_b64:
                return base64.b64decode(key_b64)

            # Generate new key
            key = self._generate_encryption_key()
            keyring.set_password(
                self.config.keyring_service,
                "encryption_key",
                base64.b64encode(key).decode(),
            )
            return key
        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to manage encryption key: %s", e, exc_info=exc_info
            )
            return None

    def _encrypt_data(self, data: str, key: bytes) -> str:
        """Encrypt string data with Fernet."""
        f = Fernet(key)
        return base64.b64encode(f.encrypt(data.encode())).decode()

    def _decrypt_data(self, encrypted: str, key: bytes) -> str:
        """Decrypt string data with Fernet."""
        f = Fernet(key)
        return f.decrypt(base64.b64decode(encrypted)).decode()

    def store_credentials(self, credentials: UserCredentials) -> None:
        """Store credentials using encryption."""
        # Get or create encryption key
        key = self._get_or_create_encryption_key()
        if not key:
            raise RuntimeError("Cannot store credentials without encryption key")

        # Encrypt password
        encrypted_password = self._encrypt_data(credentials.password, key)

        # Store encrypted credentials
        config = {
            "username": credentials.username,
            "password_encrypted": encrypted_password,
            "storage_method": "encrypted",
        }

        with self.credentials_file.open("w") as f:
            json.dump(config, f, indent=2)

        # Set restrictive permissions
        self.credentials_file.chmod(self.config.get_file_permissions_octal())
        self.logger.info("Credentials stored with encryption")

    def load_credentials(self) -> UserCredentials | None:
        """Load and decrypt credentials."""
        if not self.credentials_file.exists():
            return None

        # Get encryption key
        key = self._get_or_create_encryption_key()
        if not key:
            self.logger.error("Cannot load credentials without encryption key")
            return None

        try:
            with self.credentials_file.open() as f:
                config = json.load(f)

            username = config.get("username")
            encrypted_password = config.get("password_encrypted")

            if not username or not encrypted_password:
                return None

            # Decrypt password
            password = self._decrypt_data(encrypted_password, key)

            return UserCredentials(username=username, password=password)

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Error loading credentials: %s", e, exc_info=exc_info)
            return None

    def store_tokens(self, tokens: AuthTokens) -> None:
        """Store authentication tokens with encryption."""
        # Get encryption key
        key = self._get_or_create_encryption_key()
        if not key:
            raise RuntimeError("Cannot store tokens without encryption key")

        # Serialize tokens
        token_data = tokens.model_dump(by_alias=True, exclude_unset=True, mode="json")
        token_json = json.dumps(token_data)

        # Encrypt and store
        encrypted_tokens = self._encrypt_data(token_json, key)

        with self.tokens_file.open("w") as f:
            json.dump({"tokens_encrypted": encrypted_tokens}, f, indent=2)

        # Set restrictive permissions
        self.tokens_file.chmod(self.config.get_file_permissions_octal())

    def load_tokens(self) -> AuthTokens | None:
        """Load and decrypt authentication tokens."""
        if not self.tokens_file.exists():
            return None

        # Get encryption key
        key = self._get_or_create_encryption_key()
        if not key:
            return None

        try:
            with self.tokens_file.open() as f:
                data = json.load(f)

            encrypted_tokens = data.get("tokens_encrypted")
            if not encrypted_tokens:
                return None

            # Decrypt tokens
            token_json = self._decrypt_data(encrypted_tokens, key)
            token_data = json.loads(token_json)

            return AuthTokens(**token_data)

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Error loading tokens: %s", e, exc_info=exc_info)
            return None

    def clear_credentials(self) -> None:
        """Clear stored credentials and encryption key."""
        keyring = self._try_keyring_import()

        # Clear encryption key from keyring
        if keyring:
            try:
                keyring.delete_password(self.config.keyring_service, "encryption_key")
            except Exception as e:
                exc_info = self.logger.isEnabledFor(logging.DEBUG)
                self.logger.debug(
                    "Error clearing encryption key: %s", e, exc_info=exc_info
                )

        # Clear files
        for file_path in [self.credentials_file, self.tokens_file]:
            if file_path.exists():
                file_path.unlink()

    def has_credentials(self) -> bool:
        """Check if credentials are stored."""
        return self.load_credentials() is not None

    def get_storage_info(self) -> dict[str, Any]:
        """Get information about credential storage."""
        keyring = self._try_keyring_import()

        info: dict[str, Any] = {
            "keyring_available": keyring is not None,
            "keyring_preferred": self.config.prefer_keyring,
            "keyring_service": self.config.keyring_service,
            "platform": platform.system(),
            "config_dir": str(self.config.config_dir),
            "credentials_file": str(self.credentials_file),
            "tokens_file": str(self.tokens_file),
            "file_permissions": self.config.file_permissions,
            "has_credentials": self.has_credentials(),
            "encryption_enabled": True,
            "encryption_method": "Fernet (AES-128-CBC + HMAC)",
        }

        if keyring:
            try:
                backend = keyring.get_keyring()
                info["keyring_backend"] = str(type(backend).__name__)
            except Exception:
                info["keyring_backend"] = "unknown"

        return info


def create_credential_manager(
    credential_config: MoErgoCredentialConfig | None = None,
) -> CredentialManager:
    """Create a CredentialManager instance with the given configuration.

    Factory function following CLAUDE.md patterns for creating
    CredentialManager instances with proper configuration.

    Args:
        credential_config: MoErgo credential configuration (defaults to default config)

    Returns:
        CredentialManager: Configured credential manager instance
    """
    return CredentialManager(credential_config)
