"""Behavior formatting service for converting JSON bindings to DTSI format."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from glovebox.config.models.zmk import MACRO_PLACEHOLDER
from glovebox.core.structlog_logger import StructlogMixin, get_struct_logger


if TYPE_CHECKING:
    from glovebox.config.models import BehaviorConfig

from glovebox.layout.models import (
    LayoutBinding,
    LayoutParam,
)

from ...protocols.behavior_protocols import BehaviorRegistryProtocol
from .models import (
    ParamValue,
)


logger = get_struct_logger(__name__)


class BehaviorFormatterImpl(StructlogMixin):
    """Implementation of behavior formatter."""

    def __init__(
        self,
        registry: BehaviorRegistryProtocol,
        behavior_config: "BehaviorConfig | None" = None,
        keycode_map: dict[str, str] | None = None,
    ) -> None:
        """Initialize with behavior registry dependency.

        Args:
            registry: Behavior registry for looking up behavior information
            behavior_config: Behavior configuration from keyboard profile
            keycode_map: Optional mapping of key names to ZMK keycodes
        """
        self._registry = registry
        self._behavior_config = behavior_config
        self._keycode_map = keycode_map or {}
        self._behavior_classes: dict[str, type[Behavior]] = {}
        self._modifier_map: dict[str, str] = {}
        self._is_behavior_reference_context = False
        self._init_behavior_class_map()
        self._init_modifier_map()

    def set_behavior_reference_context(
        self, is_behavior_reference_context: bool
    ) -> None:
        """Set whether we're formatting bindings for behavior definitions.

        Args:
            is_behavior_reference_context: True if formatting behavior reference bindings
        """
        self._is_behavior_reference_context = is_behavior_reference_context

    def format_binding(self, binding_data: LayoutBinding) -> str:
        """Format a binding dictionary to DTSI string.

        Args:
            binding_data: KeymapBehavior or dictionary representing a key binding
        """
        # Runtime type check is necessary
        # if not isinstance(binding_data, dict):
        #     logger.error(f"Invalid binding data format: {binding_data}")
        #     return "&error /* Invalid binding data */"

        # value = binding_data.get("value")
        # params_data = binding_data.get("params", [])
        value = binding_data.value
        params_data = binding_data.params

        behavior_class = self._behavior_classes.get(value)
        if behavior_class:
            try:
                behavior_instance = behavior_class(value, params_data, self)
                # format_dtsi should always return a string per the abstract method
                result: str = behavior_instance.format_dtsi()
                return result
            except Exception as e:
                logger.error(
                    f"Error formatting behavior '{value}' with params {params_data}: {e}"
                )
                param_str = ", ".join(map(str, params_data))
                return f"&error /* {value}({param_str}): {e} */"
        elif isinstance(value, str) and value.startswith("&"):
            try:
                behavior_instance = CustomBehaviorRef(value, params_data, self)
                # format_dtsi should always return a string per the abstract method
                custom_result: str = behavior_instance.format_dtsi()
                return custom_result
            except Exception as e:
                logger.error(f"Error formatting custom ref '{value}': {e}")
                return f"&error /* CustomRef: {value} */"
        else:
            logger.warning(f"Unexpected binding value '{value}'. Treating as error.")
            return f"&error /* Unexpected: {value} */"

    def get_keycode(self, key_name: str) -> str:
        """Look up ZMK keycode, returning input if not found."""
        return self._keycode_map.get(key_name, key_name)

    def format_param(self, param: ParamValue) -> str:
        """Format a single parameter."""
        return self.get_keycode(str(param))

    def format_param_recursive(self, param_data: LayoutParam) -> str:
        """Recursively format &kp parameters including modifiers."""
        mod_name = param_data.value
        inner_params_data = param_data.params

        # Check if this is a modifier function (LA, LC, etc.) with inner parameters
        if mod_name in ["LA", "LC", "LS", "LG", "RA", "RC", "RS", "RG"]:
            if inner_params_data:
                # Has inner parameters - treat as modifier function
                inner_formatted = self.format_param_recursive(inner_params_data[0])
                return f"{mod_name}({inner_formatted})"
            else:
                # No inner parameters - treat as plain keycode (e.g., &kp LC for Left Control)
                return self.format_param(mod_name)

        # Check if this is a configured modifier mapping
        elif str(mod_name) in self._modifier_map:
            if not inner_params_data:
                return self.format_param(mod_name)
            else:
                zmk_mod_func = self._modifier_map.get(str(mod_name))
                if not zmk_mod_func:
                    logger.error(
                        "Could not map modifier alias '%s' to function.", mod_name
                    )
                    return f"ERROR_MOD_ALIAS({mod_name})"
                inner_formatted = self.format_param_recursive(inner_params_data[0])
                return f"{zmk_mod_func}({inner_formatted})"
        else:
            return self.format_param(mod_name)

    def _create_behavior_class_map(self) -> dict[str, type]:
        """Create mapping of behavior names to their classes."""
        # This is a placeholder that will be updated by _init_behavior_class_map method
        # which will be called during initialization
        return {}

    def _init_behavior_class_map(self) -> None:
        """Initialize the behavior class map from configuration."""
        # Default behavior mappings for backward compatibility
        default_mappings = {
            "&none": SimpleBehavior,
            "&trans": SimpleBehavior,
            "&bootloader": SimpleBehavior,
            "&sys_reset": SimpleBehavior,
            "&reset": SimpleBehavior,
            "&kp": KPBehavior,
            "&lt": LayerTapBehavior,
            "&mt": ModTapBehavior,
            "&mo": LayerToggleBehavior,
            "&to": LayerToggleBehavior,
            "&tog": LayerToggleBehavior,
            "&sk": OneParamBehavior,
            "&rgb_ug": OneParamBehavior,
            "&out": OneParamBehavior,
            "&bt": BluetoothBehavior,
            "&msc": OneParamBehavior,
            "&mmv": OneParamBehavior,
            "&mkp": OneParamBehavior,
            "&caps_word": SimpleBehavior,
            "&lower": LowerBehavior,
            "&magic": MagicBehavior,
            "Custom": RawBehavior,
        }

        # Use configuration if available, otherwise fall back to defaults
        if self._behavior_config and self._behavior_config.behavior_mappings:
            # Build mapping from configuration
            class_mapping = {
                "SimpleBehavior": SimpleBehavior,
                "KPBehavior": KPBehavior,
                "LayerTapBehavior": LayerTapBehavior,
                "ModTapBehavior": ModTapBehavior,
                "LayerToggleBehavior": LayerToggleBehavior,
                "OneParamBehavior": OneParamBehavior,
                "BluetoothBehavior": BluetoothBehavior,
                "LowerBehavior": LowerBehavior,
                "MagicBehavior": MagicBehavior,
                "RawBehavior": RawBehavior,
            }

            configured_mappings = {}
            for mapping in self._behavior_config.behavior_mappings:
                behavior_class = class_mapping.get(mapping.behavior_class)
                if behavior_class:
                    configured_mappings[mapping.behavior_name] = behavior_class
                else:
                    logger.warning(
                        f"Unknown behavior class '{mapping.behavior_class}' for behavior '{mapping.behavior_name}', using default"
                    )

            # Merge configured mappings with defaults (configured takes precedence)
            self._behavior_classes = {**default_mappings, **configured_mappings}
        else:
            # Use defaults if no configuration is available
            self._behavior_classes = default_mappings

    def _init_modifier_map(self) -> None:
        """Initialize modifier mappings from configuration."""
        # Default modifier mappings for backward compatibility
        default_modifier_map = {
            "LALT": "LA",
            "LCTL": "LC",
            "LSHFT": "LS",
            "LGUI": "LG",
            "RALT": "RA",
            "RCTL": "RC",
            "RSHFT": "RS",
            "RGUI": "RG",
        }

        # Use configuration if available, otherwise fall back to defaults
        if self._behavior_config and self._behavior_config.modifier_mappings:
            configured_mappings = {}
            for mapping in self._behavior_config.modifier_mappings:
                configured_mappings[mapping.long_form] = mapping.short_form

            # Merge configured mappings with defaults (configured takes precedence)
            self._modifier_map = {**default_modifier_map, **configured_mappings}
        else:
            # Use defaults if no configuration is available
            self._modifier_map = default_modifier_map


# Behavior classes
class Behavior(ABC):
    """Base class for ZMK behaviors."""

    def __init__(
        self,
        value: str,
        params_data: list[LayoutParam],
        formatter: BehaviorFormatterImpl,
    ) -> None:
        self.behavior_name = value
        self.params = params_data
        self.formatter = formatter
        self._validate_params()

    def _is_behavior_reference_context(self) -> bool:
        """Check if we're in a behavior reference context."""
        return self.formatter._is_behavior_reference_context

    def _should_use_bare_reference(self) -> bool:
        """Check if this behavior should be formatted as a bare reference.

        Returns True if:
        - We're in a behavior reference context AND
        - No parameters are provided
        """
        return self._is_behavior_reference_context() and not self.params

    @abstractmethod
    def _validate_params(self) -> None:
        """Validate parameters for this behavior."""
        pass

    @abstractmethod
    def format_dtsi(self) -> str:
        """Generate DTSI string for this behavior."""
        pass


