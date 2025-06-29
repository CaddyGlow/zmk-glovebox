"""Status command for Glovebox CLI."""

import logging
from typing import TYPE_CHECKING, Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from glovebox.cli.app import AppContext
from glovebox.cli.decorators import handle_errors
from glovebox.cli.helpers.output_formatter import OutputFormatter
from glovebox.cli.helpers.parameters import OutputFormatOption
from glovebox.config.user_config import UserConfig
from glovebox.utils.diagnostics import collect_all_diagnostics


logger = logging.getLogger(__name__)


def _collect_status_data(user_config: "UserConfig | None" = None) -> dict[str, Any]:
    """Collect all status data into a structured format using comprehensive diagnostics."""
    # Use the new comprehensive diagnostics collection
    full_diagnostics = collect_all_diagnostics(user_config)

    return full_diagnostics


def _format_diagnostics_table(data: dict[str, Any], icon_mode: str = "emoji") -> None:
    """Format comprehensive diagnostics data as Rich tables."""
    from glovebox.cli.helpers.theme import Icons

    console = Console()

    # Header with version
    header = Text(f"Glovebox v{data.get('version', 'unknown')}", style="bold magenta")
    firmware_icon = Icons.get_icon("FIRMWARE", icon_mode)
    console.print(
        Panel(
            header,
            title=f"{firmware_icon} Comprehensive Diagnostics",
            border_style="blue",
        )
    )
    console.print()

    # System Diagnostics
    _print_system_diagnostics_table(console, data.get("system", {}), icon_mode)

    # Docker Diagnostics
    _print_docker_diagnostics_table(console, data.get("docker", {}), icon_mode)

    # USB/Flash Diagnostics
    _print_usb_diagnostics_table(console, data.get("usb_flash", {}), icon_mode)

    # Configuration Diagnostics
    _print_config_diagnostics_table(console, data.get("configuration", {}), icon_mode)


def _print_system_diagnostics_table(
    console: Console, system_data: dict[str, Any], icon_mode: str = "emoji"
) -> None:
    """Print system diagnostics table."""
    from glovebox.cli.helpers.theme import Icons

    system_icon = Icons.get_icon("SYSTEM", icon_mode)
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
    success_icon = Icons.get_icon("SUCCESS", icon_mode)
    system_table.add_row(
        "Platform", f"{success_icon} Available", environment.get("platform", "Unknown")
    )
    system_table.add_row(
        "Python",
        f"{success_icon} Available",
        f"v{environment.get('python_version', 'Unknown')}",
    )
    system_table.add_row(
        "Package Install Path",
        f"{success_icon} Available",
        environment.get("package_install_path", "Unknown"),
    )

    # File system checks
    for key in ["temp_directory", "config_directory", "working_directory"]:
        writable_key = f"{key}_writable"
        exists_key = f"{key}_exists"
        path_key = f"{key}_path"

        if writable_key in file_system:
            if file_system[writable_key]:
                status_icon = Icons.get_icon("SUCCESS", icon_mode)
                status = f"{status_icon} Writable"
            else:
                status_icon = Icons.get_icon("WARNING", icon_mode)
                status = f"{status_icon} Read-only"
            details = file_system.get(path_key, "Unknown path")
            system_table.add_row(key.replace("_", " ").title(), status, details)

    # Disk space
    if "available_gb" in disk_space:
        if disk_space["available_gb"] > 1.0:
            status_icon = Icons.get_icon("SUCCESS", icon_mode)
            status = f"{status_icon} Available"
        else:
            status_icon = Icons.get_icon("WARNING", icon_mode)
            status = f"{status_icon} Low space"
        details = f"{disk_space['available_gb']} GB available"
        system_table.add_row("Disk Space", status, details)

    # Memory information
    memory_info = system_data.get("memory", {})
    if "total_gb" in memory_info and "error" not in memory_info:
        usage_percent = memory_info.get("usage_percent", 0)
        if usage_percent < 80:
            status_icon = Icons.get_icon("SUCCESS", icon_mode)
            status = f"{status_icon} Available"
        elif usage_percent < 90:
            status_icon = Icons.get_icon("WARNING", icon_mode)
            status = f"{status_icon} High usage"
        else:
            status_icon = Icons.get_icon("ERROR", icon_mode)
            status = f"{status_icon} Critical"

        details = f"{memory_info['used_gb']} GB used / {memory_info['total_gb']} GB total ({usage_percent}%)"
        system_table.add_row("Memory", status, details)

        # Swap information (if swap is configured)
        swap_total = memory_info.get("swap_total_gb", 0)
        if swap_total > 0:
            swap_usage_percent = memory_info.get("swap_usage_percent", 0)
            if swap_usage_percent < 50:
                swap_status_icon = Icons.get_icon("SUCCESS", icon_mode)
                swap_status = f"{swap_status_icon} Available"
            elif swap_usage_percent < 80:
                swap_status_icon = Icons.get_icon("WARNING", icon_mode)
                swap_status = f"{swap_status_icon} High usage"
            else:
                swap_status_icon = Icons.get_icon("ERROR", icon_mode)
                swap_status = f"{swap_status_icon} Critical"

            swap_details = f"{memory_info['swap_used_gb']} GB used / {swap_total} GB total ({swap_usage_percent}%)"
            system_table.add_row("Swap", swap_status, swap_details)
        else:
            system_table.add_row(
                "Swap",
                f"{Icons.get_icon('INFO', icon_mode)} No swap",
                "Swap not configured",
            )
    elif "error" in memory_info:
        error_icon = Icons.get_icon("ERROR", icon_mode)
        system_table.add_row("Memory", f"{error_icon} Error", memory_info["error"])

    console.print(system_table)
    console.print()


