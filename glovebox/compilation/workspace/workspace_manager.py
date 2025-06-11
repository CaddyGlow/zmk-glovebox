"""Base workspace manager for compilation strategies."""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

from glovebox.core.errors import GloveboxError


if TYPE_CHECKING:
    from glovebox.compilation.workspace.workspace_context import WorkspaceContext
    from glovebox.config.models.workspace import UserWorkspaceConfig

logger = logging.getLogger(__name__)


class WorkspaceManagerError(GloveboxError):
    """Error in workspace management."""


class WorkspaceManager(ABC):
    """Base workspace manager for compilation strategies.

    Provides common workspace management functionality including
    initialization, validation, and cleanup operations.
    Enhanced to support workspace configuration for cleanup and preservation.
    """

    def __init__(
        self,
        workspace_root: Path | None = None,
        workspace_config: "UserWorkspaceConfig | None" = None,
    ) -> None:
        """Initialize workspace manager.

        Args:
            workspace_root: Root directory for workspace operations
            workspace_config: User workspace configuration for cleanup/preservation
        """
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.workspace_root = workspace_root or Path.cwd() / ".workspace"
        self.workspace_config = workspace_config

    @abstractmethod
    def initialize_workspace(self, **context: Any) -> bool:
        """Initialize workspace for compilation.

        Args:
            **context: Context for workspace initialization

        Returns:
            bool: True if workspace was initialized successfully

        Raises:
            WorkspaceManagerError: If workspace initialization fails
        """

    @abstractmethod
    def validate_workspace(self, workspace_path: Path) -> bool:
        """Validate workspace is ready for compilation.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            bool: True if workspace is valid

        Raises:
            WorkspaceManagerError: If workspace validation fails
        """

    @abstractmethod
    def cleanup_workspace(self, workspace_path: Path) -> bool:
        """Clean up workspace after compilation.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            bool: True if cleanup was successful

        Raises:
            WorkspaceManagerError: If cleanup fails
        """

    def ensure_workspace_directory(self, workspace_path: Path) -> None:
        """Ensure workspace directory exists.

        Args:
            workspace_path: Path to workspace directory

        Raises:
            WorkspaceManagerError: If directory creation fails
        """
        try:
            workspace_path.mkdir(parents=True, exist_ok=True)
            self.logger.debug("Ensured workspace directory: %s", workspace_path)
        except Exception as e:
            msg = f"Failed to create workspace directory {workspace_path}: {e}"
            self.logger.error(msg)
            raise WorkspaceManagerError(msg) from e

    def check_workspace_permissions(self, workspace_path: Path) -> bool:
        """Check workspace has required permissions.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            bool: True if permissions are adequate
        """
        try:
            # Check read permission
            if not workspace_path.exists():
                return False

            # Check write permission by creating a test file
            test_file = workspace_path / ".permission_test"
            try:
                test_file.touch()
                test_file.unlink()
                self.logger.debug("Workspace permissions verified: %s", workspace_path)
                return True
            except Exception:
                self.logger.warning(
                    "Insufficient workspace permissions: %s", workspace_path
                )
                return False

        except Exception as e:
            self.logger.error("Failed to check workspace permissions: %s", e)
            return False

    def get_workspace_info(self, workspace_path: Path) -> dict[str, Any]:
        """Get workspace information and metadata.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            dict[str, Any]: Workspace information
        """
        try:
            info = {
                "path": str(workspace_path.resolve()),
                "exists": workspace_path.exists(),
                "is_directory": workspace_path.is_dir()
                if workspace_path.exists()
                else False,
                "readable": workspace_path.exists()
                and bool(workspace_path.stat().st_mode & 0o444),
                "writable": self.check_workspace_permissions(workspace_path),
                "size_bytes": sum(
                    f.stat().st_size for f in workspace_path.rglob("*") if f.is_file()
                )
                if workspace_path.exists()
                else 0,
            }

            if workspace_path.exists():
                stat = workspace_path.stat()
                info.update(
                    {
                        "created": stat.st_ctime,
                        "modified": stat.st_mtime,
                        "permissions": oct(stat.st_mode)[-3:],
                    }
                )

            return info

        except Exception as e:
            self.logger.error("Failed to get workspace info: %s", e)
            return {"path": str(workspace_path), "error": str(e)}

    def create_workspace_context(
        self,
        workspace_path: Path,
        keyboard_name: str,
        strategy: str,
        cleanup_after_build: bool | None = None,
        preserve_on_failure: bool | None = None,
    ) -> "WorkspaceContext":
        """Create workspace context for lifecycle management.

        Args:
            workspace_path: Path to workspace directory
            keyboard_name: Name of keyboard for identification
            strategy: Compilation strategy name
            cleanup_after_build: Override workspace cleanup setting
            preserve_on_failure: Override failure preservation setting

        Returns:
            WorkspaceContext: Context manager for workspace lifecycle
        """
        from datetime import datetime

        from glovebox.compilation.workspace.workspace_context import WorkspaceContext

        # Determine cleanup settings with precedence
        should_cleanup = cleanup_after_build
        if should_cleanup is None and self.workspace_config:
            should_cleanup = self.workspace_config.cleanup_after_build
        elif should_cleanup is None:
            should_cleanup = True  # Default to cleanup

        should_preserve_on_failure = preserve_on_failure
        if should_preserve_on_failure is None and self.workspace_config:
            should_preserve_on_failure = self.workspace_config.preserve_on_failure
        elif should_preserve_on_failure is None:
            should_preserve_on_failure = False  # Default to no preservation

        return WorkspaceContext(
            path=workspace_path,
            keyboard_name=keyboard_name,
            strategy=strategy,
            created_at=datetime.now(),
            should_cleanup=should_cleanup,
            preserve_on_failure=should_preserve_on_failure,
        )


def create_workspace_manager() -> WorkspaceManager:
    """Create base workspace manager instance.

    Note: This is an abstract base class. Use specific implementations
    like create_west_workspace_manager() or create_zmk_config_workspace_manager().

    Returns:
        WorkspaceManager: Base workspace manager instance

    Raises:
        NotImplementedError: Always, as this is an abstract base class
    """
    raise NotImplementedError(
        "WorkspaceManager is abstract. Use create_west_workspace_manager() "
        "or create_zmk_config_workspace_manager() instead."
    )
