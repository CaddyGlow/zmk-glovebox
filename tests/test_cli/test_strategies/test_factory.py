"""Tests for strategy factory."""

from unittest.mock import Mock

import pytest

from glovebox.cli.strategies.base import CompilationStrategyProtocol
from glovebox.cli.strategies.factory import (
    CompilationStrategyFactory,
    StrategyNotFoundError,
    create_strategy_by_name,
    create_strategy_for_profile,
    get_strategy_factory,
    list_available_strategies,
)
from glovebox.cli.strategies.moergo import MoergoStrategy
from glovebox.cli.strategies.zmk_config import ZmkConfigStrategy
from glovebox.config.profile import KeyboardProfile


class TestCompilationStrategyFactory:
    """Test compilation strategy factory."""

    def test_factory_initialization(self):
        """Test factory initializes with default strategies."""
        factory = CompilationStrategyFactory()
        strategies = factory.list_strategies()

        assert "zmk_config" in strategies
        assert "moergo" in strategies
        assert len(strategies) == 2

    def test_get_strategy_for_zmk_profile(self):
        """Test getting strategy for ZMK profile."""
        factory = CompilationStrategyFactory()

        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "planck"

        strategy = factory.get_strategy_for_profile(profile)

        assert isinstance(strategy, ZmkConfigStrategy)
        assert strategy.name == "zmk_config"

    def test_get_strategy_for_moergo_profile(self):
        """Test getting strategy for Moergo profile."""
        factory = CompilationStrategyFactory()

        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "glove80"

        strategy = factory.get_strategy_for_profile(profile)

        assert isinstance(strategy, MoergoStrategy)
        assert strategy.name == "moergo"

    def test_get_strategy_for_unsupported_profile(self):
        """Test that ZMK config strategy acts as fallback for unsupported profiles."""
        factory = CompilationStrategyFactory()

        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "unsupported_keyboard"

        # ZMK config strategy should act as fallback for unknown keyboards
        strategy = factory.get_strategy_for_profile(profile)
        assert isinstance(strategy, ZmkConfigStrategy)
        assert strategy.name == "zmk_config"

    def test_no_strategy_supports_profile(self):
        """Test error when no strategy supports profile (mock scenario)."""
        # Create factory with no strategies
        factory = CompilationStrategyFactory()
        factory._strategies.clear()  # Remove all strategies

        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "any_keyboard"

        with pytest.raises(StrategyNotFoundError) as exc_info:
            factory.get_strategy_for_profile(profile)

        assert "any_keyboard" in str(exc_info.value)

    def test_get_strategy_by_name_zmk(self):
        """Test getting strategy by name - ZMK."""
        factory = CompilationStrategyFactory()

        strategy = factory.get_strategy_by_name("zmk_config")

        assert isinstance(strategy, ZmkConfigStrategy)
        assert strategy.name == "zmk_config"

    def test_get_strategy_by_name_moergo(self):
        """Test getting strategy by name - Moergo."""
        factory = CompilationStrategyFactory()

        strategy = factory.get_strategy_by_name("moergo")

        assert isinstance(strategy, MoergoStrategy)
        assert strategy.name == "moergo"

    def test_get_strategy_by_invalid_name(self):
        """Test error when strategy name not found."""
        factory = CompilationStrategyFactory()

        with pytest.raises(StrategyNotFoundError) as exc_info:
            factory.get_strategy_by_name("invalid_strategy")

        assert "invalid_strategy" in str(exc_info.value)

    def test_register_custom_strategy(self):
        """Test registering a custom strategy."""
        factory = CompilationStrategyFactory()

        # Create mock custom strategy
        custom_strategy = Mock(spec=CompilationStrategyProtocol)
        custom_strategy.name = "custom"

        factory.register_strategy(custom_strategy)

        strategies = factory.list_strategies()
        assert "custom" in strategies

        retrieved_strategy = factory.get_strategy_by_name("custom")
        assert retrieved_strategy is custom_strategy

    def test_list_strategies(self):
        """Test listing all strategies."""
        factory = CompilationStrategyFactory()

        strategies = factory.list_strategies()

        assert isinstance(strategies, list)
        assert "zmk_config" in strategies
        assert "moergo" in strategies


class TestGlobalFactoryFunctions:
    """Test global factory convenience functions."""

    def test_get_strategy_factory_singleton(self):
        """Test global factory is singleton."""
        factory1 = get_strategy_factory()
        factory2 = get_strategy_factory()

        assert factory1 is factory2

    def test_create_strategy_for_profile(self):
        """Test creating strategy for profile."""
        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "planck"

        strategy = create_strategy_for_profile(profile)

        assert isinstance(strategy, ZmkConfigStrategy)

    def test_create_strategy_by_name(self):
        """Test creating strategy by name."""
        strategy = create_strategy_by_name("moergo")

        assert isinstance(strategy, MoergoStrategy)

    def test_list_available_strategies(self):
        """Test listing available strategies."""
        strategies = list_available_strategies()

        assert "zmk_config" in strategies
        assert "moergo" in strategies


class TestStrategyNotFoundError:
    """Test StrategyNotFoundError exception."""

    def test_error_message_format(self):
        """Test error message formatting."""
        error = StrategyNotFoundError("test_profile", ["strategy1", "strategy2"])

        assert "test_profile" in str(error)
        assert "strategy1" in str(error)
        assert "strategy2" in str(error)

    def test_error_attributes(self):
        """Test error attributes."""
        error = StrategyNotFoundError("test_profile", ["strategy1", "strategy2"])

        assert error.profile_name == "test_profile"
        assert error.available_strategies == ["strategy1", "strategy2"]
