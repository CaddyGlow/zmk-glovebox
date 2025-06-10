"""Test imports work correctly for compilation domain."""

import pytest


def test_compilation_domain_imports():
    """Test that compilation domain can be imported successfully."""
    from glovebox.compilation import (
        CompilationCoordinatorProtocol,
        CompilationServiceProtocol,
        create_cmake_service,
        create_compilation_coordinator,
        create_west_service,
        create_zmk_config_service,
    )

    # Test protocol imports
    assert CompilationCoordinatorProtocol is not None
    assert CompilationServiceProtocol is not None

    # Test factory function availability
    assert callable(create_compilation_coordinator)
    assert callable(create_zmk_config_service)
    assert callable(create_west_service)
    assert callable(create_cmake_service)


def test_protocol_imports():
    """Test that all protocol imports work correctly."""
    from glovebox.compilation.protocols import (
        ArtifactCollectorProtocol,
        ArtifactValidatorProtocol,
        CompilationCoordinatorProtocol,
        CompilationServiceProtocol,
        FirmwareScannerProtocol,
        WestWorkspaceManagerProtocol,
        WorkspaceManagerProtocol,
        ZmkConfigWorkspaceManagerProtocol,
    )

    # Test all protocols are available
    protocols = [
        CompilationCoordinatorProtocol,
        CompilationServiceProtocol,
        WorkspaceManagerProtocol,
        WestWorkspaceManagerProtocol,
        ZmkConfigWorkspaceManagerProtocol,
        ArtifactCollectorProtocol,
        FirmwareScannerProtocol,
        ArtifactValidatorProtocol,
    ]

    for protocol in protocols:
        assert protocol is not None


def test_factory_functions_exist():
    """Test that factory functions exist but are not implemented yet."""
    from glovebox.compilation import (
        create_cmake_service,
        create_compilation_coordinator,
        create_west_service,
        create_zmk_config_service,
    )

    # These should raise NotImplementedError for now
    with pytest.raises(NotImplementedError):
        create_compilation_coordinator()

    with pytest.raises(NotImplementedError):
        create_zmk_config_service()

    with pytest.raises(NotImplementedError):
        create_west_service()

    with pytest.raises(NotImplementedError):
        create_cmake_service()


def test_subdomain_factory_functions():
    """Test that subdomain factory functions exist."""
    from glovebox.compilation.artifacts import (
        create_artifact_collector,
        create_artifact_validator,
        create_firmware_scanner,
    )
    from glovebox.compilation.configuration import (
        create_build_matrix_resolver,
        create_environment_manager,
        create_volume_manager,
    )
    from glovebox.compilation.workspace import (
        create_cache_manager,
        create_west_workspace_manager,
        create_workspace_manager,
        create_zmk_config_workspace_manager,
    )

    # Test all factory functions exist
    factory_functions = [
        # Artifacts
        create_artifact_collector,
        create_firmware_scanner,
        create_artifact_validator,
        # Configuration
        create_build_matrix_resolver,
        create_volume_manager,
        create_environment_manager,
        # Workspace
        create_workspace_manager,
        create_west_workspace_manager,
        create_zmk_config_workspace_manager,
        create_cache_manager,
    ]

    for func in factory_functions:
        assert callable(func)
        # These should return None for now (stub implementations)
        assert func() is None
