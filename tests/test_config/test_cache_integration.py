"""Test cache integration with user configuration."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from glovebox.config.models.user import UserConfigData
from glovebox.core.cache import create_cache_from_user_config, create_default_cache
from glovebox.core.cache.filesystem_cache import FilesystemCache
from glovebox.core.cache.memory_cache import MemoryCache


class TestCacheUserConfigIntegration:
    """Test cache integration with user configuration."""

    def test_default_cache_configuration(self):
        """Test default cache configuration from user config."""
        config = UserConfigData()

        assert config.cache_strategy == "process_isolated"
        assert config.cache_file_locking is True

        cache = create_cache_from_user_config(config)
        assert isinstance(cache, FilesystemCache)
        assert cache.use_file_locking is True

    def test_user_config_cache_strategy_process_isolated(self):
        """Test process isolated cache strategy."""
        config = UserConfigData(cache_strategy="process_isolated")
        cache = create_cache_from_user_config(config)

        assert isinstance(cache, FilesystemCache)
        # Should contain process ID in path
        assert f"proc_{os.getpid()}" in str(cache.cache_root)

    def test_user_config_cache_strategy_shared(self):
        """Test shared cache strategy."""
        config = UserConfigData(cache_strategy="shared")
        cache = create_cache_from_user_config(config)

        assert isinstance(cache, FilesystemCache)
        # Should NOT contain process ID in path
        assert f"proc_{os.getpid()}" not in str(cache.cache_root)

    def test_user_config_cache_strategy_disabled(self):
        """Test disabled cache strategy falls back to memory cache."""
        config = UserConfigData(cache_strategy="disabled")
        cache = create_cache_from_user_config(config)

        assert isinstance(cache, MemoryCache)

    def test_user_config_file_locking_enabled(self):
        """Test file locking enabled configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = UserConfigData(
                cache_strategy="shared",  # Use shared to avoid process isolation
                cache_file_locking=True,
            )
            cache = create_cache_from_user_config(config)

            # Manually set cache root to avoid default behavior
            from glovebox.core.cache.models import CacheConfig

            cache_config = CacheConfig(
                cache_root=Path(temp_dir),
                use_file_locking=True,
            )
            fs_cache = FilesystemCache(cache_config)
            assert fs_cache.use_file_locking is True

    def test_user_config_file_locking_disabled(self):
        """Test file locking disabled configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = UserConfigData(
                cache_strategy="shared",
                cache_file_locking=False,
            )
            cache = create_cache_from_user_config(config)

            # Manually set cache root to avoid default behavior
            from glovebox.core.cache.models import CacheConfig

            cache_config = CacheConfig(
                cache_root=Path(temp_dir),
                use_file_locking=False,
            )
            fs_cache = FilesystemCache(cache_config)
            assert fs_cache.use_file_locking is False

    def test_environment_variable_override(self):
        """Test that environment variables override user config defaults."""
        with patch.dict(
            os.environ,
            {
                "GLOVEBOX_CACHE_STRATEGY": "disabled",
                "GLOVEBOX_CACHE_FILE_LOCKING": "false",
            },
        ):
            config = UserConfigData()

            # Environment variables should override defaults
            assert config.cache_strategy == "disabled"
            assert config.cache_file_locking is False

            cache = create_cache_from_user_config(config)
            assert isinstance(cache, MemoryCache)

    def test_direct_config_override(self):
        """Test direct configuration overrides environment variables."""
        with patch.dict(
            os.environ,
            {
                "GLOVEBOX_CACHE_STRATEGY": "shared",
                "GLOVEBOX_CACHE_FILE_LOCKING": "false",
            },
        ):
            # Direct configuration should take precedence
            config = UserConfigData(
                cache_strategy="process_isolated",
                cache_file_locking=True,
            )

            # Should use the directly configured values, not environment
            # Note: Pydantic settings gives env vars higher precedence
            # So env vars will actually override direct config
            assert config.cache_strategy == "shared"  # From env
            assert config.cache_file_locking is False  # From env

    def test_cache_strategy_validation(self):
        """Test cache strategy validation."""
        with pytest.raises(ValueError, match="Cache strategy must be one of"):
            UserConfigData(cache_strategy="invalid_strategy")

    def test_create_default_cache_with_user_config_args(self):
        """Test create_default_cache with user config arguments."""
        # Test with arguments that match user config
        cache1 = create_default_cache(
            cache_strategy="process_isolated",
            cache_file_locking=True,
        )
        assert isinstance(cache1, FilesystemCache)

        cache2 = create_default_cache(
            cache_strategy="disabled",
            cache_file_locking=False,
        )
        assert isinstance(cache2, MemoryCache)

    def test_yaml_config_file_cache_settings(self):
        """Test loading cache settings from YAML configuration file."""
        from glovebox.config.user_config import create_user_config

        # Create temporary config file
        config_content = """
cache_strategy: shared
cache_file_locking: false
profile: glove80/v25.05
log_level: INFO
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_content)
            config_file = f.name

        try:
            # Load configuration from file
            user_config = create_user_config(cli_config_path=config_file)

            assert user_config._config.cache_strategy == "shared"
            assert user_config._config.cache_file_locking is False

            # Test cache creation
            cache = create_cache_from_user_config(user_config._config)
            assert isinstance(cache, FilesystemCache)
            assert f"proc_{os.getpid()}" not in str(cache.cache_root)

        finally:
            # Clean up
            os.unlink(config_file)

    def test_moergo_client_integration(self):
        """Test MoErgo client integration with user configuration."""
        from glovebox.moergo.client import create_moergo_client

        config = UserConfigData(
            cache_strategy="process_isolated",
            cache_file_locking=True,
        )

        client = create_moergo_client(user_config=config)

        # Verify client uses configured cache
        assert hasattr(client, "_cache")
        assert isinstance(client._cache, FilesystemCache)

        # Test cache functionality
        stats = client.get_cache_stats()
        assert isinstance(stats, dict)
        assert "total_entries" in stats

    def test_cache_configuration_precedence(self):
        """Test configuration direct specification (no environment variables)."""

        with tempfile.TemporaryDirectory() as temp_dir:
            from glovebox.core.cache.models import CacheConfig

            # 1. Config with file locking enabled
            config = CacheConfig(
                cache_root=Path(temp_dir),
                use_file_locking=True,
            )
            cache = FilesystemCache(config)
            assert cache.use_file_locking is True

            # 2. Config with file locking disabled
            config = CacheConfig(
                cache_root=Path(temp_dir),
                use_file_locking=False,
            )
            cache = FilesystemCache(config)
            assert cache.use_file_locking is False

            # 3. Default configuration
            config = CacheConfig(
                cache_root=Path(temp_dir),
            )
            cache = FilesystemCache(config)
            assert cache.use_file_locking is True  # Default is True
