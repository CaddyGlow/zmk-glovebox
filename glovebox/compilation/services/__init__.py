"""Compilation services for different build strategies."""

# Base service (Phase 1, Step 1.3)
from glovebox.compilation.services.base_compilation_service import (
    BaseCompilationService,
)


# Services to be added in Phase 4
# from glovebox.compilation.services.compilation_coordinator import CompilationCoordinator
# from glovebox.compilation.services.zmk_config_service import ZmkConfigCompilationService
# from glovebox.compilation.services.west_compilation_service import WestCompilationService
# from glovebox.compilation.services.cmake_compilation_service import CMakeCompilationService

__all__: list[str] = [
    # Base service (added in Phase 1, Step 1.3)
    "BaseCompilationService",
    # Coordinator service (to be added)
    # "CompilationCoordinator",
    # Strategy services (to be added)
    # "ZmkConfigCompilationService",
    # "WestCompilationService",
    # "CMakeCompilationService",
]
