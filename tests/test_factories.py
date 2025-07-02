"""Test factory functions for dependency injection.

These provide sensible defaults for testing while maintaining explicit dependencies in production.
"""

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from glovebox.compilation.services.moergo_nix_service import MoergoNixService
    from glovebox.compilation.services.zmk_west_service import ZmkWestService
    from glovebox.firmware.flash.device_detector import DeviceDetector
    from glovebox.firmware.flash.flasher_methods import USBFlasher
    from glovebox.firmware.flash.service import FlashService
    from glovebox.layout import (
        LayoutComponentService,
        LayoutDisplayService,
        LayoutService,
    )
    from glovebox.protocols.usb_adapter_protocol import USBAdapterProtocol


def create_layout_service_for_tests(
    file_adapter=None,
    template_adapter=None,
    behavior_registry=None,
    component_service=None,
    layout_service=None,
    behavior_formatter=None,
    dtsi_generator=None,
) -> "LayoutService":
    """Create a LayoutService with test-friendly defaults.

    This is a test-specific factory that provides sensible defaults for all dependencies.
    Production code should use create_layout_service() with explicit dependencies.
    """
    from glovebox.adapters import create_file_adapter, create_template_adapter
    from glovebox.layout import (
        ZmkFileContentGenerator,
        create_behavior_registry,
        create_grid_layout_formatter,
        create_layout_component_service,
        create_layout_display_service,
        create_layout_service,
    )
    from glovebox.layout.behavior.formatter import BehaviorFormatterImpl

    # Create defaults if not provided
    if file_adapter is None:
        file_adapter = create_file_adapter()
    if template_adapter is None:
        template_adapter = create_template_adapter()
    if behavior_registry is None:
        behavior_registry = create_behavior_registry()
    if behavior_formatter is None:
        behavior_formatter = BehaviorFormatterImpl(behavior_registry)
    if dtsi_generator is None:
        dtsi_generator = ZmkFileContentGenerator(behavior_formatter)
    if layout_service is None:
        layout_generator = create_grid_layout_formatter()
        layout_service = create_layout_display_service(layout_generator)
    if component_service is None:
        component_service = create_layout_component_service(file_adapter)

    return create_layout_service(
        file_adapter=file_adapter,
        template_adapter=template_adapter,
        behavior_registry=behavior_registry,
        component_service=component_service,
        layout_service=layout_service,
        behavior_formatter=behavior_formatter,
        dtsi_generator=dtsi_generator,
    )


def create_layout_component_service_for_tests(
    file_adapter=None,
) -> "LayoutComponentService":
    """Create a LayoutComponentService with test-friendly defaults."""
    from glovebox.adapters import create_file_adapter
    from glovebox.layout import create_layout_component_service

    if file_adapter is None:
        file_adapter = create_file_adapter()

    return create_layout_component_service(file_adapter)


def create_layout_display_service_for_tests(
    layout_generator=None,
) -> "LayoutDisplayService":
    """Create a LayoutDisplayService with test-friendly defaults."""
    from glovebox.layout import (
        create_grid_layout_formatter,
        create_layout_display_service,
    )

    if layout_generator is None:
        layout_generator = create_grid_layout_formatter()

    return create_layout_display_service(layout_generator)


def create_usb_adapter_for_tests(
    flash_operations=None, detector=None
) -> "USBAdapterProtocol":
    """Create a USBAdapter with test-friendly defaults."""
    from glovebox.adapters.usb_adapter import create_usb_adapter
    from glovebox.firmware.flash.device_detector import (
        MountPointCache,
        create_device_detector,
    )
    from glovebox.firmware.flash.flash_operations import create_flash_operations
    from glovebox.firmware.flash.os_adapters import create_flash_os_adapter
    from glovebox.firmware.flash.usb_monitor import create_usb_monitor

    if flash_operations is None:
        os_adapter = create_flash_os_adapter()
        flash_operations = create_flash_operations(os_adapter)

    if detector is None:
        mount_cache = MountPointCache()
        usb_monitor = create_usb_monitor()
        detector = create_device_detector(usb_monitor, mount_cache)

    return create_usb_adapter(flash_operations, detector)


