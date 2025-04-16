import re
import logging
from typing import List, Dict, Any, Optional, Type

logger = logging.getLogger(__name__)

# KEYCODE_MAP: Needs to be properly populated, e.g., from a config file or constants
# Example population (incomplete):
KEYCODE_MAP = {}


def get_keycode(key_name: str) -> str:
    """Looks up the ZMK keycode, returning the input if not found."""
    # Basic check, can be expanded (e.g., handle case, aliases)
    return KEYCODE_MAP.get(key_name, key_name)


# --- Base Behavior Class ---
class Behavior:
    """Base class for ZMK behaviors."""

    def __init__(self, value: str, params_data: List[Any]):
        self.behavior_name = value  # e.g., "&kp", "&mt"
        self.raw_params = params_data
        self.params: List[Any] = self._parse_params(params_data)
        self._validate_params()

    def _parse_params(self, params_data):
        """Extracts 'value' if params are dicts like {'value': X}."""
        parsed = []
        for p in params_data:
            if isinstance(p, dict) and "value" in p:
                parsed.append(p["value"])
            else:
                # Keep raw ints, strings, etc.
                parsed.append(p)
        return parsed

    def _validate_params(self):
        """Basic validation, subclasses should override."""
        pass

    def _format_param(self, param: Any) -> str:
        """Formats a single parameter (keycode, layer, number, etc.)."""
        if isinstance(param, str):
            # Handle layer names, keycodes, etc.
            # Assumes layer refs look like "LAYER_Name" or are indices
            # Assumes keycodes are looked up
            if param.startswith("LAYER_") or param.isdigit():
                return param
            elif param.startswith("&"):  # Reference to another behavior
                return param
            else:
                # Assume it's a keycode or simple ZMK define name
                return get_keycode(param)
        elif isinstance(param, int):
            return str(param)
        elif isinstance(
            param, Behavior
        ):  # If a param is a nested behavior (e.g., for &sk)
            return param.format_dtsi()
        else:
            logger.warning(
                f"Unhandled parameter type: {type(param)} ({param}). Converting to string."
            )
            return str(param)

    def format_dtsi(self) -> str:
        """Generates the DTSI string for this behavior."""
        raise NotImplementedError


# --- Concrete Behavior Subclasses ---


class SimpleBehavior(Behavior):
    """For behaviors with no parameters (&none, &trans, &bootloader, &sys_reset)."""

    def _validate_params(self):
        if self.params:
            logger.warning(
                f"{self.behavior_name} expects no parameters, found {len(self.params)}"
            )

    def format_dtsi(self) -> str:
        # Map specific names if needed (e.g., &reset -> &sys_reset)
        if self.behavior_name == "&reset":
            return "&sys_reset"
        return self.behavior_name


class KPBehavior(Behavior):
    """Handles &kp key presses, including modifiers."""

    def _validate_params(self):
        if not self.params:
            raise ValueError(f"{self.behavior_name} requires at least one parameter.")
        # More validation could check param type

    def _format_kp_recursive(self, param_data: Any) -> str:
        """Recursively formats &kp parameters including modifiers."""
        if isinstance(param_data, dict) and "value" in param_data:
            mod_name = param_data["value"]
            # Check if it's a known modifier function like LA, LC, etc.
            # A more robust way might involve parsing the structure explicitly.
            # Check if it's a known modifier function like LA, LC, etc.
            # These modifier functions are essentially behaviors themselves in ZMK DTSI
            if mod_name in ["LA", "LC", "LS", "LG", "RA", "RC", "RS", "RG"]:
                 inner_params_data = param_data.get("params", [])
                 if not inner_params_data:
                     logger.error(f"Modifier function '{mod_name}' in &kp missing inner parameter.")
                     return f"{mod_name}(ERROR_MOD_PARAM)"

                 # The inner parameter could be another modifier or a simple keycode.
                 # Format it recursively using the same logic.
                 inner_formatted = self._format_kp_recursive(inner_params_data[0])
                 return f"{mod_name}({inner_formatted})"
            # Handle aliases like LALT -> LA
            elif mod_name in ["LALT", "LCTL", "LSHFT", "LGUI", "RALT", "RCTL", "RSHFT", "RGUI"]:
                 zmk_mod_func = {
                     "LALT": "LA", "LCTL": "LC", "LSHFT": "LS", "LGUI": "LG",
                     "RALT": "RA", "RCTL": "RC", "RSHFT": "RS", "RGUI": "RG",
                 }.get(mod_name)
                 inner_params_data = param_data.get("params", [])
                 if not inner_params_data:
                     logger.error(f"Modifier alias '{mod_name}' in &kp missing inner parameter.")
                     return f"{zmk_mod_func}(ERROR_MOD_PARAM)" # Return the ZMK func name even on error

                 inner_formatted = self._format_kp_recursive(inner_params_data[0])
                 return f"{zmk_mod_func}({inner_formatted})"
            else:
            else:
                 # Not a recognized modifier function, treat as simple keycode
                 # This handles cases like &kp A, &kp LSHFT, &kp SEMI
                 return self._format_param(param_data["value"])

        elif isinstance(param_data, (str, int)):
             # Simple keycode or value passed directly (e.g., from macro param)
             # Check if it's an alias that needs mapping for &kp context
             if param_data in ["LALT", "LCTL", "LSHFT", "LGUI", "RALT", "RCTL", "RSHFT", "RGUI"]:
                 zmk_mod_func = {
                     "LALT": "LA", "LCTL": "LC", "LSHFT": "LS", "LGUI": "LG",
                     "RALT": "RA", "RCTL": "RC", "RSHFT": "RS", "RGUI": "RG",
                 }.get(param_data)
                 # Modifiers used directly in &kp should just be the keycode name
                 # return f"{zmk_mod_func}(ERROR_MOD_PARAM)" # Incorrect - this implies function call
                 return self._format_param(param_data) # Return the original alias name
             else:
                 return self._format_param(param_data)
        else:
            logger.error(
                f"Unexpected parameter type in &kp: {type(param_data)} ({param_data})"
            )
            return "ERROR_KP_PARAM"

    def format_dtsi(self) -> str:
        # Start formatting from the first raw parameter structure
        kp_param_formatted = self._format_kp_recursive(self.raw_params[0])
        return f"&kp {kp_param_formatted}"


