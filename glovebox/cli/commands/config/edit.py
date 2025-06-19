"""Unified configuration editing commands."""

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Annotated, Any

import typer

from glovebox.cli.app import AppContext
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


def complete_config_keys(incomplete: str) -> list[str]:
    """Tab completion for configuration keys."""
    try:

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


def _get_field_type_for_key(config_key: str) -> type:
    """Get the expected type for a configuration key."""
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


def _parse_key_value_pair(pair: str) -> tuple[str, str]:
    """Parse key=value string."""
    if "=" not in pair:
        raise ValueError(f"Invalid key=value format: {pair}")

    key, value = pair.split("=", 1)
    return key.strip(), value.strip()


def _convert_value(value: str, field_type: type) -> Any:
    """Convert string value to appropriate type."""
    try:
        if field_type is bool:
            return value.lower() in ("true", "yes", "1", "y")
        elif field_type is int:
            return int(value)
        elif field_type is list:
            return [item.strip() for item in value.split(",")]
        else:
            return value
    except ValueError as err:
        if field_type is int:
            raise ValueError(f"Invalid integer value: {value}") from err
        raise


@handle_errors
def edit(
    ctx: typer.Context,
    get: Annotated[
        list[str] | None,
        typer.Option(
            "--get",
            help="Get configuration values (can be used multiple times)",
            autocompletion=complete_config_keys,
        ),
    ] = None,
    set: Annotated[
        list[str] | None,
        typer.Option(
            "--set",
            help="Set configuration values as key=value (can be used multiple times)",
        ),
    ] = None,
    add: Annotated[
        list[str] | None,
        typer.Option(
            "--add",
            help="Add values to list configurations as key=value (can be used multiple times)",
        ),
    ] = None,
    remove: Annotated[
        list[str] | None,
        typer.Option(
            "--remove",
            help="Remove values from list configurations as key=value (can be used multiple times)",
        ),
    ] = None,
    clear: Annotated[
        list[str] | None,
        typer.Option(
            "--clear",
            help="Clear values (lists to empty, other fields to default/null) (can be used multiple times)",
            autocompletion=complete_config_keys,
        ),
    ] = None,
    save: Annotated[
        bool, typer.Option("--save/--no-save", help="Save configuration to file")
    ] = True,
    interactive: Annotated[
        bool,
        typer.Option(
            "--interactive",
            "-i",
            help="Open configuration file in editor for interactive editing",
        ),
    ] = False,
) -> None:
    """Unified configuration editing command.

    This command supports getting, setting, adding to, removing from, and clearing
    configuration values in a single operation. Multiple operations can be performed at once.

    Examples:
        # Get single value
        glovebox config edit --get keyboard.type

        # Get multiple values
        glovebox config edit --get keyboard.type --get firmware.flash.timeout

        # Set single value
        glovebox config edit --set keyboard.type=glove80

        # Set multiple values
        glovebox config edit --set keyboard.type=glove80 --set firmware.flash.timeout=30

        # Add to list
        glovebox config edit --add keyboard_paths=/new/path

        # Remove from list
        glovebox config edit --remove keyboard_paths=/old/path

        # Clear entire list
        glovebox config edit --clear keyboard_paths

        # Clear normal field to default/null
        glovebox config edit --clear cache_strategy

        # Combined operations
        glovebox config edit --set keyboard.type=glove80 --add keyboard_paths=/new/path --clear old_list --save

        # Interactive editing
        glovebox config edit --interactive
    """
    # Get app context with user config
    app_ctx: AppContext = ctx.obj

    # Handle interactive editing first (exclusive mode)
    if interactive:
        if any([get, set, add, remove, clear]):
            print_error_message(
                "Interactive mode (--interactive) cannot be combined with other operations"
            )
            raise typer.Exit(1)

        _handle_interactive_edit(app_ctx)
        return

    # Ensure at least one operation is specified for non-interactive mode
    if not any([get, set, add, remove, clear]):
        print_error_message(
            "At least one operation (--get, --set, --add, --remove, --clear, --interactive) must be specified"
        )
        raise typer.Exit(1)

    # Get all valid keys for validation
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

    valid_keys = get_all_config_keys()
    changes_made = False

    # Handle GET operations
    if get:
        for key in get:
            if key not in valid_keys:
                print_error_message(f"Unknown configuration key: {key}")
                continue

            value = app_ctx.user_config.get(key)
            if isinstance(value, list):
                if not value:
                    print(f"{key}: (empty list)")
                else:
                    print(f"{key}:")
                    for item in value:
                        print(f"  - {item}")
            else:
                print(f"{key}: {value}")

    # Handle SET operations
    if set:
        for pair in set:
            try:
                key, value = _parse_key_value_pair(pair)

                if key not in valid_keys:
                    print_error_message(f"Unknown configuration key: {key}")
                    continue

                field_type = _get_field_type_for_key(key)
                typed_value = _convert_value(value, field_type)

                app_ctx.user_config.set(key, typed_value)
                print_success_message(f"Set {key} = {typed_value}")
                changes_made = True

            except ValueError as e:
                print_error_message(str(e))
                continue

    # Handle ADD operations
    if add:
        for pair in add:
            try:
                key, value = _parse_key_value_pair(pair)

                if key not in valid_keys:
                    print_error_message(f"Unknown configuration key: {key}")
                    continue

                field_type = _get_field_type_for_key(key)
                if field_type is not list:
                    print_error_message(f"Configuration key '{key}' is not a list")
                    continue

                # Get current list value
                current_list = app_ctx.user_config.get(key, [])
                if not isinstance(current_list, list):
                    current_list = []

                # Convert value to appropriate type if needed
                add_typed_value: Any = value
                if key.endswith("_paths") or key == "keyboard_paths":
                    from pathlib import Path

                    add_typed_value = Path(value)

                # Check if value already exists
                if add_typed_value in current_list:
                    print_error_message(f"Value '{value}' already exists in {key}")
                    continue

                # Add the value to the list
                current_list.append(add_typed_value)
                app_ctx.user_config.set(key, current_list)
                print_success_message(f"Added '{value}' to {key}")
                changes_made = True

            except ValueError as e:
                print_error_message(str(e))
                continue

    # Handle REMOVE operations
    if remove:
        for pair in remove:
            try:
                key, value = _parse_key_value_pair(pair)

                if key not in valid_keys:
                    print_error_message(f"Unknown configuration key: {key}")
                    continue

                field_type = _get_field_type_for_key(key)
                if field_type is not list:
                    print_error_message(f"Configuration key '{key}' is not a list")
                    continue

                # Get current list value
                current_list = app_ctx.user_config.get(key, [])
                if not isinstance(current_list, list):
                    print_error_message(f"Configuration key '{key}' is not a list")
                    continue

                # Convert value to appropriate type if needed
                remove_typed_value: Any = value
                if key.endswith("_paths") or key == "keyboard_paths":
                    from pathlib import Path

                    remove_typed_value = Path(value)

                # Check if value exists in list
                if remove_typed_value not in current_list:
                    print_error_message(f"Value '{value}' not found in {key}")
                    continue

                # Remove the value from the list
                current_list.remove(remove_typed_value)
                app_ctx.user_config.set(key, current_list)
                print_success_message(f"Removed '{value}' from {key}")
                changes_made = True

            except ValueError as e:
                print_error_message(str(e))
                continue

    # Handle CLEAR operations
    if clear:
        for key in clear:
            try:
                if key not in valid_keys:
                    print_error_message(f"Unknown configuration key: {key}")
                    continue

                field_type = _get_field_type_for_key(key)

                if field_type is list:
                    # Handle list fields - clear to empty list
                    current_list = app_ctx.user_config.get(key, [])
                    if not isinstance(current_list, list):
                        print_error_message(f"Configuration key '{key}' is not a list")
                        continue

                    # Check if list is already empty
                    if not current_list:
                        print_success_message(f"List '{key}' is already empty")
                        continue

                    # Clear the entire list
                    app_ctx.user_config.set(key, [])
                    print_success_message(f"Cleared all values from {key}")
                    changes_made = True
                else:
                    # Handle non-list fields - set to default value or None
                    default_val, _ = get_field_info(key)

                    # Get current value to check if already at default
                    current_value = app_ctx.user_config.get(key)

                    if current_value == default_val:
                        print_success_message(
                            f"Field '{key}' is already at default value"
                        )
                        continue

                    # Set to default value
                    app_ctx.user_config.set(key, default_val)
                    if default_val is None:
                        print_success_message(f"Cleared {key} (set to null)")
                    else:
                        print_success_message(
                            f"Cleared {key} (set to default: {default_val})"
                        )
                    changes_made = True

            except ValueError as e:
                print_error_message(str(e))
                continue

    # Save configuration if requested and changes were made
    if save and changes_made:
        app_ctx.user_config.save()
        print_success_message("Configuration saved")


