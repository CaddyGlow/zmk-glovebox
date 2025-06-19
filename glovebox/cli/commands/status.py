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


def _format_status_markdown(data: dict[str, Any], use_emoji: bool = True) -> None:
    """Format status data as Markdown."""
    from glovebox.cli.helpers.theme import Icons

    print(f"# Glovebox Status v{data['version']}")
    print()

    # Dependencies section
    link_icon = Icons.get_icon("ARROW", use_emoji)
    print(f"## {link_icon} System Dependencies")
    print()
    print("| Tool | Status | Version |")
    print("|------|--------|---------|")

    for name, info in data["dependencies"].items():
        success_icon = Icons.get_icon("SUCCESS", use_emoji)
        error_icon = Icons.get_icon("ERROR", use_emoji)
        status_icon = (
            f"{success_icon} Available"
            if info["status"] == "available"
            else f"{error_icon} Missing"
        )
        print(f"| {name} | {status_icon} | {info['version']} |")

    print()

    # Keyboards section
    keyboard_icon = Icons.get_icon("KEYBOARD", use_emoji)
    print(f"## {keyboard_icon} Available Keyboards ({len(data['keyboards'])})")
    print()

    if data["keyboards"]:
        for kb in data["keyboards"]:
            print(f"### {kb['name']}")

            if kb["status"] == "error":
                error_icon = Icons.get_icon("ERROR", use_emoji)
                print(f"{error_icon} **Error**: {kb['error']}")
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
    system_icon = Icons.get_icon("SYSTEM", use_emoji)
    print(f"## {system_icon} Environment Information")
    print()
    print("| Property | Value |")
    print("|----------|-------|")

    for key, value in data["environment"].items():
        formatted_key = key.replace("_", " ").title()
        print(f"| {formatted_key} | {value} |")


def _format_status_table(data: dict[str, Any], use_emoji: bool = True) -> None:
    """Format status data as Rich tables (default format)."""
    from glovebox.cli.helpers.theme import Icons

    console = Console()

    # Header with version
    header = Text(f"Glovebox v{data['version']}", style="bold magenta")
    firmware_icon = Icons.get_icon("FIRMWARE", use_emoji)
    console.print(
        Panel(header, title=f"{firmware_icon} Glovebox Status", border_style="blue")
    )
    console.print()

    # Dependencies table
    link_icon = Icons.get_icon("ARROW", use_emoji)
    deps_table = Table(
        title=f"{link_icon} System Dependencies",
        show_header=True,
        header_style="bold blue",
    )
    deps_table.add_column("Tool", style="cyan", no_wrap=True)
    deps_table.add_column("Status", style="bold")
    deps_table.add_column("Version", style="dim")

    docker_info = data.get("docker", {})
    if docker_info.get("availability") == "available":
        version = docker_info.get("version_info", {}).get("client", "Unknown")
        status_text = Icons.format_with_icon("SUCCESS", "Available", use_emoji)
        deps_table.add_row("Docker", status_text, version)
    else:
        status_text = Icons.format_with_icon("ERROR", "Missing", use_emoji)
        deps_table.add_row("Docker", status_text, "Not found")

    console.print(deps_table)
    console.print()

    # Keyboards table
    config_info = data.get("configuration", {})
    keyboard_status = config_info.get("keyboard_discovery", {}).get(
        "keyboard_status", []
    )
    if keyboard_status:
        keyboard_icon = Icons.get_icon("KEYBOARD", use_emoji)
        keyboards_table = Table(
            title=f"{keyboard_icon} Available Keyboards ({len(keyboard_status)})",
            show_header=True,
            header_style="bold green",
        )
        keyboards_table.add_column("Keyboard", style="cyan", no_wrap=True)
        keyboards_table.add_column("Status", style="yellow")
        keyboards_table.add_column("Description", style="dim")

        for kb in keyboard_status:
            name = kb.get("name", "Unknown")
            if kb.get("status") == "error":
                status_text = Icons.format_with_icon("ERROR", "Error", use_emoji)
                keyboards_table.add_row(
                    name, status_text, kb.get("error", "Unknown error")
                )
            else:
                status_text = Icons.format_with_icon("SUCCESS", "Available", use_emoji)
                keyboards_table.add_row(name, status_text, "")

        console.print(keyboards_table)
    else:
        console.print("[yellow]No keyboards found[/yellow]")

    console.print()

    # Environment table
    system_icon = Icons.get_icon("SYSTEM", use_emoji)
    env_table = Table(
        title=f"{system_icon} Environment Information",
        show_header=True,
        header_style="bold cyan",
    )
    env_table.add_column("Property", style="cyan", no_wrap=True)
    env_table.add_column("Value", style="white")

    env_info = data.get("system", {}).get("environment", {})
    for key, value in env_info.items():
        formatted_key = key.replace("_", " ").title()
        env_table.add_row(formatted_key, str(value))

    console.print(env_table)


