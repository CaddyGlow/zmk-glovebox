"""Test imports work correctly for compilation domain."""

import pytest

pytestmark = [pytest.mark.docker, pytest.mark.integration]


def test_compilation_domain_imports():
    """Test that compilation domain can be imported successfully."""
    from glovebox.compilation import (
        CompilationServiceProtocol,
        create_compilation_service,
        create_moergo_nix_service,
        create_zmk_west_service,
    )

    # Test protocol imports
    assert CompilationServiceProtocol is not None

    # Test factory function availability
    assert callable(create_compilation_service)
    assert callable(create_zmk_west_service)
    assert callable(create_moergo_nix_service)


def test_protocol_imports():
    """Test that all protocol imports work correctly."""
    from glovebox.compilation.protocols import CompilationServiceProtocol

    # Test protocol is available
    assert CompilationServiceProtocol is not None


def test_factory_functions_exist(isolated_config):
    """Test that factory functions exist and work correctly."""
    from glovebox.compilation import (
        create_compilation_service,
        create_moergo_nix_service,
        create_zmk_west_service,
    )

    # ZMK config service is implemented
    from tests.test_factories import (
        create_moergo_nix_service_for_tests,
        create_zmk_west_service_for_tests,
    )

    zmk_service = create_zmk_west_service_for_tests(user_config=isolated_config)
    assert zmk_service is not None

    # Moergo service is implemented
    moergo_service = create_moergo_nix_service_for_tests()
    assert moergo_service is not None

    # Test compilation service factory with different method types
    from glovebox.adapters import create_docker_adapter, create_file_adapter
    from glovebox.core.cache import create_default_cache
    from glovebox.core.metrics.session_metrics import SessionMetrics

    docker_adapter = create_docker_adapter()
    file_adapter = create_file_adapter()
    cache_manager = create_default_cache(tag="test")
    session_metrics = SessionMetrics(
        cache_manager=cache_manager, session_uuid="test-session"
    )

    # Test ZMK service creation (requires cache services)
    from glovebox.compilation.cache import create_compilation_cache_service

    cache_mgr, workspace_service, build_cache_service = (
        create_compilation_cache_service(isolated_config, session_metrics)
    )

    zmk_service_via_factory = create_compilation_service(
        method_type="zmk_config",
        user_config=isolated_config,
        docker_adapter=docker_adapter,
        file_adapter=file_adapter,
        cache_manager=cache_mgr,
        session_metrics=session_metrics,
        workspace_cache_service=workspace_service,
        build_cache_service=build_cache_service,
    )
    assert zmk_service_via_factory is not None

    # Test that unsupported method types raise ValueError
    with pytest.raises(
        ValueError, match="Unknown compilation method type.*Supported method types"
    ):
        create_compilation_service(
            method_type="unsupported_method_type",
            user_config=isolated_config,
            docker_adapter=docker_adapter,
            file_adapter=file_adapter,
            cache_manager=cache_manager,
            session_metrics=session_metrics,
        )

    # Test that moergo method type works
    moergo_service_via_factory = create_compilation_service(
        method_type="moergo",
        user_config=isolated_config,
        docker_adapter=docker_adapter,
        file_adapter=file_adapter,
        cache_manager=cache_manager,
        session_metrics=session_metrics,
    )
    assert moergo_service_via_factory is not None


def test_subdomain_factory_functions():
    """Test that subdomain factory functions exist."""
    # The configuration subdomain has been removed in the refactoring
    # Test that models are still available
    from glovebox.compilation.models.build_matrix import BuildMatrix, BuildTarget

    # Test model classes exist
    assert BuildMatrix is not None
    assert BuildTarget is not None
