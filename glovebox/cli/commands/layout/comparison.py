"""Layout comparison CLI commands."""

import logging
from pathlib import Path
from typing import Annotated, Any

import typer

from glovebox.adapters import create_file_adapter
from glovebox.cli.core.command_base import IOCommand
from glovebox.cli.decorators import handle_errors, with_metrics
from glovebox.cli.helpers.parameter_factory import ParameterFactory
from glovebox.layout.comparison import create_layout_comparison_service


@handle_errors
@with_metrics("diff")
def diff(
    ctx: typer.Context,
    layout1: Annotated[
        str,
        typer.Argument(
            help="First layout file, @library-ref, '-' for stdin, or env:GLOVEBOX_JSON_FILE"
        ),
    ],
    layout2: Annotated[
        str, typer.Argument(help="Second layout file to compare or @library-name/uuid")
    ],
    output: Annotated[
        str | None,
        typer.Option(
            "--output", "-o", help="Create LayoutDiff patch file for later application"
        ),
    ] = None,
    detailed: Annotated[
        bool,
        typer.Option("--detailed", help="Show detailed key changes within layers"),
    ] = False,
    include_dtsi: Annotated[
        bool,
        typer.Option(
            "--include-dtsi", help="Include custom DTSI fields in diff output"
        ),
    ] = False,
    patch_section: Annotated[
        str,
        typer.Option(
            "--patch-section",
            help="DTSI section for patch: behaviors, devicetree, or both",
        ),
    ] = "both",
    format: Annotated[
        str,
        typer.Option("--format", help="Output format: text, json, table"),
    ] = "text",
) -> None:
    """Compare two layouts showing differences with optional patch creation.

    Examples:
        glovebox layout diff my-layout-v42.json my-layout-v41.json
        glovebox layout diff @my-layout layout2.json --detailed
        glovebox layout diff layout2.json layout1.json --output changes.json
        export GLOVEBOX_JSON_FILE=my-layout.json
        glovebox layout diff - layout2.json
    """
    command = DiffLayoutCommand()
    command.execute(
        ctx, layout1, layout2, output, detailed, include_dtsi, patch_section, format
    )


@handle_errors
@with_metrics("patch")
def patch(
    ctx: typer.Context,
    layout_file: Annotated[
        str,
        typer.Argument(
            help="Source layout file to patch, @library-ref, or '-' for stdin"
        ),
    ],
    patch_file: Annotated[
        str,
        typer.Argument(
            help="JSON diff file from 'glovebox layout diff --output changes.json'"
        ),
    ],
    output: Annotated[
        str | None,
        typer.Option(
            "--output", "-o", help="Create LayoutDiff patch file for later application"
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force", "-f", help="Overwrite existing files without prompting"
        ),
    ] = False,
    exclude_dtsi: Annotated[
        bool,
        typer.Option(
            "--exclude-dtsi", help="Exclude DTSI changes even if present in patch"
        ),
    ] = False,
) -> None:
    """Apply a JSON diff patch to transform a layout.

    Examples:
        # Generate a diff
        glovebox layout diff old.json new.json --output changes.json

        # Apply the diff to transform another layout
        glovebox layout patch my-layout.json changes.json --output patched-layout.json

        # Apply diff with auto-generated output name
        glovebox layout patch my-layout.json changes.json
    """
    command = PatchLayoutCommand()
    command.execute(ctx, layout_file, patch_file, output, force, exclude_dtsi)


