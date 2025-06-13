"""ZMK Config content generator for dynamic workspace creation."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from glovebox.adapters import FileAdapter
from glovebox.compilation.models.build_matrix import BuildTargetConfig, BuildYamlConfig
from glovebox.compilation.models.compilation_params import (
    ZmkConfigFileParams,
    ZmkConfigGenerationParams,
)
from glovebox.compilation.models.west_config import (
    WestDefaults,
    WestManifest,
    WestManifestConfig,
    WestProject,
    WestRemote,
    WestSelf,
    WestWorkspaceConfig,
)
from glovebox.core.errors import GloveboxError
from glovebox.models.docker_path import create_zmk_docker_paths


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile


logger = logging.getLogger(__name__)


class ZmkConfigGenerationError(GloveboxError):
    """Error in ZMK config content generation."""


class ZmkConfigContentGenerator:
    """Generate ZMK config repository content on-the-fly.

    Creates the necessary files (build.yaml, west.yml, keymap, conf)
    for a ZMK config repository without requiring an external repository.
    """

    def __init__(
        self,
        file_adapter: FileAdapter | None = None,
    ) -> None:
        """Initialize ZMK config content generator.

        Args:
            file_adapter: File operations adapter
        """
        self.file_adapter = file_adapter
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def generate_config_workspace(
        self,
        params: ZmkConfigGenerationParams,
    ) -> bool:
        """Generate complete ZMK config workspace from glovebox files.

        Args:
            params: Consolidated generation parameters with Docker paths

        Returns:
            bool: True if workspace generated successfully

        Raises:
            ZmkConfigGenerationError: If generation fails
        """
        try:
            self.logger.info(
                "Generating ZMK config workspace at %s", params.workspace_path
            )

            # Ensure workspace directory exists
            if not self._ensure_workspace_directory(params.workspace_path):
                return False

            # Create file-specific parameters for helper methods
            file_params = ZmkConfigFileParams(
                workspace_path=params.workspace_path,
                keyboard_profile=params.keyboard_profile,
                shield_name=params.effective_shield_name,
                docker_paths=params.docker_paths,
                board_name=params.board_name,
                zephyr_base_path=params.zephyr_base_path,
            )

            # Generate build.yaml for GitHub Actions style builds
            if not self._generate_build_yaml(file_params):
                return False

            # Generate west.yml for workspace configuration
            if not self._generate_west_yml(file_params):
                return False

            # Create config directory and copy keymap/config files
            if not self._setup_config_directory(params, file_params):
                return False

            # Generate additional files for compatibility
            if not self._generate_additional_files(file_params):
                return False

            self.logger.info("ZMK config workspace generated successfully")
            return True

        except Exception as e:
            msg = f"Failed to generate ZMK config workspace: {e}"
            self.logger.error(msg)
            raise ZmkConfigGenerationError(msg) from e

    def _ensure_workspace_directory(self, workspace_path: Path) -> bool:
        """Ensure workspace directory exists.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            bool: True if directory exists or was created
        """
        try:
            if self.file_adapter:
                self.file_adapter.create_directory(workspace_path)
                return True
            else:
                workspace_path.mkdir(parents=True, exist_ok=True)
                return True
        except Exception as e:
            self.logger.error("Failed to create workspace directory: %s", e)
            return False

    def _generate_build_yaml(self, params: ZmkConfigFileParams) -> bool:
        """Generate build.yaml file for GitHub Actions builds.

        Args:
            params: File generation parameters

        Returns:
            bool: True if build.yaml generated successfully
        """
        build_yaml_content = self._create_build_yaml_content(
            params.shield_name, params.board_name
        )
        build_yaml_path = params.workspace_path / "build.yaml"

        try:
            if self.file_adapter:
                self.file_adapter.write_text(build_yaml_path, build_yaml_content)
            else:
                build_yaml_path.write_text(build_yaml_content)

            self.logger.debug("Generated build.yaml at %s", build_yaml_path)
            return True
        except Exception as e:
            self.logger.error("Failed to generate build.yaml: %s", e)
            return False

    def _create_build_yaml_content(self, shield_name: str, board_name: str) -> str:
        """Create build.yaml content using BuildYamlConfig model.

        Args:
            shield_name: Shield name for builds
            board_name: Board name for builds

        Returns:
            str: build.yaml content
        """
        # Detect if this is a split keyboard by shield name patterns
        is_split = any(
            indicator in shield_name.lower()
            for indicator in ["corne", "crkbd", "lily58", "sofle", "kyria", "glove80"]
        )

        # Create BuildYamlConfig based on keyboard type
        if is_split:
            if "glove80" in shield_name.lower():
                # Glove80 uses board array format (boards, not shields)
                build_config = BuildYamlConfig(
                    board=[f"{shield_name}_lh", f"{shield_name}_rh"],
                    shield=[],
                    include=[],
                )
            else:
                # Standard ZMK split keyboards use include format with shields
                left_suffix = "_left"
                right_suffix = "_right"
                build_config = BuildYamlConfig(
                    board=[],
                    shield=[],
                    include=[
                        BuildTargetConfig(
                            board=board_name, shield=f"{shield_name}{left_suffix}"
                        ).model_dump(exclude_none=True),
                        BuildTargetConfig(
                            board=board_name, shield=f"{shield_name}{right_suffix}"
                        ).model_dump(exclude_none=True),
                    ],
                )
        else:
            # Generate single keyboard build target
            build_config = BuildYamlConfig(
                board=[],
                shield=[],
                include=[
                    BuildTargetConfig(board=board_name, shield=shield_name).model_dump(
                        exclude_none=True
                    )
                ],
            )

        # Convert to YAML with GitHub Actions matrix header comment
        header_comment = """# This file generates the GitHub Actions matrix.
