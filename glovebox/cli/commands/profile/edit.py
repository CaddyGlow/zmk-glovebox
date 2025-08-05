"""Profile configuration editing commands."""

import os
import subprocess
from pathlib import Path
from typing import Annotated, Any

import typer

from glovebox.cli.app import AppContext
from glovebox.cli.core.command_base import IOCommand
from glovebox.cli.decorators import handle_errors
from glovebox.cli.helpers.theme import (
    Icons,
    get_themed_console,
)
from glovebox.config.keyboard_profile import (
    get_available_keyboards,
    load_keyboard_config,
)
from glovebox.config.models.keyboard import KeyboardConfig
from glovebox.core.structlog_logger import get_struct_logger


logger = get_struct_logger(__name__)


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


def complete_profile_config_keys(incomplete: str) -> list[str]:
    """Tab completion for profile configuration keys."""
    try:

        def get_all_keyboard_config_keys() -> list[str]:
            """Get all valid keyboard configuration keys from the models."""
            keys = []

            # Add keyboard config keys
            for field_name in KeyboardConfig.model_fields:
                if field_name not in ["includes"]:  # Skip internal fields
                    keys.append(field_name)

            # Add nested keys for complex objects
            # Add firmware-related keys
            keys.extend(
                [
                    "firmwares",
                    "compile_methods",
                    "flash_methods",
                ]
            )

            # Add behavior keys
            keys.extend(
                [
                    "behaviors.system_behaviors",
                    "behaviors.custom_behaviors",
                ]
            )

            # Add display keys
            keys.extend(
                [
                    "display.layout_structure",
                    "display.formatting",
                ]
            )

            # Add ZMK keys
            keys.extend(
                [
                    "zmk.validation_limits",
                    "zmk.patterns",
                    "zmk.compatible_strings",
                ]
            )

            return keys

        valid_keys = get_all_keyboard_config_keys()
        return [key for key in valid_keys if key.startswith(incomplete)]
    except Exception:
        # If completion fails, return empty list
        return []


def _get_profile_field_type_for_key(config_key: str) -> type:
    """Get the expected type for a keyboard configuration key."""
    if "." in config_key:
        # Handle nested keys
        parts = config_key.split(".")
        # For simplicity, treat nested keys as strings for now
        return str
    else:
        field_info = KeyboardConfig.model_fields.get(config_key)

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


