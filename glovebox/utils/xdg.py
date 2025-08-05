"""XDG Base Directory specification helpers."""

import os
from pathlib import Path


def get_xdg_data_dir() -> Path:
    """Get XDG data directory for Glovebox.

    Returns:
        Path to data directory: $XDG_DATA_HOME/glovebox or ~/.local/share/glovebox
    """
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        return Path(xdg_data) / "glovebox"
    return Path.home() / ".local" / "share" / "glovebox"


def get_xdg_config_dir() -> Path:
    """Get XDG config directory for Glovebox.

    Returns:
        Path to config directory: $XDG_CONFIG_HOME/glovebox or ~/.config/glovebox
    """
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config) / "glovebox"
    return Path.home() / ".config" / "glovebox"


def get_xdg_cache_dir() -> Path:
    """Get XDG cache directory for Glovebox.

    Returns:
        Path to cache directory: $XDG_CACHE_HOME/glovebox or ~/.cache/glovebox
    """
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        return Path(xdg_cache) / "glovebox"
    return Path.home() / ".cache" / "glovebox"


def get_version_check_state_file() -> Path:
    """Get the version check state file path.

    Returns:
        Path to version check state file in XDG data directory
    """
    return get_xdg_data_dir() / "version_check_state.json"


def ensure_xdg_directories() -> None:
    """Ensure all XDG directories exist."""
    for dir_func in [get_xdg_data_dir, get_xdg_config_dir, get_xdg_cache_dir]:
        directory = dir_func()
        directory.mkdir(parents=True, exist_ok=True)
