"""Tests for firmware auto-profile detection functionality."""

import json
import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.cli.helpers.auto_profile import (
    extract_keyboard_from_json,
    get_auto_profile_from_json,
    resolve_json_file_path,
    resolve_profile_with_auto_detection,
)


def test_extract_keyboard_from_json_success(tmp_path):
    """Test successful keyboard extraction from JSON."""
    test_json = {"keyboard": "glove80", "title": "Test Layout", "layers": []}
    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(test_json))

    result = extract_keyboard_from_json(json_file)

    assert result == "glove80"


def test_extract_keyboard_from_json_with_whitespace(tmp_path):
    """Test keyboard extraction with whitespace trimming."""
    test_json = {"keyboard": "  corne  ", "title": "Test Layout", "layers": []}
    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(test_json))

    result = extract_keyboard_from_json(json_file)

    assert result == "corne"


def test_extract_keyboard_from_json_missing_field(tmp_path):
    """Test keyboard extraction when keyboard field is missing."""
    test_json = {"title": "Test Layout", "layers": []}
    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(test_json))

    result = extract_keyboard_from_json(json_file)

    assert result is None


def test_extract_keyboard_from_json_empty_field(tmp_path):
    """Test keyboard extraction when keyboard field is empty."""
    test_json = {"keyboard": "", "title": "Test Layout", "layers": []}
    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(test_json))

    result = extract_keyboard_from_json(json_file)

    assert result is None


def test_extract_keyboard_from_json_invalid_type(tmp_path):
    """Test keyboard extraction when keyboard field is not a string."""
    test_json = {"keyboard": 123, "title": "Test Layout", "layers": []}
    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(test_json))

    result = extract_keyboard_from_json(json_file)

    assert result is None


def test_extract_keyboard_from_json_invalid_json(tmp_path):
    """Test keyboard extraction with invalid JSON."""
    json_file = tmp_path / "invalid.json"
    json_file.write_text("{ invalid json")

    result = extract_keyboard_from_json(json_file)

    assert result is None


def test_extract_keyboard_from_json_nonexistent_file(tmp_path):
    """Test keyboard extraction with nonexistent file."""
    json_file = tmp_path / "nonexistent.json"

    result = extract_keyboard_from_json(json_file)

    assert result is None


def test_get_auto_profile_from_json_keyboard_only(tmp_path):
    """Test auto-profile detection returning keyboard-only profile."""
    test_json = {"keyboard": "corne", "title": "Test Layout", "layers": []}
    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(test_json))

    with patch(
        "glovebox.config.keyboard_profile.create_keyboard_profile"
    ) as mock_create_profile:
        # Mock successful keyboard profile creation
        mock_profile = Mock()
        mock_create_profile.return_value = mock_profile

        result = get_auto_profile_from_json(json_file, user_config=None)

        assert result == "corne"
        mock_create_profile.assert_called_once_with("corne", None, None)


def test_get_auto_profile_from_json_with_user_config_firmware(tmp_path):
    """Test auto-profile detection with user config default firmware."""
    test_json = {"keyboard": "glove80", "title": "Test Layout", "layers": []}
    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(test_json))

    # Mock user config with matching keyboard in default profile
    mock_user_config = Mock()
    mock_user_config._config.profile = "glove80/v25.05"

    with patch(
        "glovebox.config.keyboard_profile.create_keyboard_profile"
    ) as mock_create_profile:
        # Mock successful keyboard profile creation
        mock_profile = Mock()
        mock_create_profile.return_value = mock_profile

        result = get_auto_profile_from_json(json_file, user_config=mock_user_config)

        assert result == "glove80/v25.05"
        mock_create_profile.assert_called_once_with("glove80", None, mock_user_config)


