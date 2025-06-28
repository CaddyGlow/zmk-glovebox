"""Converters from AST nodes to glovebox behavior models."""

import logging
from typing import Any

from glovebox.layout.behavior.models import ParamValue
from glovebox.layout.models import (
    CapsWordBehavior,
    ComboBehavior,
    HoldTapBehavior,
    LayoutBinding,
    LayoutParam,
    MacroBehavior,
    ModMorphBehavior,
    StickyKeyBehavior,
    TapDanceBehavior,
)
from glovebox.layout.parsers.ast_nodes import DTNode, DTValue, DTValueType


logger = logging.getLogger(__name__)


class ModelConverter:
    """Base class for converting AST nodes to glovebox models."""

    def __init__(self) -> None:
        """Initialize converter."""
        self.logger = logging.getLogger(__name__)

    def _get_property_value(
        self, node: DTNode, prop_name: str, default: Any = None
    ) -> Any:
        """Get property value from node with enhanced ZMK property mapping.

        Args:
            node: Device tree node
            prop_name: Property name (with dashes)
            default: Default value if property not found

        Returns:
            Property value or default
        """
        # Enhanced property name variants for comprehensive ZMK support
        prop_names = [
            prop_name,
            prop_name.replace("-", "_"),  # dash to underscore
            prop_name.replace("_", "-"),  # underscore to dash
        ]

        # Add common ZMK property aliases
        zmk_aliases = self._get_zmk_property_aliases(prop_name)
        prop_names.extend(zmk_aliases)

        for name in prop_names:
            prop = node.get_property(name)
            if prop and prop.value:
                return self._convert_dt_value(prop.value)

        return default

    def _get_zmk_property_aliases(self, prop_name: str) -> list[str]:
        """Get ZMK-specific property name aliases.

        Args:
            prop_name: Original property name

        Returns:
            List of alternative property names to try
        """
        aliases = []

        # Common ZMK property name mappings
        zmk_property_map = {
            # Timing properties
            "tapping-term-ms": ["tapping_term_ms", "tapping-term", "tap-term"],
            "quick-tap-ms": ["quick_tap_ms", "quick-tap", "quick_tap"],
            "require-prior-idle-ms": ["require_prior_idle_ms", "prior-idle-ms"],
            "release-after-ms": ["release_after_ms", "release-time"],
            "wait-ms": ["wait_ms", "wait", "delay-ms"],
            "tap-ms": ["tap_ms", "tap", "tap-time"],
            # Boolean properties
            "hold-trigger-on-release": ["hold_trigger_on_release", "hold-on-release"],
            "retro-tap": ["retro_tap", "retroTap"],
            "quick-release": ["quick_release", "quickRelease"],
            "ignore-modifiers": ["ignore_modifiers", "ignoreModifiers"],
            # Array properties
            "hold-trigger-key-positions": [
                "hold_trigger_key_positions",
                "hold-triggers",
            ],
            "key-positions": ["key_positions", "keyPositions", "positions"],
            "continue-list": ["continue_list", "continueList"],
            # Value properties
            "flavor": ["flavour", "type"],
            "mods": ["modifiers", "modifier"],
            "keep-mods": ["keep_mods", "keepMods", "keep-modifiers"],
            "timeout-ms": ["timeout_ms", "timeout"],
            "layers": ["layer", "active-layers"],
        }

        # Check for direct mappings
        if prop_name in zmk_property_map:
            aliases.extend(zmk_property_map[prop_name])

        # Check reverse mappings (in case input is an alias)
        for canonical, alias_list in zmk_property_map.items():
            if prop_name in alias_list:
                aliases.append(canonical)
                aliases.extend([a for a in alias_list if a != prop_name])

        return aliases

    def _convert_dt_value(self, dt_value: DTValue) -> Any:
        """Convert DTValue to appropriate Python type with enhanced ZMK support.

        Args:
            dt_value: Device tree value

        Returns:
            Converted value with proper type handling
        """
        if dt_value.type == DTValueType.STRING:
            return self._convert_string_value(dt_value.value)
        elif dt_value.type == DTValueType.INTEGER:
            return self._convert_integer_value(dt_value.value)
        elif dt_value.type == DTValueType.ARRAY:
            return self._convert_array_value(dt_value.value)
        elif dt_value.type == DTValueType.REFERENCE:
            return self._convert_reference_value(dt_value.value)
        elif dt_value.type == DTValueType.BOOLEAN:
            return dt_value.value
        else:
            return dt_value.value

    def _convert_string_value(self, value: str) -> str | int | float:
        """Convert string value with smart type detection.

        Args:
            value: String value from device tree

        Returns:
            Converted value (string, int, or float)
        """
        # Remove surrounding quotes if present
        if (
            isinstance(value, str)
            and len(value) >= 2
            and (
                (value.startswith('"') and value.endswith('"'))
                or (value.startswith("'") and value.endswith("'"))
            )
        ):
            value = value[1:-1]

        # Try to convert to number if it looks like one
        if isinstance(value, str):
            # Check for hex numbers
            if value.startswith("0x") or value.startswith("0X"):
                try:
                    return int(value, 16)
                except ValueError:
                    pass

            # Check for decimal numbers
            if value.replace(".", "").replace("-", "").isdigit():
                try:
                    if "." in value:
                        return float(value)
                    else:
                        return int(value)
                except ValueError:
                    pass

        return str(value)

    def _convert_integer_value(self, value: Any) -> int:
        """Convert integer value with proper handling.

        Args:
            value: Integer value from device tree

        Returns:
            Integer value
        """
        if isinstance(value, int):
            return value

        # Handle string representations
        if isinstance(value, str):
            # Handle hex values
            if value.startswith("0x") or value.startswith("0X"):
                return int(value, 16)
            # Handle decimal values
            return int(value)

        return int(value)

    def _convert_array_value(self, value: list[Any]) -> list[Any]:
        """Convert array value with element type conversion.

        Args:
            value: Array value from device tree

        Returns:
            Converted array with proper element types
        """
        if not isinstance(value, list):
            return [value]

        converted = []
        for item in value:
            if isinstance(item, str):
                # Handle references in arrays
                if item.startswith("&"):
                    converted.append(item)
                else:
                    converted.append(self._convert_string_value(item))
            elif isinstance(item, int | float):
                converted.append(item)
            else:
                converted.append(str(item))

        return converted

    def _convert_reference_value(self, value: str) -> str:
        """Convert reference value with proper formatting.

        Args:
            value: Reference value from device tree

        Returns:
            Properly formatted reference string
        """
        if not isinstance(value, str):
            value = str(value)

        # Ensure reference starts with &
        if not value.startswith("&"):
            return f"&{value}"

        return value

    def _get_string_property(
        self, node: DTNode, prop_name: str, default: str = ""
    ) -> str:
        """Get string property value.

        Args:
            node: Device tree node
            prop_name: Property name
            default: Default value

        Returns:
            String value
        """
        value = self._get_property_value(node, prop_name, default)
        return str(value) if value is not None else default

    def _get_int_property(
        self, node: DTNode, prop_name: str, default: int | None = None
    ) -> int | None:
        """Get integer property value.

        Args:
            node: Device tree node
            prop_name: Property name
            default: Default value

        Returns:
            Integer value or None
        """
        value = self._get_property_value(node, prop_name, default)
        if value is None:
            return default

        try:
            # Handle array values (single-element arrays are common in device tree)
            if isinstance(value, list) and len(value) == 1:
                return int(value[0])
            return int(value)
        except (ValueError, TypeError):
            self.logger.warning(
                "Failed to convert property '%s' to int: %s", prop_name, value
            )
            return default

    def _get_bool_property(
        self, node: DTNode, prop_name: str, default: bool = False
    ) -> bool:
        """Get boolean property value.

        Args:
            node: Device tree node
            prop_name: Property name
            default: Default value

        Returns:
            Boolean value
        """
        prop = node.get_property(prop_name) or node.get_property(
            prop_name.replace("-", "_")
        )
        if prop is None:
            return default

        # Boolean properties can be:
        # 1. Present without value (true)
        # 2. Present with value (convert value)
        if prop.value is None or prop.value.type == DTValueType.BOOLEAN:
            return True  # Property presence indicates true

        # Try to convert value
        value = self._convert_dt_value(prop.value)
        if isinstance(value, bool):
            return value
        elif isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "on")
        elif isinstance(value, int):
            return value != 0
        else:
            return default

    def _get_array_property(
        self, node: DTNode, prop_name: str, default: list[int] | None = None
    ) -> list[int]:
        """Get array property value.

        Args:
            node: Device tree node
            prop_name: Property name
            default: Default value

        Returns:
            List of integers
        """
        if default is None:
            default = []

        value = self._get_property_value(node, prop_name)
        if value is None:
            return default

        if isinstance(value, list):
            # Convert all elements to integers
            result = []
            for item in value:
                try:
                    if isinstance(item, str) and item.startswith("&"):
                        # Keep references as strings for now
                        result.append(item)
                    else:
                        result.append(int(item))
                except (ValueError, TypeError):
                    self.logger.warning("Failed to convert array item to int: %s", item)
            return result
        else:
            # Single value, convert to list
            try:
                return [int(value)]
            except (ValueError, TypeError):
                return default

    def _parse_enhanced_binding(self, binding_str: str) -> LayoutBinding:
        """Enhanced binding parser with better parameter type detection.

        Args:
            binding_str: Binding string to parse

        Returns:
            LayoutBinding with properly typed parameters
        """
        if not binding_str or not binding_str.strip():
            return LayoutBinding(value="&none", params=[])

        # Clean up the binding string
        binding_str = binding_str.strip()

        # Handle quoted parameters and complex expressions
        parts = self._parse_binding_parts(binding_str)
        if not parts:
            return LayoutBinding(value="&none", params=[])

        # First part is the behavior
        behavior = parts[0]
        if not behavior.startswith("&"):
            behavior = f"&{behavior}"

        # Convert remaining parts to LayoutParam objects with proper typing
        params = []
        for param_str in parts[1:]:
            param_value = self._convert_binding_parameter(param_str)
            params.append(LayoutParam(value=param_value, params=[]))

        return LayoutBinding(value=behavior, params=params)

    def _parse_binding_parts(self, binding_str: str) -> list[str]:
        """Parse binding string into parts, handling quoted parameters.

        Args:
            binding_str: Raw binding string

        Returns:
            List of string parts (behavior + parameters)
        """
        parts = []
        current_part = ""
        in_quotes = False
        quote_char = None

        i = 0
        while i < len(binding_str):
            char = binding_str[i]

            if char in ('"', "'") and not in_quotes:
                # Start of quoted section
                in_quotes = True
                quote_char = char
            elif char == quote_char and in_quotes:
                # End of quoted section
                in_quotes = False
                quote_char = None
            elif char.isspace() and not in_quotes:
                # Whitespace outside quotes - end current part
                if current_part:
                    parts.append(current_part)
                    current_part = ""
            else:
                # Regular character or whitespace inside quotes
                current_part += char

            i += 1

        # Add final part if exists
        if current_part:
            parts.append(current_part)

        return parts

    def _convert_binding_parameter(self, param_str: str) -> ParamValue:
        """Convert binding parameter with enhanced type detection.

        Args:
            param_str: Parameter string

        Returns:
            ParamValue with proper type (int or str)
        """
        if not isinstance(param_str, str):
            return str(param_str)

        # Remove quotes if present
        cleaned = param_str.strip()
        if (cleaned.startswith('"') and cleaned.endswith('"')) or (
            cleaned.startswith("'") and cleaned.endswith("'")
        ):
            return cleaned[1:-1]

        # Try to parse as integer (including hex)
        try:
            # Handle hexadecimal numbers
            if cleaned.startswith("0x") or cleaned.startswith("0X"):
                return int(cleaned, 16)
            # Handle decimal numbers
            return int(cleaned)
        except ValueError:
            # Return as string if not numeric
            return cleaned


