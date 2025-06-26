"""Tests for MoErgo configuration models."""

from pathlib import Path

import pytest

from glovebox.config.models.moergo import (
    MoErgoCredentialConfig,
    MoErgoServiceConfig,
    create_default_moergo_config,
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
        config_dir = isolated_config.config_file_path.parent if isolated_config.config_file_path else Path("/tmp/test")

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


class TestMoErgoServiceConfig:
    """Test MoErgo service configuration."""

    def test_default_configuration(self):
        """Test default service configuration values."""
        config = MoErgoServiceConfig()

        assert config.api_base_url == "https://my.glove80.com"
        assert isinstance(config.credentials, MoErgoCredentialConfig)
        assert config.enable_layout_sync is True
        assert config.enable_bookmark_sync is True
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

    def test_create_moergo_credential_config(self, isolated_config):
        """Test MoErgo credential config factory."""
        config_dir = isolated_config.config_file_path.parent if isolated_config.config_file_path else Path("/tmp/test")

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


class TestMoErgoModelSerialization:
    """Test MoErgo model serialization and deserialization."""

    def test_credential_config_serialization(self, isolated_config):
        """Test credential config serialization."""
        config_dir = isolated_config.config_file_path.parent if isolated_config.config_file_path else Path("/tmp/test")

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
            enable_layout_sync=False,
            connection_timeout=45,
        )

        # Test model_dump
        data = config.model_dump(mode="json")
        assert data["api_base_url"] == "https://test.example.com"
        assert data["enable_layout_sync"] is False
        assert data["connection_timeout"] == 45
        assert "credentials" in data

        # Test round-trip serialization
        restored = MoErgoServiceConfig.model_validate(data)
        assert restored.api_base_url == config.api_base_url
        assert restored.enable_layout_sync == config.enable_layout_sync
        assert restored.connection_timeout == config.connection_timeout
        assert isinstance(restored.credentials, MoErgoCredentialConfig)
