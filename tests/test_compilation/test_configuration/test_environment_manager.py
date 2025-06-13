"""Test EnvironmentManager class."""

import os
from unittest.mock import Mock, patch

import pytest

from glovebox.compilation.configuration.environment_manager import (
    EnvironmentManager,
    EnvironmentManagerError,
    create_environment_manager,
)
from glovebox.config.compile_methods import DockerCompilationConfig


class TestEnvironmentManager:
    """Test EnvironmentManager functionality."""

    def setup_method(self):
        """Set up test instance."""
        self.manager = EnvironmentManager()

    def test_initialization(self):
        """Test manager initialization."""
        assert hasattr(self.manager, "logger")

    def test_create_environment_manager(self):
        """Test factory function."""
        manager = create_environment_manager()
        assert isinstance(manager, EnvironmentManager)

    def test_prepare_environment_basic(self):
        """Test basic environment preparation."""
        config = Mock(spec=DockerCompilationConfig)
        config.environment_template = {
            "JOBS": "4",
            "BUILD_TYPE": "Release",
        }

        result = self.manager.prepare_environment(config)

        assert isinstance(result, dict)
        assert result["JOBS"] == "4"
        assert result["BUILD_TYPE"] == "Release"

    def test_prepare_environment_with_templates(self):
        """Test environment preparation with template expansion."""
        config = Mock(spec=DockerCompilationConfig)
        config.environment_template = {
            "JOBS": "{jobs}",
            "USER_NAME": "{user}",
            "BUILD_DIR": "{build_dir}",
        }

        result = self.manager.prepare_environment(
            config, user="testuser", build_dir="/build"
        )

        assert result["USER_NAME"] == "testuser"
        assert result["BUILD_DIR"] == "/build"
        # JOBS should be expanded to CPU count
        assert result["JOBS"].isdigit()

    def test_prepare_environment_with_env_var_expansion(self):
        """Test environment variable expansion in templates."""
        config = Mock(spec=DockerCompilationConfig)
        config.environment_template = {
            "ZMK_CONFIG": "${ZMK_CONFIG}",
            "HOME_DIR": "${HOME}",
        }

        with patch.dict(
            os.environ, {"ZMK_CONFIG": "/test/config", "HOME": "/home/test"}
        ):
            result = self.manager.prepare_environment(config)

        assert result["ZMK_CONFIG"] == "/test/config"
        assert result["HOME_DIR"] == "/home/test"

    def test_prepare_environment_missing_env_var(self):
        """Test missing environment variable expansion."""
        config = Mock(spec=DockerCompilationConfig)
        config.environment_template = {
            "MISSING_VAR": "${NONEXISTENT_VAR}",
        }

        result = self.manager.prepare_environment(config)
        # Missing env vars should expand to empty string
        assert result["MISSING_VAR"] == ""

    def test_expand_environment_variable_simple(self):
        """Test simple environment variable expansion."""
        context = {"user": "testuser", "jobs": "8"}

        result = self.manager._expand_environment_variable("USER", "{user}", context)
        assert result == "testuser"

    def test_expand_environment_variable_complex(self):
        """Test complex environment variable with multiple expansions."""
        context = {"user": "testuser", "build_type": "Debug"}

        with patch.dict(os.environ, {"HOME": "/home/test"}):
            result = self.manager._expand_environment_variable(
                "BUILD_PATH", "${HOME}/builds/{user}/{build_type}", context
            )

        assert result == "/home/test/builds/testuser/Debug"

    def test_expand_environment_variable_missing_template(self):
        """Test error handling for missing template variables."""
        context = {"user": "testuser"}

        with pytest.raises(EnvironmentManagerError, match="Missing template variable"):
            self.manager._expand_environment_variable("TEST", "{missing_var}", context)

    def test_build_template_context(self):
        """Test template context building."""
        context = self.manager._build_template_context(
            custom_var="custom", number_var=42, bool_var=True
        )

        # Check default context variables
        assert "user" in context
        assert "home" in context
        assert "pwd" in context
        assert "jobs" in context
        assert "build_type" in context

        # Check custom variables
        assert context["custom_var"] == "custom"
        assert context["number_var"] == "42"
        assert context["bool_var"] == "True"

    @patch.dict(os.environ, {"ZMK_CONFIG": "/test/zmk", "ZEPHYR_BASE": "/test/zephyr"})
    def test_build_template_context_zmk_vars(self):
        """Test ZMK-specific environment variables in context."""
        context = self.manager._build_template_context()

        assert context["zmk_config"] == "/test/zmk"
        assert context["zephyr_base"] == "/test/zephyr"

    def test_get_system_environment(self):
        """Test system environment variable retrieval."""
        with patch.dict(
            os.environ,
            {
                "HOME": "/home/test",
                "USER": "testuser",
                "ZMK_CONFIG": "/zmk/config",
                "PRIVATE_VAR": "secret",  # Should not be included
            },
        ):
            result = self.manager._get_system_environment()

        assert result["HOME"] == "/home/test"
        assert result["USER"] == "testuser"
        assert result["ZMK_CONFIG"] == "/zmk/config"
        assert "PRIVATE_VAR" not in result

    def test_get_system_environment_missing_vars(self):
        """Test system environment with missing variables."""
        # Clear environment variables
        with patch.dict(os.environ, {}, clear=True):
            result = self.manager._get_system_environment()

        # Should be empty dict when no safe vars are present
        assert isinstance(result, dict)

    def test_validate_environment_templates_valid(self):
        """Test validation of valid environment templates."""
        templates = {
            "JOBS": "4",
            "BUILD_TYPE": "Release",
            "USER_NAME": "{user}",
            "BUILD_PATH": "${HOME}/builds",
        }

        result = self.manager.validate_environment_templates(templates)
        assert result is True

    def test_validate_environment_templates_invalid_key(self):
        """Test validation fails for invalid keys."""
        templates = {
            "": "value",  # Empty key
        }

        with pytest.raises(
            EnvironmentManagerError, match="Invalid environment variable name"
        ):
            self.manager.validate_environment_templates(templates)

    def test_validate_environment_templates_with_variables(self):
        """Test validation logs template variables."""
        templates = {
            "TEMPLATE_VAR": "{user}_{build_type}",
            "ENV_VAR": "${HOME}/config",
        }

        with patch.object(self.manager.logger, "debug") as mock_debug:
            result = self.manager.validate_environment_templates(templates)
            assert result is True
            # Should log detected variables
            assert mock_debug.call_count >= 2

    def test_get_build_environment_defaults(self):
        """Test default build environment variables."""
        defaults = self.manager.get_build_environment_defaults()

        assert "JOBS" in defaults
        assert "BUILD_TYPE" in defaults
        assert "CMAKE_BUILD_PARALLEL_LEVEL" in defaults
        assert "MAKEFLAGS" in defaults

        assert defaults["BUILD_TYPE"] == "Release"
        assert defaults["JOBS"].isdigit()

    def test_prepare_environment_inherit_system(self):
        """Test inheriting system environment variables."""
        config = Mock(spec=DockerCompilationConfig)
        config.environment_template = {
            "CUSTOM_VAR": "custom_value",
        }
        config.inherit_system_env = True

        with patch.object(self.manager, "_get_system_environment") as mock_get_env:
            mock_get_env.return_value = {
                "HOME": "/home/test",
                "USER": "testuser",
            }

            result = self.manager.prepare_environment(config)

        # Custom vars should take priority
        assert result["CUSTOM_VAR"] == "custom_value"
        # System vars should be included
        assert result["HOME"] == "/home/test"
        assert result["USER"] == "testuser"

    def test_prepare_environment_no_inherit_system(self):
        """Test not inheriting system environment variables."""
        config = Mock(spec=DockerCompilationConfig)
        config.environment_template = {
            "CUSTOM_VAR": "custom_value",
        }
        # No inherit_system_env attribute

        with patch.object(self.manager, "_get_system_environment") as mock_get_env:
            mock_get_env.return_value = {
                "HOME": "/home/test",
                "USER": "testuser",
            }

            result = self.manager.prepare_environment(config)

        # Only custom vars should be present
        assert result["CUSTOM_VAR"] == "custom_value"
        assert "HOME" not in result
        assert "USER" not in result


