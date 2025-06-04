# This file marks the 'glovebox' directory as a Python package.
# Core functionalities will be exposed via submodules like 'glovebox.core'.

# from ._version import __version__
from importlib.metadata import distribution

from .models import BuildResult, FlashResult, KeymapResult


__version__ = distribution(__package__ or "glovebox").version

__all__ = [
    "BuildResult",
    "FlashResult",
    "KeymapResult",
    "__version__",
]


def test_function() -> str:
    """
    A simple test function to verify that the package is working.

    Returns:
        A simple test string
    """
    return "expected"
