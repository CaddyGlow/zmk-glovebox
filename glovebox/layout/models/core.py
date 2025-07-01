"""Core layout models for keyboard layouts."""

from typing import Any

from pydantic import Field, field_validator

from glovebox.layout.behavior.models import ParamValue
from glovebox.models.base import GloveboxBaseModel


class LayoutParam(GloveboxBaseModel):
    """Model for parameter values in key bindings."""

    value: ParamValue
    params: list["LayoutParam"] = Field(default_factory=list)


# Recursive type reference for LayoutParam
LayoutParam.model_rebuild()


class LayoutBinding(GloveboxBaseModel):
    """Model for individual key bindings."""

    value: str
    params: list[LayoutParam] = Field(default_factory=list)

    @property
    def behavior(self) -> str:
        """Get the behavior code."""
        return self.value

    @classmethod
    def from_str(cls, behavior_str: str) -> "LayoutBinding":
        """Parse ZMK behavior string into LayoutBinding with nested parameter support.

        Args:
            behavior_str: ZMK behavior string like "&kp Q", "&trans", "&mt LCTRL A", "&kp LC(X)"

        Returns:
            LayoutBinding instance

        Raises:
            ValueError: If behavior string is invalid or malformed

        Examples:
            "&kp Q" -> LayoutBinding(value="&kp", params=[LayoutParam(value="Q")])
            "&trans" -> LayoutBinding(value="&trans", params=[])
            "&mt LCTRL A" -> LayoutBinding(value="&mt", params=[LayoutParam(value="LCTRL"), LayoutParam(value="A")])
            "&kp LC(X)" -> LayoutBinding(value="&kp", params=[LayoutParam(value="LC", params=[LayoutParam(value="X")])])
        """
        import logging

        logger = logging.getLogger(__name__)

        # Handle empty or whitespace-only strings
        if not behavior_str or not behavior_str.strip():
            raise ValueError("Behavior string cannot be empty")

        # Try nested parameter parsing first (handles both simple and complex cases)
        try:
            return cls._parse_nested_binding(behavior_str.strip())
        except Exception as e:
            # Fall back to simple parsing for quote handling compatibility
            try:
                return cls._parse_simple_binding(behavior_str.strip())
            except Exception as fallback_e:
                exc_info = logger.isEnabledFor(logging.DEBUG)
                logger.error(
                    "Failed to parse binding '%s' with both nested (%s) and simple (%s) parsing",
                    behavior_str,
                    e,
                    fallback_e,
                    exc_info=exc_info,
                )
                raise ValueError(f"Invalid behavior string: {behavior_str}") from e

    @staticmethod
    def _parse_behavior_parts(behavior_str: str) -> list[str]:
        """Parse behavior string into parts, handling quoted parameters.

        Args:
            behavior_str: Raw behavior string

        Returns:
            List of string parts (behavior + parameters)
        """
        parts = []
        current_part = ""
        in_quotes = False
        quote_char = None

        i = 0
        while i < len(behavior_str):
            char = behavior_str[i]

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

    @staticmethod
    def _parse_param_value(param_str: str) -> ParamValue:
        """Parse parameter string into appropriate type.

        Args:
            param_str: Parameter string

        Returns:
            ParamValue (str or int)
        """
        # Remove quotes if present
        if (param_str.startswith('"') and param_str.endswith('"')) or (
            param_str.startswith("'") and param_str.endswith("'")
        ):
            return param_str[1:-1]

        # Try to parse as integer
        try:
            return int(param_str)
        except ValueError:
            # Return as string if not an integer
            return param_str

    @classmethod
    def _parse_nested_binding(cls, binding_str: str) -> "LayoutBinding":
        """Parse binding string with nested parameter support.

        Handles structures like:
        - &sk LA(LC(LSHFT)) -> nested with parentheses
        - &kp LC X -> creates LC containing X as nested parameter
        - &mt LCTRL A -> creates LCTRL and A as nested chain
        - &kp Q -> single parameter

        Args:
            binding_str: Binding string to parse

        Returns:
            LayoutBinding with nested parameter structure
        """
        if not binding_str.strip():
            return LayoutBinding(value="&none", params=[])

        # Tokenize the binding string
        tokens = cls._tokenize_binding(binding_str)
        if not tokens:
            return LayoutBinding(value="&none", params=[])

        # First token should be the behavior
        behavior = tokens[0]
        if not behavior.startswith("&"):
            behavior = f"&{behavior}"

        # Parse remaining tokens as nested parameters
        if len(tokens) == 1:
            # No parameters
            return cls(value=behavior, params=[])
        elif len(tokens) == 2:
            # Single parameter - could be nested or simple
            param, _ = cls._parse_nested_parameter(tokens, 1)
            return cls(value=behavior, params=[param] if param else [])
        else:
            # Multiple parameters - create nested chain
            # For "&kp LC X", create LC containing X
            # For "&mt LCTRL A", create LCTRL and A as separate params
            params = []

            # Check behavior type to determine parameter structure
            behavior_name = behavior.lower()

            # Behaviors that should have flat parameters (multiple separate params)
            flat_param_behaviors: tuple[str, ...] = ("&mt", "&lt", "&caps_word")
            # Add HRM behaviors and other custom behaviors that expect flat params
            if any(
                hrm in behavior_name for hrm in ("&hrm_", "&caps", "&thumb", "&space")
            ):
                flat_param_behaviors = flat_param_behaviors + (behavior_name,)

            if behavior_name in flat_param_behaviors:
                # These behaviors expect flat parameters
                for i in range(1, len(tokens)):
                    param_value = cls._parse_param_value(tokens[i])
                    params.append(LayoutParam(value=param_value, params=[]))
            elif behavior_name in ("&kp", "&key_repeat") and not any(
                "(" in token for token in tokens[1:]
            ):
                # These behaviors use nested structure for modifier patterns
                # Check if this is a modifier chain (LC, LS, G -> LC(LS(G)))
                modifier_commands = ("lc", "la", "lg", "ls", "rc", "ra", "rg", "rs")
                param_tokens = tokens[1:]

                # Check if all parameters are modifiers or if first parameter is a modifier
                if param_tokens and param_tokens[0].lower() in modifier_commands:
                    # Create nested modifier chain for any length
                    params.append(cls._create_modifier_chain(param_tokens))
                else:
                    # Single parameter for non-modifier cases
                    param_value = cls._parse_param_value(tokens[1])
                    params.append(LayoutParam(value=param_value, params=[]))
            else:
                # Handle complex cases with parentheses or other behaviors
                if any("(" in token for token in tokens[1:]):
                    # Use the existing nested parameter parsing for complex parenthetical structures
                    i = 1
                    while i < len(tokens):
                        param, i = cls._parse_nested_parameter(tokens, i)
                        if param:
                            params.append(param)
                else:
                    # Default: most other behaviors with 2+ parameters expect flat structure
                    for i in range(1, len(tokens)):
                        param_value = cls._parse_param_value(tokens[i])
                        params.append(LayoutParam(value=param_value, params=[]))

            return cls(value=behavior, params=params)

    @classmethod
    def _create_modifier_chain(cls, param_tokens: list[str]) -> LayoutParam:
        """Create nested modifier chain from parameter tokens.

        Converts ["LC", "LS", "G"] to LC(LS(G)) structure.

        Args:
            param_tokens: List of parameter tokens where first tokens are modifiers

        Returns:
            LayoutParam with nested modifier structure
        """
        if not param_tokens:
            return LayoutParam(value="", params=[])

        if len(param_tokens) == 1:
            # Single parameter, no nesting needed
            param_value = cls._parse_param_value(param_tokens[0])
            return LayoutParam(value=param_value, params=[])

        # Start with the last parameter (the actual key)
        innermost_param = LayoutParam(
            value=cls._parse_param_value(param_tokens[-1]), params=[]
        )

        # Work backwards through modifiers, wrapping each level
        current_param = innermost_param
        for modifier_token in reversed(param_tokens[:-1]):
            modifier_value = cls._parse_param_value(modifier_token)
            current_param = LayoutParam(value=modifier_value, params=[current_param])

        return current_param

    @staticmethod
    def _tokenize_binding(binding_str: str) -> list[str]:
        """Tokenize binding string preserving parentheses structure.

        For '&sk LA(LC(LSHFT))', this should produce:
        ['&sk', 'LA(LC(LSHFT))']

        Args:
            binding_str: Raw binding string

        Returns:
            List of tokens
        """
        tokens = []
        current_token = ""
        paren_depth = 0

        i = 0
        while i < len(binding_str):
            char = binding_str[i]

            if char.isspace() and paren_depth == 0:
                # Space outside parentheses - end current token
                if current_token:
                    tokens.append(current_token)
                    current_token = ""
            elif char == "(":
                # Start of nested parameters - include in current token
                current_token += char
                paren_depth += 1
            elif char == ")":
                # End of nested parameters - include in current token
                current_token += char
                paren_depth -= 1
            else:
                current_token += char

            i += 1

        # Add final token
        if current_token:
            tokens.append(current_token)

        return tokens

    @classmethod
    def _parse_nested_parameter(
        cls, tokens: list[str], start_index: int
    ) -> tuple[LayoutParam | None, int]:
        """Parse a single parameter which may contain nested sub-parameters.

        Handles tokens like:
        - 'LA(LC(LSHFT))' -> LA with nested LC(LSHFT)
        - 'LCTRL' -> Simple parameter

        Args:
            tokens: List of tokens
            start_index: Index to start parsing from

        Returns:
            Tuple of (LayoutParam or None, next_index)
        """
        if start_index >= len(tokens):
            return None, start_index

        token = tokens[start_index]

        # Check if this token has nested parameters (contains parentheses)
        if "(" in token and ")" in token:
            # Find the first parenthesis to split parameter name from nested content
            paren_pos = token.find("(")
            param_name = token[:paren_pos]

            # Extract everything inside the outermost parentheses
            # Find matching closing parenthesis
            paren_depth = 0
            start_content = paren_pos + 1
            end_content = len(token)

            for i in range(paren_pos, len(token)):
                if token[i] == "(":
                    paren_depth += 1
                elif token[i] == ")":
                    paren_depth -= 1
                    if paren_depth == 0:
                        end_content = i
                        break

            inner_content = token[start_content:end_content]

            if not param_name or not inner_content:
                # Fall back to simple parameter
                param_value = cls._parse_param_value(token)
                return LayoutParam(value=param_value, params=[]), start_index + 1

            # Parameter name becomes the value
            param_value = cls._parse_param_value(param_name)

            # Parse nested content recursively
            # The inner content should be treated as parameters, not as a full binding
            inner_tokens = cls._tokenize_binding(inner_content)

            sub_params = []
            i = 0
            while i < len(inner_tokens):
                sub_param, i = cls._parse_nested_parameter(inner_tokens, i)
                if sub_param:
                    sub_params.append(sub_param)

            return LayoutParam(value=param_value, params=sub_params), start_index + 1
        else:
            # Simple parameter without nesting
            param_value = cls._parse_param_value(token)
            return LayoutParam(value=param_value, params=[]), start_index + 1

    @classmethod
    def _parse_simple_binding(cls, binding_str: str) -> "LayoutBinding":
        """Parse binding string using simple parsing for backward compatibility.

        This method maintains compatibility with existing quote handling and
        simple parameter parsing for cases without parentheses.

        Args:
            binding_str: Binding string to parse

        Returns:
            LayoutBinding with simple parameter structure
        """
        if not binding_str.strip():
            return LayoutBinding(value="&none", params=[])

        # Use existing quote-aware parsing logic
        parts = cls._parse_behavior_parts(binding_str)
        if not parts:
            return LayoutBinding(value="&none", params=[])

        # First part is the behavior
        behavior = parts[0]
        if not behavior.startswith("&"):
            behavior = f"&{behavior}"

        # Remaining parts are simple parameters
        params = []
        for part in parts[1:]:
            param_value = cls._parse_param_value(part)
            params.append(LayoutParam(value=param_value, params=[]))

        return cls(value=behavior, params=params)


