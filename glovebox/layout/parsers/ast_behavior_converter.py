"""AST-based behavior converter for extracting behaviors from device tree nodes."""

import logging
from typing import Any

from glovebox.layout.models import (
    ComboBehavior,
    HoldTapBehavior,
    LayoutBinding,
    MacroBehavior,
)
from glovebox.layout.parsers.ast_nodes import DTNode, DTProperty, DTValue, DTValueType


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

            # Add & prefix for JSON format consistency
            behavior_name = f"&{name}"

            # Get description from comments or properties
            description = self._extract_description_from_node(node)

            # Create base behavior
            hold_tap = HoldTapBehavior(name=behavior_name, description=description)

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

            # Add & prefix for JSON format consistency
            behavior_name = f"&{name}"

            # Get description from comments or properties
            description = self._extract_description_from_node(node)

            # Create base behavior
            macro = MacroBehavior(name=behavior_name, description=description)

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

            # Combos use plain names without & prefix in JSON format
            # Also strip "combo_" prefix if present (device tree vs JSON format difference)
            behavior_name = name
            if behavior_name.startswith("combo_"):
                behavior_name = behavior_name[6:]  # Remove "combo_" prefix

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
                name=behavior_name,
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
            # Concatenate all consecutive description comments
            comment_lines = []
            for comment in node.comments:
                comment_text = comment.text
                # Skip property-like comments (they're not descriptions)
                if not comment_text.strip().startswith("#"):
                    # Clean up comment markers
                    if comment_text.startswith("//"):
                        cleaned_text = comment_text[2:].strip()
                    elif comment_text.startswith("/*") and comment_text.endswith("*/"):
                        cleaned_text = comment_text[2:-2].strip()
                    else:
                        cleaned_text = comment_text.strip()

                    # Add all comment lines, including empty ones for proper formatting
                    comment_lines.append(cleaned_text)

            if comment_lines:
                # Join all lines and clean up excessive whitespace while preserving structure
                description = "\n".join(comment_lines).strip()
                # Remove excessive empty lines but preserve single empty lines for formatting
                import re
                description = re.sub(r'\n\s*\n\s*\n+', '\n\n', description)
                return description

        # Priority 2: Comments from parent node (for behaviors in behaviors blocks)
        if hasattr(node, "parent") and node.parent and node.parent.comments:
            # Look for consecutive description comments in parent
            comment_lines = []
            for comment in reversed(node.parent.comments):
                comment_text = comment.text
                # Skip property-like comments
                if not comment_text.strip().startswith("#"):
                    # Clean up comment markers
                    if comment_text.startswith("//"):
                        cleaned_text = comment_text[2:].strip()
                    elif comment_text.startswith("/*") and comment_text.endswith("*/"):
                        cleaned_text = comment_text[2:-2].strip()
                    else:
                        cleaned_text = comment_text.strip()

                    # Add all comment lines, including empty ones for proper formatting
                    comment_lines.append(cleaned_text)

            if comment_lines:
                # Reverse to get original order since we processed in reverse
                comment_lines.reverse()
                # Join all lines and clean up excessive whitespace while preserving structure
                description = "\n".join(comment_lines).strip()
                # Remove excessive empty lines but preserve single empty lines for formatting
                import re
                description = re.sub(r'\n\s*\n\s*\n+', '\n\n', description)
                return description

        # Priority 3: Description property
        description_prop = node.get_property("description")
        if description_prop and description_prop.value:
            return self._extract_string_from_property(description_prop)

        # Priority 4: Label property (cleaned up)
        label_prop = node.get_property("label")
        if label_prop and label_prop.value:
            label_value = self._extract_string_from_property(label_prop)
            # Clean up common label patterns
            if label_value.startswith("&"):
                return label_value
            return label_value

        return ""

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

        # Hold trigger key positions array
        hold_trigger_positions_prop = node.get_property("hold-trigger-key-positions")
        if hold_trigger_positions_prop:
            positions = self._extract_array_from_property(hold_trigger_positions_prop)
            if positions:
                hold_tap.hold_trigger_key_positions = positions

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

        # Binding cells for parameter configuration - this has highest priority

        # Try different property name formats for #binding-cells
        binding_cells_prop = (
            node.get_property("#binding-cells")
            or node.get_property("binding-cells")
            or node.get_property("binding_cells")
        )
        if binding_cells_prop:
            binding_cells = self._extract_int_from_property(binding_cells_prop)
            if binding_cells == 0:
                macro.params = []
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
            self.logger.debug(
                "Using #binding-cells=%d for macro %s: %s",
                binding_cells,
                macro.name,
                macro.params,
            )
        else:
            # Fallback: infer from compatible property when #binding-cells is missing
            compatible_prop = node.get_property("compatible")
            if compatible_prop:
                compatible_value = self._extract_string_from_property(compatible_prop)

                if compatible_value == "zmk,behavior-macro-one-param":
                    macro.params = ["code"]
                    self.logger.warning(
                        "Missing #binding-cells for macro %s, inferred 1 parameter from compatible property '%s'. Consider adding #binding-cells = <1>; to the macro definition.",
                        macro.name,
                        compatible_value,
                    )
                elif compatible_value == "zmk,behavior-macro-two-param":
                    macro.params = ["param1", "param2"]
                    self.logger.warning(
                        "Missing #binding-cells for macro %s, inferred 2 parameters from compatible property '%s'. Consider adding #binding-cells = <2>; to the macro definition.",
                        macro.name,
                        compatible_value,
                    )
                elif compatible_value == "zmk,behavior-macro":
                    # Standard macro with no parameters by default
                    macro.params = []
                    self.logger.warning(
                        "Missing #binding-cells for macro %s, inferred 0 parameters from compatible property '%s'. Consider adding #binding-cells = <0>; to the macro definition.",
                        macro.name,
                        compatible_value,
                    )

        # If we haven't set params yet, warn and default to empty
        if not hasattr(macro, "params") or macro.params is None:
            self.logger.warning(
                "Unable to determine parameter count for macro %s - missing #binding-cells and unrecognized compatible property. Defaulting to no parameters. Please add #binding-cells property to the macro definition.",
                macro.name,
            )
            macro.params = []

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
        else:
            # Fallback: when layers property is missing, add placeholder
            # This ensures combos have the required layers field with a default value
            combo.layers = [-1]
            self.logger.debug("Added placeholder layers [-1] for combo %s", combo.name)

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
        elif prop.value.type == DTValueType.ARRAY:
            # Handle array values like ['1']
            try:
                if prop.value.value and len(prop.value.value) > 0:
                    # Take the first element of the array
                    first_value = prop.value.value[0]
                    return int(str(first_value).strip("<>"))
            except (ValueError, IndexError):
                return None
        else:
            # Try to parse from raw value
            try:
                raw_value = prop.value.raw.strip("<>")
                return int(raw_value)
            except ValueError:
                return None

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
                # Group behavior references with their parameters like in keymap_parser.py
                # In device tree syntax, <&kp HOME &kp LS(END)> means two bindings: "&kp HOME" and "&kp LS(END)"
                i = 0
                values = prop.value.value
                while i < len(values):
                    item = str(values[i]).strip()

                    # Check if this is a behavior reference
                    if item.startswith("&"):
                        # Look for parameters following this behavior
                        binding_parts = [item]
                        i += 1

                        # Collect parameters until we hit another behavior reference or end of array
                        while i < len(values):
                            next_item = str(values[i]).strip()
                            # Stop if we hit another behavior reference
                            if next_item.startswith("&"):
                                break
                            # Collect this parameter
                            binding_parts.append(next_item)
                            i += 1

                        # Join the parts to form the complete binding
                        binding_str = " ".join(binding_parts)

                        # Log the binding string for debugging parameter issues
                        if self.logger.isEnabledFor(logging.DEBUG):
                            self.logger.debug(
                                "Converting macro binding: '%s' from parts: %s",
                                binding_str,
                                binding_parts,
                            )

                        try:
                            binding = LayoutBinding.from_str(binding_str)
                            bindings.append(binding)

                            # Debug log the parsed parameters
                            if self.logger.isEnabledFor(logging.DEBUG):
                                param_strs = [str(p.value) for p in binding.params]
                                self.logger.debug(
                                    "Parsed macro binding '%s' with %d params: %s",
                                    binding.value,
                                    len(binding.params),
                                    param_strs,
                                )
                        except Exception as e:
                            exc_info = self.logger.isEnabledFor(logging.DEBUG)
                            self.logger.error(
                                "Failed to parse macro binding '%s': %s",
                                binding_str,
                                e,
                                exc_info=exc_info,
                            )
                            # Create fallback binding with empty params
                            bindings.append(
                                LayoutBinding(value=binding_parts[0], params=[])
                            )
                    else:
                        # Standalone parameter without behavior - this shouldn't happen in well-formed macro
                        self.logger.warning(
                            "Found standalone parameter '%s' without behavior reference in macro",
                            item,
                        )
                        i += 1
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
            # Debug: log the raw value and array value
            self.logger.debug(
                "Processing combo binding - raw: '%s', type: %s",
                prop.value.raw if prop.value else "None",
                prop.value.type if prop.value else "None",
            )
            if prop.value and prop.value.type == DTValueType.ARRAY:
                self.logger.debug("Array value: %s", prop.value.value)

            # Try raw parsing first to preserve complex nested structures like LG(LA(LC(LSHFT)))
            raw_value = prop.value.raw.strip()
            # Remove angle brackets properly
            import re

            cleaned_raw = re.sub(r"<\s*([^>]+)\s*>", r"\1", raw_value).strip()

            # Check if this looks like a malformed nested structure before parsing
            if cleaned_raw and cleaned_raw.startswith("&"):
                # If it contains spaced parentheses, fix them and try parsing
                if "( " in cleaned_raw or " )" in cleaned_raw:
                    self.logger.debug(
                        "Raw value has spaced parentheses, attempting to fix and parse directly"
                    )
                    # Fix the spaced parentheses by removing spaces around them
                    fixed_raw = cleaned_raw.replace(" ( ", "(").replace(" )", ")")
                    try:
                        return LayoutBinding.from_str(fixed_raw)
                    except Exception as e:
                        self.logger.debug(
                            "Failed to parse fixed raw value '%s': %s", fixed_raw, e
                        )
                        # Fall through to array reconstruction
                else:
                    return LayoutBinding.from_str(cleaned_raw)

            # Fallback to array parsing for simpler cases
            if prop.value.type == DTValueType.ARRAY and prop.value.value:
                # Reconstruct complete binding string from array elements
                binding_parts = []
                for value in prop.value.value:
                    if isinstance(value, str) and value.strip():
                        binding_parts.append(str(value).strip())

                if binding_parts and binding_parts[0].startswith("&"):
                    # Smart reconstruction for nested function calls
                    complete_binding = self._reconstruct_nested_function_call(
                        binding_parts
                    )
                    return LayoutBinding.from_str(complete_binding)

            # Return fallback binding
            return LayoutBinding(value="&none", params=[])
        except Exception as e:
            self.logger.warning(
                "Failed to parse combo binding '%s': %s", prop.value.raw, e
            )
            # Return fallback binding
            return LayoutBinding(value="&none", params=[])

    def _reconstruct_nested_function_call(self, parts: list[str]) -> str:
        """Reconstruct nested function call from tokenized parts.

        Converts ['&sk', 'LG', '(', 'LA', '(', 'LC', '(', 'LSHFT', ')', ')', ')']
        to '&sk LG(LA(LC(LSHFT)))'

        Args:
            parts: List of string tokens

        Returns:
            Reconstructed function call string
        """
        if not parts:
            return ""

        # Simple case: no parentheses, just join with spaces
        if "(" not in parts and ")" not in parts:
            return " ".join(parts)

        # Complex case: reconstruct nested function calls
        result = []
        i = 0

        while i < len(parts):
            part = parts[i]

            # If we find an opening parenthesis after a function name
            if i + 1 < len(parts) and parts[i + 1] == "(":
                # This is a function call, find the matching closing parenthesis
                func_name = part
                paren_depth = 0
                j = i + 1
                func_parts = []

                while j < len(parts):
                    if parts[j] == "(":
                        paren_depth += 1
                        if paren_depth == 1:
                            # Skip the opening parenthesis
                            pass
                        else:
                            func_parts.append(parts[j])
                    elif parts[j] == ")":
                        paren_depth -= 1
                        if paren_depth == 0:
                            # Found matching closing parenthesis
                            break
                        else:
                            func_parts.append(parts[j])
                    else:
                        func_parts.append(parts[j])
                    j += 1

                # Recursively reconstruct the function arguments
                if func_parts:
                    inner_call = self._reconstruct_nested_function_call(func_parts)
                    result.append(f"{func_name}({inner_call})")
                else:
                    result.append(f"{func_name}()")

                i = j + 1  # Skip past the closing parenthesis
            else:
                # Regular part, add as-is
                result.append(part)
                i += 1

        return " ".join(result)


def create_ast_behavior_converter() -> ASTBehaviorConverter:
    """Create AST behavior converter instance.

    Returns:
        Configured ASTBehaviorConverter instance
    """
    return ASTBehaviorConverter()
