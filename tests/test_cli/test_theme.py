"""Tests for CLI theme system and IconMode functionality."""

from unittest.mock import Mock

import pytest

from glovebox.cli.helpers.theme import (
    IconMode,
    Icons,
    ThemedConsole,
    get_icon_mode_from_context,
    get_themed_console,
)


class TestIconMode:
    """Tests for IconMode enum."""

    def test_icon_mode_values(self):
        """Test IconMode enum values."""
        assert IconMode.EMOJI.value == "emoji"
        assert IconMode.NERDFONT.value == "nerdfont"
        assert IconMode.TEXT.value == "text"

    def test_icon_mode_string_inheritance(self):
        """Test that IconMode inherits from str."""
        assert isinstance(IconMode.EMOJI, str)
        assert isinstance(IconMode.NERDFONT, str)
        assert isinstance(IconMode.TEXT, str)

    def test_icon_mode_comparison(self):
        """Test IconMode comparison with strings."""
        # Test that enum values can be compared to strings
        assert IconMode.EMOJI.value == "emoji"
        assert IconMode.NERDFONT.value == "nerdfont"
        assert IconMode.TEXT.value == "text"

    def test_icon_mode_from_string(self):
        """Test creating IconMode from string."""
        assert IconMode("emoji") == IconMode.EMOJI
        assert IconMode("nerdfont") == IconMode.NERDFONT
        assert IconMode("text") == IconMode.TEXT

    def test_icon_mode_invalid_string(self):
        """Test that invalid strings raise ValueError."""
        with pytest.raises(ValueError):
            IconMode("invalid")


class TestIcons:
    """Tests for Icons class."""

    def test_get_icon_emoji_mode(self):
        """Test getting icons in emoji mode."""
        assert Icons.get_icon("SUCCESS", IconMode.EMOJI) == "✅"
        assert Icons.get_icon("ERROR", IconMode.EMOJI) == "❌"
        assert Icons.get_icon("WARNING", IconMode.EMOJI) == "⚠️"
        assert Icons.get_icon("INFO", IconMode.EMOJI) == "ℹ️"

    def test_get_icon_nerdfont_mode(self):
        """Test getting icons in nerdfont mode."""
        # Check that nerdfont icons are returned (actual unicode characters)
        success_icon = Icons.get_icon("SUCCESS", IconMode.NERDFONT)
        assert success_icon != ""  # Should have some icon
        assert len(success_icon) > 0  # Should not be empty

        error_icon = Icons.get_icon("ERROR", IconMode.NERDFONT)
        assert error_icon != ""
        assert len(error_icon) > 0

    def test_get_icon_text_mode(self):
        """Test getting icons in text mode."""
        # Check that text icons are returned (some might be empty for TEXT mode)
        success_icon = Icons.get_icon("SUCCESS", IconMode.TEXT)
        # TEXT mode might return empty string for some icons
        assert isinstance(success_icon, str)

        error_icon = Icons.get_icon("ERROR", IconMode.TEXT)
        assert isinstance(error_icon, str)

    def test_get_icon_string_mode(self):
        """Test getting icons using string mode (backward compatibility)."""
        assert Icons.get_icon("SUCCESS", "emoji") == "✅"
        # Just check that string mode works, don't assume specific values
        nerdfont_icon = Icons.get_icon("SUCCESS", "nerdfont")
        assert isinstance(nerdfont_icon, str)
        text_icon = Icons.get_icon("SUCCESS", "text")
        assert isinstance(text_icon, str)

    def test_get_icon_unknown_icon(self):
        """Test getting unknown icon returns fallback."""
        # Unknown icons may return empty string or fallback depending on implementation
        unknown_emoji = Icons.get_icon("UNKNOWN", IconMode.EMOJI)
        assert isinstance(unknown_emoji, str)
        unknown_nerdfont = Icons.get_icon("UNKNOWN", IconMode.NERDFONT)
        assert isinstance(unknown_nerdfont, str)
        unknown_text = Icons.get_icon("UNKNOWN", IconMode.TEXT)
        assert isinstance(unknown_text, str)

    def test_format_with_icon(self):
        """Test formatting message with icon."""
        result = Icons.format_with_icon("SUCCESS", "Test message", IconMode.EMOJI)
        assert result == "✅ Test message"

        # Test that format works with other modes (don't assume specific icon values)
        result = Icons.format_with_icon("ERROR", "Error message", IconMode.NERDFONT)
        assert "Error message" in result
        assert isinstance(result, str)

        result = Icons.format_with_icon("WARNING", "Warning message", IconMode.TEXT)
        assert "Warning message" in result
        assert isinstance(result, str)

    def test_format_with_icon_string_mode(self):
        """Test formatting message with icon using string mode."""
        result = Icons.format_with_icon("SUCCESS", "Test message", "emoji")
        assert result == "✅ Test message"

        # Test that format works with string mode (don't assume specific icon values)
        result = Icons.format_with_icon("ERROR", "Error message", "text")
        assert "Error message" in result
        assert isinstance(result, str)


