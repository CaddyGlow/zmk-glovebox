"""Workspace creation service for direct Docker-based ZMK workspace setup."""

import logging
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from glovebox.compilation.cache.models import (
    WorkspaceCacheMetadata,
    WorkspaceCacheResult,
)
from glovebox.compilation.models import ZmkCompilationConfig
from glovebox.compilation.parsers.repository_spec_parser import (
    RepositorySpec,
    create_repository_spec_parser,
)
from glovebox.config.models.cache import CacheLevel
from glovebox.config.user_config import UserConfig
from glovebox.core.file_operations import (
    CompilationProgressCallback,
    FileCopyService,
    create_copy_service,
)
from glovebox.models.docker import DockerUserContext
from glovebox.protocols import (
    DockerAdapterProtocol,
    FileAdapterProtocol,
    MetricsProtocol,
)
from glovebox.utils.stream_process import (
    DefaultOutputMiddleware,
    OutputMiddleware,
    create_chained_middleware,
)


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile
    from glovebox.protocols.progress_coordinator_protocol import (
        ProgressCoordinatorProtocol,
    )


class WorkspaceCreationResult(WorkspaceCacheResult):
    """Extended result for workspace creation operations."""

    docker_image_used: str | None = None
    west_init_success: bool = False
    west_update_success: bool = False
    git_clone_success: bool = False
    creation_duration_seconds: float | None = None


