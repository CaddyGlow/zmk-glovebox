"""File copy service with strategy-based optimization."""

import logging
from pathlib import Path
from typing import Any

from .enums import CopyStrategy
from .models import CopyResult
from .protocols import CopyStrategyProtocol
from .strategies import (
    BaselineCopyStrategy,
    BufferedCopyStrategy,
    ParallelCopyStrategy,
    PipelineCopyStrategy,
    SendfileCopyStrategy,
)


class FileCopyService:
    """Service for optimized file copying with pluggable strategies."""

    def __init__(
        self,
        default_strategy: CopyStrategy = CopyStrategy.BASELINE,
        buffer_size_kb: int = 1024,
        max_workers: int = 4,
    ):
        """Initialize the file copy service.

        Args:
            default_strategy: Strategy to use by default
            buffer_size_kb: Buffer size for buffered strategy
            max_workers: Number of worker threads for parallel strategy
        """
        self.default_strategy = default_strategy
        self.buffer_size_kb = buffer_size_kb
        self.max_workers = max_workers
        self.logger = logging.getLogger(__name__)

        # Initialize available strategies
        self._strategies: dict[CopyStrategy, CopyStrategyProtocol] = {}
        self._register_strategies()

    def _register_strategies(self) -> None:
        """Register available copy strategies."""
        # Always available baseline
        self._strategies[CopyStrategy.BASELINE] = BaselineCopyStrategy()

        # Buffered strategy with configured buffer size
        self._strategies[CopyStrategy.BUFFERED] = BufferedCopyStrategy(
            self.buffer_size_kb
        )

        # Parallel strategy with configured workers and buffer
        self._strategies[CopyStrategy.PARALLEL] = ParallelCopyStrategy(
            self.max_workers, self.buffer_size_kb
        )

        # Pipeline strategy with component-level parallelism
        self._strategies[CopyStrategy.PIPELINE] = PipelineCopyStrategy(
            max_workers=3,  # Conservative for component copying
            size_calculation_workers=4,
        )

        # Sendfile strategy if available
        sendfile_strategy = SendfileCopyStrategy()
        missing_prereqs = sendfile_strategy.validate_prerequisites()
        if not missing_prereqs:
            self._strategies[CopyStrategy.SENDFILE] = sendfile_strategy
        else:
            self.logger.debug("Sendfile strategy not available: %s", missing_prereqs)

    def copy_directory(
        self,
        src: Path,
        dst: Path,
        exclude_git: bool = False,
        strategy: CopyStrategy | None = None,
        **options: Any,
    ) -> CopyResult:
        """Copy directory using specified strategy.

        Args:
            src: Source directory path
            dst: Destination directory path
            exclude_git: Whether to exclude .git directories
            strategy: Specific strategy to use (overrides default)
            **options: Strategy-specific options

        Returns:
            CopyResult with operation details
        """
        selected_strategy = strategy or self.default_strategy

        # Get strategy instance
        copy_strategy = self._strategies.get(selected_strategy)
        if not copy_strategy:
            self.logger.warning(
                "Strategy '%s' not available, falling back to baseline",
                selected_strategy.value,
            )
            copy_strategy = self._strategies[CopyStrategy.BASELINE]

        # Validate strategy prerequisites
        missing = copy_strategy.validate_prerequisites()
        if missing:
            self.logger.warning(
                "Strategy '%s' missing prerequisites: %s, falling back to baseline",
                copy_strategy.name,
                missing,
            )
            copy_strategy = self._strategies[CopyStrategy.BASELINE]

        self.logger.debug(
            "Using copy strategy '%s' for %s -> %s", copy_strategy.name, src, dst
        )

        # Execute copy operation
        return copy_strategy.copy_directory(src, dst, exclude_git, **options)

    def list_available_strategies(self) -> list[CopyStrategy]:
        """Get list of available strategies.

        Returns:
            List of available copy strategies
        """
        return list(self._strategies.keys())

    def get_strategy_info(self, strategy: CopyStrategy) -> dict[str, Any] | None:
        """Get information about a specific strategy.

        Args:
            strategy: Strategy to inspect

        Returns:
            Dictionary with strategy information or None if not found
        """
        strategy_impl = self._strategies.get(strategy)
        if not strategy_impl:
            return None

        return {
            "name": strategy_impl.name,
            "description": strategy_impl.description,
            "prerequisites": strategy_impl.validate_prerequisites(),
            "available": len(strategy_impl.validate_prerequisites()) == 0,
        }


def create_copy_service(user_config: Any | None = None) -> FileCopyService:
    """Factory function to create file copy service from user configuration.

    Args:
        user_config: User configuration object with copy settings

    Returns:
        Configured FileCopyService instance
    """
    # Extract copy settings from user config if available
    if user_config and hasattr(user_config, "_config"):
        config = user_config._config
        try:
            strategy_str = getattr(config, "copy_strategy", "baseline")
            buffer_size_kb = getattr(config, "copy_buffer_size_kb", 1024)
            max_workers = getattr(config, "copy_max_workers", 4)

            # Convert string strategy to enum
            try:
                default_strategy = CopyStrategy(strategy_str)
            except ValueError:
                default_strategy = CopyStrategy.BASELINE

            # Ensure we have valid values (not Mock objects)
            if not isinstance(buffer_size_kb, int):
                buffer_size_kb = 1024
            if not isinstance(max_workers, int):
                max_workers = 4
        except (AttributeError, TypeError):
            default_strategy = CopyStrategy.BASELINE
            buffer_size_kb = 1024
            max_workers = 4
    else:
        default_strategy = CopyStrategy.BASELINE
        buffer_size_kb = 1024
        max_workers = 4

    return FileCopyService(
        default_strategy=default_strategy,
        buffer_size_kb=buffer_size_kb,
        max_workers=max_workers,
    )
