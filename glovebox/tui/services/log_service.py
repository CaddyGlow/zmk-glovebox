"""Background service for log generation and management."""

import asyncio
import random
from collections.abc import Callable
from datetime import datetime
from typing import Optional


class LogService:
    """Service for generating and managing application logs."""

    def __init__(self, log_callback: Callable[[str], None] | None = None):
        """Initialize the log service."""
        self.log_callback = log_callback
        self.running = False
        self.task: asyncio.Task | None = None
        self.log_counter = 0

        # Sample log messages for demonstration
        self.sample_messages = [
            "Processing keyboard layout...",
            "Compiling firmware configuration",
            "Checking device connectivity",
            "Loading user preferences",
            "Validating keymap structure",
            "Optimizing layout bindings",
            "Generating ZMK configuration",
            "Building firmware image",
            "Preparing flash sequence",
            "Monitoring system resources",
        ]

        self.log_levels = [
            ("[green]INFO[/green]", 0.6),
            ("[yellow]WARNING[/yellow]", 0.25),
            ("[red]ERROR[/red]", 0.1),
            ("[blue]DEBUG[/blue]", 0.05),
        ]

    def set_log_callback(self, callback: Callable[[str], None]) -> None:
        """Set the callback function for log messages."""
        self.log_callback = callback

    async def start(self) -> None:
        """Start the background log generation."""
        if self.running:
            return

        self.running = True
        self.task = asyncio.create_task(self._log_generation_loop())

    async def stop(self) -> None:
        """Stop the background log generation."""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    async def _log_generation_loop(self) -> None:
        """Main loop for generating log messages."""
        # Initial burst of logs
        await self._generate_initial_logs()

        # Continuous log generation
        while self.running:
            try:
                # Random delay between logs (1-8 seconds)
                await asyncio.sleep(random.uniform(1.0, 8.0))

                if self.running:
                    await self._generate_log_message()

            except asyncio.CancelledError:
                break
            except Exception as e:
                # Handle any errors gracefully
                if self.log_callback:
                    self.log_callback(f"[red]Log service error: {e}[/red]")

    async def _generate_initial_logs(self) -> None:
        """Generate initial burst of log messages."""
        if not self.log_callback:
            return

        # Startup sequence
        startup_messages = [
            "Application initializing...",
            "Loading configuration files",
            "Initializing user interface",
            "Starting background services",
            "Ready for user input",
        ]

        for i, message in enumerate(startup_messages):
            if not self.running:
                break

            self.log_counter += 1
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = self._format_log_message(message, "INFO", timestamp)
            self.log_callback(formatted_message)

            # Small delay between startup messages
            await asyncio.sleep(0.3)

    async def _generate_log_message(self) -> None:
        """Generate a single log message."""
        if not self.log_callback:
            return

        # Choose random message and level
        message = random.choice(self.sample_messages)
        level, _ = self._choose_log_level()

        self.log_counter += 1
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Add some variation to messages
        if random.random() < 0.3:  # 30% chance of adding details
            details = [
                f"(step {self.log_counter})",
                f"[{random.randint(1000, 9999)}ms]",
                f"batch #{random.randint(1, 10)}",
                "completed successfully",
                "requires attention",
            ]
            message += f" {random.choice(details)}"

        formatted_message = self._format_log_message(message, level, timestamp)
        self.log_callback(formatted_message)

    def _choose_log_level(self) -> tuple[str, float]:
        """Choose a log level based on weighted probabilities."""
        rand_val = random.random()
        cumulative = 0.0

        for level, probability in self.log_levels:
            cumulative += probability
            if rand_val <= cumulative:
                return level, probability

        # Fallback to INFO
        return "[green]INFO[/green]", 0.6

    def _format_log_message(self, message: str, level: str, timestamp: str) -> str:
        """Format a log message with timestamp and level."""
        return f"[dim]{timestamp}[/dim] {level} {message}"

    def add_custom_log(self, message: str, level: str = "INFO") -> None:
        """Add a custom log message immediately."""
        if not self.log_callback:
            return

        self.log_counter += 1
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Format level with colors
        level_colors = {
            "DEBUG": "[blue]DEBUG[/blue]",
            "INFO": "[green]INFO[/green]",
            "WARNING": "[yellow]WARNING[/yellow]",
            "ERROR": "[red]ERROR[/red]",
        }

        formatted_level = level_colors.get(level.upper(), f"[white]{level}[/white]")
        formatted_message = self._format_log_message(
            message, formatted_level, timestamp
        )
        self.log_callback(formatted_message)