class LayerTapBehavior(Behavior):
    """Handles &lt (Layer-Tap)."""

    def _validate_params(self):
        if len(self.params) != 2:
            raise ValueError(
                f"{self.behavior_name} requires exactly 2 parameters (layer, keycode/binding)."
            )

    def format_dtsi(self) -> str:
        layer = self._format_param(self.params[0])
        layer = self._format_param(self.params[0])
        # The tap parameter is typically a simple keycode for &lt
        # Format it directly using _format_param
        tap_keycode = self._format_param(self.params[1])
        return f"&lt {layer} {tap_keycode}"


class ModTapBehavior(Behavior):
    """Handles &mt (Mod-Tap)."""

    def _validate_params(self):
        if len(self.params) != 2:
            raise ValueError(
                f"{self.behavior_name} requires exactly 2 parameters (modifier, keycode/binding)."
            )

    def format_dtsi(self) -> str:
        mod = self._format_param(self.params[0])
        # The tap parameter is typically a simple keycode for &mt
        # Format it directly using _format_param
        tap_keycode = self._format_param(self.params[1])
        return f"&mt {mod} {tap_keycode}"


class LayerToggleBehavior(Behavior):
    """Handles &mo, &to, &tog."""

    def _validate_params(self):
        if len(self.params) != 1:
            raise ValueError(
                f"{self.behavior_name} requires exactly 1 parameter (layer)."
            )

    def format_dtsi(self) -> str:
        layer = self._format_param(self.params[0])
        return f"{self.behavior_name} {layer}"


class OneParamBehavior(Behavior):
    """Handles behaviors taking one parameter like &sk, &rgb_ug, &out, &bt BT_CLR."""

    def _validate_params(self):
        if len(self.params) != 1:
            raise ValueError(f"{self.behavior_name} requires exactly 1 parameter.")

    def format_dtsi(self) -> str:
        # The parameter could itself be complex, e.g., &sk LA(LC(LSHFT))
        # We need to format the parameter using format_binding if it's complex
        # The raw parameter data is needed for format_binding
        if not self.raw_params:
             logger.error(f"Behavior {self.behavior_name} missing raw parameters.")
             return f"&error /* {self.behavior_name} missing params */"

        # Assume the parameter is the first element in the raw_params list
        param_data = self.raw_params[0]

        # If the parameter data looks like a binding object (dict with 'value'),
        # it might be a simple keycode reference {'value': 'A'} or a complex
        # modifier stack {'value': 'LA', 'params': [...]}.
        # We need to format it like &kp does for modifiers.
        if isinstance(param_data, dict) and "value" in param_data:
            # Use the recursive formatter from KPBehavior to handle potential modifier stacks
            # We need an instance of KPBehavior to call its protected method, which isn't ideal.
            # Let's duplicate the relevant formatting logic here for now.
            # TODO: Refactor _format_kp_recursive into a shared utility function.
            param_formatted = KPBehavior._format_kp_recursive(KPBehavior(self.behavior_name, self.raw_params), param_data)

        else:
            # Otherwise, format it as a simple parameter (number, keycode name, etc.)
            # Use the parsed param value here
            param_formatted = self._format_param(self.params[0])

        return f"{self.behavior_name} {param_formatted}"


