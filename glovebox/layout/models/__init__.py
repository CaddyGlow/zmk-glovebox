"""Layout models for keyboard layouts."""

from datetime import datetime
from pathlib import Path
from typing import Any, TypeAlias, Union

from pydantic import (
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_serializer,
    model_validator,
)

# Import behavior models that are now part of the layout domain
from glovebox.layout.behavior.models import (
    BehaviorCommand,
    BehaviorParameter,
    KeymapBehavior,
    ParameterType,
    ParamValue,
    SystemBehavior,
    SystemBehaviorParam,
    SystemParamList,
)
from glovebox.models.base import GloveboxBaseModel

from .behavior_data import BehaviorData
from .bookmarks import BookmarkCollection, BookmarkSource, LayoutBookmark


# Type aliases for common parameter types
ConfigValue: TypeAlias = str | int | bool
LayerIndex: TypeAlias = int
# Template-aware numeric type that accepts integers or template strings
TemplateNumeric: TypeAlias = int | str | None
#
# This type alias improves type safety and makes future changes easier
LayerBindings: TypeAlias = list["LayoutBinding"]
# Type alias for collections of behaviors
BehaviorList: TypeAlias = list[
    Union["HoldTapBehavior", "ComboBehavior", "MacroBehavior", "InputListener"]
]
# Type alias for configuration parameters
ConfigParamList: TypeAlias = list["ConfigParameter"]


# TODO: rename to maybe KeyPararm to avoid confusion with LayoutParam
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
            
            # Check if this looks like a modifier chain (common ZMK pattern)
            if len(tokens) == 3 and not any("(" in token for token in tokens[1:]):
                # For certain behaviors, keep flat structure
                behavior_name = behavior.lower()
                if behavior_name in ("&mt", "&lt", "&caps_word"):
                    # These behaviors expect flat parameters
                    for i in range(1, len(tokens)):
                        param_value = cls._parse_param_value(tokens[i])
                        params.append(LayoutParam(value=param_value, params=[]))
                else:
                    # Create nested structure: first param contains second param
                    first_param_value = cls._parse_param_value(tokens[1])
                    second_param_value = cls._parse_param_value(tokens[2])
                    
                    nested_param = LayoutParam(
                        value=first_param_value,
                        params=[LayoutParam(value=second_param_value, params=[])]
                    )
                    params.append(nested_param)
            else:
                # Handle complex cases or more than 2 parameters normally
                i = 1
                while i < len(tokens):
                    param, i = cls._parse_nested_parameter(tokens, i)
                    if param:
                        params.append(param)

            return cls(value=behavior, params=params)

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


class HoldTapBehavior(GloveboxBaseModel):
    """Model for hold-tap behavior definitions."""

    name: str
    description: str | None = ""
    bindings: list[str] = Field(default_factory=list)
    tapping_term_ms: TemplateNumeric = Field(default=None, alias="tappingTermMs")
    quick_tap_ms: TemplateNumeric = Field(default=None, alias="quickTapMs")
    flavor: str | None = None
    hold_trigger_on_release: bool | None = Field(
        default=None, alias="holdTriggerOnRelease"
    )
    require_prior_idle_ms: TemplateNumeric = Field(
        default=None, alias="requirePriorIdleMs"
    )
    hold_trigger_key_positions: list[int] | None = Field(
        default=None, alias="holdTriggerKeyPositions"
    )
    retro_tap: bool | None = Field(default=None, alias="retroTap")
    tap_behavior: str | None = Field(default=None, alias="tapBehavior")
    hold_behavior: str | None = Field(default=None, alias="holdBehavior")

    @field_validator("flavor")
    @classmethod
    def validate_flavor(cls, v: str | None) -> str | None:
        """Validate hold-tap flavor."""
        if v is not None:
            valid_flavors = [
                "tap-preferred",
                "hold-preferred",
                "balanced",
                "tap-unless-interrupted",
            ]
            if v not in valid_flavors:
                raise ValueError(
                    f"Invalid flavor: {v}. Must be one of {valid_flavors}"
                ) from None
        return v

    @field_validator("bindings")
    @classmethod
    def validate_bindings_count(cls, v: list[str]) -> list[str]:
        """Validate that hold-tap has exactly 2 bindings."""
        if len(v) != 2:
            raise ValueError(
                f"Hold-tap behavior requires exactly 2 bindings, found {len(v)}"
            ) from None
        return v


