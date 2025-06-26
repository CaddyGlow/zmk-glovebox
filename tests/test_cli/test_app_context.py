"""Tests for CLI AppContext functionality, focusing on IconMode integration."""

from unittest.mock import Mock, patch

import pytest

from glovebox.cli.app import AppContext
from glovebox.cli.helpers.theme import IconMode


def create_mock_session_metrics():
    """Create a properly mocked session metrics object."""
    mock_session_metrics = Mock()
    # Mock the context manager protocol for time_operation
    mock_context = Mock()
    mock_context.__enter__ = Mock(return_value=None)
    mock_context.__exit__ = Mock(return_value=None)
    mock_session_metrics.time_operation.return_value = mock_context
    return mock_session_metrics


class TestAppContextIconMode:
    """Tests for AppContext icon_mode property."""

    def test_icon_mode_with_no_emoji_flag(self):
        """Test icon_mode property when no_emoji flag is set."""
        with (
            patch("glovebox.config.user_config.create_user_config") as mock_create,
            patch("glovebox.core.metrics.create_session_metrics") as mock_metrics,
        ):
            # Mock user config and session metrics
            mock_user_config = Mock()
            mock_session_metrics = create_mock_session_metrics()
            mock_create.return_value = mock_user_config
            mock_metrics.return_value = mock_session_metrics

            # Create AppContext with no_emoji=True
            app_ctx = AppContext(no_emoji=True)

            # Should return "text" regardless of config
            assert app_ctx.icon_mode == "text"

    def test_icon_mode_with_icon_mode_config(self):
        """Test icon_mode property with icon_mode in config."""
        with (
            patch("glovebox.config.user_config.create_user_config") as mock_create,
            patch("glovebox.core.metrics.create_session_metrics") as mock_metrics,
        ):
            # Mock user config with icon_mode set to nerdfont
            mock_user_config = Mock()
            mock_user_config._config = Mock()
            mock_user_config._config.icon_mode = IconMode.NERDFONT
            mock_session_metrics = create_mock_session_metrics()
            mock_create.return_value = mock_user_config
            mock_metrics.return_value = mock_session_metrics

            # Create AppContext
            app_ctx = AppContext(no_emoji=False)

            # Should return the enum value
            assert app_ctx.icon_mode == "nerdfont"

    def test_icon_mode_with_icon_mode_string_config(self):
        """Test icon_mode property with icon_mode as string in config."""
        with (
            patch("glovebox.config.user_config.create_user_config") as mock_create,
            patch("glovebox.core.metrics.create_session_metrics") as mock_metrics,
        ):
            # Mock user config with icon_mode as string
            mock_user_config = Mock()
            mock_user_config._config = Mock()
            mock_user_config._config.icon_mode = "text"
            mock_session_metrics = create_mock_session_metrics()
            mock_create.return_value = mock_user_config
            mock_metrics.return_value = mock_session_metrics

            # Create AppContext
            app_ctx = AppContext(no_emoji=False)

            # Should return the string value
            assert app_ctx.icon_mode == "text"

    def test_icon_mode_legacy_emoji_mode_true(self):
        """Test icon_mode property with legacy emoji_mode=True."""
        with (
            patch("glovebox.config.user_config.create_user_config") as mock_create,
            patch("glovebox.core.metrics.create_session_metrics") as mock_metrics,
        ):
            # Mock user config with only emoji_mode (legacy)
            mock_user_config = Mock()
            mock_user_config._config = Mock()
            # No icon_mode attribute, but has emoji_mode
            del mock_user_config._config.icon_mode  # Remove icon_mode
            mock_user_config._config.emoji_mode = True
            mock_session_metrics = create_mock_session_metrics()
            mock_create.return_value = mock_user_config
            mock_metrics.return_value = mock_session_metrics

            # Create AppContext
            app_ctx = AppContext(no_emoji=False)

            # Should return "emoji" for legacy compatibility
            assert app_ctx.icon_mode == "emoji"

    def test_icon_mode_legacy_emoji_mode_false(self):
        """Test icon_mode property with legacy emoji_mode=False."""
        with (
            patch("glovebox.config.user_config.create_user_config") as mock_create,
            patch("glovebox.core.metrics.create_session_metrics") as mock_metrics,
        ):
            # Mock user config with only emoji_mode=False (legacy)
            mock_user_config = Mock()
            mock_user_config._config = Mock()
            # No icon_mode attribute, but has emoji_mode
            del mock_user_config._config.icon_mode  # Remove icon_mode
            mock_user_config._config.emoji_mode = False
            mock_session_metrics = create_mock_session_metrics()
            mock_create.return_value = mock_user_config
            mock_metrics.return_value = mock_session_metrics

            # Create AppContext
            app_ctx = AppContext(no_emoji=False)

            # Should return "text" for legacy compatibility
            assert app_ctx.icon_mode == "text"

    def test_icon_mode_no_config_fields(self):
        """Test icon_mode property with no icon_mode or emoji_mode fields."""
        with (
            patch("glovebox.config.user_config.create_user_config") as mock_create,
            patch("glovebox.core.metrics.create_session_metrics") as mock_metrics,
        ):
            # Mock user config with neither icon_mode nor emoji_mode
            mock_user_config = Mock()
            mock_user_config._config = Mock()
            # Remove both attributes
            del mock_user_config._config.icon_mode
            del mock_user_config._config.emoji_mode
            mock_session_metrics = create_mock_session_metrics()
            mock_create.return_value = mock_user_config
            mock_metrics.return_value = mock_session_metrics

            # Create AppContext
            app_ctx = AppContext(no_emoji=False)

            # Should return default "emoji"
            assert app_ctx.icon_mode == "emoji"

    def test_icon_mode_no_emoji_overrides_config(self):
        """Test that no_emoji flag overrides config settings."""
        with (
            patch("glovebox.config.user_config.create_user_config") as mock_create,
            patch("glovebox.core.metrics.create_session_metrics") as mock_metrics,
        ):
            # Mock user config with icon_mode set to nerdfont
            mock_user_config = Mock()
            mock_user_config._config = Mock()
            mock_user_config._config.icon_mode = IconMode.NERDFONT
            mock_session_metrics = create_mock_session_metrics()
            mock_create.return_value = mock_user_config
            mock_metrics.return_value = mock_session_metrics

            # Create AppContext with no_emoji=True (should override config)
            app_ctx = AppContext(no_emoji=True)

            # Should return "text" despite config being nerdfont
            assert app_ctx.icon_mode == "text"

    def test_use_emoji_property_compatibility(self):
        """Test that use_emoji property still works for backward compatibility."""
        with (
            patch("glovebox.config.user_config.create_user_config") as mock_create,
            patch("glovebox.core.metrics.create_session_metrics") as mock_metrics,
        ):
            # Mock user config
            mock_user_config = Mock()
            mock_user_config._config = Mock()
            mock_user_config._config.icon_mode = IconMode.EMOJI
            mock_session_metrics = create_mock_session_metrics()
            mock_create.return_value = mock_user_config
            mock_metrics.return_value = mock_session_metrics

            # Test use_emoji property
            app_ctx = AppContext(no_emoji=False)
            assert app_ctx.use_emoji is True

            # Test with nerdfont mode
            mock_user_config._config.icon_mode = IconMode.NERDFONT
            app_ctx = AppContext(no_emoji=False)
            assert app_ctx.use_emoji is False

            # Test with text mode
            mock_user_config._config.icon_mode = IconMode.TEXT
            app_ctx = AppContext(no_emoji=False)
            assert app_ctx.use_emoji is False
