"""Builder for template contexts used in keymap generation."""

import logging
from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING, Any, TypeAlias


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile
from glovebox.layout.models import (
    ComboBehavior,
    HoldTapBehavior,
    InputListener,
    LayerBindings,
    LayoutData,
    MacroBehavior,
)
from glovebox.protocols.dtsi_generator_protocol import DtsiGeneratorProtocol


logger = logging.getLogger(__name__)


# Type aliases
TemplateContext: TypeAlias = dict[str, Any]


class TemplateContextBuilder:
    """Builder for template contexts used in keymap generation."""

    def __init__(self, dtsi_generator: DtsiGeneratorProtocol):
        """Initialize with DTSI generator dependency."""
        self._dtsi_generator = dtsi_generator

    def build_context(
        self, keymap_data: LayoutData, profile: "KeyboardProfile"
    ) -> TemplateContext:
        """Build template context with generated DTSI content.

        Args:
            keymap_data: Keymap data model
            profile: Keyboard profile with configuration

        Returns:
            Dictionary with template context
        """
        # Extract data for generation with fallback to empty lists
        layer_names = keymap_data.layer_names
        layers_data = keymap_data.layers
        hold_taps_data = keymap_data.hold_taps
        combos_data = keymap_data.combos
        macros_data = keymap_data.macros
        input_listeners_data = getattr(keymap_data, "input_listeners", [])

        # Get resolved includes from the profile
        resolved_includes = (
            profile.keyboard_config.keymap.includes
            if hasattr(profile.keyboard_config.keymap, "includes")
            else []
        )

        # Generate DTSI components
        layer_defines = self._dtsi_generator.generate_layer_defines(
            profile, layer_names
        )
        keymap_node = self._dtsi_generator.generate_keymap_node(
            profile, layer_names, layers_data
        )
        behaviors_dtsi = self._dtsi_generator.generate_behaviors_dtsi(
            profile, hold_taps_data
        )
        combos_dtsi = self._dtsi_generator.generate_combos_dtsi(
            profile, combos_data, layer_names
        )
        macros_dtsi = self._dtsi_generator.generate_macros_dtsi(profile, macros_data)
        input_listeners_dtsi = self._dtsi_generator.generate_input_listeners_node(
            profile, input_listeners_data
        )

        # Get template elements from the keyboard profile
        key_position_header = (
            profile.keyboard_config.keymap.key_position_header
            if hasattr(profile.keyboard_config.keymap, "key_position_header")
            else ""
        )
        system_behaviors_dts = (
            profile.keyboard_config.keymap.system_behaviors_dts
            if hasattr(profile.keyboard_config.keymap, "system_behaviors_dts")
            else ""
        )

        # Profile identifiers
        profile_name = f"{profile.keyboard_name}/{profile.firmware_version}"
        firmware_version = profile.firmware_version

        # Build and return the template context with defaults for missing values
        context: TemplateContext = {
            "keyboard": keymap_data.keyboard,
            "layer_names": layer_names,
            "layers": layers_data,
            "layer_defines": layer_defines,
            "keymap_node": keymap_node,
            "user_behaviors_dtsi": behaviors_dtsi,
            "combos_dtsi": combos_dtsi,
            "input_listeners_dtsi": input_listeners_dtsi,
            "user_macros_dtsi": macros_dtsi,
            "resolved_includes": "\n".join(resolved_includes),
            "key_position_header": key_position_header,
            "system_behaviors_dts": system_behaviors_dts,
            "custom_defined_behaviors": keymap_data.custom_defined_behaviors or "",
            "custom_devicetree": keymap_data.custom_devicetree or "",
            "profile_name": profile_name,
            "firmware_version": firmware_version,
            "generation_timestamp": datetime.now().isoformat(),
        }

        return context


def create_template_context_builder(
    dtsi_generator: DtsiGeneratorProtocol,
) -> TemplateContextBuilder:
    """Create a TemplateContextBuilder instance.

    Args:
        dtsi_generator: DTSI generator dependency

    Returns:
        Configured TemplateContextBuilder instance
    """
    return TemplateContextBuilder(dtsi_generator)
