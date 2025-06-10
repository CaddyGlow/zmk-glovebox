"""Compilation-specific protocols for type safety."""

from glovebox.compilation.protocols.artifact_protocols import (
    ArtifactCollectorProtocol,
    ArtifactValidatorProtocol,
    FirmwareScannerProtocol,
)
from glovebox.compilation.protocols.compilation_protocols import (
    CompilationCoordinatorProtocol,
    CompilationServiceProtocol,
)
from glovebox.compilation.protocols.workspace_protocols import (
    WestWorkspaceManagerProtocol,
    WorkspaceManagerProtocol,
    ZmkConfigWorkspaceManagerProtocol,
)


__all__ = [
    # Compilation protocols
    "CompilationCoordinatorProtocol",
    "CompilationServiceProtocol",
    # Workspace protocols
    "WorkspaceManagerProtocol",
    "ZmkConfigWorkspaceManagerProtocol",
    "WestWorkspaceManagerProtocol",
    # Artifact protocols
    "ArtifactCollectorProtocol",
    "FirmwareScannerProtocol",
    "ArtifactValidatorProtocol",
]
