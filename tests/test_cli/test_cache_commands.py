"""Tests for CLI cache commands."""

import os
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from glovebox.cli.app import app
from glovebox.cli.commands import register_all_commands
from glovebox.core.cache_v2 import create_default_cache
from glovebox.core.cache_v2.cache_coordinator import reset_shared_cache_instances


class TestCacheClearCommand:
    """Test the cache clear CLI command."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        reset_shared_cache_instances()
        # Register all commands to ensure cache commands are available
        register_all_commands(app)

    def teardown_method(self):
        """Clean up test environment."""
        reset_shared_cache_instances()

    def test_cache_clear_specific_module(self, tmp_path):
        """Test clearing cache for a specific module."""
        # Use temporary directory as cache root
        with patch.dict(os.environ, {"XDG_CACHE_HOME": str(tmp_path)}):
            # Create test data in multiple modules
            metrics_cache = create_default_cache(tag="metrics")
            layout_cache = create_default_cache(tag="layout")
            compilation_cache = create_default_cache(tag="compilation")

            # Store test data
            test_data = {"key1": "value1", "key2": "value2"}
            for key, value in test_data.items():
                metrics_cache.set(key, f"metrics_{value}")
                layout_cache.set(key, f"layout_{value}")
                compilation_cache.set(key, f"compilation_{value}")

            # Verify data exists in all caches
            for key in test_data:
                assert metrics_cache.get(key) == f"metrics_{test_data[key]}"
                assert layout_cache.get(key) == f"layout_{test_data[key]}"
                assert compilation_cache.get(key) == f"compilation_{test_data[key]}"

            # Clear only the metrics cache using CLI
            result = self.runner.invoke(
                app, ["cache", "clear", "-m", "metrics", "--force"]
            )

            # Debug output if command fails
            if result.exit_code != 0:
                print(f"Command failed with exit code {result.exit_code}")
                print(f"STDOUT: {result.stdout}")
                if result.exception:
                    print(f"Exception: {result.exception}")
                    import traceback

                    traceback.print_exception(
                        type(result.exception),
                        result.exception,
                        result.exception.__traceback__,
                    )

            # Command should succeed
            assert result.exit_code == 0
            assert "Cleared cache for module 'metrics'" in result.stdout

            # Verify metrics cache is cleared
            for key in test_data:
                assert metrics_cache.get(key) is None

            # Verify other caches are NOT affected
            for key in test_data:
                assert layout_cache.get(key) == f"layout_{test_data[key]}"
                assert compilation_cache.get(key) == f"compilation_{test_data[key]}"

            # Clean up
            layout_cache.close()
            compilation_cache.close()
            metrics_cache.close()

    def test_cache_clear_nonexistent_module(self, tmp_path):
        """Test clearing cache for a module that doesn't exist."""
        with patch.dict(os.environ, {"XDG_CACHE_HOME": str(tmp_path)}):
            result = self.runner.invoke(
                app, ["cache", "clear", "-m", "nonexistent", "--force"]
            )

            # Should gracefully handle non-existent module
            assert result.exit_code == 0
            assert "No cache found for module 'nonexistent'" in result.stdout

    def test_cache_clear_all_modules(self, tmp_path):
        """Test clearing all cache modules."""
        with patch.dict(os.environ, {"XDG_CACHE_HOME": str(tmp_path)}):
            # Create test data in multiple modules
            modules = ["metrics", "layout", "compilation"]
            caches = {}

            for module in modules:
                cache = create_default_cache(tag=module)
                cache.set("test_key", f"{module}_data")
                caches[module] = cache

            # Verify all caches have data
            for module, cache in caches.items():
                assert cache.get("test_key") == f"{module}_data"

            # Clear all caches using CLI
            result = self.runner.invoke(app, ["cache", "clear", "--force"])

            # Command should succeed
            assert result.exit_code == 0
            assert "Cleared all cache directories" in result.stdout

            # Verify all caches are cleared by recreating cache instances
            # (since the original instances may be stale after filesystem deletion)
            reset_shared_cache_instances()
            for module in modules:
                new_cache = create_default_cache(tag=module)
                assert new_cache.get("test_key") is None
                new_cache.close()

    def test_cache_clear_with_confirmation(self, tmp_path):
        """Test cache clear with user confirmation."""
        with patch.dict(os.environ, {"XDG_CACHE_HOME": str(tmp_path)}):
            # Create some test data
            cache = create_default_cache(tag="test_module")
            cache.set("test_key", "test_value")

            # Test declining confirmation
            result = self.runner.invoke(
                app, ["cache", "clear", "-m", "test_module"], input="n\n"
            )
            assert result.exit_code == 0
            assert "Cancelled" in result.stdout

            # Verify data is still there
            assert cache.get("test_key") == "test_value"

            # Test accepting confirmation
            result = self.runner.invoke(
                app, ["cache", "clear", "-m", "test_module"], input="y\n"
            )
            assert result.exit_code == 0
            assert "Cleared cache for module 'test_module'" in result.stdout

            # Verify data is cleared
            assert cache.get("test_key") is None
            cache.close()

    def test_cache_clear_module_isolation(self, tmp_path):
        """Test that clearing one module doesn't affect others - comprehensive test."""
        with patch.dict(os.environ, {"XDG_CACHE_HOME": str(tmp_path)}):
            # Create multiple modules with overlapping key names
            modules = ["metrics", "layout", "compilation", "moergo"]
            caches = {}
            test_keys = ["config", "data", "result", "cache_key"]

            # Set up test data
            for module in modules:
                cache = create_default_cache(tag=module)
                for key in test_keys:
                    cache.set(key, f"{module}_{key}_value")
                caches[module] = cache

            # Verify all data is present
            for module, cache in caches.items():
                for key in test_keys:
                    assert cache.get(key) == f"{module}_{key}_value"

            # Clear only the layout module
            result = self.runner.invoke(
                app, ["cache", "clear", "-m", "layout", "--force"]
            )
            if result.exit_code != 0:
                print(f"Command failed with exit code {result.exit_code}")
                print(f"STDOUT: {result.stdout}")
                print(f"Exception: {result.exception}")
            assert result.exit_code == 0

            # Verify layout cache is cleared
            for key in test_keys:
                assert caches["layout"].get(key) is None

            # Verify all other modules are unaffected
            for module in ["metrics", "compilation", "moergo"]:
                for key in test_keys:
                    assert caches[module].get(key) == f"{module}_{key}_value"

            # Clean up
            for cache in caches.values():
                cache.close()

    def test_cache_clear_no_cache_directory(self, tmp_path):
        """Test cache clear when no cache directory exists."""
        non_existent_cache = tmp_path / "non_existent"
        with patch.dict(os.environ, {"XDG_CACHE_HOME": str(non_existent_cache)}):
            result = self.runner.invoke(
                app, ["cache", "clear", "-m", "test", "--force"]
            )

            assert result.exit_code == 0
            assert "No cache directory found" in result.stdout


