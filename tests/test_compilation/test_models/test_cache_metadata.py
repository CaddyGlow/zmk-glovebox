"""Test cache metadata models."""

import time
from datetime import datetime
from pathlib import Path

import pytest

from glovebox.compilation.models.cache_metadata import (
    CacheConfig,
    CacheMetadata,
    CacheValidationResult,
    WorkspaceCacheEntry,
)


def test_cache_metadata_creation():
    """Test CacheMetadata model creation."""
    metadata = CacheMetadata(workspace_path="/test/workspace")

    assert metadata.workspace_path == "/test/workspace"
    assert metadata.cache_version == "1.0"
    assert metadata.west_modules == []
    assert metadata.manifest_hash == "unknown"
    assert metadata.config_hash == "unknown"
    assert metadata.west_version == "unknown"

    # Check that cached_at is a recent timestamp
    cached_timestamp = int(metadata.cached_at)
    current_timestamp = int(time.time())
    assert abs(current_timestamp - cached_timestamp) < 5  # Within 5 seconds


def test_cache_metadata_with_custom_values():
    """Test CacheMetadata with custom values."""
    metadata = CacheMetadata(
        workspace_path="/custom/workspace",
        cached_at="1234567890",
        west_modules=["zmk", "custom-module"],
        manifest_hash="abc123def456",
        config_hash="def456ghi789",
        west_version="west_installed",
    )

    assert metadata.workspace_path == "/custom/workspace"
    assert metadata.cached_at == "1234567890"
    assert metadata.west_modules == ["zmk", "custom-module"]
    assert metadata.manifest_hash == "abc123def456"
    assert metadata.config_hash == "def456ghi789"
    assert metadata.west_version == "west_installed"


def test_workspace_cache_entry():
    """Test WorkspaceCacheEntry model."""
    metadata = CacheMetadata(workspace_path="/test/workspace")

    entry = WorkspaceCacheEntry(
        workspace_name="test-workspace",
        workspace_path=Path("/test/workspace"),
        metadata=metadata,
        size_bytes=1024000,
    )

    assert entry.workspace_name == "test-workspace"
    assert entry.workspace_path == Path("/test/workspace")
    assert entry.metadata == metadata
    assert entry.size_bytes == 1024000
    assert isinstance(entry.last_used, datetime)


def test_cache_validation_result():
    """Test CacheValidationResult model."""
    result = CacheValidationResult(
        is_valid=False,
        reasons=["manifest_changed", "cache_expired"],
        cache_age_hours=25.5,
        needs_refresh=True,
    )

    assert result.is_valid is False
    assert result.reasons == ["manifest_changed", "cache_expired"]
    assert result.cache_age_hours == 25.5
    assert result.needs_refresh is True


def test_cache_validation_result_valid():
    """Test CacheValidationResult for valid cache."""
    result = CacheValidationResult(is_valid=True)

    assert result.is_valid is True
    assert result.reasons == []
    assert result.cache_age_hours == 0.0
    assert result.needs_refresh is False


def test_cache_config_defaults():
    """Test CacheConfig with default values."""
    config = CacheConfig()

    assert config.max_age_hours == 24.0
    assert config.max_cache_size_gb == 5.0
    assert config.cleanup_interval_hours == 6.0
    assert config.enable_compression is True
    assert config.enable_smart_invalidation is True


def test_cache_config_custom():
    """Test CacheConfig with custom values."""
    config = CacheConfig(
        max_age_hours=48.0,
        max_cache_size_gb=10.0,
        cleanup_interval_hours=12.0,
        enable_compression=False,
        enable_smart_invalidation=False,
    )

    assert config.max_age_hours == 48.0
    assert config.max_cache_size_gb == 10.0
    assert config.cleanup_interval_hours == 12.0
    assert config.enable_compression is False
    assert config.enable_smart_invalidation is False


def test_cache_metadata_validation():
    """Test CacheMetadata model validation."""
    metadata_data = {
        "workspace_path": "/validation/test",
        "cached_at": "1640995200",
        "cache_version": "2.0",
        "west_modules": ["zmk", "hal_nordic"],
        "manifest_hash": "abcdef123456",
        "config_hash": "654321fedcba",
        "west_version": "0.13.1",
    }

    metadata = CacheMetadata.model_validate(metadata_data)

    assert metadata.workspace_path == "/validation/test"
    assert metadata.cached_at == "1640995200"
    assert metadata.cache_version == "2.0"
    assert metadata.west_modules == ["zmk", "hal_nordic"]
    assert metadata.manifest_hash == "abcdef123456"
    assert metadata.config_hash == "654321fedcba"
    assert metadata.west_version == "0.13.1"
