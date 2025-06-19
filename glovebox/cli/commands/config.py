"""Configuration management CLI commands."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from glovebox.cli.app import AppContext
from glovebox.cli.decorators import handle_errors
from glovebox.cli.helpers import (
    print_error_message,
    print_list_item,
    print_success_message,
)
from glovebox.config.keyboard_profile import (
    get_available_keyboards,
    load_keyboard_config,
)


logger = logging.getLogger(__name__)


def complete_config_keys(incomplete: str) -> list[str]:
    """Tab completion for configuration keys."""
    try:
        from glovebox.config.models.firmware import (
            FirmwareDockerConfig,
            FirmwareFlashConfig,
        )
        from glovebox.config.models.user import UserConfigData

        def get_all_config_keys() -> list[str]:
            """Get all valid configuration keys from the models."""
            keys = []

            # Add core keys
            for field_name in UserConfigData.model_fields:
                if field_name not in [
                    "firmware",
                    "compilation",
                ]:  # These are handled separately
                    keys.append(field_name)

            # Add firmware keys
            for field_name in FirmwareFlashConfig.model_fields:
                keys.append(f"firmware.flash.{field_name}")

            for field_name in FirmwareDockerConfig.model_fields:
                keys.append(f"firmware.docker.{field_name}")

            return keys

        valid_keys = get_all_config_keys()
        return [key for key in valid_keys if key.startswith(incomplete)]
    except Exception:
        # If completion fails, return empty list
        return []


def complete_config_list_keys(incomplete: str) -> list[str]:
    """Tab completion for configuration keys that are lists."""
    try:
        from glovebox.config.models.firmware import (
            FirmwareDockerConfig,
            FirmwareFlashConfig,
        )
        from glovebox.config.models.user import UserConfigData

        def get_list_config_keys() -> list[str]:
            """Get configuration keys that are lists."""
            keys = []

            # Check core keys for list types
            for field_name, field_info in UserConfigData.model_fields.items():
                if (
                    field_name not in ["firmware", "compilation"]
                    and hasattr(field_info, "annotation")
                    and field_info.annotation
                ):
                    annotation = field_info.annotation
                    if (
                        hasattr(annotation, "__origin__")
                        and annotation.__origin__ is list
                    ):
                        keys.append(field_name)

            # Check firmware keys for list types
            for field_name, field_info in FirmwareFlashConfig.model_fields.items():
                if hasattr(field_info, "annotation") and field_info.annotation:
                    annotation = field_info.annotation
                    if (
                        hasattr(annotation, "__origin__")
                        and annotation.__origin__ is list
                    ):
                        keys.append(f"firmware.flash.{field_name}")

            for field_name, field_info in FirmwareDockerConfig.model_fields.items():
                if hasattr(field_info, "annotation") and field_info.annotation:
                    annotation = field_info.annotation
                    if (
                        hasattr(annotation, "__origin__")
                        and annotation.__origin__ is list
                    ):
                        keys.append(f"firmware.docker.{field_name}")

            return keys

        valid_keys = get_list_config_keys()
        return [key for key in valid_keys if key.startswith(incomplete)]
    except Exception:
        # If completion fails, return empty list
        return []


def complete_keyboard_names(incomplete: str) -> list[str]:
    """Tab completion for keyboard names."""
    try:
        from glovebox.config import create_user_config

        user_config = create_user_config()
        keyboards = get_available_keyboards(user_config)
        return [keyboard for keyboard in keyboards if keyboard.startswith(incomplete)]
    except Exception:
        # If completion fails, return empty list
        return []


def complete_firmware_names(ctx: typer.Context, incomplete: str) -> list[str]:
    """Tab completion for firmware names based on keyboard context."""
    try:
        from glovebox.cli.app import AppContext

        # Try to get keyboard name from command line args
        # This is a bit tricky since we need to parse the current command context
        app_ctx = getattr(ctx, "obj", None)
        if not app_ctx or not isinstance(app_ctx, AppContext):
            return []

        # Get keyboard from command line arguments - this is contextual
        # In practice, we need the keyboard parameter which should be before this
        params = getattr(ctx, "params", {})
        keyboard_name = params.get("keyboard_name")

        if not keyboard_name:
            return []

        keyboard_config = load_keyboard_config(keyboard_name, app_ctx.user_config)

        if not keyboard_config.firmwares:
            return []

        firmwares = list(keyboard_config.firmwares.keys())
        return [firmware for firmware in firmwares if firmware.startswith(incomplete)]
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
                "method_type": method.type,
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
            "primary_method": primary_compile.type,
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


# Create a typer app for configuration commands
config_app = typer.Typer(
    name="config",
    help="Configuration management commands",
    no_args_is_help=True,
)


@config_app.command(name="set")
@handle_errors
def set_config(
    ctx: typer.Context,
    key: Annotated[
        str,
        typer.Argument(
            help="Configuration key to set", autocompletion=complete_config_keys
        ),
    ],
    value: Annotated[str, typer.Argument(help="Value to set")],
    save: Annotated[
        bool, typer.Option("--save", help="Save configuration to file")
    ] = True,
) -> None:
    """Set a configuration value."""
    # Get app context with user config
    app_ctx: AppContext = ctx.obj

    # Get all valid keys from the configuration models
    from glovebox.config.models.firmware import (
        FirmwareDockerConfig,
        FirmwareFlashConfig,
    )
    from glovebox.config.models.user import UserConfigData

    def get_all_config_keys() -> list[str]:
        """Get all valid configuration keys from the models."""
        keys = []

        # Add core keys
        for field_name in UserConfigData.model_fields:
            if field_name not in [
                "firmware",
                "compilation",
            ]:  # These are handled separately
                keys.append(field_name)

        # Add firmware keys
        for field_name in FirmwareFlashConfig.model_fields:
            keys.append(f"firmware.flash.{field_name}")

        for field_name in FirmwareDockerConfig.model_fields:
            keys.append(f"firmware.docker.{field_name}")

        return keys

    valid_keys = get_all_config_keys()

    # Check if key is valid
    if key not in valid_keys:
        print_error_message(f"Unknown configuration key: {key}")
        print_error_message(f"Valid keys: {', '.join(sorted(valid_keys))}")
        raise typer.Exit(1)

    # Get field info for type conversion
    def get_field_type_for_key(config_key: str) -> type:
        """Get the expected type for a configuration key."""
        from glovebox.config.models.firmware import (
            FirmwareDockerConfig,
            FirmwareFlashConfig,
        )
        from glovebox.config.models.user import UserConfigData

        if "." in config_key:
            parts = config_key.split(".")
            if len(parts) == 3 and parts[0] == "firmware":
                if parts[1] == "flash":
                    field_info = FirmwareFlashConfig.model_fields.get(parts[2])
                elif parts[1] == "docker":
                    field_info = FirmwareDockerConfig.model_fields.get(parts[2])
                else:
                    return str
            else:
                return str
        else:
            field_info = UserConfigData.model_fields.get(config_key)

        if field_info and hasattr(field_info, "annotation") and field_info.annotation:
            annotation = field_info.annotation
            # Handle basic types
            if annotation is int:
                return int
            elif annotation is bool:
                return bool
            elif hasattr(annotation, "__origin__") and annotation.__origin__ is list:
                return list
            else:
                return str
        return str

    field_type = get_field_type_for_key(key)

    # Convert value to appropriate type
    typed_value: Any = None
    try:
        if field_type is bool:
            typed_value = value.lower() in ("true", "yes", "1", "y")
        elif field_type is int:
            typed_value = int(value)
        elif field_type is list:
            typed_value = [item.strip() for item in value.split(",")]
        else:
            typed_value = value
    except ValueError as err:
        if field_type is int:
            print_error_message(f"Invalid integer value: {value}")
            raise typer.Exit(1) from err
        raise

    # Set the value
    app_ctx.user_config.set(key, typed_value)
    print_success_message(f"Set {key} = {typed_value}")

    # Save configuration if requested
    if save:
        app_ctx.user_config.save()
        print_success_message("Configuration saved")


@config_app.command(name="show")
@handle_errors
def show_config(
    ctx: typer.Context,
    show_sources: Annotated[
        bool, typer.Option("--sources", help="Show configuration sources")
    ] = False,
) -> None:
    """Show current configuration settings."""
    # Get app context with user config
    app_ctx: AppContext = ctx.obj

    # Create a nice table display
    console = Console()
    table = Table(title="Glovebox Configuration")

    # Add columns based on what to show
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    if show_sources:
        table.add_column("Source", style="yellow")

    # Get all configuration keys from models
    def get_all_display_keys() -> list[str]:
        """Get all configuration keys for display."""
        from glovebox.config.models.firmware import (
            FirmwareDockerConfig,
            FirmwareFlashConfig,
        )
        from glovebox.config.models.user import UserConfigData

        keys = []

        # Add core keys
        for field_name in UserConfigData.model_fields:
            if field_name not in ["firmware"]:  # Handle firmware separately
                keys.append(field_name)

        # Add firmware keys
        for field_name in FirmwareFlashConfig.model_fields:
            keys.append(f"firmware.flash.{field_name}")

        for field_name in FirmwareDockerConfig.model_fields:
            keys.append(f"firmware.docker.{field_name}")

        return keys

    display_keys = get_all_display_keys()

    # Add rows for each configuration setting
    for key in sorted(display_keys):
        value = app_ctx.user_config.get(key)

        # Format list values for display
        if isinstance(value, list):
            if not value:
                value_str = "(empty list)"
            else:
                value_str = "\n".join(str(v) for v in value)
        else:
            value_str = str(value)

        if show_sources:
            source = app_ctx.user_config.get_source(key)
            table.add_row(key, value_str, source)
        else:
            table.add_row(key, value_str)

    # Print the table
    console.print(table)


@config_app.command(name="options")
@handle_errors
def show_all_options(
    ctx: typer.Context,
    format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json, markdown)"
    ),
    category: str = typer.Option(
        "all",
        "--category",
        "-c",
        help="Show specific category (all, core, firmware, cache)",
    ),
) -> None:
    """Show all available configuration options with descriptions and defaults."""
    from glovebox.config.models.firmware import (
        FirmwareDockerConfig,
        FirmwareFlashConfig,
        UserFirmwareConfig,
    )
    from glovebox.config.models.user import UserConfigData

    console = Console()

    def format_default_value(default_val: Any) -> str:
        """Format default value for display."""
        if isinstance(default_val, list):
            if not default_val:
                return "[]"
            return f"[{', '.join(str(v) for v in default_val)}]"
        elif isinstance(default_val, bool):
            return str(default_val).lower()
        elif isinstance(default_val, Path):
            return str(default_val)
        elif default_val is None:
            return "null"
        else:
            return str(default_val)

    def get_field_info(model_class: Any, prefix: str = "") -> list[dict[str, Any]]:
        """Extract field information from a Pydantic model."""
        fields = []
        for field_name, field_info in model_class.model_fields.items():
            full_name = f"{prefix}.{field_name}" if prefix else field_name

            # Get default value
            default_val = field_info.default
            if hasattr(field_info, "default_factory") and field_info.default_factory:
                try:
                    default_val = field_info.default_factory()
                except Exception:
                    default_val = f"<factory: {field_info.default_factory}>"

            # Get description
            description = field_info.description or "No description available"

            # Get type hint
            type_hint = str(field_info.annotation).replace("typing.", "")

            fields.append(
                {
                    "name": full_name,
                    "type": type_hint,
                    "default": format_default_value(default_val),
                    "description": description,
                    "category": prefix.split(".")[0] if "." in prefix else "core",
                }
            )

        return fields

    # Collect all configuration options
    all_options = []

    # Core options from UserConfigData
    all_options.extend(get_field_info(UserConfigData))

    # Firmware options
    all_options.extend(get_field_info(FirmwareFlashConfig, "firmware.flash"))
    all_options.extend(get_field_info(FirmwareDockerConfig, "firmware.docker"))

    # Filter by category if specified
    if category != "all":
        all_options = [
            opt
            for opt in all_options
            if opt["category"] == category or opt["name"].startswith(category)
        ]

    if format == "json":
        import json

        output = {
            "total_options": len(all_options),
            "categories": list({opt["category"] for opt in all_options}),
            "options": all_options,
        }
        print(json.dumps(output, indent=2))
        return

    elif format == "markdown":
        print("# Glovebox Configuration Options\n")

        # Group by category
        categories: dict[str, list[dict[str, Any]]] = {}
        for opt in all_options:
            cat = opt["category"]
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(opt)

        for cat_name, options in sorted(categories.items()):
            print(f"## {cat_name.title()} Options\n")
            for opt in sorted(options, key=lambda x: x["name"]):
                print(f"### `{opt['name']}`")
                print(f"- **Type**: `{opt['type']}`")
                print(f"- **Default**: `{opt['default']}`")
                print(f"- **Description**: {opt['description']}\n")
        return

    # Table format (default)
    table = Table(title=f"Available Configuration Options ({len(all_options)} total)")
    table.add_column("Setting", style="cyan", width=30)
    table.add_column("Type", style="yellow", width=20)
    table.add_column("Default", style="green", width=15)
    table.add_column("Description", style="white", width=40)

    # Sort options by name
    for opt in sorted(all_options, key=lambda x: x["name"]):
        # Truncate long descriptions
        desc = opt["description"]
        if len(desc) > 80:
            desc = desc[:77] + "..."

        table.add_row(opt["name"], opt["type"], opt["default"], desc)

    console.print(table)
    console.print(
        "\n[dim]Use 'glovebox config set <setting> <value>' to change settings[/dim]"
    )
    console.print("[dim]Use --category to filter by: core, firmware, cache[/dim]")


@config_app.command(name="list")
@handle_errors
def list_keyboards(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed information"
    ),
    format: str = typer.Option(
        "text", "--format", "-f", help="Output format (text, json)"
    ),
) -> None:
    """List available keyboard configurations."""
    # Get app context with user config
    app_ctx: AppContext = ctx.obj
    keyboards = get_available_keyboards(app_ctx.user_config)

    if not keyboards:
        print("No keyboards found")
        return

    if format.lower() == "json":
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

    # Text output
    if verbose:
        print(f"Available Keyboard Configurations ({len(keyboards)}):")
        print("-" * 60)

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
                version = (
                    "N/A"  # Version is not a top-level attribute in KeyboardConfig
                )

                print(f"• {keyboard_name}")
                print(f"  Description: {description}")
                print(f"  Vendor: {vendor}")
                print(f"  Version: {version}")
                print("")
            except Exception as e:
                print(f"• {keyboard_name}")
                print(f"  Error: {e}")
                print("")
    else:
        print(f"Available keyboard configurations ({len(keyboards)}):")
        for keyboard in keyboards:
            print_list_item(keyboard)


@config_app.command(name="show-keyboard")
@handle_errors
def show_keyboard(
    ctx: typer.Context,
    keyboard_name: str = typer.Argument(
        ..., help="Keyboard name to show", autocompletion=complete_keyboard_names
    ),
    format: str = typer.Option(
        "text", "--format", "-f", help="Output format (text, json, markdown, table)"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed configuration information"
    ),
) -> None:
    """Show details of a specific keyboard configuration."""
    from glovebox.cli.helpers.output_formatter import create_output_formatter

    # Get app context with user config
    app_ctx: AppContext = ctx.obj
    # Get the keyboard configuration
    keyboard_config = load_keyboard_config(keyboard_name, app_ctx.user_config)

    # Create output formatter
    formatter = create_output_formatter()

    # Build comprehensive configuration data
    config_data = _build_keyboard_config_data(keyboard_config, verbose)

    # Use the unified output formatter
    formatter.print_formatted(config_data, format)


@config_app.command(name="firmwares")
@handle_errors
def list_firmwares(
    ctx: typer.Context,
    keyboard_name: str = typer.Argument(
        ..., help="Keyboard name", autocompletion=complete_keyboard_names
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed information"
    ),
    format: str = typer.Option(
        "text", "--format", "-f", help="Output format (text, json)"
    ),
) -> None:
    """List available firmware configurations for a keyboard."""
    # Get app context with user config
    app_ctx: AppContext = ctx.obj
    # Get keyboard configuration
    keyboard_config = load_keyboard_config(keyboard_name, app_ctx.user_config)

    # Get firmwares from keyboard config
    firmwares = keyboard_config.firmwares

    if not firmwares:
        print(f"No firmwares found for {keyboard_name}")
        return

    if format.lower() == "json":
        # JSON output
        output: dict[str, Any] = {"keyboard": keyboard_name, "firmwares": []}

        for firmware_name, firmware_config in firmwares.items():
            if verbose:
                output["firmwares"].append(
                    {
                        "name": firmware_name,
                        "config": firmware_config.model_dump(
                            mode="json", by_alias=True
                        ),
                    }
                )
            else:
                output["firmwares"].append({"name": firmware_name})

        print(json.dumps(output, indent=2))
        return

    # Text output
    if verbose:
        print(f"Available Firmware Versions for {keyboard_name} ({len(firmwares)}):")
        print("-" * 60)

        for firmware_name, firmware in firmwares.items():
            version = firmware.version
            description = firmware.description

            print(f"• {firmware_name}")
            print(f"  Version: {version}")
            print(f"  Description: {description}")

            # Show build options if available
            build_options = firmware.build_options
            if build_options:
                print("  Build Options:")
                print(f"    repository: {build_options.repository}")
                print(f"    branch: {build_options.branch}")

            print("")
    else:
        print(f"Found {len(firmwares)} firmware(s) for {keyboard_name}:")
        for firmware_name in firmwares:
            print_list_item(firmware_name)


@config_app.command(name="firmware")
@handle_errors
def show_firmware(
    ctx: typer.Context,
    keyboard_name: str = typer.Argument(
        ..., help="Keyboard name", autocompletion=complete_keyboard_names
    ),
    firmware_name: str = typer.Argument(
        ..., help="Firmware name to show", autocompletion=complete_firmware_names
    ),
    format: str = typer.Option(
        "text", "--format", "-f", help="Output format (text, json)"
    ),
) -> None:
    """Show details of a specific firmware configuration."""
    # Get app context with user config
    app_ctx: AppContext = ctx.obj
    # Get keyboard configuration
    keyboard_config = load_keyboard_config(keyboard_name, app_ctx.user_config)

    # Get firmware configuration
    firmwares = keyboard_config.firmwares
    if firmware_name not in firmwares:
        print_error_message(f"Firmware {firmware_name} not found for {keyboard_name}")
        print("Available firmwares:")
        for name in firmwares:
            print_list_item(name)
        raise typer.Exit(1)

    firmware_config = firmwares[firmware_name]

    if format.lower() == "json":
        # JSON output
        output = {
            "keyboard": keyboard_name,
            "firmware": firmware_name,
            "config": firmware_config.model_dump(mode="json", by_alias=True),
        }
        print(json.dumps(output, indent=2))
        return

    # Text output
    print(f"Firmware: {firmware_name} for {keyboard_name}")
    print("-" * 60)

    # Display basic information
    version = firmware_config.version
    description = firmware_config.description

    print(f"Version: {version}")
    print(f"Description: {description}")

    # Display build options
    build_options = firmware_config.build_options
    if build_options:
        print("\nBuild Options:")
        print(f"  repository: {build_options.repository}")
        print(f"  branch: {build_options.branch}")

    # Display kconfig options
    kconfig = (
        firmware_config.kconfig
        if hasattr(firmware_config, "kconfig") and firmware_config.kconfig is not None
        else {}
    )
    if kconfig:
        print("\nKconfig Options:")
        for _key, config in kconfig.items():
            # config is always a KConfigOption instance
            name = config.name
            type_str = config.type
            default = config.default
            description = config.description

            print(f"  • {name} ({type_str})")
            print(f"    Default: {default}")
            if description:
                print(f"    Description: {description}")


@config_app.command(name="check-updates")
@handle_errors
def check_updates(
    ctx: typer.Context,
    force: bool = typer.Option(
        False, "--force", "-f", help="Force check even if recently checked"
    ),
    include_prereleases: bool = typer.Option(
        False, "--include-prereleases", help="Include pre-release versions"
    ),
) -> None:
    """Check for ZMK firmware updates."""
    from glovebox.core.version_check import create_zmk_version_checker

    version_checker = create_zmk_version_checker()
    result = version_checker.check_for_updates(
        force=force, include_prereleases=include_prereleases
    )

    if result.check_disabled and not force:
        from glovebox.cli.app import AppContext
        from glovebox.cli.helpers.theme import Icons

        app_ctx: AppContext = ctx.obj
        use_emoji = app_ctx.use_emoji
        print(
            Icons.format_with_icon("WARNING", "Version checks are disabled", use_emoji)
        )
        print("   To enable: glovebox config set disable_version_checks false")
        return

    if result.has_update and result.latest_version:
        from glovebox.cli.app import AppContext
        from glovebox.cli.helpers.theme import Icons

        app_context: AppContext = ctx.obj
        use_emoji = app_context.use_emoji
        print(
            Icons.format_with_icon(
                "LOADING", "ZMK Firmware Update Available!", use_emoji
            )
        )
        print(f"   Current: {result.current_version or 'unknown'}")
        print(f"   Latest:  {result.latest_version}")
        if result.is_prerelease:
            print("   Type:    Pre-release")
        if result.latest_url:
            print(f"   Details: {result.latest_url}")
    else:
        from glovebox.cli.app import AppContext
        from glovebox.cli.helpers.theme import Icons

        app_ctx2: AppContext = ctx.obj
        use_emoji = app_ctx2.use_emoji
        print(
            Icons.format_with_icon("SUCCESS", "ZMK firmware is up to date", use_emoji)
        )

    if result.last_check:
        print(f"   Last checked: {result.last_check.strftime('%Y-%m-%d %H:%M:%S')}")


@config_app.command(name="disable-updates")
@handle_errors
def disable_updates(ctx: typer.Context) -> None:
    """Disable automatic ZMK version checks."""
    from glovebox.core.version_check import create_zmk_version_checker

    version_checker = create_zmk_version_checker()
    version_checker.disable_version_checks()
    print_success_message("ZMK version checks disabled")


@config_app.command(name="enable-updates")
@handle_errors
def enable_updates(ctx: typer.Context) -> None:
    """Enable automatic ZMK version checks."""
    from glovebox.core.version_check import create_zmk_version_checker

    version_checker = create_zmk_version_checker()
    version_checker.enable_version_checks()
    print_success_message("ZMK version checks enabled")


@config_app.command(name="export")
@handle_errors
def export_config(
    ctx: typer.Context,
    output_file: str = typer.Option(
        "glovebox-config.yaml", "--output", "-o", help="Output file path"
    ),
    format: str = typer.Option(
        "yaml", "--format", "-f", help="Output format (yaml, json, toml)"
    ),
    include_defaults: bool = typer.Option(
        True, "--include-defaults/--no-defaults", help="Include default values"
    ),
    include_descriptions: bool = typer.Option(
        True,
        "--include-descriptions/--no-descriptions",
        help="Include field descriptions as comments",
    ),
) -> None:
    """Export all configuration options to a file with current values."""
    from pathlib import Path

    from glovebox.cli.app import AppContext as AppCtx
    from glovebox.config.models.firmware import (
        FirmwareDockerConfig,
        FirmwareFlashConfig,
    )
    from glovebox.config.models.user import UserConfigData

    # Get app context with user config
    app_ctx: AppCtx = ctx.obj
    output_path = Path(output_file)

    def get_current_value(key: str) -> Any:
        """Get current configuration value, handling nested keys."""
        try:
            if "." in key:
                # Handle nested keys like firmware.flash.timeout
                parts = key.split(".")
                if len(parts) == 3 and parts[0] in ["firmware", "compilation"]:
                    # Get the nested object
                    parent_obj = app_ctx.user_config.get(parts[0])
                    if hasattr(parent_obj, parts[1]):
                        nested_obj = getattr(parent_obj, parts[1])
                        if hasattr(nested_obj, parts[2]):
                            return getattr(nested_obj, parts[2])
                return None
            else:
                return app_ctx.user_config.get(key)
        except Exception:
            return None

    def get_field_info_with_values(
        model_class: Any, prefix: str = ""
    ) -> dict[str, Any]:
        """Extract field information with current values from a Pydantic model."""
        config_data = {}

        for field_name, field_info in model_class.model_fields.items():
            full_name = f"{prefix}.{field_name}" if prefix else field_name

            # Get current value
            current_value = get_current_value(full_name)

            # Get default value for comparison
            default_val = field_info.default
            if hasattr(field_info, "default_factory") and field_info.default_factory:
                try:
                    default_val = field_info.default_factory()
                except Exception:
                    default_val = None

            # Decide whether to include this field
            if include_defaults or current_value != default_val:
                # Convert Path objects to strings for serialization
                if isinstance(current_value, Path):
                    current_value = str(current_value)
                elif isinstance(current_value, list):
                    current_value = [
                        str(item) if isinstance(item, Path) else item
                        for item in current_value
                    ]

                config_data[field_name] = current_value

        return config_data

    # Build complete configuration structure
    config_export = {}

    # Add core configuration
    core_fields = get_field_info_with_values(UserConfigData)
    for key, value in core_fields.items():
        if key not in ["firmware"]:  # Handle firmware separately
            config_export[key] = value

    # Add firmware configuration
    firmware_config = {}
    firmware_config["flash"] = get_field_info_with_values(
        FirmwareFlashConfig, "firmware.flash"
    )
    firmware_config["docker"] = get_field_info_with_values(
        FirmwareDockerConfig, "firmware.docker"
    )
    config_export["firmware"] = firmware_config

    # Add metadata
    metadata = {
        "generated_at": datetime.now().isoformat(),
        "glovebox_version": "unknown",  # Could be enhanced to get actual version
        "export_format": format,
        "include_defaults": include_defaults,
    }
    config_export["_metadata"] = metadata

    try:
        # Write the configuration file
        if format.lower() == "yaml":
            import yaml

            yaml_content = ""
            if include_descriptions:
                yaml_content += "# Glovebox Configuration Export\n"
                yaml_content += f"# Generated at: {metadata['generated_at']}\n"
                yaml_content += f"# Include defaults: {include_defaults}\n\n"

            yaml_content += yaml.dump(
                config_export,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
                indent=2,
            )

            output_path.write_text(yaml_content, encoding="utf-8")

        elif format.lower() == "json":
            import json

            output_path.write_text(
                json.dumps(config_export, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        elif format.lower() == "toml":
            import tomlkit

            def filter_none_values(data: Any) -> Any:
                """Recursively filter out None values for TOML compatibility."""
                if isinstance(data, dict):
                    return {
                        k: filter_none_values(v)
                        for k, v in data.items()
                        if v is not None
                    }
                elif isinstance(data, list):
                    return [
                        filter_none_values(item) for item in data if item is not None
                    ]
                else:
                    return data

            # Filter None values from config_export for TOML compatibility
            filtered_config = filter_none_values(config_export)
            toml_content = tomlkit.dumps(filtered_config)
            output_path.write_text(toml_content, encoding="utf-8")

        else:
            print_error_message(
                f"Unsupported format: {format}. Use yaml, json, or toml."
            )
            raise typer.Exit(1)

        # Success message
        total_options = sum(
            len(section) if isinstance(section, dict) else 1
            for key, section in config_export.items()
            if not key.startswith("_")
        )

        print_success_message(f"Configuration exported to {output_path}")
        from glovebox.cli.app import AppContext
        from glovebox.cli.helpers.theme import Icons

        app_context: AppContext = ctx.obj
        use_emoji = app_context.use_emoji
        print(f"{Icons.get_icon('CONFIG', use_emoji)} Format: {format.upper()}")
        print(
            f"{Icons.get_icon('CONFIG', use_emoji)} Options exported: {total_options}"
        )
        print(
            f"{Icons.get_icon('INFO', use_emoji)} Include defaults: {include_defaults}"
        )

        if include_descriptions and format.lower() == "yaml":
            print(
                Icons.format_with_icon(
                    "INFO", "Descriptions included as comments", use_emoji
                )
            )
        elif format.lower() == "toml":
            print(Icons.format_with_icon("INFO", "TOML format exported", use_emoji))

    except Exception as e:
        print_error_message(f"Failed to export configuration: {e}")
        raise typer.Exit(1) from e


@config_app.command(name="add")
@handle_errors
def add_to_list(
    ctx: typer.Context,
    key: Annotated[
        str,
        typer.Argument(
            help="Configuration list key to add to",
            autocompletion=complete_config_list_keys,
        ),
    ],
    value: Annotated[str, typer.Argument(help="Value to add to the list")],
    save: Annotated[
        bool, typer.Option("--save", help="Save configuration to file")
    ] = True,
) -> None:
    """Add a value to a configuration list."""
    # Get app context with user config
    app_ctx: AppContext = ctx.obj

    # Check if key exists and is a list
    def get_field_type_for_key(config_key: str) -> type:
        """Get the expected type for a configuration key."""
        from glovebox.config.models.firmware import (
            FirmwareDockerConfig,
            FirmwareFlashConfig,
        )
        from glovebox.config.models.user import UserConfigData

        if "." in config_key:
            parts = config_key.split(".")
            if len(parts) == 3 and parts[0] == "firmware":
                if parts[1] == "flash":
                    field_info = FirmwareFlashConfig.model_fields.get(parts[2])
                elif parts[1] == "docker":
                    field_info = FirmwareDockerConfig.model_fields.get(parts[2])
                else:
                    return str
            else:
                return str
        else:
            field_info = UserConfigData.model_fields.get(config_key)

        if field_info and hasattr(field_info, "annotation") and field_info.annotation:
            annotation = field_info.annotation
            if hasattr(annotation, "__origin__") and annotation.__origin__ is list:
                return list
            else:
                return annotation
        return str

    field_type = get_field_type_for_key(key)

    if field_type is not list:
        print_error_message(f"Configuration key '{key}' is not a list")
        raise typer.Exit(1)

    # Get current list value
    current_list = app_ctx.user_config.get(key, [])
    if not isinstance(current_list, list):
        current_list = []

    # Convert value to appropriate type if needed
    typed_value: Any = value
    if key.endswith("_paths") or key == "keyboard_paths":
        typed_value = Path(value)

    # Check if value already exists
    if typed_value in current_list:
        print_error_message(f"Value '{value}' already exists in {key}")
        raise typer.Exit(1)

    # Add the value to the list
    current_list.append(typed_value)
    app_ctx.user_config.set(key, current_list)
    print_success_message(f"Added '{value}' to {key}")

    # Save configuration if requested
    if save:
        app_ctx.user_config.save()
        print_success_message("Configuration saved")


@config_app.command(name="remove")
@handle_errors
def remove_from_list(
    ctx: typer.Context,
    key: Annotated[
        str,
        typer.Argument(
            help="Configuration list key to remove from",
            autocompletion=complete_config_list_keys,
        ),
    ],
    value: Annotated[str, typer.Argument(help="Value to remove from the list")],
    save: Annotated[
        bool, typer.Option("--save", help="Save configuration to file")
    ] = True,
) -> None:
    """Remove a value from a configuration list."""
    # Get app context with user config
    app_ctx: AppContext = ctx.obj

    # Check if key exists and is a list
    def get_field_type_for_key(config_key: str) -> type:
        """Get the expected type for a configuration key."""
        from glovebox.config.models.firmware import (
            FirmwareDockerConfig,
            FirmwareFlashConfig,
        )
        from glovebox.config.models.user import UserConfigData

        if "." in config_key:
            parts = config_key.split(".")
            if len(parts) == 3 and parts[0] == "firmware":
                if parts[1] == "flash":
                    field_info = FirmwareFlashConfig.model_fields.get(parts[2])
                elif parts[1] == "docker":
                    field_info = FirmwareDockerConfig.model_fields.get(parts[2])
                else:
                    return str
            else:
                return str
        else:
            field_info = UserConfigData.model_fields.get(config_key)

        if field_info and hasattr(field_info, "annotation") and field_info.annotation:
            annotation = field_info.annotation
            if hasattr(annotation, "__origin__") and annotation.__origin__ is list:
                return list
            else:
                return annotation
        return str

    field_type = get_field_type_for_key(key)

    if field_type is not list:
        print_error_message(f"Configuration key '{key}' is not a list")
        raise typer.Exit(1)

    # Get current list value
    current_list = app_ctx.user_config.get(key, [])
    if not isinstance(current_list, list):
        print_error_message(f"Configuration key '{key}' is not a list")
        raise typer.Exit(1)

    # Convert value to appropriate type if needed
    typed_value: Any = value
    if key.endswith("_paths") or key == "keyboard_paths":
        typed_value = Path(value)

    # Check if value exists in list
    if typed_value not in current_list:
        print_error_message(f"Value '{value}' not found in {key}")
        raise typer.Exit(1)

    # Remove the value from the list
    current_list.remove(typed_value)
    app_ctx.user_config.set(key, current_list)
    print_success_message(f"Removed '{value}' from {key}")

    # Save configuration if requested
    if save:
        app_ctx.user_config.save()
        print_success_message("Configuration saved")


@config_app.command(name="import")
@handle_errors
def import_config(
    ctx: typer.Context,
    config_file: str = typer.Argument(..., help="Configuration file to import"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be imported without making changes"
    ),
    backup: bool = typer.Option(
        True,
        "--backup/--no-backup",
        help="Create backup of current config before importing",
    ),
    force: bool = typer.Option(
        False, "--force", help="Import without confirmation prompts"
    ),
) -> None:
    """Import configuration from a YAML, JSON, or TOML file."""
    from pathlib import Path

    from glovebox.cli.app import AppContext as AppCtx
    from glovebox.cli.helpers.theme import Icons

    # Get app context with user config
    app_ctx: AppCtx = ctx.obj
    use_emoji = app_ctx.use_emoji
    config_path = Path(config_file)

    if not config_path.exists():
        print_error_message(f"Configuration file not found: {config_path}")
        raise typer.Exit(1)

    # Determine format from file extension
    suffix = config_path.suffix.lower()
    if suffix in [".yaml", ".yml"]:
        file_format = "yaml"
    elif suffix == ".json":
        file_format = "json"
    elif suffix == ".toml":
        file_format = "toml"
    else:
        print_error_message(
            f"Unsupported file format: {suffix}. Use .yaml, .json, or .toml"
        )
        raise typer.Exit(1)

    try:
        # Load configuration file
        config_content = config_path.read_text(encoding="utf-8")

        if file_format == "yaml":
            import yaml

            config_data = yaml.safe_load(config_content)
        elif file_format == "json":
            import json

            config_data = json.loads(config_content)
        elif file_format == "toml":
            import tomlkit

            config_data = tomlkit.loads(config_content)

        # Remove metadata section if present
        if "_metadata" in config_data:
            metadata = config_data.pop("_metadata")
            print(
                f"{Icons.get_icon('INFO', use_emoji)} Imported config generated at: {metadata.get('generated_at', 'unknown')}"
            )

        # Flatten the configuration for setting
        settings_to_apply = []

        def flatten_config(data: dict[str, Any], prefix: str = "") -> None:
            """Recursively flatten nested configuration."""
            for key, value in data.items():
                full_key = f"{prefix}.{key}" if prefix else key

                if isinstance(value, dict):
                    # Recurse into nested objects
                    flatten_config(value, full_key)
                else:
                    # This is a leaf value
                    settings_to_apply.append((full_key, value))

        flatten_config(config_data)

        if not settings_to_apply:
            print(
                Icons.format_with_icon(
                    "WARNING", "No configuration settings found to import", use_emoji
                )
            )
            return

        print(
            Icons.format_with_icon(
                "INFO",
                f"Found {len(settings_to_apply)} configuration settings to import",
                use_emoji,
            )
        )

        # Show what will be changed
        if dry_run:
            console = Console()
            table = Table(title="Configuration Changes (Dry Run)")
            table.add_column("Setting", style="cyan")
            table.add_column("Current Value", style="red")
            table.add_column("New Value", style="green")

            for key, new_value in settings_to_apply:
                current_value = app_ctx.user_config.get(key)
                table.add_row(key, str(current_value), str(new_value))

            console.print(table)
            print(
                Icons.format_with_icon(
                    "INFO", "Dry run complete - no changes made", use_emoji
                )
            )
            return

        # Confirm before applying changes
        if not force:
            confirm = typer.confirm(
                f"Apply {len(settings_to_apply)} configuration changes?"
            )
            if not confirm:
                print(Icons.format_with_icon("ERROR", "Import cancelled", use_emoji))
                return

        # Create backup if requested
        if backup:
            backup_file = f"glovebox-config-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.yaml"
            try:
                # Export current config as backup
                export_config(ctx, backup_file, "yaml", True, False)
                print(
                    f"{Icons.get_icon('SAVE', use_emoji)} Backup saved to: {backup_file}"
                )
            except Exception as e:
                print(
                    Icons.format_with_icon(
                        "WARNING", f"Failed to create backup: {e}", use_emoji
                    )
                )
                if not force:
                    confirm_continue = typer.confirm("Continue without backup?")
                    if not confirm_continue:
                        print(
                            Icons.format_with_icon(
                                "ERROR", "Import cancelled", use_emoji
                            )
                        )
                        return

        # Apply configuration changes
        successful_changes = 0
        failed_changes = []

        for key, value in settings_to_apply:
            try:
                # Convert string values to appropriate types
                if isinstance(value, str) and key.endswith(
                    ("_paths", "keyboard_paths")
                ):
                    # Handle path lists
                    value = [Path(p.strip()) for p in value.split(",") if p.strip()]

                app_ctx.user_config.set(key, value)
                successful_changes += 1
            except Exception as e:
                failed_changes.append((key, str(e)))

        # Save configuration
        try:
            app_ctx.user_config.save()
            print_success_message("Configuration imported successfully!")
            print(
                Icons.format_with_icon(
                    "SUCCESS", f"Applied: {successful_changes} settings", use_emoji
                )
            )

            if failed_changes:
                print(
                    Icons.format_with_icon(
                        "WARNING", f"Failed: {len(failed_changes)} settings", use_emoji
                    )
                )
                for key, error in failed_changes:
                    print(f"   {key}: {error}")
        except Exception as e:
            print_error_message(f"Failed to save configuration: {e}")
            raise typer.Exit(1) from e

    except Exception as e:
        print_error_message(f"Failed to import configuration: {e}")
        raise typer.Exit(1) from e


def register_commands(app: typer.Typer) -> None:
    """Register config commands with the main app.

    Args:
        app: The main Typer app
    """
    app.add_typer(config_app, name="config")