class SimpleBehavior(Behavior):
    """For behaviors with no parameters."""

    def _validate_params(self) -> None:
        if self.params:
            logger.warning(
                f"{self.behavior_name} expects no parameters, found {len(self.params)}"
            )

    def format_dtsi(self) -> str:
        if self.behavior_name == "&reset":
            # Use configured reset behavior alias or default
            if self.formatter._behavior_config:
                return self.formatter._behavior_config.reset_behavior_alias
            else:
                return "&sys_reset"
        return self.behavior_name


class KPBehavior(Behavior):
    """Handles &kp key presses, including modifiers."""

    def _validate_params(self) -> None:
        # Allow empty params for hold-tap bindings where &kp is just a reference
        pass

    def format_dtsi(self) -> str:
        if not self.params:
            # For hold-tap bindings, &kp without params is valid ZMK syntax
            return "&kp"

        # Get the first parameter and handle it based on its type
        param = self.params[0]

        kp_param_formatted = self.formatter.format_param_recursive(param)
        return f"&kp {kp_param_formatted}"


class LayerTapBehavior(Behavior):
    """Handles &lt (Layer-Tap)."""

    def _validate_params(self) -> None:
        if len(self.params) != 2:
            raise ValueError(
                f"{self.behavior_name} requires exactly 2 parameters (layer, keycode/binding)."
            ) from None

    def format_dtsi(self) -> str:
        layer = self.formatter.format_param_recursive(self.params[0])
        tap_keycode = self.formatter.format_param_recursive(self.params[1])
        return f"&lt {layer} {tap_keycode}"


