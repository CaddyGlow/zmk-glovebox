"""Test fixtures for configuration tests.

This module provides reusable fixtures for testing the configuration system.
These fixtures can be used across all test modules by importing pytest.
"""

import os
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
import yaml

from glovebox.adapters.config_file_adapter import ConfigFileAdapter
from glovebox.config.models import UserConfigData
from glovebox.config.user_config import UserConfig


@pytest.fixture
def temp_config_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for config files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_config_dict() -> dict[str, Any]:
    """Sample configuration dictionary for testing."""
    return {
        "profile": "test_keyboard/v1.0",
        "log_level": "DEBUG",
        "keyboard_paths": ["/path/to/keyboards", "~/custom/keyboards"],
        "firmware": {
            "flash": {
                "timeout": 120,
                "count": 5,
                "track_flashed": False,
                "skip_existing": True,
            }
        },
    }


@pytest.fixture
def sample_config_yaml(sample_config_dict: dict[str, Any]) -> str:
    """Sample configuration as YAML string."""
    return yaml.dump(sample_config_dict, default_flow_style=False)


@pytest.fixture
def config_file(temp_config_dir: Path, sample_config_yaml: str) -> Path:
    """Create a temporary config file with sample data."""
    config_path = temp_config_dir / "config.yml"
    config_path.write_text(sample_config_yaml, encoding="utf-8")
    return config_path


@pytest.fixture
def invalid_config_yaml() -> str:
    """Invalid configuration YAML for testing validation."""
    return """
profile: "invalid_format"  # Missing slash
log_level: "INVALID_LEVEL"
firmware:
  flash:
    timeout: -5  # Invalid negative value
    count: "not_a_number"
"""


@pytest.fixture
def invalid_config_file(temp_config_dir: Path, invalid_config_yaml: str) -> Path:
    """Create a temporary config file with invalid data."""
    config_path = temp_config_dir / "invalid_config.yml"
    config_path.write_text(invalid_config_yaml, encoding="utf-8")
    return config_path


@pytest.fixture
def minimal_config_dict() -> dict[str, Any]:
    """Minimal valid configuration dictionary."""
    return {
        "profile": "minimal/v1.0",
        "log_level": "INFO",
    }


@pytest.fixture
def minimal_config_file(
    temp_config_dir: Path, minimal_config_dict: dict[str, Any]
) -> Path:
    """Create a minimal config file."""
    config_path = temp_config_dir / "minimal.yml"
    config_yaml = yaml.dump(minimal_config_dict, default_flow_style=False)
    config_path.write_text(config_yaml, encoding="utf-8")
    return config_path


@pytest.fixture
def empty_config_file(temp_config_dir: Path) -> Path:
    """Create an empty config file."""
    config_path = temp_config_dir / "empty.yml"
    config_path.write_text("", encoding="utf-8")
    return config_path


@pytest.fixture
def mock_config_adapter() -> Mock:
    """Mock ConfigFileAdapter for testing."""
    adapter = Mock(spec=ConfigFileAdapter)
    # Mock base config loading with realistic defaults
    adapter.load_config.return_value = {
        "profile": "glove80/v25.05",
        "cache_strategy": "shared",
        "icon_mode": "emoji",
        "firmware": {
            "flash": {
                "timeout": 30,
                "verify": True,
                "auto_detect": True,
                "wait_for_device": True,
                "device_wait_timeout": 60,
            }
        },
        "cache_ttls": {
            "compilation_workspace": 3600,
            "compilation_build": 3600,
            "layout_diff": 1800,
        },
    }
    return adapter


@pytest.fixture
def user_config_data_factory():
    """Factory function to create UserConfigData instances with custom values."""

    def _create_config(**kwargs) -> UserConfigData:
        from pathlib import Path

        # Handle special conversion for keyboard_paths
        if (
            "keyboard_paths" in kwargs
            and kwargs["keyboard_paths"]
            and isinstance(kwargs["keyboard_paths"], list)
            and kwargs["keyboard_paths"]
            and isinstance(kwargs["keyboard_paths"][0], str)
        ):
            kwargs["keyboard_paths"] = [Path(p) for p in kwargs["keyboard_paths"]]

        # Set defaults for missing fields
        config_data = {
            "profile": kwargs.get("profile", "glove80/v25.05"),
            "log_level": kwargs.get("log_level", "INFO"),
            "keyboard_paths": kwargs.get("keyboard_paths", []),
        }

        # Add any other kwargs that aren't the main fields
        for key, value in kwargs.items():
            if key not in config_data:
                config_data[key] = value

        return UserConfigData(**config_data)

    return _create_config


