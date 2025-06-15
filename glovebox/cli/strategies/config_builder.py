"""Configuration builder that loads YAML config first, then applies CLI overrides."""

import logging
from pathlib import Path
from typing import Any

from glovebox.config.compile_methods import (
    CacheConfig,
    DockerCompilationConfig,
    DockerUserConfig,
    MoergoCompilationConfig,
    ZmkCompilationConfig,
    ZmkWorkspaceConfig,
)
from glovebox.config.models.workspace import UserWorkspaceConfig
from glovebox.config.profile import KeyboardProfile
from glovebox.models.docker_path import DockerPath


logger = logging.getLogger(__name__)


class CLIOverrides:
    """CLI arguments that can override YAML configuration values.

    This replaces the massive CompilationParams dataclass with a focused
    class that only contains CLI overrides, not base configuration.
    """

    def __init__(
        self,
        keymap_file: Path,
        kconfig_file: Path,
        output_dir: Path,
        # Docker overrides
        jobs: int | None = None,
        verbose: bool | None = None,
        no_cache: bool | None = None,
        docker_uid: int | None = None,
        docker_gid: int | None = None,
        docker_username: str | None = None,
        docker_home: str | None = None,
        docker_container_home: str | None = None,
        no_docker_user_mapping: bool | None = None,
        # Build overrides
        branch: str | None = None,
        repo: str | None = None,
        board_targets: str | None = None,
        preserve_workspace: bool | None = None,
        force_cleanup: bool | None = None,
        clear_cache: bool | None = None,
    ) -> None:
        """Initialize CLI overrides.

        Args:
            keymap_file: Path to keymap file (required)
            kconfig_file: Path to kconfig file (required)
            output_dir: Path to output directory (required)
            **kwargs: Optional CLI overrides
        """
        # Required files
        self.keymap_file = keymap_file
        self.kconfig_file = kconfig_file
        self.output_dir = output_dir

        # Docker overrides
        self.jobs = jobs
        self.verbose = verbose
        self.no_cache = no_cache
        self.docker_uid = docker_uid
        self.docker_gid = docker_gid
        self.docker_username = docker_username
        self.docker_home = docker_home
        self.docker_container_home = docker_container_home
        self.no_docker_user_mapping = no_docker_user_mapping

        # Build overrides
        self.branch = branch
        self.repo = repo
        self.board_targets = board_targets
        self.preserve_workspace = preserve_workspace
        self.force_cleanup = force_cleanup
        self.clear_cache = clear_cache

    def has_override(self, field: str) -> bool:
        """Check if CLI has an override for the given field.

        Args:
            field: Field name to check

        Returns:
            bool: True if CLI provides an override for this field
        """
        return hasattr(self, field) and getattr(self, field) is not None


