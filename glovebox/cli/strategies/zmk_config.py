"""ZMK config compilation strategy implementation."""

import logging
from typing import TYPE_CHECKING

from glovebox.cli.strategies.base import BaseCompilationStrategy
from glovebox.cli.strategies.config_builder import CLIOverrides
from glovebox.config.compile_methods import DockerCompilationConfig


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile

logger = logging.getLogger(__name__)


class ZmkConfigStrategy(BaseCompilationStrategy):
    """ZMK config compilation strategy.

    This strategy now uses the new configuration-first approach where
    YAML configuration is loaded first, then CLI overrides are applied
    through the unified configuration builder.
    """

    def __init__(self) -> None:
        """Initialize ZMK config strategy."""
        super().__init__("zmk_config")

    def supports_profile(self, profile: "KeyboardProfile") -> bool:
        """Check if strategy supports the given profile.

        ZMK config strategy supports most keyboard profiles except those
        specifically requiring Moergo builds.

        Args:
            profile: Keyboard profile to check

        Returns:
            bool: True if strategy supports this profile
        """
        # ZMK config supports most profiles except Moergo-specific ones
        return not self._is_moergo_profile(profile)

    def get_service_name(self) -> str:
        """Get the compilation service name.

        Returns:
            str: Service name for ZMK config strategy
        """
        return "zmk_config_compilation"

    def _is_moergo_profile(self, profile: "KeyboardProfile") -> bool:
        """Check if profile is a Moergo-specific profile.

        Args:
            profile: Keyboard profile to check

        Returns:
            bool: True if profile requires Moergo compilation
        """
        # Check for Moergo-specific indicators
        keyboard_name = getattr(profile, "keyboard_name", "").lower()
        return "moergo" in keyboard_name or "glove80" in keyboard_name


def create_zmk_config_strategy() -> ZmkConfigStrategy:
    """Create ZMK config compilation strategy.

    Returns:
        ZmkConfigStrategy: Configured strategy instance
    """
    return ZmkConfigStrategy()
