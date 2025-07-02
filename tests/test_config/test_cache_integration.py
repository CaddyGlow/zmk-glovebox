"""Test cache integration with user configuration."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from glovebox.config.models.user import UserConfigData
from glovebox.core.cache import create_cache_from_user_config, create_default_cache
from glovebox.core.cache.disabled_cache import DisabledCache
from glovebox.core.cache.diskcache_manager import DiskCacheManager


class TestCacheUserConfigIntegration:
    """Test cache integration with user configuration using DiskCache."""

    def test_default_cache_configuration(self, isolated_cache_environment):
        """Test default cache configuration from user config."""
        # Use isolated cache path to prevent pollution
        isolated_cache_path = isolated_cache_environment["cache_root"]
        config = UserConfigData(cache_path=str(isolated_cache_path))

        assert config.cache_strategy == "shared"

        cache = create_cache_from_user_config(config)
        assert isinstance(cache, DiskCacheManager)

    def test_user_config_cache_strategy_shared(self, isolated_cache_environment):
        """Test shared cache strategy."""
        # Use isolated cache path to prevent pollution
        isolated_cache_path = isolated_cache_environment["cache_root"]
        config = UserConfigData(
            cache_strategy="shared",
            cache_path=str(isolated_cache_path)
        )
        cache = create_cache_from_user_config(config)

        assert isinstance(cache, DiskCacheManager)

    def test_user_config_cache_strategy_disabled(self, isolated_cache_environment):
        """Test disabled cache strategy returns DisabledCache."""
        # Use isolated cache path to prevent pollution
        isolated_cache_path = isolated_cache_environment["cache_root"]
        config = UserConfigData(
            cache_strategy="disabled",
            cache_path=str(isolated_cache_path)
        )
        cache = create_cache_from_user_config(config)

        assert isinstance(cache, DisabledCache)

    def test_cache_with_tag(self, isolated_cache_environment):
        """Test cache creation with tag creates subdirectory."""
        from glovebox.config.models.user import UserConfigData
        
        # Use isolated cache path to prevent directory pollution
        isolated_cache_path = isolated_cache_environment["cache_root"]
        config = UserConfigData(
            cache_strategy="shared",
            cache_path=str(isolated_cache_path)
        )
        cache = create_cache_from_user_config(config, tag="test_module")

        assert isinstance(cache, DiskCacheManager)
        # Verify tag creates subdirectory in isolated environment
        expected_path = isolated_cache_path / "test_module"
        assert expected_path.exists()

    def test_environment_variable_override(self, isolated_cache_environment):
        """Test that environment variables override user config defaults."""
        # Use isolated cache path to prevent pollution
        isolated_cache_path = isolated_cache_environment["cache_root"]
        with patch.dict(
            os.environ,
            {
                "GLOVEBOX_CACHE_STRATEGY": "disabled",
            },
        ):
            config = UserConfigData(cache_path=str(isolated_cache_path))

            # Environment variables should override defaults
            assert config.cache_strategy == "disabled"

            cache = create_cache_from_user_config(config)
            assert isinstance(cache, DisabledCache)

    def test_global_cache_disable_environment(self, isolated_cache_environment):
        """Test global cache disable via environment variable."""
        # Use isolated cache path to prevent pollution
        isolated_cache_path = isolated_cache_environment["cache_root"]
        with patch.dict(
            os.environ,
            {
                "GLOVEBOX_CACHE_GLOBAL": "false",
            },
        ):
            config = UserConfigData(
                cache_strategy="shared",
                cache_path=str(isolated_cache_path)
            )
            cache = create_cache_from_user_config(config)

            # Should return disabled cache even though config says shared
            assert isinstance(cache, DisabledCache)

    def test_module_cache_disable_environment(self, isolated_cache_environment):
        """Test module-specific cache disable via environment variable."""
        # Use isolated cache path to prevent pollution
        isolated_cache_path = isolated_cache_environment["cache_root"]
        with patch.dict(
            os.environ,
            {
                "GLOVEBOX_CACHE_LAYOUT": "false",
            },
        ):
            config = UserConfigData(
                cache_strategy="shared",
                cache_path=str(isolated_cache_path)
            )

            # Layout module should be disabled
            layout_cache = create_cache_from_user_config(config, tag="layout")
            assert isinstance(layout_cache, DisabledCache)

            # Other modules should still work
            compilation_cache = create_cache_from_user_config(config, tag="compilation")
            assert isinstance(compilation_cache, DiskCacheManager)

    def test_cache_strategy_validation(self):
        """Test cache strategy validation."""
        with pytest.raises(ValueError, match="Cache strategy must be one of"):
            UserConfigData(cache_strategy="invalid_strategy")

        # process_isolated is no longer valid
        with pytest.raises(ValueError, match="Cache strategy must be one of"):
            UserConfigData(cache_strategy="process_isolated")

    def test_create_default_cache(self):
        """Test create_default_cache function."""
        cache = create_default_cache()
        assert isinstance(cache, DiskCacheManager)

    def test_create_default_cache_with_tag(self):
        """Test create_default_cache with tag."""
        cache = create_default_cache(tag="test_tag")
        assert isinstance(cache, DiskCacheManager)

    def test_xdg_cache_home_respected(self, isolated_cli_environment):
        """Test that XDG_CACHE_HOME is respected."""
        # Use isolated cache path to prevent pollution
        isolated_cache_path = isolated_cli_environment["cache_root"]
        config = UserConfigData(cache_path=str(isolated_cache_path))

        # Cache path should use the isolated cache path
        assert config.cache_path == isolated_cache_path

    def test_yaml_config_file_cache_settings(self):
        """Test loading cache settings from YAML configuration file."""
        from glovebox.config.user_config import create_user_config

        # Create temporary config file
        config_content = """
