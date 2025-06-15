"""Simplified ZMK config compilation service without template method pattern."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from glovebox.compilation.protocols.compilation_protocols import (
    CompilationServiceProtocol,
)
from glovebox.config.compile_methods import ZmkCompilationConfig
from glovebox.config.models.keyboard import CompileMethodConfigUnion
from glovebox.core.errors import BuildError
from glovebox.firmware.models import BuildResult, FirmwareOutputFiles
from glovebox.protocols import DockerAdapterProtocol


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile


class SimplifiedZmkConfigCompilationService(CompilationServiceProtocol):
    """Simplified ZMK config compilation service.

    Direct implementation without template method pattern, focusing on essential
    functionality only. Targets <200 lines total per CLAUDE.md specifications.
    """

    def __init__(self, docker_adapter: DockerAdapterProtocol) -> None:
        """Initialize service with minimal dependencies.

        Args:
            docker_adapter: Docker adapter for container operations
        """
        self.docker_adapter = docker_adapter
        self.logger = logging.getLogger(__name__)

    def compile(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: CompileMethodConfigUnion,
        keyboard_profile: "KeyboardProfile",
    ) -> BuildResult:
        """Execute ZMK compilation.

        Args:
            keymap_file: Path to keymap file
            config_file: Path to config file
            output_dir: Output directory for build artifacts
            config: Compilation configuration
            keyboard_profile: Keyboard profile for dynamic generation

        Returns:
            BuildResult: Results of compilation
        """
        self.logger.info("Starting ZMK config compilation")

        try:
            # Validate config type
            if not isinstance(config, ZmkCompilationConfig):
                return BuildResult(
                    success=False,
                    errors=["Invalid configuration type for ZMK config strategy"],
                )

            # Setup workspace
            workspace_path = self._setup_workspace(
                keymap_file, config_file, config, keyboard_profile
            )
            if not workspace_path:
                return BuildResult(success=False, errors=["Failed to setup workspace"])

            # Execute compilation
            success = self._execute_compilation(workspace_path, config)
            if not success:
                return BuildResult(success=False, errors=["Compilation failed"])

            # Collect artifacts
            output_files = self._collect_artifacts(workspace_path, output_dir)

            return BuildResult(
                success=True,
                output_files=output_files,
                messages=[
                    f"ZMK compilation completed. Generated {'1' if output_files.main_uf2 else '0'} firmware files."
                ],
            )

        except Exception as e:
            self.logger.error("ZMK compilation failed: %s", e)
            return BuildResult(success=False, errors=[f"ZMK compilation failed: {e}"])

    def validate_config(self, config: CompileMethodConfigUnion) -> bool:
        """Validate ZMK configuration.

        Args:
            config: Configuration to validate

        Returns:
            bool: True if valid
        """
        if not isinstance(config, ZmkCompilationConfig):
            return False

        if not config.image:
            self.logger.error("Docker image not specified")
            return False

        if not config.workspace:
            self.logger.error("ZMK workspace configuration is required")
            return False

        return True

    def check_available(self) -> bool:
        """Check if ZMK compilation is available.

        Returns:
            bool: True if available
        """
        return self.docker_adapter is not None

    def _setup_workspace(
        self,
        keymap_file: Path,
        config_file: Path,
        config: ZmkCompilationConfig,
        keyboard_profile: "KeyboardProfile",
    ) -> Path | None:
        """Setup ZMK workspace.

        Args:
            keymap_file: Path to keymap file
            config_file: Path to config file
            config: ZMK compilation configuration
            keyboard_profile: Keyboard profile

        Returns:
            Path | None: Workspace path if successful
        """
        try:
            # Create temporary workspace
            import tempfile

            workspace_path = Path(tempfile.mkdtemp(prefix="zmk_config_"))

            # Setup config directory
            config_dir = workspace_path / "config"
            config_dir.mkdir(exist_ok=True)

            # Copy input files
            import shutil

            shutil.copy2(keymap_file, config_dir / keymap_file.name)
            shutil.copy2(config_file, config_dir / config_file.name)

            # Generate build.yaml if needed
            self._generate_build_config(config_dir, keyboard_profile)

            self.logger.info("ZMK workspace setup at: %s", workspace_path)
            return workspace_path

        except Exception as e:
            self.logger.error("Failed to setup ZMK workspace: %s", e)
            return None

    def _execute_compilation(
        self, workspace_path: Path, config: ZmkCompilationConfig
    ) -> bool:
        """Execute Docker compilation.

        Args:
            workspace_path: Path to workspace
            config: ZMK compilation configuration

        Returns:
            bool: True if successful
        """
        try:
            # Build commands
            commands = [
                "cd /workspace",
                "west init -l config",
                "west update",
                "west zephyr-export",
                "west build -s zmk/app -b nice_nano_v2 -d build -- -DZMK_CONFIG=/workspace/config",
            ]

            # Prepare volumes
            volumes = [
                (str(workspace_path), "/workspace"),
            ]

            # Execute compilation
            return_code, stdout, stderr = self.docker_adapter.run_container(
                image=config.image,
                command=["sh", "-c", " && ".join(commands)],
                volumes=volumes,
                environment={"JOBS": "4"},
            )

            if return_code != 0:
                self.logger.error("Compilation failed with exit code %d", return_code)
                return False

            return True

        except Exception as e:
            self.logger.error("Docker compilation failed: %s", e)
            return False

    def _collect_artifacts(self, workspace_path: Path, output_dir: Path) -> FirmwareOutputFiles:
        """Collect firmware artifacts.

        Args:
            workspace_path: Path to workspace
            output_dir: Output directory

        Returns:
            FirmwareOutputFiles: Collected firmware files
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Look for .uf2 files in build directory
        build_dir = workspace_path / "build" / "zephyr"
        main_uf2 = None
        
        if build_dir.exists():
            for uf2_file in build_dir.glob("*.uf2"):
                # Copy to output directory
                output_file = output_dir / uf2_file.name
                import shutil
                shutil.copy2(uf2_file, output_file)
                
                # Use first .uf2 file as main firmware
                if main_uf2 is None:
                    main_uf2 = output_file

        return FirmwareOutputFiles(
            output_dir=output_dir,
            main_uf2=main_uf2,
            artifacts_dir=build_dir if build_dir.exists() else None,
        )

    def _generate_build_config(
        self, config_dir: Path, keyboard_profile: "KeyboardProfile"
    ) -> None:
        """Generate build.yaml configuration.

        Args:
            config_dir: Configuration directory
            keyboard_profile: Keyboard profile
        """
        build_config = {"include": [{"board": "nice_nano_v2"}]}

        import yaml

        build_yaml_path = config_dir / "build.yaml"
        with build_yaml_path.open("w") as f:
            yaml.safe_dump(build_config, f)


def create_simplified_zmk_config_service(
    docker_adapter: DockerAdapterProtocol,
) -> SimplifiedZmkConfigCompilationService:
    """Create simplified ZMK config service.

    Args:
        docker_adapter: Docker adapter instance

    Returns:
        SimplifiedZmkConfigCompilationService: Service instance
    """
    return SimplifiedZmkConfigCompilationService(docker_adapter)
