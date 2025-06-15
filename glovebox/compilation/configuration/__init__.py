"""Build configuration management for compilation strategies."""

from glovebox.compilation.configuration.build_matrix_resolver import (
    BuildMatrixResolver,
    create_build_matrix_resolver,
)


__all__: list[str] = [
    # Configuration managers
    "BuildMatrixResolver",
    # Factory functions
    "create_build_matrix_resolver",
]
