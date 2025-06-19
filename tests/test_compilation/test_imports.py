"""Test imports work correctly for compilation domain."""

import pytest


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


def test_factory_functions_exist():
    """Test that factory functions exist and work correctly."""
    from glovebox.compilation import (
        create_compilation_service,
        create_moergo_nix_service,
        create_zmk_west_service,
    )

    # ZMK config service is implemented
    zmk_service = create_zmk_west_service()
    assert zmk_service is not None

    # Moergo service is implemented
    moergo_service = create_moergo_nix_service()
    assert moergo_service is not None

    # Test compilation service factory with different strategies
    zmk_service_via_factory = create_compilation_service("zmk_config")
    assert zmk_service_via_factory is not None

    # Test that unsupported strategies raise ValueError
    with pytest.raises(
        ValueError, match="Unknown compilation strategy.*Supported strategies"
    ):
        create_compilation_service("unsupported_strategy")

    # Test that moergo strategy works
    moergo_service_via_factory = create_compilation_service("moergo")
    assert moergo_service_via_factory is not None


def test_subdomain_factory_functions():
    """Test that subdomain factory functions exist."""
    # The configuration subdomain has been removed in the refactoring
    # Test that models are still available
    from glovebox.compilation.models.build_matrix import BuildMatrix, BuildTarget

    # Test model classes exist
    assert BuildMatrix is not None
    assert BuildTarget is not None
