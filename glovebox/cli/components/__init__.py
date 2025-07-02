"""CLI components for reusable UI elements."""

from glovebox.cli.components.noop_progress_context import get_noop_progress_context
from glovebox.cli.components.progress_config import ProgressConfig
from glovebox.cli.components.progress_context import ProgressContext
from glovebox.cli.components.progress_display import ProgressDisplay
from glovebox.cli.components.progress_manager import ProgressManager
from glovebox.cli.helpers.theme import IconMode
from glovebox.protocols.progress_context_protocol import ProgressContextProtocol


def create_progress_display(config: ProgressConfig) -> ProgressDisplay:
    """Create a progress display instance.

    Args:
        config: Progress display configuration

    Returns:
        Configured ProgressDisplay instance
    """
    return ProgressDisplay(config)


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
    display: ProgressDisplay | None = None
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


__all__ = [
    "ProgressConfig",
    "ProgressDisplay",
    "ProgressManager",
    "ProgressContext",
    "ProgressContextProtocol",
    "create_progress_display",
    "create_progress_manager",
    "create_progress_context",
    "get_noop_progress_context",
]
