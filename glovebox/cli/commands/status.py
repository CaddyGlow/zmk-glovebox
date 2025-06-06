"""Status command for Glovebox CLI."""

import logging
import platform
import subprocess
from importlib.metadata import distribution
from pathlib import Path

import typer

from glovebox.cli.decorators import handle_errors


# Import version directly to avoid circular imports
__version__ = distribution("glovebox").version
from glovebox.config.keyboard_config import (
    get_available_keyboards,
    load_keyboard_config,
)


logger = logging.getLogger(__name__)


@handle_errors
def status_command() -> None:
    """Show system status and diagnostics."""
    print(f"Glovebox v{__version__}\n")

    # Check dependencies
    dependencies = {
        "Docker": "docker --version",
    }

    print("System Dependencies:")
    print("-" * 50)
    print("Tool\tStatus\tVersion")

    for name, cmd in dependencies.items():
        try:
            result = subprocess.run(
                cmd.split(), check=True, capture_output=True, text=True, timeout=5
            )
            print(f"{name}\tAvailable\t{result.stdout.strip()}")
        except (
            subprocess.SubprocessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ):
            print(f"{name}\tMissing\tNot found")

    # Show keyboards and firmwares
    keyboards = get_available_keyboards()
    print(f"\nAvailable Keyboards: {len(keyboards)}")
    for keyboard in keyboards:
        print(f"  • {keyboard}")

        try:
            # Load keyboard config to get available firmwares
            config = load_keyboard_config(keyboard)
            firmwares = config.firmwares
            if firmwares:
                print(f"    Firmwares: {len(firmwares)}")
                for firmware in firmwares:
                    print(f"      ‣ {firmware}")
        except Exception as e:
            print(f"    Error loading keyboard config: {e}")

    # Environment info
    print("\nEnvironment:")
    print("-" * 50)
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Python: {platform.python_version()}")
    print(f"Working Directory: {Path.cwd().as_posix()}")


def register_commands(app: typer.Typer) -> None:
    """Register status command with the main app.

    Args:
        app: The main Typer app
    """
    app.command(name="status")(status_command)
