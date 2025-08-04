"""MoErgo service configuration models.

This module contains configuration models for the MoErgo domain,
following domain-driven design principles where domains own their configuration.
"""

from pathlib import Path
from typing import Any

from pydantic import Field, field_validator

from glovebox.models.base import GloveboxBaseModel


class MoErgoCredentialConfig(GloveboxBaseModel):
    """Configuration for MoErgo API credentials and storage.

    This model defines where and how MoErgo credentials are stored,
    providing flexibility for different deployment scenarios.
    """

    # Base configuration directory for MoErgo files
    config_dir: Path = Field(
        default_factory=lambda: Path.home() / ".glovebox",
        description="Directory for storing MoErgo configuration and credential files",
    )

    # Specific credential file paths (relative to config_dir if not absolute)
    credentials_file: str = Field(
        default="moergo_credentials.json",
        description="Filename for storing MoErgo user credentials",
    )

    tokens_file: str = Field(
        default="moergo_tokens.json",
        description="Filename for storing MoErgo authentication tokens",
    )

    # Default username (can be overridden)
    default_username: str | None = Field(
        default=None,
        description="Default username for MoErgo authentication",
    )

    # Storage preferences
    prefer_keyring: bool = Field(
        default=True,
        description="Prefer OS keyring for credential storage when available",
    )

    # Keyring service name
    keyring_service: str = Field(
        default="glovebox-moergo",
        description="Service name used for OS keyring credential storage",
    )

    # File permissions for credential files (octal as string)
    file_permissions: str = Field(
        default="600",
        description="File permissions for credential files (octal, e.g., '600')",
    )

    @field_validator("config_dir", mode="before")
    @classmethod
    def validate_config_dir(cls, v: str | Path) -> Path:
        """Validate and expand config directory path."""
        if isinstance(v, str):
            path = Path(v).expanduser()
        else:
            path = v.expanduser()
        return path.resolve()

    @field_validator("file_permissions")
    @classmethod
    def validate_file_permissions(cls, v: str) -> str:
        """Validate file permissions are valid octal."""
        try:
            # Test that it's valid octal
            int(v, 8)
            return v
        except ValueError as e:
            raise ValueError(
                f"File permissions must be valid octal (e.g., '600', '644'): {v}"
            ) from e

    def get_credentials_path(self) -> Path:
        """Get the full path to the credentials file."""
        cred_path = Path(self.credentials_file)
        if cred_path.is_absolute():
            return cred_path
        return self.config_dir / self.credentials_file

    def get_tokens_path(self) -> Path:
        """Get the full path to the tokens file."""
        tokens_path = Path(self.tokens_file)
        if tokens_path.is_absolute():
            return tokens_path
        return self.config_dir / self.tokens_file

    def get_file_permissions_octal(self) -> int:
        """Get file permissions as octal integer."""
        return int(self.file_permissions, 8)


class MoErgoCognitoConfig(GloveboxBaseModel):
    """Configuration for MoErgo Cognito authentication.

    This model configures AWS Cognito authentication settings for MoErgo API access.
    """

    # AWS Cognito configuration
    client_id: str = Field(
        default="3hvr36st4kdb6p7kasi1cdnson",
        description="AWS Cognito client ID for MoErgo authentication",
    )

    cognito_url: str = Field(
        default="https://cognito-idp.us-east-1.amazonaws.com/",
        description="AWS Cognito identity provider URL",
    )

    # Request configuration
    request_timeout: int = Field(
        default=30,
        description="Request timeout for Cognito authentication (seconds)",
    )

    # User agent and browser simulation
    user_agent: str = Field(
        default="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        description="User agent string for Cognito requests",
    )

    origin_url: str = Field(
        default="https://my.glove80.com",
        description="Origin URL for CORS headers",
    )

    referer_url: str = Field(
        default="https://my.glove80.com/",
        description="Referer URL for authentication requests",
    )

    # AWS Amplify configuration
    aws_amplify_version: str = Field(
        default="aws-amplify/5.0.4 js",
        description="AWS Amplify version string for requests",
    )

    @field_validator("request_timeout")
    @classmethod
    def validate_request_timeout(cls, v: int) -> int:
        """Validate request timeout is positive."""
        if v <= 0:
            raise ValueError("Request timeout must be positive")
        return v

    @field_validator("cognito_url", "origin_url", "referer_url")
    @classmethod
    def validate_urls(cls, v: str) -> str:
        """Validate URLs are properly formatted."""
        v = v.strip()
        if not v:
            raise ValueError("URL cannot be empty")

        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")

        return v

    @field_validator("client_id")
    @classmethod
    def validate_client_id(cls, v: str) -> str:
        """Validate client ID is not empty."""
        v = v.strip()
        if not v:
            raise ValueError("Client ID cannot be empty")
        return v


