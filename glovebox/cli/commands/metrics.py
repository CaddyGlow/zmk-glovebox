"""Metrics management CLI commands."""

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from glovebox.cli.decorators import handle_errors
from glovebox.cli.helpers import print_error_message, print_success_message
from glovebox.cli.helpers.theme import Icons
from glovebox.config.user_config import create_user_config
from glovebox.core.cache_v2 import create_default_cache
from glovebox.core.cache_v2.cache_manager import CacheManager
from glovebox.metrics.session_metrics import create_session_metrics


logger = logging.getLogger(__name__)
console = Console()

metrics_app = typer.Typer(help="Metrics management commands")


def _get_metrics_cache_manager() -> CacheManager:
    """Get cache manager for metrics using shared cache coordination."""
    return create_default_cache(tag="metrics")


def _format_duration(seconds: float) -> str:
    """Format duration in human readable format."""
    if seconds < 1:
        return f"{seconds:.3f}s"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def _find_session_by_prefix(prefix: str) -> str | None:
    """Find a unique session UUID by prefix, similar to Docker container IDs.

    Args:
        prefix: The UUID prefix to match

    Returns:
        The full UUID if a unique match is found, None otherwise

    Raises:
        ValueError: If prefix matches multiple sessions (ambiguous)
    """
    cache_manager = _get_metrics_cache_manager()
    all_keys = list(cache_manager.keys())
    session_keys = [
        key
        for key in all_keys
        if not key.startswith("metrics:") and len(key) == 36 and key.count("-") == 4
    ]

    # Find all keys that start with the prefix
    matches = [key for key in session_keys if key.startswith(prefix)]

    if len(matches) == 0:
        return None
    elif len(matches) == 1:
        return matches[0]
    else:
        # Multiple matches - this is ambiguous
        raise ValueError(
            f"Ambiguous session ID '{prefix}' matches {len(matches)} sessions: {', '.join(matches[:5])}{'...' if len(matches) > 5 else ''}"
        )


def _complete_session_uuid(incomplete: str) -> list[str]:
    """Tab completion for session UUIDs.

    Args:
        incomplete: The incomplete UUID prefix

    Returns:
        List of matching UUIDs
    """
    try:
        cache_manager = _get_metrics_cache_manager()
        all_keys = list(cache_manager.keys())
        session_keys = [
            key
            for key in all_keys
            if not key.startswith("metrics:") and len(key) == 36 and key.count("-") == 4
        ]

        # Return all keys that start with the incomplete string
        matches = [key for key in session_keys if key.startswith(incomplete)]
        return sorted(matches)
    except Exception:
        # If completion fails, return empty list
        return []


def _format_timestamp(iso_timestamp: str) -> str:
    """Format ISO timestamp for display."""
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        now = datetime.now(dt.tzinfo)
        diff = now - dt

        if diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours}h ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes}m ago"
        else:
            return "just now"
    except Exception:
        return iso_timestamp


