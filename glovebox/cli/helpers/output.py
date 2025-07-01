"""Helper functions for CLI output formatting with Rich integration."""

from typing import TYPE_CHECKING, Any

from rich.console import Console

from glovebox.cli.helpers.theme import get_themed_console
from glovebox.models.results import BaseResult


if TYPE_CHECKING:
    from glovebox.cli.helpers.theme import IconMode


def print_success_message(
    message: str,
    use_rich: bool = True,
    use_emoji: bool = False,
    icon_mode: "IconMode | str | None" = None,
) -> None:
    """Print a success message with a checkmark.

    Args:
        message: The message to print
        use_rich: Whether to use Rich formatting (default: True)
        use_emoji: Whether to use emoji icons (default: False) - legacy parameter
        icon_mode: Icon mode override (IconMode enum or string)
    """
    from glovebox.cli.helpers.theme import IconMode

    # Determine icon mode - prefer explicit icon_mode over legacy use_emoji
    if icon_mode is None:
        icon_mode = IconMode.EMOJI if use_emoji else IconMode.TEXT
    elif isinstance(icon_mode, str):
        icon_mode = IconMode(icon_mode)

    if use_rich:
        console = get_themed_console(icon_mode=icon_mode)
        console.print_success(message)
    else:
        from glovebox.cli.helpers.theme import Icons

        icon = Icons.get_icon("CHECKMARK", icon_mode)
        print(f"{icon} {message}")


def print_error_message(
    message: str, use_rich: bool = True, icon_mode: "IconMode | str" = "text"
) -> None:
    """Print an error message with an X symbol.

    Args:
        message: The message to print
        use_rich: Whether to use Rich formatting (default: True)
        icon_mode: Icon mode (IconMode enum or string)
    """
    from glovebox.cli.helpers.theme import IconMode

    # Convert string to enum for backward compatibility
    if isinstance(icon_mode, str):
        icon_mode = IconMode(icon_mode)

    if use_rich:
        console = get_themed_console(icon_mode=icon_mode)
        console.print_error(message)
    else:
        from glovebox.cli.helpers.theme import Icons

        icon = Icons.get_icon("CROSS", icon_mode)
        print(f"{icon} {message}")


def print_list_item(
    item: str,
    indent: int = 1,
    use_rich: bool = True,
    icon_mode: "IconMode | str" = "text",
) -> None:
    """Print a list item with bullet and indentation.

    Args:
        item: The list item to print
        indent: Number of indentation levels (default: 1)
        use_rich: Whether to use Rich formatting (default: True)
        icon_mode: Icon mode (IconMode enum or string)
    """
    from glovebox.cli.helpers.theme import IconMode

    # Convert string to enum for backward compatibility
    if isinstance(icon_mode, str):
        icon_mode = IconMode(icon_mode)

    if use_rich:
        console = get_themed_console(icon_mode=icon_mode)
        console.print_list_item(item, indent)
    else:
        from glovebox.cli.helpers.theme import Icons

        bullet = Icons.get_icon("BULLET", icon_mode)
        print(f"{' ' * (indent * 2)}{bullet} {item}")


def print_result(result: BaseResult, icon_mode: str = "text") -> None:
    """Print operation result with appropriate formatting.

    Args:
        result: The operation result object
        icon_mode: Icon mode ("emoji", "nerdfont", "text")
    """
    if result.success:
        print_success_message("Operation completed successfully", icon_mode=icon_mode)

        # Print any messages
        if hasattr(result, "messages") and result.messages:
            for message in result.messages:
                print_list_item(message, icon_mode=icon_mode)

        # Print any output files
        if hasattr(result, "get_output_files") and callable(result.get_output_files):
            output_files = result.get_output_files()
            if output_files:
                for file_type, file_path in output_files.items():
                    print_list_item(f"{file_type}: {file_path}", icon_mode=icon_mode)
    else:
        print_error_message("Operation failed", icon_mode=icon_mode)
        for error in result.errors:
            print_list_item(error, icon_mode=icon_mode)


# Rich-enhanced helper functions
def print_info_message(
    message: str, use_rich: bool = True, icon_mode: "IconMode | str" = "text"
) -> None:
    """Print an info message with icon.

    Args:
        message: The message to print
        use_rich: Whether to use Rich formatting (default: True)
        icon_mode: Icon mode (IconMode enum or string)
    """
    from glovebox.cli.helpers.theme import IconMode

    # Convert string to enum for backward compatibility
    if isinstance(icon_mode, str):
        icon_mode = IconMode(icon_mode)

    if use_rich:
        console = get_themed_console(icon_mode=icon_mode)
        console.print_info(message)
    else:
        from glovebox.cli.helpers.theme import Icons

        icon = Icons.get_icon("INFO", icon_mode)
        print(f"{icon} {message}")


