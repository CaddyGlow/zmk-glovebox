"""Strategy factory for firmware compilation strategies."""

import logging
from typing import TYPE_CHECKING

from glovebox.cli.strategies.base import CompilationStrategyProtocol
from glovebox.cli.strategies.moergo import create_moergo_strategy
from glovebox.cli.strategies.zmk_config import create_zmk_config_strategy
from glovebox.core.errors import GloveboxError


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile

logger = logging.getLogger(__name__)


class StrategyNotFoundError(GloveboxError):
    """Raised when no suitable compilation strategy is found."""

    def __init__(self, profile_name: str, available_strategies: list[str]) -> None:
        """Initialize strategy not found error.
        
        Args:
            profile_name: Name of the profile that couldn't be matched
            available_strategies: List of available strategy names
        """
        super().__init__(
            f"No compilation strategy found for profile '{profile_name}'. "
            f"Available strategies: {', '.join(available_strategies)}"
        )
        self.profile_name = profile_name
        self.available_strategies = available_strategies


class CompilationStrategyFactory:
    """Factory for creating compilation strategies."""

    def __init__(self) -> None:
        """Initialize strategy factory."""
        self._strategies: dict[str, CompilationStrategyProtocol] = {}
        self._register_default_strategies()

    def _register_default_strategies(self) -> None:
        """Register default compilation strategies."""
        # Register ZMK config strategy
        zmk_strategy = create_zmk_config_strategy()
        self._strategies[zmk_strategy.name] = zmk_strategy

        # Register Moergo strategy
        moergo_strategy = create_moergo_strategy()
        self._strategies[moergo_strategy.name] = moergo_strategy

        logger.debug("Registered %d compilation strategies", len(self._strategies))

    def get_strategy_for_profile(self, profile: "KeyboardProfile") -> CompilationStrategyProtocol:
        """Get the best compilation strategy for a keyboard profile.
        
        Args:
            profile: Keyboard profile to match
            
        Returns:
            CompilationStrategyProtocol: Matching compilation strategy
            
        Raises:
            StrategyNotFoundError: If no strategy supports the profile
        """
        # Find strategies that support this profile
        supporting_strategies = [
            strategy for strategy in self._strategies.values()
            if strategy.supports_profile(profile)
        ]

        if not supporting_strategies:
            profile_name = getattr(profile, 'keyboard_name', 'unknown')
            raise StrategyNotFoundError(
                profile_name,
                list(self._strategies.keys())
            )

        # For now, return the first supporting strategy
        # In the future, we could add priority-based selection
        strategy = supporting_strategies[0]
        logger.debug(
            "Selected strategy '%s' for profile '%s'",
            strategy.name,
            getattr(profile, 'keyboard_name', 'unknown')
        )

        return strategy

    def get_strategy_by_name(self, name: str) -> CompilationStrategyProtocol:
        """Get a compilation strategy by name.
        
        Args:
            name: Strategy name
            
        Returns:
            CompilationStrategyProtocol: Named compilation strategy
            
        Raises:
            StrategyNotFoundError: If strategy name is not found
        """
        if name not in self._strategies:
            raise StrategyNotFoundError(name, list(self._strategies.keys()))

        return self._strategies[name]

    def list_strategies(self) -> list[str]:
        """List all available strategy names.
        
        Returns:
            list[str]: Available strategy names
        """
        return list(self._strategies.keys())

    def register_strategy(self, strategy: CompilationStrategyProtocol) -> None:
        """Register a custom compilation strategy.
        
        Args:
            strategy: Strategy to register
        """
        self._strategies[strategy.name] = strategy
        logger.debug("Registered custom strategy: %s", strategy.name)


# Global factory instance
_strategy_factory: CompilationStrategyFactory | None = None


def get_strategy_factory() -> CompilationStrategyFactory:
    """Get the global strategy factory instance.
    
    Returns:
        CompilationStrategyFactory: Global factory instance
    """
    global _strategy_factory
    if _strategy_factory is None:
        _strategy_factory = CompilationStrategyFactory()
    return _strategy_factory


def create_strategy_for_profile(profile: "KeyboardProfile") -> CompilationStrategyProtocol:
    """Create compilation strategy for a keyboard profile.
    
    Args:
        profile: Keyboard profile
        
    Returns:
        CompilationStrategyProtocol: Matching compilation strategy
    """
    factory = get_strategy_factory()
    return factory.get_strategy_for_profile(profile)


def create_strategy_by_name(name: str) -> CompilationStrategyProtocol:
    """Create compilation strategy by name.
    
    Args:
        name: Strategy name
        
    Returns:
        CompilationStrategyProtocol: Named compilation strategy
    """
    factory = get_strategy_factory()
    return factory.get_strategy_by_name(name)


def list_available_strategies() -> list[str]:
    """List all available compilation strategies.
    
    Returns:
        list[str]: Available strategy names
    """
    factory = get_strategy_factory()
    return factory.list_strategies()
