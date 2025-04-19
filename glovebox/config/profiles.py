# glovebox/config/profiles.py
import logging
from typing import List, Dict, Optional, Type, Any
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class Profile:
    """Base class for firmware configuration profiles."""

    name: str = "base"
    # ClassVar needed if we want strict class-level definition, but instance works too
    parent: Optional[Type["Profile"]] = None
    firmware_patterns: List[str] = []
    config_dir_name: Optional[str] = None
    board_name: Optional[str] = None
    system_behaviors_file: Optional[str] = "system_behaviors.json"
    kconfig_map_file: Optional[str] = "kconfig_mapping.json"
    key_position_header_file: Optional[str] = None
    system_behaviors_dts_file: Optional[str] = None  # Legacy/alternative
    layout_file: Optional[str] = None  # e.g., "glove80.json" in layout dir
    keycode_map_file: Optional[str] = None  # Future use
    template_file: Optional[str] = "keymap.dtsi.j2"  # Default template name

    # Base includes common to most ZMK setups
    includes: List[str] = [
        "<behaviors.dtsi>",
        "<dt-bindings/zmk/outputs.h>",
        "<dt-bindings/zmk/keys.h>",
        "<dt-bindings/zmk/bt.h>",
        "<dt-bindings/zmk/rgb.h>",
    ]
    # Conditional includes based on Kconfig flags
    conditional_includes: List[Dict[str, str]] = [
        {
            "include": "<dt-bindings/zmk/pointing.h>",
            "kconfig": "CONFIG_ZMK_POINTING",
        },
    ]

    # --- Instance methods for resolved data ---
    # These will be called on the *resolved* instance returned by the resolver

    def __init__(self, resolver: "ProfileResolver"):
        """
        Initialize a resolved profile instance.
        The resolver is passed to allow access to resolved paths/attributes.
        """
        self._resolver = resolver  # Store the resolver for accessing resolved data

    def get_resolved_attribute(self, attr_name: str, default: Any = None) -> Any:
        """Gets a resolved attribute value from the resolver."""
        return self._resolver.get_resolved_attribute(self.__class__, attr_name, default)

    def get_absolute_path(self, filename_attr: str) -> Optional[Path]:
        """
        Gets the absolute path for a config file attribute (e.g., kconfig_map_file).
        Returns None if the attribute or file is not found in the resolved hierarchy.
        """
        filename = self.get_resolved_attribute(filename_attr)
        if not filename:
            return None
        return self._resolver.find_config_file(self.__class__, filename)

    def get_resolved_includes(self, kconfig_settings: Dict[str, str]) -> List[str]:
        """
        Calculates the final list of includes based on base and conditional ones,
        checking against provided Kconfig settings.
        """
        # Use resolver to get merged lists from MRO
        base_includes = self._resolver.get_resolved_list_attribute(
            self.__class__, "includes"
        )
        conditional = self._resolver.get_resolved_list_attribute(
            self.__class__, "conditional_includes"
        )

        final_includes = list(base_includes)  # Start with base includes

        for item in conditional:
            include_path = item.get("include")
            kconfig_flag = item.get("kconfig")
            if include_path and kconfig_flag:
                # Check if the Kconfig flag is set to 'y' (or True)
                # Kconfig settings from generate_kconfig_conf might be 'y'/'n' or actual values
                # We primarily care if the flag enabling the feature is 'y'
                if str(kconfig_settings.get(kconfig_flag, "n")).lower() == "y":
                    if include_path not in final_includes:
                        final_includes.append(include_path)
            else:
                logger.warning(f"Invalid conditional include item: {item}")

        # Add hash includes
        final_includes = [f"#include {inc}" for inc in final_includes]

        return final_includes

    def load_system_behaviors(self) -> List[Dict[str, Any]]:
        """Loads and returns system behavior definitions from the resolved JSON file."""
        file_path = self.get_absolute_path("system_behaviors_file")
        if file_path and file_path.is_file():
            try:
                with open(file_path, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.error(f"Error decoding JSON from {file_path}")
            except Exception as e:
                logger.error(f"Error reading system behaviors file {file_path}: {e}")
        return []

    def load_kconfig_map(self) -> Dict[str, Dict[str, Any]]:
        """Loads and returns the Kconfig mapping from the resolved JSON file."""
        file_path = self.get_absolute_path("kconfig_map_file")
        if file_path and file_path.is_file():
            try:
                with open(file_path, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.error(f"Error decoding JSON from {file_path}")
            except Exception as e:
                logger.error(f"Error reading Kconfig map file {file_path}: {e}")
        return {}

    def load_key_position_header(self) -> Optional[str]:
        """Loads and returns the content of the key position header file."""
        file_path = self.get_absolute_path("key_position_header_file")
        if file_path and file_path.is_file():
            try:
                with open(file_path, "r") as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Error reading key position header {file_path}: {e}")
        return None

    def load_system_behaviors_dts(self) -> Optional[str]:
        """Loads and returns the content of the system behaviors DTS file."""
        file_path = self.get_absolute_path("system_behaviors_dts_file")
        if file_path and file_path.is_file():
            try:
                with open(file_path, "r") as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Error reading system behaviors DTS {file_path}: {e}")
        return None


# --- Concrete Profile Definitions ---


class ZmkBaseProfile(Profile):
    name = "zmk_base"
    # No specific patterns, acts as a base
    config_dir_name = "zmk/base"
    # Includes and conditional includes are inherited or overridden from Profile


class Glove80BaseProfile(ZmkBaseProfile):
    name = "glove80_base"
    # Matches glove80 firmware names OR version numbers like vXX.YY
    firmware_patterns = [
        r"^glove80/.*",
        r"^v\d{2}\.\d{2}.*",
        r"^pr34$",
        r"^zmk-update$",
        r"pull/34/.*",
    ]
    config_dir_name = "glove80/base"
    board_name = "glove80"
    key_position_header_file = "key_position.h"  # Found in glove80/base
    layout_file = "layout.json"  # Found in layout/
    system_behaviors_dts_file = (
        "system_behaviors.dts"  # System behaviors in DTS format ship by Moergo
    )
    system_behaviors_file = (
        "system_behaviors.json"  # used to register behaviors in `behaviors.py`
    )
    kconfig_map_file = "kconfig_mapping.json"  # mapping between Moergo json config name and kconfig options


class Glove80V2504Profile(Glove80BaseProfile):
    name = "glove80_v25.04"
    # More specific pattern for v25.05, and also allow matching the profile name itself
    firmware_patterns = [
        r"^v25\.04.*",
        r"^glove80_v25\.04$",
        r"^pr38$",
        r"pull/38/.*",
    ]  # Added exact match for profile name
    # Specific config files for this version reside here
    config_dir_name = "glove80/v25.04"
    conditional_includes = (
        Glove80BaseProfile.conditional_includes
        + [
            # {
            #     "include": "<input/processors.h>",
            #     "kconfig": "CONFIG_ZMK_POINTING",
            # },
            # {
            #     "include": "<dt-bindings/zmk/input_transform.h>",
            #     "kconfig": "CONFIG_ZMK_POINTING",
            # },
            # {
            #     "include": "<dt-bindings/zmk/pointing.h>",
            #     "kconfig": "CONFIG_ZMK_POINTING",
            # },
        ]
    )


# include <dt-bindings/zmk/input_transform.h>
# include <dt-bindings/zmk/pointing.h>
# include <input/processors.dtsi>

# Example for a potential future community profile
# class CommunityPr36Profile(Glove80BaseProfile):
#     name = "community_pr36"
#     firmware_patterns = [r"^pr36.*"]
#     config_dir_name = "community/pr36"
#     # Override or add specific settings/files for PR36
#     kconfig_map_file = "kconfig_mapping_pr36.json" # Example override
#     conditional_includes = Glove80BaseProfile.conditional_includes + [
#         {"include": "<dt-bindings/zmk/rgb_layer.h>", "kconfig": "CONFIG_EXPERIMENTAL_RGB_LAYER"},
#     ]

# Add more profiles here as needed...