class HoldTapConverter(ModelConverter):
    """Convert device tree hold-tap nodes to HoldTapBehavior models."""

    def convert(self, node: DTNode) -> HoldTapBehavior | None:
        """Convert hold-tap node to HoldTapBehavior.

        Args:
            node: Device tree node with hold-tap behavior

        Returns:
            HoldTapBehavior or None if conversion fails
        """
        try:
            # Extract name (use label if available, otherwise node name)
            name = node.label or node.name
            if not name.startswith("&"):
                name = f"&{name}"

            # Create base behavior
            behavior = HoldTapBehavior(
                name=name,
                description=self._extract_description(node),
            )

            # Map timing properties
            behavior.tapping_term_ms = self._get_int_property(node, "tapping-term-ms")
            behavior.quick_tap_ms = self._get_int_property(node, "quick-tap-ms")
            behavior.require_prior_idle_ms = self._get_int_property(
                node, "require-prior-idle-ms"
            )

            # Map flavor
            flavor = self._get_string_property(node, "flavor")
            if flavor:
                behavior.flavor = flavor

            # Map boolean properties
            behavior.hold_trigger_on_release = self._get_bool_property(
                node, "hold-trigger-on-release"
            )
            behavior.retro_tap = self._get_bool_property(node, "retro-tap")

            # Map hold trigger key positions
            key_positions = self._get_array_property(node, "hold-trigger-key-positions")
            if key_positions:
                behavior.hold_trigger_key_positions = key_positions

            # Map bindings
            bindings = self._parse_bindings_property(node, "bindings")
            if bindings:
                behavior.bindings = bindings

            return behavior

        except Exception as e:
            self.logger.error("Failed to convert hold-tap node '%s': %s", node.name, e)
            return None

    def _extract_description(self, node: DTNode) -> str:
        """Extract description from comments or label property.

        Args:
            node: Device tree node

        Returns:
            Description string
        """
        # Try label property first
        description = self._get_string_property(node, "label")
        if description:
            return description

        # Try to find description in comments
        for comment in node.comments:
            if not comment.text.startswith("//"):
                continue
            # Remove // and clean up
            desc = comment.text[2:].strip()
            if desc and not desc.startswith("TODO") and not desc.startswith("FIXME"):
                return desc

        return ""

    def _parse_bindings_property(self, node: DTNode, prop_name: str) -> list[str]:
        """Parse bindings property for hold-tap behaviors with enhanced reference handling.

        Args:
            node: Device tree node
            prop_name: Property name

        Returns:
            List of binding strings with proper reference formatting
        """
        value = self._get_property_value(node, prop_name)
        if not value:
            return []

        if isinstance(value, list):
            # Array of bindings
            bindings = []
            for item in value:
                if isinstance(item, str):
                    # Use enhanced reference conversion
                    binding = self._convert_reference_value(item.strip())
                    bindings.append(binding)
                else:
                    binding = self._convert_reference_value(str(item))
                    bindings.append(binding)
            return bindings
        else:
            # Single binding
            binding = self._convert_reference_value(str(value).strip())
            return [binding]


