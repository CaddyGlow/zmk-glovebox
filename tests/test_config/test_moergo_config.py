"""Tests for MoErgo configuration models."""

from pathlib import Path

import pytest

from glovebox.moergo.config import (
    MoErgoCognitoConfig,
    MoErgoCredentialConfig,
    MoErgoServiceConfig,
    create_default_moergo_config,
    create_moergo_cognito_config,
    create_moergo_credential_config,
)


class TestMoErgoCredentialConfig:
    """Test MoErgo credential configuration."""

    def test_default_configuration(self, isolated_config):
        """Test default credential configuration values."""
        config = MoErgoCredentialConfig()

        assert config.config_dir == Path.home() / ".glovebox"
        assert config.credentials_file == "moergo_credentials.json"
        assert config.tokens_file == "moergo_tokens.json"
        assert config.default_username is None
        assert config.prefer_keyring is True
        assert config.keyring_service == "glovebox-moergo"
        assert config.file_permissions == "600"

    def test_custom_configuration(self, isolated_config):
        """Test custom credential configuration."""
        config_dir = (
            isolated_config.config_file_path.parent
            if isolated_config.config_file_path
            else Path("/tmp/test")
        )

        config = MoErgoCredentialConfig(
            config_dir=config_dir,
            default_username="test@example.com",
            prefer_keyring=False,
            keyring_service="custom-service",
            file_permissions="644",
        )

        assert config.config_dir == config_dir.resolve()
        assert config.default_username == "test@example.com"
        assert config.prefer_keyring is False
        assert config.keyring_service == "custom-service"
        assert config.file_permissions == "644"

    def test_path_methods(self, isolated_config):
        """Test credential and token path methods."""
        config_dir = Path("/tmp/test")
        config = MoErgoCredentialConfig(config_dir=config_dir)

        assert config.get_credentials_path() == config_dir / "moergo_credentials.json"
        assert config.get_tokens_path() == config_dir / "moergo_tokens.json"

        # Test absolute paths
        config_abs = MoErgoCredentialConfig(
            credentials_file="/abs/path/creds.json",
            tokens_file="/abs/path/tokens.json",
        )

        assert config_abs.get_credentials_path() == Path("/abs/path/creds.json")
        assert config_abs.get_tokens_path() == Path("/abs/path/tokens.json")

    def test_file_permissions_validation(self):
        """Test file permissions validation."""
        # Valid octal permissions
        config = MoErgoCredentialConfig(file_permissions="755")
        assert config.get_file_permissions_octal() == 0o755

        config = MoErgoCredentialConfig(file_permissions="600")
        assert config.get_file_permissions_octal() == 0o600

        # Invalid permissions should raise ValueError
        with pytest.raises(ValueError, match="File permissions must be valid octal"):
            MoErgoCredentialConfig(file_permissions="999")

        with pytest.raises(ValueError, match="File permissions must be valid octal"):
            MoErgoCredentialConfig(file_permissions="abc")

    def test_config_dir_expansion(self):
        """Test config directory path expansion."""
        # Test with tilde expansion
        config = MoErgoCredentialConfig(config_dir=Path("~/test"))
        assert config.config_dir == Path.home().resolve() / "test"

        # Test with relative path
        config = MoErgoCredentialConfig(config_dir=Path("relative/path"))
        assert config.config_dir.is_absolute()


