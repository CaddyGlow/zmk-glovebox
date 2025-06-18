"""MoErgo API interaction history tracking."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel


class MoErgoHistoryEntry(BaseModel):
    """Single entry in MoErgo interaction history."""

    timestamp: datetime
    action: Literal["upload", "download", "delete", "update_attempt", "compile"]
    layout_uuid: str
    layout_title: str | None = None
    local_file: str | None = None
    success: bool
    error_message: str | None = None
    metadata: dict[str, Any] = {}


class MoErgoHistoryTracker:
    """Tracks history of MoErgo API interactions."""

    def __init__(self, config_dir: Path | None = None):
        """Initialize history tracker."""
        self.config_dir = config_dir or Path.home() / ".glovebox"
        self.config_dir.mkdir(exist_ok=True)
        self.history_file = self.config_dir / "moergo_history.json"

    def add_entry(
        self,
        action: Literal["upload", "download", "delete", "update_attempt", "compile"],
        layout_uuid: str,
        success: bool,
        layout_title: str | None = None,
        local_file: str | None = None,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a new history entry."""
        entry = MoErgoHistoryEntry(
            timestamp=datetime.now(),
            action=action,
            layout_uuid=layout_uuid,
            layout_title=layout_title,
            local_file=str(local_file) if local_file else None,
            success=success,
            error_message=error_message,
            metadata=metadata or {},
        )

        history = self.load_history()
        history.append(entry)

        # Keep only last 1000 entries to prevent file from growing too large
        if len(history) > 1000:
            history = history[-1000:]

        self.save_history(history)

    def load_history(self) -> list[MoErgoHistoryEntry]:
        """Load history from file."""
        if not self.history_file.exists():
            return []

        try:
            with self.history_file.open() as f:
                data = json.load(f)

            # Convert to MoErgoHistoryEntry objects
            entries = []
            for item in data:
                try:
                    entries.append(MoErgoHistoryEntry(**item))
                except Exception:
                    # Skip invalid entries
                    continue

            return entries
        except Exception:
            # If file is corrupted, start fresh
            return []

    def save_history(self, history: list[MoErgoHistoryEntry]) -> None:
        """Save history to file."""
        data = [entry.model_dump(mode="json") for entry in history]

        with self.history_file.open("w") as f:
            json.dump(data, f, indent=2, default=str)

        # Set restrictive permissions
        self.history_file.chmod(0o600)

    def get_layout_history(self, layout_uuid: str) -> list[MoErgoHistoryEntry]:
        """Get history for a specific layout UUID."""
        history = self.load_history()
        return [entry for entry in history if entry.layout_uuid == layout_uuid]

    def get_recent_history(self, limit: int = 20) -> list[MoErgoHistoryEntry]:
        """Get recent history entries."""
        history = self.load_history()
        return sorted(history, key=lambda x: x.timestamp, reverse=True)[:limit]

    def get_file_history(self, file_path: str) -> list[MoErgoHistoryEntry]:
        """Get history for a specific local file."""
        history = self.load_history()
        abs_path = str(Path(file_path).resolve())
        return [
            entry
            for entry in history
            if entry.local_file and Path(entry.local_file).resolve() == Path(abs_path)
        ]

    def get_statistics(self) -> dict[str, Any]:
        """Get usage statistics."""
        history = self.load_history()

        if not history:
            return {
                "total_operations": 0,
                "successful_operations": 0,
                "failed_operations": 0,
                "uploads": 0,
                "downloads": 0,
                "deletes": 0,
                "update_attempts": 0,
                "compiles": 0,
                "unique_layouts": 0,
                "date_range": None,
            }

        successful = [e for e in history if e.success]
        failed = [e for e in history if not e.success]

        actions = {}
        for entry in history:
            actions[entry.action] = actions.get(entry.action, 0) + 1

        unique_layouts = len({entry.layout_uuid for entry in history})

        timestamps = [entry.timestamp for entry in history]
        date_range = {
            "earliest": min(timestamps).isoformat(),
            "latest": max(timestamps).isoformat(),
        }

        return {
            "total_operations": len(history),
            "successful_operations": len(successful),
            "failed_operations": len(failed),
            "uploads": actions.get("upload", 0),
            "downloads": actions.get("download", 0),
            "deletes": actions.get("delete", 0),
            "update_attempts": actions.get("update_attempt", 0),
            "compiles": actions.get("compile", 0),
            "unique_layouts": unique_layouts,
            "date_range": date_range,
        }

    def clear_history(self) -> None:
        """Clear all history."""
        if self.history_file.exists():
            self.history_file.unlink()


def create_history_tracker(config_dir: Path | None = None) -> MoErgoHistoryTracker:
    """Factory function to create MoErgo history tracker."""
    return MoErgoHistoryTracker(config_dir)
