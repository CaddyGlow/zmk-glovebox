"""Layout module for DTSI layouts rendering.

This module is maintained for backwards compatibility.
It now imports classes from the generators.layout_generator module.
"""

import logging
from typing import Any, Optional

from glovebox.config.profile import KeyboardProfile
from glovebox.generators.layout_generator import (
    DtsiLayoutGenerator,
    LayoutConfig,
    LayoutMetadata,
    ViewMode,
)


logger = logging.getLogger(__name__)


class LayoutFormatter:
    """LayoutFormatter is maintained for backwards compatibility.

    It delegates to the new DtsiLayoutGenerator.
    """

    def __init__(self, layout_config: LayoutConfig | None = None) -> None:
        """Initialize the formatter with an optional layout configuration."""
        self.layout_config = layout_config
        self._generator = DtsiLayoutGenerator()

    def format_layer_bindings_grid(
        self, bindings: list[str], profile: KeyboardProfile
    ) -> list[str]:
        """Arrange formatted binding strings into a grid based on LayoutConfig."""
        return self._generator.generate_layer_layout(bindings, profile)

    def format_keymap_grid(
        self,
        keymap_data: dict[str, Any],
        layout_config: LayoutConfig,
        view_mode: ViewMode | None = None,
        layer_index: int | None = None,
    ) -> str:
        """Format a keymap using the provided layout configuration.

        Args:
            keymap_data: The keymap data to format
            layout_config: Layout configuration to use
            view_mode: Optional view mode to use
            layer_index: Optional specific layer to display

        Returns:
            Formatted keymap display
        """
        return self._generator.generate_keymap_display(
            keymap_data, layout_config, view_mode, layer_index
        )