def _print_docker_diagnostics_table(
    console: Console, docker_data: dict[str, Any], icon_mode: str = "emoji"
) -> None:
    """Print Docker diagnostics table."""
    from glovebox.cli.helpers.theme import Icons

    docker_icon = Icons.get_icon("DOCKER", icon_mode)
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
        status = Icons.format_with_icon("SUCCESS", "Available", icon_mode)
        version = docker_data.get("version_info", {}).get("client", "Unknown version")
    else:
        status = Icons.format_with_icon("ERROR", "Unavailable", icon_mode)
        version = "Not installed or not accessible"

    docker_table.add_row("Docker Client", status, version)

    # Docker daemon
    daemon_status = docker_data.get("daemon_status", "unknown")
    if daemon_status == "running":
        daemon_display = Icons.format_with_icon("SUCCESS", "Running", icon_mode)
        server_version = docker_data.get("version_info", {}).get("server", "Unknown")
    elif daemon_status == "stopped":
        daemon_display = Icons.format_with_icon("ERROR", "Stopped", icon_mode)
        server_version = "Daemon not running"
    else:
        daemon_display = Icons.format_with_icon("WARNING", "Unknown", icon_mode)
        server_version = "Status unclear"

    docker_table.add_row("Docker Daemon", daemon_display, server_version)

    # Docker images with version information
    images = docker_data.get("images", {})
    image_versions = docker_data.get("image_versions", {})

    for image_name, image_status in images.items():
        if image_status == "available":
            base_status = Icons.format_with_icon("SUCCESS", "Available", icon_mode)
        elif image_status == "missing":
            base_status = Icons.format_with_icon("ERROR", "Missing", icon_mode)
        else:
            base_status = Icons.format_with_icon("WARNING", "Error", icon_mode)

        # Add version information if available
        details = ""
        if image_name in image_versions and image_status == "available":
            version_info = image_versions[image_name]
            current_ver = version_info.get("current_version", "unknown")
            has_update = version_info.get("has_update", False)

            if has_update:
                latest_ver = version_info.get("latest_version", "unknown")
                details = f"v{current_ver} (update to v{latest_ver} available)"
                status_display = Icons.format_with_icon(
                    "WARNING", "Update available", icon_mode
                )
            elif version_info.get("check_disabled", False):
                details = f"v{current_ver} (version checks disabled)"
                status_display = base_status
            elif "error" in version_info:
                details = f"v{current_ver} (version check failed)"
                status_display = base_status
            else:
                details = f"v{current_ver} (up to date)"
                status_display = base_status
        else:
            status_display = base_status

        docker_table.add_row(f"Image: {image_name}", status_display, details)

    # Docker capabilities
    capabilities = docker_data.get("capabilities", {})
    for cap_name, cap_status in capabilities.items():
        if cap_status == "available":
            cap_display = Icons.format_with_icon("SUCCESS", "Working", icon_mode)
        elif cap_status == "limited":
            cap_display = Icons.format_with_icon("WARNING", "Limited", icon_mode)
        else:
            cap_display = Icons.format_with_icon("ERROR", "Unavailable", icon_mode)

        docker_table.add_row(
            f"Capability: {cap_name.replace('_', ' ').title()}", cap_display, ""
        )

    console.print(docker_table)
    console.print()


