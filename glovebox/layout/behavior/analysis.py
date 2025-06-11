"""Functional utilities for analyzing behavior usage in layouts."""

import logging
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile
    from glovebox.layout.models import LayoutData
    from glovebox.protocols.behavior_protocols import BehaviorRegistryProtocol


logger = logging.getLogger(__name__)


def extract_behavior_codes_from_layout(
    profile: "KeyboardProfile", layout_data: "LayoutData"
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


def get_required_includes_for_layout(
    profile: "KeyboardProfile", layout_data: "LayoutData"
) -> list[str]:
    """Get all includes needed for this profile+layout combination.

    Args:
        profile: Keyboard profile containing configuration
        layout_data: Layout data with behaviors

    Returns:
        List of include statements needed for the behaviors
    """
    behavior_codes = extract_behavior_codes_from_layout(profile, layout_data)
    base_includes: set[str] = set(profile.keyboard_config.keymap.includes)

    # Add includes for each behavior
    for behavior in profile.system_behaviors:
        if behavior.code in behavior_codes and behavior.includes:
            base_includes.update(behavior.includes)

    return sorted(base_includes)


def register_layout_behaviors(
    profile: "KeyboardProfile",
    layout_data: "LayoutData",
    behavior_registry: "BehaviorRegistryProtocol",
) -> None:
    """Register all behaviors needed for this profile+layout combination.

    Args:
        profile: Keyboard profile containing configuration
        layout_data: Layout data (currently unused but kept for consistency)
        behavior_registry: The registry to register behaviors with
    """
    for behavior in profile.system_behaviors:
        behavior_registry.register_behavior(behavior)