# For simple board + shield combinations, add them to the top level board and
# shield arrays, for more control, add individual board + shield combinations
# to the `include` property. You can also use the `cmake-args` property to
# pass flags to the build command, `snippet` to add a Zephyr snippet, and
# `artifact-name` to assign a name to distinguish build outputs from each other:
#
# board: [ "nice_nano_v2" ]
# shield: [ "corne_left", "corne_right" ]
# include:
#   - board: bdn9_rev2
#   - board: nice_nano_v2
#     shield: reviung41
#   - board: nice_nano_v2
#     shield: corne_left
#     snippet: studio-rpc-usb-uart
#     cmake-args: -DCONFIG_ZMK_STUDIO=y
#     artifact-name: corne_left_with_studio
#
---"""

        # Serialize BuildYamlConfig to YAML, excluding empty arrays
        config_dict = build_config.model_dump(exclude_none=True, exclude_unset=True)

        # Remove empty arrays for cleaner output
        if not config_dict.get("board"):
            config_dict.pop("board", None)
        if not config_dict.get("shield"):
            config_dict.pop("shield", None)
        if not config_dict.get("include"):
            config_dict.pop("include", None)

        yaml_content = yaml.dump(config_dict, default_flow_style=False, sort_keys=False)

        return f"{header_comment}\n{yaml_content}"

    def _generate_west_yml(self, params: ZmkConfigFileParams) -> bool:
        """Generate west.yml for ZMK workspace configuration using WestManifestConfig.

        Args:
            params: File generation parameters

        Returns:
            bool: True if west.yml generated successfully
        """
        west_config = self._create_west_config(params.keyboard_profile)

        # Use config directory from Docker paths
        config_dir = params.config_directory_host
        west_yml_path = config_dir / "west.yml"

        try:
            # Ensure config directory exists
            if self.file_adapter:
                self.file_adapter.create_directory(config_dir)
            else:
                config_dir.mkdir(parents=True, exist_ok=True)

            # Serialize west config to YAML
            west_yml_content = self._serialize_west_config(west_config)

            # Write west.yml
            if self.file_adapter:
                self.file_adapter.write_text(west_yml_path, west_yml_content)
            else:
                west_yml_path.write_text(west_yml_content)

            self.logger.debug("Generated west.yml at %s", west_yml_path)
            return True
        except Exception as e:
            self.logger.error("Failed to generate west.yml: %s", e)
            return False

    def _create_west_config(
        self, keyboard_profile: "KeyboardProfile"
    ) -> WestManifestConfig:
        """Create WestManifestConfig from keyboard profile.

        Args:
            keyboard_profile: Keyboard profile to determine ZMK repository

        Returns:
            WestManifestConfig: West manifest configuration
        """
        # Determine the correct ZMK repository and branch based on firmware config
        if keyboard_profile.firmware_config is not None:
            # Use firmware configuration's repository and branch
            build_options = keyboard_profile.firmware_config.build_options
            repository_url = build_options.repository
            branch = build_options.branch

            # Extract repository name and organization from URL or org/repo format
            if repository_url.startswith("https://github.com/"):
                repo_path = repository_url.replace("https://github.com/", "")
                org_name, repo_name = repo_path.split("/")
            elif "/" in repository_url:
                # Handle org/repo format (e.g., "moergo-sc/zmk")
                org_name, repo_name = repository_url.split("/")
            else:
                # Fallback for unknown formats
                org_name = "zmkfirmware"
                repo_name = "zmk"
        elif "glove80" in keyboard_profile.keyboard_name.lower():
            # Fallback: Glove80 uses MoErgo's ZMK fork
            org_name = "moergo-sc"
            repo_name = "zmk"
            branch = "main"
        else:
            # Fallback: Standard ZMK repository for other keyboards
            org_name = "zmkfirmware"
            repo_name = "zmk"
            branch = "main"

        # Create west manifest configuration
        return WestManifestConfig(
            manifest=WestManifest(
                defaults=WestDefaults(remote=org_name)
                if org_name == "zmkfirmware"
                else None,
                remotes=[
                    WestRemote(name=org_name, url_base=f"https://github.com/{org_name}")
                ],
                projects=[
                    WestProject(
                        name=repo_name,
                        remote=org_name,
                        revision=branch,
                        import_="app/west.yml",
                    )
                ],
                self=WestSelf(path="config"),
            )
        )

    def _serialize_west_config(self, west_config: WestManifestConfig) -> str:
        """Serialize WestManifestConfig to YAML string.

        Args:
            west_config: West manifest configuration

        Returns:
            str: YAML content for west.yml
        """
        # Convert to dict for YAML serialization, using aliases
        config_dict = west_config.model_dump(by_alias=True, exclude_none=True)

        # Add header comment
        header_comment = "# West configuration for ZMK - Generated by Glovebox"

        # Serialize to YAML
        yaml_content = yaml.dump(config_dict, default_flow_style=False, sort_keys=False)

        return f"{header_comment}\n{yaml_content}"

    def _setup_config_directory(
        self,
        generation_params: ZmkConfigGenerationParams,
        file_params: ZmkConfigFileParams,
    ) -> bool:
        """Setup config directory with keymap and config files.

        Args:
            generation_params: Generation parameters with source files
            file_params: File-specific parameters

        Returns:
            bool: True if config directory setup successfully
        """
        # Always create workspace config directory for west.yml
        workspace_config_dir = generation_params.workspace_config_directory_host

        # Get config directory from Docker paths
        config_dir = file_params.config_directory_host

        try:
            # Ensure both directories exist
            if self.file_adapter:
                self.file_adapter.create_directory(workspace_config_dir)
                if config_dir != workspace_config_dir:
                    self.file_adapter.create_directory(config_dir)
            else:
                workspace_config_dir.mkdir(parents=True, exist_ok=True)
                if config_dir != workspace_config_dir:
                    config_dir.mkdir(parents=True, exist_ok=True)

            # Copy keymap file
            keymap_dest = config_dir / f"{file_params.shield_name}.keymap"
            if self.file_adapter:
                keymap_content = self.file_adapter.read_text(
                    generation_params.keymap_file
                )
                self.file_adapter.write_text(keymap_dest, keymap_content)
            else:
                keymap_content = generation_params.keymap_file.read_text()
                keymap_dest.write_text(keymap_content)

            # Copy config file
            config_dest = config_dir / f"{file_params.shield_name}.conf"
            if self.file_adapter:
                config_content = self.file_adapter.read_text(
                    generation_params.config_file
                )
                self.file_adapter.write_text(config_dest, config_content)
            else:
                config_content = generation_params.config_file.read_text()
                config_dest.write_text(config_content)

            self.logger.debug("Copied keymap and config files to %s", config_dir)
            return True

        except Exception as e:
            self.logger.error("Failed to setup config directory: %s", e)
            return False

    def _generate_additional_files(self, params: ZmkConfigFileParams) -> bool:
        """Generate additional files for workspace compatibility.

        Args:
            params: File generation parameters

        Returns:
            bool: True if additional files generated successfully
        """
        try:
            # Generate README.md for the workspace
            readme_content = self._create_readme_content(params.keyboard_profile)
            readme_path = params.workspace_path / "README.md"

            if self.file_adapter:
                self.file_adapter.write_text(readme_path, readme_content)
            else:
                readme_path.write_text(readme_content)

            # Generate .gitignore for the workspace
            gitignore_content = """# ZMK Workspace - Generated by Glovebox
