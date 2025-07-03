"""Layout parsing commands for reverse engineering keymaps."""

import logging
from pathlib import Path
from typing import Annotated, Any

import typer

from glovebox.cli.commands.layout.base import BaseLayoutCommand
from glovebox.cli.decorators import handle_errors, with_metrics, with_profile
from glovebox.cli.helpers.parameters import (
    OutputFormatOption,
    ProfileOption,
)


logger = logging.getLogger(__name__)


class ParseKeymapCommand(BaseLayoutCommand):
    """Command to parse ZMK keymap files to JSON layout format."""

    def execute(
        self,
        ctx: typer.Context,
        keymap_file: Path,
        profile: str | None,
        mode: str,
        method: str,
        output: Path | None,
        output_format: str,
        force: bool,
        verbose: bool,
    ) -> None:
        """Execute keymap parsing operation.

        Args:
            ctx: Typer context with profile information
            keymap_file: Path to ZMK keymap file
            profile: Keyboard profile string
            mode: Parsing mode (auto/full/template)
            method: Parsing method (ast/regex)
            output: Output file path
            output_format: Output format (text/json)
            force: Force overwrite existing files
            verbose: Show detailed information
        """
        try:
            # Auto-detect parsing mode if not specified
            if mode == "auto":
                if profile:
                    mode = "template"
                    if verbose:
                        self.console.print_info(
                            "Auto-detected template mode (profile provided)"
                        )
                else:
                    mode = "full"
                    if verbose:
                        self.console.print_info(
                            "Auto-detected full mode (no profile provided)"
                        )

            # Determine output file
            if output is None:
                output = keymap_file.with_suffix(".json")

            # Check if output exists and force not specified
            if output.exists() and not force:
                self.console.print_error(f"Output file already exists: {output}")
                self.console.print_error("Use --force to overwrite")
                raise typer.Exit(1)

            # Get profile from context
            from glovebox.cli.helpers.profile import get_keyboard_profile_from_context

            keyboard_profile = get_keyboard_profile_from_context(ctx)
            if verbose and keyboard_profile:
                self.console.print_info(
                    f"Using keyboard profile: {keyboard_profile.keyboard_name}"
                )

            # Create keymap parser
            from glovebox.layout import create_zmk_keymap_parser
            from glovebox.layout.parsers.models import ParsingMethod, ParsingMode

            keymap_parser = create_zmk_keymap_parser()

            if verbose:
                self.console.print_info(f"Parsing mode: {mode}, method: {method}")
                self.console.print_info(f"Input file: {keymap_file}")
                self.console.print_info(f"Output file: {output}")

            # Convert string modes to enum values
            parsing_mode = (
                ParsingMode.TEMPLATE_AWARE if mode == "template" else ParsingMode.FULL
            )
            parsing_method = (
                ParsingMethod.AST if method == "ast" else ParsingMethod.REGEX
            )

            # Parse keymap file
            result = keymap_parser.parse_keymap(
                keymap_file=keymap_file,
                mode=parsing_mode,
                profile=keyboard_profile,
                method=parsing_method,
            )

            if not result.success:
                self.console.print_error("Keymap parsing failed:")
                for error in result.errors:
                    self.console.print_error(f"  • {error}")
                raise typer.Exit(1)

            # Save the parsed layout data to output file
            if result.layout_data:
                from glovebox.adapters import create_file_adapter

                file_adapter = create_file_adapter()
                file_adapter.write_json(output, result.layout_data.to_dict())

            # Show success message
            self.console.print_success(f"Successfully parsed keymap to {output}")

            # Show additional information
            if verbose or result.warnings:
                for warning in result.warnings:
                    self.console.print_info(f"  • {warning}")

            # Format output if JSON requested
            if output_format == "json":
                result_data = {
                    "success": result.success,
                    "output_file": str(output),
                    "warnings": result.warnings,
                    "errors": result.errors,
                }
                self.write_output(result_data, destination=None)

        except Exception as e:
            self.handle_service_error(e, "parse keymap")


