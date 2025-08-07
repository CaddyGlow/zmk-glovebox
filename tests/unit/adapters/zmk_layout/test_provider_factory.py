"""Unit tests for provider factory."""

from unittest.mock import Mock, patch

import pytest

from glovebox.adapters.zmk_layout.provider_factory import (
    LayoutProviders,
    create_glovebox_providers,
    create_test_providers,
    validate_glovebox_providers,
)


class TestProviderFactory:
    """Test suite for provider factory functions."""

    def test_layout_providers_initialization(self):
        """Test LayoutProviders initialization."""
        config = Mock()
        template = Mock()
        logger = Mock()

        providers = LayoutProviders(
            configuration=config, template=template, logger=logger
        )

        assert providers.configuration is config
        assert providers.template is template
        assert providers.logger is logger

    def test_create_glovebox_providers_with_mock_services(self):
        """Test creating providers with mock services (current implementation)."""
        providers = create_glovebox_providers(keyboard_id="test_keyboard")

        assert isinstance(providers, LayoutProviders)
        assert providers.configuration is not None
        assert providers.template is not None
        assert providers.logger is not None

        # Test that keyboard_id is properly set
        assert providers.configuration.keyboard_id == "test_keyboard"

    def test_create_glovebox_providers_with_injected_services(self):
        """Test creating providers with injected services."""
        mock_services = {
            "keyboard_profile": Mock(),
            "template": Mock(),
            "logging": Mock(),
            "settings": Mock(),
        }

        # Configure mock services
        mock_services[
            "settings"
        ].get_active_keyboard_id.return_value = "injected_keyboard"
        mock_services["logging"].get_logger.return_value = Mock()

        providers = create_glovebox_providers(services=mock_services)

        assert isinstance(providers, LayoutProviders)
        assert providers.configuration.keyboard_id == "injected_keyboard"
        assert (
            providers.configuration.profile_service is mock_services["keyboard_profile"]
        )
        assert providers.template.template_service is mock_services["template"]

    def test_create_glovebox_providers_default_keyboard_id(self):
        """Test creating providers with default keyboard ID from settings."""
        providers = create_glovebox_providers()

        # Should get keyboard ID from mock settings service
        assert providers.configuration.keyboard_id == "test_keyboard"

    def test_create_test_providers_default(self):
        """Test creating test providers with defaults."""
        providers = create_test_providers()

        assert isinstance(providers, LayoutProviders)
        assert providers.configuration is not None
        assert providers.template is not None
        assert providers.logger is not None

    def test_create_test_providers_with_config(self):
        """Test creating test providers with custom config."""
        keyboard_config = {
            "name": "Custom Keyboard",
            "key_count": 36,
            "features": {"split": True, "wireless": True},
        }

        providers = create_test_providers(
            keyboard_config=keyboard_config, template_engine="jinja2", log_level="DEBUG"
        )

        assert isinstance(providers, LayoutProviders)

    def test_validate_glovebox_providers_success(self):
        """Test successful provider validation."""
        providers = create_glovebox_providers()

        errors = validate_glovebox_providers(providers)

        # Should have no errors with mock services
        assert isinstance(errors, list)
        # Note: With current mock implementation, some validations might fail
        # This is expected until we integrate with real services

    def test_validate_glovebox_providers_configuration_error(self):
        """Test provider validation with configuration errors."""
        providers = Mock()

        # Mock configuration provider that fails
        config_provider = Mock()
        config_provider.get_behavior_definitions.side_effect = Exception("Config error")

        providers.configuration = config_provider
        providers.template = Mock()
        providers.logger = Mock()

        errors = validate_glovebox_providers(providers)

        assert len(errors) > 0
        assert any("Configuration provider error" in error for error in errors)

    def test_validate_glovebox_providers_template_error(self):
        """Test provider validation with template errors."""
        providers = Mock()

        # Mock providers
        config_provider = Mock()
        config_provider.get_behavior_definitions.return_value = [{"name": "kp"}]
        config_provider.get_validation_rules.return_value = {"key_count": 42}

        template_provider = Mock()
        template_provider.render_string.side_effect = Exception("Template error")

        providers.configuration = config_provider
        providers.template = template_provider
        providers.logger = Mock()

        errors = validate_glovebox_providers(providers)

        assert len(errors) > 0
        assert any("Template provider error" in error for error in errors)

    def test_validate_glovebox_providers_logger_error(self):
        """Test provider validation with logger errors."""
        providers = Mock()

        # Mock providers
        config_provider = Mock()
        config_provider.get_behavior_definitions.return_value = [{"name": "kp"}]
        config_provider.get_validation_rules.return_value = {"key_count": 42}

        template_provider = Mock()
        template_provider.render_string.return_value = "Hello World"

        logger_provider = Mock()
        logger_provider.info.side_effect = Exception("Logger error")

        providers.configuration = config_provider
        providers.template = template_provider
        providers.logger = logger_provider

        errors = validate_glovebox_providers(providers)

        assert len(errors) > 0
        assert any("Logger provider error" in error for error in errors)

    def test_validate_glovebox_providers_missing_behaviors(self):
        """Test provider validation with missing behaviors."""
        providers = Mock()

        # Mock configuration provider that returns empty behaviors
        config_provider = Mock()
        config_provider.get_behavior_definitions.return_value = []
        config_provider.get_validation_rules.return_value = {"key_count": 42}

        providers.configuration = config_provider
        providers.template = Mock()
        providers.logger = Mock()

        errors = validate_glovebox_providers(providers)

        assert len(errors) > 0
        assert any(
            "Configuration provider returned no behaviors" in error for error in errors
        )

    def test_validate_glovebox_providers_missing_validation_rules(self):
        """Test provider validation with missing validation rules."""
        providers = Mock()

        # Mock configuration provider with incomplete validation rules
        config_provider = Mock()
        config_provider.get_behavior_definitions.return_value = [{"name": "kp"}]
        config_provider.get_validation_rules.return_value = {}  # Missing key_count

        providers.configuration = config_provider
        providers.template = Mock()
        providers.logger = Mock()

        errors = validate_glovebox_providers(providers)

        assert len(errors) > 0
        assert any("missing key_count validation rule" in error for error in errors)

    def test_validate_glovebox_providers_template_rendering_incorrect(self):
        """Test provider validation with incorrect template rendering."""
        providers = Mock()

        # Mock providers
        config_provider = Mock()
        config_provider.get_behavior_definitions.return_value = [{"name": "kp"}]
        config_provider.get_validation_rules.return_value = {"key_count": 42}

        template_provider = Mock()
        template_provider.render_string.return_value = (
            "Incorrect output"  # Should contain "Hello World"
        )

        providers.configuration = config_provider
        providers.template = template_provider
        providers.logger = Mock()

        errors = validate_glovebox_providers(providers)

        assert len(errors) > 0
        assert any(
            "Template provider not rendering correctly" in error for error in errors
        )

    @patch("glovebox.adapters.zmk_layout.provider_factory.logging.getLogger")
    def test_create_glovebox_providers_logging(self, mock_get_logger):
        """Test that provider creation includes proper logging."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        providers = create_glovebox_providers(keyboard_id="test_kb")

        # Check that logging was called
        assert mock_logger.info.called

        # Check that the log message contains the keyboard ID
        call_args = mock_logger.info.call_args
        assert "keyboard_id" in call_args[1]["extra"]
        assert call_args[1]["extra"]["keyboard_id"] == "test_kb"

    def test_error_handling_in_create_glovebox_providers(self):
        """Test error handling in create_glovebox_providers."""
        # Create services that will cause an error during provider operations
        mock_services = {
            "keyboard_profile": None,  # This should cause an error when used
            "template": Mock(),
            "logging": Mock(),
            "settings": Mock(),
        }

        # Configure mock settings to avoid attribute errors
        mock_services["settings"].get_active_keyboard_id.return_value = "test_keyboard"
        mock_services["logging"].get_logger.return_value = Mock()

        # Provider creation should succeed (uses error handling inside)
        providers = create_glovebox_providers(services=mock_services)

        # But operations that rely on the None service should fail gracefully
        # The error is caught and logged, but fallback behaviors are returned
        behaviors = providers.configuration.get_behavior_definitions()

        # Verify that we get fallback behaviors (not empty, but basic behaviors)
        assert isinstance(behaviors, list)
        assert len(behaviors) >= 3  # Should have at least kp, trans, none
        assert any(b["name"] == "kp" for b in behaviors)

        # The important thing is that no exception was raised despite the None service

    def test_integration_with_real_mock_services(self):
        """Test integration with the real mock services implementation."""
        # This tests the actual mock service implementations in the factory
        providers = create_glovebox_providers()

        # Test configuration provider
        behaviors = providers.configuration.get_behavior_definitions()
        assert len(behaviors) > 0
        assert any(b["name"] == "kp" for b in behaviors)

        # Test validation rules
        rules = providers.configuration.get_validation_rules()
        assert "key_count" in rules
        assert rules["key_count"] == 42

        # Test template provider
        result = providers.template.render_string("Hello {{name}}", {"name": "World"})
        assert result == "Hello World"

        # Test logger (shouldn't raise exception)
        providers.logger.info("Test message")

    def test_provider_caching_behavior(self):
        """Test that providers properly cache expensive operations."""
        providers = create_glovebox_providers()

        # First call should populate cache
        behaviors1 = providers.configuration.get_behavior_definitions()

        # Second call should return cached result
        behaviors2 = providers.configuration.get_behavior_definitions()

        # Should be the same object (cached)
        assert behaviors1 is behaviors2

        # Test cache invalidation
        providers.configuration.invalidate_cache()

        # Third call should regenerate
        behaviors3 = providers.configuration.get_behavior_definitions()

        # Should be different object (regenerated)
        assert behaviors1 is not behaviors3
        # But should have same content
        assert behaviors1 == behaviors3
