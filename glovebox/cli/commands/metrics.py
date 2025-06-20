"""Metrics CLI commands for viewing and managing application metrics."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from glovebox.core.logging import get_logger
from glovebox.metrics import create_metrics_service
from glovebox.metrics.models import OperationType


logger = get_logger(__name__)
console = Console()

metrics_app = typer.Typer(
    name="metrics",
    help="View and manage application metrics",
    no_args_is_help=True,
)


def format_duration(seconds: float | None) -> str:
    """Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string
    """
    if seconds is None:
        return "N/A"

    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def format_success_rate(rate: float | None) -> str:
    """Format success rate as percentage.

    Args:
        rate: Success rate as decimal (0.0-1.0)

    Returns:
        Formatted percentage string
    """
    if rate is None:
        return "N/A"
    return f"{rate * 100:.1f}%"


def format_datetime(dt: datetime | None) -> str:
    """Format datetime for display.

    Args:
        dt: Datetime to format

    Returns:
        Formatted datetime string
    """
    if dt is None:
        return "N/A"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


@metrics_app.command("show")
def show_metrics(
    operation_type: OperationType | None = typer.Option(
        None, "--type", "-t", help="Filter by operation type"
    ),
    limit: int = typer.Option(
        10, "--limit", "-l", help="Maximum number of records to show"
    ),
    days: int | None = typer.Option(
        None, "--days", "-d", help="Show metrics from last N days"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
) -> None:
    """Show recent operation metrics."""
    try:
        metrics_service = create_metrics_service()

        # Calculate time filter
        start_time = None
        if days is not None:
            start_time = datetime.now() - timedelta(days=days)

        # Get metrics
        metrics = metrics_service.get_operation_metrics(
            operation_type=operation_type,
            start_time=start_time,
            limit=limit,
        )

        if json_output:
            # Output as JSON
            metrics_data = [metric.to_dict() for metric in metrics]
            console.print(json.dumps(metrics_data, indent=2, default=str))
            return

        if not metrics:
            console.print("[yellow]No metrics found matching the criteria.[/yellow]")
            return

        # Create table
        table = Table(title=f"Recent Operation Metrics ({len(metrics)} records)")
        table.add_column("Operation", style="cyan")
        table.add_column("Type", style="blue")
        table.add_column("Status", style="green")
        table.add_column("Duration", style="magenta")
        table.add_column("Profile", style="yellow")
        table.add_column("Started", style="dim")

        for metric in metrics:
            # Handle enum values that might be stored as strings
            status_value = (
                metric.status.value
                if hasattr(metric.status, "value")
                else str(metric.status)
            )
            operation_type_value = (
                metric.operation_type.value
                if hasattr(metric.operation_type, "value")
                else str(metric.operation_type)
            )

            status_style = "green" if status_value == "success" else "red"

            table.add_row(
                metric.operation_id[:8] + "...",
                operation_type_value,
                f"[{status_style}]{status_value}[/{status_style}]",
                format_duration(metric.duration_seconds),
                metric.profile_name or "N/A",
                format_datetime(metric.start_time),
            )

        console.print(table)

    except Exception as e:
        exc_info = logger.isEnabledFor(logging.DEBUG)
        logger.error("Failed to show metrics: %s", e, exc_info=exc_info)
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e


@metrics_app.command("summary")
def show_summary(
    days: int | None = typer.Option(
        7, "--days", "-d", help="Show summary for last N days"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
) -> None:
    """Show metrics summary statistics."""
    try:
        metrics_service = create_metrics_service()

        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days) if days else None

        # Generate summary
        summary = metrics_service.generate_summary(
            start_time=start_time,
            end_time=end_time,
        )

        if json_output:
            console.print(json.dumps(summary.to_dict(), indent=2, default=str))
            return

        # Display summary table
        table = Table(title=f"Metrics Summary (Last {days} days)")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Total Operations", str(summary.total_operations))
        table.add_row("Successful Operations", str(summary.successful_operations))
        table.add_row("Failed Operations", str(summary.failed_operations))
        table.add_row(
            "Overall Success Rate",
            format_success_rate(
                summary.successful_operations / summary.total_operations
                if summary.total_operations > 0
                else None
            ),
        )

        # Operation-specific success rates
        if summary.layout_success_rate is not None:
            table.add_row(
                "Layout Success Rate", format_success_rate(summary.layout_success_rate)
            )

        if summary.firmware_success_rate is not None:
            table.add_row(
                "Firmware Success Rate",
                format_success_rate(summary.firmware_success_rate),
            )

        if summary.flash_success_rate is not None:
            table.add_row(
                "Flash Success Rate", format_success_rate(summary.flash_success_rate)
            )

        # Performance metrics
        table.add_row(
            "Average Duration", format_duration(summary.average_duration_seconds)
        )
        table.add_row(
            "Median Duration", format_duration(summary.median_duration_seconds)
        )
        table.add_row(
            "Fastest Operation", format_duration(summary.fastest_operation_seconds)
        )
        table.add_row(
            "Slowest Operation", format_duration(summary.slowest_operation_seconds)
        )

        # Cache metrics
        if summary.cache_hit_rate is not None:
            table.add_row("Cache Hit Rate", format_success_rate(summary.cache_hit_rate))
            table.add_row(
                "Cache-Enabled Operations", str(summary.cache_enabled_operations)
            )

        console.print(table)

        # Show error breakdown if there are errors
        if summary.error_breakdown:
            console.print("\n")
            error_table = Table(title="Error Breakdown")
            error_table.add_column("Error Category", style="red")
            error_table.add_column("Count", style="yellow")

            for error_category, count in summary.error_breakdown.items():
                # Handle enum values that might be stored as strings
                error_category_value = (
                    error_category.value
                    if hasattr(error_category, "value")
                    else str(error_category)
                )
                error_table.add_row(error_category_value, str(count))

            console.print(error_table)

    except Exception as e:
        exc_info = logger.isEnabledFor(logging.DEBUG)
        logger.error("Failed to show summary: %s", e, exc_info=exc_info)
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e


@metrics_app.command("export")
def export_metrics(
    output_file: Path = typer.Argument(
        ..., help="Output file path for exported metrics"
    ),
    days: int | None = typer.Option(
        None, "--days", "-d", help="Export metrics from last N days (default: all)"
    ),
    operation_type: OperationType | None = typer.Option(
        None, "--type", "-t", help="Filter by operation type"
    ),
) -> None:
    """Export metrics data to JSON file."""
    try:
        metrics_service = create_metrics_service()

        # Calculate time range
        start_time = None
        end_time = None
        if days is not None:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)

        # Export metrics
        snapshot = metrics_service.export_metrics(
            output_file=output_file,
            start_time=start_time,
            end_time=end_time,
        )

        console.print(
            f"[green]Exported {snapshot.total_operations} metrics to {output_file}[/green]"
        )

        if snapshot.summary:
            console.print(
                f"Time range: {format_datetime(snapshot.date_range_start)} to {format_datetime(snapshot.date_range_end)}"
            )
            console.print(
                f"Success rate: {format_success_rate(snapshot.summary.successful_operations / snapshot.summary.total_operations if snapshot.summary.total_operations > 0 else None)}"
            )

    except Exception as e:
        exc_info = logger.isEnabledFor(logging.DEBUG)
        logger.error("Failed to export metrics: %s", e, exc_info=exc_info)
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e


@metrics_app.command("clear")
def clear_metrics(
    days: int | None = typer.Option(
        None, "--older-than", help="Clear metrics older than N days"
    ),
    operation_type: OperationType | None = typer.Option(
        None, "--type", "-t", help="Clear metrics of specific operation type"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
) -> None:
    """Clear stored metrics data."""
    try:
        metrics_service = create_metrics_service()

        # Get current count
        current_count = metrics_service.get_metrics_count()

        if current_count == 0:
            console.print("[yellow]No metrics to clear.[/yellow]")
            return

        # Determine what will be cleared
        if days is not None:
            before_time = datetime.now() - timedelta(days=days)
            description = f"metrics older than {days} days"
        elif operation_type is not None:
            before_time = None
            # Handle enum values that might be stored as strings
            operation_type_value = (
                operation_type.value
                if hasattr(operation_type, "value")
                else str(operation_type)
            )
            description = f"all {operation_type_value} metrics"
        else:
            before_time = None
            description = "all metrics"

        # Confirm action
        if not force:
            confirm = typer.confirm(
                f"Clear {description}? ({current_count} total metrics)"
            )
            if not confirm:
                console.print("[yellow]Cancelled.[/yellow]")
                return

        # Clear metrics
        deleted_count = metrics_service.clear_metrics(
            before_time=before_time,
            operation_type=operation_type,
        )

        console.print(f"[green]Cleared {deleted_count} metrics.[/green]")

    except Exception as e:
        exc_info = logger.isEnabledFor(logging.DEBUG)
        logger.error("Failed to clear metrics: %s", e, exc_info=exc_info)
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e


@metrics_app.command("count")
def show_count() -> None:
    """Show total count of stored metrics."""
    try:
        metrics_service = create_metrics_service()
        count = metrics_service.get_metrics_count()

        console.print(f"Total metrics stored: [green]{count}[/green]")

    except Exception as e:
        exc_info = logger.isEnabledFor(logging.DEBUG)
        logger.error("Failed to get metrics count: %s", e, exc_info=exc_info)
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e


def register_commands(app: typer.Typer) -> None:
    """Register metrics commands with the main app.

    Args:
        app: Main typer application
    """
    app.add_typer(metrics_app, name="metrics")
