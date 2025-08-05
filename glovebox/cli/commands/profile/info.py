"""Keyboard information commands (list, show)."""

import json
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from glovebox.cli.app import AppContext
from glovebox.cli.decorators import handle_errors
from glovebox.cli.helpers import (
    print_error_message,
)
from glovebox.cli.helpers.parameters import OutputFormatOption
from glovebox.cli.helpers.theme import Colors, Icons
from glovebox.config.keyboard_profile import (
    get_available_keyboards,
    load_keyboard_config,
)
from glovebox.core.structlog_logger import get_struct_logger


logger = get_struct_logger(__name__)


def _get_keyboard_field_defaults() -> dict[str, Any]:
    """Get default values for keyboard configuration fields."""
    from glovebox.config.models.behavior import BehaviorConfig
    from glovebox.config.models.display import DisplayConfig
    from glovebox.config.models.keyboard import KeyboardConfig
    from glovebox.config.models.zmk import ZmkConfig

    defaults = {}

    # Get field defaults from KeyboardConfig
    for field_name, field_info in KeyboardConfig.model_fields.items():
        if hasattr(field_info, "default") and field_info.default is not None:
            defaults[field_name] = field_info.default
        elif (
            hasattr(field_info, "default_factory")
            and field_info.default_factory is not None
        ):
            try:
                defaults[field_name] = field_info.default_factory()  # type: ignore
            except Exception:
                defaults[field_name] = (
                    f"<factory: {field_info.default_factory.__name__}>"
                )
        else:
            defaults[field_name] = None

    # Add defaults for nested config objects
    try:
        defaults["display"] = DisplayConfig()
        defaults["behaviors"] = BehaviorConfig()
        defaults["zmk"] = ZmkConfig()
    except Exception:
        # If factory creation fails, mark as factory
        defaults["display"] = "<factory: DisplayConfig>"
        defaults["behaviors"] = "<factory: BehaviorConfig>"
        defaults["zmk"] = "<factory: ZmkConfig>"

    return defaults


def _get_keyboard_config_sources(
    keyboard_name: str, app_ctx: AppContext
) -> dict[str, str]:
    """Get source file information for keyboard configuration fields."""
    # This is a simplified implementation - in a full implementation,
    # we would need to modify the config loading to track sources
    from pathlib import Path

    sources = {}
    keyboard_paths = app_ctx.user_config.get("keyboard_paths", [])

    # Try to find the main config file
    main_config_file = None
    for keyboard_path in keyboard_paths:
        possible_files = [
            Path(keyboard_path) / f"{keyboard_name}.yaml",
            Path(keyboard_path) / keyboard_name / "main.yaml",
            Path(keyboard_path) / "keyboards" / f"{keyboard_name}.yaml",
            Path(keyboard_path) / "keyboards" / keyboard_name / "main.yaml",
        ]

        for file_path in possible_files:
            if file_path.exists():
                main_config_file = file_path
                break

        if main_config_file:
            break

    # For now, mark all fields as coming from the main config file
    # In a full implementation, we would track which include file each field came from
    source_name = (
        str(main_config_file)
        if main_config_file
        else f"{keyboard_name}.yaml (not found)"
    )

    # Basic keyboard fields
    basic_fields = ["keyboard", "description", "vendor", "key_count"]
    for field in basic_fields:
        sources[field] = source_name

    # Config sections that might come from includes
    sources["compile_methods"] = f"{keyboard_name}/strategies.yaml"
    sources["flash_methods"] = f"{keyboard_name}/hardware.yaml"
    sources["firmwares"] = f"{keyboard_name}/firmwares.yaml"
    sources["behaviors"] = "config/behaviors/common.yaml"
    sources["display"] = "config/display/defaults.yaml"
    sources["zmk"] = "config/zmk/validation.yaml"

    return sources


