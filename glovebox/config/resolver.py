# glovebox/config/resolver.py
import importlib
import inspect
import logging
import re
import importlib.resources
from pathlib import Path
from typing import List, Dict, Optional, Type, Any, Tuple, Set

# Import the Profile base class directly
from .profiles import Profile

logger = logging.getLogger(__name__)

# --- Helper Functions ---


def _merge_lists(list_of_lists: List[List[Any]]) -> List[Any]:
    """Merges lists, preserving order and uniqueness, prioritizing items from later lists."""
    seen = set()
    merged = []
    # Iterate in reverse to prioritize items from more specific profiles (later in MRO)
    for sublist in reversed(list_of_lists):
        for item in reversed(sublist):
            # Use tuple representation for dicts to make them hashable for the set
            item_repr = tuple(sorted(item.items())) if isinstance(item, dict) else item
            if item_repr not in seen:
                seen.add(item_repr)
                merged.insert(
                    0, item
                )  # Insert at beginning to maintain original relative order
    return merged


def _merge_dicts(list_of_dicts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merges dictionaries, with values from later dicts overriding earlier ones."""
    merged = {}
    for d in list_of_dicts:
        merged.update(d)
    return merged


class ProfileResolver:
    """Discovers, matches, and resolves configuration profiles."""

    def __init__(self, base_config_package: str = "glovebox.config"):
        """
        Initializes the resolver.

        Args:
            base_config_package: The Python package path where config profiles and data reside.
                                 Defaults to "glovebox.config".
        """
        self.base_config_package = base_config_package
        self.profiles: Dict[str, Type[Profile]] = self._discover_profiles()
        self._base_config_path: Optional[Path] = self._find_base_config_path()
        if not self._base_config_path:
            logger.error(
                f"Could not locate base config directory for package '{base_config_package}'. Resolution may fail."
            )

    def _find_base_config_path(self) -> Optional[Path]:
        """Finds the filesystem path to the base configuration package directory."""
        try:
            # Use the modern importlib.resources API
            # importlib.resources.files returns a Traversable object representing the package directory
            package_traversable = importlib.resources.files(self.base_config_package)

            # We need a concrete Path object. Using 'as_file' provides a context
            # manager that yields a real filesystem path, potentially creating a
            # temporary file/directory if the resource is inside a zip file.
            with importlib.resources.as_file(package_traversable) as path:
                if path.is_dir():
                    logger.debug(f"Found base config directory at: {path}")
                    return path.resolve()  # Return the resolved absolute path
                else:
                    # This case should be less common with importlib.resources.files
                    # unless the package structure is unusual.
                    logger.warning(
                        f"Expected a directory for package '{self.base_config_package}', but got: {path}"
                    )
                    return None
        except ModuleNotFoundError:
            logger.error(f"Base config package '{self.base_config_package}' not found.")
            return None
        except Exception as e:
            logger.error(
                f"Error finding base config path for '{self.base_config_package}': {e}"
            )
            return None

    def _discover_profiles(self) -> Dict[str, Type[Profile]]:
        """Discovers all Profile subclasses within the profiles module."""
        profiles_found = {}
        profiles_module_name = f"{self.base_config_package}.profiles"
        try:
            # Dynamically import the profiles module relative to the base config package
            profiles_module = importlib.import_module(profiles_module_name)

            for name, obj in inspect.getmembers(profiles_module):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, Profile)
                    and obj is not Profile  # Exclude the base class itself
                ):
                    profile_name = getattr(obj, "name", None)
                    if profile_name:
                        if profile_name in profiles_found:
                            logger.warning(
                                f"Duplicate profile name '{profile_name}' found. Overwriting."
                            )
                        profiles_found[profile_name] = obj
                        logger.debug(
                            f"Discovered profile: {profile_name} ({obj.__name__})"
                        )
                    else:
                        logger.warning(
                            f"Profile class {obj.__name__} is missing 'name' attribute. Skipping."
                        )
        except ModuleNotFoundError:
            logger.error(f"Profiles module '{profiles_module_name}' not found.")
        except Exception as e:
            logger.error(f"Error discovering profiles: {e}")
        return profiles_found

    def list_available_profiles(self) -> List[str]:
        """Returns a list of names of the discovered profiles."""
        return sorted(list(self.profiles.keys()))

    def find_profile(self, firmware_name: str) -> Optional[Type[Profile]]:
        """
        Finds the best matching Profile class for a given firmware name.

        Args:
            firmware_name: The firmware name string (e.g., "v25.05", "glove80/main").

        Returns:
            The matched Profile class, or None if no match is found.
        """
        best_match = None
        highest_specificity = -1  # Track specificity (e.g., pattern length)

        logger.info(f"Attempting to find profile for firmware: '{firmware_name}'")
        logger.debug(f"Available profiles: {list(self.profiles.keys())}")

        for profile_cls in self.profiles.values():
            patterns = getattr(profile_cls, "firmware_patterns", [])
            if not patterns:
                logger.debug(
                    f"Profile '{profile_cls.name}' has no patterns, skipping match."
                )
                continue

            for pattern in patterns:
                try:
                    # Use fullmatch to ensure the entire firmware name matches
                    if re.fullmatch(pattern, firmware_name):
                        # Simple specificity: longer pattern = more specific
                        specificity = len(pattern)
                        logger.debug(
                            f"Firmware '{firmware_name}' matches pattern '{pattern}' for profile '{profile_cls.name}' (specificity: {specificity})"
                        )
                        if specificity > highest_specificity:
                            highest_specificity = specificity
                            best_match = profile_cls
                            logger.debug(f"New best match: '{profile_cls.name}'")
                        # Optional: Add tie-breaking logic here if needed
                        break  # Move to next profile class once a pattern matches
                except re.error as e:
                    logger.warning(
                        f"Invalid regex pattern '{pattern}' in profile {profile_cls.name}: {e}"
                    )

        if best_match:
            logger.info(f"Found best match profile: '{best_match.name}'")
        else:
            logger.warning(
                f"No profile found matching firmware name: '{firmware_name}'"
            )

        return best_match

    def get_resolved_attribute(
        self, profile_cls: Type[Profile], attr_name: str, default: Any = None
    ) -> Any:
        """
        Resolves a single attribute value by walking the MRO.
        Finds the first class in the MRO that defines the attribute.
        """
        for cls in profile_cls.__mro__:
            if issubclass(cls, Profile) and hasattr(cls, attr_name):
                value = getattr(cls, attr_name)
                # Ensure we don't get the default from the base Profile class if overridden
                if value is not None:  # Check for None specifically
                    # Check if the attribute is defined directly on cls, not inherited from its parent within Profile hierarchy
                    if (
                        attr_name in cls.__dict__ or cls is Profile
                    ):  # Allow base Profile defaults
                        logger.debug(
                            f"Resolved attribute '{attr_name}' to '{value}' from class '{cls.__name__}'"
                        )
                        return value
        logger.debug(
            f"Attribute '{attr_name}' not found in MRO for '{profile_cls.name}', returning default '{default}'"
        )
        return default

    def get_resolved_list_attribute(
        self, profile_cls: Type[Profile], attr_name: str
    ) -> List[Any]:
        """Resolves a list attribute by merging lists from the MRO."""
        lists_to_merge = []
        for cls in profile_cls.__mro__:
            if issubclass(cls, Profile) and hasattr(cls, attr_name):
                # Check if the attribute is defined directly on cls
                if attr_name in cls.__dict__:
                    value = getattr(cls, attr_name)
                    if isinstance(value, list):
                        logger.debug(
                            f"Found list attribute '{attr_name}' in class '{cls.__name__}': {value}"
                        )
                        lists_to_merge.append(value)
                    else:
                        logger.warning(
                            f"Attribute '{attr_name}' in '{cls.__name__}' is not a list, skipping merge."
                        )

        merged = _merge_lists(lists_to_merge)
        logger.debug(f"Resolved merged list for '{attr_name}': {merged}")
        return merged

    def find_config_file(
        self, profile_cls: Type[Profile], filename: str
    ) -> Optional[Path]:
        """
        Finds a configuration file by searching config directories defined in the MRO.
        Starts from the most specific profile and walks up the inheritance chain.

        Args:
            profile_cls: The specific profile class that was matched.
            filename: The base name of the file to find (e.g., "kconfig_mapping.json").

        Returns:
            The absolute Path to the file if found, otherwise None.
        """
        if not self._base_config_path:
            logger.error("Base config path not set, cannot find config file.")
            return None
        if not filename:
            logger.warning(
                f"Cannot search for an empty filename (profile: {profile_cls.name})."
            )
            return None

        logger.debug(
            f"Searching for config file '{filename}' for profile '{profile_cls.name}'"
        )
        for cls in profile_cls.__mro__:
            if issubclass(cls, Profile) and hasattr(cls, "config_dir_name"):
                config_dir_name = getattr(cls, "config_dir_name")
                if config_dir_name:
                    # Construct path relative to the base config directory
                    potential_path = self._base_config_path / config_dir_name / filename
                    logger.debug(f"Checking path: {potential_path}")
                    if potential_path.is_file():
                        logger.info(
                            f"Found config file '{filename}' at: {potential_path}"
                        )
                        return potential_path.resolve()  # Return absolute path

        logger.warning(
            f"Config file '{filename}' not found in MRO search path for profile '{profile_cls.name}'."
        )
        return None

    def resolve(self, firmware_name: str) -> Optional[Profile]:
        """
        Resolves the configuration for a given firmware name.

        Args:
            firmware_name: The firmware name string.

        Returns:
            An *instance* of the resolved Profile class, configured with access
            to resolved data via the resolver, or None if no profile matches.
        """
        matched_cls = self.find_profile(firmware_name)
        if matched_cls:
            # Return an instance, passing self (the resolver) to its constructor
            return matched_cls(self)
        return None


# Example Usage (for testing)
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    resolver = ProfileResolver()
    print("Available profiles:", resolver.list_available_profiles())

    # --- Test Resolution ---
    test_firmware = "v25.05-testbuild"
    resolved_profile_instance = resolver.resolve(test_firmware)

    if resolved_profile_instance:
        print(
            f"\nResolved profile for '{test_firmware}': {resolved_profile_instance.name}"
        )

        # --- Test Attribute Resolution ---
        print(
            f"  Board Name: {resolved_profile_instance.get_resolved_attribute('board_name')}"
        )
        print(
            f"  Key Pos Header File: {resolved_profile_instance.get_resolved_attribute('key_position_header_file')}"
        )
        print(
            f"  Sys Behaviors File: {resolved_profile_instance.get_resolved_attribute('system_behaviors_file')}"
        )  # Should be from v25.05
        print(
            f"  Layout File: {resolved_profile_instance.get_resolved_attribute('layout_file')}"
        )  # Should be from glove80_base

        # --- Test Path Resolution ---
        kconfig_path = resolved_profile_instance.get_absolute_path("kconfig_map_file")
        print(
            f"  Kconfig Map Path: {kconfig_path} (Exists: {kconfig_path.is_file() if kconfig_path else 'N/A'})"
        )

        keypos_path = resolved_profile_instance.get_absolute_path(
            "key_position_header_file"
        )
        print(
            f"  Key Pos Header Path: {keypos_path} (Exists: {keypos_path.is_file() if keypos_path else 'N/A'})"
        )

        sysbehav_path = resolved_profile_instance.get_absolute_path(
            "system_behaviors_file"
        )
        print(
            f"  Sys Behaviors Path: {sysbehav_path} (Exists: {sysbehav_path.is_file() if sysbehav_path else 'N/A'})"
        )

        layout_path = resolved_profile_instance.get_layout_path()
        print(
            f"  Layout Path: {layout_path} (Exists: {layout_path.is_file() if layout_path else 'N/A'})"
        )

        template_path = resolved_profile_instance.get_template_path()
        print(
            f"  Template Path: {template_path} (Exists: {template_path.is_file() if template_path else 'N/A'})"
        )
        breakpoint()
        # --- Test Include Resolution (dummy kconfig) ---
        dummy_kconfig = {"CONFIG_ZMK_POINTING": "y", "CONFIG_OTHER_FLAG": "n"}
        includes = resolved_profile_instance.get_resolved_includes(dummy_kconfig)
        print(f"  Resolved Includes ({dummy_kconfig}):")
        for inc in includes:
            print(f"    {inc}")

        dummy_kconfig_no_pointing = {"CONFIG_ZMK_POINTING": "n"}
        includes_no_pointing = resolved_profile_instance.get_resolved_includes(
            dummy_kconfig_no_pointing
        )
        print(f"  Resolved Includes ({dummy_kconfig_no_pointing}):")
        for inc in includes_no_pointing:
            print(f"    {inc}")

        # --- Test Data Loading ---
        kconfig_map_data = resolved_profile_instance.load_kconfig_map()
        print(
            f"  Loaded Kconfig Map: {bool(kconfig_map_data)} keys"
        )  # Just check if loaded

        sys_behaviors_data = resolved_profile_instance.load_system_behaviors()
        print(f"  Loaded System Behaviors: {len(sys_behaviors_data)} items")

        keypos_header_content = resolved_profile_instance.load_key_position_header()
        print(f"  Loaded Key Pos Header: {bool(keypos_header_content)} content")

        sys_behaviors_dts_content = (
            resolved_profile_instance.load_system_behaviors_dts()
        )
        print(
            f"  Loaded System Behaviors DTS: {bool(sys_behaviors_dts_content)} content"
        )

    else:
        print(f"\nCould not resolve profile for '{test_firmware}'")

    # Test non-matching firmware
    resolved_none = resolver.resolve("unknown-firmware-xyz")
    print(f"\nResolved profile for 'unknown-firmware-xyz': {resolved_none}")
