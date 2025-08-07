"""Factory for creating glovebox-specific zmk-layout providers."""

import logging
from typing import Optional

from glovebox.models.base import GloveboxBaseModel

from .configuration_provider import GloveboxConfigurationProvider
from .logger import GloveboxLogger
from .template_provider import GloveboxTemplateProvider


class LayoutProviders(GloveboxBaseModel):
    """Container for layout providers."""

    def __init__(self, configuration, template, logger):
        super().__init__()
        self.configuration = configuration
        self.template = template
        self.logger = logger


def create_glovebox_providers(
    keyboard_id: str | None = None, services: dict | None = None
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
            # For Phase 1, we'll use mock services as the real service layer
            # will be integrated in Phase 2 of the migration
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
    keyboard_config: dict | None = None,
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
def _create_mock_keyboard_service():
    """Create mock keyboard service for development."""

    class MockKeyboardProfile:
        def __init__(self):
            self.display_name = "Test Keyboard"
            self.manufacturer = "Test Manufacturer"
            self.variant = "default"
            self.hardware_revision = "1.0"
            self.layout_name = "test_layout"
            self.target_zmk_version = "3.5.0"

            # Mock layout configuration
            self.layout_configuration = MockLayoutConfig()

        def get_available_behaviors(self):
            return [MockBehavior()]

        def has_oled(self):
            return False

        def has_rotary_encoder(self):
            return False

        def has_rgb(self):
            return False

        def is_split(self):
            return True

        def supports_wireless(self):
            return True

        def supports_usb(self):
            return True

        def get_custom_includes(self):
            return []

    class MockLayoutConfig:
        def __init__(self):
            self.total_keys = 42
            self.rows = 4
            self.columns = 6
            self.thumb_key_count = 6

    class MockBehavior:
        def __init__(self):
            self.zmk_name = "kp"
            self.behavior_type = "key-press"
            self.parameter_names = ["keycode"]
            self.description = "Key press behavior"
            self.zmk_compatible = "zmk,behavior-key-press"

        def get_validation_rules(self):
            return {"required_params": 1}

    class MockKeyboardService:
        def get_profile(self, keyboard_id):
            return MockKeyboardProfile()

    return MockKeyboardService()


def _create_mock_template_service():
    """Create mock template service for development."""

    class MockTemplateService:
        def render_string(self, template: str, context: dict) -> str:
            # Simple template rendering for testing
            result = template
            for key, value in context.items():
                result = result.replace(f"{{{{{key}}}}}", str(value))
            return result

        def render_file(self, template_path: str, context: dict) -> str:
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

        def get_supported_features(self) -> list:
            return ["basic_templating", "context_variables"]

    return MockTemplateService()


def _create_mock_logging_service():
    """Create mock logging service for development."""

    class MockLoggingService:
        def get_logger(self, component: str):
            return logging.getLogger(f"glovebox.{component}")

    return MockLoggingService()


def _create_mock_settings_service():
    """Create mock settings service for development."""

    class MockSettingsService:
        def get_active_keyboard_id(self):
            return "test_keyboard"

        def get(self, key: str, default=None):
            defaults = {
                "max_layers": 32,
                "max_combos": 64,
                "max_macros": 32,
                "max_hold_taps": 16,
                "max_tap_dances": 8,
            }
            return defaults.get(key, default)

        def get_user_settings(self):
            return {
                "author_name": "Test User",
                "author_email": "test@example.com",
                "preferred_behaviors": ["kp", "mt", "lt"],
            }

        def get_user_preferences(self):
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

        def get_build_timestamp(self):
            return "2024-01-01T00:00:00Z"

        def get_app_version(self):
            return "1.0.0"

    return MockSettingsService()


def _create_test_keyboard_service(config: dict | None = None):
    """Create test keyboard service with specific config."""
    service = _create_mock_keyboard_service()
    if config:
        # Apply any test-specific configuration overrides
        pass
    return service


def _create_test_template_service(engine: str = "simple"):
    """Create test template service."""
    return _create_mock_template_service()


def _create_test_logging_service(log_level: str = "INFO"):
    """Create test logging service."""
    return _create_mock_logging_service()


def _create_test_settings_service():
    """Create test settings service."""
    return _create_mock_settings_service()