class TestMoErgoCognitoConfig:
    """Test MoErgo Cognito configuration."""

    def test_default_configuration(self):
        """Test default Cognito configuration values."""
        config = MoErgoCognitoConfig()

        assert config.client_id == "3hvr36st4kdb6p7kasi1cdnson"
        assert config.cognito_url == "https://cognito-idp.us-east-1.amazonaws.com/"
        assert config.request_timeout == 30
        assert config.origin_url == "https://my.glove80.com"
        assert config.referer_url == "https://my.glove80.com/"
        assert config.aws_amplify_version == "aws-amplify/5.0.4 js"
        assert "Mozilla/5.0" in config.user_agent

    def test_custom_configuration(self):
        """Test custom Cognito configuration."""
        config = MoErgoCognitoConfig(
            client_id="custom-client-id",
            cognito_url="https://custom-cognito.amazonaws.com/",
            request_timeout=60,
            origin_url="https://custom.example.com",
            referer_url="https://custom.example.com/auth/",
            user_agent="Custom User Agent",
        )

        assert config.client_id == "custom-client-id"
        assert config.cognito_url == "https://custom-cognito.amazonaws.com/"
        assert config.request_timeout == 60
        assert config.origin_url == "https://custom.example.com"
        assert config.referer_url == "https://custom.example.com/auth/"
        assert config.user_agent == "Custom User Agent"

    def test_client_id_validation(self):
        """Test client ID validation."""
        # Valid client ID
        config = MoErgoCognitoConfig(client_id="valid-client-id")
        assert config.client_id == "valid-client-id"

        # Empty client ID should raise ValueError
        with pytest.raises(ValueError, match="Client ID cannot be empty"):
            MoErgoCognitoConfig(client_id="")

        with pytest.raises(ValueError, match="Client ID cannot be empty"):
            MoErgoCognitoConfig(client_id="   ")

    def test_url_validation(self):
        """Test URL validation."""
        # Valid URLs
        config = MoErgoCognitoConfig(
            cognito_url="https://example.com",
            origin_url="http://localhost:8080",
            referer_url="https://custom.com/path",
        )
        assert config.cognito_url == "https://example.com"
        assert config.origin_url == "http://localhost:8080"
        assert config.referer_url == "https://custom.com/path"

        # Invalid URLs
        with pytest.raises(ValueError, match="URL must start with http"):
            MoErgoCognitoConfig(cognito_url="ftp://example.com")

        with pytest.raises(ValueError, match="URL cannot be empty"):
            MoErgoCognitoConfig(origin_url="")

    def test_timeout_validation(self):
        """Test request timeout validation."""
        # Valid timeout
        config = MoErgoCognitoConfig(request_timeout=120)
        assert config.request_timeout == 120

        # Invalid timeout
        with pytest.raises(ValueError, match="Request timeout must be positive"):
            MoErgoCognitoConfig(request_timeout=0)

        with pytest.raises(ValueError, match="Request timeout must be positive"):
            MoErgoCognitoConfig(request_timeout=-10)


class TestMoErgoServiceConfig:
    """Test MoErgo service configuration."""

    def test_default_configuration(self):
        """Test default service configuration values."""
        config = MoErgoServiceConfig()

        assert config.api_base_url == "https://my.glove80.com"
        assert isinstance(config.credentials, MoErgoCredentialConfig)
        assert isinstance(config.cognito, MoErgoCognitoConfig)
        assert config.connection_timeout == 30
        assert config.request_timeout == 60

    def test_api_base_url_validation(self):
        """Test API base URL validation."""
        # Valid URLs
        config = MoErgoServiceConfig(api_base_url="https://example.com")
        assert config.api_base_url == "https://example.com"

        config = MoErgoServiceConfig(api_base_url="http://localhost:8080/")
        assert config.api_base_url == "http://localhost:8080"  # Trailing slash removed

        # Invalid URLs
        with pytest.raises(ValueError, match="API base URL must start with http"):
            MoErgoServiceConfig(api_base_url="ftp://example.com")

        with pytest.raises(ValueError, match="API base URL cannot be empty"):
            MoErgoServiceConfig(api_base_url="")

    def test_timeout_validation(self):
        """Test timeout validation."""
        # Valid timeouts
        config = MoErgoServiceConfig(connection_timeout=60, request_timeout=120)
        assert config.connection_timeout == 60
        assert config.request_timeout == 120

        # Invalid timeouts
        with pytest.raises(ValueError, match="Timeout values must be positive"):
            MoErgoServiceConfig(connection_timeout=0)

        with pytest.raises(ValueError, match="Timeout values must be positive"):
            MoErgoServiceConfig(request_timeout=-1)


