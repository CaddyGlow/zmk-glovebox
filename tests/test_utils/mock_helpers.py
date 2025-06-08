"""Helper functions for creating standardized mocks in tests."""

from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional, Protocol, Union
from unittest.mock import Mock, patch

from glovebox.config.models import (
    BuildConfig,
    BuildOptions,
    FirmwareConfig,
    FlashConfig,
    FormattingConfig,
    KConfigOption,
    KeyboardConfig,
    KeymapSection,
)
from glovebox.config.profile import KeyboardProfile
from glovebox.models import SystemBehavior
from glovebox.models.build import FirmwareOutputFiles
from glovebox.models.results import BuildResult, FlashResult, LayoutResult


def create_mock_build_result(
    success: bool = True,
    messages: list[str] | None = None,
    output_dir: Path | None = None,
    main_uf2: Path | None = None,
) -> BuildResult:
    """Create a standardized BuildResult for testing."""
    if messages is None:
        messages = ["Firmware built successfully"]

    if output_dir is None:
        output_dir = Path("/tmp/test/output")

    if main_uf2 is None and output_dir is not None:
        main_uf2 = output_dir / "firmware.uf2"

    output_files = FirmwareOutputFiles(
        main_uf2=main_uf2,
        output_dir=output_dir,
    )

    return BuildResult(
        success=success,
        messages=messages,
        output_files=output_files,
    )


def create_mock_layout_result(
    success: bool = True,
    keymap_path: Path | None = None,
    conf_path: Path | None = None,
    json_path: Path | None = None,
    errors: list[str] | None = None,
) -> LayoutResult:
    """Create a standardized LayoutResult for testing."""
    result = LayoutResult(success=success)

    if keymap_path is not None:
        result.keymap_path = keymap_path
    elif success:
        result.keymap_path = Path("/tmp/test/output/keymap.keymap")

    if conf_path is not None:
        result.conf_path = conf_path
    elif success:
        result.conf_path = Path("/tmp/test/output/keymap.conf")

    if json_path is not None:
        result.json_path = json_path
    elif success:
        result.json_path = Path("/tmp/test/output/keymap.json")

    if errors is not None:
        for error in errors:
            result.errors.append(error)

    return result


# Backward compatibility alias
def create_mock_keymap_result(*args, **kwargs) -> LayoutResult:
    """Backward compatibility alias for create_mock_layout_result."""
    return create_mock_layout_result(*args, **kwargs)


def create_mock_flash_result(
    success: bool = True,
    devices_flashed: int = 1,
    devices_failed: int = 0,
    device_details: list[dict[str, str]] | None = None,
    messages: list[str] | None = None,
) -> FlashResult:
    """Create a standardized FlashResult for testing."""
    if device_details is None and success:
        device_details = [
            {"name": f"Device {i + 1}", "status": "success"}
            for i in range(devices_flashed)
        ]

    if messages is None:
        messages = ["Firmware flashed successfully"]

    result = FlashResult(
        success=success,
        devices_flashed=devices_flashed,
        devices_failed=devices_failed,
        device_details=device_details or [],
    )

    for message in messages:
        result.add_message(message)

    return result


@contextmanager
def patch_behavior_registry(registry: Mock):
    """Patch a behavior registry with proper protocol methods."""
    registry._behaviors = {}

    # ruff: noqa: SIM117 - Nested with statements are more readable here
    with patch.object(registry, "list_behaviors", return_value=registry._behaviors):
        with patch.object(
            registry,
            "register_behavior",
            side_effect=lambda behavior: registry._behaviors.update(
                {behavior.code: behavior}
            ),
        ):
            yield registry


def setup_mock_behavior_registry() -> Mock:
    """Set up a mock behavior registry that correctly implements the protocol."""
    # We don't use the actual BehaviorRegistry class, just mock it
    registry = Mock()
    registry._behaviors = {}

    # Set up behavior list method
    registry.list_behaviors = Mock(side_effect=lambda: registry._behaviors)

    # Set up behavior register method
    registry.register_behavior = Mock(
        side_effect=lambda behavior: registry._behaviors.update(
            {behavior.code: behavior}
        )
    )

    return registry


def create_mock_system_behaviors(
    behavior_codes: list[str] | None = None,
) -> list[SystemBehavior]:
    """Create a list of mock SystemBehavior objects with specified codes."""
    if behavior_codes is None:
        behavior_codes = ["&kp", "&bt", "&lt", "&mo"]

    behaviors = []
    for code in behavior_codes:
        # Default values
        name = code
        description = f"{code} behavior"
        expected_params = 1
        origin = "zmk"
        params: list[Any] = []
        includes = None

        # Special cases
        if code == "&lt":
            expected_params = 2
        elif code == "&bt":
            includes = ["#include <dt-bindings/zmk/bt.h>"]

        behavior = SystemBehavior(
            code=code,
            name=name,
            description=description,
            expected_params=expected_params,
            origin=origin,
            params=params,
            includes=includes,
        )
        behaviors.append(behavior)

    return behaviors
