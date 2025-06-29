"""Progress coordinators for different compilation strategies."""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from glovebox.cli.progress.models import (
        ProgressContext,
        ProgressCoordinatorProtocol,
    )


def create_zmk_west_coordinator(
    context: ProgressContext,
) -> ProgressCoordinatorProtocol:
    """Create ZMK West progress coordinator."""
    from glovebox.cli.progress.coordinators.zmk_west import ZmkWestProgressCoordinator

    return ZmkWestProgressCoordinator(context)


def create_moergo_nix_coordinator(
    context: ProgressContext,
) -> ProgressCoordinatorProtocol:
    """Create MoErgo Nix progress coordinator."""
    from glovebox.cli.progress.coordinators.moergo_nix import (
        MoergoNixProgressCoordinator,
    )

    return MoergoNixProgressCoordinator(context)


def create_noop_coordinator(context: ProgressContext) -> ProgressCoordinatorProtocol:
    """Create no-op progress coordinator."""
    from glovebox.cli.progress.coordinators.noop import NoOpProgressCoordinator

    return NoOpProgressCoordinator(context)


__all__ = [
    "create_zmk_west_coordinator",
    "create_moergo_nix_coordinator",
    "create_noop_coordinator",
]