def _print_keyboard_config_table(
    keyboard_config: Any,
    keyboard_name: str,
    app_ctx: AppContext,
    show_sources: bool,
    show_defaults: bool,
    verbose: bool,
) -> None:
    """Print keyboard configuration in a table format with optional sources and defaults."""
    from glovebox.cli.helpers.theme import Icons

    console = Console()

    # Create table with appropriate columns
    table = Table(title=f"Keyboard Configuration: {keyboard_name}")
    table.add_column("Setting", style=Colors.PRIMARY, width=25)
    table.add_column("Current Value", style=Colors.SUCCESS, width=30)

    if show_defaults:
        table.add_column("Default Value", style=Colors.SECONDARY, width=25)

    if show_sources:
        table.add_column("Source", style=Colors.WARNING, width=35)

    # Get defaults and sources if requested
    defaults = _get_keyboard_field_defaults() if show_defaults else {}
    sources = (
        _get_keyboard_config_sources(keyboard_name, app_ctx) if show_sources else {}
    )

    def format_value(value: Any) -> str:
        """Format a value for display."""
        if value is None:
            return "(not set)"
        elif isinstance(value, list):
            if not value:
                return "(empty list)"
            elif len(value) == 1:
                return str(value[0])
            else:
                return f"[{len(value)} items]"
        elif isinstance(value, dict):
            if not value:
                return "(empty dict)"
            else:
                return f"{{...}} ({len(value)} keys)"
        elif hasattr(value, "__dict__"):
            # For Pydantic models
            return f"<{value.__class__.__name__}>"
        else:
            return str(value)

    # Basic keyboard information
    basic_fields = [
        ("keyboard", getattr(keyboard_config, "keyboard", None)),
        ("description", getattr(keyboard_config, "description", None)),
        ("vendor", getattr(keyboard_config, "vendor", None)),
        ("key_count", getattr(keyboard_config, "key_count", None)),
    ]

    for field_name, field_value in basic_fields:
        row_data = [field_name, format_value(field_value)]

        if show_defaults:
            default_value = defaults.get(field_name)
            row_data.append(format_value(default_value))

        if show_sources:
            source = sources.get(field_name, "unknown")
            row_data.append(source)

        table.add_row(*row_data)

    # Configuration sections
    config_sections = []
    if hasattr(keyboard_config, "compile_methods") and keyboard_config.compile_methods:
        config_sections.append(("compile_methods", keyboard_config.compile_methods))

    if hasattr(keyboard_config, "flash_methods") and keyboard_config.flash_methods:
        config_sections.append(("flash_methods", keyboard_config.flash_methods))

    if hasattr(keyboard_config, "firmwares") and keyboard_config.firmwares:
        config_sections.append(("firmwares", keyboard_config.firmwares))

    # Show verbose sections if verbose flag is set OR if sources/defaults are requested
    show_verbose_sections = verbose or show_sources or show_defaults

    if show_verbose_sections:
        if hasattr(keyboard_config, "behaviors") and keyboard_config.behaviors:
            config_sections.append(("behaviors", keyboard_config.behaviors))

        if hasattr(keyboard_config, "display") and keyboard_config.display:
            config_sections.append(("display", keyboard_config.display))

        if hasattr(keyboard_config, "zmk") and keyboard_config.zmk:
            config_sections.append(("zmk", keyboard_config.zmk))

    for field_name, field_value in config_sections:
        row_data = [field_name, format_value(field_value)]

        if show_defaults:
            default_value = defaults.get(field_name)
            row_data.append(format_value(default_value))

        if show_sources:
            source = sources.get(field_name, "unknown")
            row_data.append(source)

        table.add_row(*row_data)

    # Print header with icon
    header_icon = Icons.get_icon("KEYBOARD", app_ctx.icon_mode)
    console.print(
        Panel(
            f"{header_icon} Keyboard Configuration Details", border_style=Colors.PRIMARY
        )
    )
    console.print(table)

    # Print helpful information
    console.print("\n[dim]Configuration information:[/dim]")
    if show_defaults:
        console.print(
            "[dim]  • Default values shown are from Pydantic model field definitions[/dim]"
        )
    if show_sources:
        console.print(
            "[dim]  • Sources show the configuration files that provide each setting[/dim]"
        )
        console.print(
            "[dim]  • Keyboard configs use an include system for modular configuration[/dim]"
        )

    console.print(
        f"\n[dim]Use 'glovebox keyboard edit {keyboard_name} --interactive' to modify configuration[/dim]"
    )


