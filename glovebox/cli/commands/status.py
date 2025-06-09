"""Status command for Glovebox CLI."""

import json
import logging
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from glovebox.cli.decorators import handle_errors
from glovebox.utils.diagnostics import collect_all_diagnostics


logger = logging.getLogger(__name__)


def _collect_status_data() -> dict[str, Any]:
    """Collect all status data into a structured format using comprehensive diagnostics."""
    # Use the new comprehensive diagnostics collection
    full_diagnostics = collect_all_diagnostics()

    # Transform the comprehensive diagnostics into the legacy format for compatibility
    # with existing formatting functions
    legacy_format = {
        "version": full_diagnostics["version"],
        "dependencies": _transform_docker_to_legacy(full_diagnostics.get("docker", {})),
        "keyboards": _transform_keyboards_to_legacy(
            full_diagnostics.get("configuration", {})
        ),
        "environment": _transform_environment_to_legacy(
            full_diagnostics.get("system", {})
        ),
        # Include the full diagnostics for new enhanced output formats
        "full_diagnostics": full_diagnostics,
    }

    return legacy_format


def _transform_docker_to_legacy(docker_diagnostics: dict[str, Any]) -> dict[str, Any]:
    """Transform Docker diagnostics to legacy dependencies format."""
    dependencies = {}

    if docker_diagnostics.get("availability") == "available":
        dependencies["Docker"] = {
            "status": "available",
            "version": docker_diagnostics.get("version_info", {}).get(
                "client", "Unknown"
            ),
        }
    else:
        dependencies["Docker"] = {
            "status": "missing",
            "version": "Not found",
        }

    return dependencies


def _transform_keyboards_to_legacy(
    config_diagnostics: dict[str, Any],
) -> list[dict[str, Any]]:
    """Transform configuration diagnostics to legacy keyboards format."""
    keyboards_info = []

    keyboard_discovery = config_diagnostics.get("keyboard_discovery", {})
    keyboard_status = keyboard_discovery.get("keyboard_status", [])

    for kb_info in keyboard_status:
        keyboard_data = {
            "name": kb_info.get("name", "unknown"),
            "status": kb_info.get("status", "unknown"),
        }

        if kb_info.get("status") == "error":
            keyboard_data["error"] = kb_info.get("error", "Unknown error")
            keyboard_data["firmwares"] = []
        else:
            # For now, we'll keep the simplified format
            # The full diagnostic data is available in full_diagnostics
            keyboard_data["firmwares"] = []
            if kb_info.get("has_firmwares"):
                keyboard_data["firmwares"] = [
                    {"note": "Firmwares available (see full diagnostics)"}
                ]

        keyboards_info.append(keyboard_data)

    return keyboards_info


def _transform_environment_to_legacy(
    system_diagnostics: dict[str, Any],
) -> dict[str, Any]:
    """Transform system diagnostics to legacy environment format."""
    environment_info = system_diagnostics.get("environment", {})

    return {
        "platform": environment_info.get("platform", "Unknown"),
        "python": environment_info.get("python_version", "Unknown"),
        "working_directory": environment_info.get("working_directory", "Unknown"),
    }


def _format_status_json(data: dict[str, Any]) -> None:
    """Format status data as JSON."""
    print(json.dumps(data, indent=2))


def _format_diagnostics_json(data: dict[str, Any]) -> None:
    """Format full diagnostics data as JSON."""
    full_diagnostics = data.get("full_diagnostics", {})
    print(json.dumps(full_diagnostics, indent=2))


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


def _format_diagnostics_table(data: dict[str, Any]) -> None:
    """Format comprehensive diagnostics data as Rich tables."""
    console = Console()
    full_diagnostics = data.get("full_diagnostics", {})

    # Header with version
    header = Text(
        f"Glovebox v{full_diagnostics.get('version', 'unknown')}", style="bold magenta"
    )
    console.print(
        Panel(header, title="🔧 Comprehensive Diagnostics", border_style="blue")
    )
    console.print()

    # System Diagnostics
    _print_system_diagnostics_table(console, full_diagnostics.get("system", {}))

    # Docker Diagnostics
    _print_docker_diagnostics_table(console, full_diagnostics.get("docker", {}))

    # USB/Flash Diagnostics
    _print_usb_diagnostics_table(console, full_diagnostics.get("usb_flash", {}))

    # Configuration Diagnostics
    _print_config_diagnostics_table(console, full_diagnostics.get("configuration", {}))

    # Layout Diagnostics
    _print_layout_diagnostics_table(console, full_diagnostics.get("layout", {}))


