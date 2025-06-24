"""Tests for CompilationBuildCacheService."""

import json
import shutil
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from glovebox.compilation.cache.compilation_build_cache_service import (
    CompilationBuildCacheService,
)
from glovebox.config.user_config import UserConfig
from glovebox.core.cache.cache_manager import CacheManager


class TestCompilationBuildCacheService:
    """Test suite for CompilationBuildCacheService."""

    @pytest.fixture
    def mock_cache_manager(self) -> Mock:
        """Create a mock cache manager."""
        return Mock(spec=CacheManager)

    @pytest.fixture
    def service(
        self, isolated_config: UserConfig, mock_cache_manager: Mock
    ) -> CompilationBuildCacheService:
        """Create CompilationBuildCacheService instance."""
        return CompilationBuildCacheService(isolated_config, mock_cache_manager)

    @pytest.fixture
    def sample_build_dir(self, tmp_path: Path) -> Path:
        """Create a sample build directory with artifacts."""
        build_dir = tmp_path / "sample_build"
        build_dir.mkdir()

        # Create sample build artifacts
        (build_dir / "zmk.uf2").write_bytes(b"fake firmware data")
        (build_dir / "zmk.hex").write_text("fake hex data")
        (build_dir / "zmk.kconfig").write_text("CONFIG_ZMK=y\n")
        (build_dir / "zmk.dts").write_text("device tree source")

        return build_dir

    @pytest.fixture
    def sample_keymap_file(self, tmp_path: Path) -> Path:
        """Create a sample keymap file."""
        keymap_file = tmp_path / "keymap.keymap"
        keymap_file.write_text("""
            #include <behaviors.dtsi>
            #include <dt-bindings/zmk/keys.h>

            / {
                keymap {
                    compatible = "zmk,keymap";
                    default_layer {
                        bindings = <&kp A &kp B>;
                    };
                };
            };
        """)
        return keymap_file

    @pytest.fixture
    def sample_config_file(self, tmp_path: Path) -> Path:
        """Create a sample config file."""
        config_file = tmp_path / "config.conf"
        config_file.write_text('CONFIG_ZMK_KEYBOARD_NAME="test"\n')
        return config_file

    def test_generate_cache_key_basic(self, service: CompilationBuildCacheService):
        """Test basic cache key generation."""
        cache_key = service.generate_cache_key(
            repository="zmkfirmware/zmk",
            branch="main",
            config_hash="config123",
            keymap_hash="keymap456",
        )

        assert cache_key.startswith("compilation_build_")

        # Test that the same inputs generate the same key (deterministic)
        cache_key2 = service.generate_cache_key(
            repository="zmkfirmware/zmk",
            branch="main",
            config_hash="config123",
            keymap_hash="keymap456",
        )
        assert cache_key == cache_key2

        # Test that different inputs generate different keys
        cache_key3 = service.generate_cache_key(
            repository="zmkfirmware/zmk",
            branch="develop",
            config_hash="config123",
            keymap_hash="keymap456",
        )
        assert cache_key != cache_key3

    def test_generate_cache_key_with_file_paths(
        self,
        service: CompilationBuildCacheService,
        sample_keymap_file: Path,
        sample_config_file: Path,
    ):
        """Test cache key generation with actual file paths."""
        cache_key = service.generate_cache_key_from_files(
            repository="zmkfirmware/zmk",
            branch="main",
            config_file=sample_config_file,
            keymap_file=sample_keymap_file,
        )

        assert cache_key.startswith("compilation_build_")

        # Test deterministic generation with same files
        cache_key2 = service.generate_cache_key_from_files(
            repository="zmkfirmware/zmk",
            branch="main",
            config_file=sample_config_file,
            keymap_file=sample_keymap_file,
        )
        assert cache_key == cache_key2

    def test_cache_build_result_success(
        self,
        service: CompilationBuildCacheService,
        sample_build_dir: Path,
        mock_cache_manager: Mock,
    ):
        """Test successful build result caching."""
        cache_key = "test_cache_key"
        mock_cache_manager.set.return_value = True

        result = service.cache_build_result(sample_build_dir, cache_key)

        assert result is True
        mock_cache_manager.set.assert_called_once()
        call_args = mock_cache_manager.set.call_args
        assert call_args[0][0] == cache_key  # cache key
        assert call_args[1]["ttl"] == 3600  # TTL should be 3600 seconds

    def test_cache_build_result_nonexistent_directory(
        self,
        service: CompilationBuildCacheService,
        tmp_path: Path,
        mock_cache_manager: Mock,
    ):
        """Test caching with non-existent build directory."""
        nonexistent_dir = tmp_path / "nonexistent"
        cache_key = "test_cache_key"

        result = service.cache_build_result(nonexistent_dir, cache_key)

        assert result is False
        mock_cache_manager.set.assert_not_called()

    def test_get_cached_build_hit(
        self,
        service: CompilationBuildCacheService,
        mock_cache_manager: Mock,
        tmp_path: Path,
    ):
        """Test cache hit scenario."""
        cache_key = "test_cache_key"
        cached_build_dir = tmp_path / "cached_build"
        cached_build_dir.mkdir()
        (cached_build_dir / "zmk.uf2").write_bytes(b"cached firmware")

        # Mock cache hit
        cache_data = {
            "build_artifacts": ["zmk.uf2"],
            "cached_path": str(cached_build_dir),
            "created_at": "2024-01-01T00:00:00",
        }
        mock_cache_manager.get.return_value = cache_data

        result = service.get_cached_build(cache_key)

        assert result is not None
        assert result == cached_build_dir
        mock_cache_manager.get.assert_called_once_with(cache_key)

    def test_get_cached_build_miss(
        self, service: CompilationBuildCacheService, mock_cache_manager: Mock
    ):
        """Test cache miss scenario."""
        cache_key = "test_cache_key"
        mock_cache_manager.get.return_value = None

        result = service.get_cached_build(cache_key)

        assert result is None
        mock_cache_manager.get.assert_called_once_with(cache_key)

    def test_get_cached_build_stale_entry(
        self,
        service: CompilationBuildCacheService,
        mock_cache_manager: Mock,
        tmp_path: Path,
    ):
        """Test handling of stale cache entries (cached path no longer exists)."""
        cache_key = "test_cache_key"
        nonexistent_path = tmp_path / "nonexistent_build"

        # Mock cache hit with non-existent path
        cache_data = {
            "build_artifacts": ["zmk.uf2"],
            "cached_path": str(nonexistent_path),
            "created_at": "2024-01-01T00:00:00",
        }
        mock_cache_manager.get.return_value = cache_data

        result = service.get_cached_build(cache_key)

        assert result is None
        # Should clean up stale entry
        mock_cache_manager.delete.assert_called_once_with(cache_key)

    def test_delete_cached_build(
        self,
        service: CompilationBuildCacheService,
        mock_cache_manager: Mock,
        tmp_path: Path,
    ):
        """Test cached build deletion."""
        cache_key = "test_cache_key"
        cached_build_dir = tmp_path / "cached_build"
        cached_build_dir.mkdir()
        (cached_build_dir / "zmk.uf2").write_bytes(b"cached firmware")

        # Mock cache data
        cache_data = {
            "build_artifacts": ["zmk.uf2"],
            "cached_path": str(cached_build_dir),
            "created_at": "2024-01-01T00:00:00",
        }
        mock_cache_manager.get.return_value = cache_data
        mock_cache_manager.delete.return_value = True

        result = service.delete_cached_build(cache_key)

        assert result is True
        mock_cache_manager.delete.assert_called_once_with(cache_key)
        assert not cached_build_dir.exists()  # Directory should be removed

    def test_list_cached_builds(
        self, service: CompilationBuildCacheService, mock_cache_manager: Mock
    ):
        """Test listing cached builds."""
        # Mock cache keys
        mock_cache_manager.keys.return_value = [
            "compilation_build_key1",
            "compilation_build_key2",
            "other_cache_key",  # Should be filtered out
        ]

        # Mock cache data
        cache_data_1 = {
            "build_artifacts": ["zmk.uf2"],
            "cached_path": "/path/to/build1",
            "created_at": "2024-01-01T00:00:00",
        }
        cache_data_2 = {
            "build_artifacts": ["zmk.uf2", "zmk.hex"],
            "cached_path": "/path/to/build2",
            "created_at": "2024-01-01T01:00:00",
        }

        mock_cache_manager.get.side_effect = [cache_data_1, cache_data_2]

        cached_builds = service.list_cached_builds()

        assert len(cached_builds) == 2
        assert all("compilation_build_" in key for key, _ in cached_builds)

    def test_cleanup_stale_entries(
        self,
        service: CompilationBuildCacheService,
        mock_cache_manager: Mock,
        tmp_path: Path,
    ):
        """Test cleanup of stale cache entries."""
        # Create some build directories
        build1 = tmp_path / "build1"
        build1.mkdir()
        build2 = tmp_path / "build2"
        # build2 doesn't exist (stale)

        # Mock cache data
        cache_data_1 = {
            "build_artifacts": ["zmk.uf2"],
            "cached_path": str(build1),
            "created_at": "2024-01-01T00:00:00",
        }
        cache_data_2 = {
            "build_artifacts": ["zmk.uf2"],
            "cached_path": str(build2),
            "created_at": "2024-01-01T00:00:00",
        }

        mock_cache_manager.keys.return_value = [
            "compilation_build_key1",
            "compilation_build_key2",
        ]
        # Mock the get calls for list_cached_builds and then for cleanup
        mock_cache_manager.get.side_effect = [cache_data_1, cache_data_2, cache_data_2]
        mock_cache_manager.delete.return_value = True  # Mock successful deletion

        cleaned_count = service.cleanup_stale_entries()

        assert cleaned_count == 1  # Only one stale entry should be cleaned
        mock_cache_manager.delete.assert_called_once_with("compilation_build_key2")

    def test_get_cache_directory(
        self,
        service: CompilationBuildCacheService,
        isolated_config: UserConfig,
        tmp_path: Path,
    ):
        """Test cache directory path generation."""
        expected_path = isolated_config._config.cache_path / "compilation" / "builds"
        cache_dir = service.get_cache_directory()

        assert cache_dir == expected_path

    def test_cache_build_result_creates_directory_structure(
        self,
        service: CompilationBuildCacheService,
        sample_build_dir: Path,
        mock_cache_manager: Mock,
        isolated_config: UserConfig,
    ):
        """Test that caching creates proper directory structure."""
        cache_key = "test_cache_key"
        mock_cache_manager.set.return_value = True

        result = service.cache_build_result(sample_build_dir, cache_key)

        assert result is True
        # Check that cache directory structure is created
        expected_cache_dir = (
            isolated_config._config.cache_path / "compilation" / "builds"
        )
        assert expected_cache_dir.exists()

    def test_integration_cache_and_retrieve(
        self,
        isolated_config: UserConfig,
        isolated_cache_environment: dict[str, Any],
        sample_build_dir: Path,
        sample_keymap_file: Path,
        sample_config_file: Path,
    ):
        """Integration test: cache a build and retrieve it."""
        # Use real cache manager for integration test
        from glovebox.core.cache import create_default_cache

        cache_manager = create_default_cache(tag="compilation_test")
        service = CompilationBuildCacheService(isolated_config, cache_manager)

        # Generate cache key
        cache_key = service.generate_cache_key_from_files(
            repository="zmkfirmware/zmk",
            branch="main",
            config_file=sample_config_file,
            keymap_file=sample_keymap_file,
        )

        # Cache the build
        cache_result = service.cache_build_result(sample_build_dir, cache_key)
        assert cache_result is True

        # Retrieve the cached build
        retrieved_build = service.get_cached_build(cache_key)
        assert retrieved_build is not None
        assert retrieved_build.exists()
        assert (retrieved_build / "zmk.uf2").exists()

        # Verify build artifacts were copied correctly
        original_uf2 = sample_build_dir / "zmk.uf2"
        cached_uf2 = retrieved_build / "zmk.uf2"
        assert original_uf2.read_bytes() == cached_uf2.read_bytes()
