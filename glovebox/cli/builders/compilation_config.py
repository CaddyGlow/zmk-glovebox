"""Compilation configuration builder for CLI commands."""

import logging
from typing import TYPE_CHECKING

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

        # Build config from strategy (includes Docker config with strategy-specific defaults)
        config = strategy.build_config(params, keyboard_profile)

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
        # Use defaults when params are None
        preserve_workspace = (
            params.preserve_workspace
            if params.preserve_workspace is not None
            else False
        )
        force_cleanup = (
            params.force_cleanup if params.force_cleanup is not None else False
        )

        if hasattr(config, "cleanup_workspace"):
            config.cleanup_workspace = not preserve_workspace or force_cleanup
            logger.debug("Set cleanup_workspace=%s", config.cleanup_workspace)

        if hasattr(config, "preserve_on_failure"):
            config.preserve_on_failure = preserve_workspace and not force_cleanup
            logger.debug("Set preserve_on_failure=%s", config.preserve_on_failure)