def test_get_auto_profile_from_json_with_user_config_different_keyboard(tmp_path):
    """Test auto-profile detection with user config for different keyboard."""
    test_json = {"keyboard": "corne", "title": "Test Layout", "layers": []}
    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(test_json))

    # Mock user config with different keyboard in default profile
    mock_user_config = Mock()
    mock_user_config._config.profile = "glove80/v25.05"

    with patch(
        "glovebox.config.keyboard_profile.create_keyboard_profile"
    ) as mock_create_profile:
        # Mock successful keyboard profile creation
        mock_profile = Mock()
        mock_create_profile.return_value = mock_profile

        result = get_auto_profile_from_json(json_file, user_config=mock_user_config)

        # Should return keyboard-only since user config keyboard doesn't match
        assert result == "corne"
        mock_create_profile.assert_called_once_with("corne", None, mock_user_config)


def test_get_auto_profile_from_json_no_keyboard_field(tmp_path):
    """Test auto-profile detection when JSON has no keyboard field."""
    test_json = {"title": "Test Layout", "layers": []}
    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(test_json))

    result = get_auto_profile_from_json(json_file, user_config=None)

    assert result is None


def test_get_auto_profile_from_json_invalid_keyboard(tmp_path):
    """Test auto-profile detection when keyboard doesn't exist in config."""
    test_json = {
        "keyboard": "nonexistent-keyboard",
        "title": "Test Layout",
        "layers": [],
    }
    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(test_json))

    with patch(
        "glovebox.config.keyboard_profile.create_keyboard_profile"
    ) as mock_create_profile:
        # Mock keyboard profile creation failure
        mock_create_profile.side_effect = Exception("Keyboard configuration not found")

        result = get_auto_profile_from_json(json_file, user_config=None)

        assert result is None
        mock_create_profile.assert_called_once_with("nonexistent-keyboard", None, None)


def test_get_auto_profile_from_json_with_user_config_no_profile_attribute(tmp_path):
    """Test auto-profile detection when user config has no profile attribute."""
    test_json = {"keyboard": "corne", "title": "Test Layout", "layers": []}
    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(test_json))

    # Mock user config that has _config but profile access raises AttributeError
    mock_user_config = Mock()
    mock_user_config._config = Mock()

    # Configure the profile property to raise AttributeError
    with (
        patch.object(
            mock_user_config._config,
            "profile",
            side_effect=AttributeError("profile not found"),
        ),
        patch(
            "glovebox.config.keyboard_profile.create_keyboard_profile"
        ) as mock_create_profile,
    ):
        # Mock successful keyboard profile creation
        mock_profile = Mock()
        mock_create_profile.return_value = mock_profile

        result = get_auto_profile_from_json(json_file, user_config=mock_user_config)

        # Should fallback to keyboard-only
        assert result == "corne"
        mock_create_profile.assert_called_once_with("corne", None, mock_user_config)


def test_get_auto_profile_from_json_with_user_config_keyboard_only_profile(tmp_path):
    """Test auto-profile detection when user config has keyboard-only profile."""
    test_json = {"keyboard": "corne", "title": "Test Layout", "layers": []}
    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(test_json))

    # Mock user config with keyboard-only profile (no slash)
    mock_user_config = Mock()
    mock_user_config._config.profile = "glove80"  # No firmware version

    with patch(
        "glovebox.config.keyboard_profile.create_keyboard_profile"
    ) as mock_create_profile:
        # Mock successful keyboard profile creation
        mock_profile = Mock()
        mock_create_profile.return_value = mock_profile

        result = get_auto_profile_from_json(json_file, user_config=mock_user_config)

        # Should return keyboard-only since user config doesn't have firmware
        assert result == "corne"
        mock_create_profile.assert_called_once_with("corne", None, mock_user_config)