class MacroConverter(ModelConverter):
    """Convert device tree macro nodes to MacroBehavior models."""

    def convert(self, node: DTNode) -> MacroBehavior | None:
        """Convert macro node to MacroBehavior.

        Args:
            node: Device tree node with macro behavior

        Returns:
            MacroBehavior or None if conversion fails
        """
        try:
            # Extract name
            name = node.label or node.name
            if not name.startswith("&"):
                name = f"&{name}"
            
            # DEBUG: Log available metadata for this macro
            if "mod_tab_v1_TKZ" in name:
                self.logger.debug("=== Macro %s metadata ===", name)
                self.logger.debug("Node name: %s", node.name)
                self.logger.debug("Node label: %s", node.label)
                self.logger.debug("Node path: %s", node.path)
                self.logger.debug("Comments (%d total):", len(node.comments))
                for i, comment in enumerate(node.comments):
                    self.logger.debug("  %d: %r", i, comment.text)
                self.logger.debug("Properties (%d total):", len(node.properties))
                for prop_name, prop_value in node.properties.items():
                    self.logger.debug("  %s: %r", prop_name, prop_value)
                self.logger.debug("=== END DEBUG ===")

            # Create base behavior
            behavior = MacroBehavior(
                name=name,
                description=self._extract_description(node),
            )

            # Map timing properties
            behavior.wait_ms = self._get_int_property(node, "wait-ms")
            behavior.tap_ms = self._get_int_property(node, "tap-ms")

            # Parse bindings (more complex for macros)
            bindings = self._parse_macro_bindings(node)
            if bindings:
                behavior.bindings = bindings

            # Parse macro parameters from #binding-cells property
            binding_cells = self._get_int_property(node, "#binding-cells")
            if binding_cells is not None:
                if binding_cells == 0:
                    behavior.params = None
                elif binding_cells == 1:
                    behavior.params = ["code"]
                elif binding_cells == 2:
                    behavior.params = ["param1", "param2"]
                else:
                    self.logger.warning(
                        "Unexpected binding-cells value for macro %s: %s",
                        name, binding_cells
                    )
                    behavior.params = None

            return behavior

        except Exception as e:
            self.logger.error("Failed to convert macro node '%s': %s", node.name, e)
            return None

    def _extract_description(self, node: DTNode) -> str:
        """Extract description from comments or label property."""
        # First try to find comments (most descriptive)
        for comment in node.comments:
            if not comment.text.startswith("//"):
                continue
            desc = comment.text[2:].strip()
            if desc and not desc.startswith("TODO") and not desc.startswith("FIXME"):
                return desc

        # Fall back to label property but clean it up
        description = self._get_string_property(node, "label")
        if description:
            # Clean up label: remove quotes and ampersand prefix
            clean_desc = description.strip('"').strip("'")
            if clean_desc.startswith("&"):
                clean_desc = clean_desc[1:]  # Remove & prefix
            return clean_desc

        return ""

    def _parse_macro_bindings(self, node: DTNode) -> list[LayoutBinding]:
        """Parse macro bindings into LayoutBinding objects.

        Args:
            node: Device tree node

        Returns:
            List of LayoutBinding objects
        """
        bindings: list[LayoutBinding] = []
        value = self._get_property_value(node, "bindings")

        if not value:
            return bindings

        # Macro bindings can be complex with multiple formats
        if isinstance(value, list):
            # Array of binding expressions - need to group them properly
            # In device tree syntax, <&kp H &kp E> means two bindings: "&kp H" and "&kp E"
            i = 0
            while i < len(value):
                item = str(value[i]).strip()

                # Check if this is a behavior reference
                if item.startswith("&"):
                    # Look for parameters following this behavior
                    binding_parts = [item]
                    i += 1

                    # Collect parameters until we hit another behavior reference
                    while i < len(value) and not str(value[i]).startswith("&"):
                        binding_parts.append(str(value[i]).strip())
                        i += 1

                    # Join the parts to form the complete binding
                    binding_str = " ".join(binding_parts)
                    try:
                        binding = self._parse_enhanced_binding(binding_str)
                        bindings.append(binding)
                    except Exception as e:
                        self.logger.warning(
                            "Failed to parse macro binding '%s': %s", binding_str, e
                        )
                        # Create fallback binding
                        bindings.append(
                            LayoutBinding(value=binding_parts[0], params=[])
                        )
                else:
                    # Standalone parameter without behavior - skip it
                    i += 1
        else:
            # Single binding expression
            binding_str = str(value).strip()
            if binding_str:
                try:
                    binding = self._parse_enhanced_binding(binding_str)
                    bindings.append(binding)
                except Exception as e:
                    self.logger.warning(
                        "Failed to parse macro binding '%s': %s", binding_str, e
                    )
                    bindings.append(LayoutBinding(value=binding_str, params=[]))

        return bindings

    def _parse_single_binding(self, binding_str: str) -> LayoutBinding:
        """Parse single binding string into LayoutBinding with enhanced parameter handling.

        Args:
            binding_str: Binding string like "&kp A" or "&macro_tap"

        Returns:
            LayoutBinding object with properly typed parameters
        """
        # Use the enhanced binding parser
        return self._parse_enhanced_binding(binding_str)


