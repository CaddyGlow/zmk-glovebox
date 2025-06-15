"""Firmware command executor for CLI operations."""

import logging
from typing import TYPE_CHECKING, Any, cast

from glovebox.cli.strategies import CLIOverrides
from glovebox.cli.strategies.factory import create_strategy_for_profile
from glovebox.compilation import create_compilation_service


if TYPE_CHECKING:
    from glovebox.config.models.keyboard import CompileMethodConfigUnion
    from glovebox.config.profile import KeyboardProfile

logger = logging.getLogger(__name__)


class FirmwareExecutor:
    """Executor for firmware compilation operations."""

    def __init__(self) -> None:
        """Initialize executor."""
        pass

    def compile(
        self,
        cli_overrides: CLIOverrides,
        keyboard_profile: "KeyboardProfile",
        strategy: str | None = None,
    ) -> Any:
        """Execute firmware compilation.

        Args:
            cli_overrides: CLI argument overrides
            keyboard_profile: Keyboard profile
            strategy: Compilation strategy name (optional, auto-detect if None)

        Returns:
            Compilation result
        """
        logger.info("Starting firmware compilation")
        logger.debug("Strategy: %s (auto-detect if None)", strategy)
        logger.debug(
            "Keyboard profile: %s",
            getattr(keyboard_profile, "keyboard_name", "unknown"),
        )

        # Handle cache clearing if requested
        if hasattr(cli_overrides, "clear_cache") and cli_overrides.clear_cache:
            logger.info("Cache clearing requested but not yet implemented")
            # TODO: Implement cache clearing in future phase

        # Determine strategy to use
        if strategy is None:
            # Auto-detect strategy from profile
            strategy_instance = create_strategy_for_profile(keyboard_profile)
            final_strategy = strategy_instance.name
        else:
            from glovebox.cli.strategies.factory import create_strategy_by_name

            strategy_instance = create_strategy_by_name(strategy)
            final_strategy = strategy

        logger.debug("Using compilation strategy: %s", final_strategy)

        # Build configuration using the strategy
        config = strategy_instance.build_config(cli_overrides, keyboard_profile)

        logger.debug("Built compilation config: %s", type(config).__name__)

        # Create compilation service
        compilation_service = create_compilation_service(final_strategy)

        # Execute compilation using the service
        logger.info("Executing compilation via service")
        result = compilation_service.compile(
            keymap_file=cli_overrides.keymap_file,
            config_file=cli_overrides.kconfig_file,
            output_dir=cli_overrides.output_dir,
            config=cast("CompileMethodConfigUnion", config),
            keyboard_profile=keyboard_profile,
        )

        logger.info(
            "Compilation completed with success=%s",
            getattr(result, "success", "unknown"),
        )
        return result
