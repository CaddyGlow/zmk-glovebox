"""Ultra-simplified Moergo compilation service."""

import logging
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from glovebox.compilation.protocols.compilation_protocols import (
    CompilationServiceProtocol,
)
from glovebox.config.minimal_compile_config import (
    MinimalCompileConfigUnion,
    MinimalMoergoConfig,
)
from glovebox.firmware.models import BuildResult, FirmwareOutputFiles
from glovebox.models.docker import DockerUserContext
from glovebox.models.docker_path import DockerPath
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
        config: MinimalCompileConfigUnion,
        keyboard_profile: "KeyboardProfile",
    ) -> BuildResult:
        """Execute Moergo compilation."""
        self.logger.info("Starting Moergo compilation")

        try:
            if not isinstance(config, MinimalMoergoConfig):
                return BuildResult(success=False, errors=["Invalid config type"])

            workspace_path = self._setup_workspace(
                keymap_file, config_file, keyboard_profile
            )
            if not workspace_path or not workspace_path.host_path:
                return BuildResult(success=False, errors=["Workspace setup failed"])

            compilation_success = self._run_compilation(workspace_path, config)

            # Always try to collect artifacts, even on build failure (for debugging)
            output_files = self._collect_files(workspace_path.host_path, output_dir)

            if not compilation_success:
                return BuildResult(
                    success=False,
                    errors=["Compilation failed"],
                    output_files=output_files,  # Include partial artifacts for debugging
                )
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
        return isinstance(config, MinimalMoergoConfig) and bool(config.image)

    def check_available(self) -> bool:
        """Check availability."""
        return self.docker_adapter is not None

    def _setup_workspace(
        self, keymap_file: Path, config_file: Path, keyboard_profile: "KeyboardProfile"
    ) -> DockerPath | None:
        """Setup temporary workspace."""
        try:
            workspace_path = DockerPath(
                host_path=Path(tempfile.mkdtemp(prefix="moergo_")),
                container_path="/workspace",
            )
            assert workspace_path.host_path is not None

            config_dir = workspace_path.host_path / "config"
            config_dir.mkdir(parents=True)

            # Copy files with Moergo expected names
            shutil.copy2(keymap_file, config_dir / "glove80.keymap")
            shutil.copy2(config_file, config_dir / "glove80.conf")

            # Load default.nix from keyboard's toolchain directory
            default_nix_content = keyboard_profile.load_toolchain_file("default.nix")
            if not default_nix_content:
                self.logger.error("Could not load default.nix from keyboard toolchain")
                return None

            (config_dir / "default.nix").write_text(default_nix_content)
            return workspace_path
        except Exception as e:
            self.logger.error("Workspace setup failed: %s", e)
            return None

    def _run_compilation(
        self, workspace_path: DockerPath, config: MinimalMoergoConfig
    ) -> bool:
        """Run Docker compilation."""
        try:
            # For Moergo, disable user mapping and pass user info via environment
            user_context = DockerUserContext.detect_current_user()
            user_context.enable_user_mapping = False

            # Build environment with user information and ZMK repository config
            environment = {
                "PUID": str(user_context.uid),
                "PGID": str(user_context.gid),
                "REPO": config.repository,
                "BRANCH": config.branch,
            }

            return_code, _, stderr = self.docker_adapter.run_container(
                image=config.image,
                command=["build.sh"],  # Use the build script, not direct nix-build
                volumes=[workspace_path.vol()],
                environment=environment,
                user_context=user_context,
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
        """Collect firmware files from artifacts directory, including partial artifacts for debugging."""
        output_dir.mkdir(parents=True, exist_ok=True)
        main_uf2 = None
        artifacts_dir = None
        collected_items = []

        # Look for artifacts directory created by build.sh
        build_artifacts_dir = workspace_path / "artifacts"
        if build_artifacts_dir.exists():
            try:
                # Copy all contents of artifacts directory directly to output directory
                for item in build_artifacts_dir.iterdir():
                    try:
                        if item.is_file():
                            shutil.copy2(item, output_dir / item.name)
                            collected_items.append(f"file: {item.name}")
                        elif item.is_dir():
                            shutil.copytree(item, output_dir / item.name)
                            collected_items.append(f"directory: {item.name}")
                    except Exception as e:
                        self.logger.warning("Failed to copy artifact %s: %s", item, e)

                artifacts_dir = output_dir

                # Find the main combined firmware file
                main_firmware = output_dir / "glove80.uf2"
                if main_firmware.exists():
                    main_uf2 = main_firmware

                self.logger.info(
                    "Collected %d Moergo artifacts: %s",
                    len(collected_items),
                    ", ".join(collected_items),
                )
            except Exception as e:
                self.logger.error(
                    "Error collecting artifacts from %s: %s", build_artifacts_dir, e
                )
        else:
            self.logger.warning(
                "No artifacts directory found at %s - checking for partial files",
                build_artifacts_dir,
            )

            # Even without artifacts directory, check for any generated files in workspace
            partial_files: list[Path] = []
            for pattern in ["*.uf2", "*.log", "*.json", "*.dts", "*.h"]:
                partial_files.extend(workspace_path.glob(f"**/{pattern}"))

            if partial_files:
                self.logger.info(
                    "Found %d partial files for debugging: %s",
                    len(partial_files),
                    [f.name for f in partial_files],
                )
                for partial_file in partial_files:
                    try:
                        shutil.copy2(partial_file, output_dir / partial_file.name)
                        collected_items.append(f"partial: {partial_file.name}")
                    except Exception as e:
                        self.logger.warning(
                            "Failed to copy partial file %s: %s", partial_file, e
                        )

        return FirmwareOutputFiles(
            output_dir=output_dir,
            main_uf2=main_uf2,
            artifacts_dir=artifacts_dir,
        )


def create_moergo_simple_service(
    docker_adapter: DockerAdapterProtocol,
) -> MoergoSimpleService:
    """Create simplified Moergo service."""
    return MoergoSimpleService(docker_adapter)
