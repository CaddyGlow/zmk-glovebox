"""Protocol definitions for behavior-related interfaces."""

from typing import TYPE_CHECKING, Any, Optional, Protocol, runtime_checkable


if TYPE_CHECKING:
    from glovebox.layout.behavior.models import SystemBehavior


@runtime_checkable
class BehaviorRegistryProtocol(Protocol):
    """Protocol for behavior registry."""

    def get_behavior_info(self, name: str) -> Optional["SystemBehavior"]:
        """Get information about a registered behavior."""
        ...

    def register_behavior(self, behavior: "SystemBehavior") -> None:
        """Register a behavior in the registry."""
        ...

    def list_behaviors(self) -> dict[str, "SystemBehavior"]:
        """List all registered behaviors."""
        ...

    def clear(self) -> None:
        """Clear all registered behaviors."""
        ...