def _handle_interactive_edit(app_ctx: AppContext) -> None:
    """Handle interactive editing of the configuration file."""
    # Get the editor from user config or environment
    editor = app_ctx.user_config.get("editor")
    if not editor:
        editor = os.environ.get("EDITOR", "nano")

    # Get the config file path
    config_file_path = app_ctx.user_config.config_file_path

    if not config_file_path or not config_file_path.exists():
        print_error_message("Configuration file not found. Creating a new one...")
        # Create the config file if it doesn't exist
        app_ctx.user_config.save()
        if not config_file_path:
            print_error_message("Failed to determine config file path")
            raise typer.Exit(1)

    # Get the file modification time before editing
    original_mtime = (
        config_file_path.stat().st_mtime if config_file_path.exists() else 0
    )

    try:
        # Open the config file in the editor
        print_success_message(f"Opening {config_file_path} in {editor}...")
        result = subprocess.run([editor, str(config_file_path)], check=True)

        # Check if the file was modified
        if config_file_path.exists():
            new_mtime = config_file_path.stat().st_mtime
            if new_mtime > original_mtime:
                print_success_message("Configuration file modified")

                # Try to reload the configuration to validate it
                try:
                    app_ctx.user_config.reload()
                    print_success_message("Configuration reloaded successfully")
                except Exception as e:
                    print_error_message(
                        f"Configuration file has validation errors: {e}"
                    )

                    # Ask if user wants to re-edit
                    if typer.confirm(
                        "Would you like to edit the file again to fix the errors?"
                    ):
                        _handle_interactive_edit(app_ctx)
                    else:
                        print_error_message(
                            "Configuration changes were not applied due to validation errors"
                        )
                        raise typer.Exit(1) from e
            else:
                print_success_message("No changes made to configuration file")
        else:
            print_error_message("Configuration file was deleted during editing")
            raise typer.Exit(1)

    except subprocess.CalledProcessError as e:
        print_error_message(f"Editor exited with error code {e.returncode}")
        raise typer.Exit(1) from e
    except FileNotFoundError as e:
        print_error_message(
            f"Editor '{editor}' not found. Please check your editor configuration."
        )
        print_error_message(
            "You can set the editor with: glovebox config edit --set editor=your_editor"
        )
        raise typer.Exit(1) from e
    except KeyboardInterrupt as e:
        print_error_message("Interactive editing cancelled")
        raise typer.Exit(1) from e