class ComboConverter(ModelConverter):
    """Convert device tree combo nodes to ComboBehavior models."""

    def convert(self, node: DTNode) -> ComboBehavior | None:
        """Convert combo node to ComboBehavior.

        Args:
            node: Device tree node with combo definition

        Returns:
            ComboBehavior or None if conversion fails
        """
        try:
            # Extract name
            name = node.label or node.name

            # Get required properties
            key_positions = self._get_array_property(node, "key-positions")
            if not key_positions:
                self.logger.warning("Combo '%s' missing key-positions", name)
                return None

            # Parse binding
            binding = self._parse_combo_binding(node)
            if not binding:
                self.logger.warning("Combo '%s' missing bindings", name)
                return None

            # Create combo behavior
            behavior = ComboBehavior(
                name=name,
                description=self._extract_description(node),
                key_positions=key_positions,
                binding=binding,
            )

            # Optional properties
            behavior.timeout_ms = self._get_int_property(node, "timeout-ms")

            # Layers property
            layers = self._get_array_property(node, "layers")
            if layers:
                behavior.layers = layers

            return behavior

        except Exception as e:
            self.logger.error("Failed to convert combo node '%s': %s", node.name, e)
            return None

    def _extract_description(self, node: DTNode) -> str:
        """Extract description from comments."""
        for comment in node.comments:
            if not comment.text.startswith("//"):
                continue
            desc = comment.text[2:].strip()
            if desc and not desc.startswith("TODO") and not desc.startswith("FIXME"):
                return desc
        return ""

    def _parse_combo_binding(self, node: DTNode) -> LayoutBinding | None:
        """Parse combo binding into LayoutBinding object with enhanced parsing.

        Args:
            node: Device tree node

        Returns:
            LayoutBinding object or None
        """
        value = self._get_property_value(node, "bindings")
        if not value:
            return None

        # Handle array bindings (e.g., ['&kp', 'ESC'])
        if isinstance(value, list) and value:
            if len(value) >= 1:
                behavior = str(value[0]).strip()
                if not behavior.startswith("&"):
                    behavior = f"&{behavior}"

                # Convert parameters with proper typing
                params = []
                for param in value[1:]:
                    param_value = self._convert_binding_parameter(str(param))
                    params.append(LayoutParam(value=param_value, params=[]))
                return LayoutBinding(value=behavior, params=params)
            else:
                return LayoutBinding(value="&none", params=[])
        else:
            # Single string binding - use enhanced parser
            binding_str = str(value).strip()
            if not binding_str:
                return None

            return self._parse_enhanced_binding(binding_str)