class TestMoErgoFactoryFunctions:
    """Test MoErgo factory functions."""

    def test_create_default_moergo_config(self):
        """Test default MoErgo config factory."""
        config = create_default_moergo_config()

        assert isinstance(config, MoErgoServiceConfig)
        assert config.api_base_url == "https://my.glove80.com"
        assert isinstance(config.credentials, MoErgoCredentialConfig)
        assert isinstance(config.cognito, MoErgoCognitoConfig)

    def test_create_moergo_credential_config(self, isolated_config):
        """Test MoErgo credential config factory."""
        config_dir = (
            isolated_config.config_file_path.parent
            if isolated_config.config_file_path
            else Path("/tmp/test")
        )

        config = create_moergo_credential_config(
            config_dir=config_dir,
            username="test@example.com",
            prefer_keyring=False,
        )

        assert isinstance(config, MoErgoCredentialConfig)
        assert config.config_dir == config_dir.resolve()
        assert config.default_username == "test@example.com"
        assert config.prefer_keyring is False

    def test_create_moergo_credential_config_defaults(self):
        """Test MoErgo credential config factory with defaults."""
        config = create_moergo_credential_config()

        assert isinstance(config, MoErgoCredentialConfig)
        assert config.config_dir == Path.home() / ".glovebox"
        assert config.default_username is None
        assert config.prefer_keyring is True

    def test_create_moergo_cognito_config(self):
        """Test MoErgo Cognito config factory."""
        config = create_moergo_cognito_config(
            client_id="test-client-id",
            request_timeout=45,
            origin_url="https://test.example.com",
        )

        assert isinstance(config, MoErgoCognitoConfig)
        assert config.client_id == "test-client-id"
        assert config.request_timeout == 45
        assert config.origin_url == "https://test.example.com"
        assert config.referer_url == "https://test.example.com/"

    def test_create_moergo_cognito_config_defaults(self):
        """Test MoErgo Cognito config factory with defaults."""
        config = create_moergo_cognito_config()

        assert isinstance(config, MoErgoCognitoConfig)
        assert config.client_id == "3hvr36st4kdb6p7kasi1cdnson"
        assert config.request_timeout == 30
        assert config.origin_url == "https://my.glove80.com"


class TestMoErgoModelSerialization:
    """Test MoErgo model serialization and deserialization."""

    def test_credential_config_serialization(self, isolated_config):
        """Test credential config serialization."""
        config_dir = (
            isolated_config.config_file_path.parent
            if isolated_config.config_file_path
            else Path("/tmp/test")
        )

        config = MoErgoCredentialConfig(
            config_dir=config_dir,
            default_username="test@example.com",
            prefer_keyring=False,
        )

        # Test model_dump
        data = config.model_dump(mode="json")
        assert isinstance(data["config_dir"], str)
        assert data["default_username"] == "test@example.com"
        assert data["prefer_keyring"] is False

        # Test round-trip serialization
        restored = MoErgoCredentialConfig.model_validate(data)
        assert restored.config_dir == config.config_dir
        assert restored.default_username == config.default_username
        assert restored.prefer_keyring == config.prefer_keyring

    def test_service_config_serialization(self):
        """Test service config serialization."""
        config = MoErgoServiceConfig(
            api_base_url="https://test.example.com",
            connection_timeout=45,
        )

        # Test model_dump
        data = config.model_dump(mode="json")
        assert data["api_base_url"] == "https://test.example.com"
        assert data["connection_timeout"] == 45
        assert "credentials" in data

        # Test round-trip serialization
        restored = MoErgoServiceConfig.model_validate(data)
        assert restored.api_base_url == config.api_base_url
        assert restored.connection_timeout == config.connection_timeout
        assert isinstance(restored.credentials, MoErgoCredentialConfig)