def _enhance_config_data_with_metadata(
    config_data: dict[str, Any],
    keyboard_config: Any,
    keyboard_name: str,
    app_ctx: AppContext,
    show_sources: bool,
    show_defaults: bool,
) -> dict[str, Any]:
    """Enhance config data with sources and defaults metadata for non-text formats."""
    enhanced_data = config_data.copy()

    if show_defaults:
        enhanced_data["_defaults"] = _get_keyboard_field_defaults()

    if show_sources:
        enhanced_data["_sources"] = _get_keyboard_config_sources(keyboard_name, app_ctx)

    return enhanced_data


def complete_profile_names(incomplete: str) -> list[str]:
    """Tab completion for profile names."""
    try:
        from glovebox.config import create_user_config

        user_config = create_user_config()
        keyboards = get_available_keyboards(user_config)
        return [keyboard for keyboard in keyboards if keyboard.startswith(incomplete)]
    except Exception:
        # If completion fails, return empty list
        return []


def _build_keyboard_config_data(
    keyboard_config: Any, verbose: bool = False
) -> dict[str, Any]:
    """Build comprehensive keyboard configuration data for output formatting.

    Args:
        keyboard_config: The keyboard configuration object
        verbose: Include detailed configuration information

    Returns:
        Dictionary containing formatted configuration data
    """
    # Basic keyboard information
    config_data = {
        "keyboard": keyboard_config.keyboard,
        "description": keyboard_config.description,
        "vendor": keyboard_config.vendor,
        "key_count": keyboard_config.key_count,
    }

    # Flash methods (multiple methods support)
    if keyboard_config.flash_methods:
        flash_methods = []
        for i, method in enumerate(keyboard_config.flash_methods):
            method_data = {
                "priority": i + 1,
                "method_type": method.method_type,
            }

            # Add method-specific fields
            if hasattr(method, "device_query") and method.device_query:
                method_data["device_query"] = method.device_query
            if hasattr(method, "vid") and method.vid:
                method_data["vid"] = method.vid
            if hasattr(method, "pid") and method.pid:
                method_data["pid"] = method.pid
            if hasattr(method, "mount_timeout") and method.mount_timeout:
                method_data["mount_timeout"] = method.mount_timeout
            if hasattr(method, "copy_timeout") and method.copy_timeout:
                method_data["copy_timeout"] = method.copy_timeout

            flash_methods.append(method_data)

        config_data["flash_methods"] = flash_methods

        # Keep primary flash for backward compatibility
        primary_flash = keyboard_config.flash_methods[0]
        config_data["flash"] = {
            "primary_method": "usb",
            "total_methods": len(keyboard_config.flash_methods),
        }

    # Compile methods (multiple methods support)
    if keyboard_config.compile_methods:
        compile_methods = []
        for i, method in enumerate(keyboard_config.compile_methods):
            method_data = {
                "priority": i + 1,
                "method_type": method.method_type,
            }

            # Add method-specific fields
            if hasattr(method, "image") and method.image:
                method_data["image"] = method.image
            if hasattr(method, "repository") and method.repository:
                method_data["repository"] = method.repository
            if hasattr(method, "branch") and method.branch:
                method_data["branch"] = method.branch
            if hasattr(method, "jobs") and method.jobs:
                method_data["jobs"] = method.jobs

            compile_methods.append(method_data)

        config_data["compile_methods"] = compile_methods

        # Keep primary build for backward compatibility
        primary_compile = keyboard_config.compile_methods[0]
        config_data["build"] = {
            "primary_method": primary_compile.method_type,
            "total_methods": len(keyboard_config.compile_methods),
        }

    # Firmware configurations
    if keyboard_config.firmwares:
        firmwares = {}
        for name, fw in keyboard_config.firmwares.items():
            fw_data = {
                "version": fw.version,
                "description": fw.description,
            }

            # Include build options if verbose
            if verbose and hasattr(fw, "build_options") and fw.build_options:
                fw_data["build_options"] = {
                    "repository": fw.build_options.repository,
                    "branch": fw.build_options.branch,
                }

            # Include kconfig if verbose and present
            if verbose and hasattr(fw, "kconfig") and fw.kconfig:
                kconfig_data = {}
                for key, config in fw.kconfig.items():
                    kconfig_data[key] = {
                        "name": config.name,
                        "type": config.type,
                        "default": config.default,
                        "description": config.description,
                    }
                fw_data["kconfig"] = kconfig_data

            firmwares[name] = fw_data

        config_data["firmwares"] = firmwares
        config_data["firmware_count"] = len(firmwares)

    # Include configuration sections if verbose
    if verbose:
        # Behavior configuration
        if hasattr(keyboard_config, "behaviors") and keyboard_config.behaviors:
            behaviors_data = {}
            if hasattr(keyboard_config.behaviors, "system_behaviors"):
                behaviors_data["system_behaviors_count"] = len(
                    keyboard_config.behaviors.system_behaviors
                )
            config_data["behaviors"] = behaviors_data

        # Display configuration
        if hasattr(keyboard_config, "display") and keyboard_config.display:
            display_data = {}
            if hasattr(keyboard_config.display, "layout_structure"):
                display_data["has_layout_structure"] = True
            if hasattr(keyboard_config.display, "formatting"):
                display_data["has_formatting_config"] = True
            config_data["display"] = display_data

        # ZMK configuration
        if hasattr(keyboard_config, "zmk") and keyboard_config.zmk:
            zmk_data = {}
            if hasattr(keyboard_config.zmk, "validation_limits"):
                zmk_data["has_validation_limits"] = True
            if hasattr(keyboard_config.zmk, "patterns"):
                zmk_data["has_patterns"] = True
            if hasattr(keyboard_config.zmk, "compatible_strings"):
                zmk_data["has_compatible_strings"] = True
            config_data["zmk"] = zmk_data

        # Include configuration
        if hasattr(keyboard_config, "includes") and keyboard_config.includes:
            config_data["includes"] = keyboard_config.includes
            config_data["include_count"] = len(keyboard_config.includes)

    return config_data


