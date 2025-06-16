"""Simplified compilation services for different build strategies."""

from glovebox.compilation.services.moergo_simple import (
    MoergoNixService,
    create_moergo_simple_service,
)
from glovebox.compilation.services.zmk_config_simple import (
    ZmkWestService,
    create_zmk_config_simple_service,
)


__all__: list[str] = [
    "ZmkWestService",
    "create_zmk_config_simple_service",
    "MoergoNixService",
    "create_moergo_simple_service",
]
