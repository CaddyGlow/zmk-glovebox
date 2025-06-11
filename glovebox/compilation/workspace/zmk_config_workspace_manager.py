"""ZMK config repository workspace manager."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from glovebox.compilation.workspace.workspace_manager import (
    WorkspaceManager,
    WorkspaceManagerError,
)
from glovebox.config.compile_methods import ZmkConfigRepoConfig


if TYPE_CHECKING:
    from glovebox.compilation.cache.base_dependencies_cache import BaseDependenciesCache
    from glovebox.compilation.cache.keyboard_config_cache import KeyboardConfigCache
    from glovebox.compilation.generation.zmk_config_generator import (
        ZmkConfigContentGenerator,
    )
    from glovebox.config.profile import KeyboardProfile


logger = logging.getLogger(__name__)


class ZmkConfigWorkspaceManagerError(WorkspaceManagerError):
    """Error in ZMK config workspace management."""


class ZmkConfigWorkspaceManager(WorkspaceManager):
    """Manage ZMK config repository workspaces following GitHub Actions pattern.

    Handles ZMK config repository cloning, west workspace initialization,
    and user configuration integration for GitHub Actions-style builds.
    """

    def __init__(
        self,
        workspace_root: Path | None = None,
        content_generator: "ZmkConfigContentGenerator | None" = None,
        base_dependencies_cache: "BaseDependenciesCache | None" = None,
        keyboard_config_cache: "KeyboardConfigCache | None" = None,
    ) -> None:
        """Initialize ZMK config workspace manager.

        Args:
            workspace_root: Root directory for workspace operations
            content_generator: Content generator for dynamic workspace creation
            base_dependencies_cache: Base ZMK dependencies cache
            keyboard_config_cache: Keyboard configuration cache
        """
        super().__init__(workspace_root)
        self.content_generator = content_generator
        self.base_dependencies_cache = base_dependencies_cache
        self.keyboard_config_cache = keyboard_config_cache

    def initialize_workspace(self, **context: Any) -> bool:
        """Initialize ZMK config workspace for compilation.

        Args:
            **context: Context including config_repo_config, keymap_file, config_file

        Returns:
            bool: True if workspace was initialized successfully

        Raises:
            ZmkConfigWorkspaceManagerError: If workspace initialization fails
        """
        try:
            config_repo_config = context.get("config_repo_config")
            if not isinstance(config_repo_config, ZmkConfigRepoConfig):
                raise ZmkConfigWorkspaceManagerError(
                    "config_repo_config is required for ZMK config workspace initialization"
                )

            workspace_path = context.get("workspace_path")
            if not workspace_path:
                workspace_path = self.workspace_root / "zmk_config"

            keymap_file = context.get("keymap_file")
            config_file = context.get("config_file")

            self.logger.info("Initializing ZMK config workspace: %s", workspace_path)

            # Create workspace directory
            self.ensure_workspace_directory(workspace_path)

            # Clone config repository
            if not self.clone_config_repository(config_repo_config, workspace_path):
                return False

            # Initialize west workspace
            if not self.initialize_west_workspace(workspace_path):
                return False

            # Copy user files if provided
            if (
                keymap_file
                and config_file
                and not self.copy_user_configuration(
                    workspace_path, keymap_file, config_file
                )
            ):
                return False

            self.logger.info("ZMK config workspace initialized successfully")
            return True

        except Exception as e:
            msg = f"Failed to initialize ZMK config workspace: {e}"
            self.logger.error(msg)
            raise ZmkConfigWorkspaceManagerError(msg) from e

    def validate_workspace(self, workspace_path: Path) -> bool:
        """Validate ZMK config workspace is ready for compilation.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            bool: True if workspace is valid

        Raises:
            ZmkConfigWorkspaceManagerError: If workspace validation fails
        """
        try:
            self.logger.debug("Validating ZMK config workspace: %s", workspace_path)

            # Check basic workspace requirements
            if not workspace_path.exists() or not workspace_path.is_dir():
                self.logger.warning(
                    "Workspace directory does not exist: %s", workspace_path
                )
                return False

            # Check for west workspace
            west_yml = workspace_path / "west.yml"
            if not west_yml.exists():
                self.logger.warning(
                    "west.yml not found in workspace: %s", workspace_path
                )
                return False

            # Check for config directory
            config_dir = workspace_path / "config"
            if not config_dir.exists() or not config_dir.is_dir():
                self.logger.warning("config directory not found: %s", config_dir)
                return False

            # Check for build.yaml (GitHub Actions pattern)
            build_yaml = workspace_path / "build.yaml"
            if not build_yaml.exists():
                self.logger.warning("build.yaml not found: %s", build_yaml)
                return False

            self.logger.debug("ZMK config workspace validation successful")
            return True

        except Exception as e:
            msg = f"Failed to validate ZMK config workspace: {e}"
            self.logger.error(msg)
            raise ZmkConfigWorkspaceManagerError(msg) from e

    def cleanup_workspace(self, workspace_path: Path) -> bool:
        """Clean up ZMK config workspace after compilation.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            bool: True if cleanup was successful

        Raises:
            ZmkConfigWorkspaceManagerError: If cleanup fails
        """
        try:
            if not workspace_path.exists():
                self.logger.debug("Workspace already cleaned up: %s", workspace_path)
                return True

            self.logger.debug("Cleaning up ZMK config workspace: %s", workspace_path)

            # Remove build artifacts
            build_dir = workspace_path / "build"
            if build_dir.exists():
                import shutil

                shutil.rmtree(build_dir)
                self.logger.debug("Removed build directory: %s", build_dir)

            # Clean west workspace artifacts
            west_dir = workspace_path / ".west"
            if west_dir.exists():
                import shutil

                shutil.rmtree(west_dir)
                self.logger.debug("Removed west directory: %s", west_dir)

            self.logger.debug("ZMK config workspace cleanup completed")
            return True

        except Exception as e:
            msg = f"Failed to cleanup ZMK config workspace: {e}"
            self.logger.error(msg)
            raise ZmkConfigWorkspaceManagerError(msg) from e

    def clone_config_repository(
        self, config: ZmkConfigRepoConfig, workspace_path: Path
    ) -> bool:
        """Clone ZMK config repository.

        Args:
            config: ZMK config repository configuration
            workspace_path: Target workspace directory

        Returns:
            bool: True if clone succeeded

        Raises:
            ZmkConfigWorkspaceManagerError: If cloning fails
        """
        try:
            self.logger.info(
                "Cloning ZMK config repository: %s", config.config_repo_url
            )

            # Use git command to clone repository
            import subprocess

            # Prepare git clone command
            cmd = ["git", "clone"]

            # Add branch/tag if specified
            if config.config_repo_revision and config.config_repo_revision.strip():
                cmd.extend(["--branch", config.config_repo_revision])

            # Add depth limit for faster clones
            cmd.extend(["--depth", "1"])

            # Add repository URL and target directory
            cmd.extend([config.config_repo_url, str(workspace_path)])

            # Execute git clone
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            if result.returncode != 0:
                raise ZmkConfigWorkspaceManagerError(
                    f"Git clone failed: {result.stderr}"
                )

            self.logger.info("Successfully cloned config repository")
            return True

        except subprocess.TimeoutExpired as e:
            msg = f"Git clone timed out after 5 minutes: {e}"
            self.logger.error(msg)
            raise ZmkConfigWorkspaceManagerError(msg) from e
        except Exception as e:
            msg = f"Failed to clone config repository: {e}"
            self.logger.error(msg)
            raise ZmkConfigWorkspaceManagerError(msg) from e

    def initialize_west_workspace(self, workspace_path: Path) -> bool:
        """Initialize west workspace in config repository.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            bool: True if initialization succeeded

        Raises:
            ZmkConfigWorkspaceManagerError: If west initialization fails
        """
        try:
            self.logger.info("Initializing west workspace: %s", workspace_path)

            import subprocess

            # Initialize west workspace
            result = subprocess.run(
                ["west", "init", "-l", str(workspace_path)],
                capture_output=True,
                text=True,
                cwd=workspace_path.parent,
                timeout=120,  # 2 minute timeout
            )

            if result.returncode != 0:
                raise ZmkConfigWorkspaceManagerError(
                    f"West init failed: {result.stderr}"
                )

            # Update west workspace
            result = subprocess.run(
                ["west", "update"],
                capture_output=True,
                text=True,
                cwd=workspace_path,
                timeout=300,  # 5 minute timeout
            )

            if result.returncode != 0:
                raise ZmkConfigWorkspaceManagerError(
                    f"West update failed: {result.stderr}"
                )

            self.logger.info("West workspace initialized successfully")
            return True

        except subprocess.TimeoutExpired as e:
            msg = f"West command timed out: {e}"
            self.logger.error(msg)
            raise ZmkConfigWorkspaceManagerError(msg) from e
        except Exception as e:
            msg = f"Failed to initialize west workspace: {e}"
            self.logger.error(msg)
            raise ZmkConfigWorkspaceManagerError(msg) from e

    def copy_user_configuration(
        self, workspace_path: Path, keymap_file: Path, config_file: Path
    ) -> bool:
        """Copy user configuration files to workspace.

        Args:
            workspace_path: Path to workspace directory
            keymap_file: Source keymap file
            config_file: Source config file

        Returns:
            bool: True if copy succeeded

        Raises:
            ZmkConfigWorkspaceManagerError: If copying fails
        """
        try:
            self.logger.debug("Copying user configuration to workspace")

            config_dir = workspace_path / "config"
            if not config_dir.exists():
                config_dir.mkdir(parents=True)

            # Copy keymap file
            if keymap_file.exists():
                import shutil

                target_keymap = config_dir / keymap_file.name
                shutil.copy2(keymap_file, target_keymap)
                self.logger.debug("Copied keymap: %s -> %s", keymap_file, target_keymap)

            # Copy config file
            if config_file.exists():
                import shutil

                target_config = config_dir / config_file.name
                shutil.copy2(config_file, target_config)
                self.logger.debug("Copied config: %s -> %s", config_file, target_config)

            return True

        except Exception as e:
            msg = f"Failed to copy user configuration: {e}"
            self.logger.error(msg)
            raise ZmkConfigWorkspaceManagerError(msg) from e

    def initialize_dynamic_workspace(
        self,
        workspace_path: Path,
        keymap_file: Path,
        config_file: Path,
        keyboard_profile: "KeyboardProfile",
        shield_name: str | None = None,
        board_name: str = "nice_nano_v2",
    ) -> bool:
        """Initialize dynamic ZMK config workspace without external repository.

        Creates a complete ZMK config workspace dynamically using the content generator,
        enabling compilation without requiring an external zmk-config repository.

        Uses tiered caching to improve performance:
        1. Base ZMK dependencies cache (shared across all builds)
        2. Keyboard configuration cache (shared for same keyboard/shield/board combo)

        Args:
            workspace_path: Path to workspace directory
            keymap_file: Source keymap file
            config_file: Source config file
            keyboard_profile: Keyboard profile for configuration
            shield_name: Shield name (defaults to keyboard name)
            board_name: Board name for builds

        Returns:
            bool: True if workspace initialized successfully

        Raises:
            ZmkConfigWorkspaceManagerError: If dynamic workspace initialization fails
        """
        try:
            self.logger.info(
                "Initializing dynamic ZMK config workspace: %s", workspace_path
            )

            # Try cached approach first if caching is available
            if self.base_dependencies_cache and self.keyboard_config_cache:
                return self._initialize_dynamic_workspace_cached(
                    workspace_path,
                    keymap_file,
                    config_file,
                    keyboard_profile,
                    shield_name,
                    board_name,
                )
            else:
                # Fall back to non-cached approach
                return self._initialize_dynamic_workspace_direct(
                    workspace_path,
                    keymap_file,
                    config_file,
                    keyboard_profile,
                    shield_name,
                    board_name,
                )

        except Exception as e:
            msg = f"Failed to initialize dynamic ZMK config workspace: {e}"
            self.logger.error(msg)
            raise ZmkConfigWorkspaceManagerError(msg) from e

    def _initialize_dynamic_workspace_cached(
        self,
        workspace_path: Path,
        keymap_file: Path,
        config_file: Path,
        keyboard_profile: "KeyboardProfile",
        shield_name: str | None = None,
        board_name: str = "nice_nano_v2",
    ) -> bool:
        """Initialize dynamic workspace using tiered caching system.

        Args:
            workspace_path: Path to workspace directory
            keymap_file: Source keymap file
            config_file: Source config file
            keyboard_profile: Keyboard profile for configuration
            shield_name: Shield name (defaults to keyboard name)
            board_name: Board name for builds

        Returns:
            bool: True if workspace initialized successfully
        """
        try:
            # Type assertions for mypy - these are guaranteed by the caller
            assert self.base_dependencies_cache is not None
            assert self.keyboard_config_cache is not None

            # Determine ZMK repository details from keyboard profile
            zmk_repo_url, zmk_revision = self._get_zmk_repo_info(keyboard_profile)

            # Generate cache keys
            base_cache_key = self.base_dependencies_cache.get_cache_key(
                zmk_repo_url, zmk_revision
            )
            keyboard_cache_key = self.keyboard_config_cache.get_cache_key(
                keyboard_profile, shield_name, board_name
            )

            self.logger.info(
                "Using cached approach - base: %s, keyboard: %s",
                base_cache_key,
                keyboard_cache_key,
            )

            # Try to get keyboard-specific cached workspace
            cached_workspace = self.keyboard_config_cache.get_cached_workspace(
                keyboard_cache_key, base_cache_key
            )

            if cached_workspace:
                # Clone cached workspace to target location
                self.logger.info(
                    "Using cached keyboard workspace: %s", cached_workspace
                )
                if not self.keyboard_config_cache.clone_cached_workspace(
                    cached_workspace, workspace_path
                ):
                    self.logger.warning(
                        "Failed to clone cached workspace, falling back to direct creation"
                    )
                    return self._initialize_dynamic_workspace_direct(
                        workspace_path,
                        keymap_file,
                        config_file,
                        keyboard_profile,
                        shield_name,
                        board_name,
                    )
            else:
                # Create new cached workspace
                self.logger.info("Creating new cached workspace")

                # Get or create base dependencies cache
                base_workspace = self.base_dependencies_cache.get_cached_workspace(
                    base_cache_key
                )
                if not base_workspace:
                    self.logger.info(
                        "Creating base dependencies cache: %s", base_cache_key
                    )
                    base_workspace = (
                        self.base_dependencies_cache.create_cached_workspace(
                            base_cache_key, zmk_repo_url, zmk_revision
                        )
                    )

                # Create keyboard-specific cache from base
                cached_workspace = self.keyboard_config_cache.create_cached_workspace(
                    keyboard_cache_key,
                    base_cache_key,
                    base_workspace,
                    keyboard_profile,
                    shield_name,
                    board_name,
                )

                # Clone to target location
                if not self.keyboard_config_cache.clone_cached_workspace(
                    cached_workspace, workspace_path
                ):
                    raise ZmkConfigWorkspaceManagerError(
                        "Failed to clone newly created cached workspace"
                    )

            # Copy user keymap and config files to the workspace
            if not self._copy_user_files_to_workspace(
                workspace_path,
                keymap_file,
                config_file,
                shield_name or keyboard_profile.keyboard_name,
            ):
                return False

            self.logger.info(
                "Dynamic ZMK config workspace initialized successfully using cache"
            )
            return True

        except Exception as e:
            self.logger.error("Cached workspace initialization failed: %s", e)
            # Fall back to direct approach
            return self._initialize_dynamic_workspace_direct(
                workspace_path,
                keymap_file,
                config_file,
                keyboard_profile,
                shield_name,
                board_name,
            )

    def _initialize_dynamic_workspace_direct(
        self,
        workspace_path: Path,
        keymap_file: Path,
        config_file: Path,
        keyboard_profile: "KeyboardProfile",
        shield_name: str | None = None,
        board_name: str = "nice_nano_v2",
    ) -> bool:
        """Initialize dynamic workspace directly without caching (fallback method).

        Args:
            workspace_path: Path to workspace directory
            keymap_file: Source keymap file
            config_file: Source config file
            keyboard_profile: Keyboard profile for configuration
            shield_name: Shield name (defaults to keyboard name)
            board_name: Board name for builds

        Returns:
            bool: True if workspace initialized successfully
        """
        try:
            self.logger.info("Using direct workspace creation (no caching)")

            if not self.content_generator:
                # Lazy load content generator if not provided
                from glovebox.compilation.generation.zmk_config_generator import (
                    create_zmk_config_content_generator,
                )

                self.content_generator = create_zmk_config_content_generator()

            # Generate workspace content using content generator
            workspace_generated = self.content_generator.generate_config_workspace(
                workspace_path=workspace_path,
                keymap_file=keymap_file,
                config_file=config_file,
                keyboard_profile=keyboard_profile,
                shield_name=shield_name,
                board_name=board_name,
            )

            if not workspace_generated:
                raise ZmkConfigWorkspaceManagerError(
                    "Content generator failed to create workspace"
                )

            # Initialize west workspace in the generated config directory
            if not self.initialize_west_workspace(workspace_path):
                return False

            self.logger.info(
                "Dynamic ZMK config workspace initialized successfully (direct)"
            )
            return True

        except Exception as e:
            self.logger.error("Direct workspace initialization failed: %s", e)
            return False

    def _get_zmk_repo_info(
        self, keyboard_profile: "KeyboardProfile"
    ) -> tuple[str, str]:
        """Extract ZMK repository URL and revision from keyboard profile.

        Args:
            keyboard_profile: Keyboard profile configuration

        Returns:
            tuple[str, str]: (repository_url, revision)
        """
        if keyboard_profile.firmware_config:
            build_options = keyboard_profile.firmware_config.build_options
            return build_options.repository, build_options.branch
        elif "glove80" in keyboard_profile.keyboard_name.lower():
            return "moergo-sc/zmk", "main"
        else:
            return "zmkfirmware/zmk", "main"

    def _copy_user_files_to_workspace(
        self,
        workspace_path: Path,
        keymap_file: Path,
        config_file: Path,
        shield_name: str,
    ) -> bool:
        """Copy user keymap and config files to workspace config directory.

        Args:
            workspace_path: Path to workspace directory
            keymap_file: Source keymap file
            config_file: Source config file
            shield_name: Shield name for file naming

        Returns:
            bool: True if files copied successfully
        """
        try:
            config_dir = workspace_path / "config"

            # Copy keymap file
            keymap_dest = config_dir / f"{shield_name}.keymap"
            import shutil

            shutil.copy2(keymap_file, keymap_dest)
            self.logger.debug("Copied keymap: %s -> %s", keymap_file, keymap_dest)

            # Copy config file
            config_dest = config_dir / f"{shield_name}.conf"
            shutil.copy2(config_file, config_dest)
            self.logger.debug("Copied config: %s -> %s", config_file, config_dest)

            return True

        except Exception as e:
            self.logger.error("Failed to copy user files to workspace: %s", e)
            return False


def create_zmk_config_workspace_manager(
    workspace_root: Path | None = None,
    content_generator: "ZmkConfigContentGenerator | None" = None,
    enable_caching: bool = True,
) -> ZmkConfigWorkspaceManager:
    """Create ZMK config workspace manager instance.

    Args:
        workspace_root: Root directory for workspace operations
        content_generator: Content generator for dynamic workspace creation
        enable_caching: Whether to enable tiered caching system

    Returns:
        ZmkConfigWorkspaceManager: New ZMK config workspace manager
    """
    base_dependencies_cache = None
    keyboard_config_cache = None

    if enable_caching:
        # Lazy load caching system
        from glovebox.compilation.cache.base_dependencies_cache import (
            create_base_dependencies_cache,
        )
        from glovebox.compilation.cache.keyboard_config_cache import (
            create_keyboard_config_cache,
        )

        base_dependencies_cache = create_base_dependencies_cache()
        keyboard_config_cache = create_keyboard_config_cache(base_dependencies_cache)

    return ZmkConfigWorkspaceManager(
        workspace_root=workspace_root,
        content_generator=content_generator,
        base_dependencies_cache=base_dependencies_cache,
        keyboard_config_cache=keyboard_config_cache,
    )