@pytest.fixture
def user_config_factory(mock_config_adapter: Mock):
    """Factory function to create UserConfig instances for testing."""

    def _create_user_config(
        cli_config_path: Path | None = None,
        config_data: dict[str, Any] | None = None,
        found_path: Path | None = None,
    ) -> UserConfig:
        # Configure mock adapter behavior
        if config_data is not None and found_path is not None:
            mock_config_adapter.search_config_files.return_value = (
                config_data,
                found_path,
            )
        else:
            # No config file found
            mock_config_adapter.search_config_files.return_value = ({}, None)

        return UserConfig(
            cli_config_path=cli_config_path, config_adapter=mock_config_adapter
        )

    return _create_user_config


@pytest.fixture
def env_vars() -> dict[str, str]:
    """Sample environment variables for testing."""
    return {
        "GLOVEBOX_PROFILE": "env_keyboard/v2.0",
        "GLOVEBOX_LOG_LEVEL": "ERROR",
        "GLOVEBOX_FIRMWARE__FLASH__TIMEOUT": "180",
        "GLOVEBOX_FIRMWARE__FLASH__COUNT": "10",
        "GLOVEBOX_FIRMWARE__FLASH__TRACK_FLASHED": "false",
        "GLOVEBOX_FIRMWARE__FLASH__SKIP_EXISTING": "true",
    }


@pytest.fixture
def mock_environment(env_vars: dict[str, str]) -> Generator[None, None, None]:
    """Mock environment variables for testing."""
    original_env = dict(os.environ)

    # Clear any existing GLOVEBOX_ env vars
    for key in list(os.environ.keys()):
        if key.startswith("GLOVEBOX_"):
            del os.environ[key]

    # Set test environment variables
    os.environ.update(env_vars)

    try:
        yield
    finally:
        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)


@pytest.fixture
def clean_environment() -> Generator[None, None, None]:
    """Clean environment with no GLOVEBOX_ variables."""
    original_env = dict(os.environ)

    # Remove any existing GLOVEBOX_ env vars
    for key in list(os.environ.keys()):
        if key.startswith("GLOVEBOX_"):
            del os.environ[key]

    try:
        yield
    finally:
        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)


@pytest.fixture
def profile_test_cases() -> list[tuple[str, bool, str]]:
    """Test cases for profile validation: (profile, is_valid, error_description)."""
    return [
        # Valid profiles
        ("glove80/v25.05", True, ""),
        ("custom_keyboard/v1.0", True, ""),
        ("test-board/dev-build", True, ""),
        ("long_keyboard_name/very.long.firmware.version", True, ""),
        # Valid keyboard-only profiles (new format)
        ("glove80", True, ""),
        ("custom_keyboard", True, ""),
        ("test-board", True, ""),
        # Invalid profiles
        ("", False, "empty profile"),
        ("trailing/slash/", False, "trailing slash"),
        ("/leading/slash", False, "leading slash"),
        ("double//slash", False, "double slash"),
        ("keyboard/", False, "empty firmware"),
        ("/firmware", False, "empty keyboard"),
        ("   /firmware", False, "whitespace keyboard"),
        ("keyboard/   ", False, "whitespace firmware"),
    ]


@pytest.fixture
def log_level_test_cases() -> list[tuple[str, bool, str]]:
    """Test cases for log level validation: (level, is_valid, expected_normalized)."""
    return [
        # Valid levels (should be normalized to uppercase)
        ("DEBUG", True, "DEBUG"),
        ("debug", True, "DEBUG"),
        ("Info", True, "INFO"),
        ("WARNING", True, "WARNING"),
        ("error", True, "ERROR"),
        ("Critical", True, "CRITICAL"),
        # Invalid levels
        ("INVALID", False, ""),
        ("TRACE", False, ""),
        ("VERBOSE", False, ""),
        ("", False, ""),
        ("123", False, ""),
    ]


# Export fixtures that should be available to other test modules
__all__ = [
    "temp_config_dir",
    "sample_config_dict",
    "sample_config_yaml",
    "config_file",
    "invalid_config_file",
    "minimal_config_file",
    "empty_config_file",
    "mock_config_adapter",
    "user_config_data_factory",
    "user_config_factory",
    "env_vars",
    "mock_environment",
    "clean_environment",
    "profile_test_cases",
    "log_level_test_cases",
]