def print_warning_message(
    message: str, use_rich: bool = True, icon_mode: "IconMode | str" = "text"
) -> None:
    """Print a warning message with icon.

    Args:
        message: The message to print
        use_rich: Whether to use Rich formatting (default: True)
        icon_mode: Icon mode (IconMode enum or string)
    """
    from glovebox.cli.helpers.theme import IconMode

    # Convert string to enum for backward compatibility
    if isinstance(icon_mode, str):
        icon_mode = IconMode(icon_mode)

    if use_rich:
        console = get_themed_console(icon_mode=icon_mode)
        console.print_warning(message)
    else:
        from glovebox.cli.helpers.theme import Icons

        icon = Icons.get_icon("WARNING", icon_mode)
        print(f"{icon} {message}")


def print_header_panel(
    title: str, subtitle: str = "", icon: str = "", icon_mode: str = "text"
) -> None:
    """Print a styled header panel using Rich.

    Args:
        title: Main title
        subtitle: Optional subtitle
        icon: Optional icon
        icon_mode: Icon mode ("emoji", "nerdfont", "text")
    """
    from glovebox.cli.helpers.theme import PanelStyles

    console = Console()
    panel = PanelStyles.create_header_panel(title, subtitle, icon, icon_mode)
    console.print(panel)


def print_device_table(
    devices: list[dict[str, Any]], icon_mode: "IconMode | str" = "text"
) -> None:
    """Print devices in a formatted Rich table.

    Args:
        devices: List of device dictionaries
        icon_mode: Icon mode (IconMode enum or string)
    """
    from glovebox.cli.helpers.output_formatter import DeviceListFormatter
    from glovebox.cli.helpers.theme import IconMode

    # Convert string to enum for backward compatibility
    if isinstance(icon_mode, str):
        icon_mode = IconMode(icon_mode)

    formatter = DeviceListFormatter()
    formatter.format_device_list(devices, "table", icon_mode=icon_mode)


def print_status_table(
    status_data: dict[str, Any], icon_mode: "IconMode | str" = "text"
) -> None:
    """Print status information in a formatted Rich table.

    Args:
        status_data: Status data dictionary
        icon_mode: Icon mode (IconMode enum or string)
    """
    from glovebox.cli.helpers.theme import IconMode, TableStyles

    # Convert string to enum for backward compatibility
    if isinstance(icon_mode, str):
        icon_mode = IconMode(icon_mode)

    console = Console()
    table = TableStyles.create_status_table(icon_mode)

    for component, details in status_data.items():
        if isinstance(details, dict):
            status = details.get("status", "unknown")
            info = details.get("info", "")
        else:
            status = str(details)
            info = ""

        table.add_row(component, status, info)

    console.print(table)


def print_configuration_table(
    config_data: dict[str, Any], icon_mode: "IconMode | str" = "text"
) -> None:
    """Print configuration in a formatted Rich table.

    Args:
        config_data: Configuration data dictionary
        icon_mode: Icon mode (IconMode enum or string)
    """
    from glovebox.cli.helpers.theme import IconMode, TableStyles

    # Convert string to enum for backward compatibility
    if isinstance(icon_mode, str):
        icon_mode = IconMode(icon_mode)

    console = Console()
    table = TableStyles.create_config_table(icon_mode)

    for setting, value in config_data.items():
        if isinstance(value, list | dict):
            value_str = str(value)
        else:
            value_str = str(value)
        table.add_row(setting, value_str)

    console.print(table)


def format_file_list(
    files: list[str] | dict[str, str], format_type: str = "text"
) -> str:
    """Format a list of files for output.

    Args:
        files: List of file paths or dict of {type: path}
        format_type: Output format (text, json, markdown, table)

    Returns:
        Formatted file list
    """
    from glovebox.cli.helpers.output_formatter import OutputFormatter

    formatter = OutputFormatter()
    return formatter.format(files, format_type)


def print_build_progress(stage: str, progress: int = 0, total: int = 100) -> None:
    """Print build progress with Rich formatting.

    Args:
        stage: Current build stage
        progress: Current progress value
        total: Total progress value
    """
    from rich.progress import Progress, SpinnerColumn, TextColumn

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress_bar:
        task = progress_bar.add_task(f"Building: {stage}", total=total)
        progress_bar.update(task, advance=progress)
