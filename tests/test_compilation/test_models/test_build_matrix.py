"""Test build matrix models."""

from glovebox.compilation.models.build_matrix import (
    BuildMatrix,
    BuildTarget,
)


def test_build_target_creation():
    """Test BuildTarget dataclass creation."""
    target = BuildTarget(board="nice_nano_v2")
    assert target.board == "nice_nano_v2"
    assert target.shield is None
    assert target.cmake_args == []
    assert target.snippet is None
    # artifact_name is computed from board when not explicitly set
    assert target.artifact_name == "nice_nano_v2-zmk"


def test_build_target_with_shield():
    """Test BuildTarget with shield configuration."""
    target = BuildTarget(
        board="nice_nano_v2",
        shield="corne_left",
        cmake_args=["-DCONFIG_ZMK_SLEEP=y"],
        artifact_name="corne_left",
    )
    assert target.board == "nice_nano_v2"
    assert target.shield == "corne_left"
    assert target.cmake_args == ["-DCONFIG_ZMK_SLEEP=y"]
    assert target.artifact_name == "corne_left"


def test_build_matrix_creation():
    """Test BuildMatrix creation with targets."""
    target1 = BuildTarget(board="nice_nano_v2", shield="corne_left")
    target2 = BuildTarget(board="nice_nano_v2", shield="corne_right")

    matrix = BuildMatrix(
        include=[target1, target2],
        board=["nice_nano_v2"],
        shield=["corne_left", "corne_right"],
    )

    assert len(matrix.include if matrix.include else []) == 2
    assert matrix.board == ["nice_nano_v2"]
    assert matrix.shield == ["corne_left", "corne_right"]


def test_build_target_config_validation():
    """Test BuildTarget Pydantic model validation."""
    config = BuildTarget.model_validate(
        {
            "board": "nice_nano_v2",
            "shield": "corne_left",
            "cmake_args": ["-DCONFIG_ZMK_SLEEP=y"],
            "artifact_name": "corne_left",
        }
    )

    assert config.board == "nice_nano_v2"
    assert config.shield == "corne_left"
    assert config.cmake_args == ["-DCONFIG_ZMK_SLEEP=y"]
    assert config.artifact_name == "corne_left"


def test_build_yaml_config_empty():
    """Test BuildYamlConfig with empty defaults."""
    config = BuildMatrix()

    assert config.board == []
    assert config.shield == []
    assert config.include == []