def create_flash_service_for_tests(
    file_adapter=None, device_wait_service=None, loglevel="INFO"
) -> "FlashService":
    """Create a FlashService with test-friendly defaults."""
    from glovebox.adapters import create_file_adapter
    from glovebox.firmware.flash import create_flash_service
    from glovebox.firmware.flash.device_wait_service import create_device_wait_service

    if file_adapter is None:
        file_adapter = create_file_adapter()

    if device_wait_service is None:
        device_wait_service = create_device_wait_service()

    return create_flash_service(
        file_adapter, device_wait_service, usb_adapter=None, loglevel=loglevel
    )


def create_usb_flasher_for_tests(usb_adapter=None, file_adapter=None) -> "USBFlasher":
    """Create a USBFlasher with test-friendly defaults."""
    from glovebox.adapters import create_file_adapter
    from glovebox.firmware.flash import create_usb_flasher

    if file_adapter is None:
        file_adapter = create_file_adapter()

    if usb_adapter is None:
        usb_adapter = create_usb_adapter_for_tests()

    return create_usb_flasher(usb_adapter, file_adapter)


def create_device_detector_for_tests(
    usb_monitor=None, mount_cache=None
) -> "DeviceDetector":
    """Create a DeviceDetector with test-friendly defaults."""
    from glovebox.firmware.flash.device_detector import (
        MountPointCache,
        create_device_detector,
    )
    from glovebox.firmware.flash.usb_monitor import create_usb_monitor

    if usb_monitor is None:
        usb_monitor = create_usb_monitor()

    if mount_cache is None:
        mount_cache = MountPointCache()

    return create_device_detector(usb_monitor, mount_cache)


def create_layout_comparison_service_for_tests(user_config=None, file_adapter=None):
    """Create a LayoutComparisonService with test-friendly defaults."""
    from glovebox.adapters import create_file_adapter
    from glovebox.config import create_user_config
    from glovebox.layout.comparison.service import create_layout_comparison_service

    if user_config is None:
        user_config = create_user_config()

    if file_adapter is None:
        file_adapter = create_file_adapter()

    return create_layout_comparison_service(user_config, file_adapter)


def create_layout_layer_service_for_tests(file_adapter=None):
    """Create a LayoutLayerService with test-friendly defaults."""
    from glovebox.adapters import create_file_adapter
    from glovebox.layout.layer.service import create_layout_layer_service

    if file_adapter is None:
        file_adapter = create_file_adapter()

    return create_layout_layer_service(file_adapter)


def create_moergo_nix_service_for_tests(
    docker_adapter=None, file_adapter=None, session_metrics=None
):
    """Create a MoergoNixService with test-friendly defaults."""
    from glovebox.adapters import create_docker_adapter, create_file_adapter
    from glovebox.compilation.services.moergo_nix_service import (
        create_moergo_nix_service,
    )
    from glovebox.core.cache import create_default_cache
    from glovebox.core.metrics.session_metrics import SessionMetrics

    if docker_adapter is None:
        docker_adapter = create_docker_adapter()

    if file_adapter is None:
        file_adapter = create_file_adapter()

    if session_metrics is None:
        cache_manager = create_default_cache(tag="test")
        session_metrics = SessionMetrics(
            cache_manager=cache_manager, session_uuid="test-session"
        )

    return create_moergo_nix_service(docker_adapter, file_adapter, session_metrics)


def create_zmk_west_service_for_tests(
    user_config=None,
    docker_adapter=None,
    file_adapter=None,
    cache_manager=None,
    workspace_cache_service=None,
    build_cache_service=None,
    session_metrics=None,
):
    """Create a ZmkWestService with test-friendly defaults."""
    from unittest.mock import Mock

    from glovebox.adapters import create_docker_adapter, create_file_adapter
    from glovebox.compilation.services.zmk_west_service import create_zmk_west_service
    from glovebox.config import create_user_config
    from glovebox.core.cache import create_default_cache

    if user_config is None:
        user_config = create_user_config()

    if docker_adapter is None:
        docker_adapter = create_docker_adapter()

    if file_adapter is None:
        file_adapter = create_file_adapter()

    if cache_manager is None:
        cache_manager = create_default_cache(tag="test_compilation")

    if workspace_cache_service is None:
        workspace_cache_service = Mock()  # Mock complex service for tests

    if build_cache_service is None:
        build_cache_service = Mock()  # Mock complex service for tests

    return create_zmk_west_service(
        user_config=user_config,
        docker_adapter=docker_adapter,
        file_adapter=file_adapter,
        cache_manager=cache_manager,
        workspace_cache_service=workspace_cache_service,
        build_cache_service=build_cache_service,
        session_metrics=session_metrics,
    )