class BluetoothBehavior(Behavior):
    """Handles &bt commands like BT_SEL, BT_CLR, BT_NXT, BT_PRV."""

    def _validate_params(self):
        if not self.params or len(self.params) < 1 or len(self.params) > 2:
            raise ValueError(f"{self.behavior_name} requires 1 or 2 parameters.")
        if not isinstance(self.params[0], str) or not self.params[0].startswith("BT_"):
            raise ValueError(
                f"{self.behavior_name} first parameter must be a BT_ command."
            )
        if len(self.params) == 2 and self.params[0] not in [
            "BT_SEL",
            "BT_DISC",
        ]:  # Only SEL/DISC take index
            raise ValueError(
                f"{self.behavior_name} {self.params[0]} does not take a second parameter."
            )

    def format_dtsi(self) -> str:
        command = self._format_param(self.params[0])
        if len(self.params) == 2:
            index = self._format_param(self.params[1])
            return f"&bt {command} {index}"
        else:
            return f"&bt {command}"


class CustomBehaviorRef(Behavior):
    """Handles references to custom behaviors defined elsewhere (e.g., in hold-taps, macros)."""

    # Assumes parameters are simple values passed along
    def format_dtsi(self) -> str:
        # behavior_name starts with '&' already
        param_str = " ".join(self._format_param(p) for p in self.params)
        return f"{self.behavior_name} {param_str}".strip()


class RawBehavior(Behavior):
    """Handles passthrough for 'Custom' type or unrecognized '&' behaviors."""

    def format_dtsi(self) -> str:
        # Assume the first parameter is the intended raw string
        if self.params:
            return str(self.params[0])
        else:
            logger.warning(
                f"Raw/Custom behavior '{self.behavior_name}' used without parameters."
            )
            return f"&error /* Raw: {self.behavior_name} */"


# --- Behavior Factory ---
BEHAVIOR_CLASS_MAP: Dict[str, Type[Behavior]] = {
    "&none": SimpleBehavior,
    "&trans": SimpleBehavior,
    "&bootloader": SimpleBehavior,
    "&sys_reset": SimpleBehavior,
    "&reset": SimpleBehavior,  # Map alias
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
    "&msc": OneParamBehavior, # Mouse scroll
    "&mmv": OneParamBehavior, # Mouse move
    "&mkp": OneParamBehavior, # Mouse key press
    "&caps_word": SimpleBehavior, # No params
    # "&magic": DeprecatedBehavior, # Handle deprecated separately if needed
    # "&lower": DeprecatedBehavior,
    "Custom": RawBehavior,  # Handle the "Custom" type from JSON
    # Add other specific behaviors if they have unique parameter structures
}


# Keep the global format_binding function, but make it use the classes
def format_binding(binding_data: Dict[str, Any]) -> str:
    """
    Converts a JSON key binding object into a ZMK DTSI binding string
    using Behavior classes.
    """
    if not isinstance(binding_data, dict):
        logger.error(f"Invalid binding data format: {binding_data}")
        return "&error /* Invalid binding data */"

    value = binding_data.get("value")
    params_data = binding_data.get("params", [])

    if value is None:
        logger.warning("Binding data missing 'value'. Returning '&none'.")
        return "&none"

    behavior_class = BEHAVIOR_CLASS_MAP.get(value)

    if behavior_class:
        try:
            behavior_instance = behavior_class(value, params_data)
            return behavior_instance.format_dtsi()
        except Exception as e:
            logger.error(
                f"Error formatting behavior '{value}' with params {params_data}: {e}"
            )
            # Optionally include param details in error comment for debugging
            param_str = ", ".join(map(str, params_data))
            return f"&error /* {value}({param_str}): {e} */"
    elif isinstance(value, str) and value.startswith("&"):
        # Fallback for unknown behaviors starting with '&' - treat as custom ref
        try:
            behavior_instance = CustomBehaviorRef(value, params_data)
            return behavior_instance.format_dtsi()
        except Exception as e:
            logger.error(f"Error formatting custom ref '{value}': {e}")
            return f"&error /* CustomRef: {value} */"
    else:
        # Handle unexpected values (not starting with '&', not 'Custom', not None)
        logger.warning(f"Unexpected binding value '{value}'. Treating as error.")
        return f"&error /* Unexpected: {value} */"