def _format_diagnostics_table(data: dict[str, Any], use_emoji: bool = True) -> None:
    """Format comprehensive diagnostics data as Rich tables."""
    from glovebox.cli.helpers.theme import Icons

    console = Console()

    # Header with version
    header = Text(f"Glovebox v{data.get('version', 'unknown')}", style="bold magenta")
    firmware_icon = Icons.get_icon("FIRMWARE", use_emoji)
    console.print(
        Panel(
            header,
            title=f"{firmware_icon} Comprehensive Diagnostics",
            border_style="blue",
        )
    )
    console.print()

    # System Diagnostics
    _print_system_diagnostics_table(console, data.get("system", {}), use_emoji)

    # Docker Diagnostics
    _print_docker_diagnostics_table(console, data.get("docker", {}), use_emoji)

    # USB/Flash Diagnostics
    _print_usb_diagnostics_table(console, data.get("usb_flash", {}), use_emoji)

    # Configuration Diagnostics
    _print_config_diagnostics_table(console, data.get("configuration", {}), use_emoji)

    # Layout Diagnostics
    _print_layout_diagnostics_table(console, data.get("layout", {}), use_emoji)


def _print_system_diagnostics_table(
    console: Console, system_data: dict[str, Any], use_emoji: bool = True
) -> None:
    """Print system diagnostics table."""
    from glovebox.cli.helpers.theme import Icons

    system_icon = Icons.get_icon("SYSTEM", use_emoji)
    system_table = Table(
        title=f"{system_icon} System Environment",
        show_header=True,
        header_style="bold cyan",
    )
    system_table.add_column("Component", style="cyan", no_wrap=True)
    system_table.add_column("Status", style="bold")
    system_table.add_column("Details", style="dim")

    environment = system_data.get("environment", {})
    file_system = system_data.get("file_system", {})
    disk_space = system_data.get("disk_space", {})

    # Environment info
    success_icon = Icons.get_icon("SUCCESS", use_emoji)
    system_table.add_row(
        "Platform", f"{success_icon} Available", environment.get("platform", "Unknown")
    )
    system_table.add_row(
        "Python",
        f"{success_icon} Available",
        f"v{environment.get('python_version', 'Unknown')}",
    )

    # File system checks
    for key in ["temp_directory", "config_directory", "working_directory"]:
        writable_key = f"{key}_writable"
        exists_key = f"{key}_exists"
        path_key = f"{key}_path"

        if writable_key in file_system:
            if file_system[writable_key]:
                status_icon = Icons.get_icon("SUCCESS", use_emoji)
                status = f"{status_icon} Writable"
            else:
                status_icon = Icons.get_icon("WARNING", use_emoji)
                status = f"{status_icon} Read-only"
            details = file_system.get(path_key, "Unknown path")
            system_table.add_row(key.replace("_", " ").title(), status, details)

    # Disk space
    if "available_gb" in disk_space:
        if disk_space["available_gb"] > 1.0:
            status_icon = Icons.get_icon("SUCCESS", use_emoji)
            status = f"{status_icon} Available"
        else:
            status_icon = Icons.get_icon("WARNING", use_emoji)
            status = f"{status_icon} Low space"
        details = f"{disk_space['available_gb']} GB available"
        system_table.add_row("Disk Space", status, details)

    console.print(system_table)
    console.print()