@metrics_app.command("list")
@handle_errors
def list_sessions(
    ctx: typer.Context,
    json_output: Annotated[
        bool, typer.Option("--json", help="Output in JSON format")
    ] = False,
    limit: Annotated[
        int, typer.Option("--limit", "-n", help="Limit number of sessions shown")
    ] = 10,
) -> None:
    """List recent metrics sessions."""
    cache_manager = _get_metrics_cache_manager()

    try:
        # Get all cache keys (session UUIDs)
        all_keys = list(cache_manager.keys())
        # SessionMetrics are stored with plain UUID keys (36 chars with hyphens)
        # Filter out old metrics system keys that start with "metrics:"
        session_keys = [
            key
            for key in all_keys
            if not key.startswith("metrics:") and len(key) == 36 and key.count("-") == 4
        ]

        if not session_keys:
            if not json_output:
                console.print("[yellow]No metrics sessions found.[/yellow]")
            else:
                print(json.dumps({"sessions": [], "total": 0}))
            return

        # Get session data for each key
        sessions = []
        for key in session_keys:
            try:
                data = cache_manager.get(key)
                if data and isinstance(data, dict) and "session_info" in data:
                    session_info = data["session_info"]
                    metadata = cache_manager.get_metadata(key)

                    session = {
                        "uuid": key,
                        "session_id": session_info.get("session_id", "unknown"),
                        "start_time": session_info.get("start_time", "unknown"),
                        "end_time": session_info.get("end_time", "unknown"),
                        "duration_seconds": session_info.get("duration_seconds", 0),
                        "exit_code": session_info.get("exit_code"),
                        "success": session_info.get("success"),
                        "cli_args": session_info.get("cli_args", []),
                        "created_at": metadata.created_at if metadata else None,
                        "metrics_count": {
                            "counters": len(data.get("counters", {})),
                            "gauges": len(data.get("gauges", {})),
                            "histograms": len(data.get("histograms", {})),
                            "summaries": len(data.get("summaries", {})),
                        },
                    }
                    sessions.append(session)
            except Exception as e:
                logger.debug("Failed to load session %s: %s", key, e)
                continue

        # Sort by start time (most recent first)
        sessions.sort(key=lambda s: s.get("start_time", ""), reverse=True)

        # Apply limit
        if limit > 0:
            sessions = sessions[:limit]

        if json_output:
            output_data = {
                "sessions": sessions,
                "total": len(sessions),
                "timestamp": datetime.now().isoformat(),
            }
            print(json.dumps(output_data, indent=2, ensure_ascii=False))
        else:
            # Display table
            table = Table(title="Recent Metrics Sessions")
            table.add_column("UUID", style="cyan")
            table.add_column("Started", style="blue")
            table.add_column("Duration", style="green")
            table.add_column("Status", style="bold")
            table.add_column("Command", style="white")
            table.add_column("Metrics", style="yellow")

            for session in sessions:
                # Format status
                exit_code = session.get("exit_code")
                if exit_code is None:
                    status = "[yellow]Running[/yellow]"
                elif exit_code == 0:
                    status = "[green]Success[/green]"
                else:
                    status = f"[red]Error ({exit_code})[/red]"

                # Format command (first few args)
                cli_args = session.get("cli_args", [])
                if cli_args:
                    if len(cli_args) > 3:
                        command = " ".join(cli_args[1:4]) + "..."
                    else:
                        command = (
                            " ".join(cli_args[1:]) if len(cli_args) > 1 else "glovebox"
                        )
                else:
                    command = "unknown"

                # Format metrics count
                metrics = session.get("metrics_count", {})
                metrics_str = f"C:{metrics.get('counters', 0)} G:{metrics.get('gauges', 0)} H:{metrics.get('histograms', 0)} S:{metrics.get('summaries', 0)}"

                table.add_row(
                    session.get("uuid", "unknown")[:12],
                    _format_timestamp(session.get("start_time", "")),
                    _format_duration(session.get("duration_seconds", 0)),
                    status,
                    command,
                    metrics_str,
                )

            console.print(table)
            console.print(
                f"\n[dim]Showing {len(sessions)} of {len(session_keys)} total sessions[/dim]"
            )

    except Exception as e:
        print_error_message(f"Failed to list metrics sessions: {e}")
        raise typer.Exit(1) from e


