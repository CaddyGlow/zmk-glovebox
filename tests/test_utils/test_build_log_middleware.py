"""Tests for build log capture middleware."""

from pathlib import Path

from glovebox.cli.components.noop_progress_context import get_noop_progress_context
from glovebox.utils.build_log_middleware import (
    BuildLogCaptureMiddleware,
    create_build_log_middleware,
)


def test_build_log_middleware_basic_capture(tmp_path):
    """Test basic log capture functionality."""
    log_file = tmp_path / "test_build.log"
    middleware = BuildLogCaptureMiddleware(log_file, get_noop_progress_context())

    # Process some test output
    middleware.process("Building project...", "stdout")
    middleware.process("Error: missing dependency", "stderr")
    middleware.process("Build completed successfully", "stdout")

    # Close the middleware
    middleware.close()

    # Check log file was created and contains expected content
    assert log_file.exists()
    log_content = log_file.read_text()

    # Check header was written
    assert "# Build Log -" in log_content
    assert "# Format: [timestamp] [stream] output" in log_content

    # Check output lines were captured
    assert "Building project..." in log_content
    assert "Error: missing dependency" in log_content
    assert "Build completed successfully" in log_content

    # Check stream types are indicated
    assert "[STDOUT]" in log_content
    assert "[STDERR]" in log_content


def test_build_log_middleware_with_factory(tmp_path):
    """Test build log middleware creation via factory function."""
    artifacts_dir = tmp_path / "artifacts"
    middleware = create_build_log_middleware(
        artifacts_dir, get_noop_progress_context(), "custom_build.log"
    )

    # Process some output
    middleware.process("Factory test output", "stdout")
    middleware.close()

    # Check log file was created in the right location
    log_file = artifacts_dir / "custom_build.log"
    assert log_file.exists()
    assert "Factory test output" in log_file.read_text()


def test_build_log_middleware_timestamps_and_stream_types(tmp_path):
    """Test timestamp and stream type configuration."""
    log_file = tmp_path / "test_config.log"

    # Test with both timestamps and stream types enabled
    middleware = BuildLogCaptureMiddleware(
        log_file,
        get_noop_progress_context(),
        include_timestamps=True,
        include_stream_type=True,
    )
    middleware.process("Test with full config", "stdout")
    middleware.close()

    log_content = log_file.read_text()
    assert "[STDOUT]" in log_content
    assert "Test with full config" in log_content
    # Should contain timestamp pattern
    import re

    timestamp_pattern = r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}\]"
    assert re.search(timestamp_pattern, log_content)


def test_build_log_middleware_minimal_config(tmp_path):
    """Test middleware with minimal configuration."""
    log_file = tmp_path / "test_minimal.log"

    # Test with timestamps and stream types disabled
    middleware = BuildLogCaptureMiddleware(
        log_file,
        get_noop_progress_context(),
        include_timestamps=False,
        include_stream_type=False,
    )
    middleware.process("Simple output", "stdout")
    middleware.close()

    log_content = log_file.read_text()
    lines = log_content.strip().split("\n")

    # Find the line with our output (skip header lines)
    output_lines = [line for line in lines if "Simple output" in line]
    assert len(output_lines) == 1
    # Should just be the raw output
    assert output_lines[0].strip() == "Simple output"


def test_build_log_middleware_return_value_passthrough(tmp_path):
    """Test that middleware passes through original output for chaining."""
    log_file = tmp_path / "test_passthrough.log"
    middleware = BuildLogCaptureMiddleware(log_file, get_noop_progress_context())

    # Test that the middleware returns the original line
    result = middleware.process("Original output", "stdout")
    assert result == "Original output"

    middleware.close()


def test_build_log_middleware_context_manager(tmp_path):
    """Test middleware as context manager."""
    log_file = tmp_path / "test_context.log"

    with BuildLogCaptureMiddleware(log_file, get_noop_progress_context()) as middleware:
        middleware.process("Context manager test", "stdout")

    # File should be closed automatically
    assert log_file.exists()
    assert "Context manager test" in log_file.read_text()


def test_build_log_middleware_file_creation_error(tmp_path):
    """Test handling of file creation errors."""
    # Try to create log file in a non-existent directory without permission
    invalid_path = Path("/nonexistent/path/build.log")
    middleware = BuildLogCaptureMiddleware(invalid_path, get_noop_progress_context())

    # Should handle the error gracefully and just pass through output
    result = middleware.process("Test output", "stdout")
    assert result == "Test output"

    # Should not crash when closing
    middleware.close()


def test_build_log_middleware_artifacts_directory_creation(tmp_path):
    """Test that artifacts directory is created by factory function."""
    artifacts_dir = tmp_path / "nested" / "artifacts"

    # Directory doesn't exist yet
    assert not artifacts_dir.exists()

    # Create middleware via factory - should create parent directories
    middleware = create_build_log_middleware(artifacts_dir, get_noop_progress_context())

    # Directory should be created when initializing the log file
    assert artifacts_dir.exists()

    middleware.process("Test", "stdout")
    middleware.close()

    # Log file should exist
    log_file = artifacts_dir / "build.log"
    assert log_file.exists()


def test_build_log_middleware_multiple_outputs(tmp_path):
    """Test capturing multiple lines of output."""
    log_file = tmp_path / "test_multiple.log"
    middleware = BuildLogCaptureMiddleware(log_file, get_noop_progress_context())

    # Simulate a build with multiple output lines
    build_outputs = [
        ("Starting build...", "stdout"),
        ("Compiling source files", "stdout"),
        ("Warning: deprecated function", "stderr"),
        ("Linking binaries", "stdout"),
        ("Build completed", "stdout"),
    ]

    for output, stream in build_outputs:
        middleware.process(output, stream)

    middleware.close()

    log_content = log_file.read_text()

    # All outputs should be captured
    for output, _ in build_outputs:
        assert output in log_content

    # Should have correct stream indicators
    assert log_content.count("[STDOUT]") == 4  # 4 stdout lines
    assert log_content.count("[STDERR]") == 1  # 1 stderr line
