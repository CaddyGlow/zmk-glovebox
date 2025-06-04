"""Tests for the fixtures provided in conftest.py."""

from unittest.mock import patch

import pytest


def test_mock_keyboard_config(mock_keyboard_config):
    """Test that the mock_keyboard_config fixture is properly structured."""
    assert mock_keyboard_config["keyboard"] == "test_keyboard"
    assert "description" in mock_keyboard_config
    assert "flash" in mock_keyboard_config
    assert "build" in mock_keyboard_config
    assert "firmwares" in mock_keyboard_config
    assert "default" in mock_keyboard_config["firmwares"]
    assert "bluetooth" in mock_keyboard_config["firmwares"]


def test_mock_firmware_config(mock_firmware_config):
    """Test that the mock_firmware_config fixture is properly structured."""
    assert "description" in mock_firmware_config
    assert "version" in mock_firmware_config
    assert "branch" in mock_firmware_config


def test_mock_load_keyboard_config(mock_load_keyboard_config, mock_keyboard_config):
    """Test that the mock_load_keyboard_config fixture properly mocks the function."""
    # Call the mocked function
    result = mock_load_keyboard_config("test_keyboard")

    # Verify the result
    assert result == mock_keyboard_config
    mock_load_keyboard_config.assert_called_once_with("test_keyboard")

    # Verify behavior with different input
    mock_load_keyboard_config("another_keyboard")
    mock_load_keyboard_config.assert_called_with("another_keyboard")
    assert mock_load_keyboard_config.call_count == 2


def test_mock_get_available_keyboards(mock_get_available_keyboards):
    """Test that the mock_get_available_keyboards fixture properly mocks the function."""
    # Call the mocked function
    result = mock_get_available_keyboards()

    # Verify the result
    assert "test_keyboard" in result
    assert "glove80" in result
    assert "corne" in result
    mock_get_available_keyboards.assert_called_once()


def test_mock_get_firmware_config(mock_get_firmware_config, mock_firmware_config):
    """Test that the mock_get_firmware_config fixture properly mocks the function."""
    # Call the mocked function
    result = mock_get_firmware_config("test_keyboard", "default")

    # Verify the result
    assert result == mock_firmware_config
    mock_get_firmware_config.assert_called_once_with("test_keyboard", "default")


def test_mock_get_available_firmwares(mock_get_available_firmwares):
    """Test that the mock_get_available_firmwares fixture properly mocks the function."""
    # Call the mocked function
    result = mock_get_available_firmwares("test_keyboard")

    # Verify the result
    assert "default" in result
    assert "bluetooth" in result
    assert "v25.05" in result
    mock_get_available_firmwares.assert_called_once_with("test_keyboard")


def test_mock_keyboard_config_service(
    mock_keyboard_config_service, mock_keyboard_config, mock_firmware_config
):
    """Test that the mock_keyboard_config_service fixture properly mocks the service."""
    # Test load_keyboard_config
    result = mock_keyboard_config_service.load_keyboard_config("test_keyboard")
    assert result == mock_keyboard_config
    mock_keyboard_config_service.load_keyboard_config.assert_called_once_with(
        "test_keyboard"
    )

    # Test get_available_keyboards
    result = mock_keyboard_config_service.get_available_keyboards()
    assert "test_keyboard" in result
    assert "glove80" in result
    assert "corne" in result
    mock_keyboard_config_service.get_available_keyboards.assert_called_once()

    # Test get_firmware_config
    result = mock_keyboard_config_service.get_firmware_config(
        "test_keyboard", "default"
    )
    assert result == mock_firmware_config
    mock_keyboard_config_service.get_firmware_config.assert_called_once_with(
        "test_keyboard", "default"
    )

    # Test get_available_firmwares
    result = mock_keyboard_config_service.get_available_firmwares("test_keyboard")
    assert "default" in result
    assert "bluetooth" in result
    assert "v25.05" in result
    mock_keyboard_config_service.get_available_firmwares.assert_called_once_with(
        "test_keyboard"
    )
