"""Unified layout variable management CLI command with batch operations."""

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from glovebox.adapters import create_file_adapter, create_template_adapter
from glovebox.cli.commands.layout.base import LayoutOutputCommand
from glovebox.cli.decorators import handle_errors
from glovebox.cli.helpers.parameters import OutputFormatOption
from glovebox.layout import (
    create_behavior_registry,
    create_grid_layout_formatter,
    create_layout_component_service,
    create_layout_display_service,
    create_layout_service,
)
from glovebox.layout.behavior.formatter import BehaviorFormatterImpl
from glovebox.layout.utils.variable_resolver import VariableResolver
from glovebox.layout.zmk_generator import ZmkFileContentGenerator


console = Console()


def _create_layout_service_with_dependencies():
    """Create a layout service with all required dependencies."""
    file_adapter = create_file_adapter()
    template_adapter = create_template_adapter()
    behavior_registry = create_behavior_registry()
    behavior_formatter = BehaviorFormatterImpl(behavior_registry)
    dtsi_generator = ZmkFileContentGenerator(behavior_formatter)
    layout_generator = create_grid_layout_formatter()
    component_service = create_layout_component_service(file_adapter)
    layout_display_service = create_layout_display_service(layout_generator)

    return create_layout_service(
        file_adapter=file_adapter,
        template_adapter=template_adapter,
        behavior_registry=behavior_registry,
        component_service=component_service,
        layout_service=layout_display_service,
        behavior_formatter=behavior_formatter,
        dtsi_generator=dtsi_generator,
    )


