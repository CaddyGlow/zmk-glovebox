"""Test CacheManager class."""

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.compilation.models.cache_metadata import (
    CacheConfig,
    CacheMetadata,
    CacheValidationResult,
)
from glovebox.compilation.workspace.cache_manager import (
    CacheManager,
    CacheManagerError,
    create_cache_manager,
)
from glovebox.config.compile_methods import CompilationConfig


class TestCacheManager:
    """Test CacheManager functionality."""

    def setup_method(self):
        """Set up test instance."""
        self.cache_config = CacheConfig(
            max_age_hours=24.0,
            max_cache_size_gb=1.0,
            cleanup_interval_hours=6.0,
        )
        self.manager = CacheManager(self.cache_config)

    def test_initialization(self):
        """Test manager initialization."""
        assert hasattr(self.manager, "logger")
        assert self.manager.cache_config.max_age_hours == 24.0

    def test_initialization_default_config(self):
        """Test manager initialization with default config."""
        manager = CacheManager()
        assert manager.cache_config.max_age_hours == 24.0
        assert manager.cache_config.max_cache_size_gb == 5.0

    def test_create_cache_manager(self):
        """Test factory function."""
        manager = create_cache_manager()
        assert isinstance(manager, CacheManager)

    def test_create_cache_manager_with_config(self):
        """Test factory function with custom config."""
        config = CacheConfig(max_age_hours=12.0)
        manager = create_cache_manager(config)
        assert manager.cache_config.max_age_hours == 12.0

    def test_cache_workspace_success(self):
        """Test successful workspace caching."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "test_workspace"
            workspace_path.mkdir()

            # Create test files
            (workspace_path / "west.yml").write_text("manifest: {}")
            (workspace_path / "build.yaml").write_text("include: []")

            result = self.manager.cache_workspace(workspace_path)
            assert result is True

            # Verify cache directory was created
            cache_dir = self.manager._get_cache_directory(workspace_path)
            assert cache_dir.exists()

            # Verify metadata file was created
            metadata_file = cache_dir / f"{workspace_path.name}_metadata.json"
            assert metadata_file.exists()

            # Verify metadata content
            with metadata_file.open(encoding="utf-8") as f:
                metadata = json.load(f)
            assert metadata["workspace_path"] == str(workspace_path)
            assert "cached_at" in metadata

    def test_cache_workspace_with_snapshot(self):
        """Test workspace caching with snapshot creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "large_workspace"
            workspace_path.mkdir()

            # Create .west directory with substantial content
            west_dir = workspace_path / ".west"
            west_dir.mkdir()
            large_file = west_dir / "large_file.bin"
            large_file.write_bytes(b"x" * (15 * 1024 * 1024))  # 15MB file

            with patch.object(
                self.manager, "_create_workspace_snapshot", return_value=True
            ) as mock_snapshot:
                result = self.manager.cache_workspace(workspace_path)
                assert result is True
                mock_snapshot.assert_called_once()

    def test_cache_workspace_error_handling(self):
        """Test cache workspace error handling."""
        # Test with permission denied scenario
        with (
            patch("pathlib.Path.mkdir", side_effect=PermissionError("Access denied")),
            pytest.raises(CacheManagerError),
        ):
            self.manager.cache_workspace(Path("/tmp/test_workspace"))

    def test_is_cache_valid_no_cache(self):
        """Test cache validation with no existing cache."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "no_cache_workspace"
            workspace_path.mkdir()

            config = Mock(spec=CompilationConfig)
            result = self.manager.is_cache_valid(workspace_path, config)
            assert result is False

    def test_is_cache_valid_fresh_cache(self):
        """Test cache validation with fresh valid cache."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "fresh_workspace"
            workspace_path.mkdir()

            # Create test files
            (workspace_path / "west.yml").write_text("manifest: {}")

            # Cache the workspace first
            self.manager.cache_workspace(workspace_path)

            config = Mock(spec=CompilationConfig)
            result = self.manager.is_cache_valid(workspace_path, config)
            assert result is True

    def test_validate_cache_detailed(self):
        """Test detailed cache validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "detailed_workspace"
            workspace_path.mkdir()

            # Create test files
            (workspace_path / "west.yml").write_text("manifest: {}")

            # Cache the workspace
            self.manager.cache_workspace(workspace_path)

            config = Mock(spec=CompilationConfig)
            result = self.manager.validate_cache(workspace_path, config)

            assert isinstance(result, CacheValidationResult)
            assert result.is_valid is True
            assert len(result.reasons) == 0
            assert result.cache_age_hours >= 0

    def test_validate_cache_old_cache(self):
        """Test cache validation with old cache."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "old_workspace"
            workspace_path.mkdir()

            cache_dir = self.manager._get_cache_directory(workspace_path)
            cache_dir.mkdir(parents=True, exist_ok=True)

            # Create old metadata
            old_metadata = CacheMetadata(
                workspace_path=str(workspace_path),
                cached_at=str(int(time.time() - 25 * 3600)),  # 25 hours ago
            )

            metadata_file = cache_dir / f"{workspace_path.name}_metadata.json"
            with metadata_file.open("w", encoding="utf-8") as f:
                f.write(old_metadata.model_dump_json())

            config = Mock(spec=CompilationConfig)
            result = self.manager.validate_cache(workspace_path, config)

            assert result.is_valid is False
            assert any("too old" in reason for reason in result.reasons)
            assert result.cache_age_hours > 24

    def test_validate_cache_changed_manifest(self):
        """Test cache validation with changed manifest."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "changed_workspace"
            workspace_path.mkdir()

            # Create initial west.yml
            west_yml = workspace_path / "west.yml"
            west_yml.write_text("manifest: {initial: true}")

            # Cache the workspace
            self.manager.cache_workspace(workspace_path)

            # Change the manifest
            west_yml.write_text("manifest: {modified: true}")

            config = Mock(spec=CompilationConfig)
            result = self.manager.validate_cache(workspace_path, config)

            assert result.is_valid is False
            assert any("Manifest hash changed" in reason for reason in result.reasons)

    def test_cleanup_old_caches_success(self):
        """Test successful cleanup of old caches."""
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch.object(
                self.manager, "_get_cache_base_directory", return_value=Path(temp_dir)
            ),
        ):
            # Create cache directories with old metadata
            old_cache_dir = Path(temp_dir) / "old_cache"
            old_cache_dir.mkdir()

            old_metadata = {
                "workspace_path": "/tmp/old_workspace",
                "cached_at": str(int(time.time() - 8 * 24 * 3600)),  # 8 days ago
            }

            metadata_file = old_cache_dir / "old_workspace_metadata.json"
            with metadata_file.open("w", encoding="utf-8") as f:
                json.dump(old_metadata, f)

            # Create additional cache files
            (old_cache_dir / "old_workspace_snapshot.tar.gz").touch()

            result = self.manager.cleanup_old_caches(max_age_days=7)
            assert result is True

            # Verify old files were removed
            assert not metadata_file.exists()
            assert not (old_cache_dir / "old_workspace_snapshot.tar.gz").exists()

    def test_cleanup_old_caches_no_cache_dir(self):
        """Test cleanup when no cache directory exists."""
        with patch.object(
            self.manager,
            "_get_cache_base_directory",
            return_value=Path("/nonexistent/cache"),
        ):
            result = self.manager.cleanup_old_caches()
            assert result is True

    def test_get_cache_statistics(self):
        """Test cache statistics gathering."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "stats_workspace"
            workspace_path.mkdir()

            # Cache a workspace to create statistics
            (workspace_path / "west.yml").write_text("manifest: {}")

            # Mock the cache base directory to point to our temp directory
            cache_base = Path(temp_dir) / "cache_base"
            cache_base.mkdir()

            with patch.object(
                self.manager, "_get_cache_base_directory", return_value=cache_base
            ):
                self.manager.cache_workspace(workspace_path)
                stats = self.manager.get_cache_statistics()

                assert "total_size_bytes" in stats
                assert "total_entries" in stats
                assert "cache_directories" in stats
                assert stats["total_entries"] >= 1  # At least one metadata file

    def test_get_cache_statistics_no_cache(self):
        """Test cache statistics with no cache directory."""
        with patch.object(
            self.manager,
            "_get_cache_base_directory",
            return_value=Path("/nonexistent/cache"),
        ):
            stats = self.manager.get_cache_statistics()
            assert stats["total_size_bytes"] == 0
            assert stats["total_entries"] == 0

    def test_get_west_modules(self):
        """Test west modules extraction."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir)

            # Test with no west.yml
            modules = self.manager._get_west_modules(workspace_path)
            assert modules == []

            # Test with west.yml
            (workspace_path / "west.yml").write_text("manifest: {}")
            modules = self.manager._get_west_modules(workspace_path)
            assert "zmk" in modules

    def test_calculate_manifest_hash(self):
        """Test manifest hash calculation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir)

            # Test with no west.yml
            hash_result = self.manager._calculate_manifest_hash(workspace_path)
            assert hash_result == "unknown"

            # Test with west.yml
            west_yml = workspace_path / "west.yml"
            west_yml.write_text("manifest: {test: true}")
            hash_result = self.manager._calculate_manifest_hash(workspace_path)
            assert hash_result != "unknown"
            assert len(hash_result) == 16  # 16-character hash

            # Same content should produce same hash
            hash_result2 = self.manager._calculate_manifest_hash(workspace_path)
            assert hash_result == hash_result2

    def test_calculate_config_hash(self):
        """Test config hash calculation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir)

            # Test with no config files
            hash_result = self.manager._calculate_config_hash(workspace_path)
            assert hash_result != "unknown"  # Should still produce a hash

            # Test with config files
            (workspace_path / "build.yaml").write_text("include: []")
            config_dir = workspace_path / "config"
            config_dir.mkdir()
            (config_dir / "test.conf").write_text("CONFIG_TEST=y")

            hash_result = self.manager._calculate_config_hash(workspace_path)
            assert hash_result != "unknown"
            assert len(hash_result) == 16

    def test_should_create_cache_snapshot(self):
        """Test snapshot creation decision logic."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir)

            # Test with no .west directory
            result = self.manager._should_create_cache_snapshot(workspace_path)
            assert result is False

            # Test with small .west directory
            west_dir = workspace_path / ".west"
            west_dir.mkdir()
            (west_dir / "small_file").write_bytes(b"small")
            result = self.manager._should_create_cache_snapshot(workspace_path)
            assert result is False

            # Test with large .west directory
            (west_dir / "large_file").write_bytes(b"x" * (15 * 1024 * 1024))  # 15MB
            result = self.manager._should_create_cache_snapshot(workspace_path)
            assert result is True

    def test_create_workspace_snapshot(self):
        """Test workspace snapshot creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "snapshot_workspace"
            workspace_path.mkdir()
            cache_dir = Path(temp_dir) / "cache"
            cache_dir.mkdir()

            result = self.manager._create_workspace_snapshot(workspace_path, cache_dir)
            assert result is True

            # Verify snapshot metadata was created
            snapshot_meta_file = cache_dir / f"{workspace_path.name}_snapshot_meta.json"
            assert snapshot_meta_file.exists()

            with snapshot_meta_file.open(encoding="utf-8") as f:
                metadata = json.load(f)
            assert metadata["workspace_path"] == str(workspace_path)
            assert "created_at" in metadata

    def test_remove_cache_files(self):
        """Test cache file removal."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir)

            # Create test cache files
            files_to_create = [
                "test_metadata.json",
                "test_snapshot.tar.gz",
                "test_snapshot_meta.json",
            ]

            for filename in files_to_create:
                (cache_dir / filename).touch()

            # Remove cache files
            self.manager._remove_cache_files(cache_dir, "test")

            # Verify files were removed
            for filename in files_to_create:
                assert not (cache_dir / filename).exists()

    def test_error_handling_edge_cases(self):
        """Test error handling for edge cases."""
        # Test validation with corrupted metadata
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "corrupted_workspace"
            workspace_path.mkdir()

            cache_dir = self.manager._get_cache_directory(workspace_path)
            cache_dir.mkdir(parents=True, exist_ok=True)

            # Create corrupted metadata file
            metadata_file = cache_dir / f"{workspace_path.name}_metadata.json"
            metadata_file.write_text("invalid json content")

            config = Mock(spec=CompilationConfig)

            with pytest.raises(CacheManagerError):
                self.manager.validate_cache(workspace_path, config)