class TapDanceConverter(ModelConverter):
    """Convert device tree tap-dance nodes to TapDanceBehavior models."""

    def convert(self, node: DTNode) -> TapDanceBehavior | None:
        """Convert tap-dance node to TapDanceBehavior.

        Args:
            node: Device tree node with tap-dance behavior

        Returns:
            TapDanceBehavior or None if conversion fails
        """
        try:
            # Extract name
            name = node.label or node.name
            if not name.startswith("&"):
                name = f"&{name}"

            # Create base behavior
            behavior = TapDanceBehavior(
                name=name,
                description=self._extract_description(node),
            )

            # Map timing properties
            behavior.tapping_term_ms = self._get_int_property(node, "tapping-term-ms")

            # Parse bindings
            bindings = self._parse_tap_dance_bindings(node)
            if bindings:
                behavior.bindings = bindings

            return behavior

        except Exception as e:
            self.logger.error("Failed to convert tap-dance node '%s': %s", node.name, e)
            return None

    def _extract_description(self, node: DTNode) -> str:
        """Extract description from comments or label property."""
        description = self._get_string_property(node, "label")
        if description:
            return description

        for comment in node.comments:
            if not comment.text.startswith("//"):
                continue
            desc = comment.text[2:].strip()
            if desc and not desc.startswith("TODO") and not desc.startswith("FIXME"):
                return desc

        return ""

    def _parse_tap_dance_bindings(self, node: DTNode) -> list[LayoutBinding]:
        """Parse tap-dance bindings into LayoutBinding objects.

        Args:
            node: Device tree node

        Returns:
            List of LayoutBinding objects
        """
        bindings: list[LayoutBinding] = []
        value = self._get_property_value(node, "bindings")

        if not value:
            return bindings

        # Tap-dance bindings are similar to macro bindings
        if isinstance(value, list):
            # Array of binding expressions
            i = 0
            while i < len(value):
                item = str(value[i]).strip()

                if item.startswith("&"):
                    # Look for parameters following this behavior
                    binding_parts = [item]
                    i += 1

                    # Collect parameters until we hit another behavior reference
                    while i < len(value) and not str(value[i]).startswith("&"):
                        binding_parts.append(str(value[i]).strip())
                        i += 1

                    # Join the parts to form the complete binding
                    binding_str = " ".join(binding_parts)
                    try:
                        binding = self._parse_enhanced_binding(binding_str)
                        bindings.append(binding)
                    except Exception as e:
                        self.logger.warning(
                            "Failed to parse tap-dance binding '%s': %s", binding_str, e
                        )
                        bindings.append(
                            LayoutBinding(value=binding_parts[0], params=[])
                        )
                else:
                    i += 1
        else:
            # Single binding expression
            binding_str = str(value).strip()
            if binding_str:
                try:
                    binding = self._parse_enhanced_binding(binding_str)
                    bindings.append(binding)
                except Exception as e:
                    self.logger.warning(
                        "Failed to parse tap-dance binding '%s': %s", binding_str, e
                    )
                    bindings.append(LayoutBinding(value=binding_str, params=[]))

        return bindings


