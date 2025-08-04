"""CLI components for reusable UI elements."""

from typing import Any, Union

from glovebox.cli.components.noop_progress_context import (
    get_noop_progress_context,
    get_noop_progress_manager,
)
from glovebox.cli.components.progress_config import ProgressConfig
from glovebox.cli.components.progress_context import ProgressContext
from glovebox.cli.components.progress_display import ProgressDisplay
from glovebox.cli.components.progress_manager import ProgressManager
from glovebox.cli.helpers.theme import IconMode
from glovebox.protocols.progress_context_protocol import (
    ProgressContextProtocol,
    ProgressManagerProtocol,
)


def create_progress_display(config: ProgressConfig) -> Any:
    """Create a progress display instance.

    Args:
        config: Progress display configuration

    Returns:
        Configured ProgressDisplay instance (v1 or v2 based on config)
    """
    if config.use_v2_display:
        return ProgressDisplay(config)
    else:
        # Import v1 implementation for fallback
        from glovebox.cli.components.progress_display_v1 import (
            ProgressDisplay as ProgressDisplayV1,
        )

        return ProgressDisplayV1(config)


def create_progress_manager(
    operation_name: str,
    checkpoints: list[str],
    icon_mode: IconMode = IconMode.TEXT,
) -> ProgressManager:
    """Create a progress manager with configuration.

    Args:
        operation_name: Name of the operation being tracked
        checkpoints: List of checkpoint names in order
        icon_mode: Icon mode for visual indicators (default: ASCII)

    Returns:
        Configured ProgressManager instance
    """
    config = ProgressConfig(
        operation_name=operation_name,
        checkpoints=checkpoints,
        icon_mode=icon_mode,
    )
    return ProgressManager(config)


def create_progress_context(
    display: ProgressDisplay | None = None,
) -> ProgressContextProtocol:
    """Create a progress context, returning NoOp if no display provided.

    Args:
        display: Optional ProgressDisplay to connect to

    Returns:
        ProgressContext if display provided, otherwise NoOpProgressContext
    """
    if display is None:
        return get_noop_progress_context()
    return ProgressContext(display)


def create_compilation_progress_manager(
    operation_name: str,
    base_checkpoints: list[str],
    final_checkpoints: list[str],
    board_info: dict[str, Any],
    progress_callback: Any | None = None,
    use_moergo_fallback: bool = False,
) -> ProgressManagerProtocol:
    """Create a progress manager for compilation operations with dynamic board checkpoints.

    This factory function handles the common pattern used in compilation services
    where progress tracking depends on board configuration and includes dynamic
    checkpoints for individual board builds.

    Args:
        operation_name: Name of the compilation operation (e.g., "ZMK West Compilation")
        base_checkpoints: Initial checkpoints before board builds
        final_checkpoints: Final checkpoints after board builds
        board_info: Board information dictionary with 'board_names' and 'total_boards'
        progress_callback: Progress callback to determine if manager should be created
        use_moergo_fallback: Use MoErgo-specific fallback naming for boards (Left/Right Hand)

    Returns:
        Context manager that provides progress tracking functionality
    """
    if progress_callback is None:
        return get_noop_progress_manager()

    # Import required dependencies for progress setup
    from glovebox.cli.helpers.theme import get_icon_mode_from_config
    from glovebox.config import create_user_config

    # Get user configuration for theming
    user_config = create_user_config()
    icon_mode = get_icon_mode_from_config(user_config)

    # Build dynamic checkpoints
    checkpoints = base_checkpoints.copy()

    # Add individual board build checkpoints
    if board_info.get("board_names"):
        for board_name in board_info["board_names"]:
            checkpoints.append(f"Building {board_name}")
    else:
        # Fallback for unknown boards
        total_boards = board_info.get("total_boards", 2 if use_moergo_fallback else 1)
        for i in range(total_boards):
            if use_moergo_fallback:
                if i == 0:
                    checkpoints.append("Building Left Hand")
                elif i == 1:
                    checkpoints.append("Building Right Hand")
                else:
                    checkpoints.append(f"Building Board {i + 1}")
            else:
                checkpoints.append(f"Building Board {i + 1}")

    # Add final checkpoints
    checkpoints.extend(final_checkpoints)

    # Create and return progress manager (context manager)
    return create_progress_manager(
        operation_name=operation_name,
        checkpoints=checkpoints,
        icon_mode=icon_mode,
    )


__all__ = [
    "ProgressConfig",
    "ProgressDisplay",
    "ProgressManager",
    "ProgressContext",
    "ProgressContextProtocol",
    "ProgressManagerProtocol",
    "create_progress_display",
    "create_progress_manager",
    "create_progress_context",
    "create_compilation_progress_manager",
    "get_noop_progress_context",
    "get_noop_progress_manager",
]