class TestCacheManagerIntegration:
    """Test CacheManager integration scenarios."""

    def setup_method(self):
        """Set up test instance."""
        self.manager = CacheManager()

    def test_cache_workflow_lifecycle(self):
        """Test complete cache workflow lifecycle."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "lifecycle_workspace"
            workspace_path.mkdir()

            # Create test workspace files
            (workspace_path / "west.yml").write_text("manifest: {version: 1}")
            (workspace_path / "build.yaml").write_text("include: [{board: test}]")
            config_dir = workspace_path / "config"
            config_dir.mkdir()
            (config_dir / "test.keymap").write_text("/* test keymap */")

            config = Mock(spec=CompilationConfig)

            # 1. Initial cache validation (should be invalid)
            assert self.manager.is_cache_valid(workspace_path, config) is False

            # 2. Cache the workspace
            cache_result = self.manager.cache_workspace(workspace_path)
            assert cache_result is True

            # 3. Validate fresh cache (should be valid)
            assert self.manager.is_cache_valid(workspace_path, config) is True

            # 4. Get detailed validation
            validation = self.manager.validate_cache(workspace_path, config)
            assert validation.is_valid is True
            assert len(validation.reasons) == 0

            # 5. Modify manifest (should invalidate cache)
            (workspace_path / "west.yml").write_text("manifest: {version: 2}")
            assert self.manager.is_cache_valid(workspace_path, config) is False

            # 6. Re-cache with new content
            cache_result = self.manager.cache_workspace(workspace_path)
            assert cache_result is True

            # 7. Should be valid again
            assert self.manager.is_cache_valid(workspace_path, config) is True

    def test_multiple_workspace_caching(self):
        """Test caching multiple workspaces."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspaces = []
            config = Mock(spec=CompilationConfig)

            # Mock the cache base directory to point to our temp directory
            cache_base = Path(temp_dir) / "cache_base"
            cache_base.mkdir()

            with patch.object(
                self.manager, "_get_cache_base_directory", return_value=cache_base
            ):
                # Create and cache multiple workspaces
                for i in range(3):
                    workspace_path = Path(temp_dir) / f"workspace_{i}"
                    workspace_path.mkdir()
                    (workspace_path / "west.yml").write_text(f"manifest: {{id: {i}}}")
                    workspaces.append(workspace_path)

                    # Cache each workspace
                    assert self.manager.cache_workspace(workspace_path) is True
                    assert self.manager.is_cache_valid(workspace_path, config) is True

                # Get statistics
                stats = self.manager.get_cache_statistics()
                assert stats["total_entries"] >= 3  # At least 3 workspaces

                # Cleanup old caches
                cleanup_result = self.manager.cleanup_old_caches(max_age_days=0)
                assert cleanup_result is True

    def test_cache_invalidation_scenarios(self):
        """Test various cache invalidation scenarios."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "invalidation_workspace"
            workspace_path.mkdir()

            config = Mock(spec=CompilationConfig)

            # Create initial workspace
            (workspace_path / "west.yml").write_text("manifest: {test: initial}")
            (workspace_path / "build.yaml").write_text("include: []")

            # Cache workspace
            self.manager.cache_workspace(workspace_path)
            assert self.manager.is_cache_valid(workspace_path, config) is True

            # Test manifest change invalidation
            (workspace_path / "west.yml").write_text("manifest: {test: modified}")
            validation = self.manager.validate_cache(workspace_path, config)
            assert validation.is_valid is False
            assert "Manifest hash changed" in validation.reasons

            # Re-cache and test config change invalidation
            self.manager.cache_workspace(workspace_path)
            (workspace_path / "build.yaml").write_text("include: [{board: new}]")
            validation = self.manager.validate_cache(workspace_path, config)
            assert validation.is_valid is False
            assert "Config hash changed" in validation.reasons

    def test_cache_performance_simulation(self):
        """Test cache performance with simulated large workspace."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "perf_workspace"
            workspace_path.mkdir()

            # Create simulated large workspace structure
            (workspace_path / "west.yml").write_text("manifest: {modules: [zmk]}")

            # Create .west directory with multiple files
            west_dir = workspace_path / ".west"
            west_dir.mkdir()
            for i in range(5):
                (west_dir / f"module_{i}.txt").write_text(f"module {i} content")

            # Create config directory with multiple files
            config_dir = workspace_path / "config"
            config_dir.mkdir()
            (config_dir / "test.keymap").write_text("/* test keymap */")
            (config_dir / "test.conf").write_text("CONFIG_TEST=y")

            config = Mock(spec=CompilationConfig)

            # Measure cache operations
            start_time = time.time()
            cache_result = self.manager.cache_workspace(workspace_path)
            cache_time = time.time() - start_time

            assert cache_result is True
            assert cache_time < 1.0  # Should complete in under 1 second

            # Measure validation operations
            start_time = time.time()
            validation_result = self.manager.validate_cache(workspace_path, config)
            validation_time = time.time() - start_time

            assert validation_result.is_valid is True
            assert validation_time < 0.5  # Should complete in under 0.5 seconds
