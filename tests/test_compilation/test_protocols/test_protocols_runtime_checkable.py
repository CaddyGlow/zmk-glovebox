"""Test that protocols are runtime checkable."""

import pytest


def test_compilation_protocols_runtime_checkable():
    """Test that compilation protocols are runtime checkable."""
    from glovebox.compilation.protocols.compilation_protocols import (
        CompilationCoordinatorProtocol,
        CompilationServiceProtocol,
    )

    # Test that protocols are runtime checkable
    assert hasattr(CompilationServiceProtocol, "__instancecheck__")
    assert hasattr(CompilationCoordinatorProtocol, "__instancecheck__")

    # Test basic protocol methods exist
    assert hasattr(CompilationServiceProtocol, "compile")
    assert hasattr(CompilationServiceProtocol, "validate_config")
    assert hasattr(CompilationServiceProtocol, "check_available")

    assert hasattr(CompilationCoordinatorProtocol, "compile")
    assert hasattr(CompilationCoordinatorProtocol, "validate_config")
    assert hasattr(CompilationCoordinatorProtocol, "get_available_strategies")


def test_workspace_protocols_runtime_checkable():
    """Test that workspace protocols are runtime checkable."""
    from glovebox.compilation.protocols.workspace_protocols import (
        WestWorkspaceManagerProtocol,
        WorkspaceManagerProtocol,
        ZmkConfigWorkspaceManagerProtocol,
    )

    # Test that protocols are runtime checkable
    protocols = [
        WorkspaceManagerProtocol,
        WestWorkspaceManagerProtocol,
        ZmkConfigWorkspaceManagerProtocol,
    ]

    for protocol in protocols:
        assert hasattr(protocol, "__instancecheck__")

    # Test basic protocol methods exist
    assert hasattr(WorkspaceManagerProtocol, "initialize_workspace")
    assert hasattr(WorkspaceManagerProtocol, "cleanup_workspace")

    assert hasattr(WestWorkspaceManagerProtocol, "initialize_west_workspace")
    assert hasattr(ZmkConfigWorkspaceManagerProtocol, "initialize_zmk_config_workspace")
    assert hasattr(ZmkConfigWorkspaceManagerProtocol, "clone_config_repository")


def test_artifact_protocols_runtime_checkable():
    """Test that artifact protocols are runtime checkable."""
    from glovebox.compilation.protocols.artifact_protocols import (
        ArtifactCollectorProtocol,
        ArtifactValidatorProtocol,
        FirmwareScannerProtocol,
    )

    # Test that protocols are runtime checkable
    protocols = [
        ArtifactCollectorProtocol,
        FirmwareScannerProtocol,
        ArtifactValidatorProtocol,
    ]

    for protocol in protocols:
        assert hasattr(protocol, "__instancecheck__")

    # Test basic protocol methods exist
    assert hasattr(ArtifactCollectorProtocol, "collect_artifacts")
    assert hasattr(FirmwareScannerProtocol, "scan_firmware_files")
    assert hasattr(ArtifactValidatorProtocol, "validate_artifacts")


def test_protocol_inheritance():
    """Test protocol inheritance relationships."""
    from glovebox.compilation.protocols.workspace_protocols import (
        WestWorkspaceManagerProtocol,
        WorkspaceManagerProtocol,
        ZmkConfigWorkspaceManagerProtocol,
    )

    # Test that specialized protocols inherit from base protocol
    assert issubclass(WestWorkspaceManagerProtocol, WorkspaceManagerProtocol)
    assert issubclass(ZmkConfigWorkspaceManagerProtocol, WorkspaceManagerProtocol)
