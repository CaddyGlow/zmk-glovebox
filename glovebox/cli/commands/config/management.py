"""Configuration management commands."""

import logging
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from glovebox.cli.app import AppContext
from glovebox.cli.decorators import handle_errors
from glovebox.cli.helpers import (
    print_error_message,
    print_success_message,
)
from glovebox.cli.helpers.parameters import GetConfigFieldOption
from glovebox.cli.helpers.theme import Colors, get_themed_console
from glovebox.config.models.firmware import (
    FirmwareDockerConfig,
    FirmwareFlashConfig,
)
from glovebox.config.models.user import UserConfigData


logger = logging.getLogger(__name__)


@handle_errors
def show_config(
    ctx: typer.Context,
    # Field operations (read-only, matching layout pattern) with tab completion
    get: GetConfigFieldOption = None,
    # Display options
    show_all: Annotated[
        bool,
        typer.Option(
            "--all",
            help="Show all possible configuration fields (default: only show configured values)",
        ),
    ] = False,
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
    """Show configuration settings with optional field operations.

    \b
    By default, shows only configuration fields that have been explicitly set.
    Use --all to see all possible configuration options.

    \b
    Examples:
    # Show only configured values
    glovebox config show
    # Show all possible configuration fields
    glovebox config show --all
    # Show with additional info
    glovebox config show --sources --defaults --descriptions
    # Get specific fields
    glovebox config show --get cache_strategy
    glovebox config show --get firmware.flash.timeout --get emoji_mode
    """
    from glovebox.cli.app import AppContext
    from glovebox.cli.commands.config.edit import ConfigEditor

    # Get app context with user config
    app_ctx: AppContext = ctx.obj

    # If specific fields requested, use ConfigEditor for consistent behavior
    if get:
        try:
            console = get_themed_console()
            editor = ConfigEditor(app_ctx.user_config)

            for field_path in get:
                try:
                    value = editor.get_field(field_path)
                    if isinstance(value, list):
                        if not value:
                            console.console.print(
                                f"[${Colors.FIELD_NAME}]{field_path}[/${Colors.FIELD_NAME}]: [${Colors.MUTED}](empty list)[/${Colors.MUTED}]"
                            )
                        else:
                            console.console.print(
                                f"[${Colors.FIELD_NAME}]{field_path}[/${Colors.FIELD_NAME}]:"
                            )
                            for item in value:
                                console.console.print(
                                    f"  [${Colors.MUTED}]-[/${Colors.MUTED}] {item}"
                                )
                    elif value is None:
                        console.console.print(
                            f"[${Colors.FIELD_NAME}]{field_path}[/${Colors.FIELD_NAME}]: [${Colors.MUTED}]null[/${Colors.MUTED}]"
                        )
                    else:
                        console.console.print(
                            f"[${Colors.FIELD_NAME}]{field_path}[/${Colors.FIELD_NAME}]: {value}"
                        )
                except Exception as e:
                    print_error_message(f"Cannot get field '{field_path}': {e}")
            return

        except Exception as e:
            print_error_message(f"Failed to read configuration: {e}")
            raise typer.Exit(1) from e

    # Default behavior: show configured values only (unless --all specified)
    _show_all_config(app_ctx, show_all, show_sources, show_defaults, show_descriptions)


def _show_all_config(
    app_ctx: "AppContext",
    show_all: bool,
    show_sources: bool,
    show_defaults: bool,
    show_descriptions: bool,
) -> None:
    """Show configuration settings in table format.

    Args:
        app_ctx: Application context
        show_all: If True, show all possible fields; if False, show only configured values
        show_sources: Show configuration sources
        show_defaults: Show default values
        show_descriptions: Show field descriptions
    """
    # Create a nice table display
    console = get_themed_console()
    title = "Glovebox Configuration" + (
        " (All Options)" if show_all else " (Configured Values)"
    )
    table = Table(title=title)

    # Add columns based on what to show
    table.add_column("Setting", style=Colors.FIELD_NAME)
    table.add_column("Value", style=Colors.FIELD_VALUE)

    if show_defaults:
        table.add_column("Default", style=Colors.INFO)

    if show_sources:
        table.add_column("Source", style=Colors.WARNING)

    if show_descriptions:
        table.add_column("Description", style=Colors.NORMAL)

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
        elif hasattr(value, "value"):
            # Handle enums by extracting their value
            return str(value.value)
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

    # Filter keys based on show_all flag
    if show_all:
        # Show all possible configuration keys
        keys_to_show = sorted(display_keys)
    else:
        # Show only keys that have been explicitly configured (not defaults)
        keys_to_show = []
        for key in sorted(display_keys):
            current_value = app_ctx.user_config.get(key)
            default_val, _ = get_field_info(key)

            # Include key if it has been explicitly set (different from default)
            if current_value is not None and current_value != default_val:
                keys_to_show.append(key)

    # Add rows for each configuration setting
    for key in keys_to_show:
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
    console.console.print(table)

    # Show helpful usage information based on current mode
    if show_all:
        console.console.print(
            "\n[${Colors.MUTED}]Showing all possible configuration fields (use without --all to see only configured values)[/${Colors.MUTED}]"
        )
    else:
        if not keys_to_show:
            console.console.print(
                "\n[${Colors.MUTED}]No configuration values are currently set (use --all to see all possible options)[/${Colors.MUTED}]"
            )
        else:
            console.console.print(
                f"\n[${Colors.MUTED}]Showing {len(keys_to_show)} configured value(s) (use --all to see all possible options)[/${Colors.MUTED}]"
            )

    console.console.print("\n[${Colors.MUTED}]Available options:[/${Colors.MUTED}]")
    console.console.print(
        "[${Colors.MUTED}]  --all           Show all possible configuration fields[/${Colors.MUTED}]"
    )
    console.console.print(
        "[${Colors.MUTED}]  --defaults      Show both current and default values in separate columns[/${Colors.MUTED}]"
    )
    console.console.print(
        "[${Colors.MUTED}]  --sources       Show configuration sources[/${Colors.MUTED}]"
    )
    console.console.print(
        "[${Colors.MUTED}]  --descriptions  Show field descriptions[/${Colors.MUTED}]"
    )
    console.console.print(
        "[${Colors.MUTED}]  --get <field>   Get specific field value using dot notation[/${Colors.MUTED}]"
    )
    console.console.print(
        "\n[${Colors.MUTED}]Use 'glovebox config edit --set <setting>=<value>' to change settings[/${Colors.MUTED}]"
    )
    console.console.print(
        "[${Colors.MUTED}]Use 'glovebox config edit --interactive' to edit configuration file directly[/${Colors.MUTED}]"
    )
