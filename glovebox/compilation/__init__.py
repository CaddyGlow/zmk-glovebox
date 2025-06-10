"""Compilation domain for ZMK firmware build strategies.

This domain provides comprehensive compilation services following the
GitHub Actions workflow pattern for ZMK config builds.
"""

from glovebox.compilation.protocols.compilation_protocols import (
    CompilationCoordinatorProtocol,
    CompilationServiceProtocol,
)


# Factory functions for main compilation services
def create_compilation_coordinator() -> CompilationCoordinatorProtocol:
    """Create main compilation coordinator with all dependencies.

    Returns:
        CompilationCoordinatorProtocol: Configured compilation coordinator
    """
    # Implementation will be added in Phase 4
    # from glovebox.compilation.services.compilation_coordinator import CompilationCoordinator
    # return CompilationCoordinator()
    raise NotImplementedError("CompilationCoordinator will be implemented in Phase 4")


def create_zmk_config_service() -> CompilationServiceProtocol:
    """Create ZMK config compilation service.

    Returns:
        CompilationServiceProtocol: ZMK config compilation service
    """
    from glovebox.compilation.services.zmk_config_service import (
        create_zmk_config_service as _create_service,
    )

    return _create_service()


def create_west_service() -> CompilationServiceProtocol:
    """Create west compilation service.

    Returns:
        CompilationServiceProtocol: West compilation service
    """
    from glovebox.compilation.services.west_compilation_service import (
        create_west_compilation_service as _create_service,
    )

    return _create_service()


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
    "CompilationCoordinatorProtocol",
    "CompilationServiceProtocol",
    # Factory functions
    "create_compilation_coordinator",
    "create_zmk_config_service",
    "create_west_service",
    "create_cmake_service",
]