class ComboBehavior(GloveboxBaseModel):
    """Model for combo definitions."""

    name: str
    description: str | None = ""
    timeout_ms: TemplateNumeric = Field(default=None, alias="timeoutMs")
    key_positions: list[int] = Field(alias="keyPositions")
    layers: list[LayerIndex] | None = None
    binding: LayoutBinding = Field()
    behavior: str | None = Field(default=None, alias="behavior")

    @field_validator("key_positions")
    @classmethod
    def validate_key_positions(cls, v: list[int]) -> list[int]:
        """Validate key positions are valid."""
        if not v:
            raise ValueError("Combo must have at least one key position") from None
        for pos in v:
            if not isinstance(pos, int) or pos < 0:
                raise ValueError(f"Invalid key position: {pos}") from None
        return v


class MacroBehavior(GloveboxBaseModel):
    """Model for macro definitions."""

    name: str
    description: str | None = ""
    wait_ms: TemplateNumeric = Field(default=None, alias="waitMs")
    tap_ms: TemplateNumeric = Field(default=None, alias="tapMs")
    bindings: list[LayoutBinding] = Field(default_factory=list)
    params: list[ParamValue] | None = None

    @field_validator("params")
    @classmethod
    def validate_params_count(
        cls, v: list[ParamValue] | None
    ) -> list[ParamValue] | None:
        """Validate macro parameter count."""
        if v is not None and len(v) > 2:
            raise ValueError(
                f"Macro cannot have more than 2 parameters, found {len(v)}"
            ) from None
        return v


class TapDanceBehavior(GloveboxBaseModel):
    """Model for tap-dance behavior definitions."""

    name: str
    description: str | None = ""
    tapping_term_ms: TemplateNumeric = Field(default=None, alias="tappingTermMs")
    bindings: list[LayoutBinding] = Field(default_factory=list)

    @field_validator("bindings")
    @classmethod
    def validate_bindings_count(cls, v: list[LayoutBinding]) -> list[LayoutBinding]:
        """Validate tap-dance bindings count."""
        if len(v) < 2:
            raise ValueError("Tap-dance must have at least 2 bindings") from None
        if len(v) > 5:
            raise ValueError("Tap-dance cannot have more than 5 bindings") from None
        return v


class StickyKeyBehavior(GloveboxBaseModel):
    """Model for sticky-key behavior definitions."""

    name: str
    description: str | None = ""
    release_after_ms: TemplateNumeric = Field(default=None, alias="releaseAfterMs")
    quick_release: bool = Field(default=False, alias="quickRelease")
    lazy: bool = Field(default=False)
    ignore_modifiers: bool = Field(default=False, alias="ignoreModifiers")
    bindings: list[LayoutBinding] = Field(default_factory=list)


class CapsWordBehavior(GloveboxBaseModel):
    """Model for caps-word behavior definitions."""

    name: str
    description: str | None = ""
    continue_list: list[str] = Field(default_factory=list, alias="continueList")
    mods: int | None = Field(default=None)


class ModMorphBehavior(GloveboxBaseModel):
    """Model for mod-morph behavior definitions."""

    name: str
    description: str | None = ""
    mods: int
    bindings: list[LayoutBinding] = Field(default_factory=list)
    keep_mods: int | None = Field(default=None, alias="keepMods")

    @field_validator("bindings")
    @classmethod
    def validate_bindings_count(cls, v: list[LayoutBinding]) -> list[LayoutBinding]:
        """Validate mod-morph bindings count."""
        if len(v) != 2:
            raise ValueError("Mod-morph must have exactly 2 bindings") from None
        return v