cache_strategy: disabled
profile: glove80/v25.05
log_level: INFO
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_content)
            config_file = f.name

        try:
            # Load configuration from file
            user_config = create_user_config(cli_config_path=config_file)

            assert user_config._config.cache_strategy == "disabled"

            # Test cache creation
            cache = create_cache_from_user_config(user_config._config)
            assert isinstance(cache, DisabledCache)

        finally:
            # Clean up
            Path(config_file).unlink()

    def test_moergo_client_integration(self, isolated_cache_environment):
        """Test MoErgo client integration with user configuration."""
        from glovebox.moergo.client import create_moergo_client

        # Use isolated cache path to prevent pollution
        isolated_cache_path = isolated_cache_environment["cache_root"]
        config = UserConfigData(
            cache_strategy="shared",
            cache_path=str(isolated_cache_path)
        )
        client = create_moergo_client(user_config=config)

        # Verify client uses configured cache
        assert hasattr(client, "_cache")
        assert isinstance(client._cache, DiskCacheManager)

        # Test cache functionality
        test_key = "test_key"
        test_value = {"test": "data"}
        client._cache.set(test_key, test_value)
        retrieved_value = client._cache.get(test_key)
        assert retrieved_value == test_value

    def test_cache_basic_operations(self, isolated_cache_environment):
        """Test basic cache operations work with user config."""
        # Use isolated cache path to prevent pollution
        isolated_cache_path = isolated_cache_environment["cache_root"]
        config = UserConfigData(
            cache_strategy="shared",
            cache_path=str(isolated_cache_path)
        )
        cache = create_cache_from_user_config(config)

        # Basic set/get
        cache.set("test_key", "test_value")
        assert cache.get("test_key") == "test_value"

        # Get with default
        assert cache.get("missing_key", "default") == "default"

        # Exists
        assert cache.exists("test_key") is True
        assert cache.exists("missing_key") is False

        # Delete
        assert cache.delete("test_key") is True
        assert cache.get("test_key") is None

    def test_cache_with_ttl(self, isolated_cache_environment):
        """Test cache operations with TTL."""
        # Use isolated cache path to prevent pollution
        isolated_cache_path = isolated_cache_environment["cache_root"]
        config = UserConfigData(
            cache_strategy="shared",
            cache_path=str(isolated_cache_path)
        )
        cache = create_cache_from_user_config(config)

        # Set with TTL
        cache.set("ttl_key", "ttl_value", ttl=1)
        assert cache.get("ttl_key") == "ttl_value"

        # Wait for expiration and verify it's gone
        import time

        time.sleep(1.1)
        assert cache.get("ttl_key") is None

    def test_disabled_cache_operations(self, isolated_cache_environment):
        """Test that disabled cache properly no-ops all operations."""
        # Use isolated cache path to prevent pollution
        isolated_cache_path = isolated_cache_environment["cache_root"]
        config = UserConfigData(
            cache_strategy="disabled",
            cache_path=str(isolated_cache_path)
        )
        cache = create_cache_from_user_config(config)

        # All operations should be no-ops
        cache.set("key", "value")
        assert cache.get("key") is None
        assert cache.get("key", "default") == "default"
        assert cache.exists("key") is False
        assert cache.delete("key") is False

        # Stats should be empty
        stats = cache.get_stats()
        assert stats.total_entries == 0
        assert stats.hit_count == 0
        assert stats.miss_count == 0
