"""Unit tests for GloveboxConfigurationProvider."""

from unittest.mock import Mock, patch

import pytest

from glovebox.adapters.zmk_layout.configuration_provider import (
    GloveboxConfigurationProvider,
)


class TestGloveboxConfigurationProvider:
    """Test suite for GloveboxConfigurationProvider."""

    @pytest.fixture
    def mock_keyboard_service(self):
        """Mock keyboard profile service."""
        service = Mock()

        # Mock profile
        profile = Mock()
        profile.get_available_behaviors.return_value = [
            Mock(
                zmk_name="kp",
                behavior_type="key-press",
                parameter_names=["keycode"],
                description="Key press",
                zmk_compatible="zmk,behavior-key-press",
                get_validation_rules=Mock(return_value={"required_params": 1}),
            )
        ]
        profile.has_oled.return_value = False
        profile.has_rotary_encoder.return_value = False
        profile.has_rgb.return_value = False
        profile.is_split.return_value = True
        profile.supports_wireless.return_value = True
        profile.supports_usb.return_value = True
        profile.get_custom_includes.return_value = []
        profile.display_name = "Test Keyboard"
        profile.manufacturer = "Test Manufacturer"
        profile.variant = "default"
        profile.hardware_revision = "1.0"
        profile.layout_name = "test_layout"
        profile.target_zmk_version = "3.5.0"

        # Mock layout configuration
        layout_config = Mock()
        layout_config.total_keys = 42
        layout_config.rows = 4
        layout_config.columns = 6
        layout_config.thumb_key_count = 6
        profile.layout_configuration = layout_config

        service.get_profile.return_value = profile
        return service

    @pytest.fixture
    def mock_settings_service(self):
        """Mock settings service."""
        service = Mock()
        service.get_active_keyboard_id.return_value = "test_keyboard"
        service.get.return_value = 32  # Default for max_layers
        service.get_user_settings.return_value = {
            "author_name": "Test User",
            "author_email": "test@example.com",
            "preferred_behaviors": ["kp", "mt"],
        }
        service.get_user_preferences.return_value = {
            "enable_sleep": True,
            "sleep_timeout_ms": 900000,
            "max_bt_connections": 5,
            "code_indent_size": 4,
            "use_tabs": False,
        }
        service.get_build_timestamp.return_value = "2024-01-01T00:00:00Z"
        service.get_app_version.return_value = "1.0.0"
        return service

    @pytest.fixture
    def provider(self, mock_keyboard_service, mock_settings_service):
        """Create provider instance for testing."""
        return GloveboxConfigurationProvider(
            keyboard_profile_service=mock_keyboard_service,
            settings_service=mock_settings_service,
            keyboard_id="test_keyboard",
        )

    def test_initialization(self, provider):
        """Test provider initialization."""
        assert provider.keyboard_id == "test_keyboard"
        assert provider._behavior_cache is None
        assert provider._validation_cache is None
        assert provider._template_cache is None

    def test_get_behavior_definitions(self, provider):
        """Test behavior definitions retrieval."""
        behaviors = provider.get_behavior_definitions()

        assert isinstance(behaviors, list)
        assert len(behaviors) > 0

        # Check for custom behavior from mock
        custom_behavior = next((b for b in behaviors if b["name"] == "kp"), None)
        assert custom_behavior is not None
        assert custom_behavior["type"] == "key-press"
        assert custom_behavior["params"] == ["keycode"]

        # Check for standard ZMK behaviors
        standard_behaviors = ["mt", "lt", "to", "mo", "trans", "none"]
        behavior_names = [b["name"] for b in behaviors]
        for std_behavior in standard_behaviors:
            assert std_behavior in behavior_names

    def test_behavior_definitions_caching(self, provider):
        """Test that behavior definitions are cached."""
        # First call
        behaviors1 = provider.get_behavior_definitions()

        # Second call should return cached result
        behaviors2 = provider.get_behavior_definitions()

        assert behaviors1 is behaviors2  # Same object reference

        # Verify mock was only called once
        assert provider.profile_service.get_profile.call_count == 1

    def test_get_include_files(self, provider):
        """Test include files retrieval."""
        includes = provider.get_include_files()

        assert isinstance(includes, list)
        assert len(includes) > 0

        # Check for standard includes
        expected_includes = [
            "behaviors.dtsi",
            "dt-bindings/zmk/keys.h",
            "dt-bindings/zmk/bt.h",
            "dt-bindings/zmk/rgb.h",
        ]

        for expected in expected_includes:
            assert expected in includes

    def test_get_validation_rules(self, provider):
        """Test validation rules retrieval."""
        rules = provider.get_validation_rules()

        assert isinstance(rules, dict)
        assert "key_count" in rules
        assert rules["key_count"] == 42
        assert "layer_limit" in rules
        assert "physical_layout" in rules
        assert "timing_constraints" in rules
        assert "features" in rules

        # Check physical layout
        physical = rules["physical_layout"]
        assert physical["rows"] == 4
        assert physical["columns"] == 6
        assert physical["thumb_keys"] == 6

        # Check features
        features = rules["features"]
        assert features["split_keyboard"] is True
        assert features["wireless"] is True

    def test_get_template_context(self, provider):
        """Test template context retrieval."""
        context = provider.get_template_context()

        assert isinstance(context, dict)
        assert "keyboard" in context
        assert "layout" in context
        assert "user" in context
        assert "build" in context
        assert "features" in context

        # Check keyboard info
        keyboard = context["keyboard"]
        assert keyboard["id"] == "test_keyboard"
        assert keyboard["name"] == "Test Keyboard"
        assert keyboard["manufacturer"] == "Test Manufacturer"

        # Check user info
        user = context["user"]
        assert user["name"] == "Test User"
        assert user["email"] == "test@example.com"

    def test_get_kconfig_options(self, provider):
        """Test Kconfig options retrieval."""
        config = provider.get_kconfig_options()

        assert isinstance(config, dict)
        assert "CONFIG_ZMK_SLEEP" in config
        assert "CONFIG_ZMK_BLE" in config
        assert "CONFIG_ZMK_USB" in config

        # Check values
        assert config["CONFIG_ZMK_SLEEP"] is True
        assert config["CONFIG_ZMK_BLE"] is True
        assert config["CONFIG_ZMK_USB"] is True

    def test_get_formatting_options(self, provider):
        """Test formatting options retrieval."""
        options = provider.get_formatting_options()

        assert isinstance(options, dict)
        assert "indent_size" in options
        assert "use_tabs" in options
        assert "max_line_length" in options
        assert "binding_alignment" in options

        # Check values
        assert options["indent_size"] == 4
        assert options["use_tabs"] is False

    def test_invalidate_cache(self, provider):
        """Test cache invalidation."""
        # Populate caches
        provider.get_behavior_definitions()
        provider.get_validation_rules()
        provider.get_template_context()

        # Verify caches are populated
        assert provider._behavior_cache is not None
        assert provider._validation_cache is not None
        assert provider._template_cache is not None

        # Invalidate cache
        provider.invalidate_cache()

        # Verify caches are cleared
        assert provider._behavior_cache is None
        assert provider._validation_cache is None
        assert provider._template_cache is None

    def test_error_handling_behavior_definitions(self, provider):
        """Test error handling in get_behavior_definitions."""
        # Make profile service raise exception
        provider.profile_service.get_profile.side_effect = Exception("Service error")

        behaviors = provider.get_behavior_definitions()

        # Should return fallback behaviors
        assert isinstance(behaviors, list)
        assert len(behaviors) >= 3  # At least the fallback behaviors

        # Should contain fallback behaviors
        behavior_names = [b["name"] for b in behaviors]
        assert "kp" in behavior_names
        assert "trans" in behavior_names
        assert "none" in behavior_names

    def test_error_handling_include_files(self, provider):
        """Test error handling in get_include_files."""
        # Make profile service raise exception
        provider.profile_service.get_profile.side_effect = Exception("Service error")

        includes = provider.get_include_files()

        # Should return fallback includes
        assert isinstance(includes, list)
        assert len(includes) >= 3  # At least the fallback includes
        assert "behaviors.dtsi" in includes
        assert "dt-bindings/zmk/keys.h" in includes

    def test_keyboard_specific_features_oled(self, provider):
        """Test keyboard-specific features with OLED."""
        # Configure profile to have OLED
        profile = provider.profile_service.get_profile.return_value
        profile.has_oled.return_value = True

        # Clear cache to force reload
        provider.invalidate_cache()

        includes = provider.get_include_files()
        assert "dt-bindings/zmk/outputs.h" in includes

        kconfig = provider.get_kconfig_options()
        assert kconfig.get("CONFIG_ZMK_DISPLAY") is True
        assert kconfig.get("CONFIG_ZMK_WIDGET_LAYER_STATUS") is True

    def test_keyboard_specific_features_rgb(self, provider):
        """Test keyboard-specific features with RGB."""
        # Configure profile to have RGB
        profile = provider.profile_service.get_profile.return_value
        profile.has_rgb.return_value = True

        # Clear cache to force reload
        provider.invalidate_cache()

        kconfig = provider.get_kconfig_options()
        assert kconfig.get("CONFIG_ZMK_RGB_UNDERGLOW") is True
        assert kconfig.get("CONFIG_WS2812_STRIP") is True

    def test_keyboard_specific_features_encoder(self, provider):
        """Test keyboard-specific features with rotary encoder."""
        # Configure profile to have encoder
        profile = provider.profile_service.get_profile.return_value
        profile.has_rotary_encoder.return_value = True

        # Clear cache to force reload
        provider.invalidate_cache()

        includes = provider.get_include_files()
        assert "dt-bindings/zmk/sensors.h" in includes

        kconfig = provider.get_kconfig_options()
        assert kconfig.get("CONFIG_EC11") is True
        assert kconfig.get("CONFIG_EC11_TRIGGER_GLOBAL_THREAD") is True
