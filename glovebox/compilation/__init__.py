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
        strategy: Compilation strategy

    Returns:
        CompilationServiceProtocol: Configured compilation service

    Raises:
        ValueError: If strategy is not supported
    """
    if strategy == "zmk_config":
        return create_zmk_config_service()
    else:
        raise ValueError(
            f"Unknown compilation strategy: {strategy}. Supported strategies: zmk_config"
        )


def create_zmk_config_service() -> CompilationServiceProtocol:
    """Create ZMK config compilation service with generic cache.

    Returns:
        CompilationServiceProtocol: ZMK config compilation service
    """
    from glovebox.adapters import create_docker_adapter
    from glovebox.compilation.cache import create_compilation_cache
    from glovebox.compilation.services.zmk_config_service import (
        create_zmk_config_service as _create_service,
    )

    # Create compilation cache for service
    compilation_cache = create_compilation_cache()

    # Create Docker adapter for service
    docker_adapter = create_docker_adapter()

    return _create_service(
        compilation_cache=compilation_cache,
        docker_adapter=docker_adapter,
    )


__all__ = [
    # Protocols
    "CompilationServiceProtocol",
    # Factory functions
    "create_compilation_service",
    "create_zmk_config_service",
]
