"""Cache debug CLI command."""

import logging
from pathlib import Path
from typing import Any

from rich.console import Console

from glovebox.cli.core.command_base import IOCommand
from glovebox.cli.decorators.error_handling import handle_errors
from glovebox.cli.workspace_display_utils import generate_workspace_cache_key

from .utils import (
    get_cache_manager_and_service,
)


logger = logging.getLogger(__name__)
console = Console()


class CacheDebugCommand(IOCommand):
    """Command to debug cache state and show filesystem vs cache database entries."""

    def execute(self) -> None:
        """Execute the cache debug command."""
        try:
            cache_manager, workspace_cache_service, user_config = (
                get_cache_manager_and_service()
            )

            cache_dir = workspace_cache_service.get_cache_directory()
            console.print("[bold]Cache Debug Report[/bold]")
            console.print(f"Cache directory: {cache_dir}")
            console.print("=" * 60)

            if not cache_dir.exists():
                console.print("[red]Cache directory does not exist[/red]")
                return

            self._show_filesystem_items(cache_dir)
            self._show_cache_database_entries(cache_dir, cache_manager)
            self._test_specific_keys(cache_manager)
            self._show_known_repo_keys(cache_manager)

        except Exception as e:
            self.handle_service_error(e, "debug cache state")

    def _show_filesystem_items(self, cache_dir: Path) -> None:
        """Show filesystem items in cache directory."""
        console.print("\n[bold cyan]1. Filesystem Items[/bold cyan]")
        filesystem_items = list(cache_dir.iterdir())
        for item in sorted(filesystem_items):
            item_type = (
                "symlink"
                if item.is_symlink()
                else "directory"
                if item.is_dir()
                else "file"
            )
            if item.is_symlink():
                try:
                    target = item.resolve()
                    console.print(f"  {item.name} ({item_type}) -> {target}")
                except (OSError, RuntimeError):
                    console.print(f"  {item.name} ({item_type}) -> [red]BROKEN[/red]")
            else:
                console.print(f"  {item.name} ({item_type})")

        console.print(f"\nTotal filesystem items: {len(filesystem_items)}")

    def _show_cache_database_entries(self, cache_dir: Path, cache_manager: Any) -> None:
        """Show cache database entries."""
        console.print("\n[bold cyan]2. Cache Database Entries[/bold cyan]")
        filesystem_items = list(cache_dir.iterdir())
        cache_entries = []

        for item in filesystem_items:
            if item.is_file():
                continue
            cache_key = item.name
            cached_data = cache_manager.get(cache_key)
            if cached_data:
                console.print(f"  {cache_key}: [green]HAS METADATA[/green]")
                if isinstance(cached_data, dict):
                    repo = cached_data.get("repository", "unknown")
                    branch = cached_data.get("branch", "unknown")
                    console.print(f"    -> {repo}@{branch}")
                cache_entries.append(cache_key)
            else:
                console.print(f"  {cache_key}: [red]NO METADATA[/red]")

                # Try to auto-detect git info for missing metadata
                actual_path = item
                if item.is_symlink():
                    try:
                        actual_path = item.resolve()
                    except (OSError, RuntimeError):
                        continue

                if actual_path.is_dir():
                    # Simple fallback for missing metadata (git info detection removed)
                    repo = "auto-detected"
                    branch = "main"
                    console.print(f"    -> Detected: {repo}@{branch}")

        console.print(f"\nCache entries with metadata: {len(cache_entries)}")

    def _test_specific_keys(self, cache_manager: Any) -> None:
        """Test specific cache keys mentioned in logs."""
        test_keys = ["91005f829d37fa2b", "465b177522248c96"]
        console.print("\n[bold cyan]3. Test Specific Keys[/bold cyan]")

        for test_key in test_keys:
            cached_data = cache_manager.get(test_key)
            if cached_data:
                console.print(f"  {test_key}: [green]FOUND[/green]")
                if isinstance(cached_data, dict):
                    repo = cached_data.get("repository", "unknown")
                    branch = cached_data.get("branch", "unknown")
                    workspace_path = cached_data.get("workspace_path", "unknown")
                    console.print(f"    -> {repo}@{branch}")
                    console.print(f"    -> Path: {workspace_path}")
            else:
                console.print(f"  {test_key}: [red]NOT FOUND[/red]")

                # Check if it exists on filesystem
                cache_manager, workspace_cache_service, user_config = (
                    get_cache_manager_and_service()
                )
                cache_dir = workspace_cache_service.get_cache_directory()
                cache_item = cache_dir / test_key
                if cache_item.exists():
                    item_type = "symlink" if cache_item.is_symlink() else "directory"
                    if cache_item.is_symlink():
                        try:
                            target = cache_item.resolve()
                            console.print(f"    -> Filesystem: {item_type} -> {target}")
                        except (OSError, RuntimeError):
                            console.print(
                                f"    -> Filesystem: {item_type} -> [red]BROKEN[/red]"
                            )
                    else:
                        console.print(f"    -> Filesystem: {item_type}")
                else:
                    console.print("    -> Filesystem: [red]NOT FOUND[/red]")

    def _show_known_repo_keys(self, cache_manager: Any) -> None:
        """Show cache keys for known repositories."""
        console.print(
            "\n[bold cyan]4. Cache Keys Generated for Known Repos[/bold cyan]"
        )
        test_repos = [
            ("zmkfirmware/zmk", "main", "base"),
            ("zmkfirmware/zmk", "main", "branch"),
            ("moergo-sc/zmk", "v25.05", "base"),
            ("moergo-sc/zmk", "v25.01", "base"),
        ]

        for repo, branch, level in test_repos:
            cache_key = generate_workspace_cache_key(repo, branch, level)
            cached_data = cache_manager.get(cache_key)
            status = "[green]FOUND[/green]" if cached_data else "[red]NOT FOUND[/red]"
            console.print(f"  {repo}@{branch} ({level}): {cache_key} -> {status}")


@handle_errors
def cache_debug() -> None:
    """Debug cache state - show filesystem vs cache database entries."""
    command = CacheDebugCommand()
    command.execute()
