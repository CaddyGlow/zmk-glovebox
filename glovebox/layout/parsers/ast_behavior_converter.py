"""AST-based behavior converter for extracting behaviors from device tree nodes."""

import logging

from glovebox.layout.models import (
    ComboBehavior,
    HoldTapBehavior,
    LayoutBinding,
    MacroBehavior,
)
from glovebox.layout.parsers.ast_nodes import DTNode, DTProperty, DTValueType


logger = logging.getLogger(__name__)


class ASTBehaviorConverter:
    """Convert device tree AST nodes directly to behavior model objects."""

    def __init__(self) -> None:
        """Initialize AST behavior converter."""
        self.logger = logging.getLogger(__name__)

    def convert_hold_tap_node(self, node: DTNode) -> HoldTapBehavior | None:
        """Convert a device tree node to HoldTapBehavior.

        Args:
            node: Device tree node representing a hold-tap behavior

        Returns:
            HoldTapBehavior instance or None if conversion fails
        """
        try:
            # Extract basic information
            name = node.label or node.name
            if not name:
                self.logger.warning("Hold-tap node missing name/label")
                return None

            # Get description from comments or properties
            description = self._extract_description_from_node(node)

            # Create base behavior
            hold_tap = HoldTapBehavior(name=name, description=description)

            # Extract properties and populate behavior
            self._populate_hold_tap_properties(hold_tap, node)

            return hold_tap

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to convert hold-tap node '%s': %s",
                node.name,
                e,
                exc_info=exc_info,
            )
            return None

    def convert_macro_node(self, node: DTNode) -> MacroBehavior | None:
        """Convert a device tree node to MacroBehavior.

        Args:
            node: Device tree node representing a macro behavior

        Returns:
            MacroBehavior instance or None if conversion fails
        """
        try:
            # Extract basic information
            name = node.label or node.name
            if not name:
                self.logger.warning("Macro node missing name/label")
                return None

            # Get description from comments or properties
            description = self._extract_description_from_node(node)

            # Create base behavior
            macro = MacroBehavior(name=name, description=description)

            # Extract properties and populate behavior
            self._populate_macro_properties(macro, node)

            return macro

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to convert macro node '%s': %s", node.name, e, exc_info=exc_info
            )
            return None

    def convert_combo_node(self, node: DTNode) -> ComboBehavior | None:
        """Convert a device tree node to ComboBehavior.

        Args:
            node: Device tree node representing a combo behavior

        Returns:
            ComboBehavior instance or None if conversion fails
        """
        try:
            # Extract basic information
            name = node.label or node.name
            if not name:
                self.logger.warning("Combo node missing name/label")
                return None

            # Get description from comments or properties
            description = self._extract_description_from_node(node)

            # Key positions are required for combos
            key_positions_prop = node.get_property("key-positions")
            if not key_positions_prop:
                self.logger.warning("Combo '%s' missing key-positions property", name)
                return None

            key_positions = self._extract_array_from_property(key_positions_prop)
            if not key_positions:
                self.logger.warning("Combo '%s' has invalid key-positions", name)
                return None

            # Bindings are required
            bindings_prop = node.get_property("bindings")
            if not bindings_prop:
                self.logger.warning("Combo '%s' missing bindings property", name)
                return None

            binding = self._extract_single_binding_from_property(bindings_prop)
            if not binding:
                self.logger.warning("Combo '%s' has invalid bindings", name)
                return None

            # Create combo behavior
            combo = ComboBehavior(
                name=name,
                description=description,
                keyPositions=key_positions,
                binding=binding,
            )

            # Extract optional properties
            self._populate_combo_properties(combo, node)

            return combo

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to convert combo node '%s': %s", node.name, e, exc_info=exc_info
            )
            return None

    def _extract_description_from_node(self, node: DTNode) -> str:
        """Extract description from node comments or properties.

        Args:
            node: Device tree node

        Returns:
            Description string (may be empty)
        """
        # Priority 1: Comments attached to the node itself
        if node.comments:
            comment_text = self._clean_comment_text(node.comments[0].text)
            if comment_text:
                return comment_text

        # Priority 2: Comments from parent node (for behaviors in behaviors blocks)
        if hasattr(node, "parent") and node.parent and node.parent.comments:
            for comment in reversed(node.parent.comments):
                comment_text = self._clean_comment_text(comment.text)
                if comment_text:
                    return comment_text

        # Priority 3: Description property
        description_prop = node.get_property("description")
        if description_prop and description_prop.value:
            return self._extract_string_from_property(description_prop)

        # Priority 4: Label property
        label_prop = node.get_property("label")
        if label_prop and label_prop.value:
            return self._extract_string_from_property(label_prop)

        return ""

    def _clean_comment_text(self, comment_text: str) -> str:
        """Clean comment text by removing markers and filtering out non-descriptive comments.

        Args:
            comment_text: Raw comment text

        Returns:
            Cleaned comment text or empty string if not descriptive
        """
        # Skip property-like comments (they're not descriptions)
        if not comment_text or comment_text.strip().startswith("#"):
            return ""

        # Clean up comment markers
        if comment_text.startswith("//"):
            return comment_text[2:].strip()
        elif comment_text.startswith("/*") and comment_text.endswith("*/"):
            return comment_text[2:-2].strip()

        return comment_text.strip()

    def _populate_hold_tap_properties(
        self, hold_tap: HoldTapBehavior, node: DTNode
    ) -> None:
        """Populate hold-tap behavior properties from device tree node.

        Args:
            hold_tap: HoldTapBehavior to populate
            node: Device tree node with properties
        """
        # Timing properties
        tapping_term_prop = node.get_property("tapping-term-ms")
        if tapping_term_prop:
            hold_tap.tapping_term_ms = self._extract_int_from_property(
                tapping_term_prop
            )

        quick_tap_prop = node.get_property("quick-tap-ms")
        if quick_tap_prop:
            hold_tap.quick_tap_ms = self._extract_int_from_property(quick_tap_prop)

        require_prior_idle_prop = node.get_property("require-prior-idle-ms")
        if require_prior_idle_prop:
            hold_tap.require_prior_idle_ms = self._extract_int_from_property(
                require_prior_idle_prop
            )

        # Flavor property
        flavor_prop = node.get_property("flavor")
        if flavor_prop:
            hold_tap.flavor = self._extract_string_from_property(flavor_prop)

        # Boolean properties (property presence indicates True)
        if node.get_property("hold-trigger-on-release"):
            hold_tap.hold_trigger_on_release = True

        if node.get_property("retro-tap"):
            hold_tap.retro_tap = True

        # Bindings property
        bindings_prop = node.get_property("bindings")
        if bindings_prop:
            bindings = self._extract_bindings_from_property(bindings_prop)
            hold_tap.bindings = bindings

    def _populate_macro_properties(self, macro: MacroBehavior, node: DTNode) -> None:
        """Populate macro behavior properties from device tree node.

        Args:
            macro: MacroBehavior to populate
            node: Device tree node with properties
        """
        # Timing properties
        wait_ms_prop = node.get_property("wait-ms")
        if wait_ms_prop:
            macro.wait_ms = self._extract_int_from_property(wait_ms_prop)

        tap_ms_prop = node.get_property("tap-ms")
        if tap_ms_prop:
            macro.tap_ms = self._extract_int_from_property(tap_ms_prop)

        # Bindings property
        bindings_prop = node.get_property("bindings")
        if bindings_prop:
            bindings = self._extract_macro_bindings_from_property(bindings_prop)
            macro.bindings = bindings

        # Binding cells for parameter configuration
        binding_cells_prop = node.get_property("#binding-cells")
        if binding_cells_prop:
            binding_cells = self._extract_int_from_property(binding_cells_prop)
            if binding_cells == 0:
                macro.params = None
            elif binding_cells == 1:
                macro.params = ["code"]
            elif binding_cells == 2:
                macro.params = ["param1", "param2"]
            else:
                self.logger.warning(
                    "Unexpected binding-cells value for macro %s: %s",
                    macro.name,
                    binding_cells,
                )

    def _populate_combo_properties(self, combo: ComboBehavior, node: DTNode) -> None:
        """Populate combo behavior properties from device tree node.

        Args:
            combo: ComboBehavior to populate
            node: Device tree node with properties
        """
        # Optional timeout
        timeout_prop = node.get_property("timeout-ms")
        if timeout_prop:
            combo.timeout_ms = self._extract_int_from_property(timeout_prop)

        # Optional layers
        layers_prop = node.get_property("layers")
        if layers_prop:
            layers = self._extract_array_from_property(layers_prop)
            combo.layers = layers

    def _extract_string_from_property(self, prop: DTProperty) -> str:
        """Extract string value from device tree property.

        Args:
            prop: Device tree property

        Returns:
            String value or empty string if extraction fails
        """
        if not prop.value:
            return ""

        if prop.value.type == DTValueType.STRING or prop.value.type in (
            DTValueType.INTEGER,
            DTValueType.BOOLEAN,
        ):
            return str(prop.value.value)
        else:
            return prop.value.raw

    def _extract_int_from_property(self, prop: DTProperty) -> int | None:
        """Extract integer value from device tree property.

        Args:
            prop: Device tree property

        Returns:
            Integer value or None if extraction fails
        """
        if not prop.value:
            return None

        if prop.value.type == DTValueType.INTEGER:
            return int(prop.value.value)
        elif prop.value.type == DTValueType.STRING:
            try:
                # Handle angle bracket format
                value_str = str(prop.value.value).strip("<>")
                return int(value_str)
            except ValueError:
                return None
        else:
            # Try to parse from raw value
            try:
                raw_value = prop.value.raw.strip("<>")
                return int(raw_value)
            except ValueError:
                return None

    def _extract_array_from_property(self, prop: DTProperty) -> list[int]:
        """Extract array of integers from device tree property.

        Args:
            prop: Device tree property

        Returns:
            List of integers (may be empty)
        """
        if not prop.value:
            return []

        if prop.value.type == DTValueType.ARRAY:
            # Convert all values to integers if possible
            result = []
            for value in prop.value.value:
                try:
                    if isinstance(value, int):
                        result.append(value)
                    else:
                        result.append(int(str(value)))
                except ValueError:
                    continue
            return result
        elif prop.value.type == DTValueType.INTEGER:
            return [int(prop.value.value)]
        else:
            # Try to parse from raw value
            try:
                raw_value = prop.value.raw.strip("<>")
                parts = raw_value.split()
                return [int(part) for part in parts if part.isdigit()]
            except (ValueError, AttributeError):
                return []

    def _extract_bindings_from_property(self, prop: DTProperty) -> list[str]:
        """Extract bindings array from device tree property for hold-tap behaviors.

        Args:
            prop: Device tree property containing bindings

        Returns:
            List of binding strings
        """
        if not prop.value:
            return []

        try:
            # For array values, extract the actual array elements
            if prop.value.type == DTValueType.ARRAY:
                result = []
                for value in prop.value.value:
                    if isinstance(value, str) and value.strip():
                        # Clean up the value and ensure it's a valid binding
                        cleaned_value = value.strip()
                        if cleaned_value and cleaned_value.startswith("&"):
                            result.append(cleaned_value)
                return result
            else:
                # Fallback to raw parsing for non-array values
                raw_value = prop.value.raw.strip()
                # For device tree bindings, split by comma and clean each part
                import re

                # Remove outer angle brackets and split by comma
                cleaned_raw = re.sub(r"<\s*([^>]+)\s*>", r"\1", raw_value)
                parts = [part.strip() for part in cleaned_raw.split(",")]

                result = []
                for part in parts:
                    if part and part.startswith("&"):
                        result.append(part)
                return result
        except (ValueError, AttributeError):
            return []

    def _extract_macro_bindings_from_property(
        self, prop: DTProperty
    ) -> list[LayoutBinding]:
        """Extract macro bindings from device tree property.

        Args:
            prop: Device tree property containing macro bindings

        Returns:
            List of LayoutBinding objects
        """
        bindings: list[LayoutBinding] = []
        if not prop.value:
            return bindings

        try:
            # For array values, extract the actual array elements
            if prop.value.type == DTValueType.ARRAY:
                for value in prop.value.value:
                    if isinstance(value, str) and value.strip():
                        cleaned_value = value.strip()
                        if cleaned_value and cleaned_value.startswith("&"):
                            try:
                                binding = LayoutBinding.from_str(cleaned_value)
                                bindings.append(binding)
                            except Exception as e:
                                self.logger.warning(
                                    "Failed to parse macro binding '%s': %s",
                                    cleaned_value,
                                    e,
                                )
                                # Create fallback binding
                                bindings.append(
                                    LayoutBinding(value=cleaned_value, params=[])
                                )
            else:
                # Fallback to raw parsing for non-array values
                raw_value = prop.value.raw.strip()
                # For device tree bindings, properly handle angle bracket format
                import re

                # Remove angle brackets and split by comma
                cleaned_raw = re.sub(r"<\s*([^>]+)\s*>", r"\1", raw_value)
                binding_parts = [part.strip() for part in cleaned_raw.split(",")]

                for part in binding_parts:
                    if part and part.startswith("&"):
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

    def _extract_single_binding_from_property(
        self, prop: DTProperty
    ) -> LayoutBinding | None:
        """Extract single binding from device tree property for combos.

        Args:
            prop: Device tree property containing a single binding

        Returns:
            LayoutBinding object or None if extraction fails
        """
        if not prop.value:
            return None

        try:
            # For array values with single element, extract it
            if prop.value.type == DTValueType.ARRAY and prop.value.value:
                first_value = prop.value.value[0]
                if isinstance(first_value, str) and first_value.strip():
                    cleaned_value = first_value.strip()
                    if cleaned_value.startswith("&"):
                        return LayoutBinding.from_str(cleaned_value)
            else:
                # Fallback to raw parsing
                raw_value = prop.value.raw.strip()
                # Remove angle brackets properly
                import re

                cleaned_raw = re.sub(r"<\s*([^>]+)\s*>", r"\1", raw_value).strip()
                if cleaned_raw and cleaned_raw.startswith("&"):
                    return LayoutBinding.from_str(cleaned_raw)

            # Return fallback binding
            return LayoutBinding(value="&none", params=[])
        except Exception as e:
            self.logger.warning(
                "Failed to parse combo binding '%s': %s", prop.value.raw, e
            )
            # Return fallback binding
            return LayoutBinding(value="&none", params=[])


def create_ast_behavior_converter() -> ASTBehaviorConverter:
    """Create AST behavior converter instance.

    Returns:
        Configured ASTBehaviorConverter instance
    """
    return ASTBehaviorConverter()
