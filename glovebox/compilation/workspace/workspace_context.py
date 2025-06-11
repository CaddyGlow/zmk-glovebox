"""Workspace context for managing compilation workspace lifecycle."""

import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


@dataclass
class WorkspaceContext:
    """Context manager for compilation workspace lifecycle.

    Manages workspace creation, usage, and cleanup based on user configuration.
    Implements context manager protocol for automatic cleanup handling.
    """

    path: Path
    keyboard_name: str
    strategy: str
    created_at: datetime
    should_cleanup: bool
    preserve_on_failure: bool = False
    preserved: bool = False

    def __post_init__(self) -> None:
        """Initialize workspace context logging."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def __enter__(self) -> Path:
        """Context manager entry - returns workspace path.

        Returns:
            Path: Workspace directory path for use in compilation
        """
        self.logger.info(
            "Entering workspace context: %s (strategy=%s, cleanup=%s)",
            self.path,
            self.strategy,
            self.should_cleanup,
        )
        return self.path

    def __exit__(
        self, exc_type: type[Exception] | None, exc_val: Exception | None, exc_tb: Any
    ) -> None:
        """Context manager exit - handles cleanup based on settings.

        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred
        """
        if exc_type is not None:
            # An exception occurred during compilation
            self.logger.warning(
                "Compilation failed in workspace %s: %s", self.path, exc_val
            )

            if self.preserve_on_failure:
                self.logger.info(
                    "Preserving workspace %s due to failure and preserve_on_failure=True",
                    self.path,
                )
                self.preserve("compilation_failure")
                return

        # Normal cleanup based on should_cleanup setting
        if self.should_cleanup and not self.preserved:
            self.cleanup()
        else:
            self.logger.info(
                "Preserving workspace %s (cleanup=%s, preserved=%s)",
                self.path,
                self.should_cleanup,
                self.preserved,
            )

    def cleanup(self) -> bool:
        """Remove workspace directory and contents.

        Returns:
            bool: True if cleanup was successful, False otherwise
        """
        try:
            if self.path.exists():
                self.logger.info("Cleaning up workspace: %s", self.path)
                shutil.rmtree(self.path)
                return True
            else:
                self.logger.debug("Workspace already removed: %s", self.path)
                return True
        except Exception as e:
            self.logger.error("Failed to cleanup workspace %s: %s", self.path, e)
            return False

    def preserve(self, reason: str) -> Path:
        """Mark workspace as preserved with metadata.

        Args:
            reason: Reason for preservation (e.g., "debugging", "compilation_failure")

        Returns:
            Path: Path to preserved workspace
        """
        self.preserved = True
        self.logger.info("Preserving workspace %s (reason: %s)", self.path, reason)

        # Create metadata file with preservation info
        metadata_file = self.path / ".glovebox_workspace_metadata"
        try:
            with metadata_file.open("w") as f:
                f.write(f"keyboard_name: {self.keyboard_name}\n")
                f.write(f"strategy: {self.strategy}\n")
                f.write(f"created_at: {self.created_at.isoformat()}\n")
                f.write(f"preserved_at: {datetime.now().isoformat()}\n")
                f.write(f"reason: {reason}\n")
        except Exception as e:
            self.logger.warning(
                "Failed to write workspace metadata to %s: %s",
                metadata_file,
                e,
            )

        return self.path

    def force_cleanup(self) -> bool:
        """Force cleanup regardless of preservation settings.

        Returns:
            bool: True if cleanup was successful, False otherwise
        """
        self.logger.info("Force cleaning up workspace: %s", self.path)
        self.should_cleanup = True
        self.preserved = False
        return self.cleanup()

    def is_valid(self) -> bool:
        """Check if workspace path exists and is accessible.

        Returns:
            bool: True if workspace is valid and accessible
        """
        try:
            return self.path.exists() and self.path.is_dir()
        except Exception as e:
            self.logger.error("Error checking workspace validity %s: %s", self.path, e)
            return False

    def get_metadata(self) -> dict[str, Any]:
        """Get workspace metadata as dictionary.

        Returns:
            dict[str, Any]: Workspace metadata
        """
        return {
            "path": str(self.path),
            "keyboard_name": self.keyboard_name,
            "strategy": self.strategy,
            "created_at": self.created_at.isoformat(),
            "should_cleanup": self.should_cleanup,
            "preserve_on_failure": self.preserve_on_failure,
            "preserved": self.preserved,
            "exists": self.is_valid(),
        }

    def __str__(self) -> str:
        """String representation of workspace context."""
        return (
            f"WorkspaceContext(path={self.path}, "
            f"keyboard={self.keyboard_name}, "
            f"strategy={self.strategy}, "
            f"cleanup={self.should_cleanup})"
        )

    def __repr__(self) -> str:
        """Detailed representation of workspace context."""
        return (
            f"WorkspaceContext("
            f"path={self.path!r}, "
            f"keyboard_name={self.keyboard_name!r}, "
            f"strategy={self.strategy!r}, "
            f"created_at={self.created_at!r}, "
            f"should_cleanup={self.should_cleanup!r}, "
            f"preserve_on_failure={self.preserve_on_failure!r}, "
            f"preserved={self.preserved!r})"
        )
