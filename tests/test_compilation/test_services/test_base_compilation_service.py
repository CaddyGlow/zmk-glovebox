"""Test BaseCompilationService class."""

from unittest.mock import Mock, patch

import pytest

from glovebox.compilation.services.base_compilation_service import (
    BaseCompilationService,
)
from glovebox.config.compile_methods import CompilationConfig
from glovebox.firmware.models import BuildResult


class TestBaseCompilationService:
    """Test BaseCompilationService functionality."""

    def setup_method(self):
        """Set up test instance."""
        self.service = BaseCompilationService("test_service", "1.0.0")

    def test_initialization(self):
        """Test service initialization."""
        assert self.service.service_name == "test_service"
        assert self.service.service_version == "1.0.0"
        assert hasattr(self.service, "logger")

    def test_validate_configuration_valid(self):
        """Test configuration validation with valid config."""
        config = Mock(spec=CompilationConfig)
        config.image = "zmkfirmware/zmk-build-arm:stable"
        config.build_strategy = "west"

        result = self.service.validate_configuration(config)

        assert result is True

    def test_validate_configuration_missing_image(self):
        """Test configuration validation with missing image."""
        config = Mock(spec=CompilationConfig)
        config.image = ""
        config.build_strategy = "west"

        with patch.object(self.service.logger, "error") as mock_logger:
            result = self.service.validate_configuration(config)

        assert result is False
        mock_logger.assert_called_once_with("Docker image not specified")

    def test_validate_configuration_missing_strategy(self):
        """Test configuration validation with missing build strategy."""
        config = Mock(spec=CompilationConfig)
        config.image = "zmkfirmware/zmk-build-arm:stable"
        config.build_strategy = ""

        with patch.object(self.service.logger, "error") as mock_logger:
            result = self.service.validate_configuration(config)

        assert result is False
        mock_logger.assert_called_once_with("Build strategy not specified")

    def test_validate_configuration_both_missing(self):
        """Test configuration validation with both image and strategy missing."""
        config = Mock(spec=CompilationConfig)
        config.image = ""
        config.build_strategy = ""

        with patch.object(self.service.logger, "error") as mock_logger:
            result = self.service.validate_configuration(config)

        assert result is False
        # Should call error twice
        assert mock_logger.call_count == 2

    @patch("multiprocessing.cpu_count", return_value=8)
    def test_prepare_build_environment_defaults(self, mock_cpu_count):
        """Test build environment preparation with defaults."""
        config = Mock(spec=CompilationConfig)
        config.environment_template = {}

        with patch.object(self.service.logger, "debug") as mock_logger:
            result = self.service.prepare_build_environment(config)

        expected = {
            "JOBS": "8",
            "BUILD_TYPE": "Release",
        }
        assert result == expected
        mock_logger.assert_called_once_with(
            "Prepared base build environment: %s", expected
        )

    @patch("multiprocessing.cpu_count", return_value=4)
    def test_prepare_build_environment_custom_template(self, mock_cpu_count):
        """Test build environment preparation with custom template."""
        config = Mock(spec=CompilationConfig)
        config.environment_template = {
            "CUSTOM_VAR": "custom_value",
            "BUILD_TYPE": "Debug",  # Should not be overridden
        }

        result = self.service.prepare_build_environment(config)

        expected = {
            "CUSTOM_VAR": "custom_value",
            "BUILD_TYPE": "Debug",  # Custom value preserved
            "JOBS": "4",  # Default added
        }
        assert result == expected

    @patch("multiprocessing.cpu_count", return_value=2)
    def test_prepare_build_environment_partial_override(self, mock_cpu_count):
        """Test build environment with partial custom values."""
        config = Mock(spec=CompilationConfig)
        config.environment_template = {
            "JOBS": "12",  # Custom job count
            "ZMK_CONFIG": "/workspace/config",
        }

        result = self.service.prepare_build_environment(config)

        expected = {
            "JOBS": "12",  # Custom value preserved
            "ZMK_CONFIG": "/workspace/config",
            "BUILD_TYPE": "Release",  # Default added
        }
        assert result == expected

    def test_compile_not_implemented(self):
        """Test that compile method raises NotImplementedError."""
        from pathlib import Path

        keymap_file = Path("/test/keymap.keymap")
        config_file = Path("/test/config.conf")
        output_dir = Path("/test/output")
        config = Mock(spec=CompilationConfig)

        with pytest.raises(
            NotImplementedError, match="Subclasses must implement compile method"
        ):
            self.service.compile(keymap_file, config_file, output_dir, config)

    def test_check_available_default(self):
        """Test default availability check."""
        result = self.service.check_available()
        assert result is True

    def test_service_inheritance(self):
        """Test that BaseCompilationService inherits from BaseService."""
        from glovebox.services.base_service import BaseService

        assert isinstance(self.service, BaseService)

    def test_environment_template_mutation_protection(self):
        """Test that environment template is not mutated by service."""
        original_template = {"ORIGINAL": "value"}
        config = Mock(spec=CompilationConfig)
        config.environment_template = original_template.copy()

        # Prepare environment multiple times
        result1 = self.service.prepare_build_environment(config)
        result2 = self.service.prepare_build_environment(config)

        # Original template should be unchanged
        assert config.environment_template == original_template
        # Results should be identical
        assert result1 == result2
        # Results should contain original value plus defaults
        assert result1["ORIGINAL"] == "value"
        assert "JOBS" in result1
        assert "BUILD_TYPE" in result1


class ConcreteTestService(BaseCompilationService):
    """Concrete implementation for testing abstract methods."""

    def compile(self, keymap_file, config_file, output_dir, config):
        """Concrete implementation for testing."""
        return BuildResult(success=True)

    def check_available(self):
        """Test availability check override."""
        return False


class TestConcreteService:
    """Test concrete service implementation."""

    def setup_method(self):
        """Set up concrete test service."""
        self.service = ConcreteTestService("concrete_test", "2.0.0")

    def test_concrete_compile(self):
        """Test concrete compile implementation."""
        from pathlib import Path

        keymap_file = Path("/test/keymap.keymap")
        config_file = Path("/test/config.conf")
        output_dir = Path("/test/output")
        config = Mock(spec=CompilationConfig)

        result = self.service.compile(keymap_file, config_file, output_dir, config)

        assert isinstance(result, BuildResult)
        assert result.success is True

    def test_concrete_check_available(self):
        """Test concrete availability check override."""
        result = self.service.check_available()
        assert result is False

    def test_inherited_methods_work(self):
        """Test that inherited methods work correctly."""
        config = Mock(spec=CompilationConfig)
        config.image = "test:latest"
        config.build_strategy = "test"
        config.environment_template = {}

        # Should use inherited validation
        validation_result = self.service.validate_configuration(config)
        assert validation_result is True

        # Should use inherited environment preparation
        env_result = self.service.prepare_build_environment(config)
        assert "JOBS" in env_result
        assert "BUILD_TYPE" in env_result
