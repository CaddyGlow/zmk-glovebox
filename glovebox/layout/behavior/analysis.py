"""Functional utilities for analyzing behavior usage in layouts."""

from typing import TYPE_CHECKING

from glovebox.core.structlog_logger import StructlogMixin, get_struct_logger


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile
    from glovebox.layout.models import LayoutData
    from glovebox.protocols.behavior_protocols import BehaviorRegistryProtocol


logger = get_struct_logger(__name__)


def _analyze_behavior_param_usage(layout_data: "LayoutData", behavior_code: str) -> int:
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
    from collections import Counter

    most_common = Counter(param_counts).most_common(1)
    return most_common[0][0] if most_common else 0


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
    # logger.debug("Structured layers: %s", structured_layers)

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
    # base_includes: set[str] = set(profile.keyboard_config.keymap.header_includes)
    includes: set[str] = set()
    sb = {b.code: b for b in profile.system_behaviors}
    # Add includes for each behavior
    for behavior in behavior_codes:
        if behavior in sb:
            behavior_includes = sb[behavior].includes
            if behavior_includes is not None:
                for include in behavior_includes:
                    includes.add(include)
    return sorted(includes)


def register_layout_behaviors(
    profile: "KeyboardProfile",
    layout_data: "LayoutData",
    behavior_registry: "BehaviorRegistryProtocol",
) -> None:
    """Register all behaviors needed for this profile+layout combination.

    DEPRECATED: Use BehaviorManagementService.prepare_behaviors() instead.

    This function is maintained for backward compatibility but should not be
    used in new code. The BehaviorManagementService provides better error handling,
    conflict detection, and lifecycle management.

    Args:
        profile: Keyboard profile containing configuration
        layout_data: Layout data containing custom behaviors, macros, and combos
        behavior_registry: The registry to register behaviors with
    """
    import warnings

    from .management import create_behavior_management_service

    warnings.warn(
        "register_layout_behaviors() is deprecated. Use BehaviorManagementService.prepare_behaviors() instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    # Use the new management service for consistency
    behavior_manager = create_behavior_management_service()
    behavior_manager.prepare_behaviors(profile, layout_data)

    # Copy behaviors to the provided registry for backward compatibility
    managed_registry = behavior_manager.get_behavior_registry()
    all_behaviors = managed_registry.list_behaviors()

    for behavior in all_behaviors.values():
        behavior_registry.register_behavior(behavior)

    logger.debug("Registered %d behaviors (via management service)", len(all_behaviors))
