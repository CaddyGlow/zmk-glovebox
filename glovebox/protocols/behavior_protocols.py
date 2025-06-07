"""Protocol definitions for behavior-related interfaces."""

from typing import Protocol, Optional, Any

from glovebox.models.behavior import RegistryBehavior


class BehaviorRegistryProtocol(Protocol):
    """Protocol for behavior registry."""

    def get_behavior_info(self, name: str) -> RegistryBehavior | None:
        """Get information about a registered behavior."""
        ...

    def register_behavior(self, behavior: Any) -> None:
        """Register a behavior in the registry."""
        ...

    def list_behaviors(self) -> dict[str, Any]:
        """List all registered behaviors."""
        ...


# Type alias for backwards compatibility
BehaviorRegistry = BehaviorRegistryProtocol