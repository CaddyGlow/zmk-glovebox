"""Compilation configuration builder for CLI commands."""

import logging
from typing import TYPE_CHECKING

from glovebox.cli.helpers.docker_config import DockerConfigBuilder
from glovebox.cli.strategies.base import CompilationParams
from glovebox.cli.strategies.factory import create_strategy_for_profile
from glovebox.config.compile_methods import DockerCompilationConfig


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile

logger = logging.getLogger(__name__)


class CompilationConfigBuilder:
    """Builder for compilation configurations."""

    def build(
        self,
        params: CompilationParams,
        keyboard_profile: "KeyboardProfile",
        strategy_name: str | None = None,
    ) -> DockerCompilationConfig:
        """Build compilation configuration.

        Args:
            params: Compilation parameters from CLI
            keyboard_profile: Keyboard profile
            strategy_name: Compilation strategy name (optional, auto-detect if None)

        Returns:
            Compilation configuration
        """
        # Get strategy - either explicit or auto-detect
        if strategy_name:
            from glovebox.cli.strategies.factory import create_strategy_by_name

            strategy = create_strategy_by_name(strategy_name)
        else:
            strategy = create_strategy_for_profile(keyboard_profile)

        logger.debug("Using compilation strategy: %s", strategy.name)

        # Build base config from strategy
        config = strategy.build_config(params, keyboard_profile)

        # Build Docker user configuration
        docker_config = DockerConfigBuilder.build_from_params(
            strategy=strategy.name,
            docker_uid=params.docker_uid,
            docker_gid=params.docker_gid,
            docker_username=params.docker_username,
            docker_home=params.docker_home,
            docker_container_home=params.docker_container_home,
            no_docker_user_mapping=params.no_docker_user_mapping,
        )

        # Apply Docker config (override whatever the strategy set)
        config.docker_user = docker_config

        # Apply workspace settings if supported
        self._apply_workspace_settings(config, params)

        logger.debug("Final compilation config: %r", config)
        return config

    def _apply_workspace_settings(
        self,
        config: DockerCompilationConfig,
        params: CompilationParams,
    ) -> None:
        """Apply workspace-related settings to config.

        Args:
            config: Configuration to modify
            params: Compilation parameters
        """
        # Apply workspace preservation settings if config supports them
        if hasattr(config, "cleanup_workspace"):
            config.cleanup_workspace = not params.preserve_workspace
            logger.debug("Set cleanup_workspace=%s", config.cleanup_workspace)

        if hasattr(config, "preserve_on_failure"):
            config.preserve_on_failure = (
                params.preserve_workspace and not params.force_cleanup
            )
            logger.debug("Set preserve_on_failure=%s", config.preserve_on_failure)