class DiffLayoutCommand(IOCommand):
    """Command to compare two layouts showing differences."""

    def execute(
        self,
        ctx: typer.Context,
        layout1: str,
        layout2: str,
        output: str | None,
        detailed: bool,
        include_dtsi: bool,
        patch_section: str,
        format: str,
    ) -> None:
        """Execute the diff layout command."""
        try:
            # Load both layout files
            layout1_data = self.load_json_input(layout1)
            layout2_data = self.load_json_input(layout2)

            # Create comparison service
            user_config = self._get_user_config(ctx)
            file_adapter = create_file_adapter()
            comparison_service = create_layout_comparison_service(
                user_config, file_adapter
            )

            # Perform comparison using temp files
            result = self._compare_with_temp_files(
                layout1_data,
                layout2_data,
                comparison_service,
                format,
                include_dtsi,
                detailed,
            )

            # Handle patch file creation if requested
            if output:
                result["diff_file_created"] = self._create_patch_file(
                    layout1_data, layout2_data, comparison_service, output, include_dtsi
                )

            self._handle_diff_result(result, format, output)

        except Exception as e:
            self.handle_service_error(e, "compare layouts")

    def _get_user_config(self, ctx: typer.Context) -> Any:
        """Get user config from context."""
        from glovebox.cli.helpers.profile import get_user_config_from_context
        from glovebox.config import create_user_config

        return get_user_config_from_context(ctx) or create_user_config()

    def _compare_with_temp_files(
        self,
        layout1_data: dict[str, Any],
        layout2_data: dict[str, Any],
        service: Any,
        format: str,
        include_dtsi: bool,
        detailed: bool,
    ) -> dict[str, Any]:
        """Compare layouts using temporary files."""
        import json
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f1:
            f1.write(json.dumps(layout1_data))
            temp_path1 = Path(f1.name)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f2:
            f2.write(json.dumps(layout2_data))
            temp_path2 = Path(f2.name)

        try:
            result = service.compare_layouts(
                layout1_path=temp_path1,
                layout2_path=temp_path2,
                output_format=format,
                include_dtsi=include_dtsi,
                detailed=detailed,
            )
            # Ensure we return a dict[str, Any]
            return dict(result) if result else {}
        finally:
            temp_path1.unlink(missing_ok=True)
            temp_path2.unlink(missing_ok=True)

    def _create_patch_file(
        self,
        layout1_data: dict[str, Any],
        layout2_data: dict[str, Any],
        service: Any,
        output: str,
        include_dtsi: bool,
    ) -> str:
        """Create patch file from comparison."""
        import json
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f1:
            f1.write(json.dumps(layout1_data))
            temp_path1 = Path(f1.name)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f2:
            f2.write(json.dumps(layout2_data))
            temp_path2 = Path(f2.name)

        try:
            # Use IOCommand validate_output_path for path handling
            output_path = Path(output)
            self.validate_output_path(output_path, force=True)

            # Create parent directories if needed
            output_path.parent.mkdir(parents=True, exist_ok=True)

            service.create_diff_file(
                layout1_path=temp_path1,
                layout2_path=temp_path2,
                output_path=output_path,
                include_dtsi=include_dtsi,
            )
            return str(output_path)
        finally:
            temp_path1.unlink(missing_ok=True)
            temp_path2.unlink(missing_ok=True)

    def _handle_diff_result(
        self, result: dict[str, Any], format: str, output: str | None
    ) -> None:
        """Handle diff result output."""
        if format == "json":
            self.format_and_print(result, "json")
        elif format == "table":
            self._format_table_output(result)
        else:
            self._format_text_output(result, output)

    def _format_table_output(self, result: dict[str, Any]) -> None:
        """Format table output for diff results."""
        changes_list = []
        if "layer_changes" in result:
            for change in result["layer_changes"]:
                changes_list.append(
                    {
                        "Type": "Layer",
                        "Change": change.get("type", "unknown"),
                        "Details": change.get("description", ""),
                    }
                )
        if "behavior_changes" in result:
            for change in result["behavior_changes"]:
                changes_list.append(
                    {
                        "Type": "Behavior",
                        "Change": change.get("type", "unknown"),
                        "Details": change.get("description", ""),
                    }
                )
        self.format_and_print(changes_list, "table")

    def _format_text_output(self, result: dict[str, Any], output: str | None) -> None:
        """Format text output for diff results."""
        if result.get("has_changes", False):
            self.console.print_info("Layout differences found:")
            self._print_summary(result.get("summary"))
            if output and "diff_file_created" in result:
                self.console.print_success(
                    f"Diff file created: {result['diff_file_created']}"
                )
        else:
            self.console.print_success("No differences found between layouts")

    def _print_summary(self, summary: Any) -> None:
        """Print summary information."""
        if isinstance(summary, dict):
            for category, stats in summary.items():
                if isinstance(stats, dict):
                    if any(isinstance(v, dict) for v in stats.values()):
                        for subcat, substats in stats.items():
                            if isinstance(substats, dict):
                                for change_type, count in substats.items():
                                    if isinstance(count, int) and count > 0:
                                        self.console.print_info(
                                            f"  {category}/{subcat} {change_type}: {count}"
                                        )
                    else:
                        for change_type, count in stats.items():
                            if isinstance(count, int) and count > 0:
                                self.console.print_info(
                                    f"  {category} {change_type}: {count}"
                                )
                elif isinstance(stats, int) and stats > 0:
                    self.console.print_info(f"  {category}: {stats}")
        else:
            for line in str(summary).split("\n"):
                self.console.print_info(f"  {line}")

    def handle_service_error(self, error: Exception, operation: str) -> None:
        """Handle service layer errors with consistent messaging."""
        exc_info = self.logger.isEnabledFor(logging.DEBUG)
        self.logger.error("Failed to %s: %s", operation, error, exc_info=exc_info)
        self.console.print_error(f"Failed to {operation}: {error}")
        raise typer.Exit(1) from error