@handle_errors
def variables(
    layout_file: Annotated[Path, typer.Argument(help="Path to layout JSON file")],
    # Variable display operations
    list_vars: Annotated[
        bool, typer.Option("--list", help="List all variables in the layout")
    ] = False,
    list_resolved: Annotated[
        bool,
        typer.Option("--list-resolved", help="List variables with resolved values"),
    ] = False,
    list_usage: Annotated[
        bool, typer.Option("--list-usage", help="Show where each variable is used")
    ] = False,
    # Variable modification operations
    get_var: Annotated[
        list[str] | None,
        typer.Option("--get", help="Get variable value(s) by name"),
    ] = None,
    set_var: Annotated[
        list[str] | None,
        typer.Option(
            "--set",
            help="Set variable value using name=value syntax",
        ),
    ] = None,
    remove_var: Annotated[
        list[str] | None,
        typer.Option("--remove", help="Remove variable(s) by name"),
    ] = None,
    # Variable validation and flattening
    validate: Annotated[
        bool, typer.Option("--validate", help="Validate all variable references")
    ] = False,
    flatten: Annotated[
        bool,
        typer.Option(
            "--flatten", help="Resolve variables and remove variables section"
        ),
    ] = False,
    # Output options
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output file (default: overwrite original for --flatten)",
        ),
    ] = None,
    output_format: OutputFormatOption = "text",
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
    save: Annotated[
        bool, typer.Option("--save/--no-save", help="Save changes to file")
    ] = True,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Show what would be done without making changes"
        ),
    ] = False,
) -> None:
    """Unified variable management command with batch operations support.

    This command provides comprehensive variable management for layout files,
    including listing, modification, validation, and flattening operations.

    Variable Display:
        --list                               # List all variable names
        --list-resolved                      # Show variables with resolved values
        --list-usage                         # Show where each variable is used
        --get timing --get flavor            # Get specific variable values

    Variable Modification:
        --set timing=190 --set flavor=tap-preferred    # Set variable values
        --remove old_var --remove unused_var           # Remove variables

    Variable Validation and Flattening:
        --validate                           # Check all variable references are valid
        --flatten                           # Resolve all variables and remove variables section
        --flatten --output flattened.json   # Flatten to new file

    Examples:
        # List all variables
        glovebox layout variables layout.json --list

        # Show variables with their resolved values
        glovebox layout variables layout.json --list-resolved

        # Show where variables are used
        glovebox layout variables layout.json --list-usage

        # Get specific variable values
        glovebox layout variables layout.json --get timing --get flavor

        # Set multiple variables
        glovebox layout variables layout.json --set timing=150 --set flavor=balanced

        # Validate all variable references
        glovebox layout variables layout.json --validate

        # Flatten layout (resolve variables and remove variables section)
        glovebox layout variables layout.json --flatten --output flattened.json

        # Batch operations
        glovebox layout variables layout.json \\
          --set timing=150 \\
          --remove old_timing \\
          --validate

        # Dry run to see what would change
        glovebox layout variables layout.json --set timing=150 --dry-run
    """
    command = LayoutOutputCommand()
    command.validate_layout_file(layout_file)

    try:
        layout_service = _create_layout_service_with_dependencies()

        # For flatten operation, handle specially since it doesn't need variable modification
        if flatten:
            if output is None:
                console.print(
                    "[red]Error: --output is required for --flatten operation[/red]"
                )
                raise typer.Exit(1)

            if dry_run:
                console.print(f"[blue]Would flatten {layout_file} to {output}[/blue]")
                return

            if not force and output.exists():
                console.print(
                    f"[red]Error: Output file {output} already exists. Use --force to overwrite.[/red]"
                )
                raise typer.Exit(1)

            layout_service.flatten_layout_from_file(layout_file, output)
            console.print(f"[green]Layout flattened successfully to {output}[/green]")
            return

        # Load layout for other operations
        json_data = layout_service._file_adapter.read_json(layout_file)

        # Handle validation operation
        if validate:
            errors = layout_service.validate_variables_from_file(layout_file)
            if errors:
                console.print("[red]Variable validation failed:[/red]")
                for error in errors:
                    console.print(f"  [red]• {error}[/red]")
                if not any(
                    [list_vars, list_resolved, list_usage, get_var, set_var, remove_var]
                ):
                    raise typer.Exit(1)
            else:
                console.print("[green]All variables validated successfully[/green]")

        # Get variables from the layout
        variables_dict = json_data.get("variables", {})

        if not variables_dict and any([list_vars, list_resolved, list_usage, get_var]):
            console.print("[yellow]No variables found in layout[/yellow]")
            return

        # Initialize resolver if we have variables
        resolver = VariableResolver(variables_dict) if variables_dict else None

        # Handle display operations
        if list_vars:
            _display_variables_list(variables_dict, output_format)

        if list_resolved and resolver:
            _display_variables_resolved(variables_dict, resolver, output_format)

        if list_usage and resolver:
            _display_variables_usage(json_data, resolver, output_format)

        if get_var:
            _display_variable_values(variables_dict, get_var, output_format)

        # Handle modification operations
        modified = False
        if set_var:
            _set_variables(json_data, set_var, dry_run)
            modified = True

        if remove_var:
            _remove_variables(json_data, remove_var, dry_run)
            modified = True

        # Save changes if modifications were made
        if modified and save and not dry_run:
            output_path = output if output else layout_file
            if not force and output_path.exists() and output_path != layout_file:
                console.print(
                    f"[red]Error: Output file {output_path} already exists. Use --force to overwrite.[/red]"
                )
                raise typer.Exit(1)

            layout_service._file_adapter.write_json(output_path, json_data)
            console.print(f"[green]Changes saved to {output_path}[/green]")
        elif modified and dry_run:
            console.print("[blue]Dry run completed - no changes were saved[/blue]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e


def _display_variables_list(variables_dict: dict[str, Any], output_format: str) -> None:
    """Display list of variable names."""
    if output_format == "json":
        console.print(json.dumps(list(variables_dict.keys()), indent=2))
    else:
        if not variables_dict:
            console.print("[yellow]No variables defined[/yellow]")
            return

        table = Table(title="Variables")
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="green")

        for name, value in variables_dict.items():
            table.add_row(name, type(value).__name__)

        console.print(table)