class WorkspaceCreationService:
    """Service for creating ZMK workspaces directly using Docker.

    This service handles workspace creation independent of compilation,
    allowing users to prepare build environments for later use.
    """

    def __init__(
        self,
        docker_adapter: DockerAdapterProtocol,
        file_adapter: FileAdapterProtocol,
        user_config: UserConfig,
        session_metrics: MetricsProtocol,
        copy_service: FileCopyService | None = None,
    ) -> None:
        """Initialize workspace creation service.

        Args:
            docker_adapter: Docker adapter for container operations
            file_adapter: File adapter for file operations
            user_config: User configuration
            session_metrics: Session metrics for tracking operations
            copy_service: Optional copy service for file operations
        """
        self.docker_adapter = docker_adapter
        self.file_adapter = file_adapter
        self.user_config = user_config
        self.session_metrics = session_metrics
        self.logger = logging.getLogger(__name__)
        self.copy_service = copy_service or create_copy_service(
            use_pipeline=True, max_workers=3
        )
        self.repository_parser = create_repository_spec_parser()

    def create_workspace(
        self,
        repo_spec: str,
        keyboard_profile: "KeyboardProfile | None" = None,
        docker_image: str | None = None,
        force_recreate: bool = False,
        progress_callback: CompilationProgressCallback | None = None,
        progress_coordinator: "ProgressCoordinatorProtocol | None" = None,
    ) -> WorkspaceCreationResult:
        """Create a new workspace from repository specification.

        Args:
            repo_spec: Repository specification in format 'org/repo@branch'
            keyboard_profile: Optional keyboard profile for configuration
            docker_image: Optional Docker image override
            force_recreate: Whether to recreate workspace if it exists
            progress_callback: Optional progress callback
            progress_coordinator: Optional progress coordinator for enhanced tracking

        Returns:
            WorkspaceCreationResult with creation details
        """
        self.logger.info("Creating workspace from specification: %s", repo_spec)
        creation_start_time = time.time()

        try:
            # Initialize metrics
            if self.session_metrics:
                creation_operations = self.session_metrics.Counter(
                    "workspace_creation_operations_total",
                    "Total workspace creation operations",
                    ["repository", "branch", "result"],
                )
                creation_duration = self.session_metrics.Histogram(
                    "workspace_creation_duration_seconds",
                    "Workspace creation operation duration",
                )

            # Parse repository specification
            try:
                repository_spec = self.repository_parser.parse(repo_spec)
            except ValueError as e:
                self.logger.error("Invalid repository specification: %s", e)
                if self.session_metrics:
                    creation_operations.labels(
                        "unknown", "unknown", "failed_parsing"
                    ).inc()
                return WorkspaceCreationResult(
                    success=False,
                    error_message=f"Invalid repository specification: {e}",
                )

            # Set metrics context
            if self.session_metrics:
                self.session_metrics.set_context(
                    repository=repository_spec.repository,
                    branch=repository_spec.branch,
                    operation="create_workspace",
                )

            # Use metrics timing if available
            if self.session_metrics:
                with creation_duration.time():
                    result = self._create_workspace_internal(
                        repository_spec,
                        keyboard_profile,
                        docker_image,
                        force_recreate,
                        progress_callback,
                        progress_coordinator,
                        creation_start_time,
                    )
            else:
                result = self._create_workspace_internal(
                    repository_spec,
                    keyboard_profile,
                    docker_image,
                    force_recreate,
                    progress_callback,
                    progress_coordinator,
                    creation_start_time,
                )

            # Record metrics
            if self.session_metrics:
                result_label = "success" if result.success else "failed"
                creation_operations.labels(
                    repository_spec.repository,
                    repository_spec.branch,
                    result_label,
                ).inc()

            return result

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Workspace creation failed: %s", e, exc_info=exc_info)

            if self.session_metrics:
                creation_operations.labels("unknown", "unknown", "error").inc()

            return WorkspaceCreationResult(
                success=False,
                error_message=f"Workspace creation failed: {e}",
                creation_duration_seconds=time.time() - creation_start_time,
            )

    def _create_workspace_internal(
        self,
        repository_spec: RepositorySpec,
        keyboard_profile: "KeyboardProfile | None",
        docker_image: str | None,
        force_recreate: bool,
        progress_callback: CompilationProgressCallback | None,
        progress_coordinator: "ProgressCoordinatorProtocol | None",
        creation_start_time: float,
    ) -> WorkspaceCreationResult:
        """Internal workspace creation logic."""

        # Determine Docker image to use
        effective_docker_image = self._determine_docker_image(
            docker_image, keyboard_profile
        )

        if not effective_docker_image:
            return WorkspaceCreationResult(
                success=False,
                error_message="Could not determine Docker image to use",
                creation_duration_seconds=time.time() - creation_start_time,
            )

        self.logger.info(
            "Using Docker image: %s for %s",
            effective_docker_image,
            repository_spec.display_name,
        )

        # Update progress coordinator if available
        if progress_coordinator:
            # TODO: Enable after refactoring
            # progress_coordinator.transition_to_phase(
            #     "workspace_creation",
            #     f"Creating workspace for {repository_spec.display_name}",
            # )
            pass

        # Create temporary workspace directory
        with tempfile.TemporaryDirectory(prefix="glovebox_workspace_") as temp_dir:
            workspace_path = Path(temp_dir)

            try:
                # Phase 1: Initialize west workspace
                if progress_coordinator:
                    # TODO: Enable after refactoring
                    # progress_coordinator.transition_to_phase(
                    #     "west_init", "Initializing west workspace"
                    # )
                    pass

                west_init_success = self._initialize_west_workspace(
                    workspace_path,
                    repository_spec,
                    effective_docker_image,
                    progress_coordinator,
                )

                if not west_init_success:
                    return WorkspaceCreationResult(
                        success=False,
                        error_message="Failed to initialize west workspace",
                        docker_image_used=effective_docker_image,
                        west_init_success=False,
                        creation_duration_seconds=time.time() - creation_start_time,
                    )

                # Phase 2: Clone repository and checkout branch
                if progress_coordinator:
                    # TODO: Enable after refactoring
                    # progress_coordinator.transition_to_phase(
                    #     "git_clone",
                    #     f"Cloning {repository_spec.repository}@{repository_spec.branch}",
                    # )
                    pass

                git_clone_success = self._clone_and_checkout_repository(
                    workspace_path,
                    repository_spec,
                    effective_docker_image,
                    progress_coordinator,
                )

                if not git_clone_success:
                    return WorkspaceCreationResult(
                        success=False,
                        error_message=f"Failed to clone repository {repository_spec.repository}",
                        docker_image_used=effective_docker_image,
                        west_init_success=True,
                        git_clone_success=False,
                        creation_duration_seconds=time.time() - creation_start_time,
                    )

                # Phase 3: Update dependencies
                if progress_coordinator:
                    # TODO: Enable after refactoring
                    # progress_coordinator.transition_to_phase(
                    #     "west_update", "Updating workspace dependencies"
                    # )
                    pass

                west_update_success = self._update_workspace_dependencies(
                    workspace_path,
                    effective_docker_image,
                    progress_coordinator,
                )

                if not west_update_success:
                    return WorkspaceCreationResult(
                        success=False,
                        error_message="Failed to update workspace dependencies",
                        docker_image_used=effective_docker_image,
                        west_init_success=True,
                        git_clone_success=True,
                        west_update_success=False,
                        creation_duration_seconds=time.time() - creation_start_time,
                    )

                # Phase 4: Create metadata and cache workspace
                if progress_coordinator:
                    # TODO: Enable after refactoring
                    # progress_coordinator.transition_to_phase(
                    #     "metadata_creation", "Creating workspace metadata"
                    # )
                    pass

                metadata = self._create_workspace_metadata(
                    workspace_path,
                    repository_spec,
                    effective_docker_image,
                    keyboard_profile,
                )

                # Calculate creation duration
                creation_duration = time.time() - creation_start_time

                # Return successful result with temporary workspace
                # Note: Actual caching will be handled by the calling service
                return WorkspaceCreationResult(
                    success=True,
                    workspace_path=workspace_path,
                    metadata=metadata,
                    created_new=True,
                    docker_image_used=effective_docker_image,
                    west_init_success=True,
                    git_clone_success=True,
                    west_update_success=True,
                    creation_duration_seconds=creation_duration,
                )

            except Exception as e:
                exc_info = self.logger.isEnabledFor(logging.DEBUG)
                self.logger.error(
                    "Error during workspace creation: %s", e, exc_info=exc_info
                )

                return WorkspaceCreationResult(
                    success=False,
                    error_message=f"Workspace creation error: {e}",
                    docker_image_used=effective_docker_image,
                    creation_duration_seconds=time.time() - creation_start_time,
                )

    def _determine_docker_image(
        self,
        docker_image: str | None,
        keyboard_profile: "KeyboardProfile | None",
    ) -> str | None:
        """Determine which Docker image to use for workspace creation."""
        # Use explicit image if provided
        if docker_image:
            return docker_image

        # Try to get image from keyboard profile
        if keyboard_profile and hasattr(keyboard_profile, "compilation_config"):
            compilation_config = keyboard_profile.compilation_config
            if hasattr(compilation_config, "image") and compilation_config.image:
                return str(compilation_config.image)

        # Default to standard ZMK image
        return "zmkfirmware/zmk-dev-arm:stable"

    def _initialize_west_workspace(
        self,
        workspace_path: Path,
        repository_spec: RepositorySpec,
        docker_image: str,
        progress_coordinator: "ProgressCoordinatorProtocol | None",
    ) -> bool:
        """Initialize west workspace in Docker container."""
        try:
            self.logger.info(
                "Initializing west workspace for %s", repository_spec.display_name
            )

            # Create basic west configuration directory
            config_dir = workspace_path / "config"
            config_dir.mkdir(parents=True, exist_ok=True)

            # Create west.yml manifest file
            manifest_content = self._generate_west_manifest(repository_spec)
            manifest_file = config_dir / "west.yml"
            manifest_file.write_text(manifest_content)

            # Run west init in Docker
            commands = [
                "cd /workspace",
                "west init -l config",
            ]

            return self._run_docker_commands(
                commands,
                docker_image,
                workspace_path,
                "West initialization",
                progress_coordinator,
            )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("West initialization failed: %s", e, exc_info=exc_info)
            return False

    def _clone_and_checkout_repository(
        self,
        workspace_path: Path,
        repository_spec: RepositorySpec,
        docker_image: str,
        progress_coordinator: "ProgressCoordinatorProtocol | None",
    ) -> bool:
        """Clone repository and checkout specified branch."""
        try:
            self.logger.info(
                "Cloning %s and checking out branch %s",
                repository_spec.repository,
                repository_spec.branch,
            )

            commands = [
                "cd /workspace",
                f"git clone {repository_spec.clone_url} zmk-config",
                "cd zmk-config",
                f"git checkout {repository_spec.branch}",
                "git status",
            ]

            return self._run_docker_commands(
                commands,
                docker_image,
                workspace_path,
                f"Repository cloning ({repository_spec.repository})",
                progress_coordinator,
            )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Repository cloning failed: %s", e, exc_info=exc_info)
            return False

    def _update_workspace_dependencies(
        self,
        workspace_path: Path,
        docker_image: str,
        progress_coordinator: "ProgressCoordinatorProtocol | None",
    ) -> bool:
        """Update workspace dependencies using west update."""
        try:
            self.logger.info("Updating workspace dependencies")

            commands = [
                "cd /workspace",
                "west update",
                "west zephyr-export",
                "west status",
            ]

            return self._run_docker_commands(
                commands,
                docker_image,
                workspace_path,
                "Dependency update",
                progress_coordinator,
            )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Dependencies update failed: %s", e, exc_info=exc_info)
            return False

    def _run_docker_commands(
        self,
        commands: list[str],
        docker_image: str,
        workspace_path: Path,
        operation_name: str,
        progress_coordinator: "ProgressCoordinatorProtocol | None",
    ) -> bool:
        """Run commands in Docker container with progress tracking."""
        try:
            user_context = DockerUserContext.detect_current_user()

            # Create progress middleware if coordinator available
            middlewares: list[OutputMiddleware[Any]] = []

            if progress_coordinator:
                # Add progress tracking middleware
                # Note: This would need to be implemented or use existing patterns
                pass

            # Add default logging middleware
            middlewares.append(DefaultOutputMiddleware())

            chained = create_chained_middleware(middlewares)

            self.logger.debug("Running %s in Docker", operation_name)

            # Create noop progress context for docker adapter
            from glovebox.cli.components.noop_progress_context import (
                get_noop_progress_context,
            )

            noop_progress_context = get_noop_progress_context()

            result = self.docker_adapter.run_container(
                image=docker_image,
                volumes=[(str(workspace_path), "/workspace")],
                environment={},
                progress_context=noop_progress_context,
                command=["sh", "-c", "set -xeu; " + " && ".join(commands)],
                middleware=chained,
                user_context=user_context,
            )

            return_code, stdout, stderr = result

            if return_code != 0:
                self.logger.error(
                    "%s failed with exit code %d", operation_name, return_code
                )
                return False

            self.logger.info("%s completed successfully", operation_name)
            return True

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "%s execution failed: %s", operation_name, e, exc_info=exc_info
            )
            return False

    def _generate_west_manifest(self, repository_spec: RepositorySpec) -> str:
        """Generate west.yml manifest content for the repository."""
        manifest_data = {
            "manifest": {
                "remotes": [
                    {
                        "name": "zmkfirmware",
                        "url-base": "https://github.com/zmkfirmware",
                    },
                    {
                        "name": repository_spec.organization,
                        "url-base": f"https://github.com/{repository_spec.organization}",
                    },
                ],
                "projects": [
                    {
                        "name": "zmk",
                        "remote": repository_spec.organization,
                        "revision": repository_spec.branch,
                        "import": "app/west.yml",
                    }
                ],
                "self": {
                    "path": "config",
                },
            }
        }

        import yaml

        return yaml.dump(manifest_data, default_flow_style=False)

    def _create_workspace_metadata(
        self,
        workspace_path: Path,
        repository_spec: RepositorySpec,
        docker_image: str,
        keyboard_profile: "KeyboardProfile | None",
    ) -> WorkspaceCacheMetadata:
        """Create rich metadata for the workspace."""
        from datetime import datetime

        # Detect workspace components
        components = []
        for component in ["zmk", "zephyr", "modules", ".west", "zmk-config", "config"]:
            if (workspace_path / component).exists():
                components.append(component)

        # Calculate workspace size
        workspace_size = sum(
            f.stat().st_size for f in workspace_path.rglob("*") if f.is_file()
        )

        # Create metadata instance
        metadata = WorkspaceCacheMetadata(
            workspace_path=workspace_path,
            repository=repository_spec.repository,
            branch=repository_spec.branch,
            commit_hash=None,  # Will be populated later if available
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            keymap_hash=None,  # No keymap file at workspace creation
            config_hash=None,  # No config file at workspace creation
            auto_detected=False,
            auto_detected_source=None,
            build_id=None,
            build_profile=None,
            git_remotes={},
            cache_level=CacheLevel.REPO_BRANCH,  # Created for specific branch
            cached_components=components,
            size_bytes=workspace_size,
            notes=f"Created via direct workspace creation from {repository_spec.original_spec}",
            # Enhanced fields
            creation_method="direct",
            docker_image=docker_image,
            west_manifest_path="config/west.yml",
            dependencies_updated=datetime.now(),
            creation_profile=keyboard_profile.keyboard_name
            if keyboard_profile
            else None,
        )

        # Add git remotes
        metadata.add_git_remote("origin", repository_spec.clone_url)

        return metadata


def create_workspace_creation_service(
    docker_adapter: DockerAdapterProtocol,
    file_adapter: FileAdapterProtocol,
    user_config: UserConfig,
    session_metrics: MetricsProtocol,
    copy_service: FileCopyService | None = None,
) -> WorkspaceCreationService:
    """Create workspace creation service instance.

    Args:
        docker_adapter: Docker adapter for container operations
        file_adapter: File adapter for file operations
        user_config: User configuration
        session_metrics: Session metrics for tracking operations
        copy_service: Optional copy service for file operations

    Returns:
        Configured WorkspaceCreationService instance
    """
    return WorkspaceCreationService(
        docker_adapter=docker_adapter,
        file_adapter=file_adapter,
        user_config=user_config,
        session_metrics=session_metrics,
        copy_service=copy_service,
    )