class PatchLayoutCommand(IOCommand):
    """Command to apply patches to layouts."""

    def execute(
        self,
        ctx: typer.Context,
        layout_file: str,
        patch_file: str,
        output: str | None,
        force: bool,
        exclude_dtsi: bool,
    ) -> None:
        """Execute the patch layout command."""
        try:
            # Load layout and patch files
            layout_data = self.load_json_input(layout_file)
            patch_data = self.load_json_input(patch_file)

            # Create comparison service
            user_config = self._get_user_config(ctx)
            file_adapter = create_file_adapter()
            comparison_service = create_layout_comparison_service(
                user_config, file_adapter
            )

            # Determine output path
            if output is None:
                layout_title = layout_data.get("title", "layout")
                output = f"{layout_title}-patched.json"

            # Apply patch using temp files
            result = self._apply_patch_with_temp_files(
                layout_data, patch_data, comparison_service, output, force, exclude_dtsi
            )

            self._handle_patch_success(result, output)

        except Exception as e:
            self.handle_service_error(e, "apply patch")

    def _get_user_config(self, ctx: typer.Context) -> Any:
        """Get user config from context."""
        from glovebox.cli.helpers.profile import get_user_config_from_context
        from glovebox.config import create_user_config

        return get_user_config_from_context(ctx) or create_user_config()

    def _apply_patch_with_temp_files(
        self,
        layout_data: dict[str, Any],
        patch_data: dict[str, Any],
        service: Any,
        output: str,
        force: bool,
        exclude_dtsi: bool,
    ) -> dict[str, Any]:
        """Apply patch using temporary files."""
        import json
        import tempfile

        from glovebox.cli.helpers.parameter_helpers import process_output_parameter

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f1:
            f1.write(json.dumps(layout_data))
            temp_layout_path = Path(f1.name)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f2:
            f2.write(json.dumps(patch_data))
            temp_patch_path = Path(f2.name)

        try:
            output_result = process_output_parameter(
                value=output,
                supports_stdout=False,
                force_overwrite=force,
                create_dirs=True,
            )

            patch_result = service.apply_patch(
                source_layout_path=temp_layout_path,
                patch_file_path=temp_patch_path,
                output=Path(output_result.resolved_path)
                if output_result.resolved_path
                else Path(output),
                force=force,
                skip_dtsi=exclude_dtsi,
            )
            # Ensure we return a dict[str, Any]
            result = dict(patch_result) if patch_result else {}
            result["output_path"] = (
                str(output_result.resolved_path)
                if output_result.resolved_path
                else output
            )
            return result
        finally:
            temp_layout_path.unlink(missing_ok=True)
            temp_patch_path.unlink(missing_ok=True)

    def _handle_patch_success(self, result: dict[str, Any], output: str) -> None:
        """Handle successful patch application."""
        self.console.print_success("Applied patch successfully")
        self.console.print_info(f"  Output: {result.get('output_path', output)}")
        if "changes_applied" in result:
            self.console.print_info(f"  Applied changes: {result['changes_applied']}")

    def handle_service_error(self, error: Exception, operation: str) -> None:
        """Handle service layer errors with consistent messaging."""
        exc_info = self.logger.isEnabledFor(logging.DEBUG)
        self.logger.error("Failed to %s: %s", operation, error, exc_info=exc_info)
        self.console.print_error(f"Failed to {operation}: {error}")
        raise typer.Exit(1) from error
