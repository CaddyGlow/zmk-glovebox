"""Unified configuration editing commands."""

import json
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
from glovebox.cli.helpers.parameters import (
    AppendConfigFieldOption,
    GetConfigFieldOption,
    MergeConfigFieldOption,
    SetConfigFieldOption,
    UnsetConfigFieldOption,
)
from glovebox.config.models.firmware import (
    FirmwareDockerConfig,
    FirmwareFlashConfig,
)
from glovebox.config.models.user import UserConfigData


logger = logging.getLogger(__name__)


class ConfigEditor:
    """Atomic configuration editor that performs all operations in memory."""

    def __init__(self, user_config: Any):
        """Initialize editor with user configuration.

        Args:
            user_config: The user configuration instance to edit
        """
        self.user_config = user_config
        self.operations_log: list[str] = []
        self.errors: list[str] = []

    def get_field(self, field_path: str) -> Any:
        """Get field value.

        Args:
            field_path: Dot notation path to field

        Returns:
            Field value

        Raises:
            ValueError: If field not found
        """
        try:
            return self.user_config.get(field_path)
        except Exception as e:
            raise ValueError(f"Cannot get field '{field_path}': {e}") from e

    def set_field(self, field_path: str, value: Any) -> None:
        """Set field value.

        Args:
            field_path: Dot notation path to field
            value: Value to set

        Raises:
            ValueError: If field cannot be set
        """
        try:
            self.user_config.set(field_path, value)
            self.operations_log.append(f"Set {field_path} = {value}")
        except Exception as e:
            raise ValueError(f"Cannot set field '{field_path}': {e}") from e

    def unset_field(self, field_path: str) -> None:
        """Remove field or set to default value.

        Args:
            field_path: Dot notation path to field

        Raises:
            ValueError: If field cannot be unset
        """
        try:
            # Get default value for the field
            default_val, _ = get_field_info(field_path)

            # Check if current value is a list to determine how to unset
            current_value = self.user_config.get(field_path)
            if isinstance(current_value, list):
                self.user_config.set(field_path, [])
                self.operations_log.append(f"Unset {field_path} (cleared list)")
            else:
                # For other fields, set to default value
                self.user_config.set(field_path, default_val)
                if default_val is None:
                    self.operations_log.append(f"Unset {field_path} (set to null)")
                else:
                    self.operations_log.append(
                        f"Unset {field_path} (set to default: {default_val})"
                    )
        except Exception as e:
            raise ValueError(f"Cannot unset field '{field_path}': {e}") from e

    def merge_field(self, field_path: str, merge_data: dict[str, Any]) -> None:
        """Merge dictionary into field.

        Args:
            field_path: Dot notation path to field
            merge_data: Dictionary to merge

        Raises:
            ValueError: If merge fails
        """
        try:
            current = self.get_field(field_path)
            if not isinstance(current, dict):
                raise ValueError(f"Field '{field_path}' is not a dictionary")

            merged = deep_merge_dicts(current, merge_data)
            self.set_field(field_path, merged)
            self.operations_log[-1] = f"Merged into {field_path}"
        except Exception as e:
            raise ValueError(f"Cannot merge into field '{field_path}': {e}") from e

    def append_field(self, field_path: str, value: Any) -> None:
        """Append value to array field.

        Args:
            field_path: Dot notation path to field
            value: Value to append

        Raises:
            ValueError: If append fails
        """
        try:
            current = self.get_field(field_path)
            if current is None:
                current = []
            if not isinstance(current, list):
                raise ValueError(f"Field '{field_path}' is not an array")

            # Convert value if needed for path fields
            append_value = value
            if field_path.endswith("_paths") or field_path == "keyboard_paths":
                append_value = Path(value) if not isinstance(value, Path) else value

            # Check if value already exists
            if append_value in current:
                raise ValueError(f"Value '{value}' already exists in {field_path}")

            if isinstance(value, list):
                current.extend(value)
            else:
                current.append(append_value)

            self.user_config.set(field_path, current)
            self.operations_log.append(f"Appended to {field_path}")
        except Exception as e:
            raise ValueError(f"Cannot append to field '{field_path}': {e}") from e