class StickyKeyConverter(ModelConverter):
    """Convert device tree sticky-key nodes to StickyKeyBehavior models."""

    def convert(self, node: DTNode) -> StickyKeyBehavior | None:
        """Convert sticky-key node to StickyKeyBehavior.

        Args:
            node: Device tree node with sticky-key behavior

        Returns:
            StickyKeyBehavior or None if conversion fails
        """
        try:
            # Extract name
            name = node.label or node.name
            if not name.startswith("&"):
                name = f"&{name}"

            # Create base behavior
            behavior = StickyKeyBehavior(
                name=name,
                description=self._extract_description(node),
            )

            # Map timing and behavior properties
            behavior.release_after_ms = self._get_int_property(node, "release-after-ms")
            behavior.quick_release = self._get_bool_property(node, "quick-release")
            behavior.lazy = self._get_bool_property(node, "lazy")
            behavior.ignore_modifiers = self._get_bool_property(
                node, "ignore-modifiers"
            )

            # Parse bindings with enhanced parsing
            bindings = self._parse_sticky_key_bindings(node)
            if bindings:
                behavior.bindings = bindings

            return behavior

        except Exception as e:
            self.logger.error(
                "Failed to convert sticky-key node '%s': %s", node.name, e
            )
            return None

    def _extract_description(self, node: DTNode) -> str:
        """Extract description from comments or label property."""
        description = self._get_string_property(node, "label")
        if description:
            return description

        for comment in node.comments:
            if not comment.text.startswith("//"):
                continue
            desc = comment.text[2:].strip()
            if desc and not desc.startswith("TODO") and not desc.startswith("FIXME"):
                return desc

        return ""

    def _parse_sticky_key_bindings(self, node: DTNode) -> list[LayoutBinding]:
        """Parse sticky-key bindings into LayoutBinding objects.

        Args:
            node: Device tree node

        Returns:
            List of LayoutBinding objects
        """
        bindings: list[LayoutBinding] = []
        value = self._get_property_value(node, "bindings")

        if not value:
            return bindings

        if isinstance(value, list):
            # Array of bindings - each one should be parsed as a complete binding
            for item in value:
                if isinstance(item, str):
                    binding_str = item.strip()
                    if binding_str:
                        binding = self._parse_enhanced_binding(binding_str)
                        bindings.append(binding)
                else:
                    binding_str = str(item).strip()
                    if binding_str:
                        binding = self._parse_enhanced_binding(binding_str)
                        bindings.append(binding)
        else:
            # Single binding
            binding_str = str(value).strip()
            if binding_str:
                binding = self._parse_enhanced_binding(binding_str)
                bindings.append(binding)

        return bindings

    def _parse_bindings_property(self, node: DTNode, prop_name: str) -> list[str]:
        """Parse bindings property."""
        value = self._get_property_value(node, prop_name)
        if not value:
            return []

        if isinstance(value, list):
            bindings = []
            for item in value:
                if isinstance(item, str):
                    binding = item.strip()
                    if not binding.startswith("&") and binding != "":
                        binding = f"&{binding}"
                    bindings.append(binding)
                else:
                    bindings.append(str(item))
            return bindings
        else:
            binding = str(value).strip()
            if not binding.startswith("&") and binding != "":
                binding = f"&{binding}"
            return [binding]


