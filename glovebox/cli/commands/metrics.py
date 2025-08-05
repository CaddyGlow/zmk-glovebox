"""Metrics management CLI commands."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.table import Table

from glovebox.cli.core.command_base import BaseCommand, IOCommand
from glovebox.cli.decorators import handle_errors
from glovebox.cli.helpers.parameters import OutputFormatOption
from glovebox.cli.helpers.theme import Colors, get_themed_console
from glovebox.core.cache import create_default_cache
from glovebox.core.cache.cache_manager import CacheManager
from glovebox.core.structlog_logger import get_struct_logger


logger = get_struct_logger(__name__)
console = get_themed_console()

metrics_app = typer.Typer(help="Metrics management commands")


def _get_metrics_cache_manager(session_metrics: Any = None) -> CacheManager:
    """Get cache manager for metrics using shared cache coordination."""
    return create_default_cache(tag="metrics", session_metrics=session_metrics)


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


class ListSessionsCommand(BaseCommand):
    """Command to list recent metrics sessions."""

    def __init__(self, output_format: str = "table", limit: int = 10) -> None:
        super().__init__()
        self.output_format = output_format
        self.limit = limit

    def _get_session_keys(self, cache_manager: CacheManager) -> list[str]:
        """Get filtered session keys from cache."""
        all_keys = list(cache_manager.keys())
        return [
            key
            for key in all_keys
            if not key.startswith("metrics:") and len(key) == 36 and key.count("-") == 4
        ]

    def _build_session_data(
        self, cache_manager: CacheManager, session_keys: list[str]
    ) -> list[dict[str, Any]]:
        """Build session data from cache keys."""
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
                self.logger.debug("Failed to load session %s: %s", key, e)
                continue
        return sessions

    def _output_json(self, sessions: list[dict[str, Any]]) -> None:
        """Output sessions as JSON."""
        output_data = {
            "sessions": sessions,
            "total": len(sessions),
            "timestamp": datetime.now().isoformat(),
        }
        print(json.dumps(output_data, indent=2, ensure_ascii=False))

    def _output_table(
        self, sessions: list[dict[str, Any]], total_sessions: int
    ) -> None:
        """Output sessions as formatted table."""
        table = Table(title="Recent Metrics Sessions")
        table.add_column("UUID", style=Colors.PRIMARY)
        table.add_column("Started", style=Colors.SECONDARY)
        table.add_column("Duration", style=Colors.SUCCESS)
        table.add_column("Status", style="bold")
        table.add_column("Command", style=Colors.FIELD_VALUE)
        table.add_column("Metrics", style=Colors.WARNING)

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

        self.console.console.print(table)
        self.console.console.print(
            f"\n[dim]Showing {len(sessions)} of {total_sessions} total sessions[/dim]"
        )

    def execute(self) -> None:
        """Execute the list sessions command."""
        cache_manager = _get_metrics_cache_manager()

        try:
            session_keys = self._get_session_keys(cache_manager)

            if not session_keys:
                if self.output_format == "json":
                    print(json.dumps({"sessions": [], "total": 0}))
                else:
                    self.console.console.print(
                        "[yellow]No metrics sessions found.[/yellow]"
                    )
                return

            sessions = self._build_session_data(cache_manager, session_keys)

            # Sort by start time (most recent first)
            sessions.sort(key=lambda s: s.get("start_time", ""), reverse=True)

            # Apply limit
            if self.limit > 0:
                sessions = sessions[: self.limit]

            if self.output_format == "json":
                self._output_json(sessions)
            else:
                self._output_table(sessions, len(session_keys))

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to list metrics sessions: %s", e, exc_info=exc_info
            )
            self.console.print_error(f"Failed to list metrics sessions: {e}")
            raise typer.Exit(1) from e


class ShowSessionCommand(BaseCommand):
    """Command to show detailed metrics for a specific session."""

    def __init__(
        self,
        session_uuid: str,
        output_format: str = "table",
        include_activity: bool = False,
    ) -> None:
        super().__init__()
        self.session_uuid = session_uuid
        self.output_format = output_format
        self.include_activity = include_activity

    def _resolve_session_uuid(self) -> str:
        """Resolve session UUID, handling prefix matching."""
        if len(self.session_uuid) < 36:
            try:
                found_uuid = _find_session_by_prefix(self.session_uuid)
                if found_uuid is None:
                    self.console.print_error(
                        f"No session found matching prefix: {self.session_uuid}"
                    )
                    raise typer.Exit(1)
                return found_uuid
            except ValueError as e:
                self.console.print_error(str(e))
                raise typer.Exit(1) from e
        return self.session_uuid

    def _output_json(self, data: dict[str, Any]) -> None:
        """Output session data as JSON."""
        if not self.include_activity and "activity_log" in data:
            # Remove activity log for cleaner output unless requested
            data_copy = data.copy()
            data_copy.pop("activity_log", None)
            print(json.dumps(data_copy, indent=2, ensure_ascii=False))
        else:
            print(json.dumps(data, indent=2, ensure_ascii=False))

    def _output_formatted(self, data: dict[str, Any]) -> None:
        """Output session data in formatted text."""
        session_info = data.get("session_info", {})

        self.console.console.print(
            f"[bold]Session: {session_info.get('session_id', 'unknown')}[/bold]"
        )
        self.console.console.print(f"UUID: {self.session_uuid}")
        self.console.console.print(
            f"Started: {session_info.get('start_time', 'unknown')}"
        )
        self.console.console.print(f"Ended: {session_info.get('end_time', 'unknown')}")
        self.console.console.print(
            f"Duration: {_format_duration(session_info.get('duration_seconds', 0))}"
        )

        exit_code = session_info.get("exit_code")
        if exit_code is None:
            self.console.console.print("Status: [yellow]Running[/yellow]")
        elif exit_code == 0:
            self.console.console.print("Status: [green]Success[/green]")
        else:
            self.console.console.print(
                f"Status: [red]Error (exit code: {exit_code})[/red]"
            )

        cli_args = session_info.get("cli_args", [])
        if cli_args:
            self.console.console.print(f"Command: {' '.join(cli_args)}")

        # Show metrics summary
        self.console.console.print("\n[bold]Metrics Summary:[/bold]")

        self._display_counters(data.get("counters", {}))
        self._display_gauges(data.get("gauges", {}))
        self._display_histograms(data.get("histograms", {}))
        self._display_summaries(data.get("summaries", {}))

        if self.include_activity:
            self._display_activity_log(data.get("activity_log", []))

    def _display_counters(self, counters: dict[str, Any]) -> None:
        """Display counter metrics."""
        if counters:
            self.console.console.print(f"\n[cyan]Counters ({len(counters)}):[/cyan]")
            for name, counter_data in counters.items():
                values = counter_data.get("values", {})
                total = sum(float(v) for v in values.values()) if values else 0
                self.console.console.print(f"  {name}: {total} total")
                if len(values) > 1:
                    for labels, value in values.items():
                        self.console.console.print(f"    {labels}: {value}")

    def _display_gauges(self, gauges: dict[str, Any]) -> None:
        """Display gauge metrics."""
        if gauges:
            self.console.console.print(f"\n[blue]Gauges ({len(gauges)}):[/blue]")
            for name, gauge_data in gauges.items():
                values = gauge_data.get("values", {})
                for labels, value in values.items():
                    self.console.console.print(f"  {name} {labels}: {value}")

    def _display_histograms(self, histograms: dict[str, Any]) -> None:
        """Display histogram metrics."""
        if histograms:
            self.console.console.print(
                f"\n[green]Histograms ({len(histograms)}):[/green]"
            )
            for name, hist_data in histograms.items():
                count = hist_data.get("total_count", 0)
                sum_val = hist_data.get("total_sum", 0)
                avg = sum_val / count if count > 0 else 0
                self.console.console.print(
                    f"  {name}: {count} observations, avg={avg:.3f}"
                )

    def _display_summaries(self, summaries: dict[str, Any]) -> None:
        """Display summary metrics."""
        if summaries:
            self.console.console.print(
                f"\n[magenta]Summaries ({len(summaries)}):[/magenta]"
            )
            for name, summary_data in summaries.items():
                count = summary_data.get("total_count", 0)
                sum_val = summary_data.get("total_sum", 0)
                avg = sum_val / count if count > 0 else 0
                self.console.console.print(
                    f"  {name}: {count} observations, avg={avg:.3f}"
                )

    def _display_activity_log(self, activity_log: list[dict[str, Any]]) -> None:
        """Display activity log if available."""
        if activity_log:
            self.console.console.print(
                f"\n[bold]Recent Activity ({len(activity_log)} events):[/bold]"
            )
            for event in activity_log[-10:]:  # Show last 10 events
                timestamp = datetime.fromtimestamp(event.get("timestamp", 0))
                metric_name = event.get("metric_name", "unknown")
                operation = event.get("operation", "unknown")
                value = event.get("value", 0)
                self.console.console.print(
                    f"  {timestamp.strftime('%H:%M:%S')} - {metric_name} {operation}: {value}"
                )

    def execute(self) -> None:
        """Execute the show session command."""
        cache_manager = _get_metrics_cache_manager()

        try:
            full_uuid = self._resolve_session_uuid()

            data = cache_manager.get(full_uuid)
            if not data:
                self.console.print_error(f"Session not found: {full_uuid}")
                raise typer.Exit(1)

            if not isinstance(data, dict) or "session_info" not in data:
                self.console.print_error(
                    f"Invalid session data for: {self.session_uuid}"
                )
                raise typer.Exit(1)

            if self.output_format == "json":
                self._output_json(data)
            else:
                self._output_formatted(data)

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("failed_to_show_session", error=str(e), exc_info=exc_info)
            self.console.print_error(f"Failed to show session: {e}")
            raise typer.Exit(1) from e


class DumpSessionCommand(IOCommand):
    """Command to dump session metrics data to a file."""

    def __init__(self, session_uuid: str, output_file: str = "") -> None:
        super().__init__()
        self.session_uuid = session_uuid
        self.output_file = output_file

    def _resolve_session_uuid(self) -> str:
        """Resolve session UUID, handling prefix matching."""
        if len(self.session_uuid) < 36:
            try:
                found_uuid = _find_session_by_prefix(self.session_uuid)
                if found_uuid is None:
                    self.console.print_error(
                        f"No session found matching prefix: {self.session_uuid}"
                    )
                    raise typer.Exit(1)
                return found_uuid
            except ValueError as e:
                self.console.print_error(str(e))
                raise typer.Exit(1) from e
        return self.session_uuid

    def _determine_output_path(self, data: dict[str, Any]) -> Path:
        """Determine the output file path."""
        if self.output_file:
            return Path(self.output_file)

        session_info = data.get("session_info", {})
        session_id = session_info.get("session_id", "unknown")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return Path(f"metrics_{session_id}_{timestamp}.json")

    def _display_summary(self, data: dict[str, Any]) -> None:
        """Display summary of dumped session."""
        session_info = data.get("session_info", {})
        self.console.console.print(
            f"Session ID: {session_info.get('session_id', 'unknown')}"
        )
        self.console.console.print(
            f"Duration: {_format_duration(session_info.get('duration_seconds', 0))}"
        )
        self.console.console.print(
            f"Metrics: C:{len(data.get('counters', {}))} G:{len(data.get('gauges', {}))} H:{len(data.get('histograms', {}))} S:{len(data.get('summaries', {}))}"
        )

    def execute(self) -> None:
        """Execute the dump session command."""
        cache_manager = _get_metrics_cache_manager()

        try:
            full_uuid = self._resolve_session_uuid()

            data = cache_manager.get(full_uuid)
            if not data:
                self.console.print_error(f"Session not found: {full_uuid}")
                raise typer.Exit(1)

            output_path = self._determine_output_path(data)

            # Write data to file using pathlib
            with output_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            self.console.print_success(f"Session metrics dumped to: {output_path}")
            self._display_summary(data)

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("failed_to_dump_session", error=str(e), exc_info=exc_info)
            self.console.print_error(f"Failed to dump session: {e}")
            raise typer.Exit(1) from e


class CleanSessionsCommand(BaseCommand):
    """Command to clean up old metrics sessions."""

    def __init__(
        self, older_than: int = 7, dry_run: bool = False, force: bool = False
    ) -> None:
        super().__init__()
        self.older_than = older_than
        self.dry_run = dry_run
        self.force = force

    def _get_session_keys(self, cache_manager: CacheManager) -> list[str]:
        """Get filtered session keys from cache."""
        all_keys = list(cache_manager.keys())
        return [
            key
            for key in all_keys
            if not key.startswith("metrics:") and len(key) == 36 and key.count("-") == 4
        ]

    def _find_old_sessions(
        self, cache_manager: CacheManager, session_keys: list[str]
    ) -> list[tuple[str, datetime, dict[str, Any]]]:
        """Find sessions older than the threshold."""
        cutoff_time = datetime.now() - timedelta(days=self.older_than)
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
                self.logger.debug("Failed to check session %s: %s", key, e)
                continue

        return old_sessions

    def _display_sessions_to_remove(
        self, old_sessions: list[tuple[str, datetime, dict[str, Any]]]
    ) -> None:
        """Display the sessions that will be removed."""
        self.console.console.print(
            f"[yellow]Found {len(old_sessions)} sessions older than {self.older_than} days:[/yellow]"
        )

        for _key, start_time, data in old_sessions:
            session_info = data.get("session_info", {})
            session_id = session_info.get("session_id", "unknown")
            age_days = (datetime.now() - start_time.replace(tzinfo=None)).days
            self.console.console.print(f"  - {session_id} ({age_days} days old)")

    def _remove_sessions(
        self,
        cache_manager: CacheManager,
        old_sessions: list[tuple[str, datetime, dict[str, Any]]],
    ) -> int:
        """Remove the old sessions and return count of removed sessions."""
        removed_count = 0
        for key, _, _ in old_sessions:
            try:
                cache_manager.delete(key)
                removed_count += 1
            except Exception as e:
                exc_info = self.logger.isEnabledFor(logging.DEBUG)
                self.logger.error(
                    "Failed to remove session %s: %s", key, e, exc_info=exc_info
                )
        return removed_count

    def execute(self) -> None:
        """Execute the clean sessions command."""
        cache_manager = _get_metrics_cache_manager()

        try:
            session_keys = self._get_session_keys(cache_manager)

            if not session_keys:
                self.console.console.print(
                    "[yellow]No metrics sessions found to clean.[/yellow]"
                )
                return

            old_sessions = self._find_old_sessions(cache_manager, session_keys)

            if not old_sessions:
                self.console.console.print(
                    f"[green]No sessions older than {self.older_than} days found.[/green]"
                )
                return

            self._display_sessions_to_remove(old_sessions)

            if self.dry_run:
                self.console.console.print(
                    f"\n[blue]Dry run complete - would remove {len(old_sessions)} sessions[/blue]"
                )
                return

            # Confirm removal
            if not self.force and not typer.confirm(
                f"Remove {len(old_sessions)} old sessions?"
            ):
                self.console.console.print("[yellow]Cleanup cancelled.[/yellow]")
                return

            removed_count = self._remove_sessions(cache_manager, old_sessions)
            self.console.print_success(f"Removed {removed_count} old metrics sessions")

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "failed_to_clean_sessions", error=str(e), exc_info=exc_info
            )
            self.console.print_error(f"Failed to clean sessions: {e}")
            raise typer.Exit(1) from e


@metrics_app.command("list")
@handle_errors
def list_sessions(
    ctx: typer.Context,
    output_format: OutputFormatOption = "table",
    limit: Annotated[
        int, typer.Option("--limit", "-n", help="Limit number of sessions shown")
    ] = 10,
) -> None:
    """List recent metrics sessions."""
    command = ListSessionsCommand(output_format=output_format, limit=limit)
    command.execute()


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
    output_format: OutputFormatOption = "table",
    include_activity: Annotated[
        bool, typer.Option("--activity", help="Include activity log")
    ] = False,
) -> None:
    """Show detailed metrics for a specific session."""
    command = ShowSessionCommand(
        session_uuid=session_uuid,
        output_format=output_format,
        include_activity=include_activity,
    )
    command.execute()


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
    command = DumpSessionCommand(session_uuid=session_uuid, output_file=output_file)
    command.execute()


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
    command = CleanSessionsCommand(older_than=older_than, dry_run=dry_run, force=force)
    command.execute()


def register_commands(app: typer.Typer) -> None:
    """Register metrics commands with the main app."""
    app.add_typer(metrics_app, name="metrics")