def _display_variables_resolved(
    variables_dict: dict[str, Any], resolver: VariableResolver, output_format: str
) -> None:
    """Display variables with their resolved values."""
    if output_format == "json":
        resolved = {}
        for name in variables_dict:
            try:
                resolved[name] = resolver._resolve_variable(name)
            except Exception as e:
                resolved[name] = f"<Error: {e}>"
        console.print(json.dumps(resolved, indent=2, default=str))
    else:
        table = Table(title="Variables with Resolved Values")
        table.add_column("Name", style="cyan")
        table.add_column("Raw Value", style="yellow")
        table.add_column("Resolved Value", style="green")
        table.add_column("Type", style="blue")

        for name, raw_value in variables_dict.items():
            try:
                resolved_value = resolver._resolve_variable(name)
                resolved_str = str(resolved_value)
                if len(resolved_str) > 50:
                    resolved_str = resolved_str[:47] + "..."
            except Exception as e:
                resolved_value = f"<Error: {e}>"
                resolved_str = str(resolved_value)

            raw_str = str(raw_value)
            if len(raw_str) > 30:
                raw_str = raw_str[:27] + "..."

            table.add_row(
                name,
                raw_str,
                resolved_str,
                type(resolved_value).__name__
                if not isinstance(resolved_value, str)
                or not resolved_value.startswith("<Error:")
                else "Error",
            )

        console.print(table)


def _display_variables_usage(
    json_data: dict[str, Any], resolver: VariableResolver, output_format: str
) -> None:
    """Display where each variable is used."""
    usage = resolver.get_variable_usage(json_data)

    if output_format == "json":
        console.print(json.dumps(usage, indent=2))
    else:
        if not usage:
            console.print("[yellow]No variable usage found[/yellow]")
            return

        table = Table(title="Variable Usage")
        table.add_column("Variable", style="cyan")
        table.add_column("Used In", style="green")
        table.add_column("Count", style="blue")

        for var_name, paths in usage.items():
            usage_str = (
                "\n".join(paths)
                if len(paths) <= 5
                else "\n".join(paths[:5]) + f"\n... and {len(paths) - 5} more"
            )
            table.add_row(var_name, usage_str, str(len(paths)))

        console.print(table)


def _display_variable_values(
    variables_dict: dict[str, Any], var_names: list[str], output_format: str
) -> None:
    """Display specific variable values."""
    if output_format == "json":
        result = {}
        for name in var_names:
            result[name] = variables_dict.get(name)
        console.print(json.dumps(result, indent=2, default=str))
    else:
        for name in var_names:
            if name in variables_dict:
                value = variables_dict[name]
                console.print(f"[cyan]{name}[/cyan]: [green]{value}[/green]")
            else:
                console.print(f"[cyan]{name}[/cyan]: [red]<not found>[/red]")


def _set_variables(
    json_data: dict[str, Any], set_vars: list[str], dry_run: bool
) -> None:
    """Set variable values."""
    if "variables" not in json_data:
        json_data["variables"] = {}

    for var_assignment in set_vars:
        if "=" not in var_assignment:
            console.print(
                f"[red]Invalid assignment format: {var_assignment}. Use name=value[/red]"
            )
            continue

        name, value = var_assignment.split("=", 1)
        name = name.strip()
        value = value.strip()

        # Try to parse value as JSON for proper typing
        try:
            # Handle special cases for boolean and numeric values
            parsed_value: Any
            if value.lower() in ("true", "false"):
                parsed_value = value.lower() == "true"
            elif value.isdigit():
                parsed_value = int(value)
            elif value.replace(".", "", 1).isdigit():
                parsed_value = float(value)
            else:
                # Try JSON parsing for complex values, fallback to string
                try:
                    parsed_value = json.loads(value)
                except json.JSONDecodeError:
                    parsed_value = value
        except Exception:
            parsed_value = value

        if dry_run:
            console.print(
                f"[blue]Would set {name} = {parsed_value} ({type(parsed_value).__name__})[/blue]"
            )
        else:
            json_data["variables"][name] = parsed_value
            console.print(f"[green]Set {name} = {parsed_value}[/green]")


def _remove_variables(
    json_data: dict[str, Any], remove_vars: list[str], dry_run: bool
) -> None:
    """Remove variables."""
    if "variables" not in json_data:
        console.print("[yellow]No variables section found[/yellow]")
        return

    for name in remove_vars:
        if name in json_data["variables"]:
            if dry_run:
                console.print(f"[blue]Would remove variable: {name}[/blue]")
            else:
                del json_data["variables"][name]
                console.print(f"[green]Removed variable: {name}[/green]")
        else:
            console.print(f"[yellow]Variable not found: {name}[/yellow]")
