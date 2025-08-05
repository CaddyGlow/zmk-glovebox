"""Utilities for detecting how Glovebox is installed and running."""

import os
import sys
from enum import Enum
from pathlib import Path


class InstallMethod(Enum):
    """Enumeration of possible installation methods."""

    UVX = "uvx"
    UV = "uv"
    PIPX = "pipx"
    PIP = "pip"
    DEVELOPMENT = "development"
    UNKNOWN = "unknown"


def detect_installation_method() -> InstallMethod:
    """Detect how Glovebox is currently running.

    Returns:
        InstallMethod indicating how the tool is installed/running
    """
    # Check for uvx temporary environment
    if os.environ.get("UVX"):
        return InstallMethod.UVX

    # Check if running from a uv virtual environment or via uv run
    if (
        os.environ.get("UV_PROJECT_ROOT")
        or os.environ.get("UV_PYTHON")
        or os.environ.get("UV_INTERNAL__PARENT_INTERPRETER")
    ):
        return InstallMethod.UV

    # Check for pipx
    try:
        # pipx typically installs in ~/.local/pipx/venvs/
        exe_path = Path(sys.executable).resolve()
        if "pipx" in str(exe_path):
            return InstallMethod.PIPX
    except Exception:
        pass

    # Check if running in development mode (editable install)
    try:
        import glovebox

        package_path = Path(glovebox.__file__).parent
        # Check for .git directory in parent paths
        current = package_path
        for _ in range(3):  # Check up to 3 levels up
            if (current / ".git").exists():
                return InstallMethod.DEVELOPMENT
            current = current.parent
    except Exception:
        pass

    # Check if in a virtual environment (likely pip)
    if hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    ):
        return InstallMethod.PIP

    # Default to unknown
    return InstallMethod.UNKNOWN


def get_update_command(install_method: InstallMethod | None = None) -> str:
    """Get the appropriate update command based on installation method.

    Args:
        install_method: Optional installation method to use. If None, will detect.

    Returns:
        The appropriate update command for the installation method
    """
    if install_method is None:
        install_method = detect_installation_method()

    commands = {
        InstallMethod.UVX: "uvx install -U zmk-glovebox@latest",
        InstallMethod.UV: "uv pip install -U zmk-glovebox",
        InstallMethod.PIPX: "pipx upgrade zmk-glovebox",
        InstallMethod.PIP: "pip install -U zmk-glovebox",
        InstallMethod.DEVELOPMENT: "git pull && uv sync",
        InstallMethod.UNKNOWN: "pip install -U zmk-glovebox",
    }

    return commands.get(install_method, commands[InstallMethod.UNKNOWN])


def get_install_method_display_name(install_method: InstallMethod | None = None) -> str:
    """Get a user-friendly display name for the installation method.

    Args:
        install_method: Optional installation method to use. If None, will detect.

    Returns:
        User-friendly name for the installation method
    """
    if install_method is None:
        install_method = detect_installation_method()

    names = {
        InstallMethod.UVX: "uvx",
        InstallMethod.UV: "uv",
        InstallMethod.PIPX: "pipx",
        InstallMethod.PIP: "pip",
        InstallMethod.DEVELOPMENT: "development",
        InstallMethod.UNKNOWN: "standard",
    }

    return names.get(install_method, "standard")
