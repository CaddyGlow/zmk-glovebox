# glovebox/cli/components/unified_progress_coordinator.py (REFACTORED)
"""Unified progress coordinator for all compilation phases.

This module now provides backward compatibility while delegating to the new
refactored base class and specialized implementations.
"""

import logging
from collections.abc import Callable
from typing import Any

from glovebox.cli.components.progress_coordinators import (
    ZmkWestProgressCoordinator,
    create_progress_coordinator,
)
from glovebox.protocols.progress_coordinator_protocol import ProgressCoordinatorProtocol
from glovebox.core.file_operations import (
    CompilationProgress,
    CompilationProgressCallback,
)


logger = logging.getLogger(__name__)


# Backward compatibility alias
class UnifiedCompilationProgressCoordinator(ZmkWestProgressCoordinator):
    """Coordinates progress updates from multiple compilation phases into a single TUI display.

    This class provides backward compatibility with the original implementation
    while delegating to the new ZmkWestProgressCoordinator base class.
    """
    pass


def create_unified_progress_coordinator(
    tui_callback: CompilationProgressCallback | None,
    total_boards: int = 1,
    board_names: list[str] | None = None,
    total_repositories: int = 39,
    strategy: str = "zmk_west",
) -> ProgressCoordinatorProtocol:
    """Factory function to create appropriate progress coordinator.

    Args:
        tui_callback: TUI callback function, or None for no-op coordinator
        total_boards: Total number of boards to compile
        board_names: List of board names for progress tracking
        total_repositories: Total number of repositories to download
        strategy: Compilation strategy ('zmk_west', 'moergo_nix', etc.)

    Returns:
        Strategy-specific progress coordinator implementing ProgressCoordinatorProtocol
    """
    return create_progress_coordinator(
        strategy=strategy,
        tui_callback=tui_callback,
        total_boards=total_boards,
        board_names=board_names,
        total_repositories=total_repositories,
    )
