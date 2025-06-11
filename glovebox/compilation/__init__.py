"""Compilation domain for ZMK firmware build strategies.

This domain provides comprehensive compilation services following the
GitHub Actions workflow pattern for ZMK config builds.
"""

from glovebox.compilation.protocols.compilation_protocols import (
    CompilationServiceProtocol,
)


# Simple factory function for direct service selection
def create_compilation_service(strategy: str) -> CompilationServiceProtocol:
    """Create compilation service for specified strategy.

    Args:
        strategy: Compilation strategy ("zmk_config" or "west")

    Returns:
        CompilationServiceProtocol: Configured compilation service

    Raises:
        ValueError: If strategy is not supported
    """
    if strategy == "zmk_config":
        return create_zmk_config_service()
    elif strategy == "west":
        return create_west_service()
    else:
        raise ValueError(f"Unknown compilation strategy: {strategy}")


def create_zmk_config_service() -> CompilationServiceProtocol:
    """Create ZMK config compilation service with generic cache.

    Returns:
        CompilationServiceProtocol: ZMK config compilation service
    """
    from glovebox.compilation.cache import create_compilation_cache
    from glovebox.compilation.services.zmk_config_service import (
        create_zmk_config_service as _create_service,
    )

    # Create compilation cache for service
    compilation_cache = create_compilation_cache()

    return _create_service(compilation_cache=compilation_cache)


def create_west_service() -> CompilationServiceProtocol:
    """Create west compilation service with generic cache.

    Returns:
        CompilationServiceProtocol: West compilation service
    """
    from glovebox.compilation.cache import create_compilation_cache
    from glovebox.compilation.services.west_compilation_service import (
        create_west_service as _create_service,
    )

    # Create compilation cache for service
    compilation_cache = create_compilation_cache()

    return _create_service(compilation_cache=compilation_cache)


def create_cmake_service() -> CompilationServiceProtocol:
    """Create CMake compilation service.

    Returns:
        CompilationServiceProtocol: CMake compilation service
    """
    # Implementation will be added in Phase 4
    # from glovebox.compilation.services.cmake_compilation_service import CMakeCompilationService
    # return CMakeCompilationService()
    raise NotImplementedError("CMakeCompilationService will be implemented in Phase 4")


__all__ = [
    # Protocols
    "CompilationServiceProtocol",
    # Factory functions
    "create_compilation_service",
    "create_zmk_config_service",
    "create_west_service",
    "create_cmake_service",
]