@metrics_app.command("show")
@handle_errors
def show_session(
    ctx: typer.Context,
    session_uuid: Annotated[
        str,
        typer.Argument(
            help="Session UUID or prefix to display",
            autocompletion=_complete_session_uuid,
        ),
    ],
    json_output: Annotated[
        bool, typer.Option("--json", help="Output in JSON format")
    ] = False,
    include_activity: Annotated[
        bool, typer.Option("--activity", help="Include activity log")
    ] = False,
) -> None:
    """Show detailed metrics for a specific session."""
    cache_manager = _get_metrics_cache_manager()

    try:
        # Try to find session by prefix if not a full UUID
        full_uuid = session_uuid
        if len(session_uuid) < 36:
            try:
                found_uuid = _find_session_by_prefix(session_uuid)
                if found_uuid is None:
                    print_error_message(
                        f"No session found matching prefix: {session_uuid}"
                    )
                    raise typer.Exit(1)
                full_uuid = found_uuid
            except ValueError as e:
                print_error_message(str(e))
                raise typer.Exit(1) from e

        data = cache_manager.get(full_uuid)
        if not data:
            print_error_message(f"Session not found: {full_uuid}")
            raise typer.Exit(1)

        if not isinstance(data, dict) or "session_info" not in data:
            print_error_message(f"Invalid session data for: {session_uuid}")
            raise typer.Exit(1)

        if json_output:
            if not include_activity and "activity_log" in data:
                # Remove activity log for cleaner output unless requested
                data_copy = data.copy()
                data_copy.pop("activity_log", None)
                print(json.dumps(data_copy, indent=2, ensure_ascii=False))
            else:
                print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            # Display formatted session details
            session_info = data.get("session_info", {})

            console.print(
                f"[bold]Session: {session_info.get('session_id', 'unknown')}[/bold]"
            )
            console.print(f"UUID: {session_uuid}")
            console.print(f"Started: {session_info.get('start_time', 'unknown')}")
            console.print(f"Ended: {session_info.get('end_time', 'unknown')}")
            console.print(
                f"Duration: {_format_duration(session_info.get('duration_seconds', 0))}"
            )

            exit_code = session_info.get("exit_code")
            if exit_code is None:
                console.print("Status: [yellow]Running[/yellow]")
            elif exit_code == 0:
                console.print("Status: [green]Success[/green]")
            else:
                console.print(f"Status: [red]Error (exit code: {exit_code})[/red]")

            cli_args = session_info.get("cli_args", [])
            if cli_args:
                console.print(f"Command: {' '.join(cli_args)}")

            # Show metrics summary
            console.print("\n[bold]Metrics Summary:[/bold]")

            counters = data.get("counters", {})
            if counters:
                console.print(f"\n[cyan]Counters ({len(counters)}):[/cyan]")
                for name, counter_data in counters.items():
                    values = counter_data.get("values", {})
                    total = sum(float(v) for v in values.values()) if values else 0
                    console.print(f"  {name}: {total} total")
                    if len(values) > 1:
                        for labels, value in values.items():
                            console.print(f"    {labels}: {value}")

            gauges = data.get("gauges", {})
            if gauges:
                console.print(f"\n[blue]Gauges ({len(gauges)}):[/blue]")
                for name, gauge_data in gauges.items():
                    values = gauge_data.get("values", {})
                    for labels, value in values.items():
                        console.print(f"  {name} {labels}: {value}")

            histograms = data.get("histograms", {})
            if histograms:
                console.print(f"\n[green]Histograms ({len(histograms)}):[/green]")
                for name, hist_data in histograms.items():
                    count = hist_data.get("total_count", 0)
                    sum_val = hist_data.get("total_sum", 0)
                    avg = sum_val / count if count > 0 else 0
                    console.print(f"  {name}: {count} observations, avg={avg:.3f}")

            summaries = data.get("summaries", {})
            if summaries:
                console.print(f"\n[magenta]Summaries ({len(summaries)}):[/magenta]")
                for name, summary_data in summaries.items():
                    count = summary_data.get("total_count", 0)
                    sum_val = summary_data.get("total_sum", 0)
                    avg = sum_val / count if count > 0 else 0
                    console.print(f"  {name}: {count} observations, avg={avg:.3f}")

            # Show activity log if requested
            if include_activity:
                activity_log = data.get("activity_log", [])
                if activity_log:
                    console.print(
                        f"\n[bold]Recent Activity ({len(activity_log)} events):[/bold]"
                    )
                    for event in activity_log[-10:]:  # Show last 10 events
                        timestamp = datetime.fromtimestamp(event.get("timestamp", 0))
                        metric_name = event.get("metric_name", "unknown")
                        operation = event.get("operation", "unknown")
                        value = event.get("value", 0)
                        console.print(
                            f"  {timestamp.strftime('%H:%M:%S')} - {metric_name} {operation}: {value}"
                        )

    except Exception as e:
        print_error_message(f"Failed to show session: {e}")
        raise typer.Exit(1) from e


