"""Command-line interface for Glovebox using Typer."""

from glovebox.cli.app import __version__, app, main, setup_logging


__all__ = ["app", "main", "__version__", "setup_logging"]