class ProfileEditCommand(IOCommand):
    """Command for editing keyboard profile configurations.

    Handles getting, setting, adding to, removing from, and clearing
    keyboard configuration values in a unified interface.
    """

    def __init__(self, app_ctx: AppContext) -> None:
        """Initialize profile edit command.

        Args:
            app_ctx: Application context with user configuration
        """
        super().__init__()
        self.app_ctx = app_ctx

    def execute(
        self,
        profile_name: str,
        get: list[str] | None = None,
        set: list[str] | None = None,  # noqa: A002
        add: list[str] | None = None,
        remove: list[str] | None = None,
        clear: list[str] | None = None,
        save: bool = True,  # noqa: ARG002
        interactive: bool = False,
    ) -> None:
        """Execute the profile edit command.

        Args:
            profile_name: Name of the profile to edit
            get: List of keys to get values for
            set: List of key=value pairs to set
            add: List of key=value pairs to add to lists
            remove: List of key=value pairs to remove from lists
            clear: List of keys to clear
            save: Whether to save changes (currently unused)
            interactive: Whether to use interactive editing mode
        """
        # Verify keyboard exists
        self._verify_keyboard_exists(profile_name)

        # Load keyboard configuration
        keyboard_config = self._load_keyboard_config(profile_name)

        # Handle interactive editing first (exclusive mode)
        if interactive:
            self._validate_interactive_mode(get, set, add, remove, clear)
            self._handle_interactive_edit(profile_name)
            return

        # Ensure at least one operation is specified for non-interactive mode
        self._validate_operations(get, set, add, remove, clear)

        # Handle GET operations
        if get:
            self._handle_get_operations(get, keyboard_config)

        # Handle modification operations (currently not supported)
        if any([set, add, remove, clear]):
            self._handle_unsupported_modifications()

    def _verify_keyboard_exists(self, profile_name: str) -> None:
        """Verify that the specified keyboard profile exists.

        Args:
            profile_name: Name of the profile to verify

        Raises:
            typer.Exit: If keyboard does not exist
        """
        keyboards = get_available_keyboards(self.app_ctx.user_config)
        if profile_name not in keyboards:
            self.console.print_error(f"Keyboard '{profile_name}' not found")
            self.console.print_error(f"Available keyboards: {', '.join(keyboards)}")
            raise typer.Exit(1)

    def _load_keyboard_config(self, profile_name: str) -> KeyboardConfig:
        """Load keyboard configuration for the specified profile.

        Args:
            profile_name: Name of the profile to load

        Returns:
            Loaded keyboard configuration

        Raises:
            typer.Exit: If configuration cannot be loaded
        """
        try:
            return load_keyboard_config(profile_name, self.app_ctx.user_config)
        except Exception as e:
            self.handle_service_error(e, "load keyboard configuration")
            # This line is never reached but required for type checking
            raise  # pragma: no cover

    def _validate_interactive_mode(
        self,
        get: list[str] | None,
        set: list[str] | None,  # noqa: A002
        add: list[str] | None,
        remove: list[str] | None,
        clear: list[str] | None,
    ) -> None:
        """Validate that interactive mode is not combined with other operations.

        Args:
            get: Get operations list
            set: Set operations list
            add: Add operations list
            remove: Remove operations list
            clear: Clear operations list

        Raises:
            typer.Exit: If interactive mode is combined with other operations
        """
        if any([get, set, add, remove, clear]):
            self.console.print_error(
                "Interactive mode (--interactive) cannot be combined with other operations"
            )
            raise typer.Exit(1)

    def _validate_operations(
        self,
        get: list[str] | None,
        set: list[str] | None,  # noqa: A002
        add: list[str] | None,
        remove: list[str] | None,
        clear: list[str] | None,
    ) -> None:
        """Validate that at least one operation is specified.

        Args:
            get: Get operations list
            set: Set operations list
            add: Add operations list
            remove: Remove operations list
            clear: Clear operations list

        Raises:
            typer.Exit: If no operations are specified
        """
        if not any([get, set, add, remove, clear]):
            self.console.print_error(
                "At least one operation (--get, --set, --add, --remove, --clear, --interactive) must be specified"
            )
            raise typer.Exit(1)

    def _handle_interactive_edit(self, profile_name: str) -> None:
        """Handle interactive editing of the keyboard configuration file.

        Args:
            profile_name: Name of the profile to edit interactively
        """
        _handle_interactive_profile_edit(profile_name, self.app_ctx)

    def _get_all_keyboard_config_keys(self) -> list[str]:
        """Get all valid keyboard configuration keys from the models.

        Returns:
            List of all valid configuration keys
        """
        keys = []

        # Add keyboard config keys
        for field_name in KeyboardConfig.model_fields:
            if field_name not in ["includes"]:  # Skip internal fields
                keys.append(field_name)

        # Add nested keys for complex objects
        keys.extend(
            [
                "firmwares",
                "compile_methods",
                "flash_methods",
                "behaviors.system_behaviors",
                "behaviors.custom_behaviors",
                "display.layout_structure",
                "display.formatting",
                "zmk.validation_limits",
                "zmk.patterns",
                "zmk.compatible_strings",
            ]
        )

        return keys

    def _handle_get_operations(
        self, get_keys: list[str], keyboard_config: KeyboardConfig
    ) -> None:
        """Handle GET operations for configuration values.

        Args:
            get_keys: List of keys to get values for
            keyboard_config: Loaded keyboard configuration
        """
        valid_keys = self._get_all_keyboard_config_keys()

        for key in get_keys:
            if key not in valid_keys:
                self.console.print_error(f"Unknown keyboard configuration key: {key}")
                continue

            # Get value from keyboard config
            value = _get_profile_config_value(keyboard_config, key)

            # Format and display the value
            self._display_config_value(key, value)

    def _display_config_value(self, key: str, value: Any) -> None:
        """Display a configuration key-value pair with proper formatting.

        Args:
            key: Configuration key name
            value: Configuration value to display
        """
        if isinstance(value, list):
            if not value:
                self.console.console.print(
                    f"[bold blue]{key}:[/bold blue] [dim](empty list)[/dim]"
                )
            else:
                self.console.console.print(f"[bold blue]{key}:[/bold blue]")
                for item in value:
                    bullet_icon = Icons.get_icon("BULLET", self.app_ctx.icon_mode)
                    self.console.console.print(f"  {bullet_icon} [white]{item}[/white]")
        else:
            self.console.console.print(
                f"[bold blue]{key}:[/bold blue] [white]{value}[/white]"
            )

    def _handle_unsupported_modifications(self) -> None:
        """Handle unsupported modification operations with informative error.

        Raises:
            typer.Exit: Always, as modifications are not yet supported
        """
        error_icon = Icons.get_icon("ERROR", self.app_ctx.icon_mode)
        self.console.console.print(
            f"\n[bold red]{error_icon} Direct editing of keyboard configuration values is not yet supported.[/bold red]"
        )
        self.console.console.print(
            "[yellow]Keyboard configurations are loaded from YAML files in the keyboard_paths.[/yellow]"
        )
        self.console.console.print(
            "[blue]Use --interactive mode to edit the YAML files directly, or modify the files manually.[/blue]\n"
        )
        raise typer.Exit(1)