class TestCacheShowCommand:
    """Test the cache show CLI command."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        reset_shared_cache_instances()
        # Register all commands to ensure cache commands are available
        register_all_commands(app)

    def teardown_method(self):
        """Clean up test environment."""
        reset_shared_cache_instances()

    def test_cache_show_basic(self, tmp_path):
        """Test basic cache show functionality."""
        with patch.dict(os.environ, {"XDG_CACHE_HOME": str(tmp_path)}):
            # Create some test data
            cache = create_default_cache(tag="test_module")
            cache.set("test_key", "test_value")

            result = self.runner.invoke(app, ["cache", "show"])

            assert result.exit_code == 0
            assert "Glovebox Cache System Overview" in result.stdout
            cache.close()

    def test_cache_show_specific_module(self, tmp_path):
        """Test cache show for specific module."""
        with patch.dict(os.environ, {"XDG_CACHE_HOME": str(tmp_path)}):
            # Create some test data
            cache = create_default_cache(tag="layout")
            cache.set("test_key", "test_value")

            result = self.runner.invoke(app, ["cache", "show", "-m", "layout"])

            assert result.exit_code == 0
            cache.close()

    def test_cache_show_with_stats(self, tmp_path):
        """Test cache show with stats option."""
        with patch.dict(os.environ, {"XDG_CACHE_HOME": str(tmp_path)}):
            result = self.runner.invoke(app, ["cache", "show", "--stats"])

            assert result.exit_code == 0
            assert "Cache Performance Statistics" in result.stdout


class TestCacheKeysCommand:
    """Test the cache keys CLI command."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        reset_shared_cache_instances()
        # Register all commands to ensure cache commands are available
        register_all_commands(app)

    def teardown_method(self):
        """Clean up test environment."""
        reset_shared_cache_instances()

    def test_cache_keys_for_module(self, tmp_path):
        """Test listing cache keys for a specific module."""
        with patch.dict(os.environ, {"XDG_CACHE_HOME": str(tmp_path)}):
            # Create test data
            cache = create_default_cache(tag="test_module")
            cache.set("key1", "value1")
            cache.set("key2", "value2")
            cache.set("key3", "value3")

            result = self.runner.invoke(app, ["cache", "keys", "-m", "test_module"])

            assert result.exit_code == 0
            assert "key1" in result.stdout
            assert "key2" in result.stdout
            assert "key3" in result.stdout
            cache.close()

    def test_cache_keys_json_output(self, tmp_path):
        """Test cache keys command with JSON output."""
        with patch.dict(os.environ, {"XDG_CACHE_HOME": str(tmp_path)}):
            # Create test data
            cache = create_default_cache(tag="test_module")
            cache.set("test_key", "test_value")

            result = self.runner.invoke(
                app, ["cache", "keys", "-m", "test_module", "--json"]
            )

            assert result.exit_code == 0
            assert '"test_key"' in result.stdout
            cache.close()


