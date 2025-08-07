"""Factory for creating glovebox-specific zmk-layout providers."""

import logging
from typing import Any, Optional

from glovebox.models.base import GloveboxBaseModel

from .configuration_provider import GloveboxConfigurationProvider
from .logger import GloveboxLogger
from .template_provider import GloveboxTemplateProvider


class LayoutProviders(GloveboxBaseModel):
    """Container for layout providers."""

    def __init__(self, configuration: Any, template: Any, logger: Any) -> None:
        super().__init__()
        self.configuration = configuration
        self.template = template
        self.logger = logger


def create_glovebox_providers(
    keyboard_id: str | None = None, services: dict[str, Any] | None = None
) -> LayoutProviders:
    """Create LayoutProviders using glovebox services.

    Args:
        keyboard_id: Optional specific keyboard ID
        services: Optional service overrides for testing

    Returns:
        LayoutProviders instance configured for glovebox
    """
    logger = logging.getLogger(__name__)

    try:
        # Get services (allows injection for testing)
        if services:
            keyboard_service = services.get("keyboard_profile")
            template_service = services.get("template")
            logging_service = services.get("logging")
            settings_service = services.get("settings")
        else:
            # Use actual glovebox services
            try:
                from glovebox.config.keyboard_profile import create_keyboard_profile
                from glovebox.config.user_config import create_user_config
                from glovebox.core.logging import get_logger
                from glovebox.layout.template_service import create_template_service

                # Create real glovebox services
                user_config = create_user_config()

                keyboard_service = _create_real_keyboard_service(
                    keyboard_id, user_config
                )
                template_service = _create_real_template_service()
                logging_service = _create_real_logging_service()
                settings_service = _create_real_settings_service(user_config)

                logger.info("Using real glovebox services for zmk-layout integration")

            except Exception as service_error:
                logger.warning(
                    "Failed to create real glovebox services, falling back to mocks: %s",
                    service_error,
                )
                # Fallback to mock services
                keyboard_service = _create_mock_keyboard_service()
                template_service = _create_mock_template_service()
                logging_service = _create_mock_logging_service()
                settings_service = _create_mock_settings_service()

        # Create providers
        configuration = GloveboxConfigurationProvider(
            keyboard_profile_service=keyboard_service,
            settings_service=settings_service,
            keyboard_id=keyboard_id,
        )

        template = GloveboxTemplateProvider(template_service=template_service)

        logger_provider = GloveboxLogger(
            logging_service=logging_service, component="zmk_layout"
        )

        providers = LayoutProviders(
            configuration=configuration, template=template, logger=logger_provider
        )

        logger.info("Created glovebox providers", extra={"keyboard_id": keyboard_id})

        return providers

    except Exception as e:
        logger.error(
            "Failed to create glovebox providers: %s",
            e,
            exc_info=logger.isEnabledFor(logging.DEBUG),
        )
        raise


def create_test_providers(
    keyboard_config: dict[str, Any] | None = None,
    template_engine: str = "simple",
    log_level: str = "INFO",
) -> LayoutProviders:
    """Create providers for testing with minimal dependencies.

    Args:
        keyboard_config: Optional keyboard configuration override
        template_engine: Template engine to use ("simple" or "jinja2")
        log_level: Logging level

    Returns:
        LayoutProviders for testing
    """
    # Create test services
    test_services = {
        "keyboard_profile": _create_test_keyboard_service(keyboard_config),
        "template": _create_test_template_service(template_engine),
        "logging": _create_test_logging_service(log_level),
        "settings": _create_test_settings_service(),
    }

    return create_glovebox_providers(services=test_services)


