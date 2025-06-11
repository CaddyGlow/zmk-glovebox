"""Environment variable manager for compilation strategies."""

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from glovebox.config.compile_methods import CompilationConfig
from glovebox.core.errors import GloveboxError


if TYPE_CHECKING:
    from glovebox.models.docker import DockerUserContext


logger = logging.getLogger(__name__)


class EnvironmentManagerError(GloveboxError):
    """Error in environment management."""


class EnvironmentManager:
    """Manage environment variable configuration for compilation.

    Handles environment template expansion, variable validation,
    and Docker environment setup for various compilation strategies.
    """

    def __init__(self) -> None:
        """Initialize environment manager."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def prepare_environment(
        self,
        config: CompilationConfig,
        **context: Any,
    ) -> dict[str, str]:
        """Prepare environment variables for compilation.

        Expands environment templates with provided context and
        merges with base environment configuration.

        Args:
            config: Compilation configuration with environment templates
            **context: Additional context for template expansion

        Returns:
            dict[str, str]: Environment variables for Docker container

        Raises:
            EnvironmentManagerError: If environment preparation fails
        """
        try:
            self.logger.debug("Preparing environment for compilation")

            # Start with base environment template
            environment = dict(config.environment_template)

            # Build template context
            template_context = self._build_template_context(**context)

            # Expand environment variables
            expanded_env = {}
            for key, value in environment.items():
                expanded_value = self._expand_environment_variable(
                    key, value, template_context
                )
                expanded_env[key] = expanded_value

            # Add system environment variables if requested
            if hasattr(config, "inherit_system_env") and config.inherit_system_env:
                system_env = self._get_system_environment()
                # System env has lower priority than explicit config
                for key, value in system_env.items():
                    if key not in expanded_env:
                        expanded_env[key] = value

            self.logger.info("Prepared %d environment variables", len(expanded_env))
            return expanded_env

        except Exception as e:
            msg = f"Failed to prepare environment: {e}"
            self.logger.error(msg)
            raise EnvironmentManagerError(msg) from e

    def _build_template_context(self, **context: Any) -> dict[str, str]:
        """Build template context for environment variable expansion.

        Args:
            **context: Context variables for template expansion

        Returns:
            dict[str, str]: Template context for expansion
        """
        template_context = {
            # System information
            "user": os.getenv("USER", "unknown"),
            "home": os.getenv("HOME", "/home/unknown"),
            "pwd": str(Path.cwd()),
            # Docker user context for volume permissions
            "uid": str(self._get_current_uid()),
            "gid": str(self._get_current_gid()),
            "docker_user": f"{self._get_current_uid()}:{self._get_current_gid()}",
            # Common ZMK environment variables
            "zmk_config": os.getenv("ZMK_CONFIG", ""),
            "zephyr_base": os.getenv("ZEPHYR_BASE", ""),
            # Build information
            "jobs": str(os.cpu_count() or 1),
            "build_type": "Release",
        }

        # Add provided context
        for key, value in context.items():
            if isinstance(value, str | int | float | bool) or hasattr(value, "__str__"):
                template_context[key] = str(value)

        self.logger.debug(
            "Built template context with %d variables", len(template_context)
        )
        return template_context

    def _expand_environment_variable(
        self, key: str, value: str | Any, context: dict[str, str]
    ) -> str:
        """Expand environment variable template with context.

        Args:
            key: Environment variable name
            value: Environment variable template value
            context: Template context variables

        Returns:
            str: Expanded environment variable value

        Raises:
            EnvironmentManagerError: If template expansion fails
        """
        if not isinstance(value, str):
            return str(value)

        import re

        try:
            # First expand environment variables (${VAR} format)
            env_pattern = r"\$\{([^}]+)\}"

            def expand_env_var(match: Any) -> str:
                env_var = match.group(1)
                return os.getenv(env_var, "")

            expanded = re.sub(env_pattern, expand_env_var, value)

            # Then expand template variables ({var} format)
            expanded = expanded.format(**context)

            self.logger.debug("Expanded %s: %s -> %s", key, value, expanded)
            return expanded

        except KeyError as e:
            raise EnvironmentManagerError(
                f"Missing template variable for environment '{key}={value}': {e}"
            ) from e
        except Exception as e:
            raise EnvironmentManagerError(
                f"Failed to expand environment variable '{key}={value}': {e}"
            ) from e

    def _get_system_environment(self) -> dict[str, str]:
        """Get relevant system environment variables.

        Returns:
            dict[str, str]: Filtered system environment variables
        """
        # Environment variables safe to pass to Docker containers
        safe_env_vars = [
            "HOME",
            "USER",
            "LANG",
            "LC_ALL",
            "TZ",
            "ZMK_CONFIG",
            "ZEPHYR_BASE",
            "WEST_CONFIG_LOCAL",
        ]

        system_env = {}
        for var in safe_env_vars:
            value = os.getenv(var)
            if value is not None:
                system_env[var] = value

        self.logger.debug("Retrieved %d system environment variables", len(system_env))
        return system_env

    def prepare_docker_environment(
        self,
        config: CompilationConfig,
        user_context: "DockerUserContext | None" = None,
        user_mapping_enabled: bool = False,
        **context: Any,
    ) -> dict[str, str]:
        """Prepare environment variables specifically for Docker containers.

        Args:
            config: Compilation configuration with environment templates
            user_context: Docker user context with home directory settings
            user_mapping_enabled: Whether Docker user mapping is enabled (fallback)
            **context: Additional context for template expansion

        Returns:
            dict[str, str]: Environment variables optimized for Docker containers
        """
        # Start with regular environment preparation
        environment = self.prepare_environment(config, **context)

        # Configure home directory based on user context or fallback
        if user_context and user_context.should_use_user_mapping():
            # Use custom home directory from user context
            home_env = user_context.get_home_environment()
            environment.update(home_env)

            self.logger.debug(
                "Set HOME=%s from user context (%s)",
                user_context.container_home_dir,
                user_context.detection_source,
            )
        elif user_mapping_enabled:
            # Fallback to /tmp if user mapping enabled but no context provided
            environment["HOME"] = "/tmp"
            self.logger.debug(
                "Set HOME=/tmp for Docker user mapping compatibility (fallback)"
            )

        return environment

    def prepare_docker_environment_with_context(
        self,
        config: CompilationConfig,
        user_context: "DockerUserContext",
        **context: Any,
    ) -> dict[str, str]:
        """Prepare Docker environment with user context (convenience method).

        Args:
            config: Compilation configuration with environment templates
            user_context: Docker user context with home directory settings
            **context: Additional context for template expansion

        Returns:
            dict[str, str]: Environment variables optimized for Docker containers
        """
        return self.prepare_docker_environment(
            config=config, user_context=user_context, **context
        )

    def _get_current_uid(self) -> int:
        """Get current user ID with fallback.

        Returns:
            int: Current user ID, or -1 if unavailable
        """
        try:
            return os.getuid()
        except AttributeError:
            # Windows doesn't have getuid()
            self.logger.debug("getuid() not available on this platform")
            return -1
        except Exception as e:
            self.logger.warning("Failed to get UID: %s", e)
            return -1

    def _get_current_gid(self) -> int:
        """Get current group ID with fallback.

        Returns:
            int: Current group ID, or -1 if unavailable
        """
        try:
            return os.getgid()
        except AttributeError:
            # Windows doesn't have getgid()
            self.logger.debug("getgid() not available on this platform")
            return -1
        except Exception as e:
            self.logger.warning("Failed to get GID: %s", e)
            return -1

    def validate_environment_templates(
        self, environment_template: dict[str, Any]
    ) -> bool:
        """Validate environment variable templates.

        Args:
            environment_template: Environment template dictionary

        Returns:
            bool: True if all templates are valid

        Raises:
            EnvironmentManagerError: If any template is invalid
        """
        import re

        for key, value in environment_template.items():
            if not isinstance(key, str) or not key.strip():
                raise EnvironmentManagerError(
                    f"Invalid environment variable name: {key}"
                )

            if not isinstance(value, str):
                continue  # Non-string values are valid

            # Check for template variable syntax
            if "{" in value and "}" in value:
                variables = re.findall(r"\{([^}]+)\}", value)
                self.logger.debug("Environment %s uses variables: %s", key, variables)

            # Check for environment variable expansion syntax
            if "${" in value and "}" in value:
                env_vars = re.findall(r"\$\{([^}]+)\}", value)
                self.logger.debug("Environment %s expands variables: %s", key, env_vars)

        return True

    def get_build_environment_defaults(self) -> dict[str, str]:
        """Get default build environment variables.

        Returns:
            dict[str, str]: Default environment variables for builds
        """
        return {
            "JOBS": str(os.cpu_count() or 1),
            "BUILD_TYPE": "Release",
            "CMAKE_BUILD_PARALLEL_LEVEL": str(os.cpu_count() or 1),
            "MAKEFLAGS": f"-j{os.cpu_count() or 1}",
        }


def create_environment_manager() -> EnvironmentManager:
    """Create environment manager instance.

    Returns:
        EnvironmentManager: New environment manager
    """
    return EnvironmentManager()
