"""Shared dependencies for layout commands."""

import logging
from functools import lru_cache

from glovebox.adapters import create_file_adapter, create_template_adapter
from glovebox.core.structlog_logger import get_struct_logger
from glovebox.layout import (
    LayoutService,
    ZmkFileContentGenerator,
    create_behavior_registry,
    create_enhanced_layout_service,
    create_grid_layout_formatter,
    create_layout_component_service,
    create_layout_display_service,
    create_layout_service,
)
from glovebox.layout.behavior.formatter import BehaviorFormatterImpl
from glovebox.layout.parsers import create_zmk_keymap_parser


logger = get_struct_logger(__name__)


@lru_cache(maxsize=1)
def create_full_layout_service() -> LayoutService:
    """Create a layout service with all required dependencies and zmk-layout integration.

    This function is cached to avoid recreating service dependencies
    multiple times within a CLI session. The cache ensures that we
    reuse the same service instances across commands.

    Returns:
        LayoutService: Fully configured layout service with all dependencies
                      and zmk-layout integration enabled by default
    """
    logger.debug(
        "Creating layout service with dependencies and zmk-layout integration (cached)"
    )

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

    # Create and return the enhanced layout service with zmk-layout integration
    return create_enhanced_layout_service(
        file_adapter=file_adapter,
        template_adapter=template_adapter,
        behavior_registry=behavior_registry,
        component_service=component_service,
        layout_display_service=layout_display_service,
        behavior_formatter=behavior_formatter,
        dtsi_generator=dtsi_generator,
        keymap_parser=keymap_parser,
        keyboard_id=None,  # Will be set by profile context
        enable_zmk_layout=True,  # Enable by default
    )


def clear_service_cache() -> None:
    """Clear the cached layout service.

    This should be called when the service needs to be recreated,
    such as after configuration changes or during testing.
    """
    logger.debug("Clearing layout service cache")
    create_full_layout_service.cache_clear()