class ConfigParameter(GloveboxBaseModel):
    """Model for configuration parameters."""

    param_name: str = Field(alias="paramName")
    value: ConfigValue
    description: str | None = None


class InputProcessor(GloveboxBaseModel):
    """Model for input processors."""

    code: str
    params: list[ParamValue] = Field(default_factory=list)


class InputListenerNode(GloveboxBaseModel):
    """Model for input listener nodes."""

    code: str
    description: str | None = ""
    layers: list[LayerIndex] = Field(default_factory=list)
    input_processors: list[InputProcessor] = Field(
        default_factory=list, alias="inputProcessors"
    )


class InputListener(GloveboxBaseModel):
    """Model for input listeners."""

    code: str
    input_processors: list[InputProcessor] = Field(
        default_factory=list, alias="inputProcessors"
    )
    nodes: list[InputListenerNode] = Field(default_factory=list)


class KeymapComment(GloveboxBaseModel):
    """Model for preserved comments from ZMK keymap files."""

    text: str
    line: int = Field(default=0)
    context: str = Field(default="")  # "header", "behavior", "layer", "footer", etc.
    is_block: bool = Field(default=False)  # True for /* */, False for //


class KeymapInclude(GloveboxBaseModel):
    """Model for include directives in ZMK keymap files."""

    path: str
    line: int = Field(default=0)
    resolved_path: str = Field(default="")  # Actual resolved file path if available


class ConfigDirective(GloveboxBaseModel):
    """Model for configuration directives in ZMK keymap files."""

    directive: str  # "ifdef", "ifndef", "define", etc.
    condition: str = Field(default="")
    value: str = Field(default="")
    line: int = Field(default=0)


class DependencyInfo(GloveboxBaseModel):
    """Dependency tracking information for behaviors and includes."""

    include_dependencies: list[str] = Field(
        default_factory=list, description="List of include files this keymap depends on"
    )
    behavior_sources: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of behavior names to their source files",
    )
    unresolved_includes: list[str] = Field(
        default_factory=list,
        description="Include paths that could not be resolved to actual files",
    )


class KeymapMetadata(GloveboxBaseModel):
    """Enhanced metadata extracted from ZMK keymap parsing."""

    # File structure metadata
    comments: list[KeymapComment] = Field(default_factory=list)
    includes: list[KeymapInclude] = Field(default_factory=list)
    config_directives: list[ConfigDirective] = Field(
        default_factory=list, alias="configDirectives"
    )

    # Parsing metadata
    parsing_method: str = Field(default="ast")  # "ast" or "regex"
    parsing_mode: str = Field(default="full")  # "full", "template", "auto"
    parse_timestamp: datetime = Field(default_factory=datetime.now)
    source_file: str = Field(default="")

    # Original structure preservation
    original_header: str = Field(default="")  # Comments and includes before first node
    original_footer: str = Field(default="")  # Comments after last node
    custom_sections: dict[str, str] = Field(
        default_factory=dict,
        description="Custom sections with their content for round-trip preservation",
    )

    # Dependency tracking (Phase 4.3)
    dependencies: DependencyInfo = Field(
        default_factory=DependencyInfo,
        description="Dependency tracking for include files and behaviors",
    )

    @field_serializer("parse_timestamp", when_used="json")
    def serialize_parse_timestamp(self, dt: datetime) -> int:
        """Serialize parse timestamp to Unix timestamp for JSON."""
        return int(dt.timestamp())


