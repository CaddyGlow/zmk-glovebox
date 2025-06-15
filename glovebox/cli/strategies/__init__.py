"""CLI strategy modules for firmware compilation."""

from glovebox.cli.strategies.base import (
    BaseCompilationStrategy,
    CompilationStrategyProtocol,
)
from glovebox.cli.strategies.config_builder import (
    CLIOverrides,
    CompilationConfigBuilder,
    create_config_builder,
)
from glovebox.cli.strategies.factory import (
    CompilationStrategyFactory,
    StrategyNotFoundError,
    create_strategy_by_name,
    create_strategy_for_profile,
    get_strategy_factory,
    list_available_strategies,
)
from glovebox.cli.strategies.moergo import MoergoStrategy, create_moergo_strategy
from glovebox.cli.strategies.zmk_config import (
    ZmkConfigStrategy,
    create_zmk_config_strategy,
)


__all__ = [
    "BaseCompilationStrategy",
    "CompilationStrategyProtocol",
    "CLIOverrides",
    "CompilationConfigBuilder",
    "create_config_builder",
    "CompilationStrategyFactory",
    "StrategyNotFoundError",
    "create_strategy_by_name",
    "create_strategy_for_profile",
    "get_strategy_factory",
    "list_available_strategies",
    "MoergoStrategy",
    "create_moergo_strategy",
    "ZmkConfigStrategy",
    "create_zmk_config_strategy",
]