def deep_merge_dicts(dict1: dict[str, Any], dict2: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries."""
    result = dict1.copy()
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


def parse_value(value_str: str) -> Any:
    """Parse value string into appropriate type."""
    # Handle from: syntax for imports
    if value_str.startswith("from:"):
        return ("import", value_str[5:])

    # Try JSON parsing for complex types
    if value_str.startswith(("{", "[", '"')):
        try:
            return json.loads(value_str)
        except json.JSONDecodeError:
            pass

    # Boolean values
    if value_str.lower() in ("true", "false"):
        return value_str.lower() == "true"

    # Numeric values
    if value_str.isdigit() or (value_str.startswith("-") and value_str[1:].isdigit()):
        return int(value_str)

    try:
        return float(value_str)
    except ValueError:
        pass

    # Default to string
    return value_str


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


@handle_errors
def edit(
    ctx: typer.Context,
    # Field operations (matching layout pattern) with tab completion
    get: GetConfigFieldOption = None,
    set: SetConfigFieldOption = None,
    unset: UnsetConfigFieldOption = None,
    merge: MergeConfigFieldOption = None,
    append: AppendConfigFieldOption = None,
    # Output options
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
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be done without saving"),
    ] = False,
) -> None:
    """Edit configuration with atomic operations.

    All operations are performed and saved atomically. Use --dry-run to preview changes.

    \b
    Examples:
        # Get field values
        glovebox config edit --get cache_strategy --get firmware.flash.timeout
        # Set fields
        glovebox config edit --set cache_strategy=docker --set emoji_mode=true
        # Append to arrays
        glovebox config edit --append keyboard_paths=/new/path
        # Unset fields (reset to default)
        glovebox config edit --unset firmware.flash.timeout
        # Merge dictionaries
        glovebox config edit --merge firmware.docker='{"memory_limit": "2GB"}'
        # Combined operations
        glovebox config edit --set cache_strategy=docker --append keyboard_paths=/new --save
        # Preview without saving
        glovebox config edit --set emoji_mode=true --dry-run
        # Interactive editing
        glovebox config edit --interactive
    """
    # Get app context with user config
    app_ctx: AppContext = ctx.obj

    # Handle interactive editing first (exclusive mode)
    if interactive:
        if any([get, set, unset, merge, append]):
            print_error_message(
                "Interactive mode (--interactive) cannot be combined with other operations"
            )
            raise typer.Exit(1)

        _handle_interactive_edit(app_ctx)
        return

    # Check if only read operations are requested
    has_writes = any([set, unset, merge, append])

    if not has_writes and not get:
        print_error_message(
            "At least one operation (--get, --set, --unset, --merge, --append, --interactive) must be specified"
        )
        raise typer.Exit(1)

    if not has_writes:
        # Handle read-only operations
        try:
            editor = ConfigEditor(app_ctx.user_config)

            # Execute read operations
            if get:
                for field_path in get:
                    try:
                        value = editor.get_field(field_path)
                        if isinstance(value, list):
                            if not value:
                                print(f"{field_path}: (empty list)")
                            else:
                                print(f"{field_path}:")
                                for item in value:
                                    print(f"  - {item}")
                        elif value is None:
                            print(f"{field_path}: null")
                        else:
                            print(f"{field_path}: {value}")
                    except Exception as e:
                        print_error_message(f"Cannot get field '{field_path}': {e}")
            return

        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error("Failed to read configuration: %s", e, exc_info=exc_info)
            print_error_message(f"Failed to read configuration: {e}")
            raise typer.Exit(1) from e

    # Handle write operations
    try:
        editor = ConfigEditor(app_ctx.user_config)

        # Parse operations
        operations: list[tuple[str, str, str | None]] = []

        if get:
            for field_path in get:
                operations.append(("get", field_path, None))

        if set:
            for op in set:
                if "=" not in op:
                    raise ValueError(f"Invalid set syntax: {op} (use key=value)")
                field_path, value_str = op.split("=", 1)
                operations.append(("set", field_path, value_str))

        if unset:
            for field_path in unset:
                operations.append(("unset", field_path, None))

        if merge:
            for op in merge:
                if "=" not in op:
                    raise ValueError(f"Invalid merge syntax: {op} (use key=value)")
                field_path, value_str = op.split("=", 1)
                operations.append(("merge", field_path, value_str))

        if append:
            for op in append:
                if "=" not in op:
                    raise ValueError(f"Invalid append syntax: {op} (use key=value)")
                field_path, value_str = op.split("=", 1)
                operations.append(("append", field_path, value_str))

        # Execute operations atomically
        results = {}

        for operation, field_path, value_str in operations:  # type: ignore
            try:
                if operation == "get":
                    value = editor.get_field(field_path)
                    results[f"get:{field_path}"] = value

                elif operation == "set":
                    if value_str is None:
                        raise ValueError("Set operation requires a value")
                    parsed_value = parse_value(value_str)
                    editor.set_field(field_path, parsed_value)

                elif operation == "unset":
                    editor.unset_field(field_path)

                elif operation == "merge":
                    if value_str is None:
                        raise ValueError("Merge operation requires a value")
                    if value_str.startswith("from:"):
                        # TODO: Handle file imports
                        raise ValueError("File imports not yet supported for config")
                    else:
                        parsed_value = parse_value(value_str)
                        if not isinstance(parsed_value, dict):
                            raise ValueError(
                                f"Merge value must be a dictionary, got {type(parsed_value)}"
                            )
                        editor.merge_field(field_path, parsed_value)

                elif operation == "append":
                    if value_str is None:
                        raise ValueError("Append operation requires a value")
                    parsed_value = parse_value(value_str)
                    editor.append_field(field_path, parsed_value)

            except Exception as e:
                raise ValueError(
                    f"Operation {operation} on '{field_path}' failed: {e}"
                ) from e

        # Show results for read operations
        for key, value in results.items():
            if key.startswith("get:"):
                field_path = key[4:]  # Remove "get:" prefix
                if isinstance(value, list):
                    if not value:
                        print(f"{field_path}: (empty list)")
                    else:
                        print(f"{field_path}:")
                        for item in value:
                            print(f"  - {item}")
                elif value is None:
                    print(f"{field_path}: null")
                else:
                    print(f"{field_path}: {value}")

        # Show operation log
        if editor.operations_log:
            for operation in editor.operations_log:
                print_success_message(operation)

        # Save changes if not dry run
        if not dry_run and editor.operations_log:
            if save:
                app_ctx.user_config.save()
                print_success_message("Configuration saved")
            else:
                print_success_message("Configuration updated (not saved to disk)")
        elif dry_run and editor.operations_log:
            print_success_message("Dry run complete - no changes saved")
        elif not editor.operations_log and not results:
            print_success_message("No operations performed")

    except Exception as e:
        exc_info = logger.isEnabledFor(logging.DEBUG)
        logger.error("Failed to edit configuration: %s", e, exc_info=exc_info)
        print_error_message(f"Failed to edit configuration: {e}")
        raise typer.Exit(1) from e


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