class MoErgoServiceConfig(GloveboxBaseModel):
    """Configuration for MoErgo service integration.

    This model configures how the application interacts with MoErgo services,
    including API endpoints, credential management, and service preferences.
    """

    # API configuration
    api_base_url: str = Field(
        default="https://my.glove80.com",
        description="Base URL for MoErgo API service",
    )

    # Credential configuration
    credentials: MoErgoCredentialConfig = Field(
        default_factory=MoErgoCredentialConfig,
        description="Configuration for credential storage and management",
    )

    # Cognito authentication configuration
    cognito: MoErgoCognitoConfig = Field(
        default_factory=MoErgoCognitoConfig,
        description="Configuration for AWS Cognito authentication",
    )

    # Timeout settings (in seconds)
    connection_timeout: int = Field(
        default=30,
        description="Connection timeout for MoErgo API requests (seconds)",
    )

    request_timeout: int = Field(
        default=60,
        description="Request timeout for MoErgo API operations (seconds)",
    )

    @field_validator("connection_timeout", "request_timeout")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        """Validate timeout values are positive."""
        if v <= 0:
            raise ValueError("Timeout values must be positive integers")
        return v

    @field_validator("api_base_url")
    @classmethod
    def validate_api_base_url(cls, v: str) -> str:
        """Validate API base URL format."""
        v = v.strip()
        if not v:
            raise ValueError("API base URL cannot be empty")

        # Ensure it starts with http:// or https://
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("API base URL must start with http:// or https://")

        # Remove trailing slash for consistency
        return v.rstrip("/")


def create_default_moergo_config() -> MoErgoServiceConfig:
    """Create default MoErgo service configuration.

    Factory function following CLAUDE.md patterns for creating
    default MoErgo service configuration instances.

    Returns:
        MoErgoServiceConfig: Default configuration instance
    """
    return MoErgoServiceConfig()


def create_moergo_credential_config(
    config_dir: Path | None = None,
    username: str | None = None,
    prefer_keyring: bool = True,
) -> MoErgoCredentialConfig:
    """Create MoErgo credential configuration with custom settings.

    Factory function for creating MoErgo credential configuration
    with common customization options.

    Args:
        config_dir: Custom configuration directory (defaults to ~/.glovebox)
        username: Default username for authentication
        prefer_keyring: Whether to prefer OS keyring for credential storage

    Returns:
        MoErgoCredentialConfig: Configured credential configuration
    """
    config = MoErgoCredentialConfig(
        default_username=username,
        prefer_keyring=prefer_keyring,
    )

    if config_dir is not None:
        config.config_dir = config_dir

    return config


def create_moergo_cognito_config(
    client_id: str | None = None,
    cognito_url: str | None = None,
    request_timeout: int = 30,
    origin_url: str | None = None,
) -> MoErgoCognitoConfig:
    """Create MoErgo Cognito configuration with custom settings.

    Factory function for creating MoErgo Cognito configuration
    with common customization options.

    Args:
        client_id: AWS Cognito client ID (defaults to MoErgo client ID)
        cognito_url: AWS Cognito URL (defaults to us-east-1 endpoint)
        request_timeout: Request timeout in seconds
        origin_url: Origin URL for CORS (defaults to my.glove80.com)

    Returns:
        MoErgoCognitoConfig: Configured Cognito configuration
    """
    config_kwargs: dict[str, Any] = {"request_timeout": request_timeout}

    if client_id is not None:
        config_kwargs["client_id"] = client_id
    if cognito_url is not None:
        config_kwargs["cognito_url"] = cognito_url
    if origin_url is not None:
        config_kwargs["origin_url"] = origin_url
        config_kwargs["referer_url"] = origin_url.rstrip("/") + "/"

    return MoErgoCognitoConfig(**config_kwargs)
