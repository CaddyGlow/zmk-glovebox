"""Tests for build info generation in firmware models."""

import json
import tempfile
from pathlib import Path

import pytest

from glovebox.firmware.models import create_build_info_file, generate_build_info


def test_generate_build_info_basic(tmp_path):
    """Test basic build info generation."""
    # Create test files
    keymap_file = tmp_path / "test.keymap"
    config_file = tmp_path / "test.conf"
    keymap_file.write_text("/* Test keymap */")
    config_file.write_text("CONFIG_TEST=y")

    # Generate build info
    build_info = generate_build_info(
        keymap_content=keymap_file.read_text(),
        config_content=config_file.read_text(),
        repository="test/repo",
        branch="main",
        head_hash="abc123",
        build_mode="test",
    )

    # Verify basic structure
    assert build_info["repository"] == "test/repo"
    assert build_info["branch"] == "main"
    assert build_info["head_hash"] == "abc123"
    assert build_info["build_mode"] == "test"
    assert "timestamp" in build_info
    assert "files" in build_info
    assert "firmware" in build_info
    assert "layout" in build_info

    # Verify file information
    assert build_info["files"]["keymap"]["path"] == "test.keymap"
    assert build_info["files"]["config"]["path"] == "test.conf"
    assert build_info["files"]["keymap"]["sha256"] is not None
    assert build_info["files"]["config"]["sha256"] is not None


def test_generate_build_info_with_json_and_uf2(tmp_path):
    """Test build info generation with JSON layout and UF2 files."""
    # Create test files
    keymap_file = tmp_path / "test.keymap"
    config_file = tmp_path / "test.conf"
    json_file = tmp_path / "layout.json"
    uf2_file1 = tmp_path / "firmware_left.uf2"
    uf2_file2 = tmp_path / "firmware_right.uf2"

    keymap_file.write_text("/* Test keymap */")
    config_file.write_text("CONFIG_TEST=y")
    uf2_file1.write_bytes(b"fake uf2 content left")
    uf2_file2.write_bytes(b"fake uf2 content right")

    # Create JSON layout with metadata
    layout_data = {
        "layout": {
            "id": "test-uuid-123",
            "parent_uuid": "parent-uuid-456",
            "title": "Test Layout",
        },
        "layers": [],
    }
    json_file.write_text(json.dumps(layout_data))

    # Generate build info
    build_info = generate_build_info(
        keymap_content=keymap_file.read_text(),
        config_content=config_file.read_text(),
        repository="test/repo",
        branch="main",
        head_hash="abc123",
        build_mode="test",
        layout_uuid="test-uuid-123",
        uf2_files=[uf2_file1, uf2_file2],
        compilation_duration=45.67,
    )

    # Verify enhanced structure
    assert build_info["compilation_duration_seconds"] == 45.67
    assert "json" in build_info["files"]
    assert build_info["files"]["json"]["path"] == "layout.json"

    # Verify layout metadata
    assert build_info["layout"]["uuid"] == "test-uuid-123"
    assert build_info["layout"]["parent_uuid"] == "parent-uuid-456"
    assert build_info["layout"]["title"] == "Test Layout"

    # Verify firmware information
    assert build_info["firmware"]["total_files"] == 2
    assert len(build_info["firmware"]["uf2_files"]) == 2

    uf2_files_info = build_info["firmware"]["uf2_files"]
    assert any(f["path"] == "firmware_left.uf2" for f in uf2_files_info)
    assert any(f["path"] == "firmware_right.uf2" for f in uf2_files_info)

    # Verify UF2 file details
    for uf2_info in uf2_files_info:
        assert "sha256" in uf2_info
        assert "size_bytes" in uf2_info
        assert uf2_info["sha256"] is not None
        assert uf2_info["size_bytes"] > 0


def test_create_build_info_file(tmp_path):
    """Test creating build-info.json file."""
    # Create test files
    keymap_file = tmp_path / "test.keymap"
    config_file = tmp_path / "test.conf"
    artifacts_dir = tmp_path / "artifacts"

    keymap_file.write_text("/* Test keymap */")
    config_file.write_text("CONFIG_TEST=y")

    # Create build info file
    success = create_build_info_file(
        artifacts_dir=artifacts_dir,
        keymap_file=keymap_file,
        config_file=config_file,
        json_file=None,
        repository="test/repo",
        branch="main",
        head_hash="abc123",
        build_mode="test",
    )

    assert success

    # Verify file was created
    build_info_file = artifacts_dir / "build-info.json"
    assert build_info_file.exists()

    # Verify file content
    build_info_content = json.loads(build_info_file.read_text())
    assert build_info_content["repository"] == "test/repo"
    assert build_info_content["branch"] == "main"
    assert build_info_content["head_hash"] == "abc123"
    assert build_info_content["build_mode"] == "test"


def test_layout_metadata_extraction_fallbacks(tmp_path):
    """Test layout metadata extraction with various JSON structures."""
    keymap_file = tmp_path / "test.keymap"
    config_file = tmp_path / "test.conf"
    json_file = tmp_path / "layout.json"

    keymap_file.write_text("/* Test keymap */")
    config_file.write_text("CONFIG_TEST=y")

    # Test with top-level fields only
    layout_data = {
        "uuid": "top-level-uuid",
        "parent_uuid": "top-level-parent",
        "title": "Top Level Title",
        "layers": [],
    }
    json_file.write_text(json.dumps(layout_data))

    build_info = generate_build_info(
        keymap_content=keymap_file.read_text(),
        config_content=config_file.read_text(),
        repository="test/repo",
        branch="main",
        layout_uuid="top-level-uuid",
    )

    # Should extract from top-level fields
    assert build_info["layout"]["uuid"] == "top-level-uuid"
    assert build_info["layout"]["parent_uuid"] == "top-level-parent"
    assert build_info["layout"]["title"] == "Top Level Title"


def test_missing_files_handling(tmp_path):
    """Test handling of missing files."""
    keymap_file = tmp_path / "missing.keymap"
    config_file = tmp_path / "missing.conf"

    # Files don't exist, should handle gracefully
    build_info = generate_build_info(
        keymap_content="",
        config_content="",
        repository="test/repo",
        branch="main",
    )

    # Should still generate info but with None hashes
    assert build_info["files"]["keymap"]["sha256"] is None
    assert build_info["files"]["config"]["sha256"] is None
    assert build_info["repository"] == "test/repo"
