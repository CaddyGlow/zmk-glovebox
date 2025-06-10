"""Build configuration management for compilation strategies."""

from glovebox.compilation.configuration.build_matrix_resolver import (
    BuildMatrixResolver,
    create_build_matrix_resolver,
)


# Additional configuration managers will be added in Phase 2
# from glovebox.compilation.configuration.volume_manager import VolumeManager
# from glovebox.compilation.configuration.environment_manager import EnvironmentManager


def create_volume_manager() -> None:
    """Create volume manager.

    Returns:
        VolumeManager: Volume manager instance
    """
    # Implementation will be added in Phase 2
    pass


def create_environment_manager() -> None:
    """Create environment manager.

    Returns:
        EnvironmentManager: Environment manager instance
    """
    # Implementation will be added in Phase 2
    pass


__all__: list[str] = [
    # Configuration managers
    "BuildMatrixResolver",
    # Additional managers (to be added)
    # "VolumeManager",
    # "EnvironmentManager",
    # Factory functions
    "create_build_matrix_resolver",
    "create_volume_manager",
    "create_environment_manager",
]