class TestEnvironmentManagerIntegration:
    """Test EnvironmentManager integration scenarios."""

    def setup_method(self):
        """Set up test instance."""
        self.manager = EnvironmentManager()

    def test_zmk_build_environment(self):
        """Test typical ZMK build environment configuration."""
        config = Mock(spec=DockerCompilationConfig)
        config.environment_template = {
            "JOBS": "{jobs}",
            "BUILD_TYPE": "Release",
            "ZMK_CONFIG": "/workspace/config",
            "BOARD": "{board}",
            "SHIELD": "{shield}",
        }

        result = self.manager.prepare_environment(
            config, board="nice_nano_v2", shield="corne_left"
        )

        assert result["BUILD_TYPE"] == "Release"
        assert result["ZMK_CONFIG"] == "/workspace/config"
        assert result["BOARD"] == "nice_nano_v2"
        assert result["SHIELD"] == "corne_left"
        assert result["JOBS"].isdigit()

    def test_glove80_build_environment(self):
        """Test Glove80 build environment configuration."""
        config = Mock(spec=DockerCompilationConfig)
        config.environment_template = {
            "JOBS": "8",
            "BUILD_TYPE": "Release",
            "BOARD": "{board}",
            "ZMK_CONFIG": "/workspace/glove80-config",
            "RGB_UNDERGLOW": "y",
        }

        result = self.manager.prepare_environment(config, board="glove80_lh")

        assert result["BOARD"] == "glove80_lh"
        assert result["ZMK_CONFIG"] == "/workspace/glove80-config"
        assert result["RGB_UNDERGLOW"] == "y"

    def test_development_environment(self):
        """Test development environment with debugging enabled."""
        config = Mock(spec=DockerCompilationConfig)
        config.environment_template = {
            "BUILD_TYPE": "Debug",
            "CMAKE_BUILD_TYPE": "Debug",
            "VERBOSE": "1",
            "USER_HOME": "${HOME}",
            "WORKSPACE": "/workspace/{user}",
        }
        config.inherit_system_env = True

        with patch.dict(os.environ, {"HOME": "/home/developer"}):
            result = self.manager.prepare_environment(config, user="developer")

        assert result["BUILD_TYPE"] == "Debug"
        assert result["CMAKE_BUILD_TYPE"] == "Debug"
        assert result["VERBOSE"] == "1"
        assert result["USER_HOME"] == "/home/developer"
        assert result["WORKSPACE"] == "/workspace/developer"

    def test_ci_environment(self):
        """Test CI/CD environment configuration."""
        config = Mock(spec=DockerCompilationConfig)
        config.environment_template = {
            "JOBS": "{jobs}",
            "BUILD_TYPE": "Release",
            "CI": "true",
            "GITHUB_WORKSPACE": "${GITHUB_WORKSPACE}",
            "ARTIFACT_NAME": "{board}-{shield}-{timestamp}",
        }

        with patch.dict(os.environ, {"GITHUB_WORKSPACE": "/github/workspace"}):
            result = self.manager.prepare_environment(
                config,
                board="nice_nano_v2",
                shield="corne_left",
                timestamp="20240101-120000",
            )

        assert result["CI"] == "true"
        assert result["GITHUB_WORKSPACE"] == "/github/workspace"
        assert result["ARTIFACT_NAME"] == "nice_nano_v2-corne_left-20240101-120000"