class LayoutMetadata(GloveboxBaseModel):
    """Pydantic model for layout metadata fields."""

    # Required fields
    keyboard: str
    title: str

    # Optional metadata
    firmware_api_version: str = Field(default="1", alias="firmware_api_version")
    locale: str = Field(default="en-US")
    uuid: str = Field(default="")
    parent_uuid: str = Field(default="", alias="parent_uuid")
    date: datetime = Field(default_factory=datetime.now)

    @field_serializer("date", when_used="json")
    def serialize_date(self, dt: datetime) -> int:
        """Serialize date to Unix timestamp for JSON."""
        return int(dt.timestamp())

    creator: str = Field(default="")
    notes: str = Field(default="")
    tags: list[str] = Field(default_factory=list)

    # Variables for substitution
    variables: dict[str, Any] = Field(
        default_factory=dict,
        description="Global variables for substitution using ${variable_name} syntax",
    )

    # Configuration
    config_parameters: ConfigParamList = Field(
        default_factory=list, alias="config_parameters"
    )

    # Version tracking (new)
    version: str = Field(default="1.0.0")
    base_version: str = Field(default="")  # Master version this is based on
    base_layout: str = Field(default="")  # e.g., "glorious-engrammer"

    layer_names: list[str] = Field(default_factory=list, alias="layer_names")

    # Enhanced metadata for ZMK keymap reconstruction (Phase 4.1)
    keymap_metadata: KeymapMetadata = Field(
        default_factory=KeymapMetadata,
        alias="keymapMetadata",
        description="Enhanced metadata for ZMK keymap round-trip preservation",
    )


