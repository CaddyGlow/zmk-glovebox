"""Glovebox implementation of ConfigurationProvider for zmk-layout."""

import logging
from typing import Any

from glovebox.models.base import GloveboxBaseModel


class GloveboxConfigurationProvider(GloveboxBaseModel):
    """Configuration provider that bridges glovebox services to zmk-layout."""

    def __init__(
        self, keyboard_profile_service, settings_service, keyboard_id: str | None = None
    ):
        super().__init__()
        self.profile_service = keyboard_profile_service
        self.settings_service = settings_service
        self.keyboard_id = keyboard_id or settings_service.get_active_keyboard_id()

        # Cache for expensive operations
        self._behavior_cache = None
        self._validation_cache = None
        self._template_cache = None

        # Get logger for this component
        self.logger = logging.getLogger(__name__)

    def get_behavior_definitions(self) -> list[dict[str, Any]]:
        """Get ZMK behavior definitions from glovebox behavior registry."""
        if self._behavior_cache is None:
            try:
                profile = self.profile_service.get_profile(self.keyboard_id)

                # Map glovebox behavior format to zmk-layout format
                behaviors = []
                for behavior in profile.get_available_behaviors():
                    behaviors.append(
                        {
                            "name": behavior.zmk_name,
                            "type": behavior.behavior_type,
                            "params": behavior.parameter_names,
                            "description": behavior.description,
                            "compatible": behavior.zmk_compatible,
                            "validation_rules": behavior.get_validation_rules(),
                        }
                    )

                # Add standard ZMK behaviors
                behaviors.extend(
                    [
                        {"name": "kp", "type": "key-press", "params": ["keycode"]},
                        {"name": "mt", "type": "mod-tap", "params": ["hold", "tap"]},
                        {"name": "lt", "type": "layer-tap", "params": ["layer", "tap"]},
                        {"name": "to", "type": "to-layer", "params": ["layer"]},
                        {"name": "mo", "type": "momentary-layer", "params": ["layer"]},
                        {"name": "sl", "type": "sticky-layer", "params": ["layer"]},
                        {"name": "sk", "type": "sticky-key", "params": ["keycode"]},
                        {"name": "tog", "type": "toggle-layer", "params": ["layer"]},
                        {"name": "trans", "type": "transparent", "params": []},
                        {"name": "none", "type": "none", "params": []},
                    ]
                )

                self._behavior_cache = behaviors
                self.logger.debug(
                    "Loaded %d behavior definitions",
                    len(behaviors),
                    extra={"keyboard_id": self.keyboard_id},
                )

            except Exception as e:
                self.logger.error(
                    "Failed to load behavior definitions: %s",
                    e,
                    exc_info=self.logger.isEnabledFor(logging.DEBUG),
                )
                # Return minimal fallback behaviors
                self._behavior_cache = [
                    {"name": "kp", "type": "key-press", "params": ["keycode"]},
                    {"name": "trans", "type": "transparent", "params": []},
                    {"name": "none", "type": "none", "params": []},
                ]

        return self._behavior_cache

    def get_include_files(self) -> list[str]:
        """Get required include files for ZMK compilation."""
        try:
            profile = self.profile_service.get_profile(self.keyboard_id)

            includes = [
                "behaviors.dtsi",
                "dt-bindings/zmk/keys.h",
                "dt-bindings/zmk/bt.h",
                "dt-bindings/zmk/rgb.h",
            ]

            # Add keyboard-specific includes
            if profile.has_oled():
                includes.append("dt-bindings/zmk/outputs.h")

            if profile.has_rotary_encoder():
                includes.append("dt-bindings/zmk/sensors.h")

            # Add custom behavior includes
            custom_includes = profile.get_custom_includes()
            includes.extend(custom_includes)

            self.logger.debug(
                "Generated %d include files",
                len(includes),
                extra={"keyboard_id": self.keyboard_id},
            )
            return includes

        except Exception as e:
            self.logger.error(
                "Failed to get include files: %s",
                e,
                exc_info=self.logger.isEnabledFor(logging.DEBUG),
            )
            # Return minimal fallback includes
            return [
                "behaviors.dtsi",
                "dt-bindings/zmk/keys.h",
                "dt-bindings/zmk/bt.h",
            ]

    def get_validation_rules(self) -> dict[str, Any]:
        """Get keyboard-specific validation rules."""
        if self._validation_cache is None:
            try:
                profile = self.profile_service.get_profile(self.keyboard_id)
                layout_config = profile.layout_configuration

                self._validation_cache = {
                    "key_count": layout_config.total_keys,
                    "layer_limit": self.settings_service.get("max_layers", 32),
                    "combo_limit": self.settings_service.get("max_combos", 64),
                    "macro_limit": self.settings_service.get("max_macros", 32),
                    "hold_tap_limit": self.settings_service.get("max_hold_taps", 16),
                    "tap_dance_limit": self.settings_service.get("max_tap_dances", 8),
                    # Physical layout constraints
                    "physical_layout": {
                        "rows": layout_config.rows,
                        "columns": layout_config.columns,
                        "thumb_keys": layout_config.thumb_key_count,
                    },
                    # Timing constraints
                    "timing_constraints": {
                        "min_tapping_term": 50,
                        "max_tapping_term": 1000,
                        "min_combo_timeout": 10,
                        "max_combo_timeout": 200,
                    },
                    # Feature availability
                    "features": {
                        "split_keyboard": profile.is_split(),
                        "wireless": profile.supports_wireless(),
                        "rgb": profile.has_rgb(),
                        "oled": profile.has_oled(),
                        "rotary_encoder": profile.has_rotary_encoder(),
                    },
                }

                self.logger.debug(
                    "Generated validation rules for keyboard",
                    extra={
                        "keyboard_id": self.keyboard_id,
                        "key_count": layout_config.total_keys,
                    },
                )

            except Exception as e:
                self.logger.error(
                    "Failed to get validation rules: %s",
                    e,
                    exc_info=self.logger.isEnabledFor(logging.DEBUG),
                )
                # Return minimal fallback rules
                self._validation_cache = {
                    "key_count": 42,  # Reasonable default
                    "layer_limit": 32,
                    "combo_limit": 64,
                    "features": {
                        "split_keyboard": False,
                        "wireless": True,
                        "rgb": False,
                        "oled": False,
                        "rotary_encoder": False,
                    },
                }

        return self._validation_cache

    def get_template_context(self) -> dict[str, Any]:
        """Get context data for template processing."""
        if self._template_cache is None:
            try:
                profile = self.profile_service.get_profile(self.keyboard_id)
                user_settings = self.settings_service.get_user_settings()

                self._template_cache = {
                    # Keyboard information
                    "keyboard": {
                        "id": self.keyboard_id,
                        "name": profile.display_name,
                        "manufacturer": profile.manufacturer,
                        "variant": profile.variant,
                        "revision": profile.hardware_revision,
                    },
                    # Layout information
                    "layout": {
                        "name": profile.layout_name,
                        "key_count": profile.layout_configuration.total_keys,
                        "split": profile.is_split(),
                        "thumb_count": profile.layout_configuration.thumb_key_count,
                    },
                    # User preferences
                    "user": {
                        "name": user_settings.get("author_name", "Unknown"),
                        "email": user_settings.get("author_email", ""),
                        "preferred_behaviors": user_settings.get(
                            "preferred_behaviors", []
                        ),
                    },
                    # Build information
                    "build": {
                        "timestamp": self.settings_service.get_build_timestamp(),
                        "version": self.settings_service.get_app_version(),
                        "zmk_version": profile.target_zmk_version,
                    },
                    # Feature flags
                    "features": {
                        "oled_enabled": profile.has_oled(),
                        "rgb_enabled": profile.has_rgb(),
                        "wireless_enabled": profile.supports_wireless(),
                        "encoder_enabled": profile.has_rotary_encoder(),
                    },
                }

                self.logger.debug(
                    "Generated template context",
                    extra={"keyboard_id": self.keyboard_id},
                )

            except Exception as e:
                self.logger.error(
                    "Failed to get template context: %s",
                    e,
                    exc_info=self.logger.isEnabledFor(logging.DEBUG),
                )
                # Return minimal fallback context
                self._template_cache = {
                    "keyboard": {
                        "id": self.keyboard_id or "unknown",
                        "name": "Unknown Keyboard",
                        "manufacturer": "Unknown",
                        "variant": "default",
                        "revision": "1.0",
                    },
                    "layout": {
                        "name": "default",
                        "key_count": 42,
                        "split": False,
                        "thumb_count": 6,
                    },
                    "user": {
                        "name": "Unknown",
                        "email": "",
                        "preferred_behaviors": [],
                    },
                    "features": {
                        "oled_enabled": False,
                        "rgb_enabled": False,
                        "wireless_enabled": True,
                        "encoder_enabled": False,
                    },
                }

        return self._template_cache

    def get_kconfig_options(self) -> dict[str, Any]:
        """Get Kconfig options for the keyboard."""
        try:
            profile = self.profile_service.get_profile(self.keyboard_id)
            user_prefs = self.settings_service.get_user_preferences()

            config = {
                # Basic ZMK settings
                "CONFIG_ZMK_SLEEP": user_prefs.get("enable_sleep", True),
                "CONFIG_ZMK_IDLE_SLEEP_TIMEOUT": user_prefs.get(
                    "sleep_timeout_ms", 900000
                ),
                # Bluetooth settings
                "CONFIG_ZMK_BLE": profile.supports_wireless(),
                "CONFIG_BT_MAX_CONN": user_prefs.get("max_bt_connections", 5),
                "CONFIG_BT_MAX_PAIRED": user_prefs.get("max_bt_paired", 5),
                # USB settings
                "CONFIG_ZMK_USB": profile.supports_usb(),
                "CONFIG_ZMK_USB_BOOT": user_prefs.get("usb_boot_mode", False),
            }

            # Feature-specific config
            if profile.has_oled():
                config.update(
                    {
                        "CONFIG_ZMK_DISPLAY": True,
                        "CONFIG_ZMK_WIDGET_LAYER_STATUS": True,
                        "CONFIG_ZMK_WIDGET_BATTERY_STATUS": True,
                    }
                )

            if profile.has_rgb():
                config.update(
                    {
                        "CONFIG_ZMK_RGB_UNDERGLOW": True,
                        "CONFIG_WS2812_STRIP": True,
                        "CONFIG_ZMK_RGB_UNDERGLOW_ON_START": user_prefs.get(
                            "rgb_on_start", True
                        ),
                    }
                )

            if profile.has_rotary_encoder():
                config.update(
                    {
                        "CONFIG_EC11": True,
                        "CONFIG_EC11_TRIGGER_GLOBAL_THREAD": True,
                    }
                )

            # Advanced settings from user preferences
            advanced_config = user_prefs.get("advanced_kconfig", {})
            config.update(advanced_config)

            self.logger.debug(
                "Generated %d Kconfig options",
                len(config),
                extra={"keyboard_id": self.keyboard_id},
            )
            return config

        except Exception as e:
            self.logger.error(
                "Failed to get Kconfig options: %s",
                e,
                exc_info=self.logger.isEnabledFor(logging.DEBUG),
            )
            # Return minimal fallback config
            return {
                "CONFIG_ZMK_SLEEP": True,
                "CONFIG_ZMK_IDLE_SLEEP_TIMEOUT": 900000,
                "CONFIG_ZMK_BLE": True,
                "CONFIG_BT_MAX_CONN": 5,
                "CONFIG_BT_MAX_PAIRED": 5,
                "CONFIG_ZMK_USB": True,
            }

    def get_formatting_options(self) -> dict[str, Any]:
        """Get code formatting preferences."""
        try:
            user_prefs = self.settings_service.get_user_preferences()

            return {
                "indent_size": user_prefs.get("code_indent_size", 4),
                "use_tabs": user_prefs.get("use_tabs", False),
                "max_line_length": user_prefs.get("max_line_length", 120),
                "line_ending": user_prefs.get(
                    "line_ending", "unix"
                ),  # unix, windows, mac
                "insert_final_newline": user_prefs.get("insert_final_newline", True),
                "trim_trailing_whitespace": user_prefs.get(
                    "trim_trailing_whitespace", True
                ),
                # ZMK-specific formatting
                "binding_alignment": user_prefs.get("align_bindings", True),
                "layer_comment_style": user_prefs.get(
                    "layer_comments", "block"
                ),  # block, line, none
                "behavior_grouping": user_prefs.get("group_behaviors", True),
            }

        except Exception as e:
            self.logger.error(
                "Failed to get formatting options: %s",
                e,
                exc_info=self.logger.isEnabledFor(logging.DEBUG),
            )
            # Return sensible defaults
            return {
                "indent_size": 4,
                "use_tabs": False,
                "max_line_length": 120,
                "line_ending": "unix",
                "insert_final_newline": True,
                "trim_trailing_whitespace": True,
                "binding_alignment": True,
                "layer_comment_style": "block",
                "behavior_grouping": True,
            }

    def invalidate_cache(self) -> None:
        """Invalidate all cached data (call when profile changes)."""
        self._behavior_cache = None
        self._validation_cache = None
        self._template_cache = None

        self.logger.debug(
            "Configuration provider cache invalidated",
            extra={"keyboard_id": self.keyboard_id},
        )