@handle_errors
def edit_profile(
    ctx: typer.Context,
    profile_name: str = typer.Argument(
        ..., help="Profile name to edit", autocompletion=complete_profile_names
    ),
    get: Annotated[
        list[str] | None,
        typer.Option(
            "--get",
            help="Get keyboard configuration values (can be used multiple times)",
            autocompletion=complete_profile_config_keys,
        ),
    ] = None,
    set: Annotated[
        list[str] | None,
        typer.Option(
            "--set",
            help="Set keyboard configuration values as key=value (can be used multiple times)",
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
            autocompletion=complete_profile_config_keys,
        ),
    ] = None,
    save: Annotated[
        bool,
        typer.Option("--save/--no-save", help="Save keyboard configuration to file"),
    ] = True,
    interactive: Annotated[
        bool,
        typer.Option(
            "--interactive",
            "-i",
            help="Open keyboard configuration file in editor for interactive editing",
        ),
    ] = False,
) -> None:
    """Unified keyboard configuration editing command.

    This command supports getting, setting, adding to, removing from, and clearing
    keyboard configuration values in a single operation. Multiple operations can be performed at once.

    Examples:
        # Get single value
        glovebox keyboard edit glove80 --get description

        # Get multiple values
        glovebox keyboard edit glove80 --get description --get vendor

        # Set single value
        glovebox keyboard edit glove80 --set description="Custom description"

        # Set multiple values
        glovebox keyboard edit glove80 --set description="Custom" --set vendor="Custom Vendor"

        # Interactive editing
        glovebox keyboard edit glove80 --interactive
    """
    # Get app context with user config
    app_ctx: AppContext = ctx.obj

    # Create and execute command
    command = ProfileEditCommand(app_ctx)
    command.execute(
        profile_name=profile_name,
        get=get,
        set=set,
        add=add,
        remove=remove,
        clear=clear,
        save=save,
        interactive=interactive,
    )


def _get_profile_config_value(keyboard_config: Any, key: str) -> Any:
    """Get a value from keyboard config using dot notation."""
    try:
        if "." in key:
            parts = key.split(".")
            value = keyboard_config
            for part in parts:
                if hasattr(value, part):
                    value = getattr(value, part)
                else:
                    return None
            return value
        else:
            return getattr(keyboard_config, key, None)
    except Exception:
        return None


