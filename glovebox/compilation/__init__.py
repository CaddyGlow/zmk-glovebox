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
    elif strategy == "moergo":
        return create_moergo_service()
    else:
        raise ValueError(
            f"Unknown compilation strategy: {strategy}. Supported strategies: zmk_config, moergo"
        )


def create_zmk_config_service() -> CompilationServiceProtocol:
    """Create simplified ZMK config compilation service.

    Returns:
        CompilationServiceProtocol: ZMK config compilation service
    """
    from glovebox.adapters import create_docker_adapter
    from glovebox.compilation.services.zmk_config_simple import (
        create_zmk_config_simple_service,
    )

    docker_adapter = create_docker_adapter()
    return create_zmk_config_simple_service(docker_adapter)


def create_moergo_service() -> CompilationServiceProtocol:
    """Create simplified Moergo compilation service.

    Returns:
        CompilationServiceProtocol: Moergo compilation service
    """
    from glovebox.adapters import create_docker_adapter
    from glovebox.compilation.services.moergo_simple import (
        create_moergo_simple_service,
    )

    docker_adapter = create_docker_adapter()
    return create_moergo_simple_service(docker_adapter)


__all__ = [
    # Protocols
    "CompilationServiceProtocol",
    # Factory functions
    "create_compilation_service",
    "create_zmk_config_service",
    "create_moergo_service",
]
