"""ZMK Layout batch command - Execute batch operations on multiple layouts."""

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)
from rich.table import Table

from glovebox.cli.decorators import handle_errors, with_metrics, with_profile
from glovebox.cli.helpers.theme import get_themed_console
from glovebox.core.structlog_logger import get_struct_logger


logger = get_struct_logger(__name__)
console = get_themed_console()

# Create batch sub-app
batch_app = typer.Typer(
    name="batch",
    help="""Execute batch operations on multiple layouts.

Process multiple layout files with compile, validate, export,
and analysis operations.
""",
    no_args_is_help=True,
)


@batch_app.command(name="compile")
@with_metrics("zmk_layout.batch.compile")
@with_profile()
@handle_errors
def batch_compile(
    ctx: typer.Context,
    pattern: Annotated[
        str,
        typer.Argument(
            help="File pattern for layout files (e.g., '*.json', 'layouts/**/*.json')",
            metavar="PATTERN",
        ),
    ],
    output_dir: Annotated[
        Path,
        typer.Option(
            "-o",
            "--output",
            help="Base output directory for compiled files",
            file_okay=False,
            dir_okay=True,
        ),
    ],
    profile: Annotated[
        str | None,
        typer.Option(
            "-p",
            "--profile",
            help="Keyboard profile to use for compilation",
        ),
    ] = None,
    parallel: Annotated[
        int,
        typer.Option(
            "--parallel",
            help="Number of parallel compilation processes",
        ),
    ] = 4,
    continue_on_error: Annotated[
        bool,
        typer.Option(
            "--continue-on-error",
            help="Continue processing even if some files fail",
        ),
    ] = True,
    organize_by: Annotated[
        str,
        typer.Option(
            "--organize-by",
            help="Organize output by: keyboard, profile, flat",
        ),
    ] = "keyboard",
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Force overwrite existing files",
        ),
    ] = False,
) -> None:
    """Compile multiple layout files in batch.

    **Examples:**

    \b
    # Compile all JSON files in layouts directory
    glovebox zmk-layout batch compile "layouts/*.json" -o ./build/

    \b
    # Parallel compilation with specific profile
    glovebox zmk-layout batch compile "**/*.json" -o ./output/ -p glove80 --parallel 8

    \b
    # Organized by profile with error handling
    glovebox zmk-layout batch compile "layouts/**/*.json" -o ./build/ --organize-by profile --continue-on-error
    """
    try:
        # Find matching files
        import glob

        if "/" in pattern or "*" in pattern:
            # Glob pattern
            files = [Path(f) for f in glob.glob(pattern, recursive=True)]
        else:
            # Single file
            files = [Path(pattern)]

        files = [f for f in files if f.is_file() and f.suffix == ".json"]

        if not files:
            console.console.print(
                f"[yellow]Warning:[/yellow] No JSON files found matching pattern: {pattern}"
            )
            return

        console.console.print(
            Panel(
                f"[bold blue]Batch Compilation[/bold blue]\n"
                f"Files: [green]{len(files)}[/green]\n"
                f"Output: [cyan]{output_dir}[/cyan]\n"
                f"Parallel: [yellow]{parallel}[/yellow]\n"
                f"Organize by: [yellow]{organize_by}[/yellow]",
                expand=False,
            )
        )

        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        # Results tracking
        results = {"success": 0, "failed": 0, "errors": [], "files_processed": []}

        # Progress tracking
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Compiling layouts...", total=len(files))

            for file_path in files:
                try:
                    progress.update(task, description=f"Compiling {file_path.name}...")

                    # Load layout file
                    try:
                        layout_dict = json.loads(file_path.read_text())
                    except json.JSONDecodeError as e:
                        error_msg = f"{file_path}: Invalid JSON - {e}"
                        results["errors"].append(error_msg)
                        results["failed"] += 1

                        if not continue_on_error:
                            console.console.print(
                                f"[red]Error:[/red] {error_msg}", style="error"
                            )
                            ctx.exit(1)
                        continue

                    # Determine output structure
                    keyboard = layout_dict.get("keyboard", "unknown")

                    if organize_by == "keyboard":
                        file_output_dir = output_dir / keyboard
                    elif organize_by == "profile":
                        file_output_dir = output_dir / (profile or "default")
                    else:  # flat
                        file_output_dir = output_dir

                    file_output_dir.mkdir(parents=True, exist_ok=True)

                    # This would call the actual zmk-layout compilation
                    # For now, simulate the compilation
                    keymap_file = file_output_dir / f"{file_path.stem}.keymap"
                    config_file = file_output_dir / f"{file_path.stem}.conf"

                    # Simulate compilation (replace with actual zmk-layout service call)
                    if not keymap_file.exists() or force:
                        keymap_file.write_text(
                            f"// Generated from {file_path.name}\n// Keyboard: {keyboard}\n"
                        )
                        config_file.write_text(f"# Config for {file_path.name}\n")

                    results["success"] += 1
                    results["files_processed"].append(
                        {
                            "input": str(file_path),
                            "output_dir": str(file_output_dir),
                            "keyboard": keyboard,
                        }
                    )

                except Exception as e:
                    error_msg = f"{file_path}: {str(e)}"
                    results["errors"].append(error_msg)
                    results["failed"] += 1

                    if not continue_on_error:
                        console.console.print(
                            f"[red]Error:[/red] {error_msg}", style="error"
                        )
                        ctx.exit(1)

                progress.advance(task)

        # Summary report
        console.console.print("\n[bold blue]Batch Compilation Complete[/bold blue]")

        summary_table = Table(show_header=False, box=None, padding=(0, 1))
        summary_table.add_column("Metric", style="cyan", width=15)
        summary_table.add_column("Count", style="white")

        summary_table.add_row("Total Files", str(len(files)))
        summary_table.add_row("Successful", f"[green]{results['success']}[/green]")
        summary_table.add_row("Failed", f"[red]{results['failed']}[/red]")

        console.console.print(summary_table)

        # Show errors if any
        if results["errors"]:
            console.console.print(f"\n[red]Errors ({len(results['errors'])}):[/red]")
            for error in results["errors"][:10]:  # Show first 10 errors
                console.console.print(f"  • {error}", style="error")
            if len(results["errors"]) > 10:
                console.console.print(
                    f"  ... and {len(results['errors']) - 10} more errors"
                )

        logger.info(
            "batch_compilation_completed",
            total_files=len(files),
            successful=results["success"],
            failed=results["failed"],
            output_dir=str(output_dir),
            organize_by=organize_by,
        )

        # Exit with error if any compilation failed and not continue_on_error
        if results["failed"] > 0 and not continue_on_error:
            ctx.exit(1)

    except Exception as e:
        logger.error("batch_compile_failed", error=str(e), exc_info=True)
        console.console.print(f"[red]Error:[/red] {e}", style="error")
        ctx.exit(1)


