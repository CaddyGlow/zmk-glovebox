"""Pure helper functions for ZMK compilation operations."""

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from glovebox.compilation.models.build_matrix import BuildMatrix
    from glovebox.compilation.models.compilation_params import (
        ZmkCompilationParams,
        ZmkWorkspaceParams,
    )


def setup_zmk_workspace_paths(params: "ZmkCompilationParams") -> None:
    """Setup temporary directories and DockerPath configuration.

    Creates temporary directories for workspace, build, and config paths
    and updates the DockerPath objects in the compilation configuration.

    Args:
        params: ZMK compilation parameters containing configuration
    """
    config = params.compilation_config

    if not config.zmk_config_repo:
        raise ValueError("ZMK config repository configuration is missing")

    # Create temp directories and update DockerPath objects
    temp_workspace = Path(tempfile.mkdtemp(prefix="zmk_config"))
    config.zmk_config_repo.workspace_path.host_path = temp_workspace

    temp_build = Path(tempfile.mkdtemp(prefix="zmk_build"))
    config.zmk_config_repo.build_root.host_path = temp_build
    config.zmk_config_repo.build_root.container_path = "/build"

    temp_config = Path(tempfile.mkdtemp(prefix="zmk_config_dir"))
    config.zmk_config_repo.config_path.host_path = temp_config
    config.zmk_config_repo.config_path.container_path = "/config"


def build_zmk_init_commands(workspace_params: "ZmkWorkspaceParams") -> list[str]:
    """Build west initialization commands.

    Creates the sequence of west commands needed to initialize the ZMK
    workspace and prepare for compilation.

    Args:
        workspace_params: Workspace parameters containing paths and configuration

    Returns:
        list[str]: West initialization commands
    """
    config = workspace_params.zmk_config
    container_workspace = config.workspace_path.container_path
    config_path = config.config_path_absolute
    build_root = config.build_root.container_path

    return [
        f"cd {container_workspace}",
        f"west init -l {config_path} {build_root}",
        "west update",
        "west zephyr-export",
    ]


def build_zmk_compilation_commands(
    build_matrix: "BuildMatrix", workspace_params: "ZmkWorkspaceParams"
) -> list[str]:
    """Generate west build commands from build matrix.

    Creates build commands following GitHub Actions workflow pattern
    with proper build directories and CMake arguments.

    Args:
        build_matrix: Resolved build matrix from build.yaml
        workspace_params: Workspace parameters containing configuration

    Returns:
        list[str]: West build commands for each target
    """
    commands = []
    config = workspace_params.zmk_config

    for target in build_matrix.targets:
        base_build_dir = config.build_root_absolute
        build_dir = Path(base_build_dir) / f"{target.artifact_name or target.board}"

        if target.shield:
            build_dir = Path(base_build_dir) / f"{target.shield}-{target.board}"

        west_cmd = f"west build -s zmk/app -b {target.board} -d {build_dir}"

        # Add CMake arguments
        cmake_args = [f"-DZMK_CONFIG={config.config_path_absolute}"]
        if target.shield:
            cmake_args.append(f"-DSHIELD={target.shield}")
        if target.cmake_args:
            cmake_args.extend(target.cmake_args)
        if target.snippet:
            cmake_args.append(f"-DZMK_EXTRA_MODULES={target.snippet}")

        if cmake_args:
            west_cmd += f" -- {' '.join(cmake_args)}"

        commands.append(west_cmd)

    return commands


def build_zmk_fallback_commands(
    workspace_params: "ZmkWorkspaceParams", board_targets: list[str]
) -> list[str]:
    """Generate fallback build commands when build.yaml is not available.

    Creates basic west build commands using configuration to generate
    build commands when no build matrix is available.

    Args:
        workspace_params: Workspace parameters containing configuration
        board_targets: List of board targets from compilation config

    Returns:
        list[str]: Fallback west build commands
    """
    commands = []
    config = workspace_params.zmk_config

    base_build_dir = config.build_root.container_path
    cmake_args = [f"-DZMK_CONFIG={config.config_path_absolute}"]

    if len(board_targets) > 1:
        # Multiple board targets
        for board_target in board_targets:
            build_dir = f"{base_build_dir}_{board_target}"
            target_cmd = f"west build -s zmk/app -b {board_target} -d {build_dir}"
            target_cmd += f" -- {' '.join(cmake_args)}"
            commands.append(target_cmd)
    else:
        # Single board target
        board_name = board_targets[0] if board_targets else "nice_nano_v2"
        west_cmd = f"west build -s zmk/app -b {board_name} -d {base_build_dir}"
        west_cmd += f" -- {' '.join(cmake_args)}"
        commands.append(west_cmd)

    return commands