def _print_system_diagnostics_table(
    console: Console, system_data: dict[str, Any]
) -> None:
    """Print system diagnostics table."""
    system_table = Table(
        title="🖥️ System Environment", show_header=True, header_style="bold cyan"
    )
    system_table.add_column("Component", style="cyan", no_wrap=True)
    system_table.add_column("Status", style="bold")
    system_table.add_column("Details", style="dim")

    environment = system_data.get("environment", {})
    file_system = system_data.get("file_system", {})
    disk_space = system_data.get("disk_space", {})

    # Environment info
    system_table.add_row(
        "Platform", "✅ Available", environment.get("platform", "Unknown")
    )
    system_table.add_row(
        "Python", "✅ Available", f"v{environment.get('python_version', 'Unknown')}"
    )

    # File system checks
    for key in ["temp_directory", "config_directory", "working_directory"]:
        writable_key = f"{key}_writable"
        exists_key = f"{key}_exists"
        path_key = f"{key}_path"

        if writable_key in file_system:
            status = "✅ Writable" if file_system[writable_key] else "⚠️ Read-only"
            details = file_system.get(path_key, "Unknown path")
            system_table.add_row(key.replace("_", " ").title(), status, details)

    # Disk space
    if "available_gb" in disk_space:
        status = "✅ Available" if disk_space["available_gb"] > 1.0 else "⚠️ Low space"
        details = f"{disk_space['available_gb']} GB available"
        system_table.add_row("Disk Space", status, details)

    console.print(system_table)
    console.print()


def _print_docker_diagnostics_table(
    console: Console, docker_data: dict[str, Any]
) -> None:
    """Print Docker diagnostics table."""
    docker_table = Table(
        title="🐳 Docker Environment", show_header=True, header_style="bold blue"
    )
    docker_table.add_column("Component", style="cyan", no_wrap=True)
    docker_table.add_column("Status", style="bold")
    docker_table.add_column("Details", style="dim")

    # Docker availability
    availability = docker_data.get("availability", "unknown")
    if availability == "available":
        status = "✅ Available"
        version = docker_data.get("version_info", {}).get("client", "Unknown version")
    else:
        status = "❌ Unavailable"
        version = "Not installed or not accessible"

    docker_table.add_row("Docker Client", status, version)

    # Docker daemon
    daemon_status = docker_data.get("daemon_status", "unknown")
    if daemon_status == "running":
        daemon_display = "✅ Running"
        server_version = docker_data.get("version_info", {}).get("server", "Unknown")
    elif daemon_status == "stopped":
        daemon_display = "❌ Stopped"
        server_version = "Daemon not running"
    else:
        daemon_display = "⚠️ Unknown"
        server_version = "Status unclear"

    docker_table.add_row("Docker Daemon", daemon_display, server_version)

    # Docker images
    images = docker_data.get("images", {})
    for image_name, image_status in images.items():
        if image_status == "available":
            status_display = "✅ Available"
        elif image_status == "missing":
            status_display = "❌ Missing"
        else:
            status_display = "⚠️ Error"

        docker_table.add_row(f"Image: {image_name}", status_display, "")

    # Docker capabilities
    capabilities = docker_data.get("capabilities", {})
    for cap_name, cap_status in capabilities.items():
        if cap_status == "available":
            cap_display = "✅ Working"
        elif cap_status == "limited":
            cap_display = "⚠️ Limited"
        else:
            cap_display = "❌ Unavailable"

        docker_table.add_row(
            f"Capability: {cap_name.replace('_', ' ').title()}", cap_display, ""
        )

    console.print(docker_table)
    console.print()


def _print_usb_diagnostics_table(console: Console, usb_data: dict[str, Any]) -> None:
    """Print USB/Flash diagnostics table."""
    usb_table = Table(
        title="🔌 USB/Flash Capabilities", show_header=True, header_style="bold yellow"
    )
    usb_table.add_column("Component", style="cyan", no_wrap=True)
    usb_table.add_column("Status", style="bold")
    usb_table.add_column("Details", style="dim")

    # USB detection
    usb_detection = usb_data.get("usb_detection", {})
    detection_status = usb_detection.get("status", "unknown")

    if detection_status == "available":
        status_display = "✅ Working"
        platform_adapter = usb_detection.get("platform_adapter", "Unknown")
    elif detection_status == "unsupported_platform":
        status_display = "⚠️ Unsupported"
        platform_adapter = "Platform not supported"
    else:
        status_display = "❌ Error"
        platform_adapter = usb_detection.get("error", "Unknown error")

    usb_table.add_row("USB Detection", status_display, platform_adapter)

    # Detected devices
    detected_devices = usb_data.get("detected_devices", [])
    device_count = len(detected_devices)
    usb_table.add_row(
        "USB Devices", f"✅ {device_count} found", "Currently connected devices"
    )

    # OS capabilities
    os_capabilities = usb_data.get("os_capabilities", {})
    mount_tool = os_capabilities.get("mount_tool", "unknown")

    if mount_tool in ["udisksctl", "diskutil"]:
        status_display = "✅ Available"
        details = f"Using {mount_tool}"
    else:
        status_display = "❌ Unavailable"
        details = "No mount tool found"

    usb_table.add_row("Mount Tool", status_display, details)

    console.print(usb_table)
    console.print()


