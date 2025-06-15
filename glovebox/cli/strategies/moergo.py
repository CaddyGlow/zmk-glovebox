"""Moergo compilation strategy implementation."""

import logging
from typing import TYPE_CHECKING

from glovebox.cli.strategies.base import BaseCompilationStrategy
from glovebox.cli.strategies.config_builder import CLIOverrides
from glovebox.config.compile_methods import DockerCompilationConfig


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile

logger = logging.getLogger(__name__)


class MoergoStrategy(BaseCompilationStrategy):
    """Moergo compilation strategy.

    This strategy now uses the new configuration-first approach where
    YAML configuration is loaded first, then CLI overrides are applied
    through the unified configuration builder.
    """

    def __init__(self) -> None:
        """Initialize Moergo strategy."""
        super().__init__("moergo")

    def supports_profile(self, profile: "KeyboardProfile") -> bool:
        """Check if strategy supports the given profile.

        Moergo strategy only supports Moergo/Glove80 keyboards.

        Args:
            profile: Keyboard profile to check

        Returns:
            bool: True if profile is Moergo/Glove80
        """
        keyboard_name = getattr(profile, "keyboard_name", "").lower()
        return "moergo" in keyboard_name or "glove80" in keyboard_name

    def get_service_name(self) -> str:
        """Get the compilation service name.

        Returns:
            str: Service name for Moergo strategy
        """
        return "moergo_compilation"


def create_moergo_strategy() -> MoergoStrategy:
    """Create Moergo compilation strategy.

    Returns:
        MoergoStrategy: Configured strategy instance
    """
    return MoergoStrategy()
