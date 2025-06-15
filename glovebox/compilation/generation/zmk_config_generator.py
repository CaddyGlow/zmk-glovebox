"""ZMK Config content generator for dynamic workspace creation."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from glovebox.adapters import FileAdapter
from glovebox.compilation.configuration import create_build_matrix_resolver
from glovebox.compilation.models.build_matrix import BuildTargetConfig, BuildYamlConfig
from glovebox.compilation.models.compilation_params import (
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
        self.build_matrix_resolver = create_build_matrix_resolver()
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

            # Generate build.yaml using BuildMatrixResolver
            if not self._generate_build_yaml(params):
                return False

            # Generate west.yml for workspace configuration
            if not self._generate_west_yml(params):
                return False

            # Create config directory and copy keymap/config files
            if not self._setup_config_directory(params):
                return False

            # Generate additional files for compatibility
            if not self._generate_additional_files(params):
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

    def _generate_build_yaml(self, params: ZmkConfigGenerationParams) -> bool:
        """Generate build.yaml file using BuildMatrixResolver.

        Args:
            params: Generation parameters

        Returns:
            bool: True if build.yaml generated successfully
        """
        build_yaml_path = params.workspace_path / "build.yaml"

        try:
            # Use BuildMatrixResolver to write the build configuration
            self.build_matrix_resolver.write_config_to_yaml(
                params.build_config, build_yaml_path
            )

            self.logger.debug("Generated build.yaml at %s", build_yaml_path)
            return True
        except Exception as e:
            self.logger.error("Failed to generate build.yaml: %s", e)
            return False

    def _generate_west_yml(self, params: ZmkConfigGenerationParams) -> bool:
        """Generate west.yml for ZMK workspace configuration using WestManifestConfig.

        Args:
            params: Generation parameters

        Returns:
            bool: True if west.yml generated successfully
        """
        west_config = self._create_west_config(params.repo, params.branch)

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
        self,
        repository: str,
        branch: str,
    ) -> WestManifestConfig:
        """Create WestManifestConfig from repository and branch.

        Args:
            repository: ZMK repository (org/repo format or full URL)
            branch: Git branch to use

        Returns:
            WestManifestConfig: West manifest configuration
        """
        # Extract repository name and organization from URL or org/repo format
        if repository.startswith("https://github.com/"):
            repo_path = repository.replace("https://github.com/", "")
            org_name, repo_name = repo_path.split("/")
        elif "/" in repository:
            # Handle org/repo format (e.g., "moergo-sc/zmk")
            org_name, repo_name = repository.split("/")
        else:
            # Fallback for unknown formats
            org_name = "zmkfirmware"
            repo_name = "zmk"

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
        params: ZmkConfigGenerationParams,
    ) -> bool:
        """Setup config directory with keymap and config files.

        Args:
            params: Generation parameters with source files

        Returns:
            bool: True if config directory setup successfully
        """
        # Always create workspace config directory for west.yml
        workspace_config_dir = params.workspace_config_directory_host

        # Get config directory from Docker paths
        config_dir = params.config_directory_host

        # Get shield name from build config
        shields = params.build_config.get_shields()
        shield_name = shields[0] if shields else params.keyboard_profile.keyboard_name

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
            keymap_dest = config_dir / f"{shield_name}.keymap"
            if self.file_adapter:
                keymap_content = self.file_adapter.read_text(params.keymap_file)
                self.file_adapter.write_text(keymap_dest, keymap_content)
            else:
                keymap_content = params.keymap_file.read_text()
                keymap_dest.write_text(keymap_content)

            # Copy config file
            config_dest = config_dir / f"{shield_name}.conf"
            if self.file_adapter:
                config_content = self.file_adapter.read_text(params.config_file)
                self.file_adapter.write_text(config_dest, config_content)
            else:
                config_content = params.config_file.read_text()
                config_dest.write_text(config_content)

            self.logger.debug("Copied keymap and config files to %s", config_dir)
            return True

        except Exception as e:
            self.logger.error("Failed to setup config directory: %s", e)
            return False

    def _generate_additional_files(self, params: ZmkConfigGenerationParams) -> bool:
        """Generate additional files for workspace compatibility.

        Args:
            params: Generation parameters

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

    def _generate_west_config_file(self, params: ZmkConfigGenerationParams) -> bool:
        """Generate .west/config file for west workspace configuration.

        Args:
            params: Generation parameters

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

            # Update keymap and config files in workspace
            return self._setup_config_directory(params)

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
