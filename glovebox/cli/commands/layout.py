"""Layout-related CLI commands."""

import json
import logging
from pathlib import Path
from typing import Annotated, Any, Optional

import typer

from glovebox.cli.decorators import handle_errors, with_profile
from glovebox.cli.helpers import (
    print_error_message,
    print_list_item,
    print_success_message,
)
from glovebox.cli.helpers.parameters import ProfileOption
from glovebox.cli.helpers.profile import get_keyboard_profile_from_context
from glovebox.config.profile import KeyboardProfile
from glovebox.layout.service import create_layout_service


logger = logging.getLogger(__name__)

# Create a typer app for layout commands
layout_app = typer.Typer(
    name="layout",
    help="""Layout management commands.

Convert JSON layouts to ZMK files, extract/merge layers, validate layouts,
and display visual representations of keyboard layouts.""",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@layout_app.command(name="compile")
@handle_errors
@with_profile()
def layout_compile(
    ctx: typer.Context,
    output_file_prefix: Annotated[
        str,
        typer.Argument(
            help="Output directory and base filename (e.g., 'config/my_glove80')"
        ),
    ],
    json_file: Annotated[
        str,
        typer.Argument(help="Path to keymap JSON file"),
    ],
    profile: ProfileOption = None,
    # keyboard_profile=None,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
) -> None:
    """Compile ZMK keymap and config files from a JSON keymap file.

    Takes a JSON layout file (exported from Layout Editor) and generates
    ZMK .keymap and .conf files ready for firmware compilation.

    ---

    Examples:

    * glovebox layout compile layout.json output/glove80 --profile glove80/v25.05

    * cat layout.json | glovebox layout compile - output/glove80 --profile glove80/v25.05
    """

    # Generate keymap using the file-based service method
    keymap_service = create_layout_service()

    # The @with_profile decorator injects keyboard_profile parameter
    from glovebox.cli.app import AppContext

    app_ctx: AppContext = ctx.obj
    keyboard_profile = get_keyboard_profile_from_context(ctx)

    # keyboard_profile = kwargs["keyboard_profile"]
    # assert KeyboardProfile is not None

    try:
        result = keymap_service.generate_from_file(
            profile=keyboard_profile,
            json_file_path=Path(json_file),
            output_file_prefix=output_file_prefix,
            force=force,
        )

        if result.success:
            print_success_message("Layout generated successfully")
            output_files = result.get_output_files()
            for file_type, file_path in output_files.items():
                print_list_item(f"{file_type}: {file_path}")
        else:
            print_error_message("Layout generation failed")
            for error in result.errors:
                print_list_item(error)
            raise typer.Exit(1)

    except Exception as e:
        print_error_message(f"Layout generation failed: {str(e)}")
        raise typer.Exit(1) from None


@layout_app.command()
@handle_errors
@with_profile()
def decompose(
    ctx: typer.Context,
    keymap_file: Annotated[Path, typer.Argument(help="Path to keymap JSON file")],
    output_dir: Annotated[
        Path, typer.Argument(help="Directory to save extracted files")
    ],
    profile: Annotated[str, typer.Option()],
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
) -> None:
    """Decompose layers from a keymap file into individual layer files."""

    # Use the file-based service method
    keymap_service = create_layout_service()

    # The @with_profile decorator injects keyboard_profile via kwargs
    keyboard_profile = kwargs["keyboard_profile"]

    try:
        result = keymap_service.decompose_components_from_file(
            profile=keyboard_profile,
            json_file_path=keymap_file,
            output_dir=output_dir,
            force=force,
        )

        if result.success:
            print_success_message(f"Layout layers decomposed to {output_dir}")
        else:
            print_error_message("Layout component decomposition failed")
            for error in result.errors:
                print_list_item(error)
            raise typer.Exit(1)
    except Exception as e:
        print_error_message(f"Layout component extraction failed: {str(e)}")
        raise typer.Exit(1) from None


@layout_app.command()
@handle_errors
@with_profile(default_profile="glove80/v25.05")
def compose(
    ctx: typer.Context,
    input_dir: Annotated[
        Path,
        typer.Argument(help="Directory with metadata.json and layers/ subdirectory"),
    ],
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Output keymap JSON file path")
    ],
    profile: ProfileOption = None,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
    keyboard_profile=None,
) -> None:
    """Compose layer files into a single keymap file."""

    # Use the file-based service method
    keymap_service = create_layout_service()

    # The @with_profile decorator injects keyboard_profile via kwargs
    keyboard_profile = kwargs["keyboard_profile"]

    try:
        result = keymap_service.generate_from_directory(
            profile=keyboard_profile,
            components_dir=input_dir,
            output_file_prefix=output,
            force=force,
        )

        if result.success:
            print_success_message(f"Layout composed and saved to {output}")
        else:
            print_error_message("Layout composition failed")
            for error in result.errors:
                print_list_item(error)
            raise typer.Exit(1)
    except Exception as e:
        print_error_message(f"Layout composition failed: {str(e)}")
        raise typer.Exit(1) from None


@layout_app.command()
@handle_errors
@with_profile(default_profile="glove80/v25.05")
def validate(
    ctx: typer.Context,
    json_file: Annotated[Path, typer.Argument(help="Path to keymap JSON file")],
    profile: ProfileOption = None,
    keyboard_profile=None,
) -> None:
    """Validate keymap syntax and structure."""

    # Validate using the file-based service method
    keymap_service = create_layout_service()

    # The @with_profile decorator injects keyboard_profile via kwargs
    keyboard_profile = kwargs["keyboard_profile"]

    try:
        if keymap_service.validate_from_file(
            profile=keyboard_profile, json_file_path=json_file
        ):
            print_success_message(f"Layout file {json_file} is valid")
        else:
            print_error_message(f"Layout file {json_file} is invalid")
            raise typer.Exit(1)
    except Exception as e:
        print_error_message(f"Layout validation failed: {str(e)}")
        raise typer.Exit(1) from None


@layout_app.command()
@handle_errors
@with_profile(default_profile="glove80/v25.05")
def show(
    ctx: typer.Context,
    json_file: Annotated[
        Path, typer.Argument(help="Path to keyboard layout JSON file")
    ],
    key_width: Annotated[
        int, typer.Option("--key-width", "-w", help="Width for displaying each key")
    ] = 10,
    view_mode: Annotated[
        str | None,
        typer.Option(
            "--view-mode", "-m", help="View mode (normal, compact, split, flat)"
        ),
    ] = None,
    layout: Annotated[
        str | None,
        typer.Option("--layout", "-l", help="Layout name to use for display"),
    ] = None,
    layer: Annotated[
        int | None, typer.Option("--layer", help="Show only specific layer index")
    ] = None,
    profile: ProfileOption = None,
    keyboard_profile=None,
) -> None:
    """Display keymap layout in terminal."""

    # Call the service
    keymap_service = create_layout_service()

    # The @with_profile decorator injects keyboard_profile via kwargs
    keyboard_profile = kwargs["keyboard_profile"]

    try:
        result = keymap_service.show_from_file(
            json_file_path=json_file,
            profile=keyboard_profile,
            key_width=key_width,
        )
        # The show method returns a string
        typer.echo(result)
    except NotImplementedError as e:
        print_error_message(str(e))
        raise typer.Exit(1) from e


def register_commands(app: typer.Typer) -> None:
    """Register layout commands with the main app.

    Args:
        app: The main Typer app
    """
    app.add_typer(layout_app, name="layout")