.west/
build/
*.tmp
*.swp
*.swo
*~
"""
            gitignore_path = params.workspace_path / ".gitignore"

            if self.file_adapter:
                self.file_adapter.write_text(gitignore_path, gitignore_content)
            else:
                gitignore_path.write_text(gitignore_content)

            # Generate .west/config file for workspace configuration
            if not self._generate_west_config_file(params):
                return False

            self.logger.debug("Generated additional workspace files")
            return True

        except Exception as e:
            self.logger.error("Failed to generate additional files: %s", e)
            return False

    def _create_readme_content(self, keyboard_profile: "KeyboardProfile") -> str:
        """Create README.md content for the workspace.

        Args:
            keyboard_profile: Keyboard profile for metadata

        Returns:
            str: README.md content
        """
        return f"""# {keyboard_profile.keyboard_config.description}

ZMK configuration workspace generated by Glovebox.

## Keyboard Information

- **Keyboard**: {keyboard_profile.keyboard_name}
- **Vendor**: {keyboard_profile.keyboard_config.vendor}
- **Key Count**: {keyboard_profile.keyboard_config.key_count}
- **Generated**: Dynamically by Glovebox

## Building

This workspace uses the ZMK build system with west.

```bash
# Initialize workspace
west init -l config

# Update dependencies
west update

# Export Zephyr for CMake
west zephyr-export

# Build firmware
west build -s zmk/app -p always -b nice_nano_v2 -d build/left -- -DSHIELD={keyboard_profile.keyboard_name}_left
west build -s zmk/app -p always -b nice_nano_v2 -d build/right -- -DSHIELD={keyboard_profile.keyboard_name}_right
```