def _print_docker_diagnostics_table(
    console: Console, docker_data: dict[str, Any], use_emoji: bool = True
) -> None:
    """Print Docker diagnostics table."""
    from glovebox.cli.helpers.theme import Icons

    docker_icon = Icons.get_icon("DOCKER", use_emoji)
    docker_table = Table(
        title=f"{docker_icon} Docker Environment",
        show_header=True,
        header_style="bold blue",
    )
    docker_table.add_column("Component", style="cyan", no_wrap=True)
    docker_table.add_column("Status", style="bold")
    docker_table.add_column("Details", style="dim")

    # Docker availability
    availability = docker_data.get("availability", "unknown")
    if availability == "available":
        status = Icons.format_with_icon("SUCCESS", "Available", use_emoji)
        version = docker_data.get("version_info", {}).get("client", "Unknown version")
    else:
        status = Icons.format_with_icon("ERROR", "Unavailable", use_emoji)
        version = "Not installed or not accessible"

    docker_table.add_row("Docker Client", status, version)

    # Docker daemon
    daemon_status = docker_data.get("daemon_status", "unknown")
    if daemon_status == "running":
        daemon_display = Icons.format_with_icon("SUCCESS", "Running", use_emoji)
        server_version = docker_data.get("version_info", {}).get("server", "Unknown")
    elif daemon_status == "stopped":
        daemon_display = Icons.format_with_icon("ERROR", "Stopped", use_emoji)
        server_version = "Daemon not running"
    else:
        daemon_display = Icons.format_with_icon("WARNING", "Unknown", use_emoji)
        server_version = "Status unclear"

    docker_table.add_row("Docker Daemon", daemon_display, server_version)

    # Docker images
    images = docker_data.get("images", {})
    for image_name, image_status in images.items():
        if image_status == "available":
            status_display = Icons.format_with_icon("SUCCESS", "Available", use_emoji)
        elif image_status == "missing":
            status_display = Icons.format_with_icon("ERROR", "Missing", use_emoji)
        else:
            status_display = Icons.format_with_icon("WARNING", "Error", use_emoji)

        docker_table.add_row(f"Image: {image_name}", status_display, "")

    # Docker capabilities
    capabilities = docker_data.get("capabilities", {})
    for cap_name, cap_status in capabilities.items():
        if cap_status == "available":
            cap_display = Icons.format_with_icon("SUCCESS", "Working", use_emoji)
        elif cap_status == "limited":
            cap_display = Icons.format_with_icon("WARNING", "Limited", use_emoji)
        else:
            cap_display = Icons.format_with_icon("ERROR", "Unavailable", use_emoji)

        docker_table.add_row(
            f"Capability: {cap_name.replace('_', ' ').title()}", cap_display, ""
        )

    console.print(docker_table)
    console.print()


