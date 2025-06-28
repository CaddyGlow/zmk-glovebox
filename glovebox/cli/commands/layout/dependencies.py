"""Shared dependencies for layout commands."""

import logging
from functools import lru_cache

from glovebox.adapters import create_file_adapter, create_template_adapter
from glovebox.layout import (
    create_behavior_registry,
    create_grid_layout_formatter,
    create_layout_component_service,
    create_layout_display_service,
    create_layout_service,
)
from glovebox.layout.behavior.formatter import BehaviorFormatterImpl
from glovebox.layout.parsers import create_zmk_keymap_parser
from glovebox.layout.service import LayoutService
from glovebox.layout.zmk_generator import ZmkFileContentGenerator


logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def create_full_layout_service() -> LayoutService:
    """Create a layout service with all required dependencies.

    This function is cached to avoid recreating service dependencies
    multiple times within a CLI session. The cache ensures that we
    reuse the same service instances across commands.

    Returns:
        LayoutService: Fully configured layout service with all dependencies
    """
    logger.debug("Creating layout service with dependencies (cached)")

    # Create adapters
    file_adapter = create_file_adapter()
    template_adapter = create_template_adapter()

    # Create behavior-related components
    behavior_registry = create_behavior_registry()
    behavior_formatter = BehaviorFormatterImpl(behavior_registry)

    # Create generators and formatters
    dtsi_generator = ZmkFileContentGenerator(behavior_formatter)
    layout_generator = create_grid_layout_formatter()

    # Create services
    component_service = create_layout_component_service(file_adapter)
    layout_display_service = create_layout_display_service(layout_generator)
    keymap_parser = create_zmk_keymap_parser()

    # Create and return the main layout service
    return create_layout_service(
        file_adapter=file_adapter,
        template_adapter=template_adapter,
        behavior_registry=behavior_registry,
        component_service=component_service,
        layout_service=layout_display_service,
        behavior_formatter=behavior_formatter,
        dtsi_generator=dtsi_generator,
        keymap_parser=keymap_parser,
    )


def clear_service_cache() -> None:
    """Clear the cached layout service.

    This should be called when the service needs to be recreated,
    such as after configuration changes or during testing.
    """
    logger.debug("Clearing layout service cache")
    create_full_layout_service.cache_clear()