class CompilationConfigBuilder:
    """Builds compilation configuration from YAML config + CLI overrides.

    This implements the new architecture:
    1. Load keyboard YAML configuration
    2. Extract compilation method configuration
    3. Apply CLI overrides
    4. Build final configuration object
    """

    def __init__(self) -> None:
        """Initialize configuration builder."""
        self.logger = logging.getLogger(__name__)

    def build_config(
        self,
        profile: KeyboardProfile,
        cli_overrides: CLIOverrides,
        strategy_name: str,
    ) -> DockerCompilationConfig:
        """Build compilation configuration from YAML + CLI overrides.

        Args:
            profile: Keyboard profile with YAML configuration
            cli_overrides: CLI argument overrides
            strategy_name: Strategy name (zmk_config, moergo, etc.)

        Returns:
            DockerCompilationConfig: Unified configuration object

        Raises:
            ValueError: If configuration is invalid or strategy not supported
        """
        self._validate_inputs(cli_overrides)

        # Get base configuration from YAML
        base_config = self._extract_yaml_config(profile, strategy_name)

        # Apply CLI overrides
        final_config = self._apply_cli_overrides(
            base_config, cli_overrides, profile, strategy_name
        )

        self.logger.debug(
            "Built %s configuration with %d CLI overrides",
            strategy_name,
            self._count_overrides(cli_overrides),
        )

        return final_config

    def _validate_inputs(self, cli_overrides: CLIOverrides) -> None:
        """Validate required inputs.

        Args:
            cli_overrides: CLI overrides to validate

        Raises:
            ValueError: If inputs are invalid
        """
        if not cli_overrides.keymap_file.exists():
            raise ValueError(f"Keymap file not found: {cli_overrides.keymap_file}")

        if not cli_overrides.kconfig_file.exists():
            raise ValueError(f"Kconfig file not found: {cli_overrides.kconfig_file}")

        if not cli_overrides.output_dir.parent.exists():
            raise ValueError(
                f"Output directory parent not found: {cli_overrides.output_dir.parent}"
            )

    def _extract_yaml_config(
        self, profile: KeyboardProfile, strategy_name: str
    ) -> dict[str, Any]:
        """Extract configuration from keyboard YAML for the given strategy.

        Args:
            profile: Keyboard profile with YAML configuration
            strategy_name: Strategy name to extract config for

        Returns:
            dict[str, Any]: Base configuration from YAML
        """
        base_config: dict[str, Any] = {}

        # Find matching compile method in YAML
        for method in profile.keyboard_config.compile_methods:
            if hasattr(method, "method_type") and method.method_type == "docker":
                # Extract Docker configuration
                base_config.update(
                    {
                        "image": getattr(
                            method, "image", "zmkfirmware/zmk-build-arm:stable"
                        ),
                        "repository": getattr(method, "repository", "zmkfirmware/zmk"),
                        "branch": getattr(method, "branch", "main"),
                        "jobs": getattr(method, "jobs", None),
                    }
                )
                break

        # Add firmware-specific configuration if available
        if hasattr(profile, "firmware_version") and profile.firmware_version:
            firmware_config = profile.firmware_version
            if hasattr(firmware_config, "build_options"):
                build_options = firmware_config.build_options
                base_config.update(
                    {
                        "repository": getattr(
                            build_options, "repository", base_config.get("repository")
                        ),
                        "branch": getattr(
                            build_options, "branch", base_config.get("branch")
                        ),
                    }
                )

        return base_config

    def _apply_cli_overrides(
        self,
        base_config: dict[str, Any],
        cli_overrides: CLIOverrides,
        profile: KeyboardProfile,
        strategy_name: str,
    ) -> DockerCompilationConfig:
        """Apply CLI overrides to base YAML configuration.

        Args:
            base_config: Base configuration from YAML
            cli_overrides: CLI overrides to apply
            profile: Keyboard profile
            strategy_name: Strategy name to use for configuration type

        Returns:
            DockerCompilationConfig: Final configuration with overrides applied
        """
        # Build Docker user configuration
        docker_user_config = self._build_docker_user_config(cli_overrides)

        # Build cache configuration
        cache_config = self._build_cache_config(cli_overrides)

        # Apply CLI overrides to base config
        final_config = base_config.copy()

        if cli_overrides.has_override("jobs"):
            final_config["jobs"] = cli_overrides.jobs
        if cli_overrides.has_override("branch"):
            final_config["branch"] = cli_overrides.branch
        if cli_overrides.has_override("repo"):
            final_config["repository"] = cli_overrides.repo

        # Use the strategy name to determine config type
        if strategy_name == "moergo":
            return self._build_moergo_config(
                final_config, docker_user_config, cli_overrides, profile
            )
        else:
            return self._build_zmk_config(
                final_config, docker_user_config, cache_config, cli_overrides, profile
            )

    def _build_docker_user_config(
        self, cli_overrides: CLIOverrides
    ) -> DockerUserConfig:
        """Build Docker user configuration from CLI overrides.

        Args:
            cli_overrides: CLI overrides

        Returns:
            DockerUserConfig: Docker user configuration
        """
        enable_user_mapping = True
        if cli_overrides.has_override("no_docker_user_mapping"):
            enable_user_mapping = not cli_overrides.no_docker_user_mapping

        return DockerUserConfig(
            enable_user_mapping=enable_user_mapping,
            manual_uid=cli_overrides.docker_uid,
            manual_gid=cli_overrides.docker_gid,
            manual_username=cli_overrides.docker_username,
            host_home_dir=Path(cli_overrides.docker_home)
            if cli_overrides.docker_home
            else None,
            container_home_dir=cli_overrides.docker_container_home or "/tmp",
        )

    def _build_cache_config(self, cli_overrides: CLIOverrides) -> CacheConfig:
        """Build cache configuration from CLI overrides.

        Args:
            cli_overrides: CLI overrides

        Returns:
            CacheConfig: Cache configuration
        """
        cache_enabled = True
        if cli_overrides.has_override("no_cache"):
            cache_enabled = not cli_overrides.no_cache

        return CacheConfig(enabled=cache_enabled)

    def _determine_strategy_type(self, profile: KeyboardProfile) -> str:
        """Determine strategy type from profile.

        Args:
            profile: Keyboard profile

        Returns:
            str: Strategy type (moergo, zmk_config, etc.)
        """
        keyboard_name = getattr(profile, "keyboard_name", "").lower()
        if "moergo" in keyboard_name or "glove80" in keyboard_name:
            return "moergo"
        return "zmk_config"

    def _build_moergo_config(
        self,
        config: dict[str, Any],
        docker_user_config: DockerUserConfig,
        cli_overrides: CLIOverrides,
        profile: KeyboardProfile,
    ) -> MoergoCompilationConfig:
        """Build Moergo compilation configuration.

        Args:
            config: Base configuration
            docker_user_config: Docker user configuration
            cli_overrides: CLI overrides
            profile: Keyboard profile

        Returns:
            MoergoCompilationConfig: Moergo configuration
        """
        workspace_path = DockerPath(
            host_path=cli_overrides.output_dir.parent, container_path="/workspace"
        )

        return MoergoCompilationConfig(
            image=config.get("image", "glove80-zmk-config-docker"),
            repository=config.get("repository", "moergo-sc/zmk"),
            branch=config.get("branch", "v25.05"),
            jobs=config.get("jobs"),
            docker_user=DockerUserConfig(
                enable_user_mapping=False
            ),  # Moergo disables user mapping
            workspace_path=workspace_path,
        )

    def _build_zmk_config(
        self,
        config: dict[str, Any],
        docker_user_config: DockerUserConfig,
        cache_config: CacheConfig,
        cli_overrides: CLIOverrides,
        profile: KeyboardProfile,
    ) -> ZmkCompilationConfig:
        """Build ZMK compilation configuration.

        Args:
            config: Base configuration
            docker_user_config: Docker user configuration
            cache_config: Cache configuration
            cli_overrides: CLI overrides
            profile: Keyboard profile

        Returns:
            ZmkCompilationConfig: ZMK configuration
        """
        # Build workspace configuration
        workspace_config = self._build_workspace_config(cli_overrides, profile, config)

        # Build YAML configuration for build matrix
        from glovebox.compilation.models.build_matrix import BuildYamlConfig

        build_yaml_config = BuildYamlConfig()

        return ZmkCompilationConfig(
            image=config.get("image", "zmkfirmware/zmk-build-arm:stable"),
            jobs=config.get("jobs"),
            docker_user=docker_user_config,
            cache=cache_config,
            build_config=build_yaml_config,
            workspace=workspace_config,
        )

    def _build_workspace_config(
        self,
        cli_overrides: CLIOverrides,
        profile: KeyboardProfile,
        config: dict[str, Any],
    ) -> ZmkWorkspaceConfig:
        """Build ZMK workspace configuration.

        Args:
            cli_overrides: CLI overrides
            profile: Keyboard profile
            config: Base configuration

        Returns:
            ZmkWorkspaceConfig: ZMK workspace configuration
        """
        user_workspace_config = UserWorkspaceConfig()
        workspace_root = (
            user_workspace_config.root_directory / f"zmk_{profile.keyboard_name}"
        )

        workspace_path = DockerPath(
            host_path=workspace_root, container_path="/workspace"
        )

        config_path = DockerPath(
            host_path=workspace_root / "config", container_path="/workspace/config"
        )

        build_root = DockerPath(
            host_path=cli_overrides.output_dir, container_path="/workspace/build"
        )

        return ZmkWorkspaceConfig(
            repository=config.get("repository", "zmkfirmware/zmk"),
            branch=config.get("branch", "main"),
            workspace_path=workspace_path,
            config_path=config_path,
            build_root=build_root,
            build_matrix_file=Path("build.yaml"),
            config_repo_url=cli_overrides.repo,
        )

    def _count_overrides(self, cli_overrides: CLIOverrides) -> int:
        """Count number of CLI overrides provided.

        Args:
            cli_overrides: CLI overrides

        Returns:
            int: Number of non-None override values
        """
        count = 0
        for attr in dir(cli_overrides):
            if not attr.startswith("_") and attr not in [
                "keymap_file",
                "kconfig_file",
                "output_dir",
            ]:
                if getattr(cli_overrides, attr) is not None:
                    count += 1
        return count


def create_config_builder() -> CompilationConfigBuilder:
    """Create configuration builder.

    Returns:
        CompilationConfigBuilder: Configured builder instance
    """
    return CompilationConfigBuilder()
