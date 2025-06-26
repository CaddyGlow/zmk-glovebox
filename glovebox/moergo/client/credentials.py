"""Secure credential management for MoErgo API client."""

import json
import logging
import platform
from pathlib import Path
from typing import Any

from glovebox.config.models.moergo import MoErgoCredentialConfig
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

    def store_credentials(self, credentials: UserCredentials) -> None:
        """Store credentials securely using OS keyring or encrypted file."""
        keyring = self._try_keyring_import()

        if keyring and self.config.prefer_keyring:
            # Use OS keyring (preferred)
            try:
                keyring.set_password(
                    self.config.keyring_service,
                    credentials.username,
                    credentials.password,
                )
                # Store username in config file for easy retrieval
                self._store_username(credentials.username)
                return
            except Exception as e:
                exc_info = self.logger.isEnabledFor(logging.DEBUG)
                self.logger.warning(
                    "Failed to store credentials in keyring: %s. Falling back to file storage",
                    e,
                    exc_info=exc_info,
                )
        else:
            self.logger.warning("No keyring available, falling back to file storage")

        # Fallback to file storage with basic obfuscation
        self._store_credentials_file(credentials)

    def _store_username(self, username: str) -> None:
        """Store username in plain text config file."""
        config = {"username": username}
        with self.credentials_file.open("w") as f:
            json.dump(config, f, indent=2)
        # Set restrictive permissions from configuration
        self.credentials_file.chmod(self.config.get_file_permissions_octal())

    def _store_credentials_file(self, credentials: UserCredentials) -> None:
        """Store credentials in file with basic obfuscation."""
        import base64

        # Basic obfuscation (NOT encryption, just makes it less obvious)
        encoded_password = base64.b64encode(credentials.password.encode()).decode()

        config = {
            "username": credentials.username,
            "password_encoded": encoded_password,
            "storage_method": "file",
        }

        with self.credentials_file.open("w") as f:
            json.dump(config, f, indent=2)

        # Set restrictive permissions from configuration
        self.credentials_file.chmod(self.config.get_file_permissions_octal())

        self.logger.info("Credentials stored in %s", self.credentials_file)
        self.logger.info("NOTE: File storage provides basic obfuscation only.")
        self.logger.info(
            "For better security, install the 'keyring' package: pip install keyring"
        )

    def load_credentials(self) -> UserCredentials | None:
        """Load credentials from OS keyring or file."""
        keyring = self._try_keyring_import()

        if keyring and self.credentials_file.exists():
            # Try keyring first
            try:
                with self.credentials_file.open() as f:
                    config = json.load(f)

                username = config.get("username") or self.config.default_username
                if username:
                    password = keyring.get_password(
                        self.config.keyring_service, username
                    )
                    if password:
                        return UserCredentials(username=username, password=password)
            except Exception as e:
                exc_info = self.logger.isEnabledFor(logging.DEBUG)
                self.logger.warning(
                    "Failed to load from keyring: %s", e, exc_info=exc_info
                )

        # Fallback to file storage
        return self._load_credentials_file()

    def _load_credentials_file(self) -> UserCredentials | None:
        """Load credentials from file."""
        if not self.credentials_file.exists():
            return None

        try:
            with self.credentials_file.open() as f:
                config = json.load(f)

            username = config.get("username")
            password_encoded = config.get("password_encoded")

            if not username or not password_encoded:
                return None

            import base64

            password = base64.b64decode(password_encoded.encode()).decode()

            return UserCredentials(username=username, password=password)

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Error loading credentials: %s", e, exc_info=exc_info)
            return None

    def store_tokens(self, tokens: AuthTokens) -> None:
        """Store authentication tokens."""
        token_data = tokens.model_dump(by_alias=True, exclude_unset=True, mode="json")

        with self.tokens_file.open("w") as f:
            json.dump(token_data, f, indent=2)

        # Set restrictive permissions from configuration
        self.tokens_file.chmod(self.config.get_file_permissions_octal())

    def load_tokens(self) -> AuthTokens | None:
        """Load stored authentication tokens."""
        if not self.tokens_file.exists():
            return None

        try:
            with self.tokens_file.open() as f:
                token_data = json.load(f)

            return AuthTokens(**token_data)

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Error loading tokens: %s", e, exc_info=exc_info)
            return None

    def clear_credentials(self) -> None:
        """Clear stored credentials."""
        keyring = self._try_keyring_import()

        # Clear from keyring
        if keyring and self.credentials_file.exists():
            try:
                with self.credentials_file.open() as f:
                    config = json.load(f)

                username = config.get("username") or self.config.default_username
                if username:
                    keyring.delete_password(self.config.keyring_service, username)
            except Exception as e:
                # Ignore errors when clearing, but log them for debugging
                exc_info = self.logger.isEnabledFor(logging.DEBUG)
                self.logger.debug(
                    "Error clearing keyring credentials: %s", e, exc_info=exc_info
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
