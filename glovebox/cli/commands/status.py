"""Status command for Glovebox CLI."""

import logging
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from glovebox.cli.app import AppContext
from glovebox.cli.core.command_base import BaseCommand
from glovebox.cli.decorators import handle_errors, with_metrics
from glovebox.cli.helpers.output_formatter import OutputFormatter
from glovebox.cli.helpers.parameters import OutputFormatOption
from glovebox.cli.helpers.theme import Colors, Icons
from glovebox.config.user_config import UserConfig
from glovebox.core.structlog_logger import get_struct_logger
from glovebox.utils.diagnostics import collect_all_diagnostics


logger = get_struct_logger(__name__)


class StatusCommand(BaseCommand):
    """Command class for system status and diagnostics."""

    def __init__(self) -> None:
        """Initialize StatusCommand."""
        super().__init__()
        self.output_formatter = OutputFormatter()

    def execute(
        self,
        ctx: typer.Context,
        output_format: OutputFormatOption = "table",
    ) -> None:
        """Execute status command logic.

        Args:
            ctx: Typer context with app configuration
            output_format: Output format (table, json, text)
        """
        # Get app context with user config
        app_ctx: AppContext = ctx.obj

        # Collect all status data
        data = self._collect_status_data(app_ctx.user_config)

        # Format and display based on output_format option
        if output_format.lower() == "json":
            output = self.output_formatter.format(data, "json")
            print(output)
        elif output_format.lower() == "table":
            # Use Rich table format with context-aware theme loading
            self._format_diagnostics_table(data, ctx)
        elif output_format.lower() == "text":
            # Simple text output using the formatter
            output = self.output_formatter.format(data, "text")
            print(output)
        else:
            self.console.print_error(
                f"Unknown format '{output_format}'. Supported formats: table, json, text"
            )
            ctx.exit(1)

    def _collect_status_data(
        self, user_config: "UserConfig | None" = None
    ) -> dict[str, Any]:
        """Collect all status data into a structured format using comprehensive diagnostics."""
        # Use the new comprehensive diagnostics collection
        full_diagnostics = collect_all_diagnostics(user_config)
        return full_diagnostics

    def _format_diagnostics_table(
        self, data: dict[str, Any], ctx: typer.Context | None = None
    ) -> None:
        """Format comprehensive diagnostics data as Rich tables."""
        from glovebox.cli.helpers.theme import (
            get_themed_console,
        )

        themed_console = get_themed_console(ctx=ctx)
        console = themed_console.console
        icon_mode = themed_console.icon_mode

        # Header with version
        header = Text(
            f"Glovebox v{data.get('version', 'unknown')}", style=Colors.ACCENT
        )
        firmware_icon = Icons.get_icon("FIRMWARE", icon_mode)
        console.print(
            Panel(
                header,
                title=f"{firmware_icon} Comprehensive Diagnostics",
                border_style=Colors.SECONDARY,
            )
        )
        console.print()

        # System Diagnostics
        self._print_system_diagnostics_table(console, data.get("system", {}), icon_mode)

        # Docker Diagnostics
        self._print_docker_diagnostics_table(console, data.get("docker", {}), icon_mode)

        # USB/Flash Diagnostics
        self._print_usb_diagnostics_table(console, data.get("usb_flash", {}), icon_mode)

        # Configuration Diagnostics
        self._print_config_diagnostics_table(
            console, data.get("configuration", {}), icon_mode
        )

    def _print_system_diagnostics_table(
        self, console: Console, system_data: dict[str, Any], icon_mode: str = "emoji"
    ) -> None:
        """Print system diagnostics table."""
        system_icon = Icons.get_icon("SYSTEM", icon_mode)
        system_table = Table(
            title=f"{system_icon} System Environment",
            show_header=True,
            header_style=Colors.HEADER,
        )
        system_table.add_column("Component", style=Colors.PRIMARY, no_wrap=True)
        system_table.add_column("Status", style=Colors.FIELD_NAME)
        system_table.add_column("Details", style=Colors.MUTED)

        environment = system_data.get("environment", {})
        file_system = system_data.get("file_system", {})
        disk_space = system_data.get("disk_space", {})

        # Environment info
        success_icon = Icons.get_icon("SUCCESS", icon_mode)
        system_table.add_row(
            "Platform",
            f"{success_icon} Available",
            environment.get("platform", "Unknown"),
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
        self, console: Console, docker_data: dict[str, Any], icon_mode: str = "emoji"
    ) -> None:
        """Print Docker diagnostics table."""
        docker_icon = Icons.get_icon("DOCKER", icon_mode)
        docker_table = Table(
            title=f"{docker_icon} Docker Environment",
            show_header=True,
            header_style=Colors.HEADER,
        )
        docker_table.add_column("Component", style=Colors.PRIMARY, no_wrap=True)
        docker_table.add_column("Status", style=Colors.FIELD_NAME)
        docker_table.add_column("Details", style=Colors.MUTED)

        # Docker availability
        if docker_data.get("docker_available", False):
            status_icon = Icons.get_icon("SUCCESS", icon_mode)
            status = f"{status_icon} Available"
            details = f"v{docker_data.get('docker_version', 'Unknown')}"
        else:
            status_icon = Icons.get_icon("ERROR", icon_mode)
            status = f"{status_icon} Not available"
            details = docker_data.get("docker_error", "Docker not found")

        docker_table.add_row("Docker", status, details)

        # Docker Compose availability
        if docker_data.get("compose_available", False):
            compose_status_icon = Icons.get_icon("SUCCESS", icon_mode)
            compose_status = f"{compose_status_icon} Available"
            compose_details = f"v{docker_data.get('compose_version', 'Unknown')}"
        else:
            compose_status_icon = Icons.get_icon("WARNING", icon_mode)
            compose_status = f"{compose_status_icon} Not available"
            compose_details = docker_data.get(
                "compose_error", "Docker Compose not found"
            )

        docker_table.add_row("Docker Compose", compose_status, compose_details)

        # Docker daemon status
        if docker_data.get("daemon_running", False):
            daemon_status_icon = Icons.get_icon("SUCCESS", icon_mode)
            daemon_status = f"{daemon_status_icon} Running"
            daemon_details = "Docker daemon is accessible"
        else:
            daemon_status_icon = Icons.get_icon("ERROR", icon_mode)
            daemon_status = f"{daemon_status_icon} Not running"
            daemon_details = docker_data.get(
                "daemon_error", "Docker daemon not accessible"
            )

        docker_table.add_row("Docker Daemon", daemon_status, daemon_details)

        console.print(docker_table)
        console.print()

    def _print_usb_diagnostics_table(
        self, console: Console, usb_data: dict[str, Any], icon_mode: str = "emoji"
    ) -> None:
        """Print USB/Flash diagnostics table."""
        usb_icon = Icons.get_icon("USB", icon_mode)
        usb_table = Table(
            title=f"{usb_icon} USB/Flash Environment",
            show_header=True,
            header_style=Colors.HEADER,
        )
        usb_table.add_column("Component", style=Colors.PRIMARY, no_wrap=True)
        usb_table.add_column("Status", style=Colors.FIELD_NAME)
        usb_table.add_column("Details", style=Colors.MUTED)

        # USB detection capability
        if usb_data.get("usb_detection_available", False):
            status_icon = Icons.get_icon("SUCCESS", icon_mode)
            status = f"{status_icon} Available"
            details = "USB device detection is functional"
        else:
            status_icon = Icons.get_icon("WARNING", icon_mode)
            status = f"{status_icon} Limited"
            details = usb_data.get(
                "usb_detection_error", "USB detection may not work properly"
            )

        usb_table.add_row("USB Detection", status, details)

        # Flash devices found
        devices_found = usb_data.get("flash_devices_found", 0)
        if devices_found > 0:
            device_status_icon = Icons.get_icon("SUCCESS", icon_mode)
            device_status = f"{device_status_icon} {devices_found} device(s)"
            device_details = "Flash-capable devices detected"
        else:
            device_status_icon = Icons.get_icon("INFO", icon_mode)
            device_status = f"{device_status_icon} No devices"
            device_details = "No flash-capable devices currently connected"

        usb_table.add_row("Flash Devices", device_status, device_details)

        # Platform-specific flash support
        platform_support = usb_data.get("platform_flash_support", "unknown")
        if platform_support == "full":
            platform_status_icon = Icons.get_icon("SUCCESS", icon_mode)
            platform_status = f"{platform_status_icon} Full support"
            platform_details = "All flash operations supported"
        elif platform_support == "limited":
            platform_status_icon = Icons.get_icon("WARNING", icon_mode)
            platform_status = f"{platform_status_icon} Limited support"
            platform_details = "Some flash operations may require manual steps"
        else:
            platform_status_icon = Icons.get_icon("ERROR", icon_mode)
            platform_status = f"{platform_status_icon} Unknown support"
            platform_details = "Flash support status unknown"

        usb_table.add_row("Platform Support", platform_status, platform_details)

        console.print(usb_table)
        console.print()

    def _print_config_diagnostics_table(
        self, console: Console, config_data: dict[str, Any], icon_mode: str = "emoji"
    ) -> None:
        """Print configuration diagnostics table."""
        config_icon = Icons.get_icon("CONFIG", icon_mode)
        config_table = Table(
            title=f"{config_icon} Configuration",
            show_header=True,
            header_style=Colors.HEADER,
        )
        config_table.add_column("Component", style=Colors.PRIMARY, no_wrap=True)
        config_table.add_column("Status", style=Colors.FIELD_NAME)
        config_table.add_column("Details", style=Colors.MUTED)

        # User config
        if config_data.get("user_config_exists", False):
            status_icon = Icons.get_icon("SUCCESS", icon_mode)
            status = f"{status_icon} Found"
            details = config_data.get("user_config_path", "Configuration loaded")
        else:
            status_icon = Icons.get_icon("INFO", icon_mode)
            status = f"{status_icon} Default"
            details = "Using default configuration"

        config_table.add_row("User Config", status, details)

        # Profile configuration
        profiles_count = config_data.get("keyboard_profiles_count", 0)
        if profiles_count > 0:
            profile_status_icon = Icons.get_icon("SUCCESS", icon_mode)
            profile_status = f"{profile_status_icon} {profiles_count} profile(s)"
            profile_details = "Keyboard profiles configured"
        else:
            profile_status_icon = Icons.get_icon("WARNING", icon_mode)
            profile_status = f"{profile_status_icon} No profiles"
            profile_details = "No keyboard profiles configured"

        config_table.add_row("Keyboard Profiles", profile_status, profile_details)

        # Cache configuration
        cache_status = config_data.get("cache_status", "unknown")
        if cache_status == "healthy":
            cache_status_icon = Icons.get_icon("SUCCESS", icon_mode)
            cache_status_text = f"{cache_status_icon} Healthy"
            cache_details = "Cache is functioning properly"
        elif cache_status == "warning":
            cache_status_icon = Icons.get_icon("WARNING", icon_mode)
            cache_status_text = f"{cache_status_icon} Warning"
            cache_details = config_data.get("cache_warning", "Cache has warnings")
        else:
            cache_status_icon = Icons.get_icon("ERROR", icon_mode)
            cache_status_text = f"{cache_status_icon} Error"
            cache_details = config_data.get("cache_error", "Cache has errors")

        config_table.add_row("Cache", cache_status_text, cache_details)

        console.print(config_table)
        console.print()


@handle_errors
@with_metrics("status")
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
    # Delegate to StatusCommand class
    command = StatusCommand()
    command.execute(ctx, output_format)


def register_commands(app: typer.Typer) -> None:
    """Register status command with the main app.

    Args:
        app: The main Typer app
    """
    app.command(name="status")(status_command)
