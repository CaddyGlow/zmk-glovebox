"""Compilation-specific protocols for type safety."""

from glovebox.compilation.protocols.compilation_protocols import (
    CompilationServiceProtocol,
)
from glovebox.compilation.protocols.workspace_protocols import (
    WorkspaceManagerProtocol,
    ZmkConfigWorkspaceManagerProtocol,
)


__all__ = [
    # Compilation protocols
    "CompilationServiceProtocol",
    # Workspace protocols
    "WorkspaceManagerProtocol",
    "ZmkConfigWorkspaceManagerProtocol",
]