class ModTapBehavior(Behavior):
    """Handles &mt (Mod-Tap)."""

    def _validate_params(self) -> None:
        if len(self.params) != 2:
            raise ValueError(
                f"{self.behavior_name} requires exactly 2 parameters (modifier, keycode/binding)."
            ) from None

    def format_dtsi(self) -> str:
        mod = self.formatter.format_param_recursive(self.params[0])
        tap_keycode = self.formatter.format_param_recursive(self.params[1])
        return f"&mt {mod} {tap_keycode}"


class LayerToggleBehavior(Behavior):
    """Handles &mo, &to, &tog."""

    def _validate_params(self) -> None:
        # Allow empty params in behavior reference context
        if self._is_behavior_reference_context() and not self.params:
            return
        if len(self.params) != 1:
            raise ValueError(
                f"{self.behavior_name} requires exactly 1 parameter (layer)."
            ) from None

    def format_dtsi(self) -> str:
        if self._should_use_bare_reference():
            return self.behavior_name

        layer = self.formatter.format_param_recursive(self.params[0])
        return f"{self.behavior_name} {layer}"


class OneParamBehavior(Behavior):
    """Handles behaviors taking one parameter."""

    def _validate_params(self) -> None:
        # Allow empty params in behavior reference context
        if self._is_behavior_reference_context() and not self.params:
            return
        if len(self.params) != 1:
            raise ValueError(
                f"{self.behavior_name} requires exactly 1 parameter."
            ) from None

    def format_dtsi(self) -> str:
        if self._should_use_bare_reference():
            return self.behavior_name

        if not self.params:
            logger.error(f"Behavior {self.behavior_name} missing raw parameters.")
            return f"&error /* {self.behavior_name} missing params */"

        param_formatted = self.formatter.format_param_recursive(self.params[0])
        return f"{self.behavior_name} {param_formatted}"