## Generated by Glovebox

This workspace was automatically generated by [Glovebox](https://github.com/your-repo/glovebox)
for dynamic ZMK firmware compilation.
"""

    def _generate_west_config_file(self, params: ZmkConfigFileParams) -> bool:
        """Generate .west/config file for west workspace configuration.

        Args:
            params: File generation parameters

        Returns:
            bool: True if .west/config generated successfully
        """
        try:
            # Determine config path relative to workspace using Docker paths
            config_dir = params.config_directory_host
            try:
                config_rel_path = str(config_dir.relative_to(params.workspace_path))
            except ValueError:
                # If config_dir is not relative to workspace, use absolute path
                config_rel_path = str(config_dir)

            # Create west workspace config using typed approach
            west_config = WestWorkspaceConfig.create_default(
                config_path=config_rel_path, zephyr_base=params.zephyr_base_path
            )

            # Create .west directory
            west_dir = params.workspace_path / ".west"
            if self.file_adapter:
                self.file_adapter.create_directory(west_dir)
            else:
                west_dir.mkdir(parents=True, exist_ok=True)

            # Generate and write .west/config file
            west_config_content = west_config.to_ini_string()
            west_config_path = west_dir / "config"

            if self.file_adapter:
                self.file_adapter.write_text(west_config_path, west_config_content)
            else:
                west_config_path.write_text(west_config_content)

            self.logger.debug("Generated .west/config at %s", west_config_path)
            return True

        except Exception as e:
            self.logger.error("Failed to generate .west/config: %s", e)
            return False

    def update_for_layout_changes(
        self,
        params: ZmkConfigGenerationParams,
    ) -> bool:
        """Update workspace files when layout changes.

        Args:
            params: Generation parameters with updated source files

        Returns:
            bool: True if update successful
        """
        try:
            self.logger.info("Updating ZMK config workspace for layout changes")

            # Create file-specific parameters for helper methods
            file_params = ZmkConfigFileParams(
                workspace_path=params.workspace_path,
                keyboard_profile=params.keyboard_profile,
                shield_name=params.effective_shield_name,
                docker_paths=params.docker_paths,
                board_name=params.board_name,
                zephyr_base_path=params.zephyr_base_path,
            )

            # Update keymap and config files in workspace
            return self._setup_config_directory(params, file_params)

        except Exception as e:
            msg = f"Failed to update ZMK config workspace: {e}"
            self.logger.error(msg)
            raise ZmkConfigGenerationError(msg) from e


def create_zmk_config_content_generator(
    file_adapter: FileAdapter | None = None,
) -> ZmkConfigContentGenerator:
    """Create ZMK config content generator instance.

    Args:
        file_adapter: File operations adapter

    Returns:
        ZmkConfigContentGenerator: New generator instance
    """
    return ZmkConfigContentGenerator(file_adapter=file_adapter)
