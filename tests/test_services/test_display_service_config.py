"""Tests for KeymapDisplayService with keyboard configuration API."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from glovebox.config.models import KeyboardConfig
from glovebox.config.profile import KeyboardProfile
from glovebox.layout import LayoutConfig
from glovebox.services.display_service import (
    KeymapDisplayService,
    create_display_service,
    create_profile_from_keyboard_name,
)


class TestDisplayServiceWithKeyboardConfig:
    """Test KeymapDisplayService with the new keyboard configuration API."""

    def setup_method(self):
        """Set up test environment."""
        self.service = KeymapDisplayService()

    def test_create_layout_config_from_keyboard_profile(self):
        """Test creating layout config directly from KeyboardProfile."""
        # Create mock profile
        mock_keyboard_config = Mock(spec=KeyboardConfig)
        mock_keyboard_config.keyboard = "test_keyboard"
        mock_keyboard_config.description = "Test Keyboard Description"

        mock_profile = Mock(spec=KeyboardProfile)
        mock_profile.keyboard_config = mock_keyboard_config
        mock_profile.keyboard_name = "test_keyboard"
        mock_profile.firmware_version = "test_version"

        # Execute
        layout_config = self.service._create_layout_config_from_keyboard_profile(
            mock_profile
        )

        # Verify
        assert layout_config is not None
        assert isinstance(layout_config, LayoutConfig)
        assert layout_config.keyboard_name == "test_keyboard"
        assert layout_config.total_keys == 80  # Default for Glove80
        assert len(layout_config.rows) > 0
        assert layout_config.key_position_map

    @patch("glovebox.services.display_service.create_profile_from_keyboard_name")
    def test_get_layout_config_with_profile(self, mock_create_profile):
        """Test getting layout config with KeyboardProfile."""
        # Create mock profile
        mock_keyboard_config = Mock(spec=KeyboardConfig)
        mock_keyboard_config.keyboard = "test_keyboard"

        mock_profile = Mock(spec=KeyboardProfile)
        mock_profile.keyboard_config = mock_keyboard_config
        mock_profile.keyboard_name = "test_keyboard"
        mock_profile.firmware_version = "test_version"

        # Test with explicit profile
        keymap_data = {"keyboard": "test_keyboard"}

        # Execute with direct profile
        layout_config = self.service._get_layout_config(mock_profile, None, keymap_data)

        # Verify
        assert layout_config is not None
        assert isinstance(layout_config, LayoutConfig)
        assert layout_config.keyboard_name == "test_keyboard"

        # Verify profile creation was NOT attempted since we provided a profile
        mock_create_profile.assert_not_called()

    @patch("glovebox.services.display_service.create_profile_from_keyboard_name")
    def test_get_layout_config_creates_profile(
        self, mock_create_profile, mock_keyboard_config
    ):
        """Test getting layout config creates profile when keyboard_type is provided."""
        # Setup mocks
        mock_keyboard_config_obj = Mock(spec=KeyboardConfig)
        mock_keyboard_config_obj.keyboard = "test_keyboard"

        mock_profile = Mock(spec=KeyboardProfile)
        mock_profile.keyboard_config = mock_keyboard_config_obj
        mock_profile.keyboard_name = "test_keyboard"
        mock_profile.firmware_version = "test_version"

        mock_create_profile.return_value = mock_profile

        # Test parameters
        keyboard_type = "test_keyboard"
        keymap_data = {"keyboard": "test_keyboard"}

        # Execute
        layout_config = self.service._get_layout_config(
            None, keyboard_type, keymap_data
        )

        # Verify
        assert layout_config is not None
        assert isinstance(layout_config, LayoutConfig)

        # Verify profile creation was attempted
        mock_create_profile.assert_called_once_with("test_keyboard")

    @patch("glovebox.services.display_service.get_available_keyboards")
    @patch("glovebox.services.display_service.create_profile_from_keyboard_name")
    def test_get_layout_config_no_keyboard_specified(
        self, mock_create_profile, mock_get_keyboards, mock_keyboard_config
    ):
        """Test getting layout config when no keyboard is specified."""
        # Setup mocks
        mock_get_keyboards.return_value = ["test_keyboard", "glove80"]

        mock_keyboard_config_obj = Mock(spec=KeyboardConfig)
        mock_keyboard_config_obj.keyboard = "test_keyboard"

        mock_profile = Mock(spec=KeyboardProfile)
        mock_profile.keyboard_config = mock_keyboard_config_obj
        mock_profile.keyboard_name = "test_keyboard"
        mock_profile.firmware_version = "test_version"

        mock_create_profile.return_value = mock_profile

        # Test with no keyboard specified in keymap or parameters
        keymap_data = {"title": "Test Keymap"}  # No keyboard field

        # Execute
        layout_config = self.service._get_layout_config(None, None, keymap_data)

        # Verify
        assert layout_config is not None
        assert isinstance(layout_config, LayoutConfig)

        # Verify available keyboards were fetched
        mock_get_keyboards.assert_called_once()

        # Verify first available keyboard was used
        mock_create_profile.assert_called_once_with("test_keyboard")

    def test_create_layout_config_from_keyboard_config(self, mock_keyboard_config):
        """Test creating layout config directly from keyboard config dict (backward compatibility)."""
        # Execute
        layout_config = self.service._create_layout_config_from_keyboard_config(
            mock_keyboard_config
        )

        # Verify
        assert layout_config is not None
        assert isinstance(layout_config, LayoutConfig)
        assert layout_config.keyboard_name == mock_keyboard_config["keyboard"]
        assert layout_config.total_keys == 80  # Default for Glove80
        assert len(layout_config.rows) > 0
        assert layout_config.key_position_map

    def test_display_keymap_with_profile(self):
        """Test displaying keymap with profile."""
        # Create mock profile
        mock_keyboard_config = Mock(spec=KeyboardConfig)
        mock_keyboard_config.keyboard = "test_keyboard"

        mock_profile = Mock(spec=KeyboardProfile)
        mock_profile.keyboard_config = mock_keyboard_config
        mock_profile.keyboard_name = "test_keyboard"
        mock_profile.firmware_version = "test_version"

        # Create sample keymap data
        keymap_data = {
            "keyboard": "test_keyboard",
            "title": "Test Keymap",
            "creator": "Test User",
            "locale": "en-US",
            "layer_names": ["DEFAULT"],
            "layers": [[{"value": "&kp", "params": ["A"]} for _ in range(80)]],
        }

        # Mock the layout generation methods
        with (
            patch.object(
                self.service,
                "_create_layout_config_from_keyboard_profile",
                return_value=LayoutConfig(
                    keyboard_name="test_keyboard",
                    key_width=10,
                    key_gap="  ",
                    key_position_map={},
                ),
            ),
            patch.object(
                self.service._layout_generator,
                "generate_keymap_display",
                return_value="[formatted keymap with profile]",
            ),
        ):
            # Execute with profile
            result = self.service.display_keymap_with_layout(
                keymap_data, profile=mock_profile
            )

            # Verify
            assert result == "[formatted keymap with profile]"

    @patch("glovebox.services.display_service.create_profile_from_keyboard_name")
    def test_display_keymap_with_keyboard_type(self, mock_create_profile):
        """Test displaying keymap with keyboard type (creates profile)."""
        # Setup mocks
        mock_keyboard_config = Mock(spec=KeyboardConfig)
        mock_keyboard_config.keyboard = "test_keyboard"

        mock_profile = Mock(spec=KeyboardProfile)
        mock_profile.keyboard_config = mock_keyboard_config
        mock_profile.keyboard_name = "test_keyboard"
        mock_profile.firmware_version = "test_version"

        mock_create_profile.return_value = mock_profile

        # Create sample keymap data
        keymap_data = {
            "keyboard": "test_keyboard",
            "title": "Test Keymap",
            "creator": "Test User",
            "locale": "en-US",
            "layer_names": ["DEFAULT"],
            "layers": [[{"value": "&kp", "params": ["A"]} for _ in range(80)]],
        }

        # Mock the layout generation methods
        with (
            patch.object(
                self.service,
                "_create_layout_config_from_keyboard_profile",
                return_value=LayoutConfig(
                    keyboard_name="test_keyboard",
                    key_width=10,
                    key_gap="  ",
                    key_position_map={},
                ),
            ),
            patch.object(
                self.service._layout_generator,
                "generate_keymap_display",
                return_value="[formatted keymap with keyboard type]",
            ),
        ):
            # Execute with keyboard type
            result = self.service.display_keymap_with_layout(
                keymap_data, keyboard_type="test_keyboard"
            )

            # Verify
            assert result == "[formatted keymap with keyboard type]"
            mock_create_profile.assert_called_once_with("test_keyboard")

    def test_display_keymap_with_layout_fallback(self):
        """Test display falls back to simple layout when profile creation fails."""
        # Create sample keymap data
        keymap_data = {
            "keyboard": "test_keyboard",
            "title": "Test Keymap",
            "creator": "Test User",
            "locale": "en-US",
            "layer_names": ["DEFAULT"],
            "layers": [[{"value": "&kp", "params": ["A"]} for _ in range(80)]],
        }

        # Setup mocks to simulate errors
        with (
            patch(
                "glovebox.services.display_service.create_profile_from_keyboard_name",
                side_effect=Exception("Failed to create profile"),
            ),
            patch(
                "glovebox.config.keyboard_config.load_keyboard_config_raw",
                side_effect=Exception("Failed to load config"),
            ),
            patch.object(
                self.service, "display_layout", return_value="[simple layout]"
            ),
        ):
            # Execute
            result = self.service.display_keymap_with_layout(
                keymap_data, keyboard_type="test_keyboard"
            )

            # Verify fallback was used
            assert result == "[simple layout]"


@patch("glovebox.services.display_service.create_profile_from_keyboard_name")
def test_integrated_display_workflow(mock_create_profile, mock_keyboard_config):
    """Test integrated display workflow."""
    # Create mock profile
    mock_keyboard_config_obj = Mock(spec=KeyboardConfig)
    mock_keyboard_config_obj.keyboard = "test_keyboard"

    mock_profile = Mock(spec=KeyboardProfile)
    mock_profile.keyboard_config = mock_keyboard_config_obj
    mock_profile.keyboard_name = "test_keyboard"
    mock_profile.firmware_version = "test_version"

    mock_create_profile.return_value = mock_profile

    # Create a real service
    service = create_display_service()

    # Create sample keymap data
    keymap_data = {
        "keyboard": "test_keyboard",
        "title": "Test Keymap",
        "creator": "Test User",
        "locale": "en-US",
        "notes": "Test notes",
        "layer_names": ["DEFAULT"],
        "layers": [[{"value": "&kp", "params": ["A"]} for _ in range(80)]],
    }

    # Mock keyboard config loading and layout generation
    with patch.object(
        service._layout_generator,
        "generate_keymap_display",
        return_value="[formatted keymap]",
    ):
        # This is primarily an integration test to ensure the API works correctly
        try:
            result = service.display_keymap_with_layout(
                keymap_data, keyboard_type="test_keyboard"
            )
            success = True
        except Exception:
            success = False

        assert success is True
        assert result == "[formatted keymap]"
        mock_create_profile.assert_called_once_with("test_keyboard")
