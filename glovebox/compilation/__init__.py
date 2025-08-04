"""Compilation domain for ZMK firmware build strategies.

This domain provides comprehensive compilation services following the
GitHub Actions workflow pattern for ZMK config builds.
"""

from typing import TYPE_CHECKING, Any

# Defer import to avoid circular dependency
from glovebox.compilation.protocols.compilation_protocols import (
    CompilationServiceProtocol,
)


if TYPE_CHECKING:
    from glovebox.compilation.cache import (
        CompilationBuildCacheService,
        ZmkWorkspaceCacheService,
    )
    from glovebox.config.user_config import UserConfig
    from glovebox.core.cache.cache_manager import CacheManager
    from glovebox.core.metrics.session_metrics import SessionMetrics
    from glovebox.protocols import DockerAdapterProtocol, FileAdapterProtocol


# Simple factory function for direct service selection
def create_compilation_service(
    method_type: str,
    user_config: "UserConfig",
    docker_adapter: "DockerAdapterProtocol",
    file_adapter: "FileAdapterProtocol",
    cache_manager: "CacheManager | None",
    session_metrics: "SessionMetrics",
    workspace_cache_service: Any | None = None,
    build_cache_service: Any | None = None,
    progress_callback: Any | None = None,
) -> CompilationServiceProtocol:
    """Create compilation service for specified method type with explicit dependencies.

    Args:
        method_type: Compilation method type
        user_config: UserConfig instance
        docker_adapter: Required DockerAdapter instance
        file_adapter: Required FileAdapter instance
        cache_manager: Cache manager instance (required for zmk_config method, optional for others)
        workspace_cache_service: Workspace cache service (required for zmk_config method)
        build_cache_service: Build cache service (required for zmk_config method)
        session_metrics: Optional SessionMetrics instance for metrics integration
        progress_callback: Optional progress callback for compilation progress tracking

    Returns:
        CompilationServiceProtocol: Configured compilation service

    Raises:
        ValueError: If method type is not supported or required dependencies are missing
    """
    if method_type == "zmk_config":
        if cache_manager is None:
            raise ValueError("ZMK config method requires cache_manager")
        if workspace_cache_service is None or build_cache_service is None:
            raise ValueError(
                "ZMK config method requires workspace_cache_service and build_cache_service"
            )
        return create_zmk_west_service(
            user_config=user_config,
            docker_adapter=docker_adapter,
            file_adapter=file_adapter,
            cache_manager=cache_manager,
            session_metrics=session_metrics,
            workspace_cache_service=workspace_cache_service,
            build_cache_service=build_cache_service,
            default_progress_callback=progress_callback,
        )
    elif method_type == "moergo":
        return create_moergo_nix_service(
            docker_adapter=docker_adapter,
            file_adapter=file_adapter,
            session_metrics=session_metrics,
            default_progress_callback=progress_callback,
        )
    else:
        raise ValueError(
            f"Unknown compilation method type: {method_type}. Supported method types: zmk_config, moergo"
        )


def create_zmk_west_service(
    user_config: "UserConfig",
    docker_adapter: "DockerAdapterProtocol",
    file_adapter: "FileAdapterProtocol",
    cache_manager: "CacheManager",
    session_metrics: "SessionMetrics",
    workspace_cache_service: "ZmkWorkspaceCacheService",
    build_cache_service: "CompilationBuildCacheService",
    default_progress_callback: Any | None = None,
) -> CompilationServiceProtocol:
    """Create ZMK with West compilation service with explicit dependencies.

    Args:
        user_config: UserConfig instance
        docker_adapter: Required DockerAdapter instance
        file_adapter: Required FileAdapter instance
        cache_manager: Required cache manager instance
        workspace_cache_service: Required workspace cache service
        build_cache_service: Required build cache service
        session_metrics: Optional SessionMetrics instance for metrics integration
        default_progress_callback: Optional default progress callback for compilation tracking

    Returns:
        CompilationServiceProtocol: ZMK config compilation service
    """
    from glovebox.compilation.services.zmk_west_service import (
        create_zmk_west_service,
    )

    return create_zmk_west_service(
        docker_adapter=docker_adapter,
        user_config=user_config,
        file_adapter=file_adapter,
        cache_manager=cache_manager,
        workspace_cache_service=workspace_cache_service,
        build_cache_service=build_cache_service,
        session_metrics=session_metrics,
        default_progress_callback=default_progress_callback,
    )


def create_moergo_nix_service(
    docker_adapter: "DockerAdapterProtocol",
    file_adapter: "FileAdapterProtocol",
    session_metrics: "SessionMetrics",
    default_progress_callback: Any | None = None,
) -> CompilationServiceProtocol:
    r"""Create simplified Moergo compilation service with explicit dependencies.

    Args:
        docker_adapter: Required DockerAdapter instance
        file_adapter: Required FileAdapter instance
        session_metrics: SessionMetrics instance for metrics integration
        default_progress_callback: Optional default progress callback for compilation tracking

    Returns:
        CompilationServiceProtocol: Moergo compilation service
    """
    from glovebox.compilation.services.moergo_nix_service import (
        create_moergo_nix_service,
    )

    return create_moergo_nix_service(
        docker_adapter, file_adapter, session_metrics, default_progress_callback
    )


__all__ = [
    # Protocols
    "CompilationServiceProtocol",
    # Factory functions
    "create_compilation_service",
    "create_zmk_west_service",
    "create_moergo_nix_service",
    # Additional services can be imported directly from their modules
    # "create_workspace_setup_service",
    # "create_zmk_cache_service",
]
