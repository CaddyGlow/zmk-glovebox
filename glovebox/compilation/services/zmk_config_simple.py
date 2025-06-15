"""Ultra-simplified ZMK config compilation service."""

import logging
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from glovebox.compilation.protocols.compilation_protocols import (
    CompilationServiceProtocol,
)
from glovebox.config.minimal_compile_config import (
    MinimalCompileConfigUnion,
    MinimalZmkConfig,
)
from glovebox.firmware.models import BuildResult, FirmwareOutputFiles
from glovebox.protocols import DockerAdapterProtocol


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile


class ZmkConfigSimpleService(CompilationServiceProtocol):
    """Ultra-simplified ZMK config compilation service (<200 lines)."""

    def __init__(self, docker_adapter: DockerAdapterProtocol) -> None:
        """Initialize with Docker adapter."""
        self.docker_adapter = docker_adapter
        self.logger = logging.getLogger(__name__)

    def compile(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: MinimalCompileConfigUnion,
        keyboard_profile: "KeyboardProfile",
    ) -> BuildResult:
        """Execute ZMK compilation."""
        self.logger.info("Starting ZMK config compilation")

        try:
            if not isinstance(config, MinimalZmkConfig):
                return BuildResult(success=False, errors=["Invalid config type"])

            workspace_path = self._setup_workspace(keymap_file, config_file)
            if not workspace_path:
                return BuildResult(success=False, errors=["Workspace setup failed"])

            if not self._run_compilation(workspace_path, config):
                return BuildResult(success=False, errors=["Compilation failed"])

            output_files = self._collect_files(workspace_path, output_dir)
            return BuildResult(
                success=True,
                output_files=output_files,
                messages=[
                    f"Generated {'1' if output_files.main_uf2 else '0'} firmware files"
                ],
            )

        except Exception as e:
            self.logger.error("Compilation failed: %s", e)
            return BuildResult(success=False, errors=[str(e)])

    def validate_config(self, config: MinimalCompileConfigUnion) -> bool:
        """Validate configuration."""
        return isinstance(config, MinimalZmkConfig) and bool(config.image)

    def check_available(self) -> bool:
        """Check availability."""
        return self.docker_adapter is not None

    def _setup_workspace(self, keymap_file: Path, config_file: Path) -> Path | None:
        """Setup temporary workspace."""
        try:
            workspace_path = Path(tempfile.mkdtemp(prefix="zmk_"))
            config_dir = workspace_path / "config"
            config_dir.mkdir()

            # Copy files
            shutil.copy2(keymap_file, config_dir / keymap_file.name)
            shutil.copy2(config_file, config_dir / config_file.name)

            # Create basic build.yaml
            build_config = {"include": [{"board": "nice_nano_v2"}]}
            with (config_dir / "build.yaml").open("w") as f:
                yaml.safe_dump(build_config, f)

            return workspace_path
        except Exception as e:
            self.logger.error("Workspace setup failed: %s", e)
            return None

    def _run_compilation(self, workspace_path: Path, config: MinimalZmkConfig) -> bool:
        """Run Docker compilation."""
        try:
            commands = [
                "cd /workspace",
                "west init -l config",
                "west update",
                "west zephyr-export",
                "west build -s zmk/app -b nice_nano_v2 -d build -- -DZMK_CONFIG=/workspace/config",
            ]

            return_code, _, stderr = self.docker_adapter.run_container(
                image=config.image,
                command=["sh", "-c", " && ".join(commands)],
                volumes=[(str(workspace_path), "/workspace")],
                environment={"JOBS": "4"},
            )

            if return_code != 0:
                self.logger.error("Build failed with exit code %d", return_code)
                return False

            return True
        except Exception as e:
            self.logger.error("Docker execution failed: %s", e)
            return False

    def _collect_files(
        self, workspace_path: Path, output_dir: Path
    ) -> FirmwareOutputFiles:
        """Collect firmware files."""
        output_dir.mkdir(parents=True, exist_ok=True)
        build_dir = workspace_path / "build" / "zephyr"
        main_uf2 = None

        if build_dir.exists():
            for uf2_file in build_dir.glob("*.uf2"):
                output_file = output_dir / uf2_file.name
                shutil.copy2(uf2_file, output_file)
                if main_uf2 is None:
                    main_uf2 = output_file

        return FirmwareOutputFiles(
            output_dir=output_dir,
            main_uf2=main_uf2,
            artifacts_dir=build_dir if build_dir.exists() else None,
        )


def create_zmk_config_simple_service(
    docker_adapter: DockerAdapterProtocol,
) -> ZmkConfigSimpleService:
    """Create simplified ZMK config service."""
    return ZmkConfigSimpleService(docker_adapter)
