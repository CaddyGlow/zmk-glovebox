"""Protocols for file copy strategies."""

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .models import CopyProgressCallback, CopyResult


@runtime_checkable
class CopyStrategyProtocol(Protocol):
    """Protocol defining the interface for file copy strategies."""

    @property
    def name(self) -> str:
        """Human-readable name for the strategy."""
        ...

    @property
    def description(self) -> str:
        """Detailed description of the strategy."""
        ...

    def copy_directory(
        self,
        src: Path,
        dst: Path,
        exclude_git: bool = False,
        progress_callback: CopyProgressCallback | None = None,
        **options: Any,
    ) -> CopyResult:
        """Copy directory with specified options.

        Args:
            src: Source directory path
            dst: Destination directory path
            exclude_git: Whether to exclude .git directories
            progress_callback: Optional callback for progress reporting
            **options: Strategy-specific options

        Returns:
            CopyResult with operation details
        """
        ...

    def validate_prerequisites(self) -> list[str]:
        """Return list of missing prerequisites, empty if all good.

        Returns:
            List of missing prerequisites as strings
        """
        ...