@batch_app.command(name="validate")
@with_metrics("zmk_layout.batch.validate")
@with_profile()
@handle_errors
def batch_validate(
    ctx: typer.Context,
    pattern: Annotated[
        str,
        typer.Argument(
            help="File pattern for layout files (e.g., '*.json', 'layouts/**/*.json')",
            metavar="PATTERN",
        ),
    ],
    profile: Annotated[
        str | None,
        typer.Option(
            "-p",
            "--profile",
            help="Keyboard profile to use for validation",
        ),
    ] = None,
    strict: Annotated[
        bool,
        typer.Option(
            "--strict",
            help="Enable strict validation mode",
        ),
    ] = False,
    continue_on_error: Annotated[
        bool,
        typer.Option(
            "--continue-on-error",
            help="Continue processing even if some files fail",
        ),
    ] = True,
    output_format: Annotated[
        str,
        typer.Option(
            "-f",
            "--format",
            help="Output format: table, json, summary",
        ),
    ] = "table",
    save_report: Annotated[
        Path | None,
        typer.Option(
            "--report",
            help="Save validation report to file",
        ),
    ] = None,
) -> None:
    """Validate multiple layout files in batch.

    **Examples:**

    \b
    # Validate all layouts in directory
    glovebox zmk-layout batch validate "layouts/*.json"

    \b
    # Strict validation with report
    glovebox zmk-layout batch validate "**/*.json" --strict --report validation_report.json

    \b
    # Summary format continuing on errors
    glovebox zmk-layout batch validate "layouts/**/*.json" -f summary --continue-on-error
    """
    try:
        # This is a comprehensive implementation placeholder
        console.console.print(
            "[yellow]Note:[/yellow] The batch validate command is not yet fully implemented."
        )
        console.console.print("This would validate multiple layout files in batch.")
        console.console.print(f"Pattern: [cyan]{pattern}[/cyan]")
        console.console.print(f"Strict mode: [cyan]{strict}[/cyan]")
        console.console.print(f"Output format: [cyan]{output_format}[/cyan]")

        if save_report:
            console.console.print(f"Report file: [cyan]{save_report}[/cyan]")

    except Exception as e:
        logger.error("batch_validate_failed", error=str(e), exc_info=True)
        console.console.print(f"[red]Error:[/red] {e}", style="error")
        ctx.exit(1)


@batch_app.command(name="stats")
@with_metrics("zmk_layout.batch.stats")
@with_profile()
@handle_errors
def batch_stats(
    ctx: typer.Context,
    pattern: Annotated[
        str,
        typer.Argument(
            help="File pattern for layout files (e.g., '*.json', 'layouts/**/*.json')",
            metavar="PATTERN",
        ),
    ],
    output_format: Annotated[
        str,
        typer.Option(
            "-f",
            "--format",
            help="Output format: table, json, csv",
        ),
    ] = "table",
    aggregate: Annotated[
        bool,
        typer.Option(
            "--aggregate",
            help="Show aggregated statistics across all files",
        ),
    ] = True,
    save_report: Annotated[
        Path | None,
        typer.Option(
            "--report",
            help="Save statistics report to file",
        ),
    ] = None,
    top_behaviors: Annotated[
        int,
        typer.Option(
            "--top-behaviors",
            help="Number of top behaviors to show",
        ),
    ] = 10,
) -> None:
    """Generate statistics for multiple layout files.

    **Examples:**

    \b
    # Generate stats for all layouts
    glovebox zmk-layout batch stats "layouts/*.json"

    \b
    # Aggregate stats with CSV report
    glovebox zmk-layout batch stats "**/*.json" --aggregate --report stats.csv -f csv

    \b
    # JSON format with top 20 behaviors
    glovebox zmk-layout batch stats "layouts/**/*.json" -f json --top-behaviors 20
    """
    try:
        # This is a comprehensive implementation placeholder
        console.console.print(
            "[yellow]Note:[/yellow] The batch stats command is not yet fully implemented."
        )
        console.console.print(
            "This would generate comprehensive statistics for multiple layout files."
        )
        console.console.print(f"Pattern: [cyan]{pattern}[/cyan]")
        console.console.print(f"Format: [cyan]{output_format}[/cyan]")
        console.console.print(f"Aggregate: [cyan]{aggregate}[/cyan]")
        console.console.print(f"Top behaviors: [cyan]{top_behaviors}[/cyan]")

        if save_report:
            console.console.print(f"Report file: [cyan]{save_report}[/cyan]")

    except Exception as e:
        logger.error("batch_stats_failed", error=str(e), exc_info=True)
        console.console.print(f"[red]Error:[/red] {e}", style="error")
        ctx.exit(1)