def _handle_interactive_profile_edit(profile_name: str, app_ctx: AppContext) -> None:
    """Handle interactive editing of the keyboard configuration file."""
    # Get the editor from user config or environment
    editor = app_ctx.user_config.get("editor")
    if not editor:
        editor = os.environ.get("EDITOR", "nano")

    console = get_themed_console()

    # Find the keyboard config file
    keyboard_paths = app_ctx.user_config.get("keyboard_paths", [])
    config_file_path = None

    for keyboard_path in keyboard_paths:
        # Look for keyboard config files
        possible_files = [
            Path(keyboard_path) / f"{profile_name}.yaml",
            Path(keyboard_path) / profile_name / "main.yaml",
            Path(keyboard_path) / "keyboards" / f"{profile_name}.yaml",
            Path(keyboard_path) / "keyboards" / profile_name / "main.yaml",
        ]

        for file_path in possible_files:
            if file_path.exists():
                config_file_path = file_path
                break

        if config_file_path:
            break

    if not config_file_path:
        error_icon = Icons.get_icon("ERROR", app_ctx.icon_mode)
        console.console.print(
            f"\n[bold red]{error_icon} Could not find configuration file for keyboard '{profile_name}'[/bold red]"
        )
        console.console.print("[yellow]Searched in keyboard_paths:[/yellow]")
        for path in keyboard_paths:
            bullet_icon = Icons.get_icon("BULLET", app_ctx.icon_mode)
            console.console.print(f"  {bullet_icon} [dim]{path}[/dim]")
        raise typer.Exit(1)

    # Get the file modification time before editing
    original_mtime = config_file_path.stat().st_mtime

    try:
        # Open the config file in the editor
        info_icon = Icons.get_icon("INFO", app_ctx.icon_mode)
        console.console.print(
            f"\n[bold blue]{info_icon} Opening {config_file_path} in {editor}...[/bold blue]"
        )
        result = subprocess.run([editor, str(config_file_path)], check=True)

        # Check if the file was modified
        if config_file_path.exists():
            new_mtime = config_file_path.stat().st_mtime
            if new_mtime > original_mtime:
                success_icon = Icons.get_icon("SUCCESS", app_ctx.icon_mode)
                console.console.print(
                    f"\n[bold green]{success_icon} Keyboard configuration file modified[/bold green]"
                )

                # Try to reload the configuration to validate it
                try:
                    load_keyboard_config(profile_name, app_ctx.user_config)
                    console.console.print(
                        f"[bold green]{success_icon} Keyboard configuration reloaded successfully[/bold green]"
                    )
                except Exception as e:
                    error_icon = Icons.get_icon("ERROR", app_ctx.icon_mode)
                    console.console.print(
                        f"[bold red]{error_icon} Keyboard configuration file has validation errors: {e}[/bold red]"
                    )

                    # Ask if user wants to re-edit
                    if typer.confirm(
                        "Would you like to edit the file again to fix the errors?"
                    ):
                        _handle_interactive_profile_edit(profile_name, app_ctx)
                    else:
                        error_icon = Icons.get_icon("ERROR", app_ctx.icon_mode)
                        console.console.print(
                            f"[bold red]{error_icon} Configuration changes were not applied due to validation errors[/bold red]"
                        )
                        raise typer.Exit(1) from e
            else:
                info_icon = Icons.get_icon("INFO", app_ctx.icon_mode)
                console.console.print(
                    f"[blue]{info_icon} No changes made to keyboard configuration file[/blue]"
                )
        else:
            error_icon = Icons.get_icon("ERROR", app_ctx.icon_mode)
            console.console.print(
                f"[bold red]{error_icon} Keyboard configuration file was deleted during editing[/bold red]"
            )
            raise typer.Exit(1)

    except subprocess.CalledProcessError as e:
        error_icon = Icons.get_icon("ERROR", app_ctx.icon_mode)
        console.console.print(
            f"[bold red]{error_icon} Editor exited with error code {e.returncode}[/bold red]"
        )
        raise typer.Exit(1) from e
    except FileNotFoundError as e:
        error_icon = Icons.get_icon("ERROR", app_ctx.icon_mode)
        console.console.print(
            f"[bold red]{error_icon} Editor '{editor}' not found. Please check your editor configuration.[/bold red]"
        )
        console.console.print(
            "[yellow]You can set the editor with: glovebox config edit --set editor=your_editor[/yellow]"
        )
        raise typer.Exit(1) from e
    except KeyboardInterrupt as e:
        warning_icon = Icons.get_icon("WARNING", app_ctx.icon_mode)
        console.console.print(
            f"[yellow]{warning_icon} Interactive editing cancelled[/yellow]"
        )
        raise typer.Exit(1) from e
