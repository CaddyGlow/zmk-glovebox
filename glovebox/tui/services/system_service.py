"""Background service for system monitoring."""

import asyncio
from collections.abc import Callable
from typing import Any, Dict, Optional

import psutil


class SystemService:
    """Service for monitoring system metrics and resources."""

    def __init__(
        self, metrics_callback: Callable[[dict[str, Any]], None] | None = None
    ):
        """Initialize the system service."""
        self.metrics_callback = metrics_callback
        self.running = False
        self.task: asyncio.Task | None = None
        self.update_interval = 2.0  # Update every 2 seconds

    def set_metrics_callback(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Set the callback function for metrics updates."""
        self.metrics_callback = callback

    def set_update_interval(self, interval: float) -> None:
        """Set the update interval in seconds."""
        self.update_interval = max(0.5, interval)  # Minimum 0.5 seconds

    async def start(self) -> None:
        """Start the background system monitoring."""
        if self.running:
            return

        self.running = True
        self.task = asyncio.create_task(self._monitoring_loop())

    async def stop(self) -> None:
        """Stop the background system monitoring."""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    async def _monitoring_loop(self) -> None:
        """Main loop for system monitoring."""
        while self.running:
            try:
                # Collect system metrics
                metrics = await self._collect_metrics()

                # Send metrics to callback
                if self.metrics_callback and metrics:
                    self.metrics_callback(metrics)

                # Wait for next update
                await asyncio.sleep(self.update_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                # Handle errors gracefully and continue monitoring
                await asyncio.sleep(self.update_interval)

    async def _collect_metrics(self) -> dict[str, Any]:
        """Collect current system metrics."""
        try:
            # Run CPU-intensive operations in thread pool
            loop = asyncio.get_event_loop()

            # Get CPU usage (non-blocking)
            cpu_percent = await loop.run_in_executor(
                None, lambda: psutil.cpu_percent(interval=0.1)
            )

            # Get memory information
            memory = psutil.virtual_memory()

            # Get disk information for root partition
            disk = psutil.disk_usage("/")

            # Get network statistics
            network = psutil.net_io_counters()

            # Get process count
            process_count = len(psutil.pids())

            # Get load average (Unix-like systems only)
            try:
                load_avg = psutil.getloadavg()
            except (AttributeError, OSError):
                load_avg = (0.0, 0.0, 0.0)  # Not available on Windows

            return {
                "cpu": {
                    "percent": cpu_percent,
                    "count": psutil.cpu_count(),
                    "count_logical": psutil.cpu_count(logical=True),
                    "load_avg": load_avg,
                },
                "memory": {
                    "percent": memory.percent,
                    "total": memory.total,
                    "available": memory.available,
                    "used": memory.used,
                    "free": memory.free,
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": (disk.used / disk.total) * 100 if disk.total > 0 else 0,
                },
                "network": {
                    "bytes_sent": network.bytes_sent,
                    "bytes_recv": network.bytes_recv,
                    "packets_sent": network.packets_sent,
                    "packets_recv": network.packets_recv,
                },
                "processes": {
                    "count": process_count,
                },
                "timestamp": asyncio.get_event_loop().time(),
            }

        except Exception as e:
            # Return minimal metrics if collection fails
            return {
                "error": str(e),
                "timestamp": asyncio.get_event_loop().time(),
            }

    async def get_current_metrics(self) -> dict[str, Any]:
        """Get current system metrics immediately."""
        return await self._collect_metrics()

    def format_bytes(self, bytes_value: int) -> str:
        """Format bytes into human-readable format."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f} PB"

    def format_metrics_summary(self, metrics: dict[str, Any]) -> str:
        """Format metrics into a readable summary string."""
        if "error" in metrics:
            return f"Error collecting metrics: {metrics['error']}"

        try:
            cpu_pct = metrics.get("cpu", {}).get("percent", 0)
            mem_pct = metrics.get("memory", {}).get("percent", 0)
            disk_pct = metrics.get("disk", {}).get("percent", 0)
            proc_count = metrics.get("processes", {}).get("count", 0)

            return (
                f"CPU: {cpu_pct:.1f}% | "
                f"Memory: {mem_pct:.1f}% | "
                f"Disk: {disk_pct:.1f}% | "
                f"Processes: {proc_count}"
            )
        except Exception:
            return "Metrics formatting error"
