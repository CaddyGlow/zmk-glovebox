"""Compilation domain for ZMK firmware build strategies.

This domain provides comprehensive compilation services following the
GitHub Actions workflow pattern for ZMK config builds.
"""

# Defer import to avoid circular dependency
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
        return create_zmk_west_service()
    elif strategy == "moergo":
        return create_moergo_nix_service()
    else:
        raise ValueError(
            f"Unknown compilation strategy: {strategy}. Supported strategies: zmk_config, moergo"
        )


def create_zmk_west_service() -> CompilationServiceProtocol:
    """Create ZMK with West compilation service using shared cache coordination.

    Returns:
        CompilationServiceProtocol: ZMK config compilation service
    """
    from glovebox.adapters import create_docker_adapter
    from glovebox.compilation.services.zmk_west_service import (
        create_zmk_west_service,
    )
    from glovebox.config.user_config import create_user_config

    docker_adapter = create_docker_adapter()
    user_config = create_user_config()

    # Use shared cache coordination via domain-specific factory
    from glovebox.compilation.cache import create_compilation_cache_service

    cache, workspace_service, build_service = create_compilation_cache_service(
        user_config
    )

    return create_zmk_west_service(
        docker_adapter=docker_adapter,
        user_config=user_config,
        cache_manager=cache,
        workspace_cache_service=workspace_service,
        build_cache_service=build_service,
    )


def create_moergo_nix_service() -> CompilationServiceProtocol:
    r"""Create simplified Moergo compilat\ion service.

    Returns:
        CompilationServiceProtocol: Moergo compilation service
    """
    from glovebox.adapters import create_docker_adapter
    from glovebox.compilation.services.moergo_nix_service import (
        create_moergo_nix_service,
    )

    docker_adapter = create_docker_adapter()
    return create_moergo_nix_service(docker_adapter)


__all__ = [
    # Protocols
    "CompilationServiceProtocol",
    # Factory functions
    "create_compilation_service",
    "create_zmk_west_service",
    "create_moergo_nix_service",
]