def _print_keyboard_details_rich(
    config_data: dict[str, Any],
    icon_mode: str = "emoji",
    console: Console | None = None,
) -> None:
    """Print keyboard configuration details using rich formatting.

    Args:
        config_data: Keyboard configuration data
        icon_mode: Icon mode for display
        console: Rich console instance
    """
    if console is None:
        console = Console()

    # Header panel
    keyboard_name = config_data.get("keyboard", "Unknown")
    keyboard_icon = Icons.get_icon("KEYBOARD", icon_mode)
    header = Text(f"Keyboard Configuration: {keyboard_name}", style=Colors.HEADER)
    console.print(
        Panel(
            header,
            title=f"{keyboard_icon} Keyboard Details",
            border_style=Colors.SECONDARY,
        )
    )
    console.print()

    # Basic information table
    basic_table = Table(
        title=f"{Icons.get_icon('INFO', icon_mode)} Basic Information",
        show_header=True,
        header_style=Colors.HEADER,
    )
    basic_table.add_column("Property", style=Colors.PRIMARY, no_wrap=True)
    basic_table.add_column("Value", style=Colors.FIELD_VALUE)

    # Add basic properties
    basic_properties = [
        ("Name", config_data.get("keyboard", "Unknown")),
        ("Description", config_data.get("description", "No description")),
        ("Vendor", config_data.get("vendor", "Unknown")),
        ("Key Count", config_data.get("key_count", "Unknown")),
    ]

    for prop, value in basic_properties:
        basic_table.add_row(prop, str(value))

    console.print(basic_table)
    console.print()

    # Flash methods table
    flash_methods = config_data.get("flash_methods", [])
    if flash_methods:
        flash_table = Table(
            title=f"{Icons.get_icon('FLASH', icon_mode)} Flash Methods",
            show_header=True,
            header_style=Colors.HEADER,
        )
        flash_table.add_column("Priority", style=Colors.PRIMARY, no_wrap=True)
        flash_table.add_column("Method", style=Colors.WARNING)
        flash_table.add_column("Details", style=Colors.FIELD_VALUE)

        for method in flash_methods:
            priority = str(method.get("priority", "Unknown"))
            method_type = method.get("method_type", "Unknown")

            # Build details string
            details = []
            if method.get("device_query"):
                details.append(f"Query: {method['device_query']}")
            if method.get("vid") and method.get("pid"):
                details.append(f"VID:PID {method['vid']}:{method['pid']}")
            if method.get("mount_timeout"):
                details.append(f"Mount timeout: {method['mount_timeout']}s")

            details_str = "; ".join(details) if details else "Default settings"
            flash_table.add_row(priority, method_type, details_str)

        console.print(flash_table)
        console.print()

    # Compile methods table
    compile_methods = config_data.get("compile_methods", [])
    if compile_methods:
        compile_table = Table(
            title=f"{Icons.get_icon('BUILD', icon_mode)} Compile Methods",
            show_header=True,
            header_style=Colors.HEADER,
        )
        compile_table.add_column("Priority", style=Colors.PRIMARY, no_wrap=True)
        compile_table.add_column("Method", style=Colors.SECONDARY)
        compile_table.add_column("Details", style=Colors.FIELD_VALUE)

        for method in compile_methods:
            priority = str(method.get("priority", "Unknown"))
            method_type = method.get("method_type", "Unknown")

            # Build details string
            details = []
            if method.get("repository"):
                details.append(f"Repo: {method['repository']}")
            if method.get("branch"):
                details.append(f"Branch: {method['branch']}")
            if method.get("image"):
                details.append(f"Image: {method['image']}")

            details_str = "; ".join(details) if details else "Default settings"
            compile_table.add_row(priority, method_type, details_str)

        console.print(compile_table)
        console.print()

    # Firmwares table
    firmwares = config_data.get("firmwares", {})
    if firmwares:
        firmware_table = Table(
            title=f"{Icons.get_icon('FIRMWARE', icon_mode)} Available Firmwares ({len(firmwares)})",
            show_header=True,
            header_style=Colors.HEADER,
        )
        firmware_table.add_column("Firmware", style=Colors.PRIMARY, no_wrap=True)
        firmware_table.add_column("Version", style=Colors.SUCCESS)
        firmware_table.add_column("Description", style=Colors.FIELD_VALUE)

        for name, fw_data in firmwares.items():
            version = fw_data.get("version", "Unknown")
            description = fw_data.get("description", "No description")
            firmware_table.add_row(name, version, description)

        console.print(firmware_table)
        console.print()

    # Selected firmware details if specified
    if config_data.get("selected_firmware"):
        selected_fw = config_data["selected_firmware"]
        fw_details = config_data.get("firmware_details", {})
        if fw_details:
            selected_table = Table(
                title=f"{Icons.get_icon('STAR', icon_mode)} Selected Firmware: {selected_fw}",
                show_header=True,
                header_style=Colors.HEADER,
            )
            selected_table.add_column("Property", style=Colors.PRIMARY, no_wrap=True)
            selected_table.add_column("Value", style=Colors.FIELD_VALUE)

            for prop, value in fw_details.items():
                if isinstance(value, dict):
                    value_str = "; ".join(f"{k}: {v}" for k, v in value.items())
                else:
                    value_str = str(value)
                selected_table.add_row(prop.replace("_", " ").title(), value_str)

            console.print(selected_table)
        elif config_data.get("firmware_error"):
            error_icon = Icons.get_icon("ERROR", icon_mode)
            console.print(
                f"\n[bold red]{error_icon} {config_data['firmware_error']}[/bold red]\n"
            )


