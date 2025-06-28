"""Converters from AST nodes to glovebox behavior models."""

import logging
from typing import Any

from glovebox.layout.models import (
    ComboBehavior,
    HoldTapBehavior,
    LayoutBinding,
    LayoutParam,
    MacroBehavior,
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
        """Get property value from node.

        Args:
            node: Device tree node
            prop_name: Property name (with dashes)
            default: Default value if property not found

        Returns:
            Property value or default
        """
        # Try both dash and underscore versions
        prop_names = [prop_name, prop_name.replace("-", "_")]

        for name in prop_names:
            prop = node.get_property(name)
            if prop and prop.value:
                return self._convert_dt_value(prop.value)

        return default

    def _convert_dt_value(self, dt_value: DTValue) -> Any:
        """Convert DTValue to appropriate Python type.

        Args:
            dt_value: Device tree value

        Returns:
            Converted value
        """
        if (
            dt_value.type == DTValueType.STRING
            or dt_value.type == DTValueType.INTEGER
            or dt_value.type == DTValueType.ARRAY
        ):
            return dt_value.value
        elif dt_value.type == DTValueType.REFERENCE:
            return f"&{dt_value.value}"
        elif dt_value.type == DTValueType.BOOLEAN:
            return dt_value.value
        else:
            return dt_value.value

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
        """Parse bindings property for hold-tap behaviors.

        Args:
            node: Device tree node
            prop_name: Property name

        Returns:
            List of binding strings
        """
        value = self._get_property_value(node, prop_name)
        if not value:
            return []

        if isinstance(value, list):
            # Array of bindings
            bindings = []
            for item in value:
                if isinstance(item, str):
                    # Clean up reference formatting
                    binding = item.strip()
                    if not binding.startswith("&") and binding != "":
                        binding = f"&{binding}"
                    bindings.append(binding)
                else:
                    bindings.append(str(item))
            return bindings
        else:
            # Single binding
            binding = str(value).strip()
            if not binding.startswith("&") and binding != "":
                binding = f"&{binding}"
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

            return behavior

        except Exception as e:
            self.logger.error("Failed to convert macro node '%s': %s", node.name, e)
            return None

    def _extract_description(self, node: DTNode) -> str:
        """Extract description from comments or label property."""
        # Same logic as HoldTapConverter
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
            # Array of binding expressions
            for item in value:
                binding_str = str(item).strip()
                if binding_str:
                    try:
                        binding = self._parse_single_binding(binding_str)
                        bindings.append(binding)
                    except Exception as e:
                        self.logger.warning(
                            "Failed to parse macro binding '%s': %s", binding_str, e
                        )
                        # Create fallback binding
                        bindings.append(LayoutBinding(value=binding_str, params=[]))
        else:
            # Single binding expression
            binding_str = str(value).strip()
            if binding_str:
                try:
                    binding = self._parse_single_binding(binding_str)
                    bindings.append(binding)
                except Exception as e:
                    self.logger.warning(
                        "Failed to parse macro binding '%s': %s", binding_str, e
                    )
                    bindings.append(LayoutBinding(value=binding_str, params=[]))

        return bindings

    def _parse_single_binding(self, binding_str: str) -> LayoutBinding:
        """Parse single binding string into LayoutBinding.

        Args:
            binding_str: Binding string like "&kp A" or "&macro_tap"

        Returns:
            LayoutBinding object
        """
        # Split into parts
        parts = binding_str.split()
        if not parts:
            return LayoutBinding(value="&none", params=[])

        # First part is the behavior
        behavior = parts[0]
        if not behavior.startswith("&"):
            behavior = f"&{behavior}"

        # Rest are parameters - convert to LayoutParam objects
        params = [LayoutParam(value=param) for param in parts[1:]] if len(parts) > 1 else []

        return LayoutBinding(value=behavior, params=params)


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
        """Parse combo binding into LayoutBinding object.

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
                
                # Parameters are the remaining elements
                params = [LayoutParam(value=str(param)) for param in value[1:]]
                return LayoutBinding(value=behavior, params=params)
            else:
                return LayoutBinding(value="&none", params=[])
        else:
            # Single string binding
            binding_str = str(value).strip()
            if not binding_str:
                return None

            # Parse binding string
            parts = binding_str.split()
            if not parts:
                return LayoutBinding(value="&none", params=[])

            behavior = parts[0]
            if not behavior.startswith("&"):
                behavior = f"&{behavior}"

            params = [LayoutParam(value=param) for param in parts[1:]] if len(parts) > 1 else []
            return LayoutBinding(value=behavior, params=params)


class UniversalModelConverter:
    """Universal converter that handles all behavior types."""

    def __init__(self) -> None:
        """Initialize universal converter."""
        self.hold_tap_converter = HoldTapConverter()
        self.macro_converter = MacroConverter()
        self.combo_converter = ComboConverter()
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

        # TODO: Add tap-dance and other behavior converters when needed

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


def create_universal_model_converter() -> UniversalModelConverter:
    """Create universal model converter instance.

    Returns:
        Configured UniversalModelConverter
    """
    return UniversalModelConverter()
