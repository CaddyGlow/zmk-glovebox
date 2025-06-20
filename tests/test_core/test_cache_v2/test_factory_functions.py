"""Tests for cache factory functions."""

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.core.cache_v2 import (
    create_cache_from_user_config,
    create_default_cache,
    create_diskcache_manager,
)
from glovebox.core.cache_v2.disabled_cache import DisabledCache
from glovebox.core.cache_v2.diskcache_manager import DiskCacheManager


class TestCreateDiskCacheManager:
    """Test create_diskcache_manager factory function."""

    def test_create_enabled_cache(self, tmp_path):
        """Test creating enabled cache manager."""
        cache = create_diskcache_manager(
            cache_root=tmp_path,
            enabled=True,
            max_size_gb=1,
            timeout=15,
        )

        assert isinstance(cache, DiskCacheManager)
        cache.close()

    def test_create_disabled_cache(self, tmp_path):
        """Test creating disabled cache manager."""
        cache = create_diskcache_manager(
            cache_root=tmp_path,
            enabled=False,
        )

        assert isinstance(cache, DisabledCache)

    def test_create_with_tag(self, tmp_path):
        """Test creating cache with tag (subdirectory)."""
        cache = create_diskcache_manager(
            cache_root=tmp_path,
            enabled=True,
            tag="test_module",
        )

        assert isinstance(cache, DiskCacheManager)
        # Cache directory should include tag
        expected_path = tmp_path / "test_module"
        assert expected_path.exists()
        cache.close()

    def test_default_parameters(self, tmp_path):
        """Test factory function with default parameters."""
        cache = create_diskcache_manager(cache_root=tmp_path)

        assert isinstance(cache, DiskCacheManager)
        cache.close()


class TestCreateCacheFromUserConfig:
    """Test create_cache_from_user_config factory function."""

    def test_create_from_enabled_config(self, tmp_path):
        """Test creating cache from enabled user config."""
        mock_config = Mock()
        mock_config.cache_path = tmp_path
        mock_config.cache_strategy = "shared"

        cache = create_cache_from_user_config(mock_config)
        assert isinstance(cache, DiskCacheManager)
        cache.close()

    def test_create_from_disabled_config(self, tmp_path):
        """Test creating cache from disabled user config."""
        mock_config = Mock()
        mock_config.cache_path = tmp_path
        mock_config.cache_strategy = "disabled"

        cache = create_cache_from_user_config(mock_config)
        assert isinstance(cache, DisabledCache)

    def test_create_with_tag(self, tmp_path):
        """Test creating cache with tag from user config."""
        mock_config = Mock()
        mock_config.cache_path = tmp_path
        mock_config.cache_strategy = "shared"

        cache = create_cache_from_user_config(mock_config, tag="layout")
        assert isinstance(cache, DiskCacheManager)

        expected_path = tmp_path / "layout"
        assert expected_path.exists()
        cache.close()

    def test_global_cache_disabled(self, tmp_path):
        """Test global cache disable overrides user config."""
        mock_config = Mock()
        mock_config.cache_path = tmp_path
        mock_config.cache_strategy = "shared"

        with patch.dict(os.environ, {"GLOVEBOX_CACHE_GLOBAL": "false"}):
            cache = create_cache_from_user_config(mock_config)
            assert isinstance(cache, DisabledCache)

    def test_module_cache_disabled(self, tmp_path):
        """Test module-specific cache disable."""
        mock_config = Mock()
        mock_config.cache_path = tmp_path
        mock_config.cache_strategy = "shared"

        with patch.dict(os.environ, {"GLOVEBOX_CACHE_LAYOUT": "false"}):
            cache = create_cache_from_user_config(mock_config, tag="layout")
            assert isinstance(cache, DisabledCache)

            # Other modules should still work
            cache2 = create_cache_from_user_config(mock_config, tag="compilation")
            assert isinstance(cache2, DiskCacheManager)
            cache2.close()

    def test_config_without_cache_path(self, tmp_path):
        """Test config object without cache_path attribute."""
        mock_config = Mock()
        mock_config.cache_strategy = "shared"
        # No cache_path attribute
        del mock_config.cache_path

        cache = create_cache_from_user_config(mock_config)
        assert isinstance(cache, DiskCacheManager)
        cache.close()


