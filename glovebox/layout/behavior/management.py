"""Centralized behavior management service for layout operations."""

import logging
from collections import Counter
from typing import TYPE_CHECKING

from glovebox.core.structlog_logger import StructlogMixin, get_struct_logger

from .exceptions import (
    BehaviorRegistrationError,
    BehaviorValidationError,
)
from .models import SystemBehavior
from .service import create_behavior_registry


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile
    from glovebox.layout.models import LayoutData
    from glovebox.protocols.behavior_protocols import BehaviorRegistryProtocol


logger = get_struct_logger(__name__)


class BehaviorManagementService(StructlogMixin):
    """Centralized service for managing behavior registration and lifecycle."""

    def __init__(self) -> None:
        """Initialize the behavior management service."""
        self._registry: BehaviorRegistryProtocol = create_behavior_registry()
        self._is_prepared = False
        self._profile: KeyboardProfile | None = None
        self._layout_data: LayoutData | None = None
        self._registered_behaviors: list[str] = []

    def prepare_behaviors(
        self, profile: "KeyboardProfile", layout_data: "LayoutData"
    ) -> None:
        """Prepare all behaviors for the given profile and layout combination.

        This is the main entry point for setting up behaviors. It registers behaviors
        in the correct order: System → Layout → Custom.

        Args:
            profile: Keyboard profile containing system behaviors
            layout_data: Layout data containing custom behaviors

        Raises:
            BehaviorRegistrationError: If behavior registration fails
        """
        try:
            # Handle cases where profile might be a mock or missing attributes
            keyboard_name = getattr(profile, "keyboard_name", "unknown")
            firmware_version = getattr(profile, "firmware_version", "unknown")

            logger.info(
                "Preparing behaviors for profile %s/%s",
                keyboard_name,
                firmware_version,
            )

            # Clear any existing state
            self._registry.clear()
            self._registered_behaviors.clear()
            self._is_prepared = False

            # Store references for validation
            self._profile = profile
            self._layout_data = layout_data

            # Register behaviors in phases
            self._register_system_behaviors(profile)
            self._register_layout_behaviors(layout_data)

            self._is_prepared = True
            logger.info(
                "Behavior preparation completed: %d behaviors registered",
                len(self._registered_behaviors),
            )

        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error("Behavior preparation failed: %s", e, exc_info=exc_info)
            raise BehaviorRegistrationError(f"Failed to prepare behaviors: {e}") from e

    def _register_system_behaviors(self, profile: "KeyboardProfile") -> None:
        """Register system behaviors from the keyboard profile.

        Args:
            profile: Keyboard profile containing system behaviors
        """
        logger.debug("Registering system behaviors from profile")

        # Handle cases where profile might not have system_behaviors attribute
        system_behaviors = getattr(profile, "system_behaviors", [])

        for behavior in system_behaviors:
            try:
                self._registry.register_behavior(behavior)
                self._registered_behaviors.append(f"system:{behavior.code}")
                logger.debug("Registered system behavior: %s", behavior.code)
            except Exception as e:
                logger.warning(
                    "Failed to register system behavior %s: %s", behavior.code, e
                )

        logger.debug("Registered %d system behaviors", len(system_behaviors))

    def _register_layout_behaviors(self, layout_data: "LayoutData") -> None:
        """Register custom behaviors defined in the layout.

        Args:
            layout_data: Layout data containing custom behavior definitions
        """
        self._register_hold_tap_behaviors(layout_data)
        self._register_combo_behaviors(layout_data)
        self._register_macro_behaviors(layout_data)

    def _register_hold_tap_behaviors(self, layout_data: "LayoutData") -> None:
        """Register custom hold-tap behaviors from layout data.

        Args:
            layout_data: Layout data containing hold-tap definitions
        """
        hold_taps = getattr(layout_data, "hold_taps", [])
        if not hold_taps:
            return

        logger.debug("Registering %d hold-tap behaviors", len(hold_taps))

        for hold_tap in hold_taps:
            # Handle names that may or may not already include the "&" prefix
            behavior_code = (
                hold_tap.name if hold_tap.name.startswith("&") else f"&{hold_tap.name}"
            )
            behavior_name = hold_tap.name.lstrip("&")

            # Check for conflicts and warn instead of failing
            existing = self._registry.get_behavior_info(behavior_code)
            if existing:
                logger.warning(
                    "Behavior '%s' already registered from '%s', skipping layout definition",
                    behavior_code,
                    existing.origin,
                )
                continue

            ht_behavior = SystemBehavior(
                code=behavior_code,
                name=behavior_name,
                description=hold_tap.description
                or f"Custom hold-tap behavior: {behavior_name}",
                expected_params=2,  # Hold-tap behaviors typically take tap and hold parameters
                origin="layout",
                params=[],
                type="hold_tap",
                parameters={
                    "tapping_term_ms": hold_tap.tapping_term_ms,
                    "quick_tap_ms": hold_tap.quick_tap_ms,
                    "flavor": hold_tap.flavor,
                    "tap_behavior": hold_tap.tap_behavior,
                    "hold_behavior": hold_tap.hold_behavior,
                },
            )

            self._registry.register_behavior(ht_behavior)
            self._registered_behaviors.append(f"hold-tap:{ht_behavior.code}")
            logger.debug("Registered hold-tap behavior: %s", ht_behavior.code)

    def _register_combo_behaviors(self, layout_data: "LayoutData") -> None:
        """Register custom combo behaviors from layout data.

        Args:
            layout_data: Layout data containing combo definitions
        """
        combos = getattr(layout_data, "combos", [])
        if not combos:
            return

        logger.debug("Registering %d combo behaviors", len(combos))

        for combo in combos:
            # Handle names that may or may not already include the "&" prefix
            combo_code = f"&combo_{combo.name.lstrip('&')}"
            combo_name = f"combo_{combo.name.lstrip('&')}"

            # Check for conflicts and warn instead of failing
            existing = self._registry.get_behavior_info(combo_code)
            if existing:
                logger.warning(
                    "Behavior '%s' already registered from '%s', skipping layout definition",
                    combo_code,
                    existing.origin,
                )
                continue

            combo_behavior = SystemBehavior(
                code=combo_code,
                name=combo_name,
                description=combo.description or f"Custom combo behavior: {combo_name}",
                expected_params=0,  # Combos don't take parameters when referenced
                origin="layout",
                params=[],
                type="combo",
                parameters={
                    "timeout_ms": combo.timeout_ms,
                    "key_positions": combo.key_positions,
                    "layers": combo.layers,
                    "binding": combo.binding.value if combo.binding else None,
                },
            )

            self._registry.register_behavior(combo_behavior)
            self._registered_behaviors.append(f"combo:{combo_behavior.code}")
            logger.debug("Registered combo behavior: %s", combo_behavior.code)

    def _register_macro_behaviors(self, layout_data: "LayoutData") -> None:
        """Register custom macro behaviors from layout data.

        Args:
            layout_data: Layout data containing macro definitions
        """
        macros = getattr(layout_data, "macros", [])
        if not macros:
            return

        logger.debug("Registering %d macro behaviors", len(macros))

        for macro in macros:
            # Handle names that may or may not already include the "&" prefix
            macro_code = macro.name if macro.name.startswith("&") else f"&{macro.name}"
            macro_name = macro.name.lstrip("&")

            # Check for conflicts and warn instead of failing
            existing = self._registry.get_behavior_info(macro_code)
            if existing:
                logger.warning(
                    "Behavior '%s' already registered from '%s', skipping layout definition",
                    macro_code,
                    existing.origin,
                )
                continue

            # Analyze usage in the layout to determine expected parameters
            expected_params = self._analyze_behavior_param_usage(
                layout_data, macro_code
            )

            macro_behavior = SystemBehavior(
                code=macro_code,
                name=macro_name,
                description=macro.description or f"Custom macro behavior: {macro_name}",
                expected_params=expected_params,
                origin="layout",
                params=[],
                type="macro",
                parameters={
                    "wait_ms": macro.wait_ms,
                    "tap_ms": macro.tap_ms,
                    "bindings": [binding.value for binding in macro.bindings]
                    if macro.bindings
                    else [],
                },
            )

            self._registry.register_behavior(macro_behavior)
            self._registered_behaviors.append(f"macro:{macro_behavior.code}")
            logger.debug("Registered macro behavior: %s", macro_behavior.code)

    def _analyze_behavior_param_usage(
        self, layout_data: "LayoutData", behavior_code: str
    ) -> int:
        """Analyze how many parameters a behavior is used with in the layout.

        Args:
            layout_data: Layout data containing layers and bindings
            behavior_code: The behavior code to analyze (e.g., "&AS_v1_TKZ")

        Returns:
            Most common parameter count used with this behavior
        """
        param_counts = []

        # Check all layers
        try:
            structured_layers = layout_data.get_structured_layers()
            for layer in structured_layers:
                for binding in layer.bindings:
                    if binding and binding.value == behavior_code:
                        # Count the parameters for this usage
                        param_count = len(binding.params) if binding.params else 0
                        param_counts.append(param_count)
        except Exception as e:
            logger.debug("Error analyzing behavior usage for %s: %s", behavior_code, e)

        # Check hold-taps
        hold_taps = getattr(layout_data, "hold_taps", [])
        for hold_tap in hold_taps:
            if hold_tap.tap_behavior == behavior_code:
                param_counts.append(0)  # Hold-tap references typically don't use params
            if hold_tap.hold_behavior == behavior_code:
                param_counts.append(0)

        # Check combos
        combos = getattr(layout_data, "combos", [])
        for combo in combos:
            if combo.binding and combo.binding.value == behavior_code:
                param_count = len(combo.binding.params) if combo.binding.params else 0
                param_counts.append(param_count)

        # Check macros (bindings within other macros)
        macros = getattr(layout_data, "macros", [])
        for macro in macros:
            if macro.bindings:
                for binding in macro.bindings:
                    if binding.value == behavior_code:
                        param_count = len(binding.params) if binding.params else 0
                        param_counts.append(param_count)

        # Return the most common parameter count, or 0 if no usage found
        if not param_counts:
            return 0

        # Find the most common parameter count
        most_common = Counter(param_counts).most_common(1)
        return most_common[0][0] if most_common else 0

    def validate_behaviors(self) -> list[str]:
        """Validate that all referenced behaviors are registered.

        Returns:
            List of validation errors (empty if no errors)

        Raises:
            BehaviorValidationError: If validation fails and behaviors are not prepared
        """
        if not self._is_prepared:
            raise BehaviorValidationError(
                "Behaviors must be prepared before validation"
            )

        if not self._profile or not self._layout_data:
            raise BehaviorValidationError(
                "Profile and layout data are required for validation"
            )

        errors = []
        used_behaviors = self._extract_behavior_codes_from_layout(
            self._profile, self._layout_data
        )

        for behavior_code in used_behaviors:
            if not self._registry.get_behavior_info(behavior_code):
                errors.append(f"Behavior '{behavior_code}' not found in registry")

        return errors

    def _extract_behavior_codes_from_layout(
        self, profile: "KeyboardProfile", layout_data: "LayoutData"
    ) -> list[str]:
        """Extract behavior codes used in a layout.

        Args:
            profile: Keyboard profile containing configuration
            layout_data: Layout data with layers and behaviors

        Returns:
            List of behavior codes used in the layout
        """
        behavior_codes = set()

        # Get structured layers with properly converted LayoutBinding objects
        structured_layers = layout_data.get_structured_layers()

        # Extract behavior codes from structured layers
        for layer in structured_layers:
            for binding in layer.bindings:
                if binding and binding.value:
                    # Extract base behavior code (e.g., "&kp" from "&kp SPACE")
                    code = binding.value.split()[0]
                    behavior_codes.add(code)

        # Extract behavior codes from hold-taps
        for ht in layout_data.hold_taps:
            if ht.tap_behavior:
                code = ht.tap_behavior.split()[0]
                behavior_codes.add(code)
            if ht.hold_behavior:
                code = ht.hold_behavior.split()[0]
                behavior_codes.add(code)

        # Extract behavior codes from combos
        for combo in layout_data.combos:
            if combo.behavior:
                code = combo.behavior.split()[0]
                behavior_codes.add(code)

        # Extract behavior codes from macros
        for macro in layout_data.macros:
            if macro.bindings:
                for binding in macro.bindings:
                    code = binding.value.split()[0]
                    behavior_codes.add(code)

        return list(behavior_codes)

    def get_behavior_registry(self) -> "BehaviorRegistryProtocol":
        """Get the behavior registry for use by formatters and generators.

        Returns:
            The behavior registry instance

        Raises:
            BehaviorValidationError: If behaviors are not prepared
        """
        if not self._is_prepared:
            raise BehaviorValidationError(
                "Behaviors must be prepared before accessing registry"
            )

        return self._registry

    def get_behavior_info(self, behavior_code: str) -> SystemBehavior | None:
        """Get information about a specific behavior.

        Args:
            behavior_code: The behavior code to look up

        Returns:
            Behavior information or None if not found
        """
        return self._registry.get_behavior_info(behavior_code)

    def list_registered_behaviors(self) -> list[str]:
        """Get a list of all registered behavior identifiers.

        Returns:
            List of behavior identifiers in format "type:code"
        """
        return self._registered_behaviors.copy()

    def get_required_includes_for_layout(
        self, profile: "KeyboardProfile", layout_data: "LayoutData"
    ) -> list[str]:
        """Get all includes needed for this profile+layout combination.

        Args:
            profile: Keyboard profile containing configuration
            layout_data: Layout data with behaviors

        Returns:
            List of include statements needed for the behaviors
        """
        behavior_codes = self._extract_behavior_codes_from_layout(profile, layout_data)
        includes: set[str] = set()

        # Handle cases where profile might not have system_behaviors attribute
        system_behaviors = getattr(profile, "system_behaviors", [])
        sb = {b.code: b for b in system_behaviors}

        # Add includes for each behavior
        for behavior in behavior_codes:
            if behavior in sb:
                behavior_includes = sb[behavior].includes
                if behavior_includes is not None:
                    for include in behavior_includes:
                        includes.add(include)

        return sorted(includes)

    def clear(self) -> None:
        """Clear all registered behaviors and reset state."""
        logger.debug("Clearing behavior management service state")
        self._registry.clear()
        self._registered_behaviors.clear()
        self._is_prepared = False
        self._profile = None
        self._layout_data = None


def create_behavior_management_service() -> BehaviorManagementService:
    """Create a new behavior management service instance.

    Returns:
        BehaviorManagementService instance
    """
    return BehaviorManagementService()