@handle_errors
def list_profiles(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed information"
    ),
    output_format: OutputFormatOption = "text",
) -> None:
    """List available profile configurations."""
    # Get app context with user config
    app_ctx: AppContext = ctx.obj
    keyboards = get_available_keyboards(app_ctx.user_config)

    if not keyboards:
        print("No keyboards found")
        return

    if output_format.lower() == "json":
        # JSON output
        output: dict[str, list[dict[str, Any]]] = {"keyboards": []}
        for keyboard_name in keyboards:
            # Get detailed information if verbose
            if verbose:
                try:
                    typed_config = load_keyboard_config(
                        keyboard_name, app_ctx.user_config
                    )
                    # Convert to dict for JSON serialization
                    keyboard_dict = {
                        "name": typed_config.keyboard,
                        "description": typed_config.description,
                        "vendor": typed_config.vendor,
                        "key_count": typed_config.key_count,
                    }
                    output["keyboards"].append(keyboard_dict)
                except Exception:
                    output["keyboards"].append({"name": keyboard_name})
            else:
                output["keyboards"].append({"name": keyboard_name})

        print(json.dumps(output, indent=2))
        return

    # Text output with rich formatting
    console = Console()

    if verbose:
        # Create header panel
        keyboard_icon = Icons.get_icon("KEYBOARD", app_ctx.icon_mode)
        header = Text(
            f"Available Profile Configurations ({len(keyboards)})",
            style=Colors.HEADER,
        )
        console.print(
            Panel(
                header,
                title=f"{keyboard_icon} Profile Configurations",
                border_style=Colors.SECONDARY,
            )
        )
        console.print()

        # Create table for detailed keyboard information
        table = Table(
            title=f"{keyboard_icon} Keyboard Details",
            show_header=True,
            header_style=Colors.HEADER,
        )
        table.add_column("Keyboard", style=Colors.PRIMARY, no_wrap=True)
        table.add_column("Description", style=Colors.FIELD_VALUE)
        table.add_column("Vendor", style=Colors.WARNING)
        table.add_column("Key Count", style=Colors.SUCCESS)
        table.add_column("Firmwares", style=Colors.ACCENT)

        # Get and display detailed information for each keyboard
        for keyboard_name in keyboards:
            try:
                keyboard_config = load_keyboard_config(
                    keyboard_name, app_ctx.user_config
                )
                description = (
                    keyboard_config.description
                    if hasattr(keyboard_config, "description")
                    else "N/A"
                )
                vendor = (
                    keyboard_config.vendor
                    if hasattr(keyboard_config, "vendor")
                    else "N/A"
                )
                key_count = (
                    str(keyboard_config.key_count)
                    if hasattr(keyboard_config, "key_count")
                    and keyboard_config.key_count
                    else "N/A"
                )

                # Count firmwares
                firmware_count = (
                    len(keyboard_config.firmwares)
                    if hasattr(keyboard_config, "firmwares")
                    and keyboard_config.firmwares
                    else 0
                )

                firmware_display = (
                    f"{firmware_count} available" if firmware_count > 0 else "None"
                )

                table.add_row(
                    keyboard_name, description, vendor, key_count, firmware_display
                )
            except Exception as e:
                error_icon = Icons.get_icon("ERROR", app_ctx.icon_mode)
                table.add_row(
                    keyboard_name, f"{error_icon} {str(e)}", "Error", "Error", "Error"
                )

        console.print(table)
    else:
        # Simple list format with rich styling
        keyboard_icon = Icons.get_icon("KEYBOARD", app_ctx.icon_mode)
        console.print(
            f"\n[bold cyan]{keyboard_icon} Available profile configurations ({len(keyboards)}):[/bold cyan]\n"
        )

        for keyboard in keyboards:
            bullet_icon = Icons.get_icon("BULLET", app_ctx.icon_mode)
            console.print(f"  {bullet_icon} [cyan]{keyboard}[/cyan]")


