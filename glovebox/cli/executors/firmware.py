"""Firmware command executor for CLI operations."""

import logging
from typing import TYPE_CHECKING, Any, cast

from glovebox.cli.builders.compilation_config import CompilationConfigBuilder
from glovebox.cli.strategies.base import CompilationParams
from glovebox.compilation import create_compilation_service


if TYPE_CHECKING:
    from glovebox.config.models.keyboard import CompileMethodConfigUnion
    from glovebox.config.profile import KeyboardProfile

logger = logging.getLogger(__name__)


class FirmwareExecutor:
    """Executor for firmware compilation operations."""

    def __init__(self) -> None:
        """Initialize executor."""
        self.config_builder = CompilationConfigBuilder()

    def compile(
        self,
        params: CompilationParams,
        keyboard_profile: "KeyboardProfile",
        strategy: str | None = None,
    ) -> Any:
        """Execute firmware compilation.

        Args:
            params: Compilation parameters
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
        if hasattr(params, "clear_cache") and params.clear_cache:
            logger.info("Cache clearing requested but not yet implemented")
            # TODO: Implement cache clearing in future phase

        # Build configuration using the builder
        config = self.config_builder.build(params, keyboard_profile, strategy)

        logger.debug("Built compilation config: %s", type(config).__name__)

        # Determine final strategy name for service creation
        if strategy is None:
            # If no explicit strategy, get the strategy that was used by the builder
            from glovebox.cli.strategies.factory import create_strategy_for_profile

            used_strategy = create_strategy_for_profile(keyboard_profile)
            final_strategy = used_strategy.name
        else:
            final_strategy = strategy

        # Create compilation service
        compilation_service = create_compilation_service(final_strategy)

        # Execute compilation using the service
        logger.info("Executing compilation via service")
        result = compilation_service.compile(
            keymap_file=params.keymap_file,
            config_file=params.kconfig_file,
            output_dir=params.output_dir,
            config=cast("CompileMethodConfigUnion", config),
            keyboard_profile=keyboard_profile,
        )

        logger.info(
            "Compilation completed with success=%s",
            getattr(result, "success", "unknown"),
        )
        return result
