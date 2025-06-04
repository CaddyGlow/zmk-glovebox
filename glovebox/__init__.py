"""Glovebox - ZMK Keyboard Management Tool."""

from importlib.metadata import distribution

from .models import BuildResult, FlashResult, KeymapResult


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