class TestCreateDefaultCache:
    """Test create_default_cache factory function."""

    def test_create_default_enabled(self):
        """Test creating default enabled cache."""
        cache = create_default_cache()
        assert isinstance(cache, DiskCacheManager)
        cache.close()

    def test_create_default_with_tag(self):
        """Test creating default cache with tag."""
        cache = create_default_cache(tag="test_tag")
        assert isinstance(cache, DiskCacheManager)
        cache.close()

    def test_global_disable_overrides_default(self):
        """Test global disable affects default cache."""
        with patch.dict(os.environ, {"GLOVEBOX_CACHE_GLOBAL": "disabled"}):
            cache = create_default_cache()
            assert isinstance(cache, DisabledCache)

    def test_module_disable_affects_default(self):
        """Test module disable affects default cache."""
        with patch.dict(os.environ, {"GLOVEBOX_CACHE_COMPILATION": "0"}):
            cache = create_default_cache(tag="compilation")
            assert isinstance(cache, DisabledCache)

            # Other modules should work
            cache2 = create_default_cache(tag="layout")
            assert isinstance(cache2, DiskCacheManager)
            cache2.close()

    def test_xdg_cache_home_respected(self, tmp_path):
        """Test that XDG_CACHE_HOME is respected."""
        xdg_cache = tmp_path / "xdg_cache"

        with patch.dict(os.environ, {"XDG_CACHE_HOME": str(xdg_cache)}):
            cache = create_default_cache()
            assert isinstance(cache, DiskCacheManager)

            # Cache should be created under XDG_CACHE_HOME/glovebox
            expected_path = xdg_cache / "glovebox"
            assert expected_path.exists()
            cache.close()


class TestEnvironmentVariables:
    """Test environment variable handling."""

    @pytest.mark.parametrize("env_value", ["false", "0", "disabled"])
    def test_global_disable_values(self, env_value, tmp_path):
        """Test various values for global cache disable."""
        with patch.dict(os.environ, {"GLOVEBOX_CACHE_GLOBAL": env_value}):
            cache = create_default_cache()
            assert isinstance(cache, DisabledCache)

    @pytest.mark.parametrize("env_value", ["true", "1", "enabled", ""])
    def test_global_enable_values(self, env_value, tmp_path):
        """Test values that don't disable global cache."""
        with patch.dict(os.environ, {"GLOVEBOX_CACHE_GLOBAL": env_value}):
            cache = create_default_cache()
            assert isinstance(cache, DiskCacheManager)
            cache.close()

    def test_module_specific_disable(self):
        """Test module-specific disable environment variables."""
        modules = ["layout", "compilation", "firmware"]

        for module in modules:
            env_var = f"GLOVEBOX_CACHE_{module.upper()}"
            with patch.dict(os.environ, {env_var: "false"}):
                cache = create_default_cache(tag=module)
                assert isinstance(cache, DisabledCache)

                # Other modules should still work
                other_cache = create_default_cache(tag="other")
                assert isinstance(other_cache, DiskCacheManager)
                other_cache.close()

    def test_case_insensitive_env_vars(self):
        """Test that environment variables are case insensitive."""
        with patch.dict(os.environ, {"GLOVEBOX_CACHE_GLOBAL": "FALSE"}):
            cache = create_default_cache()
            assert isinstance(cache, DisabledCache)

        with patch.dict(os.environ, {"GLOVEBOX_CACHE_LAYOUT": "DISABLED"}):
            cache = create_default_cache(tag="layout")
            assert isinstance(cache, DisabledCache)
