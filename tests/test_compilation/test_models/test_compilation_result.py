"""Test compilation result models."""

from pathlib import Path

import pytest

from glovebox.compilation.models.compilation_result import (
    BuildMatrixResult,
    CompilationResult,
    StrategyResult,
)
from glovebox.firmware.models import BuildResult, FirmwareOutputFiles


def test_strategy_result():
    """Test StrategyResult model."""
    result = StrategyResult(
        strategy_name="west",
        success=True,
        execution_time_seconds=45.2,
        memory_usage_mb=128.5,
        artifacts_generated=2,
        warnings=["Config option deprecated"],
    )

    assert result.strategy_name == "west"
    assert result.success is True
    assert result.execution_time_seconds == 45.2
    assert result.memory_usage_mb == 128.5
    assert result.artifacts_generated == 2
    assert result.error_message is None
    assert result.warnings == ["Config option deprecated"]


def test_strategy_result_failure():
    """Test StrategyResult for failed compilation."""
    result = StrategyResult(
        strategy_name="zmk_config",
        success=False,
        execution_time_seconds=12.1,
        error_message="Build failed: missing board definition",
        warnings=["Board not found in manifest"],
    )

    assert result.strategy_name == "zmk_config"
    assert result.success is False
    assert result.execution_time_seconds == 12.1
    assert result.error_message == "Build failed: missing board definition"
    assert result.warnings == ["Board not found in manifest"]


def test_build_matrix_result():
    """Test BuildMatrixResult model."""
    target_results = {
        "corne_left": StrategyResult(strategy_name="west", success=True),
        "corne_right": StrategyResult(strategy_name="west", success=True),
        "corne_nice_nano": StrategyResult(
            strategy_name="west", success=False, error_message="Build failed"
        ),
    }

    result = BuildMatrixResult(
        total_targets=3,
        successful_targets=2,
        failed_targets=1,
        target_results=target_results,
    )

    assert result.total_targets == 3
    assert result.successful_targets == 2
    assert result.failed_targets == 1
    assert len(result.target_results) == 3
    assert abs(result.success_rate - 66.66666666666667) < 0.0000001
    assert result.overall_success is False


def test_build_matrix_result_all_success():
    """Test BuildMatrixResult with all targets successful."""
    target_results = {
        "corne_left": StrategyResult(strategy_name="west", success=True),
        "corne_right": StrategyResult(strategy_name="west", success=True),
    }

    result = BuildMatrixResult(
        total_targets=2,
        successful_targets=2,
        failed_targets=0,
        target_results=target_results,
    )

    assert result.success_rate == 100.0
    assert result.overall_success is True


def test_build_matrix_result_empty():
    """Test BuildMatrixResult with no targets."""
    result = BuildMatrixResult(total_targets=0, successful_targets=0, failed_targets=0)

    assert result.success_rate == 0.0
    assert result.overall_success is False


def test_compilation_result():
    """Test CompilationResult model."""
    # Create a BuildResult
    build_result = BuildResult(success=True)
    build_result.add_message("Compilation completed successfully")

    # Create output files
    output_files = FirmwareOutputFiles(output_dir=Path("/test/output"))
    output_files.main_uf2 = Path("/test/output/firmware.uf2")
    build_result.output_files = output_files

    # Create CompilationResult
    result = CompilationResult(
        build_result=build_result,
        strategy_used="west",
        workspace_path=Path("/test/workspace"),
        build_targets=["corne_left", "corne_right"],
        cache_used=True,
        build_time_seconds=120.5,
    )

    assert result.build_result == build_result
    assert result.strategy_used == "west"
    assert result.workspace_path == Path("/test/workspace")
    assert result.build_targets == ["corne_left", "corne_right"]
    assert result.cache_used is True
    assert result.build_time_seconds == 120.5

    # Test properties
    assert result.success is True
    assert result.output_files == output_files
    assert result.messages == ["Compilation completed successfully"]
    assert result.errors == []


def test_compilation_result_failure():
    """Test CompilationResult for failed compilation."""
    # Create a failed BuildResult
    build_result = BuildResult(success=False)
    build_result.add_error("Board configuration not found")
    build_result.add_error("Missing keymap file")

    result = CompilationResult(
        build_result=build_result,
        strategy_used="zmk_config",
        cache_used=False,
        build_time_seconds=5.2,
    )

    assert result.success is False
    assert result.output_files is None
    assert result.messages == []
    assert result.errors == ["Board configuration not found", "Missing keymap file"]


def test_compilation_result_validation():
    """Test CompilationResult model validation."""
    build_result = BuildResult(success=True)

    result_data = {
        "build_result": build_result,
        "strategy_used": "cmake",
        "workspace_path": "/validation/workspace",
        "build_targets": ["target1", "target2"],
        "cache_used": False,
        "build_time_seconds": 89.3,
    }

    result = CompilationResult.model_validate(result_data)

    assert result.build_result == build_result
    assert result.strategy_used == "cmake"
    assert result.workspace_path == Path("/validation/workspace")
    assert result.build_targets == ["target1", "target2"]
    assert result.cache_used is False
    assert result.build_time_seconds == 89.3
