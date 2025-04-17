import re
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Type

logger = logging.getLogger(__name__)

# KEYCODE_MAP: Needs to be properly populated, e.g., from a config file or constants
# Example population (incomplete):
KEYCODE_MAP = {}

# Behavior Registry: Stores info about known behaviors
# Format: { "&behavior_name": {"expected_params": int, "origin": str} }
BEHAVIOR_REGISTRY: Dict[str, Dict[str, Any]] = {}


def register_behavior(name: str, expected_params: int, origin: str):
    """Registers a behavior and its expected parameter count."""
    if not name.startswith("&"):
        logger.warning(
            f"Attempting to register behavior without '&' prefix: {name}. Adding prefix."
        )
        name = f"&{name}"

    if name in BEHAVIOR_REGISTRY:
        # Allow re-registration but log it, might indicate overlapping definitions
        logger.debug(f"Re-registering behavior: {name}")
    BEHAVIOR_REGISTRY[name] = {"expected_params": expected_params, "origin": origin}
    logger.debug(
        f"Registered behavior: {name} (params: {expected_params}, origin: {origin})"
    )


def load_and_register_behaviors_from_json(file_path: Path):
    """Loads behavior definitions from a JSON file and registers them."""
    if not file_path.is_file():
        logger.error(f"Behavior definition file not found: {file_path}")
        return

    try:
        with open(file_path, "r") as f:
            behaviors_data = json.load(f)

        if not isinstance(behaviors_data, list):
            logger.error(
                f"Invalid format in {file_path}: Expected a list of behavior objects."
            )
            return

        logger.info(f"Loading behaviors from {file_path}...")
        for behavior_def in behaviors_data:
            name = behavior_def.get("name")
            expected_params = behavior_def.get("expected_params")
            origin = behavior_def.get(
                "origin", file_path.stem
            )  # Use filename stem as default origin

            if not name or not name.startswith("&") or expected_params is None:
                logger.warning(
                    f"Skipping invalid behavior definition in {file_path}: {behavior_def}"
                )
                continue

            # TODO: Handle conditional registration based on 'condition' field if needed
            # For now, register all found behaviors.
            register_behavior(name, expected_params, origin)

    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON from {file_path}")
    except Exception as e:
        logger.error(f"Error processing behavior file {file_path}: {e}")


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
            elif param == "MACRO_PLACEHOLDER":  # Handle macro placeholder literally
                return param
            # Check if it's a modifier alias - return the alias name directly
            # ZMK uses these directly for &kp, &mt etc. (e.g., &kp LCTL)
            elif param in [
                "LALT",
                "LCTL",
                "LSHFT",
                "LGUI",
                "RALT",
                "RCTL",
                "RSHFT",
                "RGUI",
                "LA",
                "LC",
                "LS",
                "LG",
                "RA",
                "RC",
                "RS",
                "RG",
            ]:  # Include function names if used simply
                return param
            else:
                # Assume it's a standard keycode or simple ZMK define name
                # get_keycode should handle potential KC_ prefixes if needed based on map
                return get_keycode(param)
        elif isinstance(param, int):
            return str(param)
        elif isinstance(
            param, Behavior
        ):  # If a param is a nested behavior (e.g., for &sk)
            return param.format_dtsi()
        else:
            # Removed debug logging for CAPSWord_v1_TKZ
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
            mod_name = param_data["value"]
            inner_params_data = param_data.get("params", [])

            # Case 1: Modifier Function (LA, LC, LS, LG, RA, RC, RS, RG)
            if mod_name in ["LA", "LC", "LS", "LG", "RA", "RC", "RS", "RG"]:
                if not inner_params_data:
                    logger.error(
                        f"Modifier function '{mod_name}' missing inner parameter."
                    )
                    return f"{mod_name}(ERROR_MOD_PARAM)"
                inner_formatted = self._format_kp_recursive(inner_params_data[0])
                return f"{mod_name}({inner_formatted})"

            # Case 2: Modifier Alias (LALT, LCTL, etc.)
            elif mod_name in [
                "LALT",
                "LCTL",
                "LSHFT",
                "LGUI",
                "RALT",
                "RCTL",
                "RSHFT",
                "RGUI",
            ]:
                if not inner_params_data:
                    # It's &kp LSHFT etc. Format the alias as a simple keycode param.
                    return self._format_param(mod_name)  # _format_param handles aliases
                else:
                    # It's &kp LALT(A) etc. Map alias to function and format recursively.
                    zmk_mod_func = {
                        "LALT": "LA",
                        "LCTL": "LC",
                        "LSHFT": "LS",
                        "LGUI": "LG",
                        "RALT": "RA",
                        "RCTL": "RC",
                        "RSHFT": "RS",
                        "RGUI": "RG",
                    }.get(mod_name)
                    inner_formatted = self._format_kp_recursive(inner_params_data[0])
                    return f"{zmk_mod_func}({inner_formatted})"

            # Case 3: Simple Keycode (A, SEMI, N1, etc.) or other value
            else:
                # Format the simple keycode value using _format_param
                return self._format_param(mod_name)

        elif isinstance(param_data, (str, int)):
            # Simple keycode or value passed directly (e.g., from macro param)
            # Format using _format_param which handles aliases
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
            param_formatted = KPBehavior._format_kp_recursive(
                KPBehavior(self.behavior_name, self.raw_params), param_data
            )

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