def test_get_auto_profile_from_json_default_firmware_selection_precedence(tmp_path):
    """Test that user config keyboard match takes precedence for firmware selection."""
    test_json = {"keyboard": "glove80", "title": "Test Layout", "layers": []}
    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(test_json))

    # Mock user config with full profile matching the JSON keyboard
    mock_user_config = Mock()
    mock_user_config._config.profile = "glove80/v26.01"

    with patch(
        "glovebox.config.keyboard_profile.create_keyboard_profile"
    ) as mock_create_profile:
        # Mock successful keyboard profile creation
        mock_profile = Mock()
        mock_create_profile.return_value = mock_profile

        result = get_auto_profile_from_json(json_file, user_config=mock_user_config)

        # Should return the full user config profile since keyboard matches
        assert result == "glove80/v26.01"
        mock_create_profile.assert_called_once_with("glove80", None, mock_user_config)


def test_get_auto_profile_from_json_user_config_fallback_to_keyboard_only(tmp_path):
    """Test fallback to keyboard-only when user config keyboard doesn't match."""
    test_json = {"keyboard": "corne", "title": "Test Layout", "layers": []}
    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(test_json))

    # Mock user config with different keyboard profile
    mock_user_config = Mock()
    mock_user_config._config.profile = "glove80/v25.05"  # Different keyboard

    with patch(
        "glovebox.config.keyboard_profile.create_keyboard_profile"
    ) as mock_create_profile:
        # Mock successful keyboard profile creation
        mock_profile = Mock()
        mock_create_profile.return_value = mock_profile

        result = get_auto_profile_from_json(json_file, user_config=mock_user_config)

        # Should return keyboard-only since user config keyboard doesn't match JSON
        assert result == "corne"
        mock_create_profile.assert_called_once_with("corne", None, mock_user_config)


# Tests for resolve_json_file_path function
def test_resolve_json_file_path_with_cli_argument(tmp_path):
    """Test resolve_json_file_path with CLI argument."""
    test_file = tmp_path / "test.json"
    test_file.write_text('{"test": "data"}')

    result = resolve_json_file_path(str(test_file))

    assert result == test_file


def test_resolve_json_file_path_with_environment_variable(tmp_path, monkeypatch):
    """Test resolve_json_file_path with environment variable."""
    test_file = tmp_path / "test.json"
    test_file.write_text('{"test": "data"}')

    # Set environment variable
    monkeypatch.setenv("GLOVEBOX_JSON_FILE", str(test_file))

    result = resolve_json_file_path(None)

    assert result == test_file


def test_resolve_json_file_path_cli_overrides_env_var(tmp_path, monkeypatch):
    """Test that CLI argument takes precedence over environment variable."""
    cli_file = tmp_path / "cli.json"
    env_file = tmp_path / "env.json"
    cli_file.write_text('{"source": "cli"}')
    env_file.write_text('{"source": "env"}')

    # Set environment variable
    monkeypatch.setenv("GLOVEBOX_JSON_FILE", str(env_file))

    result = resolve_json_file_path(str(cli_file))

    assert result == cli_file  # CLI argument should take precedence


def test_resolve_json_file_path_custom_env_var(tmp_path, monkeypatch):
    """Test resolve_json_file_path with custom environment variable name."""
    test_file = tmp_path / "test.json"
    test_file.write_text('{"test": "data"}')

    # Set custom environment variable
    monkeypatch.setenv("CUSTOM_JSON_VAR", str(test_file))

    result = resolve_json_file_path(None, env_var="CUSTOM_JSON_VAR")

    assert result == test_file


def test_resolve_json_file_path_returns_none_when_no_source(tmp_path):
    """Test resolve_json_file_path returns None when no source provided."""
    # Ensure environment variable is not set
    if "GLOVEBOX_JSON_FILE" in os.environ:
        del os.environ["GLOVEBOX_JSON_FILE"]

    result = resolve_json_file_path(None)

    assert result is None


def test_resolve_json_file_path_file_not_found(tmp_path):
    """Test resolve_json_file_path raises FileNotFoundError for non-existent file."""
    nonexistent_file = tmp_path / "nonexistent.json"

    with pytest.raises(FileNotFoundError, match="JSON file not found"):
        resolve_json_file_path(str(nonexistent_file))


