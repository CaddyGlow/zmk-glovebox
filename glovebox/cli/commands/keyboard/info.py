"""Keyboard information commands (list, show)."""

import json
import logging
from typing import Annotated, Any

import typer

from glovebox.cli.app import AppContext
from glovebox.cli.decorators import handle_errors
from glovebox.cli.helpers import print_list_item, print_success_message
from glovebox.config.keyboard_profile import (
    get_available_keyboards,
    load_keyboard_config,
)


logger = logging.getLogger(__name__)


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
                "method_type": method.strategy,
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
            "primary_method": primary_compile.strategy,
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
