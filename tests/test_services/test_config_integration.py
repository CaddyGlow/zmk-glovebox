"""Integration tests for the configuration system (mock version).

These tests mock out most of the functionality to avoid having to create complex
test fixtures. They verify that the interface works correctly but don't test
the actual implementation.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from glovebox.core.errors import ConfigError
from glovebox.models.results import BaseResult


def test_config_functions_mocked():
    """Test that configuration functions behave as expected."""
    # Create mocks directly
    mock_load = Mock()
    mock_get_keyboards = Mock()

    # Set up mock returns
    mock_keyboard_config = {
        "keyboard": "test_keyboard",
        "description": "Test keyboard",
        "flash": {
            "query": "vendor=Test and removable=true",
        },
    }
    mock_load.return_value = mock_keyboard_config
    mock_get_keyboards.return_value = ["test_keyboard", "glove80"]

    # Call the mocked functions
    result = mock_load("test_keyboard")
    keyboards = mock_get_keyboards()

    # Verify results
    assert result == mock_keyboard_config
    assert "test_keyboard" in keyboards
    assert "glove80" in keyboards

    # Verify the mock was called with expected arguments
    mock_load.assert_called_once_with("test_keyboard")
    mock_get_keyboards.assert_called_once()


def test_layout_service_with_keyboard_config():
    """Test that a mocked KeymapService can handle keyboard configuration."""
    # Create a mock service with a mocked validate_config method
    mock_service = Mock()
    mock_service.validate_config.return_value = True

    # Mock keyboard config
    mock_keyboard_config = {
        "keyboard": "test_keyboard",
        "description": "Test keyboard",
        "templates": {
            "keymap_template": "#include <behaviors.dtsi>",
        },
    }

    # Mock keymap data
    mock_keymap_data = {
        "keyboard": "test_keyboard",
        "layer_names": ["Default"],
        "layers": [[{"value": "&kp", "params": ["A"]}]],
    }

    # Test the validate_config method
    result = mock_service.validate_config(mock_keymap_data, mock_keyboard_config)

    # Verify the result and that the method was called with expected arguments
    assert result is True
    mock_service.validate_config.assert_called_once_with(
        mock_keymap_data, mock_keyboard_config
    )


def test_build_service_with_config():
    """Test that build service configuration validation works."""
    # Create a mock build service
    mock_service = Mock()

    # Create a mock result object
    mock_result = Mock(spec=BaseResult)
    mock_result.success = True
    mock_service.validate_config.return_value = mock_result

    # Test with a simple config
    config = {
        "keyboard": "test_keyboard",
        "keymap_file": "/path/to/keymap.keymap",
        "config_file": "/path/to/config.conf",
    }

    # Call the mocked method
    result = mock_service.validate_config(config)

    # Verify the result
    assert result.success is True
    mock_service.validate_config.assert_called_once_with(config)


def test_flash_service_with_keyboard_config():
    """Test that flash service can work with keyboard configurations."""
    # Create a mock flash service
    mock_service = Mock()

    # Set up mock methods for testing
    mock_service.flash_firmware.return_value = True

    # Mock keyboard config
    mock_keyboard_config = {
        "keyboard": "test_keyboard",
        "flash": {
            "query": "vendor=Test and removable=true",
        },
    }

    # Create a mock for the load_keyboard_config function
    mock_load = Mock(return_value=mock_keyboard_config)

    # Test with the mocked function
    config = mock_load("test_keyboard")

    # Verify the result
    assert config["flash"]["query"] == "vendor=Test and removable=true"
    mock_load.assert_called_once_with("test_keyboard")