@metrics_app.command("dump")
@handle_errors
def dump_session(
    ctx: typer.Context,
    session_uuid: Annotated[
        str,
        typer.Argument(
            help="Session UUID or prefix to dump", autocompletion=_complete_session_uuid
        ),
    ],
    output_file: Annotated[
        str, typer.Option("--output", "-o", help="Output file path")
    ] = "",
) -> None:
    """Dump session metrics data to a file."""
    cache_manager = _get_metrics_cache_manager()

    try:
        # Try to find session by prefix if not a full UUID
        full_uuid = session_uuid
        if len(session_uuid) < 36:
            try:
                found_uuid = _find_session_by_prefix(session_uuid)
                if found_uuid is None:
                    print_error_message(
                        f"No session found matching prefix: {session_uuid}"
                    )
                    raise typer.Exit(1)
                full_uuid = found_uuid
            except ValueError as e:
                print_error_message(str(e))
                raise typer.Exit(1) from e

        data = cache_manager.get(full_uuid)
        if not data:
            print_error_message(f"Session not found: {full_uuid}")
            raise typer.Exit(1)

        # Determine output file path
        if not output_file:
            session_info = data.get("session_info", {})
            session_id = session_info.get("session_id", "unknown")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"metrics_{session_id}_{timestamp}.json"

        output_path = Path(output_file)

        # Write data to file
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print_success_message(f"Session metrics dumped to: {output_path}")

        # Show summary
        session_info = data.get("session_info", {})
        console.print(f"Session ID: {session_info.get('session_id', 'unknown')}")
        console.print(
            f"Duration: {_format_duration(session_info.get('duration_seconds', 0))}"
        )
        console.print(
            f"Metrics: C:{len(data.get('counters', {}))} G:{len(data.get('gauges', {}))} H:{len(data.get('histograms', {}))} S:{len(data.get('summaries', {}))}"
        )

    except Exception as e:
        print_error_message(f"Failed to dump session: {e}")
        raise typer.Exit(1) from e


@metrics_app.command("clean")
@handle_errors
def clean_sessions(
    ctx: typer.Context,
    older_than: Annotated[
        int, typer.Option("--older-than", help="Remove sessions older than N days")
    ] = 7,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be removed without doing it"),
    ] = False,
    force: Annotated[
        bool, typer.Option("--force", help="Skip confirmation prompt")
    ] = False,
) -> None:
    """Clean up old metrics sessions."""
    cache_manager = _get_metrics_cache_manager()

    try:
        # Get all session keys
        all_keys = list(cache_manager.keys())
        # SessionMetrics are stored with plain UUID keys (36 chars with hyphens)
        # Filter out old metrics system keys that start with "metrics:"
        session_keys = [
            key
            for key in all_keys
            if not key.startswith("metrics:") and len(key) == 36 and key.count("-") == 4
        ]

        if not session_keys:
            console.print("[yellow]No metrics sessions found to clean.[/yellow]")
            return

        # Find sessions older than threshold
        cutoff_time = datetime.now() - timedelta(days=older_than)
        old_sessions = []

        for key in session_keys:
            try:
                data = cache_manager.get(key)
                if data and isinstance(data, dict) and "session_info" in data:
                    start_time_str = data["session_info"].get("start_time")
                    if start_time_str:
                        start_time = datetime.fromisoformat(
                            start_time_str.replace("Z", "+00:00")
                        )
                        # Convert timezone-aware start_time to naive for comparison
                        start_time_naive = start_time.replace(tzinfo=None)
                        if start_time_naive < cutoff_time:
                            old_sessions.append((key, start_time, data))
            except Exception as e:
                logger.debug("Failed to check session %s: %s", key, e)
                continue

        if not old_sessions:
            console.print(
                f"[green]No sessions older than {older_than} days found.[/green]"
            )
            return

        # Show what will be removed
        console.print(
            f"[yellow]Found {len(old_sessions)} sessions older than {older_than} days:[/yellow]"
        )

        for _key, start_time, data in old_sessions:
            session_info = data.get("session_info", {})
            session_id = session_info.get("session_id", "unknown")
            age_days = (datetime.now() - start_time.replace(tzinfo=None)).days
            console.print(f"  - {session_id} ({age_days} days old)")

        if dry_run:
            console.print(
                f"\n[blue]Dry run complete - would remove {len(old_sessions)} sessions[/blue]"
            )
            return

        # Confirm removal
        if not force and not typer.confirm(f"Remove {len(old_sessions)} old sessions?"):
            console.print("[yellow]Cleanup cancelled.[/yellow]")
            return

        # Remove old sessions
        removed_count = 0
        for key, _, _ in old_sessions:
            try:
                cache_manager.delete(key)
                removed_count += 1
            except Exception as e:
                logger.error("Failed to remove session %s: %s", key, e)

        print_success_message(f"Removed {removed_count} old metrics sessions")

    except Exception as e:
        print_error_message(f"Failed to clean sessions: {e}")
        raise typer.Exit(1) from e


def register_commands(app: typer.Typer) -> None:
    """Register metrics commands with the main app."""
    app.add_typer(metrics_app, name="metrics")
