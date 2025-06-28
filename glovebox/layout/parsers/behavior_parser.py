"""Behavior parsing utilities for reverse engineering DTSI to JSON."""

import logging
import re
from typing import Any

from glovebox.layout.models import (
    ComboBehavior,
    HoldTapBehavior,
    LayoutBinding,
    MacroBehavior,
)


logger = logging.getLogger(__name__)


class BehaviorParser:
    """Parser for extracting behavior definitions from ZMK DTSI content."""

    def __init__(self):
        """Initialize behavior parser."""
        self.logger = logging.getLogger(__name__)

    def parse_behaviors_section(self, dtsi_content: str) -> dict[str, Any]:
        """Parse behaviors section from DTSI content.

        Args:
            dtsi_content: Device tree source content

        Returns:
            Dictionary with parsed behavior definitions
        """
        behaviors = {"hold_taps": [], "macros": [], "combos": []}

        # Extract behaviors node
        behaviors_pattern = r"behaviors\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}"
        behaviors_match = re.search(behaviors_pattern, dtsi_content, re.DOTALL)

        if not behaviors_match:
            return behaviors

        behaviors_content = behaviors_match.group(1)

        # Parse different behavior types
        behaviors["hold_taps"] = self._parse_hold_tap_behaviors(behaviors_content)

        return behaviors

    def parse_macros_section(self, dtsi_content: str) -> list[MacroBehavior]:
        """Parse macros section from DTSI content.

        Args:
            dtsi_content: Device tree source content

        Returns:
            List of parsed macro behaviors
        """
        macros = []

        # Extract macros node
        macros_pattern = r"macros\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}"
        macros_match = re.search(macros_pattern, dtsi_content, re.DOTALL)

        if not macros_match:
            return macros

        macros_content = macros_match.group(1)

        # Parse individual macro definitions
        macro_pattern = r"(\w+):\s*(\w+)\s*\{([^}]*)\}"
        macro_matches = re.findall(macro_pattern, macros_content, re.DOTALL)

        for macro_name, macro_type, macro_body in macro_matches:
            try:
                macro = self._parse_macro_definition(macro_name, macro_type, macro_body)
                if macro:
                    macros.append(macro)
            except Exception as e:
                self.logger.warning("Failed to parse macro '%s': %s", macro_name, e)

        return macros

    def parse_combos_section(self, dtsi_content: str) -> list[ComboBehavior]:
        """Parse combos section from DTSI content.

        Args:
            dtsi_content: Device tree source content

        Returns:
            List of parsed combo behaviors
        """
        combos = []

        # Extract combos node
        combos_pattern = r"combos\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}"
        combos_match = re.search(combos_pattern, dtsi_content, re.DOTALL)

        if not combos_match:
            return combos

        combos_content = combos_match.group(1)

        # Parse individual combo definitions
        combo_pattern = r"(\w+):\s*(\w+)\s*\{([^}]*)\}"
        combo_matches = re.findall(combo_pattern, combos_content, re.DOTALL)

        for combo_name, combo_type, combo_body in combo_matches:
            try:
                combo = self._parse_combo_definition(combo_name, combo_type, combo_body)
                if combo:
                    combos.append(combo)
            except Exception as e:
                self.logger.warning("Failed to parse combo '%s': %s", combo_name, e)

        return combos

    def _parse_hold_tap_behaviors(
        self, behaviors_content: str
    ) -> list[HoldTapBehavior]:
        """Parse hold-tap behavior definitions.

        Args:
            behaviors_content: Content of behaviors node

        Returns:
            List of parsed hold-tap behaviors
        """
        hold_taps = []

        # Pattern for hold-tap definitions
        hold_tap_pattern = r"(\w+):\s*zmk,behavior-hold-tap\s*\{([^}]*)\}"
        hold_tap_matches = re.findall(hold_tap_pattern, behaviors_content, re.DOTALL)

        for behavior_name, behavior_body in hold_tap_matches:
            try:
                hold_tap = self._parse_hold_tap_definition(behavior_name, behavior_body)
                if hold_tap:
                    hold_taps.append(hold_tap)
            except Exception as e:
                self.logger.warning(
                    "Failed to parse hold-tap '%s': %s", behavior_name, e
                )

        return hold_taps

    def _parse_hold_tap_definition(
        self, name: str, body: str
    ) -> HoldTapBehavior | None:
        """Parse individual hold-tap behavior definition.

        Args:
            name: Behavior name
            body: Behavior body content

        Returns:
            Parsed HoldTapBehavior or None if parsing fails
        """
        try:
            # Extract properties
            properties = self._extract_dt_properties(body)

            # Map device tree properties to JSON model fields
            hold_tap = HoldTapBehavior(
                name=name,
                description=properties.get("description", ""),
            )

            # Map timing properties
            if "tapping-term-ms" in properties:
                hold_tap.tapping_term_ms = self._parse_numeric_value(
                    properties["tapping-term-ms"]
                )

            if "quick-tap-ms" in properties:
                hold_tap.quick_tap_ms = self._parse_numeric_value(
                    properties["quick-tap-ms"]
                )

            if "require-prior-idle-ms" in properties:
                hold_tap.require_prior_idle_ms = self._parse_numeric_value(
                    properties["require-prior-idle-ms"]
                )

            # Map flavor
            if "flavor" in properties:
                flavor_value = properties["flavor"].strip('"')
                hold_tap.flavor = flavor_value

            # Map boolean properties
            if "hold-trigger-on-release" in properties:
                hold_tap.hold_trigger_on_release = True

            if "retro-tap" in properties:
                hold_tap.retro_tap = True

            # Map bindings
            if "bindings" in properties:
                bindings_value = properties["bindings"]
                bindings = self._parse_bindings_property(bindings_value)
                hold_tap.bindings = bindings

            return hold_tap

        except Exception as e:
            self.logger.warning("Failed to parse hold-tap definition: %s", e)
            return None

    def _parse_macro_definition(
        self, name: str, macro_type: str, body: str
    ) -> MacroBehavior | None:
        """Parse individual macro definition.

        Args:
            name: Macro name
            macro_type: Macro type (e.g., zmk,behavior-macro)
            body: Macro body content

        Returns:
            Parsed MacroBehavior or None if parsing fails
        """
        try:
            properties = self._extract_dt_properties(body)

            macro = MacroBehavior(
                name=name,
                description=properties.get("description", ""),
            )

            # Map timing properties
            if "wait-ms" in properties:
                macro.wait_ms = self._parse_numeric_value(properties["wait-ms"])

            if "tap-ms" in properties:
                macro.tap_ms = self._parse_numeric_value(properties["tap-ms"])

            # Parse bindings
            if "bindings" in properties:
                bindings_value = properties["bindings"]
                # Parse macro bindings (more complex than hold-tap)
                bindings = self._parse_macro_bindings(bindings_value)
                macro.bindings = bindings

            return macro

        except Exception as e:
            self.logger.warning("Failed to parse macro definition: %s", e)
            return None

    def _parse_combo_definition(
        self, name: str, combo_type: str, body: str
    ) -> ComboBehavior | None:
        """Parse individual combo definition.

        Args:
            name: Combo name
            combo_type: Combo type (e.g., zmk,behavior-combo)
            body: Combo body content

        Returns:
            Parsed ComboBehavior or None if parsing fails
        """
        try:
            properties = self._extract_dt_properties(body)

            # Key positions are required for combos
            if "key-positions" not in properties:
                self.logger.warning("Combo '%s' missing key-positions", name)
                return None

            key_positions = self._parse_array_property(properties["key-positions"])

            # Binding is required
            if "bindings" not in properties:
                self.logger.warning("Combo '%s' missing bindings", name)
                return None

            bindings_value = properties["bindings"]
            binding = self._parse_single_binding(bindings_value)

            combo = ComboBehavior(
                name=name,
                description=properties.get("description", ""),
                key_positions=key_positions,
                binding=binding,
            )

            # Optional timeout
            if "timeout-ms" in properties:
                combo.timeout_ms = self._parse_numeric_value(properties["timeout-ms"])

            # Optional layers
            if "layers" in properties:
                layers = self._parse_array_property(properties["layers"])
                combo.layers = layers

            return combo

        except Exception as e:
            self.logger.warning("Failed to parse combo definition: %s", e)
            return None

    def _extract_dt_properties(self, body: str) -> dict[str, str]:
        """Extract device tree properties from body content.

        Args:
            body: Device tree node body

        Returns:
            Dictionary of property names to values
        """
        properties = {}

        # Pattern for device tree properties
        # Handles: property = value; and property;
        prop_pattern = r"([a-zA-Z][a-zA-Z0-9_-]*)\s*(?:=\s*([^;]+))?\s*;"
        prop_matches = re.findall(prop_pattern, body)

        for prop_name, prop_value in prop_matches:
            # Convert dashes to underscores for Python compatibility
            python_name = prop_name.replace("-", "_")
            properties[python_name] = prop_value.strip() if prop_value else ""

        return properties

    def _parse_numeric_value(self, value: str) -> int | None:
        """Parse numeric value from device tree property.

        Args:
            value: Property value string

        Returns:
            Parsed integer or None if parsing fails
        """
        try:
            # Remove angle brackets and parse as integer
            clean_value = value.strip("<>").strip()
            return int(clean_value)
        except (ValueError, AttributeError):
            return None

    def _parse_array_property(self, value: str) -> list[int]:
        """Parse array property from device tree.

        Args:
            value: Property value string like "<1 2 3>"

        Returns:
            List of parsed integers
        """
        try:
            # Remove angle brackets and split by whitespace
            clean_value = value.strip("<>").strip()
            parts = clean_value.split()
            return [int(part) for part in parts if part.isdigit()]
        except (ValueError, AttributeError):
            return []

    def _parse_bindings_property(self, value: str) -> list[str]:
        """Parse bindings property for hold-tap behaviors.

        Args:
            value: Bindings property value

        Returns:
            List of binding strings
        """
        try:
            # Remove angle brackets and parse binding references
            clean_value = value.strip("<>").strip()
            # Split by comma or whitespace, handle &behavior references
            parts = re.split(r"[,\s]+", clean_value)
            return [part.strip() for part in parts if part.strip()]
        except (ValueError, AttributeError):
            return []

    def _parse_macro_bindings(self, value: str) -> list[LayoutBinding]:
        """Parse macro bindings into LayoutBinding objects.

        Args:
            value: Macro bindings property value

        Returns:
            List of LayoutBinding objects
        """
        bindings = []
        try:
            # Remove angle brackets and parse individual bindings
            clean_value = value.strip("<>").strip()
            # Split by comma, handle complex macro syntax
            binding_parts = re.split(r",\s*", clean_value)

            for part in binding_parts:
                part = part.strip()
                if part:
                    try:
                        binding = LayoutBinding.from_str(part)
                        bindings.append(binding)
                    except Exception as e:
                        self.logger.warning(
                            "Failed to parse macro binding '%s': %s", part, e
                        )
                        # Create fallback binding
                        bindings.append(LayoutBinding(value=part, params=[]))

        except (ValueError, AttributeError):
            pass

        return bindings

    def _parse_single_binding(self, value: str) -> LayoutBinding:
        """Parse single binding for combos.

        Args:
            value: Binding property value

        Returns:
            LayoutBinding object
        """
        try:
            # Remove angle brackets and parse as single binding
            clean_value = value.strip("<>").strip()
            return LayoutBinding.from_str(clean_value)
        except Exception as e:
            self.logger.warning("Failed to parse combo binding '%s': %s", value, e)
            # Return fallback binding
            return LayoutBinding(value=clean_value or "&none", params=[])


def create_behavior_parser() -> BehaviorParser:
    """Create behavior parser instance.

    Returns:
        Configured BehaviorParser instance
    """
    return BehaviorParser()
