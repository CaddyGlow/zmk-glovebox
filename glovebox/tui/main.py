#!/usr/bin/env python3
"""Entry point for the Glovebox Textual TUI application."""

from .app import GloveboxTUIApp


def main() -> None:
    """Main entry point for the TUI application."""
    app = GloveboxTUIApp()
    app.run()


if __name__ == "__main__":
    main()
