"""Behavior service for tracking and managing ZMK behaviors."""

import logging

from ...protocols.behavior_protocols import BehaviorRegistryProtocol
from .models import (
    SystemBehavior,
)


logger = logging.getLogger(__name__)


class BehaviorRegistryImpl:
    """Implementation of behavior registry for tracking ZMK behaviors."""

    def __init__(self) -> None:
        self._behaviors: dict[str, SystemBehavior] = {}

    def register_behavior(self, behavior: SystemBehavior) -> None:
        """
        Register a behavior with its expected parameter count.

        Args:
            name: Behavior name (e.g., "&kp", "&lt")
            expected_params: Number of parameters this behavior expects
            origin: Source where this behavior was defined
        """
        self._behaviors[behavior.code] = behavior

    def get_behavior_info(self, name: str) -> SystemBehavior | None:
        """
        Get information about a registered behavior.

        Args:
            name: Behavior name to look up

        Returns:
            Behavior info or None if not found
        """
        return self._behaviors.get(name)

    def list_behaviors(self) -> dict[str, SystemBehavior]:
        """
        Get all registered behaviors.

        Returns:
            Dictionary mapping behavior names to their info
        """
        return self._behaviors.copy()

    def clear(self) -> None:
        """Clear all registered behaviors."""
        logger.debug("Clearing all registered behaviors")
        self._behaviors.clear()


def create_behavior_registry() -> BehaviorRegistryProtocol:
    """
    Create a BehaviorRegistryImpl instance.

    Returns:
        BehaviorRegistry instance
    """
    return BehaviorRegistryImpl()
