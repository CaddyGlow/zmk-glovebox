"""Configuration management commands (list, export, import)."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from glovebox.cli.decorators import handle_errors
from glovebox.cli.helpers import (
    print_error_message,
    print_success_message,
)
from glovebox.config.models.firmware import (
    FirmwareDockerConfig,
    FirmwareFlashConfig,
)
from glovebox.config.models.user import UserConfigData


logger = logging.getLogger(__name__)


@handle_errors
def list_config(
    ctx: typer.Context,
    show_sources: Annotated[
        bool, typer.Option("--sources", help="Show configuration sources")
    ] = False,
    show_defaults: Annotated[
        bool, typer.Option("--defaults", help="Show default values")
    ] = False,
    show_descriptions: Annotated[
        bool, typer.Option("--descriptions", help="Show field descriptions")
    ] = False,
) -> None:
    """Show configuration settings. By default shows effective values (current or default if unset)."""
    from glovebox.cli.app import AppContext

    # Get app context with user config
    app_ctx: AppContext = ctx.obj

    # Create a nice table display
    console = Console()
    table = Table(title="Glovebox Configuration")

    # Add columns based on what to show
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    if show_defaults:
        table.add_column("Default", style="blue")

    if show_sources:
        table.add_column("Source", style="yellow")

    if show_descriptions:
        table.add_column("Description", style="white")

    # Get all configuration keys from models
    def get_all_display_keys() -> list[str]:
        """Get all configuration keys for display."""
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

    def get_field_info(key: str) -> tuple[Any, str]:
        """Get default value and description for a configuration key."""
        default_val = None
        description = "No description available"

        if "." in key:
            parts = key.split(".")
            if len(parts) == 3 and parts[0] == "firmware":
                if parts[1] == "flash":
                    field_info = FirmwareFlashConfig.model_fields.get(parts[2])
                elif parts[1] == "docker":
                    field_info = FirmwareDockerConfig.model_fields.get(parts[2])
                else:
                    field_info = None
            else:
                field_info = None
        else:
            field_info = UserConfigData.model_fields.get(key)

        if field_info:
            default_val = field_info.default
            if (
                hasattr(field_info, "default_factory")
                and field_info.default_factory is not None
            ):
                try:
                    # Pydantic v2 factory functions may need special handling
                    default_val = field_info.default_factory()  # type: ignore
                except Exception:
                    default_val = f"<factory: {field_info.default_factory}>"
            description = field_info.description or "No description available"

        return default_val, description

    def format_value(value: Any) -> str:
        """Format a value for display."""
        if isinstance(value, list):
            if not value:
                return "(empty list)"
            else:
                return "\n".join(str(v) for v in value)
        elif value is None:
            return "null"
        else:
            return str(value)

    def get_effective_value(key: str, current_value: Any) -> tuple[str, bool]:
        """Get the effective value to display, returning (value_str, is_from_default)."""
        if current_value is not None:
            return format_value(current_value), False
        else:
            # Use default value if current is null/unset
            default_val, _ = get_field_info(key)
            return format_value(default_val), True

    # Add rows for each configuration setting
    for key in sorted(display_keys):
        current_value = app_ctx.user_config.get(key)

        if show_defaults:
            # Show both current and default in separate columns
            current_value_str = format_value(current_value)
            default_val, _ = get_field_info(key)
            default_str = format_value(default_val)
            row_data = [key, current_value_str, default_str]
        else:
            # Show effective value (current or default if null)
            effective_value_str, is_from_default = get_effective_value(
                key, current_value
            )
            row_data = [key, effective_value_str]

        if show_sources:
            if show_defaults:
                # When showing defaults column, always show actual source
                source = app_ctx.user_config.get_source(key)
            else:
                # When not showing defaults, show "default" for null values
                _, is_from_default = get_effective_value(key, current_value)
                if is_from_default:
                    source = "default"
                else:
                    source = app_ctx.user_config.get_source(key)
            row_data.append(source)

        if show_descriptions:
            _, description = get_field_info(key)
            # Truncate long descriptions
            if len(description) > 60:
                description = description[:57] + "..."
            row_data.append(description)

        table.add_row(*row_data)

    # Print the table
    console.print(table)

    # Show helpful usage information
    console.print(
        "\n[dim]By default shows effective values (current or default if unset)[/dim]"
    )
    console.print("\n[dim]Available options:[/dim]")
    console.print(
        "[dim]  --defaults      Show both current and default values in separate columns[/dim]"
    )
    console.print(
        "[dim]  --sources       Show configuration sources (shows 'default' for unset values)[/dim]"
    )
    console.print("[dim]  --descriptions  Show field descriptions[/dim]")
    console.print(
        "\n[dim]Use 'glovebox config edit --set <setting>=<value>' to change settings[/dim]"
    )
    console.print(
        "[dim]Use 'glovebox config edit --interactive' to edit configuration file directly[/dim]"
    )


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
    from glovebox.cli.app import AppContext

    # Get app context with user config
    app_ctx: AppContext = ctx.obj
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
                            value = getattr(nested_obj, parts[2])
                            # Convert Pydantic models to dict for serialization
                            if hasattr(value, "model_dump"):
                                return value.model_dump(mode="json")
                            return value
                return None
            else:
                value = app_ctx.user_config.get(key)
                # Convert Pydantic models to dict for serialization
                if hasattr(value, "model_dump"):
                    return value.model_dump(mode="json")
                return value
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
                # Convert complex objects for serialization
                if isinstance(current_value, Path):
                    current_value = str(current_value)
                elif isinstance(current_value, list):
                    current_value = [
                        str(item) if isinstance(item, Path) else item
                        for item in current_value
                    ]
                elif hasattr(current_value, "model_dump"):
                    # Handle Pydantic models
                    current_value = current_value.model_dump(mode="json")

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
        icon_mode = app_context.icon_mode
        print(f"{Icons.get_icon('CONFIG', icon_mode)} Format: {format.upper()}")
        print(
            f"{Icons.get_icon('CONFIG', icon_mode)} Options exported: {total_options}"
        )
        print(
            f"{Icons.get_icon('INFO', icon_mode)} Include defaults: {include_defaults}"
        )

        if include_descriptions and format.lower() == "yaml":
            print(
                Icons.format_with_icon(
                    "INFO", "Descriptions included as comments", icon_mode
                )
            )
        elif format.lower() == "toml":
            print(Icons.format_with_icon("INFO", "TOML format exported", icon_mode))

    except Exception as e:
        print_error_message(f"Failed to export configuration: {e}")
        raise typer.Exit(1) from e


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
    from glovebox.cli.app import AppContext
    from glovebox.cli.helpers.theme import Icons

    # Get app context with user config
    app_ctx: AppContext = ctx.obj
    icon_mode = app_ctx.icon_mode
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
            config_data = json.loads(config_content)
        elif file_format == "toml":
            import tomlkit

            config_data = tomlkit.loads(config_content)

        # Remove metadata section if present
        if "_metadata" in config_data:
            metadata = config_data.pop("_metadata")
            print(
                f"{Icons.get_icon('INFO', icon_mode)} Imported config generated at: {metadata.get('generated_at', 'unknown')}"
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
                    "WARNING", "No configuration settings found to import", icon_mode
                )
            )
            return

        print(
            Icons.format_with_icon(
                "INFO",
                f"Found {len(settings_to_apply)} configuration settings to import",
                icon_mode,
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
                    "INFO", "Dry run complete - no changes made", icon_mode
                )
            )
            return

        # Confirm before applying changes
        if not force:
            confirm = typer.confirm(
                f"Apply {len(settings_to_apply)} configuration changes?"
            )
            if not confirm:
                print(Icons.format_with_icon("ERROR", "Import cancelled", icon_mode))
                return

        # Create backup if requested
        if backup:
            # Create backup in config directory, not current working directory
            config_dir = (
                app_ctx.user_config.config_file_path.parent
                if app_ctx.user_config.config_file_path
                else Path.home() / ".glovebox"
            )
            backup_file = (
                config_dir
                / f"glovebox-config-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.yaml"
            )
            try:
                # Export current config as backup
                export_config(ctx, str(backup_file), "yaml", True, False)
                print(
                    f"{Icons.get_icon('SAVE', icon_mode)} Backup saved to: {backup_file}"
                )
            except Exception as e:
                print(
                    Icons.format_with_icon(
                        "WARNING", f"Failed to create backup: {e}", icon_mode
                    )
                )
                if not force:
                    confirm_continue = typer.confirm("Continue without backup?")
                    if not confirm_continue:
                        print(
                            Icons.format_with_icon(
                                "ERROR", "Import cancelled", icon_mode
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
                    "SUCCESS", f"Applied: {successful_changes} settings", icon_mode
                )
            )

            if failed_changes:
                print(
                    Icons.format_with_icon(
                        "WARNING", f"Failed: {len(failed_changes)} settings", icon_mode
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