@handle_errors
def show_profile(
    ctx: typer.Context,
    profile_name: str | None = typer.Argument(
        None, help="Profile name to show", autocompletion=complete_profile_names
    ),
    firmware_version: str | None = typer.Argument(
        None, help="Firmware version to show (optional)"
    ),
    profile: str | None = typer.Option(
        None,
        "--profile",
        "-p",
        help="Profile in format 'profile' or 'profile/firmware' (overrides positional args)",
    ),
    output_format: OutputFormatOption = "text",
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed configuration information"
    ),
    show_sources: bool = typer.Option(
        False, "--sources", help="Show configuration sources and include hierarchy"
    ),
    show_defaults: bool = typer.Option(
        False, "--defaults", help="Show default values alongside current values"
    ),
) -> None:
    """Show details of a specific keyboard configuration.

    Examples:
        # Show keyboard using positional argument
        glovebox keyboard show glove80

        # Show keyboard with firmware using positional arguments
        glovebox keyboard show glove80 v25.05

        # Show keyboard using --profile option
        glovebox keyboard show --profile glove80

        # Show keyboard with firmware using --profile option
        glovebox keyboard show --profile glove80/v25.05
    """
    from glovebox.cli.helpers.output_formatter import create_output_formatter

    # Get app context with user config
    app_ctx: AppContext = ctx.obj

    # Parse keyboard and firmware from profile or positional args
    if profile:
        if profile_name or firmware_version:
            print_error_message(
                "Cannot use both --profile and positional arguments. Use one or the other."
            )
            raise typer.Exit(1)

        # Parse profile
        if "/" in profile:
            profile_name, firmware_version = profile.split("/", 1)
        else:
            profile_name = profile
            firmware_version = None

    if not profile_name:
        print_error_message(
            "Profile name is required (either as positional argument or via --profile)"
        )
        raise typer.Exit(1)

    # Get the profile configuration
    keyboard_config = load_keyboard_config(profile_name, app_ctx.user_config)

    # Create output formatter
    formatter = create_output_formatter()

    # Build comprehensive configuration data
    config_data = _build_keyboard_config_data(keyboard_config, verbose)

    # If firmware version is specified, add firmware-specific information
    if firmware_version:
        config_data["selected_firmware"] = firmware_version
        if hasattr(keyboard_config, "firmwares") and keyboard_config.firmwares:
            firmware_config = keyboard_config.firmwares.get(firmware_version)
            if firmware_config:
                config_data["firmware_details"] = {
                    "version": firmware_config.version,
                    "description": firmware_config.description,
                }
                if (
                    verbose
                    and hasattr(firmware_config, "build_options")
                    and firmware_config.build_options
                ):
                    config_data["firmware_details"]["build_options"] = {
                        "repository": firmware_config.build_options.repository,
                        "branch": firmware_config.build_options.branch,
                    }
            else:
                config_data["firmware_error"] = (
                    f"Firmware version '{firmware_version}' not found"
                )

    # Use rich formatting for text output or unified formatter for other formats
    if output_format.lower() == "text":
        # Handle sources and defaults flags for text output
        if show_sources or show_defaults:
            _print_keyboard_config_table(
                keyboard_config,
                profile_name,
                app_ctx,
                show_sources,
                show_defaults,
                verbose,
            )
        else:
            _print_keyboard_details_rich(
                config_data, app_ctx.icon_mode, console=Console()
            )
    else:
        # For non-text formats, add sources and defaults to config_data if requested
        if show_sources or show_defaults:
            config_data = _enhance_config_data_with_metadata(
                config_data,
                keyboard_config,
                profile_name,
                app_ctx,
                show_sources,
                show_defaults,
            )
        # Use the unified output formatter for other formats
        formatter.print_formatted(config_data, output_format)
