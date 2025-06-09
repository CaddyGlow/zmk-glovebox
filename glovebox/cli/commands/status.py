"""Status command for Glovebox CLI."""

import json
import logging
import platform
import subprocess
from importlib.metadata import distribution
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from glovebox.cli.decorators import handle_errors


# Import version directly to avoid circular imports
__version__ = distribution("glovebox").version
from glovebox.config.keyboard_profile import (
    get_available_keyboards,
    load_keyboard_config,
)


logger = logging.getLogger(__name__)


def _collect_status_data() -> dict[str, Any]:
    """Collect all status data into a structured format."""
    # Version information
    version = __version__

    # Check dependencies
    dependencies_info = {}
    dependencies = {
        "Docker": "docker --version",
    }

    for name, cmd in dependencies.items():
        try:
            result = subprocess.run(
                cmd.split(), check=True, capture_output=True, text=True, timeout=5
            )
            dependencies_info[name] = {
                "status": "available",
                "version": result.stdout.strip(),
            }
        except (
            subprocess.SubprocessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ):
            dependencies_info[name] = {
                "status": "missing",
                "version": "Not found",
            }

    # Collect keyboard information
    keyboards_info = []
    keyboards = get_available_keyboards()

    for keyboard in keyboards:
        keyboard_data: dict[str, Any] = {"name": keyboard}
        try:
            config = load_keyboard_config(keyboard)
            firmwares = config.firmwares

            if firmwares:
                firmware_list = []
                for firmware_name, firmware_config in firmwares.items():
                    firmware_list.append(
                        {
                            "name": firmware_name,
                            "description": firmware_config.description,
                            "version": firmware_config.version,
                        }
                    )

                keyboard_data["firmwares"] = firmware_list
                keyboard_data["status"] = "ok"
            else:
                keyboard_data["firmwares"] = []
                keyboard_data["status"] = "ok"

        except Exception as e:
            keyboard_data["status"] = "error"
            keyboard_data["error"] = str(e)
            keyboard_data["firmwares"] = []

        keyboards_info.append(keyboard_data)

    # Environment information
    environment = {
        "platform": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
        "working_directory": str(Path.cwd()),
    }

    return {
        "version": version,
        "dependencies": dependencies_info,
        "keyboards": keyboards_info,
        "environment": environment,
    }


def _format_status_json(data: dict[str, Any]) -> None:
    """Format status data as JSON."""
    print(json.dumps(data, indent=2))


def _format_status_markdown(data: dict[str, Any]) -> None:
    """Format status data as Markdown."""
    print(f"# Glovebox Status v{data['version']}")
    print()

    # Dependencies section
    print("## 🔗 System Dependencies")
    print()
    print("| Tool | Status | Version |")
    print("|------|--------|---------|")

    for name, info in data["dependencies"].items():
        status_icon = "✅ Available" if info["status"] == "available" else "❌ Missing"
        print(f"| {name} | {status_icon} | {info['version']} |")

    print()

    # Keyboards section
    print(f"## ⌨️ Available Keyboards ({len(data['keyboards'])})")
    print()

    if data["keyboards"]:
        for kb in data["keyboards"]:
            print(f"### {kb['name']}")

            if kb["status"] == "error":
                print(f"❌ **Error**: {kb['error']}")
            elif kb["firmwares"]:
                print(f"**Firmwares**: {len(kb['firmwares'])} available")
                print()
                for fw in kb["firmwares"]:
                    print(f"- **{fw['name']}**: {fw['description']}")
            else:
                print("No firmwares available")

            print()
    else:
        print("No keyboards found")
        print()

    # Environment section
    print("## 🌍 Environment Information")
    print()
    print("| Property | Value |")
    print("|----------|-------|")

    for key, value in data["environment"].items():
        formatted_key = key.replace("_", " ").title()
        print(f"| {formatted_key} | {value} |")


def _format_status_table(data: dict[str, Any]) -> None:
    """Format status data as Rich tables (default format)."""
    console = Console()

    # Header with version
    header = Text(f"Glovebox v{data['version']}", style="bold magenta")
    console.print(Panel(header, title="🔧 Glovebox Status", border_style="blue"))
    console.print()

    # Dependencies table
    deps_table = Table(
        title="🔗 System Dependencies", show_header=True, header_style="bold blue"
    )
    deps_table.add_column("Tool", style="cyan", no_wrap=True)
    deps_table.add_column("Status", style="bold")
    deps_table.add_column("Version", style="dim")

    for name, info in data["dependencies"].items():
        status_display = (
            "✅ Available" if info["status"] == "available" else "❌ Missing"
        )
        deps_table.add_row(name, status_display, info["version"])

    console.print(deps_table)
    console.print()

    # Keyboards table
    if data["keyboards"]:
        keyboards_table = Table(
            title=f"⌨️ Available Keyboards ({len(data['keyboards'])})",
            show_header=True,
            header_style="bold green",
        )
        keyboards_table.add_column("Keyboard", style="cyan", no_wrap=True)
        keyboards_table.add_column("Firmwares", style="yellow")
        keyboards_table.add_column("Description", style="dim")

        for kb in data["keyboards"]:
            if kb["status"] == "error":
                keyboards_table.add_row(kb["name"], "❌ Error", kb["error"])
            elif kb["firmwares"]:
                firmware_list = []
                for fw in kb["firmwares"]:
                    firmware_list.append(f"• {fw['name']}: {fw['description']}")

                keyboards_table.add_row(
                    kb["name"],
                    f"{len(kb['firmwares'])} available",
                    "\n".join(firmware_list),
                )
            else:
                keyboards_table.add_row(kb["name"], "No firmwares", "")

        console.print(keyboards_table)
    else:
        console.print("[yellow]No keyboards found[/yellow]")

    console.print()

    # Environment table
    env_table = Table(
        title="🌍 Environment Information", show_header=True, header_style="bold cyan"
    )
    env_table.add_column("Property", style="cyan", no_wrap=True)
    env_table.add_column("Value", style="white")

    for key, value in data["environment"].items():
        formatted_key = key.replace("_", " ").title()
        env_table.add_row(formatted_key, value)

    console.print(env_table)


@handle_errors
def status_command(
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json, markdown)"
    ),
) -> None:
    """Show system status and diagnostics."""
    # Collect all status data
    data = _collect_status_data()

    # Format and display based on format option
    if format.lower() == "json":
        _format_status_json(data)
    elif format.lower() in ("markdown", "md"):
        _format_status_markdown(data)
    elif format.lower() == "table":
        _format_status_table(data)
    else:
        print(
            f"Error: Unknown format '{format}'. Supported formats: table, json, markdown"
        )
        raise typer.Exit(1)


def register_commands(app: typer.Typer) -> None:
    """Register status command with the main app.

    Args:
        app: The main Typer app
    """
    app.command(name="status")(status_command)
