"""Service for displaying keyboard layouts in various formats."""

import logging
import textwrap
from typing import Any, TypeAlias, cast

from glovebox.config.profile import KeyboardProfile
from glovebox.core.errors import KeymapError
from glovebox.generators.layout_generator import (
    DtsiLayoutGenerator,
    LayoutConfig,
    LayoutMetadata,
    ViewMode,
)
from glovebox.services.base_service import BaseServiceImpl


logger = logging.getLogger(__name__)


# Type aliases for internal use
KeymapDict: TypeAlias = dict[str, Any]


class LayoutDisplayService(BaseServiceImpl):
    """Service for generating keyboard layout displays.

    Responsible for formatting and displaying keyboard layouts in terminal
    or other display formats.
    """

    def __init__(self, layout_generator: DtsiLayoutGenerator | None = None):
        """Initialize layout display service.

        Args:
            layout_generator: Optional layout generator dependency
        """
        super().__init__(service_name="LayoutDisplayService", service_version="1.0.0")
        self._layout_generator = layout_generator or DtsiLayoutGenerator()

    def generate_display(
        self,
        keymap_data: KeymapDict,
        keyboard: str,
        key_width: int = 10,
        view_mode: ViewMode = ViewMode.NORMAL,
    ) -> str:
        """Generate formatted layout display text.

        Args:
            keymap_data: Keymap data dictionary
            keyboard: Keyboard name for layout configuration
            key_width: Width of keys in the display
            view_mode: Display mode (normal, compact, split)

        Returns:
            Formatted string representation of the keyboard layout

        Raises:
            KeymapError: If display generation fails
        """
        logger.info("Generating keyboard layout display")

        try:
            # Extract layout information
            title = (
                keymap_data.get("title") or keymap_data.get("name") or "Untitled Layout"
            )
            creator = keymap_data.get("creator", "N/A")
            locale = keymap_data.get("locale", "N/A")
            notes = keymap_data.get("notes", "")
            layer_names = keymap_data.get("layer_names", [])
            layers = keymap_data.get("layers", [])

            if not layers:
                raise KeymapError("No layers found in the keymap data")

            # Handle missing or mismatched layer names
            if not layer_names:
                logger.warning("No layer names found, using default names")
                layer_names = [f"Layer {i}" for i in range(len(layers))]
            elif len(layer_names) != len(layers):
                logger.warning(
                    "Mismatch between layer names (%d) and layer data (%d). Using available names.",
                    len(layer_names),
                    len(layers),
                )
                if len(layer_names) < len(layers):
                    layer_names = layer_names + [
                        f"Layer {i}" for i in range(len(layer_names), len(layers))
                    ]
                else:
                    layer_names = layer_names[: len(layers)]

            # Prepare keymap data for the generator
            display_data = {
                "title": title,
                "creator": creator,
                "locale": locale,
                "notes": notes,
                "keyboard": keyboard,
                "layer_names": layer_names,
                "layers": layers,
            }

            # Get layout structure for the keyboard
            layout_structure = self._get_keyboard_layout_structure(keyboard)

            # Flatten the structure to get all row indices
            all_rows = []
            for indices_pair in layout_structure.values():
                row = []
                row.extend(indices_pair[0])  # Left side
                row.extend(indices_pair[1])  # Right side
                all_rows.append(row)

            # Create a layout config
            layout_metadata = LayoutMetadata(
                keyboard_type=keyboard,
                description=f"{keyboard} layout",
                keyboard=keyboard,
            )

            # Create a key position map
            key_position_map = {}
            for i in range(80):  # Default key count
                key_position_map[f"KEY_{i}"] = i

            # Create the layout config
            layout_config = LayoutConfig(
                keyboard_name=keyboard,
                key_width=key_width,
                key_gap=" ",
                key_position_map=key_position_map,
                total_keys=80,
                key_count=80,
                rows=all_rows,
                metadata=layout_metadata,
                formatting={
                    "default_key_width": key_width,
                    "key_gap": " ",
                    "base_indent": "",
                },
            )

            # Generate the layout display
            return self._layout_generator.generate_keymap_display(
                display_data, layout_config, view_mode
            )

        except Exception as e:
            logger.error("Error generating layout display: %s", e)
            raise KeymapError(f"Failed to generate layout display: {e}") from e

    def _get_keyboard_layout_structure(
        self, keyboard: str
    ) -> dict[str, list[list[int]]]:
        """Get the keyboard layout structure.

        Args:
            keyboard: Keyboard name

        Returns:
            Dictionary mapping row names to key indices
        """
        # Default to Glove80 layout structure
        return {
            "row0": [[0, 1, 2, 3, 4], [5, 6, 7, 8, 9]],
            "row1": [[10, 11, 12, 13, 14, 15], [16, 17, 18, 19, 20, 21]],
            "row2": [[22, 23, 24, 25, 26, 27], [28, 29, 30, 31, 32, 33]],
            "row3": [[34, 35, 36, 37, 38, 39], [40, 41, 42, 43, 44, 45]],
            "row4": [[46, 47, 48, 49, 50, 51], [58, 59, 60, 61, 62, 63]],
            "row5": [[64, 65, 66, 67, 68], [75, 76, 77, 78, 79]],
            "thumb1": [[69, 52], [57, 74]],
            "thumb2": [[70, 53], [56, 73]],
            "thumb3": [[71, 54], [55, 72]],
        }


def create_layout_display_service() -> LayoutDisplayService:
    """Create a LayoutDisplayService instance.

    Returns:
        Configured LayoutDisplayService instance
    """
    logger.debug("Creating LayoutDisplayService")

    from glovebox.generators.layout_generator import create_layout_generator

    layout_generator = create_layout_generator()

    return LayoutDisplayService(layout_generator)
