"""Display service for keyboard layouts."""

import logging
import textwrap
from typing import Any, Optional

from glovebox.config.keyboard_config import (
    create_keyboard_profile,
    create_profile_from_keyboard_name,
    get_available_keyboards,
    load_keyboard_config_raw,
)
from glovebox.config.profile import KeyboardProfile
from glovebox.formatters.behavior_formatter import BehaviorFormatterImpl
from glovebox.generators.layout_generator import (
    DtsiLayoutGenerator,
    LayoutConfig,
    LayoutMetadata,
    ViewMode,
)
from glovebox.layout import LayoutFormatter
from glovebox.models.keymap import KeymapBinding, KeymapData
from glovebox.services.base_service import BaseServiceImpl
from glovebox.services.behavior_service import BehaviorRegistryImpl


logger = logging.getLogger(__name__)


class KeymapDisplayService(BaseServiceImpl):
    """Service for displaying keyboard layouts."""

    def __init__(
        self,
        behavior_registry: BehaviorRegistryImpl | None = None,
        layout_generator: DtsiLayoutGenerator | None = None,
    ) -> None:
        """Initialize the display service with its dependencies.

        Args:
            behavior_registry: Optional behavior registry for behavior formatting
            layout_generator: Optional layout generator for generating layouts
        """
        super().__init__(service_name="KeymapDisplayService", service_version="1.0.0")
        self._behavior_registry = behavior_registry or BehaviorRegistryImpl()
        self._behavior_formatter = BehaviorFormatterImpl(self._behavior_registry)
        # Create a default layout config - will be replaced when needed
        default_layout_config = LayoutConfig(
            keyboard_name="default",
            key_width=10,
            key_gap="  ",
            key_position_map={},
        )
        self._layout_generator = layout_generator or DtsiLayoutGenerator()
        # Keep the layout formatter for backwards compatibility
        self._layout_formatter = LayoutFormatter(default_layout_config)

    def get_service_info(self) -> dict[str, str]:
        """Return information about this service.

        Returns:
            Dictionary with service information
        """
        return {
            "name": "KeymapDisplayService",
            "version": "1.0.0",
            "description": "Service for displaying keyboard layouts",
        }

    def format_key(
        self,
        key_data: dict[str, Any] | KeymapBinding | Any,
        max_width: int = 10,
    ) -> str:
        """Format a single key binding for display."""
        blank_output = " ".center(max_width)

        # Convert KeymapBinding to dict if needed
        if isinstance(key_data, KeymapBinding):
            binding_dict = key_data.model_dump()
        elif isinstance(key_data, dict):
            binding_dict = key_data
        else:
            # Handle non-dict inputs including None
            return blank_output

        if not binding_dict:
            return blank_output

        try:
            # Special handling for specific behaviors for better display
            if binding_dict.get("value") == "&none":
                return "&none".center(max_width)
            elif binding_dict.get("value") == "&trans":
                return "▽".center(max_width)
            elif binding_dict.get("value") == "&bl":
                return "bootloader".center(max_width)
            elif binding_dict.get("value") == "&kp" and not binding_dict.get("params"):
                return "&error".center(max_width)

            # Get the DTSI formatted string using the standard formatter
            dtsi_string = self._behavior_formatter.format_binding(binding_dict)

            # Process the DTSI string for display
            if dtsi_string == "&none":
                display_string = " "
            elif dtsi_string == "&trans":
                display_string = "▽"
            elif dtsi_string.startswith("&error"):
                display_string = "ERR"
                logger.warning(f"Error formatting binding {key_data}: {dtsi_string}")
            elif dtsi_string.startswith("&"):
                display_string = dtsi_string[1:]
            else:
                display_string = dtsi_string

        except Exception as e:
            logger.error(f"Unexpected error calling format_binding for {key_data}: {e}")
            display_string = "ERR:Fmt"

        # Apply display-specific overrides based on behavior type
        value = binding_dict.get("value")
        params = binding_dict.get("params", [])

        if value == "&mt" and len(params) >= 1:
            mod_param = params[0]
            mod = (
                mod_param.get("value", "")
                if isinstance(mod_param, dict)
                else str(mod_param)
            )
            display_string = f"mt {mod}"
        elif value == "&lt" and len(params) == 2:
            layer_param = params[0]
            key_param = params[1]
            layer = (
                layer_param.get("value", "")
                if isinstance(layer_param, dict)
                else str(layer_param)
            )
            key = (
                key_param.get("value", "")
                if isinstance(key_param, dict)
                else str(key_param)
            )
            full_lt = f"lt {layer} {key}"
            short_lt = f"lt {layer}"
            display_string = full_lt if len(full_lt) <= max_width else short_lt
        elif value == "&bt" and len(params) >= 1:
            cmd_param = params[0]
            cmd = (
                cmd_param.get("value", "")
                if isinstance(cmd_param, dict)
                else str(cmd_param)
            )
            display_string = f"bt {cmd}"
        elif value == "&rgb_ug" and len(params) >= 1:
            display_string = "rgb_ug RGB"
        elif value == "&out" and len(params) >= 1:
            display_string = "out OUT_U"

        # Truncate if too long using ellipsis BEFORE centering
        if len(display_string) > max_width:
            display_string = display_string[: max_width - 1] + "…"

        # Pad with spaces to ensure consistent width using center()
        return display_string.center(max_width)

    def display_layout(
        self,
        keymap_data: dict[str, Any] | KeymapData,
        key_width: int = 10,
    ) -> str:
        """Display the keyboard layout from the parsed JSON data."""
        # Convert KeymapData to dict if needed
        if isinstance(keymap_data, KeymapData):
            data_dict = keymap_data.to_dict()
            # Use structured layers for better type safety
            keymap_data.get_structured_layers()
        else:
            data_dict = keymap_data
        output_lines = []

        def _add_line(line: str = "") -> None:
            output_lines.append(line)

        title = data_dict.get("title") or data_dict.get("name") or "Untitled Layout"
        creator = data_dict.get("creator", "N/A")
        locale = data_dict.get("locale", "N/A")
        notes = data_dict.get("notes", "")

        header_width = 80
        _add_line("=" * header_width)
        _add_line(f"Keyboard: {data_dict.get('keyboard', 'N/A')} | Title: {title}")
        _add_line(f"Creator: {creator} | Locale: {locale}")
        if notes:
            wrapped_notes = textwrap.wrap(notes, width=header_width - len("Notes: "))
            _add_line(f"Notes: {wrapped_notes[0]}")
            for line in wrapped_notes[1:]:
                _add_line(f"       {line}")
        _add_line("=" * header_width)

        layer_names = data_dict.get("layer_names", [])
        layers = data_dict.get("layers", [])

        if not layers:
            raise ValueError("No layers found in the keymap data.") from None
        if not layer_names:
            logger.warning("No layer names found, using default names.")
            layer_names = [f"Layer {i}" for i in range(len(layers))]
        elif len(layer_names) != len(layers):
            logger.warning(
                f"Mismatch between layer names ({len(layer_names)}) and layer data ({len(layers)}). Using available names."
            )
            if len(layer_names) < len(layers):
                layer_names = layer_names + [
                    f"Layer {i}" for i in range(len(layer_names), len(layers))
                ]
            else:
                layer_names = layer_names[: len(layers)]

        # Layout Structure (Glove80 specific)
        l_row0_idx = [0, 1, 2, 3, 4]
        r_row0_idx = [5, 6, 7, 8, 9]
        l_row1_idx = [10, 11, 12, 13, 14, 15]
        r_row1_idx = [16, 17, 18, 19, 20, 21]
        l_row2_idx = [22, 23, 24, 25, 26, 27]
        r_row2_idx = [28, 29, 30, 31, 32, 33]
        l_row3_idx = [34, 35, 36, 37, 38, 39]
        r_row3_idx = [40, 41, 42, 43, 44, 45]
        l_row4_idx = [46, 47, 48, 49, 50, 51]
        r_row4_idx = [58, 59, 60, 61, 62, 63]
        l_row5_idx = [64, 65, 66, 67, 68]
        r_row5_idx = [75, 76, 77, 78, 79]

        thumb_l1 = [69, 52]
        thumb_r1 = [57, 74]
        thumb_l2 = [70, 53]
        thumb_r2 = [56, 73]
        thumb_l3 = [71, 54]
        thumb_r3 = [55, 72]

        # Calculate widths and padding
        h_spacer = " | "
        key_gap = " "

        main_block_width = key_width * 6 + len(key_gap) * 5
        row5_width = key_width * 5 + len(key_gap) * 4
        total_width = main_block_width * 2 + len(h_spacer)

        pad_5_key_left = key_width + len(key_gap)
        pad_5_key_right = 0

        thumb_width = key_width * 2 + len(key_gap)
        thumb_pad_l = main_block_width - thumb_width
        mid_thumb_spacer = h_spacer
        thumb_pad_r = 0

        # Iterate through layers
        for i, layer_data in enumerate(layers):
            layer_name = layer_names[i]
            _add_line(f"\n--- Layer {i}: {layer_name} ---")

            num_keys_in_layer = len(layer_data)
            expected_keys = 80
            if num_keys_in_layer != expected_keys:
                logger.warning(
                    f"Layer '{layer_name}' has {num_keys_in_layer} keys, expected {expected_keys}. Display may be incomplete."
                )

            # NB023: Use default arguments to capture loop variables
            def get_fmt_key(
                idx: int,
                current_layer_data: list = layer_data,
                current_num_keys: int = num_keys_in_layer,
                current_key_width: int = key_width,
            ) -> str:
                if 0 <= idx < current_num_keys:
                    return self.format_key(current_layer_data[idx], current_key_width)
                return " ".center(current_key_width)

            _add_line("-" * total_width)

            # Row 0 (Top pinky cluster)
            l_row0 = key_gap.join([get_fmt_key(k) for k in l_row0_idx])
            r_row0 = key_gap.join([get_fmt_key(k) for k in r_row0_idx])
            _add_line(
                f"{' ' * pad_5_key_left}{l_row0}{h_spacer}{r_row0}{' ' * pad_5_key_right}"
            )

            # Row 1 (Number row)
            l_row1 = key_gap.join([get_fmt_key(k) for k in l_row1_idx])
            r_row1 = key_gap.join([get_fmt_key(k) for k in r_row1_idx])
            _add_line(f"{l_row1}{h_spacer}{r_row1}")

            # Row 2 (Top alpha row)
            l_row2 = key_gap.join([get_fmt_key(k) for k in l_row2_idx])
            r_row2 = key_gap.join([get_fmt_key(k) for k in r_row2_idx])
            _add_line(f"{l_row2}{h_spacer}{r_row2}")

            # Row 3 (Home row)
            l_row3 = key_gap.join([get_fmt_key(k) for k in l_row3_idx])
            r_row3 = key_gap.join([get_fmt_key(k) for k in r_row3_idx])
            _add_line(f"{l_row3}{h_spacer}{r_row3}")

            # Row 4 (Bottom alpha row)
            l_row4 = key_gap.join([get_fmt_key(k) for k in l_row4_idx])
            r_row4 = key_gap.join([get_fmt_key(k) for k in r_row4_idx])
            _add_line(f"{l_row4}{h_spacer}{r_row4}")

            # Row 5 (Bottom pinky cluster)
            l_row5 = key_gap.join([get_fmt_key(k) for k in l_row5_idx])
            r_row5 = key_gap.join([get_fmt_key(k) for k in r_row5_idx])
            _add_line(
                f"{' ' * pad_5_key_left}{l_row5}{h_spacer}{r_row5}{' ' * pad_5_key_right}"
            )

            _add_line("-" * total_width)

            # Thumb Clusters
            l_thumb1 = key_gap.join([get_fmt_key(k) for k in thumb_l1])
            r_thumb1 = key_gap.join([get_fmt_key(k) for k in thumb_r1])
            _add_line(
                f"{' ' * thumb_pad_l}{l_thumb1}{mid_thumb_spacer}{r_thumb1}{' ' * thumb_pad_r}"
            )

            l_thumb2 = key_gap.join([get_fmt_key(k) for k in thumb_l2])
            r_thumb2 = key_gap.join([get_fmt_key(k) for k in thumb_r2])
            _add_line(
                f"{' ' * thumb_pad_l}{l_thumb2}{mid_thumb_spacer}{r_thumb2}{' ' * thumb_pad_r}"
            )

            l_thumb3 = key_gap.join([get_fmt_key(k) for k in thumb_l3])
            r_thumb3 = key_gap.join([get_fmt_key(k) for k in thumb_r3])
            _add_line(
                f"{' ' * thumb_pad_l}{l_thumb3}{mid_thumb_spacer}{r_thumb3}{' ' * thumb_pad_r}"
            )

            _add_line("-" * total_width)

        return "\n".join(output_lines)

    def display_keymap_with_layout(
        self,
        keymap_data: dict[str, Any] | KeymapData,
        profile: KeyboardProfile | None = None,
        layout_name: str | None = None,
        keyboard_type: str | None = None,
        view_mode: str | None = None,
        layer_index: int | None = None,
    ) -> str:
        """
        Display keymap using the enhanced layout system.

        Args:
            keymap_data: Keymap data to display
            profile: Optional keyboard profile to use for layout configuration
            layout_name: Optional name of layout to use
            keyboard_type: Optional keyboard type for fallback layout selection
            view_mode: Optional view mode to use
            layer_index: Optional specific layer to display

        Returns:
            Formatted keymap display
        """
        # Convert KeymapData to dict if needed
        if isinstance(keymap_data, KeymapData):
            data_dict = keymap_data.to_dict()
        else:
            data_dict = keymap_data

        # Get a layout configuration
        layout_config = self._get_layout_config(profile, keyboard_type, data_dict)
        if not layout_config:
            # Fall back to the old display method if no layout found
            return self.display_layout(data_dict)

        # Convert view mode string to enum if provided
        view_mode_enum = None
        if view_mode:
            try:
                view_mode_enum = ViewMode(view_mode.lower())
            except ValueError:
                logger.warning(f"Unknown view mode: {view_mode}. Using default.")

        # Generate the keymap display using the layout generator
        return self._layout_generator.generate_keymap_display(
            data_dict, layout_config, view_mode_enum, layer_index
        )

    def _get_layout_config(
        self,
        profile: KeyboardProfile | None = None,
        keyboard_type: str | None = None,
        keymap_data: dict[str, Any] | None = None,
    ) -> LayoutConfig | None:
        """
        Get a layout configuration based on the provided parameters.

        Args:
            profile: Optional keyboard profile to use
            keyboard_type: Optional keyboard type for fallback
            keymap_data: Keymap data which might contain keyboard info

        Returns:
            LayoutConfig if found, None otherwise
        """
        # If profile is provided, use it directly
        if profile:
            return self._create_layout_config_from_keyboard_profile(profile)

        # If no profile, try to determine keyboard type
        if not keyboard_type and keymap_data:
            keyboard_type = keymap_data.get("keyboard")

        # If still no keyboard type, try to get it from available configurations
        if not keyboard_type:
            # Try to determine keyboard from available configurations
            keyboards = get_available_keyboards()
            if keyboards:
                # Use the first keyboard as fallback if there's no explicit info
                keyboard_type = keyboards[0]
                logger.debug(
                    f"No keyboard specified, using first available: {keyboard_type}"
                )

        if keyboard_type:
            # Try to create a profile from keyboard type and use that
            try:
                # Create a profile with default firmware version
                profile = create_profile_from_keyboard_name(keyboard_type)
                if profile:
                    return self._create_layout_config_from_keyboard_profile(profile)
            except Exception as e:
                logger.warning(f"Failed to create profile for {keyboard_type}: {e}")

                # Fall back to directly loading config for backward compatibility
                try:
                    keyboard_config = load_keyboard_config_raw(keyboard_type)
                    return self._create_layout_config_from_keyboard_config(
                        keyboard_config
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to load keyboard config for {keyboard_type}: {e}"
                    )

        # If no layout found, return None to fall back to old method
        return None

    def _create_layout_config_from_keyboard_profile(
        self, profile: KeyboardProfile
    ) -> LayoutConfig:
        """
        Create a layout configuration from a keyboard profile.

        Args:
            profile: Keyboard profile to create layout config from

        Returns:
            LayoutConfig created from the keyboard profile
        """
        keyboard_config = profile.keyboard_config
        keyboard_name = keyboard_config.keyboard

        # Create a default row structure for Glove80-like keyboards
        default_rows = [
            [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],  # Row 0
            [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21],  # Row 1
            [22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33],  # Row 2
            [34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45],  # Row 3
            [
                46,
                47,
                48,
                49,
                50,
                51,
                52,
                53,
                54,
                55,
                56,
                57,
                58,
                59,
                60,
                61,
                62,
                63,
            ],  # Row 4
            [64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79],  # Row 5
        ]

        # Key position map for default layout
        key_position_map = {}
        for i in range(80):  # Default for typical split keyboard
            key_position_map[f"KEY_{i}"] = i

        # Create a layout configuration
        metadata = LayoutMetadata(
            keyboard_type=keyboard_name,
            description=getattr(
                keyboard_config, "description", f"Default {keyboard_name} layout"
            ),
            keyboard=keyboard_name,
        )

        # Create the configuration with required parameters first
        layout_config = LayoutConfig(
            keyboard_name=keyboard_name,
            key_width=10,  # Default
            key_gap="  ",  # Default
            key_position_map=key_position_map,
        )

        # Then set the additional fields
        layout_config.total_keys = 80  # Default for Glove80
        layout_config.key_count = 80
        layout_config.rows = default_rows
        layout_config.metadata = metadata
        layout_config.formatting = {"default_key_width": 10, "key_gap": "  "}

        return layout_config

    def _create_layout_config_from_keyboard_config(
        self, keyboard_config: dict[str, Any]
    ) -> LayoutConfig:
        """
        Create a layout configuration from a keyboard configuration dictionary.

        This method is kept for backward compatibility.

        Args:
            keyboard_config: Keyboard configuration dictionary

        Returns:
            LayoutConfig created from the keyboard configuration
        """
        keyboard_name = keyboard_config.get("keyboard", "unknown")

        # Create a default row structure for Glove80-like keyboards
        default_rows = [
            [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],  # Row 0
            [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21],  # Row 1
            [22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33],  # Row 2
            [34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45],  # Row 3
            [
                46,
                47,
                48,
                49,
                50,
                51,
                52,
                53,
                54,
                55,
                56,
                57,
                58,
                59,
                60,
                61,
                62,
                63,
            ],  # Row 4
            [64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79],  # Row 5
        ]

        # Key position map for default layout
        key_position_map = {}
        for i in range(80):  # Default for typical split keyboard
            key_position_map[f"KEY_{i}"] = i

        # Create a layout configuration
        metadata = LayoutMetadata(
            keyboard_type=keyboard_name,
            description=keyboard_config.get(
                "description", f"Default {keyboard_name} layout"
            ),
            keyboard=keyboard_name,
        )

        # Create the configuration with required parameters first
        layout_config = LayoutConfig(
            keyboard_name=keyboard_name,
            key_width=10,  # Default
            key_gap="  ",  # Default
            key_position_map=key_position_map,
        )

        # Then set the additional fields
        layout_config.total_keys = 80  # Default for Glove80
        layout_config.key_count = 80
        layout_config.rows = default_rows
        layout_config.metadata = metadata
        layout_config.formatting = {"default_key_width": 10, "key_gap": "  "}

        return layout_config


# Helper function moved to keyboard_config.py


def create_display_service(
    behavior_registry: BehaviorRegistryImpl | None = None,
    layout_generator: DtsiLayoutGenerator | None = None,
) -> KeymapDisplayService:
    """Create a KeymapDisplayService instance.

    Args:
        behavior_registry: Optional behavior registry for behavior formatting
        layout_generator: Optional layout generator for generating layouts

    Returns:
        KeymapDisplayService instance
    """
    return KeymapDisplayService(
        behavior_registry=behavior_registry,
        layout_generator=layout_generator,
    )
