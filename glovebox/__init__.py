"""Glovebox - ZMK Keyboard Management Tool."""

try:
    from importlib.metadata import distribution
    __version__ = distribution(__package__ or "glovebox").version
except Exception:
    # Fallback for development environments or when package not installed
    __version__ = "0.0.2-dev"

__all__ = [
    "__version__",
]

# Import CLI after setting __version__ to avoid circular imports
from .cli import app, main


__all__ += ["app", "main"]