def test_resolve_json_file_path_not_a_file(tmp_path):
    """Test resolve_json_file_path raises ValueError when path is not a file."""
    directory = tmp_path / "not_a_file"
    directory.mkdir()

    with pytest.raises(ValueError, match="Path is not a file"):
        resolve_json_file_path(str(directory))


# Tests for resolve_profile_with_auto_detection function
def test_resolve_profile_explicit_cli_profile_takes_precedence(tmp_path):
    """Test that explicit CLI profile takes highest precedence."""
    test_json = {"keyboard": "corne", "title": "Test Layout", "layers": []}
    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(test_json))

    result = resolve_profile_with_auto_detection(
        profile="glove80/v25.05",  # Explicit profile
        json_file=json_file,
        no_auto=False,
        user_config=None,
    )

    assert result == "glove80/v25.05"


def test_resolve_profile_auto_detection_from_json(tmp_path):
    """Test auto-detection from JSON when no explicit profile."""
    test_json = {"keyboard": "corne", "title": "Test Layout", "layers": []}
    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(test_json))

    with patch(
        "glovebox.cli.helpers.auto_profile.get_auto_profile_from_json"
    ) as mock_get_auto:
        mock_get_auto.return_value = "corne"

        result = resolve_profile_with_auto_detection(
            profile=None,
            json_file=json_file,
            no_auto=False,
            user_config=None,
        )

        assert result == "corne"
        mock_get_auto.assert_called_once_with(json_file, None)


def test_resolve_profile_no_auto_flag_disables_detection(tmp_path):
    """Test that no_auto=True disables auto-detection."""
    test_json = {"keyboard": "corne", "title": "Test Layout", "layers": []}
    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(test_json))

    with patch(
        "glovebox.cli.helpers.auto_profile.get_auto_profile_from_json"
    ) as mock_get_auto:
        result = resolve_profile_with_auto_detection(
            profile=None,
            json_file=json_file,
            no_auto=True,  # Auto-detection disabled
            user_config=None,
        )

        assert result is None  # Should fall back to UserConfig defaults
        mock_get_auto.assert_not_called()


def test_resolve_profile_non_json_file_skips_auto_detection(tmp_path):
    """Test that non-JSON files skip auto-detection."""
    test_file = tmp_path / "test.yaml"
    test_file.write_text("keyboard: corne")

    with patch(
        "glovebox.cli.helpers.auto_profile.get_auto_profile_from_json"
    ) as mock_get_auto:
        result = resolve_profile_with_auto_detection(
            profile=None,
            json_file=test_file,
            no_auto=False,
            user_config=None,
        )

        assert result is None  # Should fall back to UserConfig defaults
        mock_get_auto.assert_not_called()


def test_resolve_profile_auto_detection_failure_fallback(tmp_path):
    """Test fallback to UserConfig when auto-detection fails."""
    test_json = {"title": "Test Layout", "layers": []}  # No keyboard field
    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps(test_json))

    with patch(
        "glovebox.cli.helpers.auto_profile.get_auto_profile_from_json"
    ) as mock_get_auto:
        mock_get_auto.return_value = None  # Auto-detection fails

        result = resolve_profile_with_auto_detection(
            profile=None,
            json_file=json_file,
            no_auto=False,
            user_config=None,
        )

        assert result is None  # Should fall back to UserConfig defaults
        mock_get_auto.assert_called_once_with(json_file, None)


def test_resolve_profile_no_json_file_fallback():
    """Test fallback to UserConfig when no JSON file provided."""
    with patch(
        "glovebox.cli.helpers.auto_profile.get_auto_profile_from_json"
    ) as mock_get_auto:
        result = resolve_profile_with_auto_detection(
            profile=None,
            json_file=None,
            no_auto=False,
            user_config=None,
        )

        assert result is None  # Should fall back to UserConfig defaults
        mock_get_auto.assert_not_called()
