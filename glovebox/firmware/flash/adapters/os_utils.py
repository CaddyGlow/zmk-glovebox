"""Shared utilities for OS-specific flash operations."""

import subprocess
from pathlib import Path


def is_wsl2() -> bool:
    """Detect if running in WSL2 environment."""
    try:
        with Path("/proc/version").open() as f:
            version = f.read().lower()
        return "microsoft" in version
    except (OSError, FileNotFoundError):
        return False


def windows_to_wsl_path(windows_path: str) -> str:
    """Convert Windows path to WSL path using wslpath.

    Args:
        windows_path: Windows path (e.g., 'E:\\')

    Returns:
        WSL path (e.g., '/mnt/e/')

    Raises:
        OSError: If wslpath command fails
    """
    try:
        result = subprocess.run(
            ["wslpath", "-u", windows_path],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        # Fallback: try to convert manually for simple drive letters
        if len(windows_path) >= 2 and windows_path[1] == ":":
            drive_letter = windows_path[0].lower()
            fallback_path = f"/mnt/{drive_letter}/"
            return fallback_path
        raise OSError(f"Failed to convert Windows path {windows_path}: {e}") from e


def wsl_to_windows_path(wsl_path: str) -> str:
    """Convert WSL path to Windows path using wslpath.

    Args:
        wsl_path: WSL path (e.g., '/mnt/e/')

    Returns:
        Windows path (e.g., 'E:\\')

    Raises:
        OSError: If wslpath command fails
    """
    try:
        result = subprocess.run(
            ["wslpath", "-w", wsl_path],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        raise OSError(f"Failed to convert WSL path {wsl_path}: {e}") from e
