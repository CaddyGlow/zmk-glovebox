"""Service for displaying keyboard layouts in various formats."""

import logging
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile

from glovebox.core.errors import KeymapError
from glovebox.layout.formatting import (
    GridLayoutFormatter,
    LayoutConfig,
    LayoutMetadata,
    ViewMode,
    create_grid_layout_formatter,
)
from glovebox.layout.models import LayoutData


logger = logging.getLogger(__name__)


class LayoutDisplayService:
    """Service for generating keyboard layout displays.

    Responsible for formatting and displaying keyboard layouts in terminal
    or other display formats.
    """

    def __init__(self, layout_generator: GridLayoutFormatter | None = None):
        """Initialize layout display service.

        Args:
            layout_generator: Optional layout generator dependency
        """
        self._service_name = "LayoutDisplayService"
        self._service_version = "1.0.0"
        self._layout_generator = layout_generator or GridLayoutFormatter()

    def show(
        self,
        keymap_data: LayoutData,
        profile: "KeyboardProfile",
        view_mode: ViewMode = ViewMode.NORMAL,
        layer_index: int | None = None,
    ) -> str:
        """Generate formatted layout display text.

        Args:
            keymap_data: Keymap data model
            profile: Keyboard profile containing layout configuration
            view_mode: Display mode (normal, compact, split)
            layer_index: Optional specific layer to display

        Returns:
            Formatted string representation of the keyboard layout

        Raises:
            KeymapError: If display generation fails
        """
        logger.info("Generating keyboard layout display")

        try:
            # Extract layout information
            title = keymap_data.title
            creator = keymap_data.creator or "N/A"
            locale = keymap_data.locale or "N/A"
            notes = keymap_data.notes or ""
            layer_names = keymap_data.layer_names
            layers = keymap_data.layers

            if not layers:
                raise KeymapError("No layers found in the keymap data")

            # Handle missing or mismatched layer names
            if not layer_names:
                logger.warning("No layer names found, using default names")
                layer_names = [f"Layer {i}" for i in range(len(layers))]
            elif len(layer_names) != len(layers):
                logger.warning(
                    "Mismatch between layer names (%d) and layer data (%d). "
                    "Using available names.",
                    len(layer_names),
                    len(layers),
                )
                if len(layer_names) < len(layers):
                    layer_names = layer_names + [
                        f"Layer {i}" for i in range(len(layer_names), len(layers))
                    ]
                else:
                    layer_names = layer_names[: len(layers)]

            # Extract configuration from profile
            keyboard_config = profile.keyboard_config
            keyboard_name = keyboard_config.keyboard
            display_config = keyboard_config.display

            # Use the LayoutData object directly instead of converting to dict
            # Update the keyboard field to use the profile's keyboard name if available
            if keyboard_name and keyboard_name != keymap_data.keyboard:
                # Create a copy with updated keyboard field if needed
                from dataclasses import replace

                display_data = replace(keymap_data, keyboard=keyboard_name)
            else:
                display_data = keymap_data

            # Determine row structure with priority order:
            # 1. Profile keymap.formatting.rows (highest priority)
            # 2. Display layout_structure.rows
            # 3. Default layout (fallback)
            keymap_formatting = keyboard_config.keymap.formatting

            if keymap_formatting.rows is not None:
                logger.debug("Using keymap.formatting.rows from profile")
                all_rows = keymap_formatting.rows
            elif display_config.layout_structure is not None:
                logger.debug("Using layout_structure.rows from display config")
                layout_structure = display_config.layout_structure
                # Handle LayoutStructure: dict[str, list[list[int]]]
                all_rows = []
                for row_segments in layout_structure.rows.values():
                    # Each row_segments is a list[list[int]] representing segments in the row
                    if len(row_segments) == 2:
                        # Split layout (left and right segments)
                        row = []
                        row.extend(row_segments[0])  # Left side
                        row.extend(row_segments[1])  # Right side
                        all_rows.append(row)
                    else:
                        # Concatenate all segments in the row
                        row = []
                        for segment in row_segments:
                            row.extend(segment)
                        all_rows.append(row)
            else:
                logger.info("No row structure configured, using default")
                all_rows = self._get_default_layout_rows()

            # Create a layout config
            layout_metadata = LayoutMetadata(
                keyboard_type=keyboard_name,
                description=f"{keyboard_name} layout",
                keyboard=keyboard_name,
            )

            # Create a key position map
            key_position_map = {}
            for i in range(keyboard_config.key_count):
                key_position_map[f"KEY_{i}"] = i

            # Create the layout config using display and keymap formatting options
            display_formatting = display_config.formatting
            layout_config = LayoutConfig(
                keyboard_name=keyboard_name,
                key_width=display_formatting.key_width,
                key_gap=keymap_formatting.key_gap,
                key_position_map=key_position_map,
                total_keys=keyboard_config.key_count,
                key_count=keyboard_config.key_count,
                rows=all_rows,
                metadata=layout_metadata,
                formatting={
                    "key_gap": keymap_formatting.key_gap,
                    "base_indent": keymap_formatting.base_indent,
                },
            )

            # Generate the layout display
            return self._layout_generator.format_keymap_display(
                display_data, layout_config, view_mode, layer_index
            )

        except Exception as e:
            logger.error("Error generating layout display: %s", e)
            raise KeymapError(f"Failed to generate layout display: {e}") from e

    def _get_default_layout_rows(self) -> list[list[int]]:
        """Get default layout structure as flattened rows.

        Returns:
            List of lists containing key indices for each row
        """
        # Default Glove80 layout structure flattened
        return [
            [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],  # Row 0
            [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21],  # Row 1
            [22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33],  # Row 2
            [34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45],  # Row 3
            [46, 47, 48, 49, 50, 51, 58, 59, 60, 61, 62, 63],  # Row 4
            [64, 65, 66, 67, 68, 75, 76, 77, 78, 79],  # Row 5
            [69, 52, 57, 74],  # Thumb row 1
            [70, 53, 56, 73],  # Thumb row 2
            [71, 54, 55, 72],  # Thumb row 3
        ]


def create_layout_display_service() -> LayoutDisplayService:
    """Create a LayoutDisplayService instance.

    Returns:
        Configured LayoutDisplayService instance
    """
    logger.debug("Creating LayoutDisplayService")

    layout_generator = create_grid_layout_formatter()
    return LayoutDisplayService(layout_generator)
