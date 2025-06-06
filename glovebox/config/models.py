"""
Type definitions for keyboard configuration (DEPRECATED).

This module is maintained for backward compatibility.
Please import models from the glovebox.models package instead.
"""

# Re-export models from models package
from glovebox.models import (
    BuildConfig,
    BuildOptions,
    FirmwareConfig,
    FlashConfig,
    FormattingConfig,
    KConfigOption,
    KeyboardConfig,
    KeymapSection,
    VisualLayout,
)


__all__ = [
    "BuildConfig",
    "BuildOptions",
    "FirmwareConfig",
    "FlashConfig",
    "FormattingConfig",
    "KConfigOption",
    "KeyboardConfig",
    "KeymapSection",
    "VisualLayout",
]
