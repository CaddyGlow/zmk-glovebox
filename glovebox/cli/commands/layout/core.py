"""Core layout CLI commands (compile, decompose, compose, validate, show)."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

import typer

from glovebox.cli.commands.layout.base import (
    ProfileAwareLayoutCommand,
)
from glovebox.cli.decorators import (
    handle_errors,
    with_metrics,
    with_profile,
)
from glovebox.core.structlog_logger import get_struct_logger
from glovebox.layout import ViewMode


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile
    from glovebox.layout.service import LayoutService


logger = get_struct_logger(__name__)


class CompileLayoutCommand(ProfileAwareLayoutCommand):
    """Command to compile ZMK keymap and config files from JSON layout."""

    def get_operation_name(self) -> str:
        """Get the operation name for error reporting."""
        return "compile layout"

    def execute(
        self,
        ctx: typer.Context,
        input: str,
        output: str | None,
        profile: str | None,
        no_auto: bool,
        force: bool,
        format: str,
    ) -> None:
        """Execute the compile layout command."""
        self.execute_with_profile(
            ctx, input, no_auto, output=output, force=force, format=format
        )

    def execute_command(
        self,
        layout_data: dict[str, Any],
        keyboard_profile: "KeyboardProfile",
        service: "LayoutService",
        output: str | None = None,
        force: bool = False,
        format: str = "text",
        **kwargs: Any,
    ) -> None:
        """Execute the specific compilation logic."""
        # Compile layout with profile information
        result = service.compile(layout_data, profile=keyboard_profile)

        if result.success:
            # Write output using OutputHandler if output specified
            if output:
                if result.keymap_content:
                    keymap_file = Path(output).with_suffix(".keymap")
                    self.write_output(result.keymap_content, str(keymap_file), "text")
                if result.config_content:
                    config_file = Path(output).with_suffix(".conf")
                    self.write_output(result.config_content, str(config_file), "text")

                self.console.print_success("Layout compiled successfully")
                self.console.print_info(f"  keymap: {keymap_file}")
                self.console.print_info(f"  config: {config_file}")
            else:
                # Output to stdout
                if format == "json":
                    output_data = {
                        "success": True,
                        "keymap_content": result.keymap_content,
                        "config_content": result.config_content,
                    }
                    self.format_and_print(output_data, "json")
                else:
                    self.console.print_success("Layout compiled successfully")
                    if result.keymap_content:
                        # Use the underlying Rich console for raw output
                        self.console.console.print(result.keymap_content)
        else:
            raise ValueError(f"Compilation failed: {'; '.join(result.errors)}")


class ValidateLayoutCommand(ProfileAwareLayoutCommand):
    """Command to validate keymap syntax and structure."""

    def get_operation_name(self) -> str:
        """Get the operation name for error reporting."""
        return "validate layout"

    def execute(
        self,
        ctx: typer.Context,
        input: str,
        profile: str | None,
        no_auto: bool,
        format: str,
    ) -> None:
        """Execute the validate layout command."""
        self.execute_with_profile(ctx, input, no_auto, format=format)

    def execute_command(
        self,
        layout_data: dict[str, Any],
        keyboard_profile: "KeyboardProfile",
        service: "LayoutService",
        format: str = "text",
        **kwargs: Any,
    ) -> None:
        """Execute the specific validation logic."""
        # Convert to LayoutData model and validate
        from glovebox.layout.models import LayoutData

        layout_model = LayoutData.model_validate(layout_data)

        # Perform validation
        errors = []
        is_syntax_valid = service.validate(layout_data)
        if not is_syntax_valid:
            errors.append("Layout syntax/structure validation failed")

        # Validate layer references
        layer_ref_errors = layout_model.validate_layer_references()
        errors.extend(layer_ref_errors)

        is_valid = is_syntax_valid and len(layer_ref_errors) == 0
        result = {"valid": is_valid, "errors": errors}

        self._handle_validation_result(result, format)

    def _handle_validation_result(self, result: dict[str, Any], format: str) -> None:
        """Handle validation result output."""
        if format == "json":
            self.format_and_print(result, "json")
        elif format == "table" and result["errors"]:
            self.format_and_print(result["errors"], "table")
        else:
            if result["valid"]:
                self.console.print_success("Layout is valid")
            else:
                self.console.print_error("Layout validation failed")
                for error in result["errors"]:
                    self.console.print_error(f"  - {error}")
                raise typer.Exit(1)


class ShowLayoutCommand(ProfileAwareLayoutCommand):
    """Command to display keymap layout in terminal."""

    def get_operation_name(self) -> str:
        """Get the operation name for error reporting."""
        return "show layout"

    def execute(
        self,
        ctx: typer.Context,
        input: str,
        key_width: int,
        layer: str | None,
        profile: str | None,
        no_auto: bool,
        format: str,
    ) -> None:
        """Execute the show layout command."""
        self.execute_with_profile(
            ctx, input, no_auto, key_width=key_width, layer=layer, format=format
        )

    def execute_command(
        self,
        layout_data: dict[str, Any],
        keyboard_profile: "KeyboardProfile",
        service: "LayoutService",
        key_width: int = 10,
        layer: str | None = None,
        format: str = "text",
        **kwargs: Any,
    ) -> None:
        """Execute the specific show logic."""
        # Resolve layer parameter
        resolved_layer_index = self._resolve_layer_index(layer, layout_data)

        # Handle different output formats
        if format == "json":
            self.format_and_print(layout_data, "json")
        elif format.startswith("rich"):
            self._handle_rich_format(
                layout_data,
                keyboard_profile,
                key_width,
                resolved_layer_index,
                format,
            )
        else:
            self._handle_text_format(
                layout_data, keyboard_profile, key_width, resolved_layer_index, service
            )

    def _resolve_layer_index(
        self, layer: str | None, layout_data: dict[str, Any]
    ) -> int | None:
        """Resolve layer parameter to index."""
        if layer is None:
            return None

        if layer.isdigit():
            return int(layer)

        # Resolve layer name to index
        layer_names = layout_data.get("layer_names", [])
        layer_lower = layer.lower()
        for i, name in enumerate(layer_names):
            if name.lower() == layer_lower:
                return i

        self.console.print_error(
            f"Layer '{layer}' not found. Available: {', '.join(layer_names)}"
        )
        raise typer.Exit(1)

    def _handle_rich_format(
        self,
        layout_data: dict[str, Any],
        keyboard_profile: "KeyboardProfile",
        key_width: int,
        layer_index: int | None,
        format: str,
    ) -> None:
        """Handle rich format display."""
        from glovebox.layout.formatting import LayoutConfig
        from glovebox.layout.models import LayoutData
        from glovebox.layout.rich_formatter import create_rich_layout_formatter

        layout_model = LayoutData.model_validate(layout_data)
        display_config = keyboard_profile.keyboard_config.display
        keymap_formatting = keyboard_profile.keyboard_config.keymap.formatting

        # Determine row structure
        if keymap_formatting.rows is not None:
            all_rows = keymap_formatting.rows
        elif display_config.layout_structure is not None:
            all_rows = []
            for row_segments in display_config.layout_structure.rows.values():
                combined_row = []
                for segment in row_segments:
                    combined_row.extend(segment)
                all_rows.append(combined_row)
        else:
            # Default rows
            all_rows = [
                [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
                [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21],
                [22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33],
                [34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45],
            ]

        layout_config = LayoutConfig(
            keyboard_name=keyboard_profile.keyboard_config.keyboard,
            key_width=key_width,
            key_gap=keymap_formatting.key_gap,
            key_position_map={},
            total_keys=keyboard_profile.keyboard_config.key_count,
            key_count=keyboard_profile.keyboard_config.key_count,
            rows=all_rows,
            formatting={
                "key_gap": keymap_formatting.key_gap,
                "base_indent": keymap_formatting.base_indent,
            },
        )

        formatter = create_rich_layout_formatter()
        formatter.format_keymap_display(
            layout_model,
            layout_config,
            format_type=format.lower(),
            layer_index=layer_index,
        )

    def _handle_text_format(
        self,
        layout_data: dict[str, Any],
        keyboard_profile: "KeyboardProfile",
        key_width: int,
        layer_index: int | None,
        service: "LayoutService",
    ) -> None:
        """Handle text format display."""
        from glovebox.layout.models import LayoutData

        layout_model = LayoutData.model_validate(layout_data)

        result = service.show(layout_data, mode=ViewMode.NORMAL)

        typer.echo(result)


@handle_errors
@with_profile(required=False, firmware_optional=False, support_auto_detection=True)
@with_metrics("compile")
def compile_layout(
    ctx: typer.Context,
    input: Annotated[
        str,
        typer.Argument(
            help="JSON layout file, @library-ref, '-' for stdin, or env:GLOVEBOX_JSON_FILE"
        ),
    ],
    output: Annotated[
        str | None,
        typer.Option(
            "--output",
            "-o",
            help="Output directory/base filename (e.g., 'config/my_glove80'). Auto-generated if not specified.",
        ),
    ] = None,
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            "-p",
            help="Keyboard profile in format 'keyboard' or 'keyboard/firmware'",
        ),
    ] = None,
    no_auto: Annotated[
        bool,
        typer.Option(
            "--no-auto",
            help="Disable automatic profile detection from JSON keyboard field",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force", "-f", help="Overwrite existing files without prompting"
        ),
    ] = False,
    format: Annotated[
        str,
        typer.Option("--format", help="Output format: text, json"),
    ] = "text",
) -> None:
    """Compile ZMK keymap and config files from a JSON keymap file.

    Examples:
        glovebox layout compile layout.json -o output/glove80
        glovebox layout compile @my-gaming-layout
        cat layout.json | glovebox layout compile -
        glovebox layout compile - --profile glove80/v25.05 < layout.json
    """
    command = CompileLayoutCommand()
    command.execute(ctx, input, output, profile, no_auto, force, format)


@handle_errors
@with_profile(required=True, firmware_optional=False, support_auto_detection=True)
@with_metrics("validate")
def validate(
    ctx: typer.Context,
    input: Annotated[
        str,
        typer.Argument(
            help="JSON layout file, @library-ref, '-' for stdin, or env:GLOVEBOX_JSON_FILE"
        ),
    ],
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            "-p",
            help="Keyboard profile in format 'keyboard' or 'keyboard/firmware'",
        ),
    ] = None,
    no_auto: Annotated[
        bool,
        typer.Option(
            "--no-auto",
            help="Disable automatic profile detection from JSON keyboard field",
        ),
    ] = False,
    format: Annotated[
        str,
        typer.Option("--format", help="Output format: text, json, table"),
    ] = "text",
) -> None:
    """Validate keymap syntax and structure.

    Examples:
        glovebox layout validate my-layout.json
        glovebox layout validate @my-gaming-layout
        glovebox layout validate @12345678-1234-1234-1234-123456789abc
        cat layout.json | glovebox layout validate -
    """
    command = ValidateLayoutCommand()
    command.execute(ctx, input, profile, no_auto, format)


@handle_errors
@with_profile(required=False, firmware_optional=True, support_auto_detection=True)
@with_metrics("show")
def show(
    ctx: typer.Context,
    input: Annotated[
        str,
        typer.Argument(
            help="JSON layout file, @library-ref, '-' for stdin, or env:GLOVEBOX_JSON_FILE"
        ),
    ],
    key_width: Annotated[
        int,
        typer.Option(
            "--key-width", "-w", help="Width of each key in display", min=1, max=30
        ),
    ] = 10,
    layer: Annotated[
        str | None,
        typer.Option("--layer", "-l", help="Layer index or name to display"),
    ] = None,
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            "-p",
            help="Keyboard profile in format 'keyboard' or 'keyboard/firmware'",
        ),
    ] = None,
    no_auto: Annotated[
        bool,
        typer.Option(
            "--no-auto",
            help="Disable automatic profile detection from JSON keyboard field",
        ),
    ] = False,
    format: Annotated[
        str,
        typer.Option("--format", help="Output format: text, json, rich"),
    ] = "text",
) -> None:
    """Display keymap layout in terminal.

    Examples:
        glovebox layout show my-layout.json
        glovebox layout show @my-gaming-layout
        glovebox layout show @my-layout --layer 2
        glovebox layout show layout.json --format rich
    """
    command = ShowLayoutCommand()
    command.execute(ctx, input, key_width, layer, profile, no_auto, format)