class LayoutLayer(GloveboxBaseModel):
    """Model for keyboard layers."""

    name: str
    bindings: list[LayoutBinding]

    @field_validator("bindings", mode="before")
    @classmethod
    def convert_string_bindings(
        cls, v: list[str | LayoutBinding | dict[str, Any]] | Any
    ) -> list[LayoutBinding]:
        """Convert string bindings to LayoutBinding objects.

        Supports mixed input types:
        - str: ZMK behavior strings like "&kp Q", "&trans"
        - LayoutBinding: Pass through unchanged
        - dict: Legacy format, convert to LayoutBinding

        Args:
            v: Input bindings in various formats

        Returns:
            List of LayoutBinding objects

        Raises:
            ValueError: If input format is invalid or conversion fails
        """
        import logging

        logger = logging.getLogger(__name__)

        if not isinstance(v, list):
            raise ValueError(f"Bindings must be a list, got {type(v)}")

        converted_bindings = []

        for i, binding in enumerate(v):
            try:
                if isinstance(binding, LayoutBinding):
                    # Already a LayoutBinding object, use as-is
                    converted_bindings.append(binding)
                elif isinstance(binding, str):
                    # String format - parse into LayoutBinding
                    converted_bindings.append(LayoutBinding.from_str(binding))
                elif isinstance(binding, dict):
                    # Dictionary format - validate and convert
                    if "value" not in binding:
                        raise ValueError("Binding dict must have 'value' field")
                    converted_bindings.append(LayoutBinding.model_validate(binding))
                else:
                    # Unknown format - try to convert to string first
                    str_binding = str(binding)
                    logger.warning(
                        "Converting unknown binding type %s to string: %s",
                        type(binding).__name__,
                        str_binding,
                    )
                    converted_bindings.append(LayoutBinding.from_str(str_binding))

            except Exception as e:
                exc_info = logger.isEnabledFor(logging.DEBUG)
                logger.error(
                    "Failed to convert binding %d in layer: %s",
                    i,
                    e,
                    exc_info=exc_info,
                )
                raise ValueError(
                    f"Invalid binding at position {i}: {binding}. Error: {e}"
                ) from e

        return converted_bindings
