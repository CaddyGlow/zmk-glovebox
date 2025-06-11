"""Status command for Glovebox CLI."""

import json
import logging
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from glovebox.config.user_config import UserConfig

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from glovebox.cli.app import AppContext
from glovebox.cli.decorators import handle_errors
from glovebox.utils.diagnostics import collect_all_diagnostics


logger = logging.getLogger(__name__)


def _collect_status_data(user_config: "UserConfig | None" = None) -> dict[str, Any]:
    """Collect all status data into a structured format using comprehensive diagnostics."""
    # Use the new comprehensive diagnostics collection
    full_diagnostics = collect_all_diagnostics(user_config)

    return full_diagnostics


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

    docker_info = data.get("docker", {})
    if docker_info.get("availability") == "available":
        version = docker_info.get("version_info", {}).get("client", "Unknown")
        deps_table.add_row("Docker", "✅ Available", version)
    else:
        deps_table.add_row("Docker", "❌ Missing", "Not found")

    console.print(deps_table)
    console.print()

    # Keyboards table
    config_info = data.get("configuration", {})
    keyboard_status = config_info.get("keyboard_discovery", {}).get(
        "keyboard_status", []
    )
    if keyboard_status:
        keyboards_table = Table(
            title=f"⌨️ Available Keyboards ({len(keyboard_status)})",
            show_header=True,
            header_style="bold green",
        )
        keyboards_table.add_column("Keyboard", style="cyan", no_wrap=True)
        keyboards_table.add_column("Status", style="yellow")
        keyboards_table.add_column("Description", style="dim")

        for kb in keyboard_status:
            name = kb.get("name", "Unknown")
            if kb.get("status") == "error":
                keyboards_table.add_row(
                    name, "❌ Error", kb.get("error", "Unknown error")
                )
            else:
                keyboards_table.add_row(name, "✅ Available", "")

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

    env_info = data.get("system", {}).get("environment", {})
    for key, value in env_info.items():
        formatted_key = key.replace("_", " ").title()
        env_table.add_row(formatted_key, str(value))

    console.print(env_table)


def _format_diagnostics_table(data: dict[str, Any]) -> None:
    """Format comprehensive diagnostics data as Rich tables."""
    console = Console()

    # Header with version
    header = Text(f"Glovebox v{data.get('version', 'unknown')}", style="bold magenta")
    console.print(
        Panel(header, title="🔧 Comprehensive Diagnostics", border_style="blue")
    )
    console.print()

    # System Diagnostics
    _print_system_diagnostics_table(console, data.get("system", {}))

    # Docker Diagnostics
    _print_docker_diagnostics_table(console, data.get("docker", {}))

    # USB/Flash Diagnostics
    _print_usb_diagnostics_table(console, data.get("usb_flash", {}))

    # Configuration Diagnostics
    _print_config_diagnostics_table(console, data.get("configuration", {}))

    # Layout Diagnostics
    _print_layout_diagnostics_table(console, data.get("layout", {}))


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

    # Detailed USB devices table if devices are found
    if detected_devices:
        devices_table = Table(
            title=f"🔌 Detected USB Devices ({len(detected_devices)})",
            show_header=True,
            header_style="bold yellow",
        )
        devices_table.add_column("Device", style="cyan", no_wrap=True)
        devices_table.add_column("Vendor", style="green")
        devices_table.add_column("Model", style="blue")
        devices_table.add_column("PIDs", style="magenta")
        devices_table.add_column("Size", style="dim")
        devices_table.add_column("Type", style="yellow")

        for device in detected_devices:
            # Format size nicely
            size = device.get("size", 0)
            if size > 0:
                if size >= 1024**3:  # GB
                    size_str = f"{size / (1024**3):.1f} GB"
                elif size >= 1024**2:  # MB
                    size_str = f"{size / (1024**2):.1f} MB"
                else:
                    size_str = f"{size} bytes"
            else:
                size_str = "Unknown"

            # Format PIDs
            vendor_id = device.get("vendor_id", "")
            product_id = device.get("product_id", "")
            if vendor_id and product_id:
                pids_str = f"{vendor_id}:{product_id}"
            elif vendor_id:
                pids_str = f"{vendor_id}:----"
            elif product_id:
                pids_str = f"----:{product_id}"
            else:
                pids_str = "Unknown"

            devices_table.add_row(
                device.get("name", "Unknown"),
                device.get("vendor", "Unknown"),
                device.get("model", "Unknown"),
                pids_str,
                size_str,
                device.get("type", "Unknown"),
            )

        console.print(devices_table)
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
    ctx: typer.Context,
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
    # Get app context with user config
    app_ctx: AppContext = ctx.obj

    # Collect all status data
    data = _collect_status_data(app_ctx.user_config)

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