class CapsWordConverter(ModelConverter):
    """Convert device tree caps-word nodes to CapsWordBehavior models."""

    def convert(self, node: DTNode) -> CapsWordBehavior | None:
        """Convert caps-word node to CapsWordBehavior.

        Args:
            node: Device tree node with caps-word behavior

        Returns:
            CapsWordBehavior or None if conversion fails
        """
        try:
            # Extract name
            name = node.label or node.name
            if not name.startswith("&"):
                name = f"&{name}"

            # Create base behavior
            behavior = CapsWordBehavior(
                name=name,
                description=self._extract_description(node),
            )

            # Map properties
            continue_list = self._get_array_property(node, "continue-list")
            if continue_list:
                behavior.continue_list = [str(item) for item in continue_list]

            behavior.mods = self._get_int_property(node, "mods")

            return behavior

        except Exception as e:
            self.logger.error("Failed to convert caps-word node '%s': %s", node.name, e)
            return None

    def _extract_description(self, node: DTNode) -> str:
        """Extract description from comments or label property."""
        description = self._get_string_property(node, "label")
        if description:
            return description

        for comment in node.comments:
            if not comment.text.startswith("//"):
                continue
            desc = comment.text[2:].strip()
            if desc and not desc.startswith("TODO") and not desc.startswith("FIXME"):
                return desc

        return ""


class ModMorphConverter(ModelConverter):
    """Convert device tree mod-morph nodes to ModMorphBehavior models."""

    def convert(self, node: DTNode) -> ModMorphBehavior | None:
        """Convert mod-morph node to ModMorphBehavior.

        Args:
            node: Device tree node with mod-morph behavior

        Returns:
            ModMorphBehavior or None if conversion fails
        """
        try:
            # Extract name
            name = node.label or node.name
            if not name.startswith("&"):
                name = f"&{name}"

            # Get required mods property
            mods = self._get_int_property(node, "mods")
            if mods is None:
                self.logger.warning("Mod-morph '%s' missing mods property", name)
                return None

            # Create base behavior
            behavior = ModMorphBehavior(
                name=name,
                description=self._extract_description(node),
                mods=mods,
            )

            # Map optional properties
            behavior.keep_mods = self._get_int_property(node, "keep-mods")

            # Parse bindings
            bindings = self._parse_mod_morph_bindings(node)
            if bindings:
                behavior.bindings = bindings

            return behavior

        except Exception as e:
            self.logger.error("Failed to convert mod-morph node '%s': %s", node.name, e)
            return None

    def _extract_description(self, node: DTNode) -> str:
        """Extract description from comments or label property."""
        description = self._get_string_property(node, "label")
        if description:
            return description

        for comment in node.comments:
            if not comment.text.startswith("//"):
                continue
            desc = comment.text[2:].strip()
            if desc and not desc.startswith("TODO") and not desc.startswith("FIXME"):
                return desc

        return ""

    def _parse_mod_morph_bindings(self, node: DTNode) -> list[LayoutBinding]:
        """Parse mod-morph bindings (should be exactly 2)."""
        bindings: list[LayoutBinding] = []
        value = self._get_property_value(node, "bindings")

        if not value:
            return bindings

        if isinstance(value, list):
            # Array of two bindings
            i = 0
            while i < len(value) and len(bindings) < 2:
                item = str(value[i]).strip()

                if item.startswith("&"):
                    # Look for parameters following this behavior
                    binding_parts = [item]
                    i += 1

                    # Collect parameters until we hit another behavior reference or end
                    while (
                        i < len(value)
                        and not str(value[i]).startswith("&")
                        and len(bindings) < 1
                    ):
                        binding_parts.append(str(value[i]).strip())
                        i += 1

                    # Join the parts to form the complete binding
                    binding_str = " ".join(binding_parts)
                    try:
                        binding = self._parse_enhanced_binding(binding_str)
                        bindings.append(binding)
                    except Exception as e:
                        self.logger.warning(
                            "Failed to parse mod-morph binding '%s': %s", binding_str, e
                        )
                        bindings.append(
                            LayoutBinding(value=binding_parts[0], params=[])
                        )
                else:
                    i += 1

        return bindings

    def _parse_single_binding(self, binding_str: str) -> LayoutBinding:
        """Parse single binding string into LayoutBinding with enhanced parsing."""
        return self._parse_enhanced_binding(binding_str)


