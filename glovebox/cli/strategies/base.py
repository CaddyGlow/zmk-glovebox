"""Base strategy classes and protocols for firmware compilation."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol

from glovebox.cli.strategies.config_builder import CLIOverrides
from glovebox.config.compile_methods import DockerCompilationConfig
from glovebox.config.profile import KeyboardProfile


class CompilationStrategyProtocol(Protocol):
    """Protocol for compilation strategies."""

    @property
    def name(self) -> str:
        """Strategy name."""
        ...

    def supports_profile(self, profile: KeyboardProfile) -> bool:
        """Check if strategy supports the given profile."""
        ...

    def build_config(
        self, cli_overrides: CLIOverrides, profile: KeyboardProfile
    ) -> DockerCompilationConfig:
        """Build compilation configuration using YAML config + CLI overrides."""
        ...

    def get_service_name(self) -> str:
        """Get the compilation service name."""
        ...


class BaseCompilationStrategy(ABC):
    """Base implementation for compilation strategies.

    This base class now uses the new configuration-first approach where
    YAML configuration is loaded first, then CLI overrides are applied.
    """

    def __init__(self, name: str) -> None:
        """Initialize base strategy.

        Args:
            name: Strategy name
        """
        from glovebox.cli.strategies.config_builder import create_config_builder

        self._name = name
        self._config_builder = create_config_builder()

    @property
    def name(self) -> str:
        """Strategy name."""
        return self._name

    @abstractmethod
    def supports_profile(self, profile: KeyboardProfile) -> bool:
        """Check if strategy supports the given profile.

        Args:
            profile: Keyboard profile to check

        Returns:
            bool: True if strategy supports this profile
        """
        ...

    def build_config(
        self, cli_overrides: CLIOverrides, profile: KeyboardProfile
    ) -> DockerCompilationConfig:
        """Build compilation configuration using YAML config + CLI overrides.

        This method uses the new configuration builder to:
        1. Load YAML configuration from the keyboard profile
        2. Apply CLI overrides
        3. Return unified configuration object

        Args:
            cli_overrides: CLI argument overrides
            profile: Keyboard profile with YAML configuration

        Returns:
            DockerCompilationConfig: Unified configuration for compilation
        """
        return self._config_builder.build_config(
            profile=profile,
            cli_overrides=cli_overrides,
            strategy_name=self.name,
        )

    @abstractmethod
    def get_service_name(self) -> str:
        """Get the compilation service name.

        Returns:
            str: Service name for this strategy
        """
        ...