class LowerBehavior(Behavior):
    """Handles the deprecated &lower behavior."""

    def _validate_params(self):
        if self.params:
            logger.warning(
                f"{self.behavior_name} expects no parameters, found {len(self.params)}"
            )

    def format_dtsi(self) -> str:
        # Outputs the reference to the system-defined 'lower' tap-dance
        return "&lower"


class MagicBehavior(Behavior):
    """Handles the deprecated &magic behavior."""

    def _validate_params(self):
        # &magic in the keymap doesn't take explicit params in the JSON,
        # but the output format requires layer and key index (assumed 0).
        if self.params:
            logger.warning(
                f"{self.behavior_name} expects no parameters in JSON, found {len(self.params)}"
            )

    def format_dtsi(self) -> str:
        # Outputs the reference to the system-defined 'magic' hold-tap
        # Assumes LAYER_Magic is defined and key index 0 is appropriate.
        # TODO: Make layer name/index configurable if needed later.
        return "&magic LAYER_Magic 0"


class CustomBehaviorRef(Behavior):
    """Handles references to custom behaviors defined elsewhere (e.g., in hold-taps, macros)."""

    # Assumes parameters are simple values passed along
    def format_dtsi(self) -> str:
        # behavior_name starts with '&' already

        registry_info = BEHAVIOR_REGISTRY.get(self.behavior_name)

        if registry_info:
            expected_params = registry_info["expected_params"]
            origin = registry_info["origin"]

            # Handle zero-parameter behaviors explicitly - if a binding directly uses
            # a zero-param behavior like &kp(caps_word) (which is invalid zmk)
            # or &my_zero_param_macro()
            if expected_params == 0:
                if self.params:
                    logger.warning(
                        f"Binding directly uses zero-parameter behavior '{self.behavior_name}' (origin: {origin}) but passed {len(self.params)} parameters. Ignoring parameters."
                    )
                return self.behavior_name  # Output only the name

            # For behaviors expecting parameters (including hold-taps like &CAPSWord_v1_TKZ which expect 2 in the binding)
            # or variable params (-1), format the parameters provided in the binding data.
            # The check for mismatch is potentially noisy if variable params are common.
            # Let's just format what we are given if params are expected.
            # if expected_params > 0 and len(self.params) != expected_params:
            #     logger.warning(
            #             f"Behavior '{self.behavior_name}' (origin: {origin}) expects {expected_params} parameters but received {len(self.params)}. Formatting received params anyway."
            #         )

            formatted_params = []
            # Limit the loop to the number of expected parameters if known and positive
            params_to_format = self.params
            num_params_received = len(self.params)

            if expected_params > 0:  # Fixed positive number expected
                if num_params_received > expected_params:
                    logger.warning(
                        f"Behavior '{self.behavior_name}' (origin: {origin}) expects {expected_params} parameters but received {num_params_received}. Using only the first {expected_params}."
                    )
                    params_to_format = self.params[:expected_params]
                elif num_params_received < expected_params:
                    logger.warning(
                        f"Behavior '{self.behavior_name}' (origin: {origin}) expects {expected_params} parameters but received only {num_params_received}. Appending '0' for missing parameters."
                    )
                    # Proceed with formatting the parameters we have, then append '0's
            # Else (expected_params is -1 or 0), format all received params (handled above for 0)

            for p in params_to_format:  # Use the potentially truncated list
                formatted = self._format_param(p)
                formatted_params.append(formatted)

            # Append '0' for missing parameters if expected > received
            if expected_params > 0 and num_params_received < expected_params:
                missing_count = expected_params - num_params_received
                formatted_params.extend(["0"] * missing_count)

            param_str = " ".join(formatted_params)
            result = f"{self.behavior_name} {param_str}".strip()
            return result

        else:
            # Behavior not found in registry - fallback to old logic (format params)
            logger.warning(
                f"Behavior '{self.behavior_name}' not found in registry. Formatting all {len(self.params)} parameters as passed."
            )
            formatted_params = []
            for p in self.params:  # Format all params if unregistered
                formatted = self._format_param(p)
                formatted_params.append(formatted)

            param_str = " ".join(formatted_params)
            result = f"{self.behavior_name} {param_str}".strip()
            return result


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
    "&msc": OneParamBehavior,  # Mouse scroll
    "&mmv": OneParamBehavior,  # Mouse move
    "&mkp": OneParamBehavior,  # Mouse key press
    "&caps_word": SimpleBehavior,  # No params
    "&lower": LowerBehavior,  # Handle deprecated &lower
    "&magic": MagicBehavior,  # Handle deprecated &magic
    "Custom": RawBehavior,  # Handle the "Custom" type from JSON
    # Add other specific behaviors if they have unique parameter structures
}

