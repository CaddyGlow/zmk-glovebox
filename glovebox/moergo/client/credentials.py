"""Secure credential management for MoErgo API client."""

import json
import os
import platform
from pathlib import Path
from typing import Any, Optional

from .models import AuthTokens, UserCredentials


class CredentialManager:
    """Manages secure storage of credentials using OS keyring or encrypted file."""

    def __init__(self, config_dir: Path | None = None):
        self.config_dir = config_dir or Path.home() / ".glovebox"
        self.config_dir.mkdir(exist_ok=True)
        self.credentials_file = self.config_dir / "moergo_credentials.json"
        self.tokens_file = self.config_dir / "moergo_tokens.json"

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

        if keyring:
            # Use OS keyring (preferred)
            try:
                keyring.set_password(
                    "glovebox-moergo", credentials.username, credentials.password
                )
                # Store username in config file for easy retrieval
                self._store_username(credentials.username)
                return
            except Exception as e:
                print(f"Warning: Failed to store credentials in keyring: {e}")
                print("Falling back to file storage...")

        # Fallback to file storage with basic obfuscation
        self._store_credentials_file(credentials)

    def _store_username(self, username: str) -> None:
        """Store username in plain text config file."""
        config = {"username": username}
        with self.credentials_file.open("w") as f:
            json.dump(config, f, indent=2)
        # Set restrictive permissions
        self.credentials_file.chmod(0o600)

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

        # Set restrictive permissions
        self.credentials_file.chmod(0o600)

        print(f"Credentials stored in {self.credentials_file}")
        print("NOTE: File storage provides basic obfuscation only.")
        print("For better security, install the 'keyring' package:")
        print("  pip install keyring")

    def load_credentials(self) -> UserCredentials | None:
        """Load credentials from OS keyring or file."""
        keyring = self._try_keyring_import()

        if keyring and self.credentials_file.exists():
            # Try keyring first
            try:
                with self.credentials_file.open() as f:
                    config = json.load(f)

                username = config.get("username")
                if username:
                    password = keyring.get_password("glovebox-moergo", username)
                    if password:
                        return UserCredentials(username=username, password=password)
            except Exception as e:
                print(f"Warning: Failed to load from keyring: {e}")

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
            print(f"Error loading credentials: {e}")
            return None

    def store_tokens(self, tokens: AuthTokens) -> None:
        """Store authentication tokens."""
        token_data = tokens.model_dump()

        with self.tokens_file.open("w") as f:
            json.dump(token_data, f, indent=2)

        # Set restrictive permissions
        self.tokens_file.chmod(0o600)

    def load_tokens(self) -> AuthTokens | None:
        """Load stored authentication tokens."""
        if not self.tokens_file.exists():
            return None

        try:
            with self.tokens_file.open() as f:
                token_data = json.load(f)

            return AuthTokens(**token_data)

        except Exception as e:
            print(f"Error loading tokens: {e}")
            return None

    def clear_credentials(self) -> None:
        """Clear stored credentials."""
        keyring = self._try_keyring_import()

        # Clear from keyring
        if keyring and self.credentials_file.exists():
            try:
                with self.credentials_file.open() as f:
                    config = json.load(f)

                username = config.get("username")
                if username:
                    keyring.delete_password("glovebox-moergo", username)
            except Exception:
                pass  # Ignore errors when clearing

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
            "platform": platform.system(),
            "config_dir": str(self.config_dir),
            "has_credentials": self.has_credentials(),
        }

        if keyring:
            try:
                backend = keyring.get_keyring()
                info["keyring_backend"] = str(type(backend).__name__)
            except Exception:
                info["keyring_backend"] = "unknown"

        return info
