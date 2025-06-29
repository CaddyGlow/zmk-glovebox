"""Progress tracking subsystem for CLI commands.

This module provides factory functions for creating unified progress contexts
that can be passed through multiple phases of command execution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from glovebox.cli.progress.models import (
    ProgressContext,
    ProgressDisplayConfig,
    ProgressDisplayType,
)
from glovebox.compilation.models import CompilationProgress, CompilationState


if TYPE_CHECKING:
    from glovebox.cli.progress.coordinators.base import BaseProgressCoordinator
    from glovebox.cli.progress.displays.base import ProgressDisplayProtocol
    from glovebox.cli.progress.models import ProgressCoordinatorProtocol


def create_progress_context(
    strategy: str,
    display_enabled: bool = True,
    show_logs: bool = True,
    show_workspace_details: bool = True,
    total_stages: int | None = None,
    operation_type: str = "compilation",
    **options: Any,
) -> ProgressContext:
    """Create unified progress context for command execution.

    Args:
        strategy: Compilation strategy (zmk_west, moergo_nix, etc.)
        display_enabled: Whether to show progress display
        show_logs: Whether to show log output
        show_workspace_details: Whether to show detailed workspace operations
        total_stages: Total number of stages for staged display
        operation_type: Type of operation (compilation, flash, etc.)
        **options: Additional strategy-specific options

    Returns:
        Configured progress context
    """
    # Configure display based on parameters
    if not display_enabled:
        display_type = ProgressDisplayType.NONE
    elif total_stages:
        display_type = ProgressDisplayType.STAGED
    else:
        display_type = ProgressDisplayType.SIMPLE

    display_config = ProgressDisplayConfig(
        display_type=display_type,
        show_logs=show_logs,
        show_workspace_details=show_workspace_details,
    )

    # Initialize compilation progress
    initial_progress = CompilationProgress(
        state=CompilationState.IDLE,
        description="Initializing...",
        current_stage=0,
        total_stages=total_stages or 0,
    )

    # Create context
    context = ProgressContext(
        progress=initial_progress,
        display_config=display_config,
        strategy=strategy,
        operation_type=operation_type,
        strategy_data=options,
    )

    return context


def create_progress_coordinator(
    context: ProgressContext,
) -> ProgressCoordinatorProtocol:
    """Create strategy-specific coordinator from context.

    Args:
        context: Progress context with strategy information

    Returns:
        Strategy-specific progress coordinator
    """
    from glovebox.cli.progress.coordinators import (
        create_moergo_nix_coordinator,
        create_noop_coordinator,
        create_zmk_west_coordinator,
    )

    strategy = context.strategy.lower()

    if strategy == "zmk_west":
        return create_zmk_west_coordinator(context)
    elif strategy == "moergo_nix":
        return create_moergo_nix_coordinator(context)
    else:
        # Default to no-op for unknown strategies
        return create_noop_coordinator(context)


def create_progress_display(
    context: ProgressContext,
) -> ProgressDisplayProtocol:
    """Create display component from context.

    Args:
        context: Progress context with display configuration

    Returns:
        Configured progress display
    """
    from glovebox.cli.progress.displays import (
        create_noop_display,
        create_simple_display,
        create_staged_display,
    )

    display_type = context.display_config.display_type

    if display_type == ProgressDisplayType.SIMPLE:
        return create_simple_display(context)
    elif display_type == ProgressDisplayType.STAGED:
        return create_staged_display(context)

    # Default to no-op for NONE or unknown display types
    return create_noop_display(context)


def create_workspace_aware_callback(
    context: ProgressContext,
) -> Any:
    """Create a callback function that updates workspace progress.

    This callback can be passed to workspace services to track
    component-level operations.

    Args:
        context: Progress context to update

    Returns:
        Callback function for workspace operations
    """

    def workspace_callback(
        operation: str,
        component: str | None = None,
        progress: dict[str, Any] | None = None,
    ) -> None:
        """Update workspace progress from service callbacks."""
        from glovebox.cli.progress.models import WorkspaceOperation

        # Map string operations to enum
        op_map = {
            "cache_check": WorkspaceOperation.CACHE_CHECK,
            "cache_restore": WorkspaceOperation.CACHE_RESTORE,
            "workspace_init": WorkspaceOperation.WORKSPACE_INIT,
            "component_copy": WorkspaceOperation.COMPONENT_COPY,
            "west_init": WorkspaceOperation.WEST_INIT,
            "west_update": WorkspaceOperation.WEST_UPDATE,
            "manifest_setup": WorkspaceOperation.MANIFEST_SETUP,
        }

        workspace_op = op_map.get(operation, WorkspaceOperation.WORKSPACE_INIT)
        update_kwargs = progress or {}

        context.update_workspace(workspace_op, component, **update_kwargs)

    return workspace_callback


__all__ = [
    "create_progress_context",
    "create_progress_coordinator",
    "create_progress_display",
    "create_workspace_aware_callback",
    "ProgressContext",
    "ProgressDisplayConfig",
    "ProgressDisplayType",
]