def validate_glovebox_providers(providers: LayoutProviders) -> list[str]:
    """Validate that providers are properly configured for glovebox integration.

    Args:
        providers: LayoutProviders to validate

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Check configuration provider
    try:
        behaviors = providers.configuration.get_behavior_definitions()
        if not behaviors:
            errors.append("Configuration provider returned no behaviors")

        rules = providers.configuration.get_validation_rules()
        if "key_count" not in rules:
            errors.append("Configuration provider missing key_count validation rule")

    except Exception as e:
        errors.append(f"Configuration provider error: {e}")

    # Check template provider
    try:
        test_template = "Hello {{name}}"
        test_context = {"name": "World"}
        result = providers.template.render_string(test_template, test_context)
        if "Hello World" not in result:
            errors.append("Template provider not rendering correctly")

    except Exception as e:
        errors.append(f"Template provider error: {e}")

    # Check logger
    try:
        providers.logger.info("Test log message")
    except Exception as e:
        errors.append(f"Logger provider error: {e}")

    return errors


# Mock service implementations for development/testing
def _create_mock_keyboard_service() -> Any:
    """Create mock keyboard service for development."""

    class MockKeyboardProfile:
        def __init__(self) -> None:
            self.display_name = "Test Keyboard"
            self.manufacturer = "Test Manufacturer"
            self.variant = "default"
            self.hardware_revision = "1.0"
            self.layout_name = "test_layout"
            self.target_zmk_version = "3.5.0"

            # Mock layout configuration
            self.layout_configuration = MockLayoutConfig()

        def get_available_behaviors(self) -> list[Any]:
            return [MockBehavior()]

        def has_oled(self) -> bool:
            return False

        def has_rotary_encoder(self) -> bool:
            return False

        def has_rgb(self) -> bool:
            return False

        def is_split(self) -> bool:
            return True

        def supports_wireless(self) -> bool:
            return True

        def supports_usb(self) -> bool:
            return True

        def get_custom_includes(self) -> list[str]:
            return []

    class MockLayoutConfig:
        def __init__(self) -> None:
            self.total_keys = 42
            self.rows = 4
            self.columns = 6
            self.thumb_key_count = 6

    class MockBehavior:
        def __init__(self) -> None:
            self.zmk_name = "kp"
            self.behavior_type = "key-press"
            self.parameter_names = ["keycode"]
            self.description = "Key press behavior"
            self.zmk_compatible = "zmk,behavior-key-press"

        def get_validation_rules(self) -> dict[str, Any]:
            return {"required_params": 1}

    class MockKeyboardService:
        def get_profile(self, keyboard_id: str) -> Any:
            return MockKeyboardProfile()

    return MockKeyboardService()


def _create_mock_template_service() -> Any:
    """Create mock template service for development."""

    class MockTemplateService:
        def render_string(self, template: str, context: dict[str, Any]) -> str:
            # Simple template rendering for testing
            result = template
            for key, value in context.items():
                result = result.replace(f"{{{{{key}}}}}", str(value))
            return result

        def render_file(self, template_path: str, context: dict[str, Any]) -> str:
            return f"Rendered file: {template_path}"

        def contains_template_syntax(self, content: str) -> bool:
            return "{{" in content and "}}" in content

        def validate_syntax(self, template: str) -> None:
            if template.count("{{") != template.count("}}"):
                raise ValueError("Unmatched template braces")

        def escape_template_content(self, content: str) -> str:
            return content.replace("{", "{{").replace("}", "}}")

        def get_engine_name(self) -> str:
            return "mock_engine"

        def get_engine_version(self) -> str:
            return "1.0.0"

        def get_supported_features(self) -> list[str]:
            return ["basic_templating", "context_variables"]

    return MockTemplateService()


def _create_mock_logging_service() -> Any:
    """Create mock logging service for development."""

    class MockLoggingService:
        def get_logger(self, component: str) -> Any:
            return logging.getLogger(f"glovebox.{component}")

    return MockLoggingService()


def _create_mock_settings_service() -> Any:
    """Create mock settings service for development."""

    class MockSettingsService:
        def get_active_keyboard_id(self) -> str:
            return "test_keyboard"

        def get(self, key: str, default: Any = None) -> Any:
            defaults = {
                "max_layers": 32,
                "max_combos": 64,
                "max_macros": 32,
                "max_hold_taps": 16,
                "max_tap_dances": 8,
            }
            return defaults.get(key, default)

        def get_user_settings(self) -> dict[str, Any]:
            return {
                "author_name": "Test User",
                "author_email": "test@example.com",
                "preferred_behaviors": ["kp", "mt", "lt"],
            }

        def get_user_preferences(self) -> dict[str, Any]:
            return {
                "enable_sleep": True,
                "sleep_timeout_ms": 900000,
                "max_bt_connections": 5,
                "max_bt_paired": 5,
                "usb_boot_mode": False,
                "rgb_on_start": True,
                "code_indent_size": 4,
                "use_tabs": False,
                "max_line_length": 120,
                "line_ending": "unix",
                "insert_final_newline": True,
                "trim_trailing_whitespace": True,
                "align_bindings": True,
                "layer_comments": "block",
                "group_behaviors": True,
                "advanced_kconfig": {},
            }

        def get_build_timestamp(self) -> str:
            return "2024-01-01T00:00:00Z"

        def get_app_version(self) -> str:
            return "1.0.0"

    return MockSettingsService()


def _create_test_keyboard_service(config: dict[str, Any] | None = None) -> Any:
    """Create test keyboard service with specific config."""
    service = _create_mock_keyboard_service()
    if config:
        # Apply any test-specific configuration overrides
        pass
    return service


def _create_test_template_service(engine: str = "simple") -> Any:
    """Create test template service."""
    return _create_mock_template_service()


def _create_test_logging_service(log_level: str = "INFO") -> Any:
    """Create test logging service."""
    return _create_mock_logging_service()


def _create_test_settings_service() -> Any:
    """Create test settings service."""
    return _create_mock_settings_service()


# Real glovebox service implementations for production use
def _create_real_keyboard_service(keyboard_id: str | None, user_config: Any) -> Any:
    """Create real keyboard service using glovebox keyboard profile system."""
    from glovebox.config.keyboard_profile import create_keyboard_profile

    class GloveboxKeyboardService:
        def __init__(self, keyboard_id: str | None, user_config: Any):
            self.keyboard_id = keyboard_id
            self.user_config = user_config

        def get_profile(self, keyboard_id: str) -> Any:
            """Get keyboard profile using real glovebox configuration system."""
            try:
                # Use the keyboard_id parameter first, then fall back to default
                profile_keyboard_id = keyboard_id or self.keyboard_id or "glove80"

                # Create keyboard profile using glovebox configuration system
                profile = create_keyboard_profile(
                    keyboard_name=profile_keyboard_id,
                    firmware_version=None,  # Use latest
                    user_config=self.user_config,
                )

                return profile

            except Exception as e:
                # If we can't load the specific keyboard, create a minimal profile
                from glovebox.config.models.keyboard import KeyboardConfig
                from glovebox.config.profile import KeyboardProfile

                # Create minimal keyboard config for fallback
                # Use all required fields for KeyboardConfig
                minimal_config = KeyboardConfig(
                    keyboard=keyboard_id or "unknown",
                    description=f"Fallback keyboard profile for {keyboard_id or 'unknown'}",
                    vendor="Unknown Vendor",
                    key_count=42,  # Reasonable default for split keyboards
                )

                return KeyboardProfile(
                    keyboard_config=minimal_config,
                    firmware_version="latest",
                )

    return GloveboxKeyboardService(keyboard_id, user_config)


def _create_real_template_service() -> Any:
    """Create real template service using glovebox template system."""
    from glovebox.layout.template_service import create_template_service

    try:
        # Try to create jinja2 template service (preferred)
        from glovebox.layout.template_service import create_jinja2_template_service

        template_service = create_jinja2_template_service()
    except Exception:
        # Fallback to simple template service
        try:
            from glovebox.adapters.template_adapter import TemplateAdapter

            template_adapter = TemplateAdapter()
            template_service = create_template_service(template_adapter)
        except Exception:
            # Last resort - use mock service
            return _create_mock_template_service()

    return template_service


def _create_real_logging_service() -> Any:
    """Create real logging service using glovebox logging system."""
    from glovebox.core.logging import get_logger

    class GloveboxLoggingService:
        def get_logger(self, component: str) -> Any:
            return get_logger(f"zmk_layout.{component}")

    return GloveboxLoggingService()


def _create_real_settings_service(user_config: Any) -> Any:
    """Create real settings service using glovebox user configuration."""

    class GloveboxSettingsService:
        def __init__(self, user_config: Any):
            self.user_config = user_config

        def get_active_keyboard_id(self) -> str:
            """Get active keyboard ID from user configuration."""
            try:
                return self.user_config.active_keyboard or "glove80"
            except Exception:
                return "glove80"

        def get(self, key: str, default: Any = None) -> Any:
            """Get configuration value by key."""
            try:
                # Map zmk-layout configuration keys to glovebox user config
                mapping = {
                    "max_layers": "layout.max_layers",
                    "max_combos": "layout.max_combos",
                    "max_macros": "layout.max_macros",
                    "max_hold_taps": "layout.max_hold_taps",
                    "max_tap_dances": "layout.max_tap_dances",
                }

                config_key = mapping.get(key, key)
                return self.user_config.get_nested(config_key, default)
            except Exception:
                # Fallback to reasonable defaults
                defaults = {
                    "max_layers": 32,
                    "max_combos": 64,
                    "max_macros": 32,
                    "max_hold_taps": 16,
                    "max_tap_dances": 8,
                }
                return defaults.get(key, default)

        def get_user_settings(self) -> dict[str, Any]:
            """Get user settings dictionary."""
            try:
                return {
                    "author_name": self.user_config.author.name,
                    "author_email": self.user_config.author.email,
                    "preferred_behaviors": self.user_config.layout.preferred_behaviors,
                }
            except Exception:
                return {
                    "author_name": "Unknown User",
                    "author_email": "",
                    "preferred_behaviors": ["kp", "mt", "lt"],
                }

        def get_user_preferences(self) -> dict[str, Any]:
            """Get user preferences dictionary."""
            try:
                return {
                    "enable_sleep": self.user_config.firmware.enable_sleep,
                    "sleep_timeout_ms": self.user_config.firmware.sleep_timeout,
                    "max_bt_connections": self.user_config.bluetooth.max_connections,
                    "max_bt_paired": self.user_config.bluetooth.max_paired,
                    "usb_boot_mode": self.user_config.usb.boot_mode,
                    "rgb_on_start": self.user_config.rgb.on_start,
                    "code_indent_size": self.user_config.editor.indent_size,
                    "use_tabs": self.user_config.editor.use_tabs,
                    "max_line_length": self.user_config.editor.max_line_length,
                    "line_ending": self.user_config.editor.line_ending,
                    "insert_final_newline": self.user_config.editor.insert_final_newline,
                    "trim_trailing_whitespace": self.user_config.editor.trim_trailing_whitespace,
                    "align_bindings": self.user_config.layout.align_bindings,
                    "layer_comments": self.user_config.layout.layer_comments,
                    "group_behaviors": self.user_config.layout.group_behaviors,
                    "advanced_kconfig": self.user_config.advanced.kconfig,
                }
            except Exception:
                # Fallback to defaults
                return {
                    "enable_sleep": True,
                    "sleep_timeout_ms": 900000,
                    "max_bt_connections": 5,
                    "max_bt_paired": 5,
                    "usb_boot_mode": False,
                    "rgb_on_start": True,
                    "code_indent_size": 4,
                    "use_tabs": False,
                    "max_line_length": 120,
                    "line_ending": "unix",
                    "insert_final_newline": True,
                    "trim_trailing_whitespace": True,
                    "align_bindings": True,
                    "layer_comments": "block",
                    "group_behaviors": True,
                    "advanced_kconfig": {},
                }

        def get_build_timestamp(self) -> str:
            """Get build timestamp."""
            from datetime import datetime

            return datetime.now().isoformat() + "Z"

        def get_app_version(self) -> str:
            """Get application version."""
            try:
                import glovebox

                return getattr(glovebox, "__version__", "unknown")
            except Exception:
                return "unknown"

    return GloveboxSettingsService(user_config)