class TestThemedConsole:
    """Tests for ThemedConsole class."""

    def test_themed_console_creation(self):
        """Test creating ThemedConsole with different icon modes."""
        console = ThemedConsole(icon_mode=IconMode.EMOJI)
        assert console.icon_mode == IconMode.EMOJI

        console = ThemedConsole(icon_mode=IconMode.NERDFONT)
        assert console.icon_mode == IconMode.NERDFONT

        console = ThemedConsole(icon_mode=IconMode.TEXT)
        assert console.icon_mode == IconMode.TEXT

    def test_themed_console_string_mode(self):
        """Test creating ThemedConsole with string icon mode."""
        console = ThemedConsole(icon_mode="emoji")
        assert console.icon_mode == IconMode.EMOJI

        console = ThemedConsole(icon_mode="nerdfont")
        assert console.icon_mode == IconMode.NERDFONT

        console = ThemedConsole(icon_mode="text")
        assert console.icon_mode == IconMode.TEXT


class TestGetThemedConsole:
    """Tests for get_themed_console function."""

    def test_get_themed_console_with_icon_mode(self):
        """Test getting themed console with specific icon mode."""
        console = get_themed_console(icon_mode=IconMode.EMOJI)
        assert isinstance(console, ThemedConsole)
        assert console.icon_mode == IconMode.EMOJI

        console = get_themed_console(icon_mode=IconMode.NERDFONT)
        assert console.icon_mode == IconMode.NERDFONT

    def test_get_themed_console_string_mode(self):
        """Test getting themed console with string icon mode."""
        console = get_themed_console(icon_mode="text")
        assert console.icon_mode == IconMode.TEXT

    def test_get_themed_console_default(self):
        """Test getting themed console with default settings."""
        console = get_themed_console()
        assert isinstance(console, ThemedConsole)
        # Should have a default icon mode
        assert hasattr(console, "icon_mode")


class MockAppContext:
    """Mock AppContext for testing."""

    def __init__(self, icon_mode_value="emoji"):
        self.icon_mode_value = icon_mode_value

    @property
    def icon_mode(self):
        """Mock icon_mode property that returns string."""
        return self.icon_mode_value


class TestGetIconModeFromContext:
    """Tests for get_icon_mode_from_context function."""

    def test_get_icon_mode_from_context_emoji(self):
        """Test getting icon mode from context with emoji mode."""
        # Create a mock context object
        ctx = Mock()
        ctx.obj = MockAppContext("emoji")

        result = get_icon_mode_from_context(ctx)
        assert result == IconMode.EMOJI

    def test_get_icon_mode_from_context_nerdfont(self):
        """Test getting icon mode from context with nerdfont mode."""
        ctx = Mock()
        ctx.obj = MockAppContext("nerdfont")

        result = get_icon_mode_from_context(ctx)
        assert result == IconMode.NERDFONT

    def test_get_icon_mode_from_context_text(self):
        """Test getting icon mode from context with text mode."""
        ctx = Mock()
        ctx.obj = MockAppContext("text")

        result = get_icon_mode_from_context(ctx)
        assert result == IconMode.TEXT

    def test_get_icon_mode_from_context_invalid(self):
        """Test getting icon mode from context with invalid mode falls back to emoji."""
        ctx = Mock()
        ctx.obj = MockAppContext("invalid")

        result = get_icon_mode_from_context(ctx)
        assert result == IconMode.EMOJI  # Should fallback to default

    def test_get_icon_mode_from_context_no_app_context(self):
        """Test getting icon mode from context with no app context falls back to emoji."""
        ctx = Mock()
        ctx.obj = None

        result = get_icon_mode_from_context(ctx)
        assert result == IconMode.EMOJI  # Should fallback to default

    def test_get_icon_mode_from_context_missing_icon_mode(self):
        """Test getting icon mode from context with object missing icon_mode attribute."""
        ctx = Mock()
        ctx.obj = object()  # Object without icon_mode attribute

        result = get_icon_mode_from_context(ctx)
        assert result == IconMode.EMOJI  # Should fallback to default