# --- Remove old registration logic ---
# def get_behavior_expected_params(behavior_class: Type[Behavior]) -> int: ...
# def register_builtin_behaviors(): ...
# register_builtin_behaviors() # Remove immediate call

# --- Load behaviors from JSON files ---
# Determine paths relative to this file or pass them in?
# Assuming they are in a standard location relative to the script execution or package.
# This might need adjustment based on how the tool is run.
try:
    # Assuming execution from project root or similar standard structure
    # Use Path(__file__).parent to get the directory of the current behaviors.py file
    CURRENT_DIR = Path(__file__).parent
    CONFIG_DIR = CURRENT_DIR / "config"  # Assumes config is a sibling directory

    # Construct paths relative to the behaviors.py location
    ZMK_BEHAVIORS_PATH = CONFIG_DIR / "zmk_behaviors.json"
    # Path to system behaviors might depend on the specific keyboard config being used.
    # This needs to be determined dynamically, perhaps passed into a setup function.
    # For now, hardcoding the glove80 path as an example.
    GLOVE80_SYSTEM_BEHAVIORS_PATH = CONFIG_DIR / "glove80/v25.05/system_behaviors.json"

    load_and_register_behaviors_from_json(ZMK_BEHAVIORS_PATH)
    # Load system-specific behaviors AFTER core ZMK ones
    load_and_register_behaviors_from_json(GLOVE80_SYSTEM_BEHAVIORS_PATH)

except Exception as e:
    logger.error(f"Failed to load initial behavior definitions: {e}")


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