def _print_usb_diagnostics_table(
    console: Console, usb_data: dict[str, Any], icon_mode: str = "emoji"
) -> None:
    """Print USB/Flash diagnostics table."""
    from glovebox.cli.helpers.theme import Icons

    usb_icon = Icons.get_icon("USB", icon_mode)
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
        status_display = Icons.format_with_icon("SUCCESS", "Working", icon_mode)
        platform_adapter = usb_detection.get("platform_adapter", "Unknown")
    elif detection_status == "unsupported_platform":
        status_display = Icons.format_with_icon("WARNING", "Unsupported", icon_mode)
        platform_adapter = "Platform not supported"
    else:
        status_display = Icons.format_with_icon("ERROR", "Error", icon_mode)
        platform_adapter = usb_detection.get("error", "Unknown error")

    usb_table.add_row("USB Detection", status_display, platform_adapter)

    # Detected devices
    detected_devices = usb_data.get("detected_devices", [])
    device_count = len(detected_devices)
    usb_table.add_row(
        "USB Devices",
        Icons.format_with_icon("SUCCESS", f"{device_count} found", icon_mode),
        "Currently connected devices",
    )

    # OS capabilities
    os_capabilities = usb_data.get("os_capabilities", {})
    mount_tool = os_capabilities.get("mount_tool", "unknown")

    if mount_tool in ["udisksctl", "diskutil"]:
        status_display = Icons.format_with_icon("SUCCESS", "Available", icon_mode)
        details = f"Using {mount_tool}"
    else:
        status_display = Icons.format_with_icon("ERROR", "Unavailable", icon_mode)
        details = "No mount tool found"

    usb_table.add_row("Mount Tool", status_display, details)

    console.print(usb_table)
    console.print()

    # Detailed USB devices table if devices are found
    if detected_devices:
        devices_table = Table(
            title=f"{Icons.get_icon('DEVICE', icon_mode)} Detected USB Devices ({len(detected_devices)})",
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
    console: Console, config_data: dict[str, Any], icon_mode: str = "emoji"
) -> None:
    """Print configuration diagnostics table."""
    from glovebox.cli.helpers.theme import Icons

    config_icon = Icons.get_icon("CONFIG", icon_mode)
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
        status_display = Icons.format_with_icon("SUCCESS", "Valid", icon_mode)
        details = user_config.get("found_config", "Configuration loaded")
    elif validation_status == "error":
        status_display = Icons.format_with_icon("ERROR", "Error", icon_mode)
        errors = user_config.get("validation_errors", ["Unknown error"])
        details = "; ".join(errors)
    else:
        status_display = Icons.format_with_icon("WARNING", "Unknown", icon_mode)
        details = "Status unclear"

    config_table.add_row("User Config", status_display, details)

    # Environment variables
    env_vars = user_config.get("environment_vars", {})
    env_count = len(env_vars)
    config_table.add_row(
        "Environment Variables",
        Icons.format_with_icon("INFO", f"{env_count} found", icon_mode),
        ", ".join(env_vars.keys()) if env_vars else "None",
    )

    # Keyboard discovery
    keyboard_discovery = config_data.get("keyboard_discovery", {})
    found_keyboards = keyboard_discovery.get("found_keyboards", 0)
    config_table.add_row(
        "Available Keyboards",
        Icons.format_with_icon("SUCCESS", f"{found_keyboards} found", icon_mode),
        "Keyboard configurations loaded",
    )

    console.print(config_table)
    console.print()


@handle_errors
def status_command(
    ctx: typer.Context,
    output_format: OutputFormatOption = "table",
) -> None:
    """Show system status and diagnostics.

    Formats:
    - table: Comprehensive diagnostics table (default)
    - json: Status data as JSON
    - text: Simple text output

    Shows comprehensive diagnostics for better troubleshooting.
    """
    # Get app context with user config
    app_ctx: AppContext = ctx.obj

    # Collect all status data
    data = _collect_status_data(app_ctx.user_config)

    # Get icon mode setting from app context
    icon_mode = app_ctx.icon_mode

    # Use the standard OutputFormatter utility
    formatter = OutputFormatter()

    # Format and display based on output_format option
    if output_format.lower() == "json":
        output = formatter.format(data, "json")
        print(output)
    elif output_format.lower() == "table":
        # Use Rich table format for comprehensive diagnostics
        _format_diagnostics_table(data, icon_mode)
    elif output_format.lower() == "text":
        # Simple text output using the formatter
        output = formatter.format(data, "text")
        print(output)
    else:
        print(
            f"Error: Unknown format '{output_format}'. Supported formats: table, json, text"
        )
        raise typer.Exit(1)


def register_commands(app: typer.Typer) -> None:
    """Register status command with the main app.

    Args:
        app: The main Typer app
    """
    app.command(name="status")(status_command)