class BluetoothBehavior(Behavior):
    """Handles &bt commands."""

    def _validate_params(self) -> None:
        if not self.params or len(self.params) < 1 or len(self.params) > 2:
            raise ValueError(
                f"{self.behavior_name} requires 1 or 2 parameters."
            ) from None
        if not str(self.params[0].value).startswith("BT_"):
            raise ValueError(
                f"{self.behavior_name} first parameter must be a BT_ command."
            ) from None

    def format_dtsi(self) -> str:
        command = self.formatter.format_param_recursive(self.params[0])
        if len(self.params) == 2:
            index = self.formatter.format_param_recursive(self.params[1])
            return f"&bt {command} {index}"
        else:
            return f"&bt {command}"


class LowerBehavior(Behavior):
    """Handles the deprecated &lower behavior."""

    def _validate_params(self) -> None:
        if self.params:
            logger.warning(
                f"{self.behavior_name} expects no parameters, found {len(self.params)}"
            )

    def format_dtsi(self) -> str:
        return "&lower"


class MagicBehavior(Behavior):
    """Handles the deprecated &magic behavior."""

    def _validate_params(self) -> None:
        if self.params:
            logger.warning(
                f"{self.behavior_name} expects no parameters in JSON, found {len(self.params)}"
            )

    def format_dtsi(self) -> str:
        # Use configured magic layer command or default
        if self.formatter._behavior_config:
            return self.formatter._behavior_config.magic_layer_command
        else:
            return "&magic LAYER_Magic 0"


class CustomBehaviorRef(Behavior):
    """Handles references to custom behaviors."""

    def _validate_params(self) -> None:
        pass  # Custom behaviors can have varying parameters

    def format_dtsi(self) -> str:
        registry_info = self.formatter._registry.get_behavior_info(self.behavior_name)

        if registry_info:
            expected_params = registry_info.expected_params
            origin = registry_info.origin

            if expected_params == 0:
                if self.params:
                    logger.warning(
                        f"Zero-parameter behavior '{self.behavior_name}' (origin: {origin}) received {len(self.params)} parameters. Ignoring."
                    )
                return self.behavior_name

            formatted_params = []
            params_to_format = self.params
            num_params_received = len(self.params)

            if expected_params > 0 and num_params_received > expected_params:
                logger.warning(
                    f"Behavior '{self.behavior_name}' (origin: {origin}) expects {expected_params} parameters but received {num_params_received}. Using only the first {expected_params}."
                )
                params_to_format = self.params[:expected_params]

            for p in params_to_format:
                formatted = self.formatter.format_param_recursive(p)
                formatted_params.append(formatted)

            if expected_params > 0 and num_params_received < expected_params:
                # Use systematic hold-tap binding context check
                if self._should_use_bare_reference():
                    return self.behavior_name
                missing_count = expected_params - num_params_received
                formatted_params.extend([MACRO_PLACEHOLDER] * missing_count)

            param_str = " ".join(formatted_params)
            return f"{self.behavior_name} {param_str}".strip()
        else:
            logger.warning(
                f"Behavior '{self.behavior_name}' not found in registry. Formatting all {len(self.params)} parameters as passed."
            )
            formatted_params = []
            for p in self.params:
                formatted = self.formatter.format_param_recursive(p)
                formatted_params.append(formatted)

            param_str = " ".join(formatted_params)
            return f"{self.behavior_name} {param_str}".strip()


class RawBehavior(Behavior):
    """Handles passthrough for 'Custom' type or unrecognized behaviors."""

    def _validate_params(self) -> None:
        pass

    def format_dtsi(self) -> str:
        if self.params:
            return str(self.params[0].value)
        else:
            logger.warning(
                f"Raw/Custom behavior '{self.behavior_name}' used without parameters."
            )
            return f"&error /* Raw: {self.behavior_name} */"