class TestCacheDeleteCommand:
    """Test the cache delete CLI command."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        reset_shared_cache_instances()
        # Register all commands to ensure cache commands are available
        register_all_commands(app)

    def teardown_method(self):
        """Clean up test environment."""
        reset_shared_cache_instances()

    def test_cache_delete_specific_keys(self, tmp_path):
        """Test deleting specific cache keys."""
        with patch.dict(os.environ, {"XDG_CACHE_HOME": str(tmp_path)}):
            # Create test data
            cache = create_default_cache(tag="test_module")
            cache.set("key1", "value1")
            cache.set("key2", "value2")
            cache.set("key3", "value3")

            # Delete specific keys
            result = self.runner.invoke(
                app,
                [
                    "cache",
                    "delete",
                    "-m",
                    "test_module",
                    "--keys",
                    "key1,key2",
                    "--force",
                ],
            )

            assert result.exit_code == 0
            assert "Deleted" in result.stdout

            # Verify deletion
            assert cache.get("key1") is None
            assert cache.get("key2") is None
            assert cache.get("key3") == "value3"  # Should still exist
            cache.close()

    def test_cache_delete_pattern(self, tmp_path):
        """Test deleting cache keys by pattern."""
        with patch.dict(os.environ, {"XDG_CACHE_HOME": str(tmp_path)}):
            # Create test data
            cache = create_default_cache(tag="test_module")
            cache.set("test_key1", "value1")
            cache.set("test_key2", "value2")
            cache.set("other_key", "value3")

            # Delete keys matching pattern
            result = self.runner.invoke(
                app,
                [
                    "cache",
                    "delete",
                    "-m",
                    "test_module",
                    "--pattern",
                    "test_",
                    "--force",
                ],
            )

            assert result.exit_code == 0

            # Verify deletion
            assert cache.get("test_key1") is None
            assert cache.get("test_key2") is None
            assert cache.get("other_key") == "value3"  # Should still exist
            cache.close()
