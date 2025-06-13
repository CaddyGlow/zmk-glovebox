"""Test imports work correctly for compilation domain."""

from collections.abc import Callable
from typing import Any, cast

import pytest


def test_compilation_domain_imports():
    """Test that compilation domain can be imported successfully."""
    from glovebox.compilation import (
        CompilationServiceProtocol,
        create_compilation_service,
        create_zmk_config_service,
    )

    # Test protocol imports
    assert CompilationServiceProtocol is not None

    # Test factory function availability
    assert callable(create_compilation_service)
    assert callable(create_zmk_config_service)


def test_protocol_imports():
    """Test that all protocol imports work correctly."""
    from glovebox.compilation.protocols import (
        CompilationServiceProtocol,
        WorkspaceManagerProtocol,
        ZmkConfigWorkspaceManagerProtocol,
    )

    # Test all protocols are available
    protocols = [
        CompilationServiceProtocol,
        WorkspaceManagerProtocol,
        ZmkConfigWorkspaceManagerProtocol,
    ]

    for protocol in protocols:
        assert protocol is not None


def test_factory_functions_exist():
    """Test that factory functions exist and work correctly."""
    from glovebox.compilation import (
        create_compilation_service,
        create_zmk_config_service,
    )

    # ZMK config service is implemented
    zmk_service = create_zmk_config_service()
    assert zmk_service is not None

    # Test compilation service factory with different strategies
    zmk_service_via_factory = create_compilation_service("zmk_config")
    assert zmk_service_via_factory is not None

    # Test that unsupported strategies raise ValueError
    with pytest.raises(
        ValueError, match="Unknown compilation strategy.*Supported strategies"
    ):
        create_compilation_service("unsupported_strategy")


def test_subdomain_factory_functions():
    """Test that subdomain factory functions exist."""
    from glovebox.compilation.configuration import (
        create_build_matrix_resolver,
        create_environment_manager,
        create_volume_manager,
    )
    from glovebox.compilation.workspace import (
        create_cache_manager,
        create_workspace_manager,
        create_zmk_config_workspace_manager,
    )

    # Test all factory functions exist
    factory_functions = [
        # Configuration
        create_build_matrix_resolver,
        create_volume_manager,
        create_environment_manager,
        # Workspace
        create_workspace_manager,
        create_zmk_config_workspace_manager,
        create_cache_manager,
    ]

    for func in factory_functions:
        assert callable(func)

    # Test implemented factory functions return actual objects
    implemented_functions = [
        create_build_matrix_resolver,
        create_volume_manager,
        create_environment_manager,
    ]

    for func in implemented_functions:
        assert func() is not None

    # Test implemented workspace factory functions return actual objects
    implemented_workspace_functions = [
        create_zmk_config_workspace_manager,
        create_cache_manager,
    ]

    for func in implemented_workspace_functions:
        factory_func = cast(Callable[[], Any], func)
        result = factory_func()
        assert result is not None

    # Test abstract workspace manager raises NotImplementedError
    with pytest.raises(NotImplementedError):
        create_workspace_manager()
