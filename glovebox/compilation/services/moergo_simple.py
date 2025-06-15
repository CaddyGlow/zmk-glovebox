"""Ultra-simplified Moergo compilation service."""

import logging
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from glovebox.compilation.protocols.compilation_protocols import (
    CompilationServiceProtocol,
)
from glovebox.config.compile_methods import MoergoCompilationConfig
from glovebox.config.models.keyboard import CompileMethodConfigUnion
from glovebox.firmware.models import BuildResult, FirmwareOutputFiles
from glovebox.protocols import DockerAdapterProtocol


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile


class MoergoSimpleService(CompilationServiceProtocol):
    """Ultra-simplified Moergo compilation service (<200 lines)."""

    def __init__(self, docker_adapter: DockerAdapterProtocol) -> None:
        """Initialize with Docker adapter."""
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
        """Execute Moergo compilation."""
        self.logger.info("Starting Moergo compilation")

        try:
            if not isinstance(config, MoergoCompilationConfig):
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

    def validate_config(self, config: CompileMethodConfigUnion) -> bool:
        """Validate configuration."""
        return isinstance(config, MoergoCompilationConfig) and bool(config.image)

    def check_available(self) -> bool:
        """Check availability."""
        return self.docker_adapter is not None

    def _setup_workspace(self, keymap_file: Path, config_file: Path) -> Path | None:
        """Setup temporary workspace."""
        try:
            temp_dir = Path(tempfile.mkdtemp(prefix="moergo_"))
            config_dir = temp_dir / "config"
            config_dir.mkdir(parents=True)

            # Copy files with Moergo expected names
            shutil.copy2(keymap_file, config_dir / "glove80.keymap")
            shutil.copy2(config_file, config_dir / "glove80.conf")

            # Create default.nix for Moergo build
            default_nix_content = """{
  pkgs ? (import <moergo-zmk/nix/pinned-nixpkgs.nix> { }),
  moergo ? (import <moergo-zmk> { }),
  zmk ? moergo.zmk,
}:
let
  config = ./.;
  glove80_left = zmk { board = "glove80_lh"; keymap = config + "/glove80.keymap"; kconfig = config + "/glove80.conf"; };
  glove80_right = zmk { board = "glove80_rh"; keymap = config + "/glove80.keymap"; kconfig = config + "/glove80.conf"; };
in
  moergo.combine_uf2 glove80_left glove80_right"""

            (config_dir / "default.nix").write_text(default_nix_content)
            return temp_dir
        except Exception as e:
            self.logger.error("Workspace setup failed: %s", e)
            return None

    def _run_compilation(
        self, workspace_path: Path, config: MoergoCompilationConfig
    ) -> bool:
        """Run Docker compilation."""
        try:
            return_code, _, stderr = self.docker_adapter.run_container(
                image=config.image,
                command=["nix-build", "/workspace/config"],
                volumes=[(str(workspace_path), "/workspace")],
                environment={},
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
        main_uf2 = None

        # Look for result symlink from nix-build
        result_link = workspace_path / "result"
        if result_link.exists():
            for uf2_file in Path(result_link).glob("*.uf2"):
                output_file = output_dir / uf2_file.name
                shutil.copy2(uf2_file, output_file)
                if main_uf2 is None:
                    main_uf2 = output_file

        return FirmwareOutputFiles(
            output_dir=output_dir,
            main_uf2=main_uf2,
        )


def create_moergo_simple_service(
    docker_adapter: DockerAdapterProtocol,
) -> MoergoSimpleService:
    """Create simplified Moergo service."""
    return MoergoSimpleService(docker_adapter)
