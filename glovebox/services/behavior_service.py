"""Behavior service for tracking and managing ZMK behaviors."""

import logging
from typing import Any, Optional, Protocol


logger = logging.getLogger(__name__)


class BehaviorRegistryImpl:
    """Implementation of behavior registry for tracking ZMK behaviors."""

    def __init__(self) -> None:
        self._behaviors: dict[str, dict[str, Any]] = {}
        logger.debug("BehaviorRegistryImpl initialized")

    def register_behavior(self, name: str, expected_params: int, origin: str) -> None:
        """
        Register a behavior with its expected parameter count.

        Args:
            name: Behavior name (e.g., "&kp", "&lt")
            expected_params: Number of parameters this behavior expects
            origin: Source where this behavior was defined
        """
        logger.debug(
            f"Registering behavior {name} with {expected_params} params from {origin}"
        )

        self._behaviors[name] = {"expected_params": expected_params, "origin": origin}

    def get_behavior_info(self, name: str) -> dict[str, Any] | None:
        """
        Get information about a registered behavior.

        Args:
            name: Behavior name to look up

        Returns:
            Dictionary with behavior info or None if not found
        """
        return self._behaviors.get(name)

    def list_behaviors(self) -> dict[str, dict[str, Any]]:
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

    def register_system_behaviors(self, profile: Any) -> None:
        """
        Register system behaviors from a keyboard profile.

        This method loads behaviors from the profile's system_behaviors list
        and adds fallbacks for essential behaviors.

        Args:
            profile: KeyboardProfile instance with system behaviors
        """
        keyboard_name = getattr(profile, "keyboard_name", "unknown")
        logger.debug(f"Registering system behaviors from: {keyboard_name}")

        behaviors = []

        try:
            # Get system behaviors from the profile
            behaviors = profile.system_behaviors

            # Process and register behaviors
            for behavior in behaviors:
                name = behavior.name
                expected_params = behavior.expected_params
                origin = behavior.origin

                if name:
                    logger.debug(
                        f"Registering behavior {name} with {expected_params} params from {origin}"
                    )
                    self._behaviors[name] = {
                        "expected_params": expected_params,
                        "origin": origin,
                    }
                else:
                    logger.warning(f"Skipping behavior without name: {behavior}")
        except Exception as e:
            logger.warning(f"Error loading system behaviors: {e}")
            logger.debug("Continuing with fallback behaviors")

        if len(behaviors) == 0:
            logger.warning("No system behaviors registered")

        # Register fallbacks for essential behaviors if not already registered
        # fallback_behaviors = {
        #     # Basic ZMK behaviors
        #     "&kp": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&mt": {"expected_params": 2, "origin": "zmk_fallback"},
        #     "&lt": {"expected_params": 2, "origin": "zmk_fallback"},
        #     "&mo": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&to": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&tog": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&none": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&trans": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&bt": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&out": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&rgb_ug": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&caps_word": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&key_repeat": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&reset": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&bootloader": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&sk": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&sl": {"expected_params": 1, "origin": "zmk_fallback"},
        #     # Mouse behaviors
        #     "&mkp": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&mmv": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&msc": {"expected_params": 1, "origin": "zmk_fallback"},
        #     # Macro behaviors
        #     "&macro_tap": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&macro_press": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&macro_release": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&macro_wait_time": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&macro_tap_time": {"expected_params": 1, "origin": "zmk_fallback"},
        #     "&macro_pause_for_release": {
        #         "expected_params": 0,
        #         "origin": "zmk_fallback",
        #     },
        #     # Bluetooth profile behaviors
        #     "&bt_0": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&bt_1": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&bt_2": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&bt_3": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&bt_select_0": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&bt_select_1": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&bt_select_2": {"expected_params": 0, "origin": "zmk_fallback"},
        #     "&bt_select_3": {"expected_params": 0, "origin": "zmk_fallback"},
        #     # Moergo behaviors
        #     "&magic": {"expected_params": 2, "origin": "zmk_fallback"},
        #     "&lower": {"expected_params": 0, "origin": "zmk_fallback"},
        # }
        #
        # # Add fallbacks only for behaviors not already registered
        # for name, info in fallback_behaviors.items():
        #     if name not in self._behaviors:
        #         logger.debug(f"Adding fallback behavior: {name}")
        #         self._behaviors[name] = info
        #
        logger.debug(f"Registered {len(self._behaviors)} total behaviors")


class BehaviorRegistry(Protocol):
    """Protocol defining the behavior registry interface."""

    def register_behavior(self, name: str, expected_params: int, origin: str) -> None:
        """Register a behavior with its expected parameter count."""
        ...

    def get_behavior_info(self, name: str) -> dict[str, Any] | None:
        """Get information about a registered behavior."""
        ...

    def list_behaviors(self) -> dict[str, dict[str, Any]]:
        """Get all registered behaviors."""
        ...

    def clear(self) -> None:
        """Clear all registered behaviors."""
        ...

    def register_system_behaviors(self, profile: Any) -> None:
        """Register system behaviors from a keyboard profile."""
        ...


def create_behavior_registry() -> BehaviorRegistry:
    """
    Create a BehaviorRegistryImpl instance.

    Returns:
        BehaviorRegistry instance
    """
    return BehaviorRegistryImpl()