def _print_config_diagnostics_table(
    console: Console, config_data: dict[str, Any]
) -> None:
    """Print configuration diagnostics table."""
    config_table = Table(
        title="⚙️ Configuration", show_header=True, header_style="bold green"
    )
    config_table.add_column("Component", style="cyan", no_wrap=True)
    config_table.add_column("Status", style="bold")
    config_table.add_column("Details", style="dim")

    # User config
    user_config = config_data.get("user_config", {})
    validation_status = user_config.get("validation_status", "unknown")

    if validation_status == "valid":
        status_display = "✅ Valid"
        details = user_config.get("found_config", "Configuration loaded")
    elif validation_status == "error":
        status_display = "❌ Error"
        errors = user_config.get("validation_errors", ["Unknown error"])
        details = "; ".join(errors)
    else:
        status_display = "⚠️ Unknown"
        details = "Status unclear"

    config_table.add_row("User Config", status_display, details)

    # Environment variables
    env_vars = user_config.get("environment_vars", {})
    env_count = len(env_vars)
    config_table.add_row(
        "Environment Variables",
        f"ℹ️ {env_count} found",
        ", ".join(env_vars.keys()) if env_vars else "None",
    )

    # Keyboard discovery
    keyboard_discovery = config_data.get("keyboard_discovery", {})
    found_keyboards = keyboard_discovery.get("found_keyboards", 0)
    config_table.add_row(
        "Available Keyboards",
        f"✅ {found_keyboards} found",
        "Keyboard configurations loaded",
    )

    console.print(config_table)
    console.print()


def _print_layout_diagnostics_table(
    console: Console, layout_data: dict[str, Any]
) -> None:
    """Print layout processing diagnostics table."""
    layout_table = Table(
        title="📐 Layout Processing", show_header=True, header_style="bold magenta"
    )
    layout_table.add_column("Component", style="cyan", no_wrap=True)
    layout_table.add_column("Status", style="bold")
    layout_table.add_column("Details", style="dim")

    processing = layout_data.get("processing", {})
    zmk_generation = layout_data.get("zmk_generation", {})

    # Processing capabilities
    for component, status in processing.items():
        if component.endswith("_error"):
            continue

        if status == "available":
            status_display = "✅ Available"
            details = "Working correctly"
        elif status == "error":
            status_display = "❌ Error"
            error_key = f"{component}_error"
            details = layout_data.get(error_key, "Unknown error")
        else:
            status_display = "⚠️ Unknown"
            details = "Status unclear"

        layout_table.add_row(
            component.replace("_", " ").title(), status_display, details
        )

    # ZMK generation capabilities
    for component, status in zmk_generation.items():
        if status == "available":
            status_display = "✅ Available"
            details = "Ready for generation"
        elif status == "error":
            status_display = "❌ Error"
            details = "Generation not available"
        else:
            status_display = "⚠️ Unknown"
            details = "Status unclear"

        layout_table.add_row(
            f"ZMK {component.replace('_', ' ').title()}", status_display, details
        )

    console.print(layout_table)
    console.print()


@handle_errors
def status_command(
    format: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format (table, json, markdown, diagnostics, diag-json)",
    ),
) -> None:
    """Show system status and diagnostics.

    Formats:
    - table: Basic status table (default)
    - json: Basic status as JSON
    - markdown: Basic status as Markdown
    - diagnostics: Comprehensive diagnostics table
    - diag-json: Full diagnostics as JSON
    """
    # Collect all status data
    data = _collect_status_data()

    # Format and display based on format option
    if format.lower() == "json":
        _format_status_json(data)
    elif format.lower() in ("markdown", "md"):
        _format_status_markdown(data)
    elif format.lower() == "table":
        _format_status_table(data)
    elif format.lower() in ("diagnostics", "diag"):
        _format_diagnostics_table(data)
    elif format.lower() in ("diag-json", "diagnostics-json"):
        _format_diagnostics_json(data)
    else:
        print(
            f"Error: Unknown format '{format}'. Supported formats: table, json, markdown, diagnostics, diag-json"
        )
        raise typer.Exit(1)


def register_commands(app: typer.Typer) -> None:
    """Register status command with the main app.

    Args:
        app: The main Typer app
    """
    app.command(name="status")(status_command)
