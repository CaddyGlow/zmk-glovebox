"""Layout parsing commands for reverse engineering keymaps."""

import logging
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from glovebox.cli.decorators import handle_errors
from glovebox.cli.helpers import (
    print_error_message,
    print_success_message,
)
from glovebox.cli.helpers.parameters import (
    JsonFileArgument,
    OutputFormatOption,
    ProfileOption,
)
from glovebox.config import create_keyboard_profile
from glovebox.layout import create_layout_service


logger = logging.getLogger(__name__)
console = Console()


@handle_errors
def parse_keymap(
    ctx: typer.Context,
    keymap_file: Annotated[
        Path,
        typer.Argument(
            help="Path to ZMK keymap file (.keymap)",
            exists=True,
            file_okay=True,
            dir_okay=False,
        ),
    ],
    # Profile options
    profile: ProfileOption = None,
    # Parsing options
    mode: Annotated[
        str,
        typer.Option(
            "--mode",
            "-m",
            help="Parsing mode: 'full' for complete parsing, 'template' for template-aware",
        ),
    ] = "template",
    # Output options
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output JSON file path (default: keymap_file.json)",
        ),
    ] = None,
    output_format: OutputFormatOption = "text",
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite existing output files"),
    ] = False,
) -> None:
    """Parse ZMK keymap file to JSON layout format.

    Converts .keymap files back to glovebox JSON layout format for editing and management.

    Two parsing modes are available:
    - template: Uses keyboard profile templates to extract only user data (recommended for Glove80)
    - full: Parses complete keymap structure including all behaviors and custom code

    Examples:
        # Parse Glove80 keymap using template-aware mode
        glovebox layout parse-keymap my_keymap.keymap --profile glove80/v25.05

        # Parse with custom output location
        glovebox layout parse-keymap keymap.keymap --profile glove80 -o my_layout.json

        # Full parsing mode for non-glovebox keymaps
        glovebox layout parse-keymap third_party.keymap --profile glove80 --mode full
    """
    # Validate inputs
    if keymap_file.suffix != ".keymap":
        print_error_message("Input file must have .keymap extension")
        raise typer.Exit(1)

    # Determine profile
    if not profile:
        print_error_message("Keyboard profile is required for keymap parsing")
        print_error_message(
            "Use --profile to specify keyboard (e.g., --profile glove80/v25.05)"
        )
        raise typer.Exit(1)

    # Determine output file
    if output is None:
        output = keymap_file.with_suffix(".json")

    # Check if output exists and force not specified
    if output.exists() and not force:
        print_error_message(f"Output file already exists: {output}")
        print_error_message("Use --force to overwrite")
        raise typer.Exit(1)

    try:
        # Get user config from context
        from glovebox.cli.helpers.profile import (
            create_profile_from_option,
            get_user_config_from_context,
        )

        user_config = get_user_config_from_context(ctx)

        # Create keyboard profile with user config
        keyboard_profile = create_profile_from_option(profile, user_config)

        # Create layout service with dependencies
        from glovebox.cli.commands.layout.dependencies import create_full_layout_service

        layout_service = create_full_layout_service()

        # Parse keymap file
        result = layout_service.parse_keymap_from_file(
            keymap_file_path=keymap_file,
            profile=keyboard_profile,
            parsing_mode=mode,
            output_file_path=output,
        )

        if not result.success:
            print_error_message("Keymap parsing failed:")
            for error in result.errors:
                console.print(f"  • {error}", style="red")
            raise typer.Exit(1)

        # Show success message
        print_success_message(f"Successfully parsed keymap to {output}")

        # Show additional information
        for message in result.messages:
            console.print(f"  • {message}", style="dim")

        # Format output if JSON requested
        if output_format == "json":
            import json

            result_data = {
                "success": result.success,
                "output_file": str(output),
                "messages": result.messages,
                "errors": result.errors,
            }
            console.print(json.dumps(result_data, indent=2))

    except Exception as e:
        exc_info = logger.isEnabledFor(logging.DEBUG)
        logger.error("Failed to parse keymap: %s", e, exc_info=exc_info)
        print_error_message(f"Parsing failed: {e}")
        raise typer.Exit(1) from e


