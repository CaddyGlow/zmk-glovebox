"""Simplified compilation services for different build strategies."""

from glovebox.compilation.services.moergo_simple import (
    MoergoSimpleService,
    create_moergo_simple_service,
)
from glovebox.compilation.services.zmk_config_simple import (
    ZmkConfigSimpleService,
    create_zmk_config_simple_service,
)


__all__: list[str] = [
    "ZmkConfigSimpleService",
    "create_zmk_config_simple_service",
    "MoergoSimpleService",
    "create_moergo_simple_service",
]