class UniversalModelConverter:
    """Universal converter that handles all behavior types."""

    def __init__(self) -> None:
        """Initialize universal converter."""
        self.hold_tap_converter = HoldTapConverter()
        self.macro_converter = MacroConverter()
        self.combo_converter = ComboConverter()
        self.tap_dance_converter = TapDanceConverter()
        self.sticky_key_converter = StickyKeyConverter()
        self.caps_word_converter = CapsWordConverter()
        self.mod_morph_converter = ModMorphConverter()
        self.logger = logging.getLogger(__name__)

    def convert_behaviors(
        self, behaviors_dict: dict[str, list[DTNode]]
    ) -> dict[str, list[Any]]:
        """Convert all behavior types from AST nodes to models.

        Args:
            behaviors_dict: Dictionary of behavior type to nodes

        Returns:
            Dictionary of behavior type to converted models
        """
        results: dict[str, list[Any]] = {
            "hold_taps": [],
            "macros": [],
            "combos": [],
            "tap_dances": [],
            "sticky_keys": [],
            "caps_word": [],
            "mods": [],
            "other_behaviors": [],
        }

        # Convert hold-tap behaviors
        for node in behaviors_dict.get("hold_taps", []):
            hold_tap_behavior = self.hold_tap_converter.convert(node)
            if hold_tap_behavior:
                results["hold_taps"].append(hold_tap_behavior)

        # Convert macros
        for node in behaviors_dict.get("macros", []):
            macro_behavior = self.macro_converter.convert(node)
            if macro_behavior:
                results["macros"].append(macro_behavior)

        # Convert combos
        for node in behaviors_dict.get("combos", []):
            combo_behavior = self.combo_converter.convert(node)
            if combo_behavior:
                results["combos"].append(combo_behavior)

        # Convert tap-dances
        for node in behaviors_dict.get("tap_dances", []):
            tap_dance_behavior = self.tap_dance_converter.convert(node)
            if tap_dance_behavior:
                results["tap_dances"].append(tap_dance_behavior)

        # Convert sticky-keys
        for node in behaviors_dict.get("sticky_keys", []):
            sticky_key_behavior = self.sticky_key_converter.convert(node)
            if sticky_key_behavior:
                results["sticky_keys"].append(sticky_key_behavior)

        # Convert caps-word behaviors
        for node in behaviors_dict.get("caps_word", []):
            caps_word_behavior = self.caps_word_converter.convert(node)
            if caps_word_behavior:
                results["caps_word"].append(caps_word_behavior)

        # Convert mod-morph behaviors
        for node in behaviors_dict.get("mods", []):
            mod_morph_behavior = self.mod_morph_converter.convert(node)
            if mod_morph_behavior:
                results["mods"].append(mod_morph_behavior)

        # Log conversion summary
        total_converted = sum(len(behaviors) for behaviors in results.values())
        total_input = sum(len(nodes) for nodes in behaviors_dict.values())
        self.logger.debug(
            "Converted %d/%d behaviors: %s",
            total_converted,
            total_input,
            {k: len(v) for k, v in results.items() if v},
        )

        return results


def create_hold_tap_converter() -> HoldTapConverter:
    """Create hold-tap converter instance.

    Returns:
        Configured HoldTapConverter
    """
    return HoldTapConverter()


def create_macro_converter() -> MacroConverter:
    """Create macro converter instance.

    Returns:
        Configured MacroConverter
    """
    return MacroConverter()


def create_combo_converter() -> ComboConverter:
    """Create combo converter instance.

    Returns:
        Configured ComboConverter
    """
    return ComboConverter()


def create_tap_dance_converter() -> TapDanceConverter:
    """Create tap-dance converter instance.

    Returns:
        Configured TapDanceConverter
    """
    return TapDanceConverter()


def create_sticky_key_converter() -> StickyKeyConverter:
    """Create sticky-key converter instance.

    Returns:
        Configured StickyKeyConverter
    """
    return StickyKeyConverter()


def create_caps_word_converter() -> CapsWordConverter:
    """Create caps-word converter instance.

    Returns:
        Configured CapsWordConverter
    """
    return CapsWordConverter()


def create_mod_morph_converter() -> ModMorphConverter:
    """Create mod-morph converter instance.

    Returns:
        Configured ModMorphConverter
    """
    return ModMorphConverter()


def create_universal_model_converter() -> UniversalModelConverter:
    """Create universal model converter instance.

    Returns:
        Configured UniversalModelConverter
    """
    return UniversalModelConverter()