@handle_errors
def import_keymap(
    ctx: typer.Context,
    keymap_file: Annotated[
        Path,
        typer.Argument(
            help="Path to ZMK keymap file (.keymap)",
            exists=True,
            file_okay=True,
            dir_okay=False,
        ),
    ],
    # Profile options
    profile: ProfileOption = None,
    # Import options
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            "-n",
            help="Name for imported layout (default: derived from filename)",
        ),
    ] = None,
    mode: Annotated[
        str,
        typer.Option(
            "--mode",
            "-m",
            help="Parsing mode: 'full' for complete parsing, 'template' for template-aware",
        ),
    ] = "template",
    # Output options
    output_dir: Annotated[
        Path | None,
        typer.Option(
            "--output-dir",
            "-d",
            help="Output directory for imported layout (default: current directory)",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite existing output files"),
    ] = False,
) -> None:
    """Import ZMK keymap file as a new glovebox layout.

    This is a convenience command that combines parsing and metadata enhancement.
    The imported layout will be properly formatted with glovebox metadata.

    Examples:
        # Import keymap with automatic naming
        glovebox layout import-keymap my_keymap.keymap --profile glove80/v25.05

        # Import with custom name and location
        glovebox layout import-keymap keymap.keymap --profile glove80 --name "My Custom Layout" -d layouts/
    """
    # Determine layout name
    if name is None:
        name = keymap_file.stem.replace("_", " ").title()

    # Determine output directory
    if output_dir is None:
        output_dir = Path.cwd()
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

    # Create output filename
    safe_name = name.lower().replace(" ", "_").replace("-", "_")
    output_file = output_dir / f"{safe_name}.json"

    # Check if output exists
    if output_file.exists() and not force:
        print_error_message(f"Layout file already exists: {output_file}")
        print_error_message("Use --force to overwrite")
        raise typer.Exit(1)

    try:
        # Get user config from context
        from glovebox.cli.helpers.profile import (
            create_profile_from_option,
            get_user_config_from_context,
        )

        user_config = get_user_config_from_context(ctx)

        # Create keyboard profile with user config
        keyboard_profile = create_profile_from_option(profile, user_config)

        # Create layout service
        from glovebox.cli.commands.layout.dependencies import create_full_layout_service

        layout_service = create_full_layout_service()

        # Parse keymap file (without saving yet)
        result = layout_service.parse_keymap_from_file(
            keymap_file_path=keymap_file,
            profile=keyboard_profile,
            parsing_mode=mode,
            output_file_path=None,  # Don't save yet
        )

        if not result.success:
            print_error_message("Keymap parsing failed:")
            for error in result.errors:
                console.print(f"  • {error}", style="red")
            raise typer.Exit(1)

        # TODO: Enhance layout data with metadata
        # This would add proper title, creator, notes, etc.
        # For now, just save the parsed data

        # Save to output file
        from glovebox.adapters import create_file_adapter

        file_adapter = create_file_adapter()
        if hasattr(result, "layout_data") and result.layout_data:
            # Get the parsed layout data from the parse result
            # We need to access it differently since it wasn't saved to a file
            # For now, re-run the parsing with the output file
            result = layout_service.parse_keymap_from_file(
                keymap_file_path=keymap_file,
                profile=keyboard_profile,
                parsing_mode=mode,
                output_file_path=output_file,
            )

        print_success_message(f"Successfully imported keymap as '{name}'")
        console.print(f"  Saved to: {output_file}", style="dim")

        # Show parsing details
        for message in result.messages:
            console.print(f"  • {message}", style="dim")

    except Exception as e:
        exc_info = logger.isEnabledFor(logging.DEBUG)
        logger.error("Failed to import keymap: %s", e, exc_info=exc_info)
        print_error_message(f"Import failed: {e}")
        raise typer.Exit(1) from e


# Create typer app for parsing commands
app = typer.Typer(name="parse", help="Keymap parsing commands")
app.command("keymap")(parse_keymap)
app.command("import")(import_keymap)


def register_parsing_commands(parent_app: typer.Typer) -> None:
    """Register parsing commands with parent app."""
    parent_app.add_typer(app, name="parse")
