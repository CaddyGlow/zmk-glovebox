"""Tests for firmware auto-profile detection functionality."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.cli.helpers.auto_profile import (
    extract_keyboard_from_json,
    get_auto_profile_from_json,
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
