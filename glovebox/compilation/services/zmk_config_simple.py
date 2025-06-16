"""ZMK config with west compilation service."""

import logging
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from glovebox.compilation.models import (
    CompilationConfigUnion,
    ZmkCompilationConfig,
)
from glovebox.compilation.models.build_matrix import BuildMatrix
from glovebox.compilation.models.west_config import (
    WestManifest,
)
from glovebox.compilation.protocols.compilation_protocols import (
    CompilationServiceProtocol,
)
from glovebox.firmware.models import BuildResult, FirmwareOutputFiles
from glovebox.models.docker import DockerUserContext
from glovebox.protocols import DockerAdapterProtocol


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile


class ZmkWestService(CompilationServiceProtocol):
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
        config: CompilationConfigUnion,
        keyboard_profile: "KeyboardProfile",
    ) -> BuildResult:
        """Execute ZMK compilation."""
        self.logger.info("Starting ZMK config compilation")

        try:
            if not isinstance(config, ZmkCompilationConfig):
                return BuildResult(
                    success=False, errors=["Invalid config type for ZMK compilation"]
                )

            # Try to use cached workspace first
            workspace_path = self._get_or_create_workspace(
                keymap_file, config_file, config
            )
            if not workspace_path:
                return BuildResult(success=False, errors=["Workspace setup failed"])

            compilation_success = self._run_compilation(workspace_path, config)

            # Always try to collect artifacts, even on build failure (for debugging)
            output_files = self._collect_files(workspace_path, output_dir)

            if not compilation_success:
                return BuildResult(
                    success=False,
                    errors=["Compilation failed"],
                    output_files=output_files,  # Include partial artifacts for debugging
                )

            # Cache workspace after successful compilation
            self._cache_workspace(workspace_path, config)

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

    def validate_config(self, config: CompilationConfigUnion) -> bool:
        """Validate configuration."""
        return isinstance(config, ZmkCompilationConfig) and bool(config.image)

    def check_available(self) -> bool:
        """Check availability."""
        return self.docker_adapter is not None

    def _get_cached_workspace(self, config: ZmkCompilationConfig) -> Path | None:
        """Get cached workspace if available."""
        if not config.use_cache:
            return None

        # Use repository as cache key
        repo_name = config.repository.replace("/", "_").replace("-", "_")
        cache_dir = Path.home() / ".cache" / "glovebox" / "workspaces" / repo_name

        if cache_dir.exists() and (cache_dir / "zmk").exists():
            self.logger.info("Using cached workspace: %s", cache_dir)
            return cache_dir
        return None

    def _cache_workspace(
        self, workspace_path: Path, config: ZmkCompilationConfig
    ) -> None:
        """Cache workspace for future use."""
        if not config.use_cache:
            return

        repo_name = config.repository.replace("/", "_").replace("-", "_")
        cache_dir = Path.home() / ".cache" / "glovebox" / "workspaces" / repo_name

        if cache_dir.exists():
            return  # Already cached

        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            # Copy the west workspace directories
            for subdir in ["modules", "zephyr", "zmk"]:
                if (workspace_path / subdir).exists():
                    shutil.copytree(workspace_path / subdir, cache_dir / subdir)
            self.logger.info(
                "Cached workspace for %s: %s", config.repository, cache_dir
            )
        except Exception as e:
            self.logger.warning("Failed to cache workspace: %s", e)

    def _get_or_create_workspace(
        self, keymap_file: Path, config_file: Path, config: ZmkCompilationConfig
    ) -> Path | None:
        """Get cached workspace or create new one."""
        # Try to use cached workspace
        cached_workspace = self._get_cached_workspace(config)
        if cached_workspace:
            # Create temporary workspace and copy from cache
            workspace_path = Path(tempfile.mkdtemp(prefix="zmk_"))
            try:
                # Copy cached workspace
                for subdir in ["modules", "zephyr", "zmk"]:
                    if (cached_workspace / subdir).exists():
                        shutil.copytree(
                            cached_workspace / subdir, workspace_path / subdir
                        )

                # Set up config directory with fresh files
                config_dir = workspace_path / "config"
                self._setup_config_dir(config_dir, keymap_file, config_file, config)
                self.logger.info(
                    "Using cached workspace (will still run west update for branch changes)"
                )
                return workspace_path
            except Exception as e:
                self.logger.warning("Failed to use cached workspace: %s", e)
                shutil.rmtree(workspace_path, ignore_errors=True)

        # Create fresh workspace
        return self._setup_workspace(keymap_file, config_file, config)

    def _setup_workspace(
        self, keymap_file: Path, config_file: Path, config: ZmkCompilationConfig
    ) -> Path | None:
        """Setup temporary workspace."""
        try:
            workspace_path = Path(tempfile.mkdtemp(prefix="zmk_"))
            config_dir = workspace_path / "config"
            self._setup_config_dir(config_dir, keymap_file, config_file, config)

            return workspace_path
        except Exception as e:
            self.logger.error("Workspace setup failed: %s", e)
            return None

    def _setup_config_dir(
        self,
        config_dir: Path,
        keymap_file: Path,
        config_file: Path,
        config: ZmkCompilationConfig,
    ) -> None:
        """Setup config directory with files."""
        config_dir.mkdir(exist_ok=True)

        # Copy files
        shutil.copy2(keymap_file, config_dir / keymap_file.name)
        shutil.copy2(config_file, config_dir / config_file.name)

        # Create build configuration files using proper models
        self._create_build_yaml(config_dir, config)
        self._create_west_yml(config_dir, config)

    def _create_build_yaml(
        self, config_dir: Path, config: ZmkCompilationConfig
    ) -> None:
        """Create build.yaml using proper build matrix models."""
        config.build_matrix.to_yaml(config_dir / "build.yaml")

    def _create_west_yml(self, config_dir: Path, config: ZmkCompilationConfig) -> None:
        """Create west.yml using proper west config models."""
        manifest = WestManifest.from_repository_config(
            repository=config.repository,
            branch=config.branch,
            config_path="config",
            import_file="app/west.yml",
        )

        # Create west manifest
        with (config_dir / "west.yml").open("w") as f:
            f.write(manifest.to_yaml())

    def _run_compilation(
        self, workspace_path: Path, config: ZmkCompilationConfig
    ) -> bool:
        """Run Docker compilation."""
        try:
            # Generate proper build commands using build matrix
            build_commands = self._generate_build_commands(workspace_path, config)
            if not build_commands:
                return False

            base_commands = [
                "cd /workspace",
                "west init -l config",
                "west update",
                "west zephyr-export",
            ]

            all_commands = base_commands + build_commands

            # Use current user context to avoid permission issues
            user_context = DockerUserContext.detect_current_user()

            self.logger.info("Running Docker command: %s", " && ".join(all_commands))

            result: tuple[int, list[str], list[str]] = (
                self.docker_adapter.run_container(
                    image=config.image,
                    command=["sh", "-c", " && ".join(all_commands)],
                    volumes=[(str(workspace_path), "/workspace")],
                    environment={"JOBS": "4"},
                    user_context=user_context,
                )
            )
            return_code, stdout, stderr = result

            if return_code != 0:
                self.logger.error("Build failed with exit code %d", return_code)
                if stderr:
                    self.logger.error("stderr: %s", stderr)
                if stdout:
                    self.logger.info("stdout: %s", stdout)
                return False

            self.logger.info("Build completed successfully")
            return True
        except Exception as e:
            self.logger.error("Docker execution failed: %s", e)
            return False

    def _generate_build_commands(
        self, workspace_path: Path, config: ZmkCompilationConfig
    ) -> list[str]:
        """Generate west build commands from build matrix."""
        try:
            build_yaml = workspace_path / "config" / "build.yaml"
            if not build_yaml.exists():
                self.logger.error("build.yaml not found")
                return []

            # Load and parse build matrix
            build_matrix = BuildMatrix.from_yaml(build_yaml)

            build_commands: list[str] = []

            for target in build_matrix.targets:
                build_dir = f"{target.artifact_name}"

                # Build west command
                cmd_parts = [
                    "west build",
                    "-s zmk/app",
                    f"-b {target.board}",
                    f"-d {build_dir}",
                    "--",
                ]

                # Add CMake arguments
                cmake_args = [f"-DZMK_CONFIG={workspace_path}/config"]
                if target.shield:
                    cmake_args.append(f"-DSHIELD={target.shield}")
                if target.cmake_args:
                    cmake_args.extend(target.cmake_args)
                if target.snippet:
                    cmake_args.append(f"-DZMK_EXTRA_MODULES={target.snippet}")

                cmd_parts.extend(cmake_args)
                build_commands.append(" ".join(cmd_parts))

            self.logger.info(
                "Generated %d build commands: %s", len(build_commands), build_commands
            )
            return build_commands

        except Exception as e:
            self.logger.error("Failed to generate build commands: %s", e)
            return []

    def _collect_files(
        self, workspace_path: Path, output_dir: Path
    ) -> FirmwareOutputFiles:
        """Collect firmware files from build directories determined by build matrix."""
        output_dir.mkdir(parents=True, exist_ok=True)
        main_uf2 = None
        artifacts_dir = None
        collected_items = []

        try:
            # Use build matrix resolver to determine expected build directories
            build_yaml = workspace_path / "config" / "build.yaml"
            if not build_yaml.exists():
                self.logger.error(
                    "build.yaml not found, cannot determine build directories"
                )
                return FirmwareOutputFiles(
                    output_dir=output_dir, main_uf2=None, artifacts_dir=None
                )

            build_matrix = BuildMatrix.from_yaml(build_yaml)

            # Look for build directories based on build matrix targets
            for target in build_matrix.targets:
                build_dir_name = target.artifact_name
                build_path = workspace_path / build_dir_name
                if not build_path.is_dir():
                    self.logger.warning(
                        "Expected build directory not found: %s", build_path
                    )
                    continue

                try:
                    cur_build_out = output_dir / build_dir_name
                    cur_build_out.mkdir(parents=True, exist_ok=True)

                    if artifacts_dir is None:
                        artifacts_dir = output_dir

                    # Copy firmware files and other artifacts
                    build_collected = self._copy_build_artifacts(
                        build_path, cur_build_out, build_dir_name
                    )
                    collected_items.extend(build_collected)

                    # Set main_uf2 to the first .uf2 file found
                    uf2_file = cur_build_out / "zmk.uf2"
                    if uf2_file.exists() and main_uf2 is None:
                        main_uf2 = uf2_file

                except Exception as e:
                    self.logger.warning(
                        "Failed to copy build directory %s: %s", build_path, e
                    )

        except Exception as e:
            self.logger.error(
                "Failed to resolve build matrix for artifact collection: %s", e
            )

        if collected_items:
            self.logger.info(
                "Collected %d ZMK artifacts: %s",
                len(collected_items),
                ", ".join(collected_items),
            )
        else:
            self.logger.warning("No build artifacts found in workspace")

        return FirmwareOutputFiles(
            output_dir=output_dir,
            main_uf2=main_uf2,
            artifacts_dir=artifacts_dir,
        )

    def _copy_build_artifacts(
        self, build_path: Path, cur_build_out: Path, build_dir_name: str
    ) -> list[str]:
        """Copy artifacts from a single build directory."""
        collected_items = []

        # Define file mappings: [source_path_from_zephyr, destination_filename]
        file_mappings = [
            # Firmware files
            ["zmk.uf2", "zmk.uf2"],
            ["zmk.hex", "zmk.hex"],
            ["zmk.bin", "zmk.bin"],
            ["zmk.elf", "zmk.elf"],
            # Configuration and debug files
            [".config", "zmk.kconfig"],
            ["zephyr.dts", "zmk.dts"],
            ["zephyr.dts.pre", "zmk.dts.pre"],
            ["include/generated/devicetree_generated.h", "devicetree_generated.h"],
        ]

        for src_path, dst_filename in file_mappings:
            src_file = build_path / "zephyr" / src_path
            dst_file = cur_build_out / dst_filename

            if src_file.exists():
                try:
                    shutil.copy2(src_file, dst_file)
                    collected_items.append(f"{build_dir_name}/{dst_filename}")
                except Exception as e:
                    self.logger.warning(
                        "Failed to copy %s to %s: %s", src_file, dst_file, e
                    )

        # Copy UF2 to base output directory with build directory name
        uf2_source = build_path / "zephyr" / "zmk.uf2"
        if uf2_source.exists():
            base_uf2 = cur_build_out.parent / f"{build_dir_name}.uf2"
            try:
                shutil.copy2(uf2_source, base_uf2)
                collected_items.append(f"{build_dir_name}.uf2")
            except Exception as e:
                self.logger.warning("Failed to copy UF2 to base: %s", e)

        return collected_items


def create_zmk_config_simple_service(
    docker_adapter: DockerAdapterProtocol,
) -> ZmkWestService:
    """Create simplified ZMK config service."""
    return ZmkWestService(docker_adapter)
