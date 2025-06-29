"""Progress display components."""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from glovebox.cli.progress.displays.base import ProgressDisplayProtocol
    from glovebox.cli.progress.models import ProgressContext


def create_staged_display(context: ProgressContext) -> ProgressDisplayProtocol:
    """Create staged progress display."""
    from glovebox.cli.progress.displays.staged import StagedProgressDisplay

    return StagedProgressDisplay(context)


def create_simple_display(context: ProgressContext) -> ProgressDisplayProtocol:
    """Create simple progress display."""
    from glovebox.cli.progress.displays.simple import SimpleProgressDisplay

    return SimpleProgressDisplay(context)


def create_noop_display(context: ProgressContext) -> ProgressDisplayProtocol:
    """Create no-op progress display."""
    from glovebox.cli.progress.displays.noop import NoOpProgressDisplay

    return NoOpProgressDisplay(context)


__all__ = [
    "create_staged_display",
    "create_simple_display",
    "create_noop_display",
]
