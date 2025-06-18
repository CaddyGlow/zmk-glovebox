#!/usr/bin/env python3
"""Cleanup script for glovebox cache directories."""

import argparse
import os
import shutil
import tempfile
from pathlib import Path

import psutil


def cleanup_orphaned_process_caches() -> None:
    """Remove cache directories for processes that no longer exist."""
    cache_base = Path(tempfile.gettempdir()) / "glovebox_cache"

    if not cache_base.exists():
        print("No cache directory found")
        return

    # Get all running process IDs
    running_pids = {p.pid for p in psutil.process_iter()}

    removed_count = 0
    total_size = 0

    # Check each process cache directory
    for proc_dir in cache_base.glob("proc_*"):
        if not proc_dir.is_dir():
            continue

        try:
            # Extract PID from directory name
            pid_str = proc_dir.name.replace("proc_", "")
            pid = int(pid_str)

            # Check if process is still running
            if pid not in running_pids:
                # Calculate size before deletion
                dir_size = sum(
                    f.stat().st_size for f in proc_dir.rglob("*") if f.is_file()
                )
                total_size += dir_size

                print(
                    f"Removing orphaned cache for PID {pid} ({dir_size / 1024 / 1024:.1f} MB)"
                )
                shutil.rmtree(proc_dir)
                removed_count += 1

        except (ValueError, OSError) as e:
            print(f"Warning: Could not process {proc_dir}: {e}")

    print(
        f"Cleaned up {removed_count} orphaned process caches ({total_size / 1024 / 1024:.1f} MB total)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Cleanup glovebox cache directories")
    parser.add_argument(
        "--all", action="store_true", help="Remove all cache directories"
    )
    parser.add_argument(
        "--orphaned",
        action="store_true",
        default=True,
        help="Remove orphaned process caches (default)",
    )

    args = parser.parse_args()

    if args.all:
        cache_base = Path(tempfile.gettempdir()) / "glovebox_cache"
        if cache_base.exists():
            shutil.rmtree(cache_base)
            print(f"Removed entire cache directory: {cache_base}")
        else:
            print("No cache directory found")
    else:
        cleanup_orphaned_process_caches()


if __name__ == "__main__":
    main()