class LayoutData(LayoutMetadata):
    """Complete layout data model following Moergo API field names with aliases."""

    # User behavior definitions
    hold_taps: list[HoldTapBehavior] = Field(default_factory=list, alias="holdTaps")
    combos: list[ComboBehavior] = Field(default_factory=list)
    macros: list[MacroBehavior] = Field(default_factory=list)
    input_listeners: list[InputListener] = Field(
        default_factory=list, alias="inputListeners"
    )

    # Essential structure fields
    layers: list[LayerBindings] = Field(default_factory=list)

    # Custom code
    custom_defined_behaviors: str = Field(default="", alias="custom_defined_behaviors")
    custom_devicetree: str = Field(default="", alias="custom_devicetree")

    @model_validator(mode="before")
    @classmethod
    def validate_data_structure(cls, data: Any, info: Any = None) -> Any:
        """Basic validation without template processing.

        This only handles basic data structure validation like date conversion.
        Template processing is handled separately by process_templates().
        """
        if not isinstance(data, dict):
            return data

        # Convert integer timestamps to datetime objects for date fields
        if "date" in data and isinstance(data["date"], int):
            from datetime import datetime

            data["date"] = datetime.fromtimestamp(data["date"])

        return data

    def process_templates(self) -> "LayoutData":
        """Process all Jinja2 templates in the layout data.

        This is a separate method that can be called explicitly when needed,
        instead of being part of model validation.

        Returns:
            New LayoutData instance with resolved templates
        """
        # Skip processing if no variables or templates present
        if not self.variables and not self._has_template_syntax(self.model_dump()):
            return self

        from glovebox.layout.template_service import create_jinja2_template_service
        from glovebox.layout.utils.json_operations import VariableResolutionContext

        try:
            # Create template service and process the data
            template_service = create_jinja2_template_service()

            # Process templates and return new instance
            resolved_layout = template_service.process_layout_data(self)
            return resolved_layout

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.warning("Template resolution failed: %s", e, exc_info=exc_info)
            return self

    @classmethod
    def load_with_templates(cls, data: dict[str, Any]) -> "LayoutData":
        """Load layout data and process templates.

        This is the method to use when you want templates processed.
        """
        # First create the model without template processing
        layout = cls.model_validate(data)

        # Then process templates if not in skip context
        from glovebox.layout.utils.json_operations import (
            should_skip_variable_resolution,
        )

        if not should_skip_variable_resolution():
            layout = layout.process_templates()

        return layout

    @classmethod
    def _has_template_syntax(cls, data: dict[str, Any]) -> bool:
        """Check if data contains any Jinja2 template syntax."""
        import re

        def scan_for_templates(obj: Any) -> bool:
            if isinstance(obj, str):
                return bool(re.search(r"\{\{|\{%|\{#", obj))
            elif isinstance(obj, dict):
                return any(scan_for_templates(v) for v in obj.values())
            elif isinstance(obj, list):
                return any(scan_for_templates(item) for item in obj)
            return False

        return scan_for_templates(data)

    @model_serializer(mode="wrap")
    def serialize_with_sorted_fields(
        self, serializer: Any, info: Any
    ) -> dict[str, Any]:
        """Serialize with fields in a specific order."""
        data = serializer(self)

        # Define the desired field order
        # IMPORTANT: variables must be first for proper template resolution
        field_order = [
            "variables",
            "keyboard",
            "firmware_api_version",
            "locale",
            "uuid",
            "parent_uuid",
            "date",
            "creator",
            "title",
            "notes",
            "tags",
            # Added fields for the layout master feature
            "version",
            "base_version",
            "base_layout",
            "last_firmware_build",
            # Enhanced metadata for full keymap reconstruction in layout parser
            "keymapMetadata",
            # Normal layout structure
            "layer_names",
            "config_parameters",
            "holdTaps",
            "combos",
            "macros",
            "inputListeners",
            "layers",
            "custom_defined_behaviors",
            "custom_devicetree",
        ]

        # Create ordered dict with known fields first
        ordered_data = {}
        for field in field_order:
            if field in data:
                ordered_data[field] = data[field]

        # Add any remaining fields not in the order list
        for key, value in data.items():
            if key not in ordered_data:
                ordered_data[key] = value

        return ordered_data

    @field_validator("layers")
    @classmethod
    def validate_layers_structure(cls, v: list[LayerBindings]) -> list[LayerBindings]:
        """Validate layers structure."""
        # Allow empty layers list during construction/processing
        if not v:
            return v

        for i, layer in enumerate(v):
            if not isinstance(layer, list):
                raise ValueError(f"Layer {i} must be a list of bindings") from None

            # Validate each binding in the layer
            for j, binding in enumerate(layer):
                if not isinstance(binding, LayoutBinding):
                    raise ValueError(
                        f"Layer {i}, binding {j} must be a LayoutBinding"
                    ) from None
                if not binding.value:
                    raise ValueError(
                        f"Layer {i}, binding {j} missing 'value' field"
                    ) from None

        return v

    def get_structured_layers(self) -> list[LayoutLayer]:
        """Create LayoutLayer objects from typed layer data."""
        structured_layers = []

        for layer_name, layer_bindings in zip(
            self.layer_names, self.layers, strict=False
        ):
            # Create LayoutLayer directly from properly typed bindings
            layer = LayoutLayer(name=layer_name, bindings=layer_bindings)
            structured_layers.append(layer)

        return structured_layers

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with proper field names and JSON serialization."""
        return self.model_dump(mode="json", by_alias=True, exclude_unset=True)

    def to_flattened_dict(self) -> dict[str, Any]:
        """Export layout with templates resolved and variables section removed.

        Returns:
            Dictionary representation with all templates resolved and variables section removed
        """
        # Get the original dict representation
        data = self.model_dump(mode="json", by_alias=True, exclude_unset=True)

        # If we have variables or templates, resolve and remove variables section
        if data.get("variables") or self._has_template_syntax(data):
            try:
                # Process templates on a copy
                resolved_layout = self.process_templates()
                resolved_data = resolved_layout.model_dump(
                    mode="json", by_alias=True, exclude_unset=True
                )

                # Remove variables section from output
                return {k: v for k, v in resolved_data.items() if k != "variables"}

            except Exception as e:
                # Fall back to removing variables section only
                import logging

                logger = logging.getLogger(__name__)
                exc_info = logger.isEnabledFor(logging.DEBUG)
                logger.warning(
                    "Template resolution failed in to_flattened_dict: %s",
                    e,
                    exc_info=exc_info,
                )
                return {k: v for k, v in data.items() if k != "variables"}

        # No variables or templates to resolve, just return without variables section
        return {k: v for k, v in data.items() if k != "variables"}


# Layout result models
class KeymapResult(GloveboxBaseModel):
    """Result of keymap operations."""

    success: bool
    timestamp: datetime = Field(default_factory=datetime.now)
    messages: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    @field_serializer("timestamp", when_used="json")
    def serialize_timestamp(self, dt: datetime) -> int:
        """Serialize timestamp to Unix timestamp for JSON."""
        return int(dt.timestamp())

    keymap_path: Path | None = None
    conf_path: Path | None = None
    json_path: Path | None = None
    profile_name: str | None = None
    layer_count: int | None = None

    def add_message(self, message: str) -> None:
        """Add an informational message."""
        if not isinstance(message, str):
            raise ValueError("Message must be a string") from None
        self.messages.append(message)

    def add_error(self, error: str) -> None:
        """Add an error message."""
        if not isinstance(error, str):
            raise ValueError("Error must be a string") from None
        self.errors.append(error)
        self.success = False


class LayoutResult(GloveboxBaseModel):
    """Result of layout operations."""

    success: bool
    timestamp: datetime = Field(default_factory=datetime.now)
    messages: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    @field_serializer("timestamp", when_used="json")
    def serialize_timestamp(self, dt: datetime) -> int:
        """Serialize timestamp to Unix timestamp for JSON."""
        return int(dt.timestamp())

    keymap_path: Path | None = None
    conf_path: Path | None = None
    json_path: Path | None = None
    profile_name: str | None = None
    layer_count: int | None = None

    @field_validator("keymap_path", "conf_path", "json_path")
    @classmethod
    def validate_paths(cls, v: Any) -> Path | None:
        """Validate that paths are Path objects if provided."""
        if v is None:
            return None
        if isinstance(v, Path):
            return v
        if isinstance(v, str):
            return Path(v)
        # If we get here, v is neither None, Path, nor str
        raise ValueError("Paths must be Path objects or strings") from None

    @field_validator("layer_count")
    @classmethod
    def validate_layer_count(cls, v: int | None) -> int | None:
        """Validate layer count is positive if provided."""
        if v is not None and (not isinstance(v, int) or v < 0):
            raise ValueError("Layer count must be a non-negative integer") from None
        return v

    def add_message(self, message: str) -> None:
        """Add an informational message."""
        if not isinstance(message, str):
            raise ValueError("Message must be a string") from None
        self.messages.append(message)

    def add_error(self, error: str) -> None:
        """Add an error message."""
        if not isinstance(error, str):
            raise ValueError("Error must be a string") from None
        self.errors.append(error)
        self.success = False

    def get_output_files(self) -> dict[str, Path]:
        """Get dictionary of output file types to paths."""
        files = {}
        if self.keymap_path:
            files["keymap"] = self.keymap_path
        if self.conf_path:
            files["conf"] = self.conf_path
        if self.json_path:
            files["json"] = self.json_path
        return files

    def validate_output_files_exist(self) -> bool:
        """Check if all output files actually exist on disk."""
        files = self.get_output_files()
        missing_files = []

        for file_type, file_path in files.items():
            if not file_path.exists():
                missing_files.append(f"{file_type}: {file_path}")

        if missing_files:
            self.add_error(f"Output files missing: {', '.join(missing_files)}")
            return False

        return True


# Re-export all models for external use
__all__ = [
    # Type aliases
    "ConfigValue",
    "LayerIndex",
    "TemplateNumeric",
    "LayerBindings",
    "BehaviorList",
    "ConfigParamList",
    # Layout models
    "LayoutParam",
    "LayoutBinding",
    "LayoutLayer",
    "LayoutData",
    "LayoutMetadata",
    # Behavior models
    "BehaviorData",
    "HoldTapBehavior",
    "ComboBehavior",
    "MacroBehavior",
    "InputProcessor",
    "InputListenerNode",
    "InputListener",
    "ConfigParameter",
    # Re-exported behavior models from behavior_models
    "BehaviorCommand",
    "BehaviorParameter",
    "KeymapBehavior",
    "ParameterType",
    "ParamValue",
    "SystemBehavior",
    "SystemBehaviorParam",
    "SystemParamList",
    # Result models
    "KeymapResult",
    "LayoutResult",
    # Bookmark models
    "LayoutBookmark",
    "BookmarkCollection",
    "BookmarkSource",
]
