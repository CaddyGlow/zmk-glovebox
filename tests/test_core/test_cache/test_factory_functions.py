"""Tests for cache factory functions."""

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.core.cache import (
    create_cache_from_user_config,
    create_default_cache,
    create_diskcache_manager,
)
from glovebox.core.cache.disabled_cache import DisabledCache
from glovebox.core.cache.diskcache_manager import DiskCacheManager


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

    def test_xdg_cache_home_respected(self, isolated_cache_environment):
        """Test that XDG_CACHE_HOME is respected."""
        cache = create_default_cache()
        assert isinstance(cache, DiskCacheManager)

        # Cache should be created under XDG_CACHE_HOME/glovebox
        expected_path = isolated_cache_environment["cache_root"]
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


class TestCacheIsolation:
    """Test cache isolation between different modules/tags."""

    def test_different_tags_create_separate_instances(self, tmp_path):
        """Test that different tags create separate cache instances."""
        from glovebox.core.cache.cache_coordinator import (
            reset_shared_cache_instances,
        )

        # Reset to ensure clean state
        reset_shared_cache_instances()

        cache1 = create_default_cache(tag="module1")
        cache2 = create_default_cache(tag="module2")

        assert cache1 is not cache2

        cache1.close()
        cache2.close()
        reset_shared_cache_instances()

    def test_same_tag_reuses_instance(self, tmp_path):
        """Test that same tag reuses the same cache instance."""
        from glovebox.core.cache.cache_coordinator import (
            reset_shared_cache_instances,
        )

        # Reset to ensure clean state
        reset_shared_cache_instances()

        cache1 = create_default_cache(tag="same_module")
        cache2 = create_default_cache(tag="same_module")

        assert cache1 is cache2

        cache1.close()
        reset_shared_cache_instances()

    def test_cache_data_isolation(self, tmp_path):
        """Test that data stored in one cache doesn't affect another."""
        from glovebox.core.cache.cache_coordinator import (
            reset_shared_cache_instances,
        )

        # Reset to ensure clean state
        reset_shared_cache_instances()

        # Create separate cache instances for different modules
        metrics_cache = create_default_cache(tag="metrics")
        layout_cache = create_default_cache(tag="layout")
        compilation_cache = create_default_cache(tag="compilation")

        # Store different data in each cache
        metrics_cache.set("test_key", "metrics_data")
        layout_cache.set("test_key", "layout_data")
        compilation_cache.set("test_key", "compilation_data")

        # Verify each cache has its own data
        assert metrics_cache.get("test_key") == "metrics_data"
        assert layout_cache.get("test_key") == "layout_data"
        assert compilation_cache.get("test_key") == "compilation_data"

        # Clean up
        metrics_cache.close()
        layout_cache.close()
        compilation_cache.close()
        reset_shared_cache_instances()

    def test_cache_clear_isolation(self, tmp_path):
        """Test that clearing one cache doesn't affect others."""
        from glovebox.core.cache.cache_coordinator import (
            reset_shared_cache_instances,
        )

        # Reset to ensure clean state
        reset_shared_cache_instances()

        # Create separate cache instances for different modules
        metrics_cache = create_default_cache(tag="metrics")
        layout_cache = create_default_cache(tag="layout")
        compilation_cache = create_default_cache(tag="compilation")

        # Store test data in each cache
        test_data = {"key1": "value1", "key2": "value2", "key3": "value3"}

        for key, value in test_data.items():
            metrics_cache.set(key, f"metrics_{value}")
            layout_cache.set(key, f"layout_{value}")
            compilation_cache.set(key, f"compilation_{value}")

        # Verify all caches have data
        for key in test_data:
            assert metrics_cache.get(key) == f"metrics_{test_data[key]}"
            assert layout_cache.get(key) == f"layout_{test_data[key]}"
            assert compilation_cache.get(key) == f"compilation_{test_data[key]}"

        # Clear only the metrics cache
        metrics_cache.clear()

        # Verify metrics cache is cleared
        for key in test_data:
            assert metrics_cache.get(key) is None

        # Verify other caches are NOT affected
        for key in test_data:
            assert layout_cache.get(key) == f"layout_{test_data[key]}"
            assert compilation_cache.get(key) == f"compilation_{test_data[key]}"

        # Clean up
        layout_cache.clear()
        compilation_cache.clear()
        metrics_cache.close()
        layout_cache.close()
        compilation_cache.close()
        reset_shared_cache_instances()

    def test_cache_filesystem_isolation(self, isolated_cache_environment):
        """Test that different tags use separate filesystem directories."""
        from glovebox.core.cache.cache_coordinator import (
            reset_shared_cache_instances,
        )

        # Reset to ensure clean state
        reset_shared_cache_instances()

        # Use isolated cache environment
        metrics_cache = create_default_cache(tag="metrics")
        layout_cache = create_default_cache(tag="layout")

        # Store some data to ensure directories are created
        metrics_cache.set("test", "metrics_data")
        layout_cache.set("test", "layout_data")

        # Verify separate directories exist
        glovebox_cache = isolated_cache_environment["cache_root"]
        metrics_dir = glovebox_cache / "metrics"
        layout_dir = glovebox_cache / "layout"

        assert metrics_dir.exists()
        assert layout_dir.exists()
        assert metrics_dir != layout_dir

        # Clean up
        metrics_cache.close()
        layout_cache.close()
        reset_shared_cache_instances()