class ImportKeymapCommand(BaseLayoutCommand):
    """Command to import ZMK keymap files as new glovebox layouts."""

    def execute(
        self,
        ctx: typer.Context,
        keymap_file: Path,
        profile: str | None,
        name: str | None,
        mode: str,
        method: str,
        output_dir: Path | None,
        force: bool,
    ) -> None:
        """Execute keymap import operation.

        Args:
            ctx: Typer context with profile information
            keymap_file: Path to ZMK keymap file
            profile: Keyboard profile string
            name: Name for imported layout
            mode: Parsing mode (auto/full/template)
            method: Parsing method (ast/regex)
            output_dir: Output directory
            force: Force overwrite existing files
        """
        try:
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
                self.console.print_error(f"Layout file already exists: {output_file}")
                self.console.print_error("Use --force to overwrite")
                raise typer.Exit(1)

            # Auto-detect parsing mode if not specified
            if mode == "auto":
                if profile:
                    mode = "template"
                    self.console.print_info(
                        "Auto-detected template mode (profile provided)"
                    )
                else:
                    mode = "full"
                    self.console.print_info(
                        "Auto-detected full mode (no profile provided)"
                    )

            # Validate mode and profile combination
            if mode == "template" and not profile:
                self.console.print_error("Template mode requires a keyboard profile")
                self.console.print_error(
                    "Use --profile to specify keyboard (e.g., --profile glove80/v25.05) or use --mode full"
                )
                raise typer.Exit(1)

            # Validate method parameter
            if method not in ["ast", "regex"]:
                self.console.print_error(f"Invalid parsing method: {method}")
                self.console.print_error("Valid methods: ast, regex")
                raise typer.Exit(1)

            # Get profile from context
            from glovebox.cli.helpers.profile import get_keyboard_profile_from_context

            keyboard_profile = get_keyboard_profile_from_context(ctx)

            # Create keymap parser
            from glovebox.layout import create_zmk_keymap_parser
            from glovebox.layout.parsers.models import ParsingMethod, ParsingMode

            keymap_parser = create_zmk_keymap_parser()

            # Convert string modes to enum values
            parsing_mode = (
                ParsingMode.TEMPLATE_AWARE if mode == "template" else ParsingMode.FULL
            )
            parsing_method = (
                ParsingMethod.AST if method == "ast" else ParsingMethod.REGEX
            )

            # Parse keymap file
            result = keymap_parser.parse_keymap(
                keymap_file=keymap_file,
                mode=parsing_mode,
                profile=keyboard_profile,
                method=parsing_method,
            )

            if not result.success:
                self.console.print_error("Keymap parsing failed:")
                for error in result.errors:
                    self.console.print_error(f"  • {error}")
                raise typer.Exit(1)

            # Save the parsed layout data to output file
            if result.layout_data:
                from glovebox.adapters import create_file_adapter

                file_adapter = create_file_adapter()
                file_adapter.write_json(output_file, result.layout_data.to_dict())

            # Show success message
            self.console.print_success(f"Successfully imported keymap as '{name}'")
            self.console.print_info(f"Saved to: {output_file}")

            # Show parsing details
            for warning in result.warnings:
                self.console.print_info(f"  • {warning}")

        except Exception as e:
            self.handle_service_error(e, "import keymap")


@handle_errors
@with_profile(required=False, firmware_optional=True)
@with_metrics("parse_keymap")
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
    ] = "auto",
    method: Annotated[
        str,
        typer.Option(
            "--method",
            help="Parsing method: 'ast' for AST-based parsing, 'regex' for legacy regex parsing",
        ),
    ] = "ast",
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
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose", "-v", help="Show detailed parsing information and debug output"
        ),
    ] = False,
) -> None:
    """Parse ZMK keymap file to JSON layout format.

    Converts .keymap files back to glovebox JSON layout format for editing and management.

    Parsing modes:
    - auto: Automatically chooses between full and template mode (default)
    - full: Parses complete keymap structure including all behaviors and custom code
    - template: Uses keyboard profile templates to extract only user data

    Parsing methods:
    - ast: Uses AST-based parsing for accurate structure extraction (default)
    - regex: Uses legacy regex-based parsing for compatibility

    Examples:
        # Parse with automatic mode detection (recommended)
        glovebox layout parse-keymap my_keymap.keymap

        # Parse Glove80 keymap using template-aware mode
        glovebox layout parse-keymap my_keymap.keymap --profile glove80/v25.05 --mode template

        # Full parsing mode with AST method
        glovebox layout parse-keymap third_party.keymap --mode full --method ast
    """
    command = ParseKeymapCommand()
    command.execute(
        ctx=ctx,
        keymap_file=keymap_file,
        profile=profile,
        mode=mode,
        method=method,
        output=output,
        output_format=output_format,
        force=force,
        verbose=verbose,
    )


@handle_errors
@with_profile(required=False, firmware_optional=True)
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
    ] = "auto",
    method: Annotated[
        str,
        typer.Option(
            "--method",
            help="Parsing method: 'ast' for AST-based parsing, 'regex' for legacy regex parsing",
        ),
    ] = "ast",
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
    command = ImportKeymapCommand()
    command.execute(
        ctx=ctx,
        keymap_file=keymap_file,
        profile=profile,
        name=name,
        mode=mode,
        method=method,
        output_dir=output_dir,
        force=force,
    )


# Create typer app for parsing commands
app = typer.Typer(name="parse", help="Keymap parsing commands")
app.command("keymap")(parse_keymap)
app.command("import")(import_keymap)


def register_parsing_commands(parent_app: typer.Typer) -> None:
    """Register parsing commands with parent app."""
    parent_app.add_typer(app, name="parse")
