"""Glovebox - ZMK Keyboard Management Tool."""

from importlib.metadata import distribution

from .firmware.flash.models import FlashResult
from .firmware.models import BuildResult
from .layout.models import KeymapResult


__version__ = distribution(__package__ or "glovebox").version

__all__ = [
    "BuildResult",
    "FlashResult",
    "KeymapResult",
    "__version__",
]

# Import CLI after setting __version__ to avoid circular imports
from .cli import app, main


__all__ += ["app", "main"]
