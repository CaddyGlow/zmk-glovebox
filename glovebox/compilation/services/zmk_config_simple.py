"""Ultra-simplified ZMK config compilation service."""

import logging
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from glovebox.compilation.configuration.build_matrix_resolver import (
    create_build_matrix_resolver,
)
from glovebox.compilation.models.build_matrix import BuildYamlConfig
from glovebox.compilation.models.west_config import (
    WestManifest,
    WestManifestConfig,
    WestProject,
    WestRemote,
    WestSelf,
)
from glovebox.compilation.protocols.compilation_protocols import (
    CompilationServiceProtocol,
)
from glovebox.config.minimal_compile_config import (
    MinimalCompileConfigUnion,
    MinimalZmkConfig,
)
from glovebox.firmware.models import BuildResult, FirmwareOutputFiles
from glovebox.models.docker import DockerUserContext
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

    def validate_config(self, config: MinimalCompileConfigUnion) -> bool:
        """Validate configuration."""
        return isinstance(config, MinimalZmkConfig) and bool(config.image)

    def check_available(self) -> bool:
        """Check availability."""
        return self.docker_adapter is not None

    def _get_cached_workspace(self, config: MinimalZmkConfig) -> Path | None:
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

    def _cache_workspace(self, workspace_path: Path, config: MinimalZmkConfig) -> None:
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
        self, keymap_file: Path, config_file: Path, config: MinimalZmkConfig
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
                self._setup_config_dir(workspace_path, keymap_file, config_file, config)
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
        self, keymap_file: Path, config_file: Path, config: MinimalZmkConfig
    ) -> Path | None:
        """Setup temporary workspace."""
        try:
            workspace_path = Path(tempfile.mkdtemp(prefix="zmk_"))
            config_dir = workspace_path / "config"
            config_dir.mkdir()

            # Copy files
            shutil.copy2(keymap_file, config_dir / keymap_file.name)
            shutil.copy2(config_file, config_dir / config_file.name)

            # Create build configuration files using proper models
            self._create_build_yaml(config_dir, config)
            self._create_west_yml(config_dir, config)

            return workspace_path
        except Exception as e:
            self.logger.error("Workspace setup failed: %s", e)
            return None

    def _setup_config_dir(
        self,
        workspace_path: Path,
        keymap_file: Path,
        config_file: Path,
        config: MinimalZmkConfig,
    ) -> None:
        """Setup config directory with files."""
        config_dir = workspace_path / "config"
        config_dir.mkdir(exist_ok=True)

        # Copy files
        shutil.copy2(keymap_file, config_dir / keymap_file.name)
        shutil.copy2(config_file, config_dir / config_file.name)

        # Create build configuration files using proper models
        self._create_build_yaml(config_dir, config)
        self._create_west_yml(config_dir, config)

    def _create_build_yaml(self, config_dir: Path, config: MinimalZmkConfig) -> None:
        """Create build.yaml using proper build matrix models."""
        # Create build matrix configuration
        if config.shields:
            # Board + shield combinations
            include_entries = []
            for board in config.boards:
                for shield in config.shields:
                    include_entries.append({"board": board, "shield": shield})
            build_config = BuildYamlConfig(include=include_entries)
        else:
            # Board-only builds
            include_entries = [{"board": board} for board in config.boards]
            build_config = BuildYamlConfig(include=include_entries)

        # Write using the build matrix resolver
        resolver = create_build_matrix_resolver()
        resolver.write_config_to_yaml(build_config, config_dir / "build.yaml")

    def _create_west_yml(self, config_dir: Path, config: MinimalZmkConfig) -> None:
        """Create west.yml using proper west config models."""
        # Parse repository to get remote info
        if "/" in config.repository:
            if config.repository.startswith("https://github.com/"):
                repo_parts = config.repository.replace("https://github.com/", "").split(
                    "/"
                )
            else:
                repo_parts = config.repository.split("/")
            remote_name = repo_parts[0]
            repo_name = repo_parts[1]
            url_base = f"https://github.com/{remote_name}"
        else:
            remote_name = "zmkfirmware"
            repo_name = config.repository
            url_base = "https://github.com/zmkfirmware"

        # Create west manifest using proper models
        west_config = WestManifestConfig(
            manifest=WestManifest(
                remotes=[WestRemote(name=remote_name, url_base=url_base)],
                projects=[
                    WestProject(
                        name=repo_name,
                        remote=remote_name,
                        revision=config.branch,
                        import_="app/west.yml",
                    )
                ],
                self=WestSelf(path="config"),
            )
        )

        # Write to YAML file
        with (config_dir / "west.yml").open("w") as f:
            yaml.safe_dump(
                west_config.model_dump(by_alias=True, exclude_none=True),
                f,
                default_flow_style=False,
                sort_keys=False,
            )

    def _run_compilation(self, workspace_path: Path, config: MinimalZmkConfig) -> bool:
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

            return_code, stdout, stderr = self.docker_adapter.run_container(
                image=config.image,
                command=["sh", "-c", " && ".join(all_commands)],
                volumes=[(str(workspace_path), "/workspace")],
                environment={"JOBS": "4"},
                user_context=user_context,
            )

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
        self, workspace_path: Path, config: MinimalZmkConfig
    ) -> list[str]:
        """Generate west build commands from build matrix."""
        try:
            build_yaml = workspace_path / "config" / "build.yaml"
            if not build_yaml.exists():
                self.logger.error("build.yaml not found")
                return []

            # Load and parse build matrix
            resolver = create_build_matrix_resolver()
            build_matrix = resolver.resolve_from_build_yaml(build_yaml)

            build_commands: list[str] = []

            for _i, target in enumerate(build_matrix.targets):
                build_dir = f"{target.artifact_name or target.board}"
                if target.shield:
                    build_dir = f"{target.shield}-{target.board}"

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
            if build_yaml.exists():
                resolver = create_build_matrix_resolver()
                build_matrix = resolver.resolve_from_build_yaml(build_yaml)

                # Look for build directories based on build matrix targets
                for target in build_matrix.targets:
                    build_dir_name = f"{target.artifact_name or target.board}"
                    if target.shield:
                        build_dir_name = f"{target.shield}-{target.board}"

                    build_path = workspace_path / build_dir_name
                    if build_path.is_dir():
                        try:
                            # cp zephyr/zmk.{uf2,hex,bin,elf} $out
                            # cp zephyr/.config $out/zmk.kconfig
                            # cp zephyr/zephyr.dts $out/zmk.dts
                            # cp zephyr/include/generated/devicetree_generated.h $out/devicetree_generated.h
                            targets = ["uf2", "hex", "bin", "elf"]

                            cur_build_out = output_dir / build_dir_name
                            for ext in targets:
                                fn = build_path / "zephyr" / f"zmk.{ext}"
                                if fn.exists():
                                    shutil.copy2(fn, cur_build_out / f"zmk.{ext}")
                                    collected_items.append(f"{fn}")

                            other_files = [
                                [
                                    ".config",
                                    "zmk.config",
                                ],
                                [
                                    "zephyr.dts",
                                    "zmk.dts",
                                ],
                                [
                                    "include/generated/devicetree_generated.h",
                                    "devicetree_generated.h",
                                ],
                            ]
                            for src, dst in other_files:
                                fn = build_path / "zephyr" / src
                                if fn.exists():
                                    shutil.copy2(fn, cur_build_out / dst)

                        except Exception as e:
                            self.logger.warning(
                                "Failed to copy build directory %s: %s", build_path, e
                            )
                    else:
                        self.logger.warning(
                            "Expected build directory not found: %s", build_path
                        )
            else:
                self.logger.error(
                    "build.yaml not found, cannot determine build directories"
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


def create_zmk_config_simple_service(
    docker_adapter: DockerAdapterProtocol,
) -> ZmkConfigSimpleService:
    """Create simplified ZMK config service."""
    return ZmkConfigSimpleService(docker_adapter)
