"""Build configuration management for compilation strategies."""

from glovebox.compilation.configuration.build_matrix_resolver import (
    BuildMatrixResolver,
    create_build_matrix_resolver,
)
from glovebox.compilation.configuration.environment_manager import (
    EnvironmentManager,
    create_environment_manager,
)
from glovebox.compilation.configuration.user_context_manager import (
    UserContextManager,
    create_user_context_manager,
)
from glovebox.compilation.configuration.volume_manager import (
    VolumeManager,
    create_volume_manager,
)


__all__: list[str] = [
    # Configuration managers
    "BuildMatrixResolver",
    "VolumeManager",
    "EnvironmentManager",
    "UserContextManager",
    # Factory functions
    "create_build_matrix_resolver",
    "create_volume_manager",
    "create_environment_manager",
    "create_user_context_manager",
]
