"""Functional utilities for analyzing behavior usage in layouts."""

import logging
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile
    from glovebox.layout.models import LayoutData
    from glovebox.protocols.behavior_protocols import BehaviorRegistryProtocol


logger = logging.getLogger(__name__)


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
    logger.debug("Includes from behavior: %s", includes)
    return sorted(includes)


def register_layout_behaviors(
    profile: "KeyboardProfile",
    layout_data: "LayoutData",
    behavior_registry: "BehaviorRegistryProtocol",
) -> None:
    """Register all behaviors needed for this profile+layout combination.

    Args:
        profile: Keyboard profile containing configuration
        layout_data: Layout data containing custom behaviors, macros, and combos
        behavior_registry: The registry to register behaviors with
    """
    from .models import SystemBehavior

    # Register system behaviors from profile
    for behavior in profile.system_behaviors:
        behavior_registry.register_behavior(behavior)

    # Register custom hold-tap behaviors defined in the layout
    hold_taps = getattr(layout_data, "hold_taps", [])
    for hold_tap in hold_taps:
        # Handle names that may or may not already include the "&" prefix
        behavior_code = (
            hold_tap.name if hold_tap.name.startswith("&") else f"&{hold_tap.name}"
        )
        behavior_name = hold_tap.name.lstrip(
            "&"
        )  # Remove "&" prefix for the name field

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
        behavior_registry.register_behavior(ht_behavior)
        logger.debug("Registered hold-tap behavior: %s", ht_behavior.code)

    # Register custom combo behaviors defined in the layout
    combos = getattr(layout_data, "combos", [])
    for combo in combos:
        # Handle names that may or may not already include the "&" prefix
        combo_code = f"&combo_{combo.name.lstrip('&')}"
        combo_name = f"combo_{combo.name.lstrip('&')}"

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
        behavior_registry.register_behavior(combo_behavior)
        logger.debug("Registered combo behavior: %s", combo_behavior.code)

    # Register custom macro behaviors defined in the layout
    macros = getattr(layout_data, "macros", [])
    for macro in macros:
        # Handle names that may or may not already include the "&" prefix
        macro_code = macro.name if macro.name.startswith("&") else f"&{macro.name}"
        macro_name = macro.name.lstrip("&")  # Remove "&" prefix for the name field

        # Analyze usage in the layout to determine expected parameters
        expected_params = _analyze_behavior_param_usage(layout_data, macro_code)

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
        behavior_registry.register_behavior(macro_behavior)
        logger.debug("Registered macro behavior: %s", macro_behavior.code)