def _print_usb_diagnostics_table(
    console: Console, usb_data: dict[str, Any], use_emoji: bool = True
) -> None:
    """Print USB/Flash diagnostics table."""
    from glovebox.cli.helpers.theme import Icons

    usb_icon = Icons.get_icon("USB", use_emoji)
    usb_table = Table(
        title=f"{usb_icon} USB/Flash Capabilities",
        show_header=True,
        header_style="bold yellow",
    )
    usb_table.add_column("Component", style="cyan", no_wrap=True)
    usb_table.add_column("Status", style="bold")
    usb_table.add_column("Details", style="dim")

    # USB detection
    usb_detection = usb_data.get("usb_detection", {})
    detection_status = usb_detection.get("status", "unknown")

    if detection_status == "available":
        status_display = Icons.format_with_icon("SUCCESS", "Working", use_emoji)
        platform_adapter = usb_detection.get("platform_adapter", "Unknown")
    elif detection_status == "unsupported_platform":
        status_display = Icons.format_with_icon("WARNING", "Unsupported", use_emoji)
        platform_adapter = "Platform not supported"
    else:
        status_display = Icons.format_with_icon("ERROR", "Error", use_emoji)
        platform_adapter = usb_detection.get("error", "Unknown error")

    usb_table.add_row("USB Detection", status_display, platform_adapter)

    # Detected devices
    detected_devices = usb_data.get("detected_devices", [])
    device_count = len(detected_devices)
    usb_table.add_row(
        "USB Devices",
        Icons.format_with_icon("SUCCESS", f"{device_count} found", use_emoji),
        "Currently connected devices",
    )

    # OS capabilities
    os_capabilities = usb_data.get("os_capabilities", {})
    mount_tool = os_capabilities.get("mount_tool", "unknown")

    if mount_tool in ["udisksctl", "diskutil"]:
        status_display = Icons.format_with_icon("SUCCESS", "Available", use_emoji)
        details = f"Using {mount_tool}"
    else:
        status_display = Icons.format_with_icon("ERROR", "Unavailable", use_emoji)
        details = "No mount tool found"

    usb_table.add_row("Mount Tool", status_display, details)

    console.print(usb_table)
    console.print()

    # Detailed USB devices table if devices are found
    if detected_devices:
        devices_table = Table(
            title=f"{Icons.get_icon('DEVICE', use_emoji)} Detected USB Devices ({len(detected_devices)})",
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
    console: Console, config_data: dict[str, Any], use_emoji: bool = True
) -> None:
    """Print configuration diagnostics table."""
    from glovebox.cli.helpers.theme import Icons

    config_icon = Icons.get_icon("CONFIG", use_emoji)
    config_table = Table(
        title=f"{config_icon} Configuration",
        show_header=True,
        header_style="bold green",
    )
    config_table.add_column("Component", style="cyan", no_wrap=True)
    config_table.add_column("Status", style="bold")
    config_table.add_column("Details", style="dim")

    # User config
    user_config = config_data.get("user_config", {})
    validation_status = user_config.get("validation_status", "unknown")

    if validation_status == "valid":
        status_display = Icons.format_with_icon("SUCCESS", "Valid", use_emoji)
        details = user_config.get("found_config", "Configuration loaded")
    elif validation_status == "error":
        status_display = Icons.format_with_icon("ERROR", "Error", use_emoji)
        errors = user_config.get("validation_errors", ["Unknown error"])
        details = "; ".join(errors)
    else:
        status_display = Icons.format_with_icon("WARNING", "Unknown", use_emoji)
        details = "Status unclear"

    config_table.add_row("User Config", status_display, details)

    # Environment variables
    env_vars = user_config.get("environment_vars", {})
    env_count = len(env_vars)
    config_table.add_row(
        "Environment Variables",
        Icons.format_with_icon("INFO", f"{env_count} found", use_emoji),
        ", ".join(env_vars.keys()) if env_vars else "None",
    )

    # Keyboard discovery
    keyboard_discovery = config_data.get("keyboard_discovery", {})
    found_keyboards = keyboard_discovery.get("found_keyboards", 0)
    config_table.add_row(
        "Available Keyboards",
        Icons.format_with_icon("SUCCESS", f"{found_keyboards} found", use_emoji),
        "Keyboard configurations loaded",
    )

    console.print(config_table)
    console.print()


def _print_layout_diagnostics_table(
    console: Console, layout_data: dict[str, Any], use_emoji: bool = True
) -> None:
    """Print layout processing diagnostics table."""
    from glovebox.cli.helpers.theme import Icons

    layout_icon = Icons.get_icon("LAYOUT", use_emoji)
    layout_table = Table(
        title=f"{layout_icon} Layout Processing",
        show_header=True,
        header_style="bold magenta",
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
            status_display = Icons.format_with_icon("SUCCESS", "Available", use_emoji)
            details = "Working correctly"
        elif status == "error":
            status_display = Icons.format_with_icon("ERROR", "Error", use_emoji)
            error_key = f"{component}_error"
            details = layout_data.get(error_key, "Unknown error")
        else:
            status_display = Icons.format_with_icon("WARNING", "Unknown", use_emoji)
            details = "Status unclear"

        layout_table.add_row(
            component.replace("_", " ").title(), status_display, details
        )

    # ZMK generation capabilities
    for component, status in zmk_generation.items():
        if status == "available":
            status_display = Icons.format_with_icon("SUCCESS", "Available", use_emoji)
            details = "Ready for generation"
        elif status == "error":
            status_display = Icons.format_with_icon("ERROR", "Error", use_emoji)
            details = "Generation not available"
        else:
            status_display = Icons.format_with_icon("WARNING", "Unknown", use_emoji)
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

    # Get emoji mode setting from app context
    use_emoji = app_ctx.use_emoji

    # Format and display based on format option
    if format.lower() == "json":
        _format_status_json(data)
    elif format.lower() in ("markdown", "md"):
        _format_status_markdown(data, use_emoji)
    elif format.lower() == "table":
        _format_status_table(data, use_emoji)
    elif format.lower() in ("diagnostics", "diag"):
        _format_diagnostics_table(data, use_emoji)
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
